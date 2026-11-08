# Task 05: Temporal Multimodal Fusion, Query Routing & Multi-Cue Composition

## 1. Objectives (What)
* Develop a flexible **Query Decomposition & Router Engine** supporting both automatic rule-based parsing and **Human-in-the-Loop Multi-Cue Query Composition** (explicitly adding multiple visual cues and OCR text filters).
* Prevent **Semantic Dilution** in long complex queries by allowing contestants to decouple independent scene attributes (e.g. `+ Visual: "a blue truck"`, `+ Visual: "heavy rain"`, `+ OCR: "51C 456.78"`).
* Resolve the **Score Incompatibility Problem** across disparate scales (SigLIP2 Cosine Similarity `[0.0, 0.4]` vs SQLite FTS5 / BM25 Lexical Scores `[0.0, 35.0]`) via Generalized Multi-Channel Reciprocal Rank Fusion (RRF).
* Implement a **5-Second Temporal Sliding Window** with 2.5-second stride (50% overlap) to aggregate multi-cue evidence and eliminate boundary cut effects across time.
* Apply **Temporal Non-Maximum Suppression (NMS)** to merge overlapping candidate windows into coherent, continuous video moments `[start_ms, end_ms]` ready for DRES submission.

---

## 2. Technical Specifications & Implementation Steps (How)

