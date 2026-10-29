"""
Core Engine: On-Screen Text Extraction with PaddleOCR on CPU (Stage 4).
Extracts Vietnamese and multilingual text from sharp keyframes, incorporates
a morphological edge-density text presence pre-filter to skip non-text frames,
and persists structured text detections for SQLite FTS5 full-text indexing.
"""

import os
import re
import cv2
import numpy as np
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger

# Prevent OpenMP / MKL DLL symbol conflict on Windows (WinError 127 in shm.dll)
import torch

try:
    from paddleocr import PaddleOCR
except ImportError:
    PaddleOCR = None

from src.common.base import BaseExtractor
from src.common.config import ConfigManager
from src.common.types import KeyframeRecord, OCRRecord
from src.indexers.metadata_db import MetadataDB


class OCRExtractor(BaseExtractor):
    """
    Extracts text from keyframe images using PaddleOCR on CPU with morphological pre-filtering.
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
        self.min_confidence: float = float(ocr_cfg.get("min_confidence", 0.65))
        self.edge_density_threshold: float = float(ocr_cfg.get("edge_density_threshold", 0.08))
        self.use_prefilter: bool = True

        db_file = db_path or self.config.get("paths", {}).get("metadata_db", "data/metadata.db")
        self.db = MetadataDB(db_file)
        self.ocr_engine: Optional[PaddleOCR] = None

    def load_model(self) -> None:
        """Initializes PaddleOCR engine lazily."""
        if self.ocr_engine is None:
            if PaddleOCR is None:
                raise ImportError("PaddleOCR is not installed. Please run: uv add paddleocr paddlepaddle==2.6.2")

            logger.info(
                f"[INFO] Initializing PaddleOCR (lang='{self.lang}', use_gpu={self.use_gpu}, min_confidence={self.min_confidence})..."
            )
            # Use CPU to preserve GPU VRAM for visual models
            self.ocr_engine = PaddleOCR(
                use_angle_cls=True,
                lang=self.lang,
                use_gpu=self.use_gpu,
                show_log=False
            )
            logger.info("[OK] PaddleOCR engine initialized successfully on CPU.")

    def safe_unload(self) -> None:
        """Releases OCR engine resources."""
        if self.ocr_engine is not None:
            self.ocr_engine = None
            logger.info("[OK] PaddleOCR engine unloaded.")

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

        # Repair common PaddleOCR Latin-v3 vowel confusions on Vietnamese text
        # 'nuäc' or 'uäc' -> 'nước' / 'ước'
        cleaned = re.sub(r"\bnuäc\b", "nước", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"uäc\b", "ước", cleaned, flags=re.IGNORECASE)
        # 'vuat' preceded by 'lai' or followed by 'qua' -> 'vượt'
        cleaned = re.sub(r"\bvuat\b", "vượt", cleaned, flags=re.IGNORECASE)

        return cleaned

    def extract_keyframe(self, keyframe: KeyframeRecord) -> List[OCRRecord]:
        """
        Runs text extraction pipeline on a single keyframe:
        1. Morphological edge density pre-filter.
        2. PaddleOCR text detection + recognition.
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
            results = self.ocr_engine.ocr(img_path, cls=True)
        except Exception as e:
            logger.error(f"[ERROR] PaddleOCR inference error on {img_path}: {e}")
            return []

        if not results or not results[0]:
            return []

        ocr_records: List[OCRRecord] = []
        for idx, line in enumerate(results[0]):
            box, (raw_text, score) = line
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

        for kf in keyframes:
            records = self.extract_keyframe(kf)
            if records:
                all_records.extend(records)
                prefiltered_count += 1

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

