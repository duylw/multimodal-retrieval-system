"""
Unified Multimodal Search Engine for Video Moment Retrieval.
Orchestrates Visual SigLIP2 search, SQLite FTS5 hybrid text search,
query routing, and temporal multi-cue RRF fusion into CandidateMoments.
"""

import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from loguru import logger

from src.common.types import CandidateMoment, ParsedMultiCueQuery, QueryStage
from src.indexers.metadata_db import MetadataDB
from src.retrieval.query_parser import QueryParser
from src.retrieval.score_fusion import TemporalMomentFusor


class SearchEngine:
    """
    Main retrieval orchestrator integrating dense visual search, lexical/fuzzy OCR search,
    multi-cue parsing, and temporal sliding window fusion.
    """

    def __init__(
        self,
        db_path: str = "data/metadata.db",
        index_path: str = "data/indices/visual_siglip2.index",
        metadata_path: str = "data/indices/visual_siglip2.json",
        keyframes_dir: str = "data/keyframes",
        fusor: Optional[TemporalMomentFusor] = None,
        embedding_dim: int = 768,
        top_k_visual: int = 1500,
        top_k_ocr: int = 500,
    ):
        self.db_path = db_path
        self.index_path = Path(index_path)
        self.metadata_path = Path(metadata_path)
        self.keyframes_dir = Path(keyframes_dir)
        self.fusor = fusor or TemporalMomentFusor()
        self.embedding_dim = embedding_dim
        self.top_k_visual = top_k_visual
        self.top_k_ocr = top_k_ocr

        # Lazy-loaded components
        self.db = MetadataDB(self.db_path)
        self._vector_index: Optional[Any] = None
        self._visual_extractor: Optional[Any] = None

    def _ensure_vector_index(self) -> Any:
        """Loads FAISS vector index lazily on first visual query."""
        if self._vector_index is not None:
            return self._vector_index

        if not self.index_path.exists() or not self.metadata_path.exists():
            raise FileNotFoundError(
                f"Visual FAISS index not found at {self.index_path}. "
                "Ensure Stage 3 and index build pipeline completed."
            )

        from src.indexers.vector_index import VectorIndex
        logger.info(f"[INFO] Lazy-loading FAISS visual index from {self.index_path}...")
        self._vector_index = VectorIndex({}, embedding_dim=self.embedding_dim)
        self._vector_index.load(str(self.index_path), str(self.metadata_path))
        logger.info(f"[OK] Visual index loaded with {self._vector_index.total_vectors} vectors.")
        return self._vector_index

    def _ensure_visual_extractor(self) -> Any:
        """Loads SigLIP2 visual extractor lazily for text query encoding."""
        if self._visual_extractor is not None:
            return self._visual_extractor

        from src.extractors.visual import VisualExtractor
        logger.info("[INFO] Lazy-loading SigLIP2 visual extractor on GPU/CPU...")
        self._visual_extractor = VisualExtractor()
        self._visual_extractor.load_model()
        logger.info("[OK] SigLIP2 visual extractor ready.")
        return self._visual_extractor

    def safe_unload(self) -> None:
        """Releases SigLIP2 model and PyTorch CUDA VRAM safely."""
        if self._visual_extractor is not None:
            self._visual_extractor.safe_unload()
            self._visual_extractor = None
            logger.info("[OK] Released SigLIP2 model from GPU VRAM.")

    def search(
        self,
        query: Union[str, Dict[str, Any], ParsedMultiCueQuery],
        mode: str = "auto",
        top_k: int = 25,
        video_id: Optional[str] = None
    ) -> List[CandidateMoment]:
        """
        Executes multimodal search and returns ranked, non-overlapping candidate moments.

        Args:
            query: Query string, dictionary payload, or ParsedMultiCueQuery.
            mode: Search mode ('auto', 'visual', or 'ocr').
            top_k: Number of moments to retrieve (default 25).
            video_id: Optional video ID filter to restrict search to one video.

        Returns:
            List of CandidateMoment instances sorted by fused score.
        """
        parsed = self._prepare_query(query, mode=mode)
        if not parsed.stages:
            logger.warning("[WARNING] No valid query stages found.")
            return []

        # Maps each unique cue_id -> modality ('visual' or 'ocr')
        cue_types: Dict[str, str] = {}
        stage_results: List[Dict[str, List[Dict[str, Any]]]] = []

        for s_idx, stage in enumerate(parsed.stages):
            hits_by_cue: Dict[str, List[Dict[str, Any]]] = {}

            # 1. Execute Visual Cues
            for v_idx, v_cue in enumerate(stage.visual_queries):
                cue_id = f"s{s_idx}_v{v_idx}"
                cue_types[cue_id] = "visual"
                hits = self._search_visual_cue(v_cue, top_k=self.top_k_visual, video_id=video_id)
                hits_by_cue[cue_id] = hits

            # 2. Execute OCR Cues
            for o_idx, o_cue in enumerate(stage.ocr_queries):
                cue_id = f"s{s_idx}_ocr{o_idx}"
                cue_types[cue_id] = "ocr"
                hits = self._search_ocr_cue(o_cue, top_k=self.top_k_ocr, video_id=video_id)
                hits_by_cue[cue_id] = hits

            stage_results.append(hits_by_cue)

        # 3. Fuse across stages and apply temporal sliding window + NMS
        moments = self.fusor.fuse_and_nms(
            stage_results=stage_results,
            cue_types=cue_types,
            weights=parsed.weights,
            top_k=top_k
        )

        # 4. Decorate moments with keyframe images and thumbnail URLs
        self._decorate_moments(moments)
        return moments

    def _prepare_query(
        self,
        query: Union[str, Dict[str, Any], ParsedMultiCueQuery],
        mode: str
    ) -> ParsedMultiCueQuery:
        """Parses and adjusts query based on explicit mode toggle."""
        if isinstance(query, ParsedMultiCueQuery):
            parsed = query
        else:
            parsed = QueryParser.parse(query)

        # Handle explicit mode overrides from UI toggle
        mode_lower = mode.lower()
        if mode_lower == "visual":
            # Strip OCR queries; keep only visual queries
            new_stages = []
            for st in parsed.stages:
                v_all = list(st.visual_queries)
                if not v_all and st.ocr_queries:
                    v_all = list(st.ocr_queries)
                new_stages.append(QueryStage(visual_queries=v_all, ocr_queries=[]))
            parsed.stages = new_stages

        elif mode_lower == "ocr":
            # Strip Visual queries; keep only OCR queries
            new_stages = []
            for st in parsed.stages:
                o_all = list(st.ocr_queries)
                if not o_all and st.visual_queries:
                    o_all = list(st.visual_queries)
                new_stages.append(QueryStage(visual_queries=[], ocr_queries=o_all))
            parsed.stages = new_stages

        return parsed

    def _search_visual_cue(
        self,
        visual_cue: str,
        top_k: int = 1500,
        video_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Encodes English visual description and searches FAISS index."""
        clean_cue = visual_cue.strip()
        if not clean_cue:
            return []

        vec_idx = self._ensure_vector_index()
        extractor = self._ensure_visual_extractor()

        # Extract 768-dim L2-normalized text embedding
        q_vec = extractor.extract_text_embedding(clean_cue)
        raw_hits = vec_idx.search(q_vec, top_k=top_k)

        # Filter by video_id if provided
        if video_id:
            raw_hits = [h for h in raw_hits if h.get("video_id") == video_id]

        return raw_hits

    def _search_ocr_cue(
        self,
        ocr_cue: str,
        top_k: int = 500,
        video_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Executes Two-Stage Hybrid Search on SQLite keyframe-aggregated FTS5 index."""
        clean_cue = ocr_cue.strip()
        if not clean_cue:
            return []

        hits = self.db.search_ocr(clean_cue, video_id=video_id, limit=top_k)
        return hits

    def _decorate_moments(self, moments: List[CandidateMoment]) -> None:
        """Decorates CandidateMoment instances with thumbnail image URLs."""
        if not moments:
            return

        # Fetch keyframe records for missing thumbnails
        for m in moments:
            vid = m.video_id
            if m.keyframe_id and not m.thumbnail_url:
                # Find matching JPEG on disk
                img_name = f"{m.keyframe_id}.jpg"
                candidate_path = self.keyframes_dir / vid / img_name
                if candidate_path.exists():
                    m.thumbnail_url = f"/api/keyframes/{vid}/{img_name}"
                else:
                    # Fallback to any matching keyframe in that video
                    m.thumbnail_url = f"/api/keyframes/{vid}/{m.keyframe_id}.jpg"


def main() -> None:
    parser = argparse.ArgumentParser(description="Unified Multimodal Video Moment Search Engine CLI.")
    parser.add_argument("--query", "-q", type=str, required=True, help="Query string or multi-cue prefix string.")
    parser.add_argument("--mode", type=str, default="auto", choices=["auto", "visual", "ocr"], help="Search mode.")
    parser.add_argument("--top-k", type=int, default=10, help="Number of moments to retrieve.")
    parser.add_argument("--video-id", type=str, default=None, help="Filter search to a specific video ID.")
    args = parser.parse_args()

    engine = SearchEngine()
    try:
        results = engine.search(query=args.query, mode=args.mode, top_k=args.top_k, video_id=args.video_id)
        print(f"\n[OK] Retrieved {len(results)} candidate moments for query: '{args.query}' (Mode: {args.mode})")
        print("=" * 80)
        for rank, m in enumerate(results, start=1):
            mins_s, secs_s = int(m.start_sec // 60), m.start_sec % 60
            mins_e, secs_e = int(m.end_sec // 60), m.end_sec % 60
            time_str = f"{mins_s:02d}:{secs_s:05.2f} - {mins_e:02d}:{secs_e:05.2f}"
            cues_str = ", ".join(m.matched_cues)
            snippet = f" | Text: '{m.text_snippet[:40]}...'" if m.text_snippet else ""
            print(f"Rank #{rank:02d} | Score: {m.score:.4f} | Video: {m.video_id} [{time_str}] ({m.start_ms}ms - {m.end_ms}ms) | Cues: [{cues_str}]{snippet}")
        print("=" * 80)
    finally:
        engine.safe_unload()


if __name__ == "__main__":
    main()

