"""
Standalone CLI runner for On-Screen Text Extraction with EasyOCR (Stage 4).
Screens keyframe images using morphological edge-density filtering, executes
Vietnamese EasyOCR recognition purely on CPU, persists detections into SQLite
relational and FTS5 full-text tables, and manages fault tolerance.
"""

import argparse
import io
import sys
import gc
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger
import torch

from src.common.config import ConfigManager
from src.extractors.ocr import OCRExtractor
from src.indexers.metadata_db import MetadataDB

# Ensure UTF-8 output encoding on Windows terminals
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def parse_args() -> argparse.Namespace:
    """Parses command-line arguments for OCR runner."""
    parser = argparse.ArgumentParser(
        description="Stage 4 Runner: On-Screen Text Extraction via EasyOCR & SQLite FTS5 Indexing."
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
        help="Force re-extraction and overwrite existing OCR records even if stage completed."
    )
    parser.add_argument(
        "--skip-filter",
        action="store_true",
        help="Disable edge-density pre-filter and run EasyOCR on every keyframe."
    )
    device_group = parser.add_mutually_exclusive_group()
    device_group.add_argument(
        "--gpu",
        action="store_true",
        help="Run EasyOCR on GPU (CUDA) for 6-8x speedup (~275MB VRAM footprint)."
    )
    device_group.add_argument(
        "--cpu",
        action="store_true",
        help="Run EasyOCR strictly on CPU (0MB GPU VRAM)."
    )
    return parser.parse_args()


def rollback_ocr(db: MetadataDB, video_id: str) -> None:
    """Rollback handler: removes partial OCR records from database upon failure."""
    logger.warning(f"[WARNING] Rolling back OCR records for {video_id}...")
    try:
        db.delete_ocr_records(video_id)
        logger.info(f"[OK] Cleaned up partial OCR database entries for {video_id}.")
    except Exception as e:
        logger.error(f"[ERROR] Failed to clean up OCR records for {video_id}: {e}")


def process_video(
    extractor: OCRExtractor,
    db: MetadataDB,
    video_id: str,
    force: bool = False
) -> bool:
    """Processes on-screen text extraction for a single video with pre-flight guards and rollback."""
    # 1. Idempotency Check
    if not force and db.is_stage_completed(video_id, "ocr"):
        logger.info(f"[SKIP] OCR text extraction already COMPLETED for {video_id}.")
        return True

    # 2. Pre-flight Dependency Guard: Keyframes stage must be COMPLETED
    if not db.is_stage_completed(video_id, "keyframes"):
        logger.error(
            f"[ERROR] Prerequisite not met: Stage 'keyframes' is not COMPLETED for {video_id}. "
            f"Please run: uv run python -m src.extractors.run_keyframes --video-id {video_id} first."
        )
        db.set_checkpoint(video_id, "ocr", "FAILED", error_message="Prerequisite 'keyframes' not completed.")
        return False

    keyframes = db.get_keyframes(video_id)
    if not keyframes:
        logger.error(f"[ERROR] Zero keyframes found in database for {video_id}.")
        db.set_checkpoint(video_id, "ocr", "FAILED", error_message="Zero keyframes found in database.")
        return False

    # 3. Clean slate before execution (always purge any stale/partial records for this video)
    rollback_ocr(db, video_id)

    # 4. Atomic Execution
    db.set_checkpoint(video_id, "ocr", "IN_PROGRESS")
    try:
        ocr_records = extractor.extract_video(video_id, keyframes)

        # Save to relational table and FTS5 virtual table
        db.save_ocr_records(ocr_records)

        record_count = len(ocr_records)
        del ocr_records
        gc.collect()
        if extractor.use_gpu and torch.cuda.is_available():
            torch.cuda.empty_cache()

        db.set_checkpoint(video_id, "ocr", "COMPLETED", artifact_count=record_count)
        logger.info(
            f"[DONE] Saved {record_count} on-screen text records to SQLite FTS5 for '{video_id}'."
        )
        return True
    except KeyboardInterrupt:
        logger.error(f"[INTERRUPT] OCR extraction interrupted by user for {video_id}.")
        rollback_ocr(db, video_id)
        db.set_checkpoint(video_id, "ocr", "FAILED", error_message="Interrupted by user (SIGINT).")
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        raise
    except Exception as e:
        logger.error(f"[ERROR] OCR extraction failed for {video_id}: {e}")
        rollback_ocr(db, video_id)
        db.set_checkpoint(video_id, "ocr", "FAILED", error_message=str(e))
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        return False


def main() -> int:
    """Main CLI entry point for Stage 4."""
    args = parse_args()
    cfg = ConfigManager(args.config).config
    db = MetadataDB(cfg.get("paths", {}).get("metadata_db", "data/metadata.db"))
    if args.gpu:
        cfg.setdefault("ocr_model", {})["use_gpu"] = True
        logger.info("[INFO] Forcing EasyOCR execution on GPU (CUDA) via CLI flag.")
    elif args.cpu:
        cfg.setdefault("ocr_model", {})["use_gpu"] = False
        logger.info("[INFO] Forcing EasyOCR execution on CPU via CLI flag.")

    extractor = OCRExtractor(config=cfg)

    if args.skip_filter:
        extractor.use_prefilter = False
        logger.info("[INFO] Edge-density text pre-filter disabled by user flag.")

    try:
        if args.video_id:
            success = process_video(extractor, db, args.video_id, force=args.force)
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
            logger.info(f"[INFO] Starting batch on-screen text extraction on {len(video_files)} videos...")

            for idx, vid_path in enumerate(video_files, 1):
                video_id = vid_path.stem
                if not args.force and db.is_stage_completed(video_id, "ocr"):
                    logger.info(f"[SKIP] [{idx}/{len(video_files)}] OCR text extraction already COMPLETED for {video_id}.")
                    summary["skipped"] += 1
                    continue

                logger.info(f"[INFO] [{idx}/{len(video_files)}] Processing '{video_id}'...")
                try:
                    ok = process_video(extractor, db, video_id, force=args.force)
                    if ok:
                        summary["completed"] += 1
                    else:
                        summary["failed"] += 1
                except KeyboardInterrupt:
                    logger.warning("[WARNING] Batch OCR processing aborted by user.")
                    break

            logger.info(
                f"[SUMMARY] OCR Batch Complete | Total: {summary['total']} | "
                f"Completed: {summary['completed']} | Skipped: {summary['skipped']} | Failed: {summary['failed']}"
            )
            return 0 if summary["failed"] == 0 else 1

    finally:
        extractor.safe_unload()


if __name__ == "__main__":
    sys.exit(main())

