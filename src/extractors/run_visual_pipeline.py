"""
CLI pipeline runner for Task 02: Visual SigLIP2 Feature Extraction and FAISS Indexing.
Processes keyframes from metadata.db, pools shot embeddings, constructs FAISS index,
and executes benchmark verification queries.
"""

import argparse
import io
import sys
import time
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import numpy as np
from loguru import logger

from src.common.config import ConfigManager
from src.extractors.visual import VisualExtractor
from src.indexers.metadata_db import MetadataDB
from src.indexers.vector_index import VectorIndex


def run_visual_pipeline(
    video_id: str = "L13_V001",
    test_query: str = "close-up shot of food preparation",
    eval_gt: bool = True,
    force: bool = False,
):
    """
    Executes end-to-end visual pipeline for a target video:
    1. Loads shots and keyframes from SQLite.
    2. Extracts SigLIP2 embeddings with safe batching and shot-level pooling (or loads existing cache).
    3. Builds and persists FAISS index.
    4. Executes a test text-to-visual query.
    5. Releases GPU VRAM.
    """
    config = ConfigManager().to_dict()
    db_path = config.get("paths", {}).get("metadata_db", "data/metadata.db")
    indices_dir = Path(config.get("paths", {}).get("indices_dir", "data/indices"))
    indices_dir.mkdir(parents=True, exist_ok=True)

    db = MetadataDB(db_path)
    shots = db.get_shots(video_id)
    keyframes = db.get_keyframes(video_id)

    if not shots or not keyframes:
        logger.error(
            f"[ERROR] No shots ({len(shots)}) or keyframes ({len(keyframes)}) found for video '{video_id}' in {db_path}."
        )
        return

    logger.info(
        f"[INFO] Starting visual pipeline for '{video_id}': {len(shots)} shots, {len(keyframes)} keyframes."
    )

    extractor = VisualExtractor(config)
    index_path = str(indices_dir / "visual_siglip2.index")
    metadata_path = str(indices_dir / "visual_siglip2.json")
    vector_index = VectorIndex(config, embedding_dim=1152)

    try:
        # Check if index is already built on disk
        if Path(index_path).exists() and Path(metadata_path).exists() and not force:
            logger.info(f"[INFO] Found existing FAISS index at {index_path}. Loading from disk...")
            vector_index.load(index_path, metadata_path)
        else:
            start_time = time.time()
            embeddings, metadata = extractor.extract_and_pool(video_id, shots, keyframes)
            elapsed_sec = time.time() - start_time
            fps = len(keyframes) / max(elapsed_sec, 0.001)

            logger.info(
                f"[OK] Extracted {len(embeddings)} vectors in {elapsed_sec:.2f}s (~{fps:.1f} frames/sec)."
            )

            vector_index = VectorIndex(config, embedding_dim=extractor.embedding_dim)
            vector_index.add(embeddings, metadata)
            vector_index.save(index_path, metadata_path)

        # 3. Test Text-to-Visual Search
        logger.info(f"[INFO] Testing text-to-visual query: '{test_query}'...")
        query_vector = extractor.extract_text_embedding(test_query)
        results = vector_index.search(query_vector, top_k=5)

        print("\n" + "=" * 80)
        print(f"TOP 5 VISUAL SEARCH RESULTS FOR QUERY: '{test_query}'")
        print("=" * 80)
        for r in results:
            shot_str = f"Shot #{r['shot_id']:03d}"
            time_str = f"t={r['timestamp_sec']:06.2f}s"
            type_str = "[SHOT POOLED]" if r.get("is_shot_pooled") else f"[KEYFRAME: {r.get('keyframe_id')}]"
            score_str = f"Cosine Score: {r['score']:.4f}"
            print(f"Rank #{r['rank']}: {shot_str} | {time_str} | {score_str} | {type_str}")
        print("=" * 80 + "\n")

        # 4. Optional Ground Truth Evaluation
        if eval_gt:
            import json
            from src.evaluation.evaluate import evaluate_retrieval, format_evaluation_table

            gt_path = Path(config.get("paths", {}).get("ground_truth_file", "data/ground_truth.json"))
            if gt_path.exists():
                with open(gt_path, "r", encoding="utf-8") as f:
                    all_gt = json.load(f)

                video_file_name = f"{video_id}.mp4"
                video_gt = [
                    g for g in all_gt
                    if g.get("video_file") == video_file_name or g.get("video_id") == video_id
                ]

                if video_gt:
                    logger.info(
                        f"[INFO] Evaluating {len(video_gt)} ground truth queries for '{video_id}'..."
                    )
                    predictions = {}
                    for g in video_gt:
                        qid = g["query_id"]
                        q_text = g["query"]
                        q_vec = extractor.extract_text_embedding(q_text)
                        hits = vector_index.search(q_vec, top_k=20)

                        preds = []
                        for h in hits:
                            preds.append({
                                "video_file": video_file_name,
                                "video_id": video_id,
                                "start_sec": h.get("start_sec", h.get("timestamp_sec", 0.0)),
                                "end_sec": h.get("end_sec", h.get("timestamp_sec", 0.0)),
                                "score": h.get("score", 0.0),
                                "shot_id": h.get("shot_id"),
                                "timestamp_sec": h.get("timestamp_sec"),
                                "is_shot_pooled": h.get("is_shot_pooled", False),
                            })
                        predictions[qid] = preds

                    eval_results = evaluate_retrieval(
                        video_gt, predictions, ks=[1, 5, 10], tolerance_sec=5.0
                    )
                    eval_table = format_evaluation_table(
                        eval_results, config_name=f"SigLIP2 Visual Baseline ({video_id})"
                    )
                    print("\n" + eval_table + "\n")
                else:
                    logger.warning(f"[WARNING] No ground truth queries found for {video_file_name}.")

    finally:
        # Strict GPU VRAM cleanup as per vram-safe-embedding skill
        extractor.safe_unload()


def main():
    parser = argparse.ArgumentParser(description="Extract SigLIP2 visual embeddings and build FAISS index.")
    parser.add_argument("--video-id", "-v", type=str, default="L13_V001", help="Target video ID to process")
    parser.add_argument("--query", "-q", type=str, default="cooking and food preparation", help="Test query to evaluate")
    parser.add_argument("--eval-gt", action="store_true", help="Evaluate against ground_truth.json queries for target video")
    parser.add_argument("--force", "-f", action="store_true", help="Force re-extraction of embeddings even if index exists")
    args = parser.parse_args()

    run_visual_pipeline(
        video_id=args.video_id,
        test_query=args.query,
        eval_gt=args.eval_gt,
        force=args.force,
    )


if __name__ == "__main__":
    main()
