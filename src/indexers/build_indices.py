"""
Standalone CLI tool to build unified search indices (FAISS, BM25, SQLite FTS5)
from per-video dense feature caches and transcript records.
Decouples feature extraction from index construction for atomic, one-pass rebuilding.
"""

import argparse
import io
import json
import sys
from pathlib import Path
from typing import Any, Dict, List
import numpy as np
from loguru import logger

from src.common.config import ConfigManager
from src.indexers.vector_index import VectorIndex

# Ensure UTF-8 output encoding on Windows terminals
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def parse_args() -> argparse.Namespace:
    """Parses command-line arguments for index builder."""
    parser = argparse.ArgumentParser(
        description="Unified Index Builder: Aggregates per-video feature caches into FAISS indices."
    )
    parser.add_argument(
        "--modality",
        type=str,
        default="visual",
        choices=["visual", "all"],
        help="Target modality index to build (default: visual)."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/default_config.yaml",
        help="Path to YAML configuration file."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/indices",
        help="Directory to persist binary indices and metadata mappings."
    )
    return parser.parse_args()


def build_visual_index(features_dir: Path, output_dir: Path, cfg: Dict[str, Any]) -> bool:
    """Aggregates all per-video visual .npz caches and builds a unified FAISS index."""
    visual_feature_dir = features_dir / "visual"
    if not visual_feature_dir.exists():
        logger.error(f"[ERROR] Visual features directory does not exist: {visual_feature_dir}")
        return False

    npz_files = sorted(list(visual_feature_dir.glob("*.npz")))
    if not npz_files:
        logger.warning(f"[WARNING] No .npz feature caches found in {visual_feature_dir}. Run run_visual first.")
        return False

    logger.info(f"[INFO] Found {len(npz_files)} visual feature caches in {visual_feature_dir}. Loading vectors...")

    all_embeddings_list: List[np.ndarray] = []
    all_metadata_list: List[Dict[str, Any]] = []

    for npz_path in npz_files:
        try:
            with np.load(npz_path, allow_pickle=True) as data:
                vecs = data["embeddings"].astype(np.float32)
                meta_json_str = str(data["metadata_json"])
                meta = json.loads(meta_json_str)

                if len(vecs) != len(meta):
                    logger.warning(
                        f"[WARNING] Vector count ({len(vecs)}) mismatch with metadata ({len(meta)}) in {npz_path.name}. Skipping."
                    )
                    continue

                all_embeddings_list.append(vecs)
                all_metadata_list.extend(meta)
                logger.info(f"  [LOAD] {npz_path.stem}: {len(vecs)} vectors")
        except Exception as e:
            logger.error(f"[ERROR] Failed to load feature cache {npz_path}: {e}")

    if not all_embeddings_list:
        logger.error("[ERROR] No valid vectors loaded from feature caches.")
        return False

    stacked_embeddings = np.vstack(all_embeddings_list)
    embedding_dim = stacked_embeddings.shape[1]

    logger.info(
        f"[INFO] Building FAISS IndexFlatIP with {len(stacked_embeddings)} total vectors (dim={embedding_dim})..."
    )

    vector_index = VectorIndex(cfg, embedding_dim=embedding_dim)
    vector_index.add(stacked_embeddings, all_metadata_list)

    output_dir.mkdir(parents=True, exist_ok=True)
    index_file = output_dir / "visual_siglip2.index"
    meta_file = output_dir / "visual_siglip2.json"

    vector_index.save(str(index_file), str(meta_file))

    logger.info(
        f"[DONE] Successfully built and saved visual FAISS index to {index_file} ({vector_index.total_vectors} vectors across {len(npz_files)} videos)."
    )
    return True


def main() -> int:
    """Main CLI entry point for index builder."""
    args = parse_args()
    cfg = ConfigManager(args.config).config
    features_dir = Path(cfg.get("paths", {}).get("features_dir", "data/features"))
    output_dir = Path(args.output_dir)

    success = False
    if args.modality in ["visual", "all"]:
        success = build_visual_index(features_dir, output_dir, cfg)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

