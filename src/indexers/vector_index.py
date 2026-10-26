"""
Vector indexer using FAISS IndexFlatIP (Inner Product over L2-normalized embeddings).
Provides exact Cosine similarity search with low latency and persistence to disk.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import faiss
import numpy as np
from loguru import logger

from src.common.base import BaseIndexer


class VectorIndex(BaseIndexer):
    """
    Manages dense vector storage and kNN similarity search using FAISS.
    Default index structure is IndexFlatIP for exact, lossless inner product search.
    """

    def __init__(self, config: Dict[str, Any], embedding_dim: int = 1152):
        super().__init__(config)
        self.embedding_dim = embedding_dim
        self.index: faiss.IndexFlatIP = faiss.IndexFlatIP(self.embedding_dim)
        self.id_to_metadata: List[Dict[str, Any]] = []

    @property
    def total_vectors(self) -> int:
        """Returns total number of vectors indexed."""
        return self.index.ntotal if self.index else 0

    def add(self, embeddings: np.ndarray, metadata: List[Dict[str, Any]]) -> None:
        """
        Appends a batch of embeddings and their corresponding metadata to the index.

        Args:
            embeddings: Float32 numpy array of shape (N, embedding_dim).
            metadata: List of N metadata dictionaries matching the vectors.
        """
        if len(embeddings) == 0:
            return

        if embeddings.ndim != 2 or embeddings.shape[1] != self.embedding_dim:
            raise ValueError(
                f"Embedding dimension mismatch: expected (N, {self.embedding_dim}), got {embeddings.shape}"
            )

        if len(embeddings) != len(metadata):
            raise ValueError(
                f"Count mismatch: got {len(embeddings)} embeddings but {len(metadata)} metadata items."
            )

        # Ensure float32 for FAISS
        embeddings = np.ascontiguousarray(embeddings, dtype=np.float32)

        # L2-normalize vectors if not already normalized (so IP equals Cosine Similarity)
        norms = np.linalg.norm(embeddings, axis=-1, keepdims=True)
        norms[norms == 0] = 1e-12
        embeddings = embeddings / norms

        start_id = self.total_vectors
        self.index.add(embeddings)

        for i, meta in enumerate(metadata):
            record = dict(meta)
            record["faiss_id"] = start_id + i
            self.id_to_metadata.append(record)

        logger.info(
            f"[INFO] Added {len(embeddings)} vectors to index. Total vectors: {self.total_vectors}"
        )

    def search(
        self, query_embedding: np.ndarray, top_k: int = 50, **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Searches the index for nearest neighbors given a query embedding.

        Args:
            query_embedding: Float32 numpy array of shape (embedding_dim,) or (1, embedding_dim).
            top_k: Number of highest-ranking candidate moments to return.

        Returns:
            List of matching records with similarity score and associated metadata.
        """
        if self.total_vectors == 0:
            logger.warning("[WARNING] FAISS index is empty. Returning empty results.")
            return []

        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)

        query_embedding = np.ascontiguousarray(query_embedding, dtype=np.float32)
        norm = np.linalg.norm(query_embedding, axis=-1, keepdims=True)
        if norm > 0:
            query_embedding = query_embedding / norm

        k = min(top_k, self.total_vectors)
        distances, indices = self.index.search(query_embedding, k)

        results = []
        for rank, (score, faiss_id) in enumerate(zip(distances[0], indices[0]), start=1):
            if faiss_id < 0 or faiss_id >= len(self.id_to_metadata):
                continue
            item = dict(self.id_to_metadata[faiss_id])
            item["score"] = float(score)
            item["rank"] = rank
            results.append(item)

        return results

    def save(self, output_path: str, metadata_path: Optional[str] = None) -> None:
        """
        Persists FAISS index binary and metadata JSON to disk.

        Args:
            output_path: Path for FAISS binary index (e.g. data/indices/visual_siglip2.index).
            metadata_path: Path for metadata JSON mapping (defaults to index path + .json).
        """
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)

        faiss.write_index(self.index, str(out_file))

        if not metadata_path:
            meta_file = out_file.with_suffix(".json")
        else:
            meta_file = Path(metadata_path)

        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(self.id_to_metadata, f, ensure_ascii=False, indent=2)

        logger.info(
            f"[OK] Saved FAISS index ({self.total_vectors} vectors) to {out_file} and metadata to {meta_file}"
        )

    def load(self, index_path: str, metadata_path: Optional[str] = None) -> None:
        """
        Loads FAISS binary index and metadata mapping from disk.
        """
        idx_file = Path(index_path)
        if not idx_file.exists():
            raise FileNotFoundError(f"FAISS index file not found at: {index_path}")

        self.index = faiss.read_index(str(idx_file))
        self.embedding_dim = self.index.d

        if not metadata_path:
            meta_file = idx_file.with_suffix(".json")
        else:
            meta_file = Path(metadata_path)

        if meta_file.exists():
            with open(meta_file, "r", encoding="utf-8") as f:
                self.id_to_metadata = json.load(f)
        else:
            logger.warning(f"[WARNING] Metadata file {meta_file} not found. Creating empty map.")
            self.id_to_metadata = []

        logger.info(
            f"[OK] Loaded FAISS index ({self.total_vectors} vectors, dim={self.embedding_dim}) from {idx_file}"
        )
