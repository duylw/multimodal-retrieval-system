# Task 05: Temporal Multimodal Fusion & Query Routing

## 1. Objectives (What)
* Develop a lightweight, rule-based **Query Parser & Router** to decompose user natural language queries into modality-specific retrieval paths (Visual, ASR, OCR).
* Resolve the **Score Incompatibility Problem** across disparate scales (SigLIP2 Cosine Similarity [0, 0.4] vs BM25 / FTS5 Lexical Scores [0, 30]).
* Implement a **5-Second Temporal Sliding Window** with 2.5-second stride (50% overlap) to eliminate boundary fragmentation across time.
* Apply **Temporal Non-Maximum Suppression (NMS)** to merge overlapping candidate windows into coherent, continuous video moments.

---

## 2. Implementation Steps (How)

### Step 2.1: Query Parser & Router (Latency < 1ms)
1. **OCR Branch:**
   * If query contains quoted terms (e.g. `"Pho Hoa"`) or explicit visual text triggers ("text", "signboard", "title", "score", "price") -> dispatch to SQLite FTS5 index.
2. **Speech (ASR) Branch:**
   * If query contains speech patterns ("spoken", "interview", "explains", "lyrics", "singing") -> dispatch to BM25 and `bge-m3` ASR indices.
3. **Visual Branch:**
   * Use the full descriptive query, translate to English if needed via local offline translation -> encode via SigLIP2 text encoder and query FAISS.

### Step 2.2: Score Normalization with Weighted Reciprocal Rank Fusion (RRF)
* Avoid raw score addition. Apply weighted RRF across Top-100 results per channel:
  `RRF_Score = Channel_Weight / (60 + rank)`
  * Default weights: `weight_visual = 1.0`, `weight_asr = 1.2`, `weight_ocr = 1.5` (exact text matches carry higher precision).

### Step 2.3: Sliding Window Aggregation & Temporal NMS
1. **Time Grid Discretization:**
   * Construct 5.0-second sliding windows with 2.5-second stride:
     `[0.0 - 5.0s]`, `[2.5 - 7.5s]`, `[5.0 - 10.0s]`, `[7.5 - 12.5s]`, ...
2. **Score Accumulation:**
   * Map hits from keyframes and transcript segments to all overlapping windows.
   * Intervals co-referenced across multiple channels receive cumulative score boosts.
3. **Temporal Non-Maximum Suppression (NMS):**
   * Merge contiguous high-scoring candidate windows into unified temporal spans: `[start_min, end_max]`.
   * Return the Top 20 ranked moments system-wide.

---

## 3. Verification & Acceptance Criteria
1. **Synthetic Multi-Channel Alignment Test:**
   * Create mock hits where Visual points to 15s, ASR points to 12-18s, and OCR points to 45s.
   * Run fusion: Interval `12.0s - 18.0s` must rank #1 due to multi-channel consensus.
2. **Ablation Study Matrix:**
   * Run [src/evaluation/evaluate.py](file:///d:/UIT/TX/doan/src/evaluation/evaluate.py) on `data/ground_truth.json` comparing:
     * Baseline: Visual Only
     * Visual + ASR
     * Visual + OCR
     * Full Fusion (Visual + ASR + OCR)
   * Verify Full Fusion achieves a 15% to 30% absolute improvement in `Recall@10` over the visual baseline.
