"""
Unified Multimodal Search Engine for Video Moment Retrieval.
Orchestrates Visual SigLIP2 search, SQLite FTS5 hybrid text search,
query routing, and temporal multi-cue RRF fusion into CandidateMoments.
"""

import argparse
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union
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

    def _ensure_vid_index_map(self, vec_idx: Any) -> Dict[str, List[int]]:
        """Builds and caches a lookup map of video_id -> list of FAISS integer IDs."""
        if not hasattr(vec_idx, "_vid_to_int_ids"):
            vid_map: Dict[str, List[int]] = {}
            for idx_i, meta in enumerate(vec_idx.id_to_metadata):
                v_id = meta.get("video_id")
                if v_id:
                    vid_map.setdefault(v_id, []).append(idx_i)
            vec_idx._vid_to_int_ids = vid_map
        return vec_idx._vid_to_int_ids

    def _ensure_kfid_index_map(self, vec_idx: Any) -> Dict[str, int]:
        """Builds and caches an O(1) lookup map of keyframe_id -> FAISS integer ID."""
        if not hasattr(vec_idx, "_kfid_to_int_id"):
            vec_idx._kfid_to_int_id = {
                meta["keyframe_id"]: idx_i
                for idx_i, meta in enumerate(vec_idx.id_to_metadata)
                if meta.get("keyframe_id")
            }
        return vec_idx._kfid_to_int_id

    @staticmethod
    def _extract_batch_id(video_id: str) -> str:
        """Extracts batch prefix (e.g. 'L15' from 'L15_V004.mp4')."""
        clean = video_id.strip().replace(".mp4", "").replace(".MP4", "")
        return clean.split("_")[0].upper() if clean else ""

    @staticmethod
    def _normalize_scope_filters(
        allowed_batches: Optional[Union[List[str], Set[str]]] = None,
        excluded_videos: Optional[Union[List[str], Set[str]]] = None
    ) -> Tuple[Optional[Set[str]], Set[str]]:
        """Normalizes batch allowlist and excluded video set."""
        allowed_set: Optional[Set[str]] = None
        if allowed_batches is not None:
            allowed_set = {str(b).strip().upper() for b in allowed_batches if str(b).strip()}

        excluded_set: Set[str] = set()
        if excluded_videos:
            excluded_set = {
                str(v).strip().replace(".mp4", "").replace(".MP4", "")
                for v in excluded_videos
                if str(v).strip()
            }
        return allowed_set, excluded_set

    def _resolve_target_videos(
        self,
        video_id: Optional[str],
        allowed_batches: Optional[Set[str]],
        excluded_videos: Set[str]
    ) -> Optional[Set[str]]:
        """Resolves explicit video subset when single-video lock or batch scope is active."""
        vid_clean = video_id.strip() if video_id and video_id.strip() else None
        if vid_clean:
            if vid_clean in excluded_videos:
                return set()
            if allowed_batches is not None and self._extract_batch_id(vid_clean) not in allowed_batches:
                return set()
            return {vid_clean}

        if allowed_batches is None:
            return None
        if not allowed_batches:
            return set()

        vec_idx = self._ensure_vector_index()
        vid_map = self._ensure_vid_index_map(vec_idx)
        return {
            vid for vid in vid_map.keys()
            if vid not in excluded_videos and self._extract_batch_id(vid) in allowed_batches
        }

    @classmethod
    def _filter_hits_by_scope(
        cls,
        hits: List[Dict[str, Any]],
        allowed_batches: Optional[Set[str]] = None,
        excluded_videos: Optional[Set[str]] = None
    ) -> List[Dict[str, Any]]:
        """Filters hit dictionaries by active batch scope and excluded video set."""
        if not hits or (allowed_batches is None and not excluded_videos):
            return hits

        excluded = excluded_videos or set()
        filtered: List[Dict[str, Any]] = []
        for h in hits:
            vid = str(h.get("video_id", "")).strip()
            if not vid or vid in excluded:
                continue
            if allowed_batches is not None and cls._extract_batch_id(vid) not in allowed_batches:
                continue
            item = dict(h)
            item["rank"] = len(filtered) + 1
            filtered.append(item)
        return filtered

    def _execute_filtered_visual_vector_search(
        self,
        q_vec: Any,
        top_k: int = 1500,
        video_id: Optional[str] = None,
        allowed_batches: Optional[Set[str]] = None,
        excluded_videos: Optional[Set[str]] = None
    ) -> List[Dict[str, Any]]:
        """Runs FAISS similarity search while honoring video lock, batch scope, and exclusions."""
        if q_vec is None:
            return []

        vec_idx = self._ensure_vector_index()
        excluded = excluded_videos or set()
        target_videos = self._resolve_target_videos(video_id, allowed_batches, excluded)

        if target_videos is not None:
            if not target_videos:
                return []
            if len(target_videos) <= 60:
                return self._score_visual_subset(q_vec, target_videos=target_videos, top_k=top_k)

        has_filters = (allowed_batches is not None) or bool(excluded)
        fetch_k = min(vec_idx.total_vectors, max(top_k * 4, 4000)) if has_filters else top_k
        raw_hits = vec_idx.search(q_vec, top_k=fetch_k)
        filtered = self._filter_hits_by_scope(raw_hits, allowed_batches=allowed_batches, excluded_videos=excluded)
        return filtered[:top_k]

    @staticmethod
    def _decorate_trace_hits(
        db: MetadataDB,
        hits: List[Dict[str, Any]],
        limit: int,
        include_text: bool = False
    ) -> List[Dict[str, Any]]:
        """Formats a compact top-hits slice for pipeline inspection traces."""
        if limit <= 0 or not hits:
            return []
        trace_list: List[Dict[str, Any]] = []
        for r_idx, h in enumerate(hits[:limit]):
            h_vid = h.get("video_id", "")
            h_kfid = h.get("keyframe_id", "")
            h_fp = h.get("file_path") or db.get_keyframe_path(h_kfid)
            img_name = Path(h_fp).name if h_fp else f"{h_kfid}.jpg"
            entry: Dict[str, Any] = {
                "rank": r_idx + 1,
                "video_id": h_vid,
                "keyframe_id": h_kfid,
                "timestamp_sec": round(float(h.get("timestamp_sec", 0.0)), 2),
                "score": round(float(h.get("score", 0.0)), 4),
                "thumbnail_url": f"/api/keyframes/{h_vid}/{img_name}"
            }
            if include_text:
                entry["text_detected"] = h.get("text_detected", "")
            trace_list.append(entry)
        return trace_list

    @staticmethod
    def _filter_quality_ocr_hits(
        hits: List[Dict[str, Any]],
        min_score: float = 0.35
    ) -> List[Dict[str, Any]]:
        """Filters low-confidence Soft-OR OCR matches to suppress cross-modal noise."""
        if not hits:
            return []
        filtered = [h for h in hits if float(h.get("score", 0.0)) >= min_score]
        return filtered

    def _encode_visual_vector(
        self,
        visual_cues: List[str],
        negative_cues: Optional[List[str]] = None
    ) -> Optional[Any]:
        """Encodes one or more positive visual cues (with optional -v: subtraction) into an L2-normalized vector."""
        import numpy as np

        pos_texts = [c.strip() for c in visual_cues if c and c.strip()]
        if not pos_texts:
            return None

        extractor = self._ensure_visual_extractor()
        pos_vecs = [extractor.extract_text_embedding(t).astype(np.float32)[0] for t in pos_texts]
        q_vec = np.mean(pos_vecs, axis=0).astype(np.float32)

        if negative_cues:
            neg_vecs = [
                extractor.extract_text_embedding(nc.strip()).astype(np.float32)[0]
                for nc in negative_cues
                if nc and nc.strip()
            ]
            if neg_vecs:
                neg_mean = np.mean(neg_vecs, axis=0).astype(np.float32)
                q_vec = q_vec - 0.35 * neg_mean

        norm = float(np.linalg.norm(q_vec))
        if norm <= 1e-6:
            return None
        return (q_vec / norm).reshape(1, -1)

    def _score_visual_subset(
        self,
        q_vec: Any,
        target_videos: Set[str],
        top_k: int = 1500,
        min_sec: Optional[float] = None,
        max_sec: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Scores all indexed keyframes belonging to target_videos directly via FAISS reconstruct."""
        import numpy as np

        if not target_videos or q_vec is None:
            return []

        vec_idx = self._ensure_vector_index()
        vid_map = self._ensure_vid_index_map(vec_idx)
        q_flat = q_vec.reshape(-1)

        scored_items: List[Dict[str, Any]] = []
        for vid in target_videos:
            for f_id in vid_map.get(vid, []):
                meta = vec_idx.id_to_metadata[f_id]
                ts = float(meta.get("timestamp_sec", 0.0))
                if min_sec is not None and ts < min_sec:
                    continue
                if max_sec is not None and ts > max_sec:
                    continue
                v_rec = vec_idx.index.reconstruct(f_id)
                sim = float(np.dot(v_rec, q_flat))
                item = dict(meta)
                item["score"] = sim
                scored_items.append(item)

        scored_items.sort(key=lambda x: x["score"], reverse=True)
        selected = scored_items[:top_k]
        for r_idx, it in enumerate(selected, start=1):
            it["rank"] = r_idx
        return selected

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
        top_k: int = 50,
        video_id: Optional[str] = None,
        allowed_batches: Optional[Union[List[str], Set[str]]] = None,
        excluded_videos: Optional[Union[List[str], Set[str]]] = None
    ) -> List[CandidateMoment]:
        """
        Executes multimodal search and returns ranked, non-overlapping candidate moments.

        Args:
            query: Query string, dictionary payload, or ParsedMultiCueQuery.
            mode: Search mode ('auto', 'visual', or 'ocr').
            top_k: Number of moments to retrieve (default 50).
            video_id: Optional video ID filter to restrict search to one video.
            allowed_batches: Optional batch prefixes to allow (e.g. ['L15', 'L16']).
            excluded_videos: Optional video IDs to exclude from results.

        Returns:
            List of CandidateMoment instances sorted by fused score.
        """
        moments, _ = self.search_with_trace(
            query=query,
            mode=mode,
            top_k=top_k,
            video_id=video_id,
            trace_top_hits=0,
            allowed_batches=allowed_batches,
            excluded_videos=excluded_videos
        )
        return moments

    def search_with_trace(
        self,
        query: Union[str, Dict[str, Any], ParsedMultiCueQuery],
        mode: str = "auto",
        top_k: int = 50,
        video_id: Optional[str] = None,
        trace_top_hits: int = 10,
        allowed_batches: Optional[Union[List[str], Set[str]]] = None,
        excluded_videos: Optional[Union[List[str], Set[str]]] = None
    ) -> Tuple[List[CandidateMoment], Dict[str, Any]]:
        """
        Executes multimodal search with explainability trace capturing per-cue hits and fusion stats.
        Uses Visual-First OCR coordination (Boost / Filter) in Hybrid mode and Two-Phase
        Anchor-then-Scan retrieval for chronological sequential queries.
        """
        start_time = time.perf_counter()
        parsed = self._prepare_query(query, mode=mode)
        if not parsed.stages:
            logger.warning("[WARNING] No valid query stages found.")
            return [], {
                "error": "No valid query stages found.",
                "total_time_ms": round((time.perf_counter() - start_time) * 1000, 2)
            }

        allowed_set, excluded_set = self._normalize_scope_filters(allowed_batches, excluded_videos)
        mode_lower = mode.lower()

        # Chronological multi-stage sequence: Two-Phase Anchor-then-Scan
        if parsed.is_sequential and len(parsed.stages) > 1:
            moments, cues_trace = self._search_sequential_anchor_then_scan(
                parsed=parsed,
                top_k=top_k,
                video_id=video_id,
                trace_top_hits=trace_top_hits,
                allowed_batches=allowed_set,
                excluded_videos=excluded_set
            )
            self._decorate_moments(moments)
            return moments, self._build_trace(
                query=query,
                mode=mode,
                parsed=parsed,
                cues_trace=cues_trace,
                moments=moments,
                start_time=start_time
            )

        # Single-stage execution
        stage = parsed.stages[0]
        use_visual_first = (
            mode_lower == "auto"
            and bool(stage.visual_queries)
            and bool(stage.ocr_queries)
        )

        if use_visual_first:
            moments, cues_trace = self._search_single_stage_visual_first(
                stage=stage,
                parsed=parsed,
                top_k=top_k,
                video_id=video_id,
                trace_top_hits=trace_top_hits,
                allowed_batches=allowed_set,
                excluded_videos=excluded_set
            )
            self._decorate_moments(moments)
            return moments, self._build_trace(
                query=query,
                mode=mode,
                parsed=parsed,
                cues_trace=cues_trace,
                moments=moments,
                start_time=start_time
            )

        # Pure Visual, Pure OCR (preserved standalone), or Hybrid with single modality
        cue_types: Dict[str, str] = {}
        hits_by_cue: Dict[str, List[Dict[str, Any]]] = {}
        cues_trace = []
        neg_cues = getattr(stage, "negative_visual_queries", [])

        for v_idx, v_cue in enumerate(stage.visual_queries):
            cue_id = f"s0_v{v_idx}"
            cue_types[cue_id] = "visual"
            t0 = time.perf_counter()
            hits = self._search_visual_cue(
                v_cue,
                top_k=self.top_k_visual,
                video_id=video_id,
                negative_cues=neg_cues,
                allowed_batches=allowed_set,
                excluded_videos=excluded_set
            )
            lat_ms = round((time.perf_counter() - t0) * 1000, 2)
            hits_by_cue[cue_id] = hits
            cues_trace.append({
                "cue_id": cue_id,
                "stage_index": 0,
                "modality": "visual",
                "query_text": v_cue,
                "hits_count": len(hits),
                "latency_ms": lat_ms,
                "top_hits": self._decorate_trace_hits(self.db, hits, trace_top_hits, include_text=False)
            })

        # Standalone OCR (mode == "ocr" or OCR-only query) preserves 100% of original search_ocr behavior
        run_ocr = (mode_lower == "ocr") or (not stage.visual_queries and bool(stage.ocr_queries))
        if run_ocr:
            for o_idx, o_cue in enumerate(stage.ocr_queries):
                cue_id = f"s0_ocr{o_idx}"
                cue_types[cue_id] = "ocr"
                t0 = time.perf_counter()
                hits = self._search_scoped_ocr_cue(
                    o_cue,
                    top_k=self.top_k_ocr,
                    video_id=video_id,
                    allowed_batches=allowed_set,
                    excluded_videos=excluded_set
                )
                lat_ms = round((time.perf_counter() - t0) * 1000, 2)
                hits_by_cue[cue_id] = hits
                cues_trace.append({
                    "cue_id": cue_id,
                    "stage_index": 0,
                    "modality": "ocr",
                    "query_text": o_cue,
                    "hits_count": len(hits),
                    "latency_ms": lat_ms,
                    "top_hits": self._decorate_trace_hits(self.db, hits, trace_top_hits, include_text=True)
                })

        moments = self.fusor.fuse_and_nms(
            stage_results=[hits_by_cue],
            cue_types=cue_types,
            weights=parsed.weights,
            top_k=top_k
        )
        self._decorate_moments(moments)

        return moments, self._build_trace(
            query=query,
            mode=mode,
            parsed=parsed,
            cues_trace=cues_trace,
            moments=moments,
            start_time=start_time
        )

    def search_by_keyframe(
        self,
        keyframe_id: str,
        steer_text: Optional[str] = None,
        steer_alpha: float = 0.3,
        negative_cues: Optional[List[str]] = None,
        top_k: int = 300,
        video_id: Optional[str] = None,
        allowed_batches: Optional[Union[List[str], Set[str]]] = None,
        excluded_videos: Optional[Union[List[str], Set[str]]] = None,
        trace_top_hits: int = 10
    ) -> Tuple[List[CandidateMoment], Dict[str, Any]]:
        """
        0ms-inference keyframe-to-keyframe similarity search via FAISS vector reconstruction.
        Loads SigLIP2 text encoder only when steer_text or negative_cues are provided.
        """
        import numpy as np

        start_time = time.perf_counter()
        clean_kfid = keyframe_id.strip()
        if not clean_kfid:
            raise ValueError("keyframe_id cannot be empty.")

        vec_idx = self._ensure_vector_index()
        kfid_map = self._ensure_kfid_index_map(vec_idx)
        if clean_kfid not in kfid_map:
            raise ValueError(f"Keyframe ID '{clean_kfid}' not found in FAISS index.")

        faiss_id = kfid_map[clean_kfid]
        v_img = vec_idx.index.reconstruct(faiss_id).astype(np.float32)

        q_vec = v_img
        clean_steer = steer_text.strip() if steer_text and steer_text.strip() else None
        clean_negs = [c.strip() for c in (negative_cues or []) if c and c.strip()]

        if clean_steer or clean_negs:
            extractor = self._ensure_visual_extractor()
            if clean_steer:
                alpha = max(0.0, min(1.0, float(steer_alpha)))
                v_txt = extractor.extract_text_embedding(clean_steer).astype(np.float32)[0]
                q_vec = (1.0 - alpha) * v_img + alpha * v_txt
            if clean_negs:
                neg_vecs = [extractor.extract_text_embedding(nc).astype(np.float32)[0] for nc in clean_negs]
                neg_mean = np.mean(neg_vecs, axis=0).astype(np.float32)
                q_vec = q_vec - 0.35 * neg_mean

        norm = float(np.linalg.norm(q_vec))
        if norm > 1e-6:
            q_vec = q_vec / norm

        allowed_set, excluded_set = self._normalize_scope_filters(allowed_batches, excluded_videos)
        t0 = time.perf_counter()
        raw_hits = self._execute_filtered_visual_vector_search(
            q_vec.reshape(1, -1),
            top_k=max(self.top_k_visual, top_k),
            video_id=video_id,
            allowed_batches=allowed_set,
            excluded_videos=excluded_set
        )
        lat_ms = round((time.perf_counter() - t0) * 1000, 2)

        cue_id = "sim_v0"
        moments = self.fusor.fuse_and_nms(
            stage_results=[{cue_id: raw_hits}],
            cue_types={cue_id: "visual"},
            weights={"visual": 1.0},
            top_k=top_k
        )
        self._decorate_moments(moments)

        trace = {
            "mode": "similar",
            "reference_keyframe_id": clean_kfid,
            "steer_text": clean_steer,
            "steer_alpha": steer_alpha if clean_steer else 0.0,
            "negative_visual_queries": clean_negs,
            "total_time_ms": round((time.perf_counter() - start_time) * 1000, 2),
            "cues": [{
                "cue_id": cue_id,
                "modality": "similar",
                "query_text": clean_kfid + (f" + {clean_steer}" if clean_steer else ""),
                "hits_count": len(raw_hits),
                "latency_ms": lat_ms,
                "top_hits": self._decorate_trace_hits(self.db, raw_hits, trace_top_hits, include_text=False)
            }],
            "returned_moments": len(moments)
        }
        return moments, trace

    def _build_trace(
        self,
        query: Any,
        mode: str,
        parsed: ParsedMultiCueQuery,
        cues_trace: List[Dict[str, Any]],
        moments: List[CandidateMoment],
        start_time: float
    ) -> Dict[str, Any]:
        """Constructs the structured explainability trace response."""
        return {
            "query": query if isinstance(query, (str, dict)) else str(query),
            "mode": mode,
            "ocr_mode": parsed.ocr_mode,
            "is_sequential": parsed.is_sequential,
            "total_stages": len(parsed.stages),
            "parsed_stages": [
                {
                    "stage_index": idx,
                    "visual_queries": st.visual_queries,
                    "ocr_queries": st.ocr_queries,
                    "negative_visual_queries": getattr(st, "negative_visual_queries", [])
                }
                for idx, st in enumerate(parsed.stages)
            ],
            "cues": cues_trace,
            "consensus_moments_count": sum(1 for m in moments if len(m.matched_cues) > 1),
            "total_moments_found": len(moments),
            "total_time_ms": round((time.perf_counter() - start_time) * 1000, 2)
        }

    def _search_single_stage_visual_first(
        self,
        stage: QueryStage,
        parsed: ParsedMultiCueQuery,
        top_k: int,
        video_id: Optional[str],
        trace_top_hits: int,
        stage_index: int = 0,
        allowed_batches: Optional[Set[str]] = None,
        excluded_videos: Optional[Set[str]] = None
    ) -> Tuple[List[CandidateMoment], List[Dict[str, Any]]]:
        """
        Visual-First Hybrid OCR coordination:
        - 'off': ignores OCR cues completely.
        - 'filter': shortlists videos matching quality OCR hits, then scores Visual within them.
        - 'boost': scores Visual first globally, then boosts windows near quality-gated OCR matches
          using their actual fuzzy+BM25 score (never rank-only weight override).
        """
        cues_trace: List[Dict[str, Any]] = []
        ocr_mode = parsed.ocr_mode
        neg_cues = getattr(stage, "negative_visual_queries", [])

        # Collect OCR hits if OCR participation is enabled
        quality_ocr_hits: List[Dict[str, Any]] = []
        if ocr_mode != "off" and stage.ocr_queries:
            for o_idx, o_cue in enumerate(stage.ocr_queries):
                cue_id = f"s{stage_index}_ocr{o_idx}"
                t0 = time.perf_counter()
                raw_ocr = self._search_scoped_ocr_cue(
                    o_cue,
                    top_k=self.top_k_ocr,
                    video_id=video_id,
                    allowed_batches=allowed_batches,
                    excluded_videos=excluded_videos
                )
                gated = self._filter_quality_ocr_hits(raw_ocr, min_score=0.35)
                if not gated and raw_ocr and ocr_mode == "filter":
                    gated = raw_ocr[:25]
                lat_ms = round((time.perf_counter() - t0) * 1000, 2)
                for gh in gated:
                    gh_copy = dict(gh)
                    gh_copy["_cue_id"] = cue_id
                    quality_ocr_hits.append(gh_copy)
                cues_trace.append({
                    "cue_id": cue_id,
                    "stage_index": stage_index,
                    "modality": "ocr",
                    "query_text": o_cue,
                    "hits_count": len(gated),
                    "latency_ms": lat_ms,
                    "top_hits": self._decorate_trace_hits(self.db, gated, trace_top_hits, include_text=True)
                })

        # Filter mode: restrict Visual scoring exclusively to OCR-matched videos within scope
        target_videos: Optional[Set[str]] = None
        if ocr_mode == "filter" and stage.ocr_queries:
            excluded = excluded_videos or set()
            target_videos = {
                h["video_id"] for h in quality_ocr_hits
                if h.get("video_id")
                and h["video_id"] not in excluded
                and (allowed_batches is None or self._extract_batch_id(h["video_id"]) in allowed_batches)
            }
            if not target_videos:
                return [], cues_trace

        cue_types: Dict[str, str] = {}
        hits_by_cue: Dict[str, List[Dict[str, Any]]] = {}

        for v_idx, v_cue in enumerate(stage.visual_queries):
            cue_id = f"s{stage_index}_v{v_idx}"
            cue_types[cue_id] = "visual"
            t0 = time.perf_counter()
            if target_videos is not None:
                q_vec = self._encode_visual_vector([v_cue], negative_cues=neg_cues)
                hits = self._score_visual_subset(q_vec, target_videos=target_videos, top_k=self.top_k_visual)
            else:
                hits = self._search_visual_cue(
                    v_cue,
                    top_k=self.top_k_visual,
                    video_id=video_id,
                    negative_cues=neg_cues,
                    allowed_batches=allowed_batches,
                    excluded_videos=excluded_videos
                )
            lat_ms = round((time.perf_counter() - t0) * 1000, 2)
            hits_by_cue[cue_id] = hits
            cues_trace.append({
                "cue_id": cue_id,
                "stage_index": stage_index,
                "modality": "visual",
                "query_text": v_cue,
                "hits_count": len(hits),
                "latency_ms": lat_ms,
                "top_hits": self._decorate_trace_hits(self.db, hits, trace_top_hits, include_text=False)
            })

        moments = self.fusor.fuse_and_nms(
            stage_results=[hits_by_cue],
            cue_types=cue_types,
            weights={"visual": 1.0},
            top_k=top_k
        )

        # Apply quality-weighted OCR Boost (+-5s temporal window, fallback +-0.05 video-level)
        if quality_ocr_hits and moments:
            ocr_by_vid: Dict[str, List[Dict[str, Any]]] = {}
            for oh in quality_ocr_hits:
                ocr_by_vid.setdefault(oh["video_id"], []).append(oh)

            boost_w = parsed.ocr_boost_weight if ocr_mode == "boost" else 0.35
            for m in moments:
                vid_hits = ocr_by_vid.get(m.video_id)
                if not vid_hits:
                    continue

                nearby = [
                    oh for oh in vid_hits
                    if (m.start_sec - 5.0) <= float(oh.get("timestamp_sec", 0.0)) <= (m.end_sec + 5.0)
                ]
                best_oh = max(nearby, key=lambda h: float(h.get("score", 0.0))) if nearby else max(
                    vid_hits, key=lambda h: float(h.get("score", 0.0))
                )
                ocr_score = float(best_oh.get("score", 0.0))
                if nearby:
                    m.score = round(m.score * (1.0 + boost_w * ocr_score), 4)
                    cue_label = best_oh.get("_cue_id", f"s{stage_index}_ocr0")
                    if cue_label not in m.matched_cues:
                        m.matched_cues.append(cue_label)
                    m.text_snippet = best_oh.get("text_detected")
                    m.cue_evidence[cue_label] = best_oh
                elif ocr_mode == "boost":
                    m.score = round(m.score * (1.0 + 0.05 * ocr_score), 4)
                    if not m.text_snippet:
                        m.text_snippet = best_oh.get("text_detected")

            moments.sort(key=lambda x: x.score, reverse=True)

        return moments[:top_k], cues_trace

    def _search_sequential_anchor_then_scan(
        self,
        parsed: ParsedMultiCueQuery,
        top_k: int,
        video_id: Optional[str],
        trace_top_hits: int,
        allowed_batches: Optional[Set[str]] = None,
        excluded_videos: Optional[Set[str]] = None
    ) -> Tuple[List[CandidateMoment], List[Dict[str, Any]]]:
        """
        Two-Phase Anchor-then-Scan Sequential Linking:
        1. Phase 1 finds Top-N anchor candidate moments using the selected anchor_stage.
        2. Phase 2 scans neighbor keyframes [t + min_gap, t + max_gap] inside each anchor video
           via direct FAISS vector reconstruction, scoring partner stages without Top-K starvation
           and rejecting unlinked single scenes.
        """
        stages = parsed.stages
        num_stages = len(stages)
        anchor_idx = max(0, min(parsed.anchor_stage, num_stages - 1))
        min_gap = parsed.min_sequence_gap_sec
        max_gap = parsed.max_sequence_gap_sec

        # Phase 1: Retrieve anchor stage pool (up to 200 distinct temporal windows)
        anchor_pool_limit = max(200, top_k)
        anchor_stage = stages[anchor_idx]
        if anchor_stage.visual_queries:
            anchor_moments, cues_trace = self._search_single_stage_visual_first(
                stage=anchor_stage,
                parsed=parsed,
                top_k=anchor_pool_limit,
                video_id=video_id,
                trace_top_hits=trace_top_hits,
                stage_index=anchor_idx,
                allowed_batches=allowed_batches,
                excluded_videos=excluded_videos
            )
        else:
            # OCR-only anchor stage fallback
            cues_trace = []
            ocr_hits: List[Dict[str, Any]] = []
            for o_idx, o_cue in enumerate(anchor_stage.ocr_queries):
                cue_id = f"s{anchor_idx}_ocr{o_idx}"
                t0 = time.perf_counter()
                h_list = self._search_scoped_ocr_cue(
                    o_cue,
                    top_k=self.top_k_ocr,
                    video_id=video_id,
                    allowed_batches=allowed_batches,
                    excluded_videos=excluded_videos
                )
                lat_ms = round((time.perf_counter() - t0) * 1000, 2)
                ocr_hits.extend(h_list)
                cues_trace.append({
                    "cue_id": cue_id,
                    "stage_index": anchor_idx,
                    "modality": "ocr",
                    "query_text": o_cue,
                    "hits_count": len(h_list),
                    "latency_ms": lat_ms,
                    "top_hits": self._decorate_trace_hits(self.db, h_list, trace_top_hits, include_text=True)
                })
            anchor_moments = self.fusor.fuse_and_nms(
                stage_results=[{f"s{anchor_idx}_ocr0": ocr_hits}],
                cue_types={f"s{anchor_idx}_ocr0": "ocr"},
                weights=parsed.weights,
                top_k=anchor_pool_limit
            )

        if not anchor_moments:
            return [], cues_trace

        # Encode visual query vectors for every non-anchor partner stage once
        stage_vecs: Dict[int, Optional[Any]] = {}
        for s_idx, st in enumerate(stages):
            if s_idx == anchor_idx:
                continue
            stage_vecs[s_idx] = self._encode_visual_vector(
                st.visual_queries,
                negative_cues=getattr(st, "negative_visual_queries", [])
            )

        max_anchor_score = max((m.score for m in anchor_moments), default=1.0) or 1.0
        partner_trace_hits: Dict[int, List[Dict[str, Any]]] = {
            s_idx: [] for s_idx in range(num_stages) if s_idx != anchor_idx
        }

        chained_moments: List[CandidateMoment] = []
        t_phase2_start = time.perf_counter()

        for anc_m in anchor_moments:
            vid = anc_m.video_id
            anc_kf_ts = None
            if isinstance(anc_m.cue_evidence, dict):
                for ev in anc_m.cue_evidence.values():
                    if isinstance(ev, dict) and ev.get("timestamp_sec") is not None:
                        anc_kf_ts = float(ev["timestamp_sec"])
                        break
            anc_center_ts = round(
                anc_kf_ts if anc_kf_ts is not None else (anc_m.start_sec + anc_m.end_sec) * 0.5,
                2
            )
            anc_hit_obj = {
                "stage_index": anchor_idx,
                "video_id": vid,
                "keyframe_id": anc_m.keyframe_id,
                "timestamp_sec": anc_center_ts,
                "score": anc_m.score,
                "thumbnail_url": anc_m.thumbnail_url,
                "text_detected": anc_m.text_snippet
            }

            stage_matched_hits: Dict[int, Dict[str, Any]] = {anchor_idx: anc_hit_obj}
            partner_sims: List[float] = []
            chain_valid = True

            # Scan backward (anchor_idx - 1 -> 0) and forward (anchor_idx + 1 -> num_stages - 1)
            directions = [
                range(anchor_idx - 1, -1, -1),
                range(anchor_idx + 1, num_stages)
            ]
            for dir_range in directions:
                curr_ts = anc_center_ts
                is_backward = (len(dir_range) > 0 and dir_range[0] < anchor_idx)
                for s_idx in dir_range:
                    win_min = max(0.0, curr_ts - max_gap) if is_backward else (curr_ts + min_gap)
                    win_max = max(0.0, curr_ts - min_gap) if is_backward else (curr_ts + max_gap)
                    if win_max <= win_min:
                        chain_valid = False
                        break

                    q_vec = stage_vecs.get(s_idx)
                    st = stages[s_idx]
                    best_hit = self._find_best_partner_in_window(
                        vid=vid,
                        win_min=win_min,
                        win_max=win_max,
                        q_vec=q_vec,
                        ocr_queries=st.ocr_queries if parsed.ocr_mode != "off" else [],
                        ocr_mode=parsed.ocr_mode
                    )
                    if best_hit is None:
                        chain_valid = False
                        break

                    best_hit_record = {
                        "stage_index": s_idx,
                        "video_id": vid,
                        "keyframe_id": best_hit.get("keyframe_id"),
                        "timestamp_sec": round(float(best_hit.get("timestamp_sec", 0.0)), 2),
                        "score": round(float(best_hit.get("score", 0.0)), 4),
                        "thumbnail_url": best_hit.get("thumbnail_url"),
                        "text_detected": best_hit.get("text_detected")
                    }
                    stage_matched_hits[s_idx] = best_hit_record
                    partner_sims.append(max(0.0, float(best_hit.get("score", 0.0))))
                    partner_trace_hits[s_idx].append(best_hit_record)
                    curr_ts = float(best_hit.get("timestamp_sec", curr_ts))

                if not chain_valid:
                    break

            if not chain_valid or len(stage_matched_hits) < num_stages:
                continue

            ordered_hits = [stage_matched_hits[i] for i in range(num_stages)]
            norm_anchor = anc_m.score / max_anchor_score
            avg_partner = sum(partner_sims) / max(1, len(partner_sims))
            seq_score = round(0.55 * norm_anchor + 0.45 * avg_partner + 0.15, 4)

            seq_start = round(min(float(h["timestamp_sec"]) for h in ordered_hits), 2)
            seq_end = round(max(float(h["timestamp_sec"]) for h in ordered_hits), 2)
            matched_labels = list(anc_m.matched_cues)
            for s_idx in range(num_stages):
                if s_idx != anchor_idx:
                    matched_labels.append(f"s{s_idx}_v0")

            evidence = dict(anc_m.cue_evidence)
            for h in ordered_hits:
                evidence[f"stage_{h['stage_index']}"] = h
            evidence["sequence_stages"] = ordered_hits

            chained_moments.append(CandidateMoment(
                video_id=vid,
                start_sec=seq_start,
                end_sec=seq_end,
                start_ms=int(round(seq_start * 1000.0)),
                end_ms=int(round(seq_end * 1000.0)),
                score=seq_score,
                matched_cues=list(dict.fromkeys(matched_labels)),
                keyframe_id=anc_m.keyframe_id,
                thumbnail_url=anc_m.thumbnail_url,
                text_snippet=anc_m.text_snippet,
                cue_evidence=evidence
            ))

        # Record partner stage trace summaries
        phase2_ms = round((time.perf_counter() - t_phase2_start) * 1000, 2)
        for s_idx, hits_list in partner_trace_hits.items():
            hits_list_sorted = sorted(hits_list, key=lambda x: x["score"], reverse=True)
            st = stages[s_idx]
            label_text = " | ".join(st.visual_queries or st.ocr_queries)
            cues_trace.append({
                "cue_id": f"s{s_idx}_scan",
                "stage_index": s_idx,
                "modality": "visual" if st.visual_queries else "ocr",
                "query_text": label_text,
                "hits_count": len(hits_list_sorted),
                "latency_ms": phase2_ms,
                "top_hits": self._decorate_trace_hits(self.db, hits_list_sorted, trace_top_hits, include_text=False)
            })

        chained_moments.sort(key=lambda m: m.score, reverse=True)
        return self._dedupe_sequence_moments(chained_moments, top_k=top_k), cues_trace

    def _find_best_partner_in_window(
        self,
        vid: str,
        win_min: float,
        win_max: float,
        q_vec: Optional[Any],
        ocr_queries: List[str],
        ocr_mode: str
    ) -> Optional[Dict[str, Any]]:
        """Finds the best-matching keyframe for a partner stage inside [win_min, win_max] of a video."""
        # Collect partner OCR matches inside the video window if OCR cues are present
        ocr_window_hits: List[Dict[str, Any]] = []
        if ocr_queries:
            for oq in ocr_queries:
                raw = self._search_ocr_cue(oq, top_k=100, video_id=vid)
                for h in self._filter_quality_ocr_hits(raw, min_score=0.35):
                    ts = float(h.get("timestamp_sec", 0.0))
                    if win_min <= ts <= win_max:
                        ocr_window_hits.append(h)

            if ocr_mode == "filter" and not ocr_window_hits:
                return None

        if q_vec is None:
            # OCR-only partner stage
            if not ocr_window_hits:
                return None
            return max(ocr_window_hits, key=lambda h: float(h.get("score", 0.0)))

        vis_hits = self._score_visual_subset(
            q_vec=q_vec,
            target_videos={vid},
            top_k=50,
            min_sec=win_min,
            max_sec=win_max
        )
        if not vis_hits:
            return None

        best_vis = vis_hits[0]
        if float(best_vis.get("score", 0.0)) < 0.05:
            return None

        if ocr_window_hits:
            best_ocr = max(ocr_window_hits, key=lambda h: float(h.get("score", 0.0)))
            best_vis["score"] = float(best_vis["score"]) * (1.0 + 0.25 * float(best_ocr.get("score", 0.0)))
            best_vis["text_detected"] = best_ocr.get("text_detected")
        return best_vis

    @staticmethod
    def _dedupe_sequence_moments(
        moments: List[CandidateMoment],
        top_k: int,
        iou_threshold: float = 0.4
    ) -> List[CandidateMoment]:
        """Applies per-video temporal NMS on ranked sequential pairs."""
        from src.retrieval.score_fusion import compute_temporal_iou

        kept_by_vid: Dict[str, List[CandidateMoment]] = {}
        final_list: List[CandidateMoment] = []
        for m in moments:
            vid_kept = kept_by_vid.setdefault(m.video_id, [])
            overlap = any(
                compute_temporal_iou(m.start_sec, m.end_sec, ex.start_sec, ex.end_sec) >= iou_threshold
                for ex in vid_kept
            )
            if not overlap:
                vid_kept.append(m)
                final_list.append(m)
                if len(final_list) >= top_k:
                    break
        return final_list

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
                new_stages.append(QueryStage(
                    visual_queries=v_all,
                    ocr_queries=[],
                    negative_visual_queries=list(getattr(st, "negative_visual_queries", []))
                ))
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
        video_id: Optional[str] = None,
        negative_cues: Optional[List[str]] = None,
        allowed_batches: Optional[Set[str]] = None,
        excluded_videos: Optional[Set[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Encodes English visual description (with optional negative cue vector subtraction)
        and searches FAISS index while honoring video, batch, and exclusion scope filters.
        """
        clean_cue = visual_cue.strip()
        if not clean_cue:
            return []

        q_vec = self._encode_visual_vector([clean_cue], negative_cues=negative_cues)
        if q_vec is None:
            return []

        return self._execute_filtered_visual_vector_search(
            q_vec,
            top_k=top_k,
            video_id=video_id,
            allowed_batches=allowed_batches,
            excluded_videos=excluded_videos
        )

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

    def _search_scoped_ocr_cue(
        self,
        ocr_cue: str,
        top_k: int = 500,
        video_id: Optional[str] = None,
        allowed_batches: Optional[Set[str]] = None,
        excluded_videos: Optional[Set[str]] = None
    ) -> List[Dict[str, Any]]:
        """Runs _search_ocr_cue with oversampling and filters by batch scope and video blacklist."""
        has_scope = (allowed_batches is not None) or bool(excluded_videos)
        fetch_k = top_k * 3 if has_scope else top_k
        raw_hits = self._search_ocr_cue(ocr_cue, top_k=fetch_k, video_id=video_id)
        if not has_scope:
            return raw_hits[:top_k]
        filtered = self._filter_hits_by_scope(
            raw_hits,
            allowed_batches=allowed_batches,
            excluded_videos=excluded_videos
        )
        return filtered[:top_k]

    def _resolve_hit_thumbnail(self, hit: Dict[str, Any], fallback_vid: str) -> None:
        """Populates thumbnail_url on a hit dict if missing."""
        if not isinstance(hit, dict):
            return
        c_vid = hit.get("video_id") or fallback_vid
        c_kfid = hit.get("keyframe_id")
        if c_kfid and not hit.get("thumbnail_url"):
            fp = hit.get("file_path") or self.db.get_keyframe_path(c_kfid)
            if fp:
                hit["thumbnail_url"] = f"/api/keyframes/{c_vid}/{Path(fp).name}"
            else:
                hit["thumbnail_url"] = f"/api/keyframes/{c_vid}/{c_kfid}.jpg"

    def _decorate_moments(self, moments: List[CandidateMoment]) -> None:
        """Decorates CandidateMoment instances with thumbnail image URLs."""
        if not moments:
            return

        for m in moments:
            vid = m.video_id
            if m.keyframe_id and not m.thumbnail_url:
                fp = self.db.get_keyframe_path(m.keyframe_id)
                if fp:
                    m.thumbnail_url = f"/api/keyframes/{vid}/{Path(fp).name}"
                else:
                    m.thumbnail_url = f"/api/keyframes/{vid}/{m.keyframe_id}.jpg"

            if m.cue_evidence:
                for cue_id, hit in m.cue_evidence.items():
                    if isinstance(hit, list):
                        for item in hit:
                            self._resolve_hit_thumbnail(item, vid)
                    elif isinstance(hit, dict):
                        self._resolve_hit_thumbnail(hit, vid)


def main() -> None:
    parser = argparse.ArgumentParser(description="Unified Multimodal Video Moment Search Engine CLI.")
    parser.add_argument("--query", "-q", type=str, required=True, help="Query string or multi-cue prefix string.")
    parser.add_argument("--mode", type=str, default="auto", choices=["auto", "visual", "ocr"], help="Search mode.")
    parser.add_argument("--top-k", type=int, default=10, help="Number of moments to retrieve.")
    parser.add_argument("--video-id", type=str, default=None, help="Filter search to a specific video ID.")
    parser.add_argument("--trace", action="store_true", help="Print explainable pipeline execution trace.")
    args = parser.parse_args()

    engine = SearchEngine()
    try:
        results, trace = engine.search_with_trace(
            query=args.query,
            mode=args.mode,
            top_k=args.top_k,
            video_id=args.video_id,
            trace_top_hits=5
        )

        if args.trace:
            print("\n" + "=" * 80)
            print(f"[TRACE] Pipeline Turnaround Time: {trace['total_time_ms']} ms | Stages: {trace['total_stages']} | Sequential: {trace['is_sequential']}")
            print(f"[TRACE] Multi-Cue Consensus Moments: {trace['consensus_moments_count']} / {trace['total_moments_found']}")
            for cue in trace.get("cues", []):
                print(f"  -> Cue '{cue['cue_id']}' [{cue['modality'].upper()}]: '{cue['query_text']}' | Hits: {cue['hits_count']} in {cue['latency_ms']} ms")
                for th in cue.get("top_hits", [])[:3]:
                    txt = f" | Text: '{th.get('text_detected', '')[:30]}'" if "text_detected" in th else ""
                    print(f"       #{th['rank']}: {th['keyframe_id']} ({th['timestamp_sec']}s) Score: {th['score']:.4f}{txt}")
            print("=" * 80)

        print(f"\n[OK] Retrieved {len(results)} candidate moments for query: '{args.query}' (Mode: {args.mode})")
        print("=" * 80)
        for rank, m in enumerate(results, start=1):
            mins_s, secs_s = int(m.start_sec // 60), m.start_sec % 60
            mins_e, secs_e = int(m.end_sec // 60), m.end_sec % 60
            time_str = f"{mins_s:02d}:{secs_s:05.2f} - {mins_e:02d}:{secs_e:05.2f}"
            cues_str = ", ".join(m.matched_cues)
            snippet = f" | Text: '{m.text_snippet[:40]}...'" if m.text_snippet else ""
            print(f"Rank #{rank:02d} | Score: {m.score:.4f} | Video: {m.video_id} [{time_str}] ({m.start_ms}ms - {m.end_ms}ms) | Cues: [{cues_str}]{snippet}")
            if args.trace and m.cue_evidence:
                for c_id, c_hit in m.cue_evidence.items():
                    if isinstance(c_hit, dict):
                        print(f"       * Evidence [{c_id}]: {c_hit.get('keyframe_id')} @ {c_hit.get('timestamp_sec')}s (score: {float(c_hit.get('score', 0)):.4f})")
                    elif isinstance(c_hit, list):
                        for item in c_hit:
                            if isinstance(item, dict):
                                print(f"       * Stage [{item.get('stage_index')}]: {item.get('keyframe_id')} @ {item.get('timestamp_sec')}s (score: {float(item.get('score', 0)):.4f})")
        print("=" * 80)
    finally:
        engine.safe_unload()


if __name__ == "__main__":
    main()

