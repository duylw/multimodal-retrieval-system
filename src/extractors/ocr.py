"""
Core Engine: On-Screen Text Extraction with EasyOCR on CPU (Stage 4).
Extracts Vietnamese and multilingual text from sharp keyframes, incorporates
a morphological edge-density text presence pre-filter to skip non-text frames,
and persists structured text detections for SQLite FTS5 full-text indexing.
"""

import os
import re
import gc
import cv2
import numpy as np
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger
import torch

try:
    import easyocr
except ImportError:
    easyocr = None

from src.common.base import BaseExtractor
from src.common.config import ConfigManager
from src.common.types import KeyframeRecord, OCRRecord
from src.indexers.metadata_db import MetadataDB


class OCRExtractor(BaseExtractor):
    """
    Extracts text from keyframe images using EasyOCR on CPU with morphological pre-filtering.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        db_path: Optional[str] = None
    ):
        if config is None:
            config = ConfigManager().config
        super().__init__(config)

        ocr_cfg = self.config.get("ocr_model", {})
        self.lang: str = ocr_cfg.get("language", "vi")
        self.use_gpu: bool = bool(ocr_cfg.get("use_gpu", False))
        self.model_dir: str = str(Path(ocr_cfg.get("model_dir", "models/easyocr")).resolve())
        self.min_confidence: float = float(ocr_cfg.get("min_confidence", 0.60))
        self.edge_density_threshold: float = float(ocr_cfg.get("edge_density_threshold", 0.08))
        self.use_prefilter: bool = True

        db_file = db_path or self.config.get("paths", {}).get("metadata_db", "data/metadata.db")
        self.db = MetadataDB(db_file)
        self.ocr_engine: Optional[Any] = None

    def load_model(self) -> None:
        """Initializes EasyOCR engine lazily."""
        if self.ocr_engine is None:
            if easyocr is None:
                raise ImportError("EasyOCR is not installed. Please run: uv add easyocr")

            os.makedirs(self.model_dir, exist_ok=True)
            logger.info(
                f"[INFO] Initializing EasyOCR (lang=['{self.lang}'], use_gpu={self.use_gpu}, "
                f"model_dir='{self.model_dir}', min_confidence={self.min_confidence})..."
            )
            # Use CPU to preserve GPU VRAM for visual models
            self.ocr_engine = easyocr.Reader(
                lang_list=[self.lang],
                gpu=self.use_gpu,
                model_storage_directory=self.model_dir,
                download_enabled=True,
                verbose=False
            )
            logger.info("[OK] EasyOCR engine initialized successfully.")

    def safe_unload(self) -> None:
        """
        Releases OCR engine resources, flushes PyTorch CUDA caches, and forces garbage collection.
        """
        if self.ocr_engine is not None:
            del self.ocr_engine
            self.ocr_engine = None

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            if hasattr(torch.cuda, "ipc_collect"):
                torch.cuda.ipc_collect()
        logger.info("[OK] EasyOCR engine unloaded. GPU VRAM and host RAM released.")

    def compute_edge_density(self, img_path: str) -> float:
        """
        Computes morphological vertical/horizontal edge density on grayscale image.
        Uses Canny edge detection followed by rectangular morphological closing to cluster text strokes.
        """
        gray = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        if gray is None:
            return 0.0

        edges = cv2.Canny(gray, 100, 200)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 3))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
        density = float(np.count_nonzero(closed) / (gray.shape[0] * gray.shape[1]))
        return density

    def has_text_prefilter(self, img_path: str) -> Tuple[bool, float]:
        """
        Quickly screens keyframe for candidate text presence using edge density.
        Prunes 70-80% of natural/action scenes without calling deep neural networks (< 10ms latency).
        """
        density = self.compute_edge_density(img_path)
        has_text = density >= self.edge_density_threshold
        return has_text, density

    @staticmethod
    def normalize_text(text: str) -> str:
        """Cleans and standardizes extracted OCR text string."""
        if not text:
            return ""
        # Collapse multiple spaces and strip control characters
        cleaned = re.sub(r"[\r\n\t]+", " ", text)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def extract_keyframe(self, keyframe: KeyframeRecord) -> List[OCRRecord]:
        """
        Runs text extraction pipeline on a single keyframe:
        1. Morphological edge density pre-filter.
        2. EasyOCR text detection + Vietnamese recognition.
        3. Confidence filtering and text normalization.
        """
        img_path = keyframe.file_path
        if not Path(img_path).exists():
            logger.warning(f"[WARNING] Keyframe file does not exist: {img_path}")
            return []

        # 1. Text Presence Pre-Filter
        if self.use_prefilter:
            has_text, density = self.has_text_prefilter(img_path)
            if not has_text:
                return []

        # 2. Deep OCR Inference
        self.load_model()
        try:
            results = self.ocr_engine.readtext(img_path)
        except Exception as e:
            logger.error(f"[ERROR] EasyOCR inference error on {img_path}: {e}")
            return []

        if not results:
            return []

        ocr_records: List[OCRRecord] = []
        for idx, item in enumerate(results):
            # EasyOCR returns: (bbox, text, prob)
            box, raw_text, score = item
            confidence = float(score)

            if confidence < self.min_confidence:
                continue

            clean_text = self.normalize_text(raw_text)
            # Filter out single-character non-alphanumeric noise
            if len(clean_text) < 2 and not clean_text.isalnum():
                continue

            # Format bbox coordinates as list of (x, y) tuples
            bbox_coords = [(int(pt[0]), int(pt[1])) for pt in box]

            rec = OCRRecord(
                ocr_id=f"{keyframe.keyframe_id}_ocr_{idx:03d}",
                video_id=keyframe.video_id,
                keyframe_id=keyframe.keyframe_id,
                timestamp_sec=keyframe.timestamp_sec,
                text_detected=clean_text,
                bbox=bbox_coords,
                confidence=round(confidence, 4)
            )
            ocr_records.append(rec)

        return ocr_records

    def extract_video(
        self,
        video_id: str,
        keyframes: List[KeyframeRecord]
    ) -> List[OCRRecord]:
        """
        Executes OCR extraction across all keyframes of a video.
        """
        if not keyframes:
            logger.warning(f"[WARNING] No keyframes provided for video '{video_id}'.")
            return []

        logger.info(f"[INFO] Running on-screen text extraction for {len(keyframes)} keyframes of '{video_id}'...")

        all_records: List[OCRRecord] = []
        prefiltered_count = 0

        for idx, kf in enumerate(keyframes):
            records = self.extract_keyframe(kf)
            if records:
                all_records.extend(records)
                prefiltered_count += 1
            if (idx + 1) % 50 == 0 or (idx + 1) == len(keyframes):
                logger.info(f"[INFO] Processed {idx + 1}/{len(keyframes)} keyframes ({len(all_records)} text items so far)...")

        # Clean intermediate tensor and memory cache after video extraction
        gc.collect()
        if self.use_gpu and torch.cuda.is_available():
            torch.cuda.empty_cache()

        logger.info(
            f"[OK] Completed OCR for '{video_id}': {len(all_records)} text items detected "
            f"across {prefiltered_count}/{len(keyframes)} text-bearing keyframes."
        )
        return all_records

    def extract(self, video_path: str, **kwargs) -> List[OCRRecord]:
        """Standard BaseExtractor interface."""
        video_id = kwargs.get("video_id", Path(video_path).stem)
        keyframes = self.db.get_keyframes(video_id)
        return self.extract_video(video_id, keyframes)

    def is_already_processed(self, video_id: str) -> bool:
        """Checks whether OCR stage has completed for this video."""
        return self.db.is_stage_completed(video_id, "ocr")
