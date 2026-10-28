"""
Visual feature extractor using Google's SigLIP / SigLIP2 vision-language foundation models.
Implements FP16 batch inference, L2 normalization, shot-level mean pooling, and strict GPU memory cleanup.
"""

import gc
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
from loguru import logger
from PIL import Image

from src.common.base import BaseExtractor
from src.common.config import ConfigManager
from src.common.types import KeyframeRecord, ShotRecord
from src.indexers.metadata_db import MetadataDB


class VisualExtractor(BaseExtractor):
    """
    Extracts L2-normalized dense visual embeddings from keyframe images and text queries.
    Enforces VRAM-safe batching (batch_size=4 or 8) and provides automatic fallback.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        if config is None:
            config = ConfigManager().to_dict()
        super().__init__(config)

        self.db = MetadataDB(self.config.get("paths", {}).get("metadata_db", "data/metadata.db"))
        self.visual_cfg = self.config.get("visual_model", {})
        self.primary_model_name = self.visual_cfg.get(
            "primary_model", "google/siglip2-so400m-patch14-384"
        )
        self.fallback_model_name = self.visual_cfg.get(
            "fallback_model", "google/siglip2-base-patch16-256"
        )
        self.batch_size = self.visual_cfg.get("batch_size", 4)
        self.use_fp16 = self.visual_cfg.get("use_fp16", True)

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = None
        self.processor = None
        self.current_model_name = None
        self.embedding_dim = 1152 if "so400m" in self.primary_model_name else 768

    def load_model(self, model_name: Optional[str] = None) -> None:
        """
        Loads the SigLIP vision-language model into GPU VRAM (or CPU fallback).
        """
        if self.model is not None and (model_name is None or model_name == self.current_model_name):
            return

        from transformers import AutoModel, AutoProcessor

        target_model = model_name or self.primary_model_name
        logger.info(f"[INFO] Loading visual model '{target_model}' on device: {self.device} (fp16={self.use_fp16})")

        dtype = torch.float16 if (self.use_fp16 and self.device == "cuda") else torch.float32

        try:
            self.processor = AutoProcessor.from_pretrained(target_model)
            self.model = AutoModel.from_pretrained(target_model, torch_dtype=dtype).to(self.device)
            self.model.eval()
            self.current_model_name = target_model

            # Determine actual embedding dimension from vision projection
            if hasattr(self.model, "vision_model") and hasattr(self.model.vision_model, "config"):
                self.embedding_dim = getattr(
                    self.model.config, "projection_dim", self.model.vision_model.config.hidden_size
                )
            logger.info(f"[OK] Visual model loaded successfully. Embedding dimension: {self.embedding_dim}")

        except Exception as e:
            if target_model != self.fallback_model_name:
                logger.warning(
                    f"[WARNING] Failed to load primary model '{target_model}': {e}. Falling back to '{self.fallback_model_name}'"
                )
                self.safe_unload()
                self.batch_size = 16
                self.load_model(self.fallback_model_name)
            else:
                logger.error(f"[ERROR] Failed to load fallback model: {e}")
                raise e

    def safe_unload(self) -> None:
        """
        Releases GPU VRAM occupied by the model and clears PyTorch caches.
        """
        if self.model is not None:
            del self.model
            self.model = None
        if self.processor is not None:
            del self.processor
            self.processor = None

        self.current_model_name = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
        logger.info("[OK] Visual model unloaded. GPU VRAM released.")

    def extract_image_embeddings(self, image_paths: List[str]) -> np.ndarray:
        """
        Extracts L2-normalized embeddings for a list of image file paths.

        Args:
            image_paths: List of absolute or relative paths to image files.

        Returns:
            Float32 numpy array of shape (N, embedding_dim).
        """
        self.load_model()
        if not image_paths:
            return np.empty((0, self.embedding_dim), dtype=np.float32)

        all_embeddings = []
        dtype = torch.float16 if (self.use_fp16 and self.device == "cuda") else torch.float32

        for i in range(0, len(image_paths), self.batch_size):
            batch_paths = image_paths[i : i + self.batch_size]
            batch_images = []
            for p in batch_paths:
                try:
                    img = Image.open(p).convert("RGB")
                    batch_images.append(img)
                except Exception as err:
                    logger.warning(f"[WARNING] Failed to open image {p}: {err}. Using black blank.")
                    batch_images.append(Image.new("RGB", (384, 384), (0, 0, 0)))

            inputs = self.processor(images=batch_images, return_tensors="pt").to(self.device)
            if dtype == torch.float16:
                inputs = {k: v.to(dtype) if torch.is_floating_point(v) else v for k, v in inputs.items()}

            with torch.inference_mode():
                if hasattr(self.model, "get_image_features"):
                    features = self.model.get_image_features(**inputs)
                else:
                    outputs = self.model(**inputs)
                    features = outputs.image_embeds if hasattr(outputs, "image_embeds") else outputs[0]

                features_np = features.detach().cpu().to(torch.float32).numpy()

                norms = np.linalg.norm(features_np, axis=-1, keepdims=True)
                norms[norms == 0] = 1e-12
                normed = features_np / norms

                all_embeddings.append(normed)

        return np.vstack(all_embeddings)

    def extract_text_embedding(self, query: str) -> np.ndarray:
        """
        Encodes a single natural language text query into an L2-normalized dense vector.

        Args:
            query: User search text query.

        Returns:
            Float32 numpy array of shape (1, embedding_dim).
        """
        self.load_model()
        inputs = self.processor(text=[query], return_tensors="pt", padding="max_length").to(self.device)

        with torch.inference_mode():
            if hasattr(self.model, "get_text_features"):
                features = self.model.get_text_features(**inputs)
            else:
                outputs = self.model(**inputs)
                features = outputs.text_embeds if hasattr(outputs, "text_embeds") else outputs[0]

            feat_np = features.detach().cpu().to(torch.float32).numpy()
            norm = np.linalg.norm(feat_np, axis=-1, keepdims=True)
            if norm > 0:
                feat_np = feat_np / norm

            return feat_np

    def pool_shot_embeddings(
        self,
        shots: List[ShotRecord],
        keyframes: List[KeyframeRecord],
        keyframe_embeddings: np.ndarray,
    ) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        """
        Computes shot-level average embeddings via mean pooling across intra-shot keyframes.

        Args:
            shots: List of shot records.
            keyframes: List of keyframe records corresponding to the embeddings array.
            keyframe_embeddings: Numpy array of keyframe vectors.

        Returns:
            Tuple of (pooled_embeddings_array, list_of_shot_metadata).
        """
        shot_to_indices = {}
        for idx, kf in enumerate(keyframes):
            shot_to_indices.setdefault(kf.shot_id, []).append(idx)

        pooled_vecs = []
        pooled_meta = []

        for shot in shots:
            indices = shot_to_indices.get(shot.shot_id, [])
            if not indices:
                continue

            vecs = keyframe_embeddings[indices]
            mean_vec = np.mean(vecs, axis=0)

            norm = np.linalg.norm(mean_vec)
            if norm > 0:
                mean_vec = mean_vec / norm

            pooled_vecs.append(mean_vec)
            pooled_meta.append({
                "video_id": shot.video_id,
                "shot_id": shot.shot_id,
                "keyframe_id": None,
                "timestamp_sec": round((shot.start_sec + shot.end_sec) / 2.0, 2),
                "start_sec": shot.start_sec,
                "end_sec": shot.end_sec,
                "duration_sec": shot.duration_sec,
                "is_shot_pooled": True,
                "keyframe_count": len(indices),
            })

        if pooled_vecs:
            return np.vstack(pooled_vecs), pooled_meta
        return np.empty((0, self.embedding_dim), dtype=np.float32), []

    def is_already_processed(self, video_id: str) -> bool:
        """Checks whether visual embeddings have already been generated for this video."""
        return self.db.is_stage_completed(video_id, "visual")

    def extract(self, video_path: str, **kwargs) -> List[Any]:
        """Standard BaseExtractor interface."""
        video_id = kwargs.get("video_id", Path(video_path).stem)
        shots = self.db.get_shots(video_id)
        keyframes = self.db.get_keyframes(video_id)
        embeddings, metadata = self.extract_and_pool(video_id, shots, keyframes)
        return metadata

    def extract_and_pool(
        self,
        video_id: str,
        shots: List[ShotRecord],
        keyframes: List[KeyframeRecord],
    ) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        """
        Full visual pipeline for a single video:
        1. Extracts L2-normalized embeddings for all keyframe images.
        2. Computes shot-level pooled embeddings.
        3. Concatenates individual + pooled vectors.
        4. Updates database checkpoint.
        """
        if not keyframes:
            logger.warning(f"[WARNING] No keyframes provided for video {video_id}.")
            return np.empty((0, self.embedding_dim), dtype=np.float32), []

        # 1. Extract individual keyframe vectors
        img_paths = [k.file_path for k in keyframes]
        logger.info(f"[INFO] Extracting SigLIP embeddings for {len(img_paths)} keyframes of '{video_id}'...")

        kf_embeddings = self.extract_image_embeddings(img_paths)

        # Build individual keyframe metadata with shot temporal intervals
        shot_map = {s.shot_id: s for s in shots}
        kf_meta = []
        for k in keyframes:
            shot_rec = shot_map.get(k.shot_id)
            kf_meta.append({
                "video_id": k.video_id,
                "shot_id": k.shot_id,
                "keyframe_id": k.keyframe_id,
                "timestamp_sec": k.timestamp_sec,
                "start_sec": shot_rec.start_sec if shot_rec else k.timestamp_sec,
                "end_sec": shot_rec.end_sec if shot_rec else k.timestamp_sec,
                "file_path": k.file_path,
                "is_shot_center": k.is_shot_center,
                "blur_score": k.blur_score,
                "is_shot_pooled": False,
            })

        # 2. Compute shot-level pooled vectors
        pooled_embeddings, pooled_meta = self.pool_shot_embeddings(shots, keyframes, kf_embeddings)

        # 3. Concatenate vectors and metadata
        all_embeddings = np.vstack([kf_embeddings, pooled_embeddings])
        all_metadata = kf_meta + pooled_meta

        # 4. Mark checkpoint in SQLite
        self.db.set_checkpoint(video_id, "visual", "COMPLETED", artifact_count=len(all_embeddings))
        logger.info(
            f"[OK] Completed visual embedding for '{video_id}': {len(kf_embeddings)} keyframe vectors + {len(pooled_embeddings)} shot pooled vectors. Total: {len(all_embeddings)}"
        )

        return all_embeddings, all_metadata
