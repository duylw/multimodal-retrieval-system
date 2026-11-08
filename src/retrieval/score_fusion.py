"""
Score Fusion, Temporal Sliding Window, and Non-Maximum Suppression (NMS) Engine.
Implements Generalized Max-Per-Cue Reciprocal Rank Fusion (RRF), Consensus Multipliers,
Chronological Sequence Linking (>>), and Temporal NMS.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set, Tuple
from loguru import logger

from src.common.types import CandidateMoment


def compute_temporal_iou(start_a: float, end_a: float, start_b: float, end_b: float) -> float:
    """Computes 1D temporal Intersection over Union (IoU) between two time intervals."""
    intersection = max(0.0, min(end_a, end_b) - max(start_a, start_b))
    union = max(end_a, end_b) - min(start_a, start_b)
    if union <= 0.0:
        return 0.0
    return intersection / union


class FusionStrategy(ABC):
    """Abstract Strategy interface for multi-channel score fusion."""

    @abstractmethod
    def fuse_single_stage(
        self,
        hits_by_cue: Dict[str, List[Dict[str, Any]]],
        cue_types: Dict[str, str],
        weights: Dict[str, float],
        window_size_sec: float = 5.0,
        stride_sec: float = 2.5
    ) -> List[Dict[str, Any]]:
        """Fuses candidate hits for a single query stage into ranked temporal windows."""
        pass


class MaxPerCueRRFStrategy(FusionStrategy):
    """
    Max-Per-Cue Reciprocal Rank Fusion Strategy.
    Prevents intra-window double-counting by taking the maximum RRF score per cue within
    each temporal window, applying a multi-cue consensus multiplier, and merging via NMS.
    """

    def __init__(self, k_rrf: int = 60, consensus_boost_per_cue: float = 0.25):
        self.k_rrf = k_rrf
        self.consensus_boost_per_cue = consensus_boost_per_cue

    def fuse_single_stage(
        self,
        hits_by_cue: Dict[str, List[Dict[str, Any]]],
        cue_types: Dict[str, str],
        weights: Dict[str, float],
        window_size_sec: float = 5.0,
        stride_sec: float = 2.5
    ) -> List[Dict[str, Any]]:
        """
        Fuses candidate hits across cues into temporal sliding windows using Max-Per-Cue RRF.

        Args:
            hits_by_cue: Mapping of cue_id -> list of candidate hits (each with video_id, timestamp_sec).
            cue_types: Mapping of cue_id -> 'visual' or 'ocr'.
            weights: Modality weights dict (e.g. {'visual': 1.0, 'ocr': 1.5}).
            window_size_sec: Temporal sliding window width (default 5.0s).
            stride_sec: Temporal sliding window stride (default 2.5s).

        Returns:
            List of window dictionaries: {video_id, start_sec, end_sec, score, matched_cues, best_kf}.
        """
        if not hits_by_cue:
            return []

        # Key: (video_id, window_idx) -> { cue_id: max_rrf_score, "hits": [best_hit_per_cue] }
        windows: Dict[Tuple[str, int], Dict[str, Any]] = {}
        total_cues = len(hits_by_cue)

        for cue_id, hits in hits_by_cue.items():
            modality = cue_types.get(cue_id, "visual")
            w_mod = weights.get(modality, 1.0)

            for rank_idx, hit in enumerate(hits, start=1):
                vid = hit.get("video_id")
                ts = float(hit.get("timestamp_sec", 0.0))
                if not vid:
                    continue

                # Pointwise RRF score for this hit under this cue
                rrf_score = w_mod / (self.k_rrf + rank_idx)

                # Determine all sliding windows overlapping with timestamp ts
                # Window i starts at i * stride_sec and spans to i * stride_sec + window_size_sec
                min_win_idx = max(0, int((ts - window_size_sec) // stride_sec) + 1)
                max_win_idx = int(ts // stride_sec)

                for win_idx in range(min_win_idx, max_win_idx + 1):
                    win_start = win_idx * stride_sec
                    win_end = win_start + window_size_sec
                    if not (win_start <= ts <= win_end):
                        continue

                    w_key = (vid, win_idx)
                    if w_key not in windows:
                        windows[w_key] = {
                            "video_id": vid,
                            "start_sec": win_start,
                            "end_sec": win_end,
                            "cue_scores": {},
                            "best_hits": {}
                        }

                    # Max-Per-Cue Rule: retain highest RRF score for this cue within the window
                    curr_max = windows[w_key]["cue_scores"].get(cue_id, 0.0)
                    if rrf_score > curr_max:
                        windows[w_key]["cue_scores"][cue_id] = rrf_score
                        windows[w_key]["best_hits"][cue_id] = hit

        # Aggregate raw scores and apply Multi-Cue Consensus Multiplier
        candidate_windows: List[Dict[str, Any]] = []
        for (vid, win_idx), win_data in windows.items():
            cue_scores = win_data["cue_scores"]
            k_matched = len(cue_scores)
            if k_matched == 0:
                continue

            raw_score = sum(cue_scores.values())

            # Apply consensus multiplier if multi-cue query
            if total_cues > 1 and k_matched > 1:
                multiplier = 1.0 + self.consensus_boost_per_cue * (k_matched - 1)
            else:
                multiplier = 1.0

            final_score = raw_score * multiplier
            best_hit = max(win_data["best_hits"].values(), key=lambda h: float(h.get("score", 0.0)))

            candidate_windows.append({
                "video_id": vid,
                "start_sec": win_data["start_sec"],
                "end_sec": win_data["end_sec"],
                "score": final_score,
                "matched_cues": list(cue_scores.keys()),
                "k_matched": k_matched,
                "best_hit": best_hit
            })

        # Sort candidate windows descending by score
        candidate_windows.sort(key=lambda w: w["score"], reverse=True)
        return candidate_windows


class TemporalMomentFusor:
    """
    Coordinates multi-cue fusion, sequential stage linking (>>),
    and temporal Non-Maximum Suppression (NMS) to generate CandidateMoments.
    """

    def __init__(
        self,
        strategy: Optional[FusionStrategy] = None,
        max_sequence_gap_sec: float = 15.0,
        sequence_bonus: float = 0.05,
        nms_iou_threshold: float = 0.3
    ):
        self.strategy = strategy or MaxPerCueRRFStrategy()
        self.max_sequence_gap_sec = max_sequence_gap_sec
        self.sequence_bonus = sequence_bonus
        self.nms_iou_threshold = nms_iou_threshold

    def fuse_and_nms(
        self,
        stage_results: List[Dict[str, List[Dict[str, Any]]]],
        cue_types: Dict[str, str],
        weights: Dict[str, float],
        top_k: int = 25
    ) -> List[CandidateMoment]:
        """
        Full fusion pipeline:
        1. Fuses per-cue hits inside each stage using Max-Per-Cue RRF sliding windows.
        2. Links multi-stage chronological transitions (>>).
        3. Applies Temporal NMS to produce discrete CandidateMoment instances.
        """
        if not stage_results:
            return []

        # 1. Fuse each stage independently into temporal windows
        fused_stages: List[List[Dict[str, Any]]] = []
        for hits_by_cue in stage_results:
            w_list = self.strategy.fuse_single_stage(hits_by_cue, cue_types, weights)
            fused_stages.append(w_list)

        # 2. Sequential Stage Linking (if query has multiple stages separated by >>)
        if len(fused_stages) > 1:
            raw_candidates = self._link_sequential_stages(fused_stages)
        else:
            raw_candidates = fused_stages[0]

        # 3. Temporal Non-Maximum Suppression (NMS)
        return self._apply_temporal_nms(raw_candidates, top_k=top_k)

    def _link_sequential_stages(
        self,
        fused_stages: List[List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """
        Chains ordered stages (Stage 1 >> Stage 2) within each video within max_sequence_gap_sec.
        """
        stage_1_windows = fused_stages[0]
        stage_2_windows = fused_stages[1]

        # Group Stage 2 by video_id for fast lookup
        s2_by_vid: Dict[str, List[Dict[str, Any]]] = {}
        for w in stage_2_windows:
            s2_by_vid.setdefault(w["video_id"], []).append(w)

        linked_candidates: List[Dict[str, Any]] = []

        for w1 in stage_1_windows:
            vid = w1["video_id"]
            matching_s2 = s2_by_vid.get(vid, [])

            found_link = False
            for w2 in matching_s2:
                time_delta = w2["start_sec"] - w1["start_sec"]
                # Must occur chronologically within sequence gap horizon
                if 0.0 <= time_delta <= self.max_sequence_gap_sec:
                    seq_score = w1["score"] + w2["score"] + self.sequence_bonus
                    linked_candidates.append({
                        "video_id": vid,
                        "start_sec": w1["start_sec"],
                        "end_sec": max(w1["end_sec"], w2["end_sec"]),
                        "score": seq_score,
                        "matched_cues": list(set(w1["matched_cues"] + w2["matched_cues"])),
                        "best_hit": w1.get("best_hit") or w2.get("best_hit")
                    })
                    found_link = True

            if not found_link:
                # Include unlinked stage 1 window with slightly decayed score
                linked_candidates.append(w1)

        linked_candidates.sort(key=lambda x: x["score"], reverse=True)
        return linked_candidates

    def _apply_temporal_nms(
        self,
        candidates: List[Dict[str, Any]],
        top_k: int = 25
    ) -> List[CandidateMoment]:
        """
        Suppresses overlapping lower-ranked windows per video and converts into CandidateMoments.
        """
        if not candidates:
            return []

        # Group by video_id
        by_vid: Dict[str, List[Dict[str, Any]]] = {}
        for c in candidates:
            by_vid.setdefault(c["video_id"], []).append(c)

        final_selected: List[Dict[str, Any]] = []

        for vid, win_list in by_vid.items():
            win_list.sort(key=lambda x: x["score"], reverse=True)
            kept: List[Dict[str, Any]] = []

            for cand in win_list:
                suppress = False
                for existing in kept:
                    iou = compute_temporal_iou(
                        cand["start_sec"], cand["end_sec"],
                        existing["start_sec"], existing["end_sec"]
                    )
                    if iou >= self.nms_iou_threshold:
                        # Merge boundary if high overlap to expand segment gracefully
                        if cand["score"] >= 0.7 * existing["score"]:
                            existing["start_sec"] = min(existing["start_sec"], cand["start_sec"])
                            existing["end_sec"] = max(existing["end_sec"], cand["end_sec"])
                            existing["matched_cues"] = list(set(existing["matched_cues"] + cand["matched_cues"]))
                        suppress = True
                        break

                if not suppress:
                    kept.append(cand)

            final_selected.extend(kept)

        # Sort all deduplicated moments globally by score descending
        final_selected.sort(key=lambda x: x["score"], reverse=True)
        top_selected = final_selected[:top_k]

        moments: List[CandidateMoment] = []
        for item in top_selected:
            s_sec = round(float(item["start_sec"]), 2)
            e_sec = round(float(item["end_sec"]), 2)
            best_h = item.get("best_hit") or {}

            moments.append(CandidateMoment(
                video_id=item["video_id"],
                start_sec=s_sec,
                end_sec=e_sec,
                start_ms=int(round(s_sec * 1000.0)),
                end_ms=int(round(e_sec * 1000.0)),
                score=round(float(item["score"]), 4),
                matched_cues=item.get("matched_cues", []),
                keyframe_id=best_h.get("keyframe_id"),
                thumbnail_url=best_h.get("thumbnail_url"),
                text_snippet=best_h.get("text_detected")
            ))

        return moments
