"""
Scientific evaluation harness for multimodal video moment retrieval.
Computes Recall@1, Recall@5, Recall@10, Mean Reciprocal Rank (MRR),
and modality-specific ablation breakdowns.
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger


def compute_temporal_iou(
    pred_interval: Tuple[float, float],
    gt_interval: Tuple[float, float]
) -> float:
    """
    Computes Temporal Intersection over Union (IoU) between two time intervals.

    Args:
        pred_interval: Tuple of (start_sec, end_sec) for prediction.
        gt_interval: Tuple of (start_sec, end_sec) for ground truth.

    Returns:
        IoU score in range [0.0, 1.0].
    """
    p_start, p_end = pred_interval
    g_start, g_end = gt_interval

    intersection_start = max(p_start, g_start)
    intersection_end = min(p_end, g_end)
    intersection = max(0.0, intersection_end - intersection_start)

    union_start = min(p_start, g_start)
    union_end = max(p_end, g_end)
    union = max(0.0, union_end - union_start)

    if union <= 0.0:
        return 0.0
    return intersection / union


def is_hit(
    pred: Dict[str, Any],
    gt: Dict[str, Any],
    tolerance_sec: float = 5.0,
    min_iou: float = 0.3,
    use_iou_mode: bool = False
) -> bool:
    """
    Determines whether a prediction is a valid hit against ground truth.

    Condition A (Tolerance Window): Center timestamp falls within [gt_start - tol, gt_end + tol].
    Condition B (IoU Threshold): Temporal IoU between predicted and true interval >= min_iou.

    Args:
        pred: Predicted item containing 'video_file', 'start_sec', 'end_sec'.
        gt: Ground truth item containing 'video_file', 'target_interval'.
        tolerance_sec: Allowed margin in seconds for tolerance matching.
        min_iou: Minimum IoU threshold for IoU matching.
        use_iou_mode: If True, uses Condition B; otherwise uses Condition A.

    Returns:
        True if hit condition is satisfied, False otherwise.
    """
    # Video file must match
    pred_video = pred.get("video_file") or pred.get("video_id")
    gt_video = gt.get("video_file") or gt.get("video_id")
    if pred_video != gt_video:
        return False

    gt_start, gt_end = gt["target_interval"]
    p_start = float(pred.get("start_sec", 0.0))
    p_end = float(pred.get("end_sec", p_start))

    if use_iou_mode:
        iou = compute_temporal_iou((p_start, p_end), (gt_start, gt_end))
        return iou >= min_iou

    # Condition A: Tolerance window matching
    p_center = (p_start + p_end) / 2.0
    return (p_center >= (gt_start - tolerance_sec)) and (p_center <= (gt_end + tolerance_sec))


def evaluate_retrieval(
    ground_truth: List[Dict[str, Any]],
    predictions: Dict[str, List[Dict[str, Any]]],
    ks: List[int] = [1, 5, 10],
    tolerance_sec: float = 5.0,
    min_iou: float = 0.3,
    use_iou_mode: bool = False
) -> Dict[str, Any]:
    """
    Evaluates ranking predictions against ground truth list.

    Args:
        ground_truth: List of ground truth objects.
        predictions: Mapping from query_id to ranked list of prediction objects.
        ks: List of K cutoffs for Recall@K.
        tolerance_sec: Timestamp tolerance window in seconds.
        min_iou: Minimum IoU threshold.
        use_iou_mode: Whether to evaluate using IoU criteria.

    Returns:
        Dictionary containing overall metrics and modality breakdowns.
    """
    valid_gt = [
        g for g in ground_truth
        if isinstance(g, dict) and "query_id" in g and not g.get("is_template_notice")
    ]
    total_queries = len(valid_gt)
    if total_queries == 0:
        return {"error": "Ground truth list is empty"}

    recall_hits = {k: 0 for k in ks}
    reciprocal_ranks = []

    # Track metrics broken down by modality
    modality_stats: Dict[str, Dict[str, Any]] = {}

    for gt in valid_gt:
        qid = gt["query_id"]
        preds_for_q = predictions.get(qid, [])
        modalities = gt.get("modality_expected", ["unknown"])

        first_hit_rank: Optional[int] = None

        # Check hits across the ranked list
        for rank_idx, pred in enumerate(preds_for_q, start=1):
            if is_hit(pred, gt, tolerance_sec=tolerance_sec, min_iou=min_iou, use_iou_mode=use_iou_mode):
                if first_hit_rank is None:
                    first_hit_rank = rank_idx
                # Count Recall@K
                for k in ks:
                    if rank_idx <= k:
                        pass  # Handled below by first_hit_rank

        # Process first hit rank for MRR and Recall@K
        if first_hit_rank is not None:
            reciprocal_ranks.append(1.0 / first_hit_rank)
            for k in ks:
                if first_hit_rank <= k:
                    recall_hits[k] += 1
        else:
            reciprocal_ranks.append(0.0)

        # Update modality-specific stats
        for mod in modalities:
            if mod not in modality_stats:
                modality_stats[mod] = {
                    "total": 0,
                    "first_ranks": [],
                    "hits_at_k": {k: 0 for k in ks}
                }
            modality_stats[mod]["total"] += 1
            if first_hit_rank is not None:
                modality_stats[mod]["first_ranks"].append(1.0 / first_hit_rank)
                for k in ks:
                    if first_hit_rank <= k:
                        modality_stats[mod]["hits_at_k"][k] += 1
            else:
                modality_stats[mod]["first_ranks"].append(0.0)

    # Calculate macro aggregates
    mrr = sum(reciprocal_ranks) / total_queries
    recall_results = {f"Recall@{k}": recall_hits[k] / total_queries for k in ks}

    # Calculate modality breakdowns
    modality_breakdown = {}
    for mod, stat in modality_stats.items():
        cnt = stat["total"]
        if cnt > 0:
            mod_mrr = sum(stat["first_ranks"]) / cnt
            mod_recalls = {f"Recall@{k}": stat["hits_at_k"][k] / cnt for k in ks}
            modality_breakdown[mod] = {
                "count": cnt,
                "MRR": round(mod_mrr, 4),
                **{k: round(v, 4) for k, v in mod_recalls.items()}
            }

    return {
        "total_queries": total_queries,
        "matching_mode": "IoU" if use_iou_mode else "Timestamp Tolerance",
        "MRR": round(mrr, 4),
        **{k: round(v, 4) for k, v in recall_results.items()},
        "modality_breakdown": modality_breakdown
    }


def format_evaluation_table(results: Dict[str, Any], config_name: str = "Current Model") -> str:
    """Formats evaluation results as a clean Markdown table without icons or LaTeX."""
    lines = [
        f"### Evaluation Benchmark Results: {config_name}",
        f"Matching Mode: {results.get('matching_mode', 'N/A')} (Total Queries: {results.get('total_queries', 0)})",
        "",
        "| Metric | Score |",
        "|---|---|",
        f"| Recall@1 | {results.get('Recall@1', 0.0):.4f} |",
        f"| Recall@5 | {results.get('Recall@5', 0.0):.4f} |",
        f"| Recall@10 | {results.get('Recall@10', 0.0):.4f} |",
        f"| MRR | {results.get('MRR', 0.0):.4f} |",
        ""
    ]

    breakdown = results.get("modality_breakdown", {})
    if breakdown:
        lines.append("#### Performance by Expected Modality")
        lines.append("| Modality | Sample Count | Recall@1 | Recall@5 | Recall@10 | MRR |")
        lines.append("|---|---|---|---|---|---|")
        for mod, stats in breakdown.items():
            lines.append(
                f"| {mod} | {stats.get('count', 0)} | "
                f"{stats.get('Recall@1', 0.0):.4f} | "
                f"{stats.get('Recall@5', 0.0):.4f} | "
                f"{stats.get('Recall@10', 0.0):.4f} | "
                f"{stats.get('MRR', 0.0):.4f} |"
            )
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate video moment retrieval predictions.")
    parser.add_argument("--gt", type=str, default=None, help="Path to ground_truth.json")
    parser.add_argument("--pred", type=str, default=None, help="Path to predictions.json")
    parser.add_argument("--out", type=str, default=None, help="Optional path to save metrics JSON")
    parser.add_argument("--name", type=str, default="Retrieval Model", help="Experiment name")
    parser.add_argument("--iou", action="store_true", help="Use IoU matching mode instead of tolerance")
    parser.add_argument("--tolerance", type=float, default=5.0, help="Timestamp tolerance in seconds")
    parser.add_argument("--min_iou", type=float, default=0.3, help="Minimum IoU threshold")
    args = parser.parse_args()

    if args.gt and args.pred:
        logger.info(f"[EVAL] Evaluating predictions: {args.pred} against ground truth: {args.gt}")
        with open(args.gt, "r", encoding="utf-8") as f:
            gt_data = json.load(f)
        with open(args.pred, "r", encoding="utf-8") as f:
            pred_data = json.load(f)

        results = evaluate_retrieval(
            ground_truth=gt_data,
            predictions=pred_data,
            ks=[1, 5, 10],
            tolerance_sec=args.tolerance,
            min_iou=args.min_iou,
            use_iou_mode=args.iou
        )
        table_str = format_evaluation_table(results, config_name=args.name)
        print("\n" + table_str)

        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            logger.info(f"[EVAL] Metrics saved to {args.out}")
    else:
        logger.info("[EVAL] Running self-test with dummy ground truth and predictions...")

        # Define minimal dummy ground truth
        dummy_gt = [
            {
                "query_id": "test_q01",
                "query": "cận cảnh đĩa thức ăn",
                "video_file": "L13_V001.mp4",
                "target_interval": [50.0, 70.0],
                "modality_expected": ["visual"]
            },
            {
                "query_id": "test_q02",
                "query": "người dẫn chương trình nói về thời tiết",
                "video_file": "L13_V001.mp4",
                "target_interval": [10.0, 30.0],
                "modality_expected": ["speech"]
            },
            {
                "query_id": "test_q03",
                "query": "biển hiệu cửa hàng",
                "video_file": "L13_V002.mp4",
                "target_interval": [100.0, 120.0],
                "modality_expected": ["ocr"]
            }
        ]

        # Define mock predictions:
        # q01: Rank 1 is hit (center 60s in [45s, 75s])
        # q02: Rank 2 is hit (center 20s in [5s, 35s])
        # q03: No hit in top 5
        dummy_preds = {
            "test_q01": [
                {"video_file": "L13_V001.mp4", "start_sec": 55.0, "end_sec": 65.0, "score": 0.95},
                {"video_file": "L13_V001.mp4", "start_sec": 10.0, "end_sec": 20.0, "score": 0.50}
            ],
            "test_q02": [
                {"video_file": "L13_V001.mp4", "start_sec": 80.0, "end_sec": 90.0, "score": 0.88},
                {"video_file": "L13_V001.mp4", "start_sec": 15.0, "end_sec": 25.0, "score": 0.82}
            ],
            "test_q03": [
                {"video_file": "L13_V002.mp4", "start_sec": 200.0, "end_sec": 220.0, "score": 0.70}
            ]
        }

        eval_out = evaluate_retrieval(dummy_gt, dummy_preds, ks=[1, 5, 10])
        table_str = format_evaluation_table(eval_out, config_name="Self-Test Dummy")
        print("\n" + table_str)

        assert eval_out["MRR"] == 0.5, f"Expected MRR 0.5, got {eval_out['MRR']}"
        assert eval_out["Recall@1"] == 0.3333, f"Expected Recall@1 0.3333, got {eval_out['Recall@1']}"
        assert eval_out["Recall@5"] == 0.6667, f"Expected Recall@5 0.6667, got {eval_out['Recall@5']}"
        logger.info("[EVAL] All mathematical assertions passed successfully!")
