# Task 05: Temporal Multimodal Fusion & Query Routing

## 1. Objectives (What)
* Develop a lightweight, rule-based **Query Parser & Router** to decompose user natural language queries into modality-specific retrieval paths (Visual SigLIP2 and On-Screen Text PaddleOCR).
* Resolve the **Score Incompatibility Problem** across disparate scales (SigLIP2 Cosine Similarity [0, 0.4] vs SQLite FTS5 / BM25 Lexical Scores [0, 30]).
* Implement a **5-Second Temporal Sliding Window** with 2.5-second stride (50% overlap) to eliminate boundary fragmentation across time.
* Apply **Temporal Non-Maximum Suppression (NMS)** to merge overlapping candidate windows into coherent, continuous video moments.

---

## 2. Implementation Steps (How)

### Step 2.1: Query Parser & Router (Latency < 1ms)
1. **On-Screen Text (OCR) Branch:**
   * If query contains quoted terms (e.g. `"Pho Hoa"`), uppercase abbreviations, or explicit visual text triggers ("chữ", "biển hiệu", "tiêu đề", "bảng", "text", "signboard", "title", "license plate") -> dispatch to SQLite FTS5 index.
2. **Visual Semantic Branch:**
   * Use the full descriptive query, translate to English if needed via local offline translation -> encode via SigLIP2 text encoder and query FAISS visual index.

### Step 2.2: Score Normalization with Weighted Reciprocal Rank Fusion (RRF)
* Avoid raw score addition. Apply weighted RRF across Top-100 results per channel:
  `RRF_Score = Channel_Weight / (60 + rank)`
  * Default weights: `weight_visual = 1.0`, `weight_ocr = 1.5` (exact on-screen text matches carry higher precision).

### Step 2.3: Sliding Window Aggregation & Temporal NMS
1. **Time Grid Discretization:**
   * Construct 5.0-second sliding windows with 2.5-second stride:
     `[0.0 - 5.0s]`, `[2.5 - 7.5s]`, `[5.0 - 10.0s]`, `[7.5 - 12.5s]`, ...
2. **Score Accumulation:**
   * Map hits from keyframes and OCR text timestamps to all overlapping windows.
   * Intervals co-referenced across both visual and text channels receive cumulative score boosts.
3. **Temporal Non-Maximum Suppression (NMS):**
   * Merge contiguous high-scoring candidate windows into unified temporal spans: `[start_min, end_max]`.
   * Return the Top 20 ranked moments system-wide.

---

## 3. Verification & Acceptance Criteria
1. **Multi-Channel Alignment Test:**
   * Create mock hits where Visual matches a scene at 15s and OCR matches a sign at 14s.
   * Run fusion: Interval `12.5s - 17.5s` must rank #1 due to multi-channel consensus.
2. **Ablation Study Matrix:**
   * Run [src/evaluation/evaluate.py](file:///d:/UIT/TX/doan/src/evaluation/evaluate.py) on `data/ground_truth.json` comparing:
     * Baseline: Visual Only
     * Text Only: OCR Only
     * Multimodal Fusion: Visual + OCR
   * Verify Multimodal Fusion achieves measurable improvement in `Recall@10` over the visual baseline.