### Step 2.1: Query Input Modalities & Multi-Cue Parser
The engine in [src/retrieval/query_parser.py](file:///d:/UIT/TX/doan/src/retrieval/query_parser.py) will support three query entry mechanisms:

1. **Structured Multi-Cue JSON Payload (API / Programmatic):**
   ```json
   {
     "visual_queries": [
       "a blue truck",
       "heavy rain in warehouse yard"
     ],
     "ocr_queries": [
       "51C 456.78"
     ],
     "weights": {
       "visual": 1.0,
       "ocr": 1.5
     }
   }
   ```
2. **Power-User Prefix Syntax (CLI & Single Search Bar):**
   * Contiguous syntax with explicit prefix indicators:
     `v: a blue truck | v: heavy rain | ocr: 51C 456.78`
   * Google-style quoted syntax:
     `a blue truck in heavy rain ocr:"51C 456.78"`
   * Parser separates `ocr:` and `ocr:"..."` tokens into the OCR retrieval branch; remaining segments (split by `|` or commas) are mapped into individual visual query vectors.
3. **Pure Natural Language Fallback (Automatic Routing < 1ms):**
   * If no explicit prefixes are provided, the rule-based router scans for high-entropy text indicators:
     * Quoted tokens (`"..."`), license plate patterns (`^[0-9]{2}[A-Z]-[0-9]{4,5}$`), title/sign markers ("chu", "bien hieu", "bang", "text", "signboard", "title").
     * Extracted text is dispatched to OCR FTS5; the complete context is routed to SigLIP2 visual encoding.

---

### Step 2.2: Generalized Multi-Cue Reciprocal Rank Fusion (Multi-Cue RRF)
In [src/retrieval/score_fusion.py](file:///d:/UIT/TX/doan/src/retrieval/score_fusion.py), calculate rank-based scores across all active query cues rather than adding raw heterogeneous scores:

For a candidate moment evaluated against $M$ visual cues and $N$ OCR text queries:

```text
RRF_Score(Moment) = Sum_{i=1..M} [ W_visual / (60 + Rank_V_i) ] + Sum_{j=1..N} [ W_ocr / (60 + Rank_OCR_j) ]
```

* **Default Weights:**
  * `W_visual = 1.0` per visual cue.
  * `W_ocr = 1.5` per OCR text cue (exact on-screen text matches provide higher discrimination).
* **Consensus Dynamics:**
  * Candidates satisfying ALL $M$ visual cues AND the OCR cue receive maximum additive RRF scores and surge to Rank #1.
  * Partial matches (e.g. matching 2 out of 3 cues) are stably ranked below complete consensus hits without falling out of the candidate pool.

---

### Step 2.3: Sliding Window Aggregation & Temporal Non-Maximum Suppression (NMS)
1. **Time Grid Discretization:**
   * Construct 5.0-second sliding windows with 2.5-second stride across each video timeline:
     `[0.0 - 5.0s]`, `[2.5 - 7.5s]`, `[5.0 - 10.0s]`, `[7.5 - 12.5s]`, ...
2. **Score Deposit & Multi-Cue Accumulation:**
   * Each keyframe hit deposits its visual RRF score into all overlapping 5s windows.
   * Each OCR text hit deposits its text RRF score into all overlapping 5s windows.
   * Intervals co-referenced across multiple visual cues and OCR records accumulate cumulative consensus scores.
3. **Temporal Non-Maximum Suppression (NMS):**
   * Sort candidate windows by accumulated score in descending order.
   * Greedily select the top window `[start, end]`.
   * Merge contiguous overlapping high-scoring windows into a unified temporal span: `[start_min, end_max]`.
   * Suppress overlapping candidates with temporal Intersection over Union (IoU) >= 0.4.
   * Return Top 25 ranked video moments with millisecond boundaries: `{ video_id, start_sec, end_sec, start_ms, end_ms, score, matched_cues }`.

---

### Step 2.4: Human-in-the-Loop Multi-Cue Query Builder in Web UI
In [src/ui/static/index.html](file:///d:/UIT/TX/doan/src/ui/static/index.html) and [src/ui/static/app.js](file:///d:/UIT/TX/doan/src/ui/static/app.js):
* Provide an interactive **Multi-Cue Query Builder** toggle:
  * `[+ Add Visual Cue]`: Inserts an individual visual input row (e.g. "a blue truck").
  * `[+ Add OCR Text]`: Inserts an individual text input row (e.g. "51C 456.78").
  * Each cue has an active tag badge and an `[X]` remove button.
* Synchronizes two-way between the interactive visual builder and the single power-user search input bar.

---

## 3. Architecture & Data Flow

```text
[User Multi-Cue Query]
  ├─► Visual Cue 1: "a blue truck"
  ├─► Visual Cue 2: "heavy rain"
  └─► OCR Cue:      "51C 456.78"
           │
           ▼
[src/retrieval/query_parser.py] (Decomposition & Routing)
           │
           ├─► SigLIP2 Encode(Cue 1) ──► FAISS Visual Search ──► Ranked List R_v1
           ├─► SigLIP2 Encode(Cue 2) ──► FAISS Visual Search ──► Ranked List R_v2
           └─► SQLite FTS5 + Fuzzy Search("51C 456.78")       ──► Ranked List R_ocr
                                   │
                                   ▼
[src/retrieval/score_fusion.py] (Multi-Cue RRF & 5s Sliding Window)
  - Accumulate: RRF_Score = 1/(60+R_v1) + 1/(60+R_v2) + 1.5/(60+R_ocr)
  - Temporal NMS merges contiguous windows into [start_ms, end_ms]
                                   │
                                   ▼
[Top Ranked Video Moments] ──► Web UI Inspector & 1-Click DRES Submission
```

---

## 4. Verification & Acceptance Criteria
1. **Multi-Cue Decomposition Test:**
   * Input: `v: blue truck | v: heavy rain | ocr: 51C 456.78`.
   * Verify parser extracts exactly 2 visual queries and 1 OCR query.
2. **Multi-Channel Alignment & Consensus Test:**
   * Mock synthetic hits: Visual Cue 1 matches at `12.0s`, Visual Cue 2 matches at `13.5s`, OCR matches at `14.0s`.
   * Verify window `[10.0s, 15.0s]` ranks #1 due to 3-way consensus boost.
3. **Semantic Dilution Prevention Test:**
   * Compare single concatenated query vs multi-cue decomposition.
   * Verify multi-cue decomposition improves Top-5 Recall for multi-attribute queries where individual attributes are visually subtle.
4. **End-to-End Latency Benchmark:**
   * Multi-cue retrieval latency (2 visual cues + 1 OCR cue across 726 videos) must complete in **< 150ms** on local machine.
5. **Ablation Matrix:**
   * Validate performance improvements via [src/evaluation/evaluate.py](file:///d:/UIT/TX/doan/src/evaluation/evaluate.py):
     * Baseline: Pure Visual
     * Baseline: Pure OCR
     * Fusion: Auto Hybrid Fusion (Visual + OCR)
