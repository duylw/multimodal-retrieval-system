---
name: video-benchmark-eval
description: >-
  Use this skill whenever running, modifying, or reporting scientific evaluation metrics for video
  moment retrieval. Covers ground truth dataset formatting, hit condition evaluation (temporal tolerance
  and IoU), Recall@K (K=1, 5, 10), MRR, and automated ablation study comparisons.
---

# Video Retrieval Evaluation Benchmark Runbook

This skill provides step-by-step guidelines for scientific evaluation, ensuring rigorous metric reporting for academic thesis defence.

---

## 1. Ground Truth Format (`data/ground_truth.json`)

Each evaluation item represents a verified query-to-video ground truth interval:

```json
[
  {
    "query_id": "q01",
    "query": "huong dan uop thit bo truoc khi xao",
    "video_file": "nau_an_01.mp4",
    "target_interval": [145.0, 180.0],
    "modality_expected": ["visual", "speech"]
  }
]
```

Target benchmark size: 30-50 queries spanning diverse categories (News, Cooking, Vlog, Lifestyle).

---

## 2. Hit Condition & Matching Logic

A predicted moment `[p_start, p_end]` with center timestamp `p_center = (p_start + p_end) / 2` is evaluated against ground truth `[gt_start, gt_end]`:

### Condition A (Timestamp Tolerance Window)
A prediction is considered a **Hit** if:
`p_center >= (gt_start - 5.0)` AND `p_center <= (gt_end + 5.0)`.

### Condition B (Temporal Intersection over Union - IoU)
Alternatively, calculate interval overlap:
* `Intersection = max(0.0, min(p_end, gt_end) - max(p_start, gt_start))`
* `Union = max(p_end, gt_end) - min(p_start, gt_start)`
* `IoU = Intersection / Union`
* Hit is confirmed if `IoU >= 0.3`.

---

## 3. Metric Computation

### Recall@K (K = 1, 5, 10)
Percentage of test queries where at least one valid Hit appears within the top K returned results:
`Recall@K = (Total queries with at least 1 Hit in Top K) / (Total test queries)`

### Mean Reciprocal Rank (MRR)
Measures how high the first correct hit ranks across all queries:
* For each query, find the rank `r` of the first correct hit.
* Reciprocal rank = `1.0 / r` (or `0.0` if no hit exists in candidate list).
* `MRR = sum(reciprocal_ranks) / Total test queries`.

---

## 4. Ablation Study Reporting Template

Every proposed module must be validated through an ablation study. Output results using this Markdown format:

| Configuration | Modalities Active | Recall@1 | Recall@5 | Recall@10 | MRR | Latency/Query |
|---|---|---|---|---|---|---|
| Baseline | Visual (SigLIP2) only | 0.22 | 0.38 | 0.45 | 0.31 | 0.08s |
| + Speech | Visual + ASR Whisper | 0.35 | 0.58 | 0.68 | 0.44 | 0.12s |
| + OCR | Visual + ASR + PaddleOCR | 0.48 | 0.72 | 0.82 | 0.56 | 0.15s |
| Full Pipeline | Visual + ASR + OCR + CLAP | 0.52 | 0.78 | 0.88 | 0.61 | 0.18s |
