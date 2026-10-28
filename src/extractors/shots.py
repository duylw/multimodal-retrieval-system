"""
Shot boundary detection extractor using SceneDetect with time-based normalization.
Handles diverse video framerates (FPS), frame-skipping downsampling, and SQLite caching.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import cv2
from loguru import logger
from scenedetect import ContentDetector, SceneManager, open_video

from src.common.base import BaseExtractor
from src.common.config import ConfigManager
from src.common.types import ShotRecord
from src.indexers.metadata_db import MetadataDB


class ShotDetector(BaseExtractor):
    """
    Extracts continuous shot boundaries from videos.
    Converts all temporal markers to seconds to remain agnostic to video FPS.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, db: Optional[MetadataDB] = None):
        cfg = config or ConfigManager.get_instance().config
        super().__init__(cfg)
        self.db = db or MetadataDB(self.config.get("paths", {}).get("metadata_db", "data/metadata.db"))

        shot_cfg = self.config.get("shot_detection", {})
        self.method = shot_cfg.get("method", "pyscenedetect")
        self.threshold = float(shot_cfg.get("threshold", 27.0))
        self.min_shot_duration_sec = float(shot_cfg.get("min_shot_duration_sec", 1.0))
        self.target_fps = float(shot_cfg.get("target_fps", 25.0))
        self.high_fps_threshold = float(shot_cfg.get("high_fps_threshold", 30.0))

    def is_already_processed(self, video_id: str) -> bool:
        """Checks if shot boundary detection has already completed for this video."""
        return self.db.is_stage_completed(video_id, "shots")

    def _read_video_metadata(self, video_path: str) -> Dict[str, Any]:
        """Extracts container metadata: dimensions, FPS, frame counts, and duration."""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video file: {video_path}")

        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        finally:
            cap.release()

        if fps <= 0:
            fps = 25.0
        duration_sec = total_frames / fps if fps > 0 else 0.0

        return {
            "fps": fps,
            "total_frames": total_frames,
            "width": width,
            "height": height,
            "duration_sec": duration_sec
        }

    def extract(self, video_path: str, **kwargs) -> List[ShotRecord]:
        """
        Executes shot boundary detection on a video file.

        Args:
            video_path: Path to the input video file.
            **kwargs: Extra execution options (e.g., force_recompute=True).

        Returns:
            List of ShotRecord instances covering the full video timeline.
        """
        path = Path(video_path)
        if not path.exists():
            raise FileNotFoundError(f"Video file not found at: {video_path}")

        video_id = path.stem
        force_recompute = kwargs.get("force_recompute", False)

        # 1. Check SQLite checkpoint for resume
        if not force_recompute and self.is_already_processed(video_id):
            cached_shots = self.db.get_shots(video_id)
            if cached_shots:
                logger.info(f"[INFO] Loaded {len(cached_shots)} cached shots for {video_id} from database.")
                return cached_shots

        # 2. Extract and catalog video metadata
        meta = self._read_video_metadata(str(path))
        fps = meta["fps"]
        total_frames = meta["total_frames"]
        duration_sec = meta["duration_sec"]

        logger.info(
            f"[INFO] Processing {video_id}: {meta['width']}x{meta['height']} @ {fps:.2f} FPS, "
            f"{total_frames} frames ({duration_sec:.2f}s)"
        )

        self.db.save_video(
            video_id=video_id,
            file_name=path.name,
            file_path=str(path.resolve()),
            duration_sec=duration_sec,
            fps=fps,
            width=meta["width"],
            height=meta["height"],
            total_frames=total_frames
        )

        # 3. Configure frame-skipping if input video framerate exceeds threshold
        frame_skip = 0
        if fps > self.high_fps_threshold:
            frame_skip = max(1, round(fps / self.target_fps) - 1)
            effective_fps = fps / (frame_skip + 1)
            logger.info(
                f"[INFO] Normalizing detection framerate from {fps:.1f} FPS to {effective_fps:.1f} FPS "
                f"(frame_skip={frame_skip})."
            )

        # 4. Run scene detection with SceneManager
        threshold_val = self.threshold if self.threshold > 1.0 else 27.0
        detector = ContentDetector(threshold=threshold_val)
        scene_manager = SceneManager()
        scene_manager.add_detector(detector)
        scene_manager.auto_downscale = True

        try:
            video_stream = open_video(str(path))
            scene_manager.detect_scenes(video=video_stream, frame_skip=frame_skip, show_progress=False)
            scene_list = scene_manager.get_scene_list()
        except Exception as e:
            logger.error(f"[ERROR] Scene detection failed for {video_id}: {e}")
            scene_list = []

        shots: List[ShotRecord] = []

        # If no cuts were detected, treat the entire video as one shot
        if not scene_list:
            shots.append(ShotRecord(
                video_id=video_id,
                shot_id=1,
                start_frame=0,
                end_frame=max(0, total_frames - 1),
                start_sec=0.0,
                end_sec=duration_sec,
                duration_sec=duration_sec
            ))
        else:
            shot_id_counter = 1
            for start_time, end_time in scene_list:
                s_frame = start_time.frame_num
                e_frame = end_time.frame_num
                s_sec = start_time.seconds
                e_sec = end_time.seconds
                shot_dur = e_sec - s_sec

                # Filter out microscopic noise flashes (< min_shot_duration_sec)
                if shot_dur < self.min_shot_duration_sec and shots:
                    prev = shots[-1]
                    shots[-1] = ShotRecord(
                        video_id=video_id,
                        shot_id=prev.shot_id,
                        start_frame=prev.start_frame,
                        end_frame=e_frame,
                        start_sec=prev.start_sec,
                        end_sec=e_sec,
                        duration_sec=e_sec - prev.start_sec
                    )
                else:
                    shots.append(ShotRecord(
                        video_id=video_id,
                        shot_id=shot_id_counter,
                        start_frame=s_frame,
                        end_frame=e_frame,
                        start_sec=s_sec,
                        end_sec=e_sec,
                        duration_sec=shot_dur
                    ))
                    shot_id_counter += 1

        # Ensure timeline starts at 0.0s and ends at duration_sec
        if shots:
            if shots[0].start_sec > 0.0:
                shots[0].start_sec = 0.0
                shots[0].start_frame = 0
            if shots[-1].end_sec < duration_sec:
                shots[-1].end_sec = duration_sec
                shots[-1].end_frame = total_frames - 1

        # 5. Persist to SQLite and mark stage complete
        self.db.save_shots(shots)
        self.db.set_checkpoint(video_id, "shots", "COMPLETED", artifact_count=len(shots))
        logger.info(f"[OK] Successfully detected and saved {len(shots)} shots for {video_id}.")

        return shots
