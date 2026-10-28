"""
Standalone CLI runner for Shot Boundary Detection (Stage 1).
Supports single video and batch directory processing with fault-tolerant checkpointing.
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional
import cv2
from loguru import logger

from src.common.config import ConfigManager
from src.extractors.shots import ShotDetector
from src.indexers.metadata_db import MetadataDB


def parse_args() -> argparse.Namespace:
    """Parses command-line arguments for shot boundary detection runner."""
    parser = argparse.ArgumentParser(
        description="Stage 1 Runner: Shot Boundary Detection with SceneDetect."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--video-id",
        type=str,
        help="Process a single video ID (e.g. L13_V001). Looks in data/raw_videos/."
    )
    group.add_argument(
        "--video-dir",
        type=str,
        help="Process all video files in the specified directory (e.g. data/raw_videos/)."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/default_config.yaml",
        help="Path to YAML configuration file."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-extraction and overwrite existing shots even if stage completed."
    )
    return parser.parse_args()


def validate_raw_video(video_path: Path) -> bool:
    """Pre-flight check to verify video file existence, non-zero size, and readable container."""
    if not video_path.exists():
        logger.error(f"[ERROR] Video file does not exist: {video_path}")
        return False
    if video_path.stat().st_size < 1024:
        logger.error(f"[ERROR] Video file is corrupted or empty (size < 1KB): {video_path}")
        return False

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        logger.error(f"[ERROR] OpenCV could not open video container: {video_path}")
        return False
    cap.release()
    return True


def rollback_shots(db: MetadataDB, video_id: str) -> None:
    """Rollback handler: purges partial shot and keyframe records upon failure."""
    logger.warning(f"[WARNING] Rolling back partial shot records for {video_id}...")
    try:
        db.delete_shots(video_id)
    except Exception as e:
        logger.error(f"[ERROR] Failed to rollback shots for {video_id}: {e}")


def process_video(
    detector: ShotDetector,
    db: MetadataDB,
    video_path: Path,
    force: bool = False
) -> bool:
    """Processes shot detection for a single video with atomic checkpointing."""
    video_id = video_path.stem

    # 1. Idempotency Check
    if not force and db.is_stage_completed(video_id, "shots"):
        logger.info(f"[SKIP] Shot detection already COMPLETED for {video_id}.")
        return True

    # 2. Pre-flight Dependency Guard
    if not validate_raw_video(video_path):
        db.set_checkpoint(video_id, "shots", "FAILED", error_message="Corrupted or unreadable video file.")
        return False

    # 3. Clean slate if forcing
    if force:
        rollback_shots(db, video_id)

    # 4. Atomic Execution
    db.set_checkpoint(video_id, "shots", "IN_PROGRESS")
    try:
        shots = detector.extract(str(video_path), force_recompute=True)
        logger.info(f"[DONE] Successfully detected {len(shots)} shots for {video_id}.")
        return True
    except KeyboardInterrupt:
        logger.error(f"[INTERRUPT] Shot detection interrupted by user for {video_id}.")
        rollback_shots(db, video_id)
        db.set_checkpoint(video_id, "shots", "FAILED", error_message="Interrupted by user (SIGINT).")
        raise
    except Exception as e:
        logger.error(f"[ERROR] Shot detection failed for {video_id}: {e}")
        rollback_shots(db, video_id)
        db.set_checkpoint(video_id, "shots", "FAILED", error_message=str(e))
        return False


def main() -> int:
    """Main CLI entry point for Stage 1."""
    args = parse_args()
    cfg = ConfigManager(args.config).config
    db = MetadataDB(cfg.get("paths", {}).get("metadata_db", "data/metadata.db"))
    detector = ShotDetector(config=cfg, db=db)

    raw_videos_dir = Path(cfg.get("paths", {}).get("raw_videos_dir", "data/raw_videos"))

    if args.video_id:
        # Single video execution
        target_path = None
        for ext in [".mp4", ".mkv", ".avi"]:
            p = raw_videos_dir / f"{args.video_id}{ext}"
            if p.exists():
                target_path = p
                break

        if not target_path:
            logger.error(f"[ERROR] Could not find video '{args.video_id}' in {raw_videos_dir}.")
            return 1

        success = process_video(detector, db, target_path, force=args.force)
        return 0 if success else 1

    else:
        # Directory batch execution
        v_dir = Path(args.video_dir)
        if not v_dir.exists() or not v_dir.is_dir():
            logger.error(f"[ERROR] Specified video directory does not exist: {v_dir}")
            return 1

        video_files = sorted([
            f for f in v_dir.iterdir()
            if f.suffix.lower() in [".mp4", ".mkv", ".avi"] and not f.name.startswith(".")
        ])

        summary = {"total": len(video_files), "completed": 0, "skipped": 0, "failed": 0}
        logger.info(f"[INFO] Starting batch shot detection on {len(video_files)} videos in {v_dir}...")

        for vid_path in video_files:
            video_id = vid_path.stem
            if not args.force and db.is_stage_completed(video_id, "shots"):
                logger.info(f"[SKIP] Shot detection already COMPLETED for {video_id}.")
                summary["skipped"] += 1
                continue

            try:
                ok = process_video(detector, db, vid_path, force=args.force)
                if ok:
                    summary["completed"] += 1
                else:
                    summary["failed"] += 1
            except KeyboardInterrupt:
                logger.warning("[WARNING] Batch processing aborted by user.")
                break

        logger.info(
            f"[SUMMARY] Shot Detection Batch Complete | Total: {summary['total']} | "
            f"Completed: {summary['completed']} | Skipped: {summary['skipped']} | Failed: {summary['failed']}"
        )
        return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

