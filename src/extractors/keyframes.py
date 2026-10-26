"""
Adaptive keyframe selection extractor with time-interval sampling,
Laplacian blur filtering, black/blank rejection, and intra-shot deduplication.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np
from loguru import logger

from src.common.base import BaseExtractor
from src.common.config import ConfigManager
from src.common.types import KeyframeRecord, ShotRecord
from src.indexers.metadata_db import MetadataDB


class KeyframeExtractor(BaseExtractor):
    """
    Extracts representative keyframe images from video shots.
    Applies time-based interval selection and multiple quality filters.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, db: Optional[MetadataDB] = None):
        cfg = config or ConfigManager.get_instance().config
        super().__init__(cfg)
        self.db = db or MetadataDB(self.config.get("paths", {}).get("metadata_db", "data/metadata.db"))

        kf_cfg = self.config.get("keyframe_selection", {})
        self.max_keyframes_per_shot = int(kf_cfg.get("max_keyframes_per_shot", 6))
        self.blur_threshold = float(kf_cfg.get("blur_threshold", 80.0))
        self.min_brightness = float(kf_cfg.get("min_brightness", 15.0))
        self.duplicate_similarity = float(kf_cfg.get("duplicate_similarity_threshold", 0.95))
        self.image_max_size = int(kf_cfg.get("image_max_size", 720))
        self.jpeg_quality = int(kf_cfg.get("jpeg_quality", 85))

        self.keyframes_base_dir = Path(self.config.get("paths", {}).get("keyframes_dir", "data/keyframes"))
        self.keyframes_base_dir.mkdir(parents=True, exist_ok=True)

    def is_already_processed(self, video_id: str) -> bool:
        """Checks if keyframe extraction has already completed for this video."""
        return self.db.is_stage_completed(video_id, "keyframes")

    def _compute_blur_score(self, gray_frame: np.ndarray) -> float:
        """Calculates variance of Laplacian to gauge frame sharpness."""
        return float(cv2.Laplacian(gray_frame, cv2.CV_64F).var())

    def _compute_hsv_hist(self, bgr_frame: np.ndarray) -> np.ndarray:
        """Computes normalized 2D HSV color histogram for deduplication."""
        hsv = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [16, 16], [0, 180, 0, 256])
        cv2.normalize(hist, hist, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
        return hist

    def _resize_frame(self, frame: np.ndarray) -> np.ndarray:
        """Resizes frame so longest dimension does not exceed image_max_size."""
        h, w = frame.shape[:2]
        max_dim = max(h, w)
        if max_dim <= self.image_max_size:
            return frame
        scale = self.image_max_size / float(max_dim)
        new_w = int(w * scale)
        new_h = int(h * scale)
        return cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

    def _calculate_sample_timestamps(self, shot: ShotRecord) -> List[Tuple[float, bool]]:
        """
        Determines sample timestamps based on duration in seconds.
        Returns list of (timestamp_sec, is_shot_center).
        """
        dur = shot.duration_sec
        start = shot.start_sec

        if dur < 3.0:
            # Short shot: 1 frame in exact middle
            return [(start + 0.5 * dur, True)]
        elif dur <= 8.0:
            # Medium shot: 2 frames at 33% and 66%
            return [
                (start + 0.33 * dur, False),
                (start + 0.66 * dur, True)
            ]
        else:
            # Long shot: sample every 3.5s, up to max_keyframes_per_shot
            num_samples = min(self.max_keyframes_per_shot, max(2, int(dur / 3.5)))
            step = dur / (num_samples + 1)
            samples = []
            center_idx = num_samples // 2
            for i in range(1, num_samples + 1):
                t = start + i * step
                is_center = (i == center_idx)
                samples.append((t, is_center))
            return samples

    def extract(self, video_path: str, shots: Optional[List[ShotRecord]] = None, **kwargs) -> List[KeyframeRecord]:
        """
        Extracts, filters, and persists keyframe images for all shots in the video.

        Args:
            video_path: Path to the input video file.
            shots: Optional pre-computed shots list. If None, loaded from database.
            **kwargs: Extra execution options (e.g., force_recompute=True).

        Returns:
            List of KeyframeRecord instances saved to disk and database.
        """
        path = Path(video_path)
        video_id = path.stem
        force_recompute = kwargs.get("force_recompute", False)

        # 1. Check SQLite checkpoint for resume
        if not force_recompute and self.is_already_processed(video_id):
            cached_kf = self.db.get_keyframes(video_id)
            if cached_kf:
                logger.info(f"[INFO] Loaded {len(cached_kf)} cached keyframes for {video_id} from database.")
                return cached_kf

        # 2. Retrieve shots
        if not shots:
            shots = self.db.get_shots(video_id)
        if not shots:
            raise ValueError(f"No shot boundaries found for {video_id}. Run ShotDetector first.")

        # 3. Open video reader
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise ValueError(f"Could not open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        output_dir = self.keyframes_base_dir / video_id
        output_dir.mkdir(parents=True, exist_ok=True)

        extracted_keyframes: List[KeyframeRecord] = []
        keyframe_counter = 1

        logger.info(f"[INFO] Extracting adaptive keyframes for {video_id} ({len(shots)} shots)...")

        for shot in shots:
            sample_specs = self._calculate_sample_timestamps(shot)
            previous_hist: Optional[np.ndarray] = None

            for target_sec, is_center in sample_specs:
                target_frame_idx = min(total_frames - 1, max(0, int(round(target_sec * fps))))

                # Seek directly to target frame
                cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame_idx)
                ret, frame = cap.read()
                if not ret or frame is None:
                    continue

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                # Filter 1: Blank / Black frame filter
                brightness = float(np.mean(gray))
                if brightness < self.min_brightness:
                    continue

                # Filter 2: Blur detection with adjacent frame search
                blur_score = self._compute_blur_score(gray)
                best_frame = frame
                best_score = blur_score
                best_frame_idx = target_frame_idx

                if blur_score < self.blur_threshold:
                    # Search +/- 4 frames nearby to find a sharper frame
                    for offset in [-4, -2, 2, 4]:
                        neighbor_idx = target_frame_idx + offset
                        if 0 <= neighbor_idx < total_frames:
                            cap.set(cv2.CAP_PROP_POS_FRAMES, neighbor_idx)
                            n_ret, n_frame = cap.read()
                            if n_ret and n_frame is not None:
                                n_gray = cv2.cvtColor(n_frame, cv2.COLOR_BGR2GRAY)
                                n_score = self._compute_blur_score(n_gray)
                                if n_score > best_score:
                                    best_score = n_score
                                    best_frame = n_frame
                                    best_frame_idx = neighbor_idx

                # Filter 3: Intra-shot deduplication (histogram correlation)
                curr_hist = self._compute_hsv_hist(best_frame)
                if previous_hist is not None:
                    similarity = cv2.compareHist(previous_hist, curr_hist, cv2.HISTCMP_CORREL)
                    if similarity > self.duplicate_similarity:
                        continue  # Skip redundant keyframe within the same shot
                previous_hist = curr_hist

                # Resize and persist keyframe to disk
                resized = self._resize_frame(best_frame)
                actual_sec = best_frame_idx / fps
                kf_filename = f"shot_{shot.shot_id:04d}_t{actual_sec:07.2f}.jpg"
                kf_filepath = output_dir / kf_filename

                encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
                cv2.imwrite(str(kf_filepath), resized, encode_params)

                kf_id = f"{video_id}_{keyframe_counter:05d}"
                extracted_keyframes.append(KeyframeRecord(
                    keyframe_id=kf_id,
                    video_id=video_id,
                    shot_id=shot.shot_id,
                    frame_idx=best_frame_idx,
                    timestamp_sec=actual_sec,
                    file_path=str(kf_filepath.resolve()),
                    is_shot_center=is_center,
                    blur_score=best_score
                ))
                keyframe_counter += 1

        cap.release()

        # 4. Batch persist to SQLite and mark checkpoint
        self.db.save_keyframes(extracted_keyframes)
        self.db.set_stage_status(video_id, "keyframes", "done")

        logger.info(
            f"[OK] Extracted {len(extracted_keyframes)} keyframes for {video_id} "
            f"(Avg: {len(extracted_keyframes)/max(1, len(shots)):.2f} frames/shot)."
        )
        return extracted_keyframes


if __name__ == "__main__":
    sample_video = "data/raw_videos/L13_V001.mp4"
    logger.info(f"[INFO] Testing KeyframeExtractor on sample video: {sample_video}")

    extractor = KeyframeExtractor()
    keyframes = extractor.extract(sample_video, force_recompute=True)

    print(f"\nTotal Keyframes Extracted: {len(keyframes)}")
    print("Sample Keyframes (First 5):")
    for k in keyframes[:5]:
        print(f"  KF ID: {k.keyframe_id} | Shot #{k.shot_id:03d} | Frame: {k.frame_idx:05d} | "
              f"Time: {k.timestamp_sec:06.2f}s | Blur: {k.blur_score:.1f} | Center: {k.is_shot_center} | Path: {Path(k.file_path).name}")
