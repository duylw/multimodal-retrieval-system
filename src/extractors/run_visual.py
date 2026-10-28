"""
Standalone CLI runner for Visual SigLIP2 Feature Extraction (Stage 3).
Extracts dense keyframe and shot-pooled embeddings, persists per-video .npz feature caches,
and manages GPU VRAM lifecycle with fault tolerance.
"""

import argparse
import io
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional
import numpy as np
from loguru import logger

from src.common.config import ConfigManager
from src.extractors.visual import VisualExtractor
from src.indexers.metadata_db import MetadataDB

# Ensure UTF-8 output encoding on Windows terminals
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def parse_args() -> argparse.Namespace:
    """Parses command-line arguments for visual feature extraction runner."""
    parser = argparse.ArgumentParser(
        description="Stage 3 Runner: Visual SigLIP2 Feature Extraction & Per-Video Feature Caching."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--video-id",
        type=str,
        help="Process a single video ID (e.g. L13_V001)."
    )
    group.add_argument(
        "--video-dir",
        type=str,
        help="Process all video files in the specified directory."
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
        help="Force re-extraction and overwrite existing feature cache even if stage completed."
    )
    return parser.parse_args()


def rollback_visual(feature_cache_path: Path) -> None:
    """Rollback handler: deletes partial feature cache file upon failure."""
    logger.warning(f"[WARNING] Rolling back visual feature cache: {feature_cache_path}...")
    try:
        if feature_cache_path.exists():
            feature_cache_path.unlink()
    except Exception as e:
        logger.error(f"[ERROR] Failed to delete partial feature cache {feature_cache_path}: {e}")


def process_video(
    extractor: VisualExtractor,
    db: MetadataDB,
    video_id: str,
    feature_dir: Path,
    force: bool = False
) -> bool:
    """Processes visual embedding extraction for a single video with pre-flight guard and rollback."""
    feature_cache_path = feature_dir / f"{video_id}.npz"

    # 1. Idempotency Check
    if not force and db.is_stage_completed(video_id, "visual") and feature_cache_path.exists():
        logger.info(f"[SKIP] Visual feature extraction already COMPLETED for {video_id}.")
        return True

    # 2. Pre-flight Dependency Guard: Keyframes stage must be COMPLETED
    if not db.is_stage_completed(video_id, "keyframes"):
        logger.error(
            f"[ERROR] Prerequisite not met: Stage 'keyframes' is not COMPLETED for {video_id}. "
            f"Please run: uv run python -m src.extractors.run_keyframes --video-id {video_id} first."
        )
        db.set_checkpoint(video_id, "visual", "FAILED", error_message="Prerequisite 'keyframes' not completed.")
        return False

    shots = db.get_shots(video_id)
    keyframes = db.get_keyframes(video_id)
    if not keyframes:
        logger.error(f"[ERROR] Zero keyframes found in database for {video_id}.")
        db.set_checkpoint(video_id, "visual", "FAILED", error_message="Zero keyframes found in database.")
        return False

    # 3. Clean slate if forcing
    if force:
        rollback_visual(feature_cache_path)

    # 4. Atomic Execution
    db.set_checkpoint(video_id, "visual", "IN_PROGRESS")
    try:
        embeddings, metadata = extractor.extract_and_pool(video_id, shots, keyframes)
        if len(embeddings) == 0:
            raise ValueError(f"Extracted 0 embeddings for {video_id}.")

        # Save compressed per-video numpy feature cache
        feature_dir.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            feature_cache_path,
            embeddings=embeddings.astype(np.float32),
            metadata_json=json.dumps(metadata)
        )

        db.set_checkpoint(video_id, "visual", "COMPLETED", artifact_count=len(embeddings))
        logger.info(
            f"[DONE] Saved visual feature cache to {feature_cache_path} "
            f"({len(embeddings)} vectors, dim={embeddings.shape[1]})."
        )
        return True
    except KeyboardInterrupt:
        logger.error(f"[INTERRUPT] Visual extraction interrupted by user for {video_id}.")
        rollback_visual(feature_cache_path)
        db.set_checkpoint(video_id, "visual", "FAILED", error_message="Interrupted by user (SIGINT).")
        raise
    except Exception as e:
        logger.error(f"[ERROR] Visual extraction failed for {video_id}: {e}")
        rollback_visual(feature_cache_path)
        db.set_checkpoint(video_id, "visual", "FAILED", error_message=str(e))
        return False


def main() -> int:
    """Main CLI entry point for Stage 3."""
    args = parse_args()
    cfg = ConfigManager(args.config).config
    db = MetadataDB(cfg.get("paths", {}).get("metadata_db", "data/metadata.db"))
    extractor = VisualExtractor(config=cfg)

    raw_videos_dir = Path(cfg.get("paths", {}).get("raw_videos_dir", "data/raw_videos"))
    feature_dir = Path(cfg.get("paths", {}).get("features_dir", "data/features")) / "visual"
    feature_dir.mkdir(parents=True, exist_ok=True)

    try:
        if args.video_id:
            success = process_video(extractor, db, args.video_id, feature_dir, force=args.force)
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
            logger.info(f"[INFO] Starting batch visual extraction on {len(video_files)} videos...")

            for vid_path in video_files:
                video_id = vid_path.stem
                if not args.force and db.is_stage_completed(video_id, "visual"):
                    cache_file = feature_dir / f"{video_id}.npz"
                    if cache_file.exists():
                        logger.info(f"[SKIP] Visual extraction already COMPLETED for {video_id}.")
                        summary["skipped"] += 1
                        continue

                try:
                    ok = process_video(extractor, db, video_id, feature_dir, force=args.force)
                    if ok:
                        summary["completed"] += 1
                    else:
                        summary["failed"] += 1
                except KeyboardInterrupt:
                    logger.warning("[WARNING] Batch processing aborted by user.")
                    break

            logger.info(
                f"[SUMMARY] Visual Extraction Batch Complete | Total: {summary['total']} | "
                f"Completed: {summary['completed']} | Skipped: {summary['skipped']} | Failed: {summary['failed']}"
            )
            return 0 if summary["failed"] == 0 else 1

    finally:
        # Mandatory GPU VRAM cleanup in finally block
        extractor.safe_unload()


if __name__ == "__main__":
    sys.exit(main())

