---
name: temporal-multimodal-fusion
description: >-
  Use this skill whenever implementing, debugging, or tuning multimodal query processing, score fusion,
  or temporal alignment across Visual (SigLIP2) and On-Screen Text (EasyOCR). Covers Reciprocal
  Rank Fusion (RRF), Max-Per-Cue 5-second sliding windows, chronological sequence alignment (>>), and temporal Non-Maximum Suppression (NMS).
---

# Multimodal Temporal Fusion Runbook

This skill outlines the exact procedures for aligning heterogeneous search scores across time and combining them into ranked video moments without scale bias or intra-window double-counting.

---

## 1. Query Decomposition, Language Convention & Multi-Cue Routing

Avoid slow LLM or translation calls during query time. Parse queries with deterministic rule-based patterns (< 1ms latency) and support **Human-in-the-Loop Multi-Cue Composition**:

* **Language Convention:**
  * **Visual Cues (`v:`):** Input directly in **English** to align with `google/siglip2-base-patch16-256` embeddings.
  * **OCR Cues (`ocr:`):** Input in **Vietnamese (accented or unaccented) or Latin/Alphanumeric** matching on-screen text.
* **Multi-Cue & Sequential Syntax Support:**
  * Co-occurring multi-cue prefix: `v: <visual_cue_1> | v: <visual_cue_2> | ocr: <ocr_text>`
  * Chronological sequence operator (`>>`): `v: <scene_stage_1> >> v: <scene_stage_2> | ocr: <text>`
  * Quoted inline prefix: `<visual_cue> ocr:"<exact_text>"`
  * Multi-Cue JSON Payload: `{ "visual_queries": [...], "ocr_queries": [...], "sequence_stages": [...] }`
* **Branch OCR (On-screen text):**
  * Route extracted term to keyframe-aggregated SQLite FTS5 table `ocr_fts` in [src/indexers/metadata_db.py](file:///d:/UIT/TX/doan/src/indexers/metadata_db.py) with deep candidate pool (`top_k_ocr = 500`, Stage 1 `pool_limit >= 500`).
* **Branch Visual (SigLIP2):**
  * Encode each English visual cue with SigLIP2 text encoder in [src/extractors/visual.py](file:///d:/UIT/TX/doan/src/extractors/visual.py) and retrieve `top_k_visual = 1500` candidates from [data/indices/visual_siglip2.index](file:///d:/UIT/TX/doan/data/indices/visual_siglip2.index) so broad attributes do not drop out before multi-cue intersection.

---

## 2. Generalized Multi-Cue Reciprocal Rank Fusion (Multi-Cue RRF)

Never add raw similarity scores directly. Cosine similarity ranges in `[0.0, 0.4]`, while SQLite FTS5 / Fuzzy scores range in `[0.0, 1.0]`.

### Pointwise RRF Conversion
For a candidate keyframe hit at rank `r` (`1 <= r <= top_k`) for cue `c`:
```text
RRF(hit, c) = weight_c / (60 + r)
```

Default Weights:
* `weight_visual = 1.0` per visual cue (`c in 1..M`)
* `weight_ocr = 1.5` per OCR text cue (`c in 1..N`)

---

## 3. Max-Per-Cue Temporal Sliding Window & Sequence Alignment

To eliminate boundary cut effects while preventing **Intra-Window Double-Counting Bias** (where a static shot with 3 redundant keyframes matching a single cue outscores a moment matching 2 distinct cues):

1. **Window Parameters:**
   * Window Size: `5.0 seconds`
   * Window Stride (Step): `2.5 seconds` (50% overlap)
2. **Max-Per-Cue Aggregation Rule (Critical):**
   * Within any 5.0s window `W = [t_start, t_end]`, each query cue `c` contributes **at most once** using its highest-scoring keyframe inside `W`:
     ```text
     Window_Raw_Score(W) = Sum_{i=1..M} [ Max_{kf in W} RRF(kf, V_i) ]
                         + Sum_{j=1..N} [ Max_{kf in W} RRF(kf, OCR_j) ]
     ```
3. **Multi-Cue Consensus Multiplier:**
   * Let `K_matched(W)` be the number of distinct cues (`1 <= K_matched(W) <= M + N`) present in window `W`:
     ```text
     Window_Score(W) = Window_Raw_Score(W) * (1.0 + 0.25 * (K_matched(W) - 1))
     ```
4. **Chronological Sequence Alignment (`Stage 1 >> Stage 2`):**
   * When sequential stages are specified, link window `W_a` (from Stage 1) and window `W_b` (from Stage 2) in the same video if `0.0 <= t_start(W_b) - t_start(W_a) <= 15.0s`, summing their stage scores plus a sequence bonus and spanning `[t_start(W_a), t_end(W_b)]`.

---

## 4. Temporal Non-Maximum Suppression (NMS) & Segment Merging

Consecutive sliding windows with high scores represent the same ongoing event:

1. Sort all candidate windows by `Window_Score(W)` in descending order.
2. Greedily select the top candidate window `[w_start, w_end]`:
   * Merge adjacent or overlapping high-scoring windows into `[min_start, max_end]`.
   * Suppress overlapping lower-ranked candidates with temporal `IoU >= 0.4`.
3. Return the Top-25 distinct moments with `[start_ms, end_ms]`, confidence score, and matched cue tags.
