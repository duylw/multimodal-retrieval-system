---
name: temporal-multimodal-fusion
description: >-
  Use this skill whenever implementing, debugging, or tuning multimodal query processing, score fusion,
  or temporal alignment across Visual (SigLIP2) and On-Screen Text (EasyOCR). Covers Reciprocal
  Rank Fusion (RRF), 5-second sliding windows, and temporal Non-Maximum Suppression (NMS).
---

# Multimodal Temporal Fusion Runbook

This skill outlines the exact procedures for aligning heterogeneous search scores across time and combining them into ranked video moments.

---

## 1. Query Decomposition & Multi-Cue Routing

Avoid slow LLM calls during query time. Parse natural language queries with rule-based patterns (< 1ms latency) and support **Human-in-the-Loop Multi-Cue Composition**:

* **Multi-Cue Syntax Support:**
  * Power-user prefix: `v: <visual_cue_1> | v: <visual_cue_2> | ocr: <ocr_text>`
  * Quoted prefix: `<visual_cue> ocr:"<exact_text>"`
  * Multi-Cue JSON Payload: `{ "visual_queries": [...], "ocr_queries": [...] }`
* **Branch OCR (On-screen text):**
  * Trigger: Explicit `ocr:` prefix, substrings enclosed in quotes (`"..."`), or terms like "chu", "bang hieu", "bien so", "text", "signboard".
  * Action: Route extracted term directly to SQLite FTS5 table `ocr_fts` in [src/indexers/metadata_db.py](file:///d:/UIT/TX/doan/src/indexers/metadata_db.py).
* **Branch Visual (SigLIP2):**
  * Action: Translate each visual cue to English if needed via local lightweight translator and encode with SigLIP2 text encoder to search FAISS visual index [data/indices/visual_siglip2.index](file:///d:/UIT/TX/doan/data/indices/visual_siglip2.index).

---

## 2. Generalized Multi-Cue Reciprocal Rank Fusion (Multi-Cue RRF)

Never add raw similarity scores directly. Cosine similarity ranges in `[0.0, 0.4]`, while SQLite FTS5 / BM25 lexical scores range in `[0.0, 35.0+]`.

### Multi-Cue RRF Formula
For $M$ visual cues and $N$ OCR text queries (Top 100 per cue):
```text
RRF_score = Sum_{i=1..M} [ weight_visual / (60 + rank_v_i) ] + Sum_{j=1..N} [ weight_ocr / (60 + rank_ocr_j) ]
```

Default Weights:
* Visual weight: `1.0` per visual cue
* OCR weight: `1.5` per OCR text cue (exact on-screen text match carries high discriminative precision)
* Co-occurrence Boost: Moments co-referenced across multiple visual cues and OCR text receive exponential additive ranking boosts, avoiding semantic dilution.

---

## 3. Temporal Sliding Window (Time-Binning)

To eliminate boundary cut effects where an event spanning second 4 to 7 gets divided and discarded:

1. Configure Window Parameters:
   * Window Size: 5.0 seconds
   * Window Stride (Step): 2.5 seconds (50% overlap)
2. Mapping Strategy:
   * Each keyframe timestamp `t` deposits its score into all windows overlapping with `t`.
   * Each OCR text timestamp `t` deposits its score into all windows overlapping with `t`.
   * Score aggregation: Sum normalized RRF scores within each window. Windows with consensus across both visual and text modalities accumulate the highest totals.

---

## 4. Temporal Non-Maximum Suppression (NMS) & Segment Merging

Consecutive sliding windows with high scores represent the same ongoing event:

1. Sort all windows by aggregated score in descending order.
2. For the top candidate window `[w_start, w_end]`:
   * Look for adjacent or overlapping windows with score > threshold.
   * Merge them into a single continuous moment: `[min_start, max_end]`.
   * Suppress overlapping lower-ranked candidates to avoid returning redundant segments from the same scene.
3. Return the Top-20 distinct moments with start time, end time, confidence score, and contributing modality tags.
