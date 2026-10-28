"""
Standalone CLI runner for Adaptive Keyframe Extraction (Stage 2).
Supports single video and batch directory processing with pre-flight guards and rollback handlers.
"""

import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Suppress low-level FFmpeg/H.264 non-fatal decoder warnings
os.environ["OPENCV_FFMPEG_LOGLEVEL"] = "-8"
os.environ["OPENCV_LOG_LEVEL"] = "OFF"

from loguru import logger

from src.common.config import ConfigManager
from src.extractors.keyframes import KeyframeExtractor
from src.indexers.metadata_db import MetadataDB


def parse_args() -> argparse.Namespace:
    """Parses command-line arguments for keyframe extraction runner."""
    parser = argparse.ArgumentParser(
        description="Stage 2 Runner: Adaptive Keyframe Extraction with Quality Filters."
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
        help="Force re-extraction and overwrite existing keyframes even if stage completed."
    )
    return parser.parse_args()


def rollback_keyframes(db: MetadataDB, video_id: str, keyframes_base_dir: Path) -> None:
    """Rollback handler: purges partial keyframe images and SQLite records upon failure."""
    logger.warning(f"[WARNING] Rolling back partial keyframe artifacts for {video_id}...")
    try:
        db.delete_keyframes(video_id)
        kf_dir = keyframes_base_dir / video_id
        if kf_dir.exists():
            shutil.rmtree(kf_dir, ignore_errors=True)
    except Exception as e:
        logger.error(f"[ERROR] Failed to rollback keyframes for {video_id}: {e}")


def process_video(
    extractor: KeyframeExtractor,
    db: MetadataDB,
    video_path: Path,
    keyframes_base_dir: Path,
    force: bool = False
) -> bool:
    """Processes keyframe extraction for a single video with pre-flight guard and rollback."""
    video_id = video_path.stem

    # 1. Idempotency Check
    if not force and db.is_stage_completed(video_id, "keyframes"):
        logger.info(f"[SKIP] Keyframe extraction already COMPLETED for {video_id}.")
        return True

    # 2. Pre-flight Dependency Guard: Shots stage must be COMPLETED
    if not db.is_stage_completed(video_id, "shots"):
        logger.error(
            f"[ERROR] Prerequisite not met: Stage 'shots' is not COMPLETED for {video_id}. "
            f"Please run: uv run python -m src.extractors.run_shots --video-id {video_id} first."
        )
        db.set_checkpoint(video_id, "keyframes", "FAILED", error_message="Prerequisite 'shots' not completed.")
        return False

    shots = db.get_shots(video_id)
    if not shots:
        logger.error(f"[ERROR] No shots found in database for {video_id}.")
        db.set_checkpoint(video_id, "keyframes", "FAILED", error_message="Zero shots found in database.")
        return False

    # 3. Clean slate if forcing
    if force:
        rollback_keyframes(db, video_id, keyframes_base_dir)

    # 4. Atomic Execution
    db.set_checkpoint(video_id, "keyframes", "IN_PROGRESS")
    try:
        keyframes = extractor.extract(str(video_path), shots=shots, force_recompute=True)
        logger.info(f"[DONE] Successfully extracted {len(keyframes)} keyframes for {video_id}.")
        return True
    except KeyboardInterrupt:
        logger.error(f"[INTERRUPT] Keyframe extraction interrupted by user for {video_id}.")
        rollback_keyframes(db, video_id, keyframes_base_dir)
        db.set_checkpoint(video_id, "keyframes", "FAILED", error_message="Interrupted by user (SIGINT).")
        raise
    except Exception as e:
        logger.error(f"[ERROR] Keyframe extraction failed for {video_id}: {e}")
        rollback_keyframes(db, video_id, keyframes_base_dir)
        db.set_checkpoint(video_id, "keyframes", "FAILED", error_message=str(e))
        return False


def main() -> int:
    """Main CLI entry point for Stage 2."""
    args = parse_args()
    cfg = ConfigManager(args.config).config
    db = MetadataDB(cfg.get("paths", {}).get("metadata_db", "data/metadata.db"))
    extractor = KeyframeExtractor(config=cfg, db=db)

    raw_videos_dir = Path(cfg.get("paths", {}).get("raw_videos_dir", "data/raw_videos"))
    keyframes_base_dir = Path(cfg.get("paths", {}).get("keyframes_dir", "data/keyframes"))

    if args.video_id:
        target_path = None
        for ext in [".mp4", ".mkv", ".avi"]:
            p = raw_videos_dir / f"{args.video_id}{ext}"
            if p.exists():
                target_path = p
                break

        if not target_path:
            logger.error(f"[ERROR] Could not find video '{args.video_id}' in {raw_videos_dir}.")
            return 1

        success = process_video(extractor, db, target_path, keyframes_base_dir, force=args.force)
        return 0 if success else 1

    else:
        v_dir = Path(args.video_dir)
        if not v_dir.exists() or not v_dir.is_dir():
            logger.error(f"[ERROR] Specified video directory does not exist: {v_dir}")
            return 1

        video_files = sorted([
            f for f in v_dir.iterdir()
            if f.suffix.lower() in [".mp4", ".mkv", ".avi"] and not f.name.startswith(".")
        ])

        summary = {"total": len(video_files), "completed": 0, "skipped": 0, "failed": 0}
        logger.info(f"[INFO] Starting batch keyframe extraction on {len(video_files)} videos in {v_dir}...")

        for vid_path in video_files:
            video_id = vid_path.stem
            if not args.force and db.is_stage_completed(video_id, "keyframes"):
                logger.info(f"[SKIP] Keyframe extraction already COMPLETED for {video_id}.")
                summary["skipped"] += 1
                continue

            try:
                ok = process_video(extractor, db, vid_path, keyframes_base_dir, force=args.force)
                if ok:
                    summary["completed"] += 1
                else:
                    summary["failed"] += 1
            except KeyboardInterrupt:
                logger.warning("[WARNING] Batch processing aborted by user.")
                break

        logger.info(
            f"[SUMMARY] Keyframe Extraction Batch Complete | Total: {summary['total']} | "
            f"Completed: {summary['completed']} | Skipped: {summary['skipped']} | Failed: {summary['failed']}"
        )
        return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

