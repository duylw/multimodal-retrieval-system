# Task 05: Temporal Multimodal Fusion, Query Routing & Multi-Cue Composition

## 1. Objectives (What)
* Develop a flexible **Query Decomposition & Router Engine** in [src/retrieval/query_parser.py](file:///d:/UIT/TX/doan/src/retrieval/query_parser.py) supporting automatic rule-based parsing, **Human-in-the-Loop Multi-Cue Query Composition** (combining multiple English visual cues and Vietnamese/Latin OCR text filters), and **Chronological Sequence Operators (`>>`)**.
* Upgrade SQLite FTS5 indexing in [src/indexers/metadata_db.py](file:///d:/UIT/TX/doan/src/indexers/metadata_db.py) from fragmented bounding-box rows to **Keyframe-Level Aggregated Documents** (`GROUP_CONCAT(text_detected, ' ')` per `keyframe_id`) with an expanded Stage 1 candidate pool (`pool_limit >= 500`), ensuring multi-line banners and signboards match holistically without common-word starvation.
* Expand per-cue candidate retrieval depth (`top_k_visual = 1500`, `top_k_ocr = 500`) across the 243,732-keyframe repository so broad visual attributes do not drop out before multi-cue intersection.
* Resolve the **Score Incompatibility Problem** (SigLIP2 Cosine Similarity `[0.0, 0.4]` vs SQLite FTS5 / Fuzzy Lexical Scores `[0.0, 1.0]`) and eliminate **Intra-Window Double-Counting Bias** via **Max-Per-Cue Reciprocal Rank Fusion (RRF)** inside a **5-Second Temporal Sliding Window** (2.5s stride).
* Support **Temporal Sequence Alignment (`Cue A >> Cue B`)** to capture multi-shot narrative transitions within a configurable lookahead horizon (`max_sequence_gap_sec = 15.0s`).
* Apply **Temporal Non-Maximum Suppression (NMS)** to merge overlapping candidate windows into coherent, continuous video moments `[start_ms, end_ms]` ready for DRES submission.

---

## 2. Technical Specifications & Implementation Steps (How)

### Step 2.0: Keyframe-Level OCR FTS5 Aggregation & Deep Candidate Pool (Database Upgrade)
Before running multimodal fusion, eliminate bounding-box fragmentation in [data/metadata.db](file:///d:/UIT/TX/doan/data/metadata.db) via [src/indexers/metadata_db.py](file:///d:/UIT/TX/doan/src/indexers/metadata_db.py) without re-running EasyOCR:
1. **Problem Fixed:** Storing each bounding box as a separate row in `ocr_fts` splits multi-line signage (e.g. Line 1: `"CONG TY TNHH"`, Line 2: `"DONG A"`) across isolated documents, degrading BM25 and fuzzy phrase alignment when searching `"CONG TY DONG A"`.
2. **In-Place SQL Aggregation (`rebuild_ocr_fts_by_keyframe()`):**
   * Keep `ocr_records` intact at the bounding-box level (568,562 rows) for UI bounding-box inspection.
   * Rebuild `ocr_fts` so each row corresponds to **one unique `keyframe_id`**, concatenating all detected text boxes on that keyframe separated by spaces (`GROUP_CONCAT(text_detected, ' ')`).
   * Execution time on existing [data/metadata.db](file:///d:/UIT/TX/doan/data/metadata.db) is `< 3 seconds`.
3. **Starvation-Resistant Hybrid OCR Search (`search_ocr()`):**
   * Increase Stage 1 FTS5 Soft OR candidate pool from `300` to `pool_limit = max(limit * 10, 500)` so frames matching rare or slightly misspelled tokens are not pushed out by high-frequency broadcast words (e.g. `"TP HCM"`, `"2024"`).

---

### Step 2.1: Query Input Modalities, Language Convention & Multi-Cue Parser
The parser in [src/retrieval/query_parser.py](file:///d:/UIT/TX/doan/src/retrieval/query_parser.py) supports three entry mechanisms and chronological sequencing:

* **Language Input Convention:**
  * **Visual Cues (`v:`):** Entered directly in **English** by the contestant to maximize zero-shot embedding alignment with `google/siglip2-base-patch16-256` without online translation overhead.
  * **OCR Text Cues (`ocr:`):** Entered in **Vietnamese (with or without diacritics) or Latin/Alphanumeric** matching on-screen banners, license plates, and signage.

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
     "sequence_stages": [
       {
         "visual_queries": ["woman entering supermarket"],
         "ocr_queries": []
       },
       {
         "visual_queries": ["close up of red paper at cashier"],
         "ocr_queries": ["HOA DON"]
       }
     ],
     "weights": {
       "visual": 1.0,
       "ocr": 1.5
     }
   }
   ```
2. **Power-User Prefix & Sequence Syntax (CLI & Single Search Bar):**
   * **Co-occurring Multi-Cue Syntax (`|` separator):**
     `v: a blue truck | v: heavy rain | ocr: 51C 456.78`
   * **Google-Style Inline Quoted Syntax:**
     `a blue truck in heavy rain ocr:"51C 456.78"`
   * **Chronological Sequence Syntax (`>>` operator):**
     `v: woman entering supermarket >> v: close up of cashier | ocr: HOA DON`
     Splits query into ordered temporal stages (`Stage 1` followed by `Stage 2` within `15.0s`).
3. **Pure Natural Language Fallback (Automatic Routing < 1ms):**
   * If no explicit prefixes are provided, the rule-based router scans for quoted tokens (`"..."`) or license plate / numeric sign patterns (`^[0-9]{2}[A-Z]-[0-9]{4,5}$`), dispatches extracted text to OCR FTS5, and routes the query to SigLIP2 visual search.

---

### Step 2.2: Deep Candidate Retrieval & Max-Per-Cue Reciprocal Rank Fusion (Multi-Cue RRF)
In [src/retrieval/score_fusion.py](file:///d:/UIT/TX/doan/src/retrieval/score_fusion.py):

1. **Deep Per-Cue Candidate Retrieval:**
   * For each Visual Cue `i` (`i = 1..M`), retrieve `top_k_visual = 1500` keyframes from [data/indices/visual_siglip2.index](file:///d:/UIT/TX/doan/data/indices/visual_siglip2.index). Retrieving 1500 vectors from 243,732 entries in FAISS `IndexFlatIP` takes `< 5ms` and prevents broad visual cues from losing true positives before fusion.
   * For each OCR Cue `j` (`j = 1..N`), retrieve `top_k_ocr = 500` keyframe hits from [src/indexers/metadata_db.py](file:///d:/UIT/TX/doan/src/indexers/metadata_db.py).
2. **Pointwise RRF Conversion:**
   * Convert each candidate hit's rank `r` (`1 <= r <= top_k`) under cue `c` into a scale-invariant RRF score:
     ```text
     RRF(hit, c) = W_c / (k_rrf + r)
     ```
   * Default parameters: `k_rrf = 60`, `W_visual = 1.0`, `W_ocr = 1.5`.

---

### Step 2.3: Max-Per-Cue Sliding Window Aggregation (No Double-Counting) & Temporal Sequence Alignment
1. **Time Grid Discretization:**
   * Construct 5.0-second sliding windows `W = [t_start, t_end]` with 2.5-second stride (50% overlap) across active videos:
     `[0.0 - 5.0s]`, `[2.5 - 7.5s]`, `[5.0 - 10.0s]`, `[7.5 - 12.5s]`, ...
2. **Max-Per-Cue Score Accumulation (Eliminating Double-Counting Bias):**
   * **Rule:** Multiple keyframes belonging to the same window `W` that match the **same cue `c`** must **NOT** be summed together (which would artificially inflate static shots with 3 similar keyframes matching only 1 cue).
   * Instead, within window `W`, take the **MAXIMUM** RRF score per individual cue, and **SUM** across distinct cues:
     ```text
     Window_Raw_Score(W) = Sum_{i=1..M} [ Max_{kf in W} RRF(kf, V_i) ]
                         + Sum_{j=1..N} [ Max_{kf in W} RRF(kf, OCR_j) ]
     ```
3. **Multi-Cue Consensus Boost:**
   * Let `K_matched(W)` be the number of distinct cues (`0 <= K_matched(W) <= M + N`) that have at least one hit inside window `W`.
   * Apply a coverage multiplier when `M + N > 1`:
     ```text
     Window_Score(W) = Window_Raw_Score(W) * (1.0 + 0.25 * (K_matched(W) - 1))
     ```
   * This mathematically guarantees that a window matching **2 or 3 distinct cues** decisively outranks a window matching only **1 cue** even at Rank #1.
4. **Chronological Sequence Alignment (`Stage 1 >> Stage 2`):**
   * When a query contains ordered stages (`Stage 1 >> Stage 2`), evaluate `Window_Score_1(W_a)` for Stage 1 and `Window_Score_2(W_b)` for Stage 2 within the same `video_id`.
   * For every pair `(W_a, W_b)` satisfying `0.0 <= t_start(W_b) - t_start(W_a) <= max_sequence_gap_sec` (default `15.0s`):
     ```text
     Sequence_Score(W_a, W_b) = Window_Score_1(W_a) + Window_Score_2(W_b) + sequence_bonus
     ```
   * Expand the candidate moment interval to cover the full narrative transition: `[t_start(W_a), t_end(W_b)]`.
5. **Temporal Non-Maximum Suppression (NMS):**
   * Sort candidate windows by final score in descending order.
   * Greedily select top window `[start, end]`, merge adjacent/overlapping high-scoring windows into `[start_min, end_max]`, and suppress remaining overlapping candidates with temporal Intersection over Union (`IoU >= 0.4`).
   * Return Top 25 ranked video moments with millisecond boundaries: `{ video_id, start_sec, end_sec, start_ms, end_ms, score, matched_cues }`.

---

### Step 2.4: Human-in-the-Loop Multi-Cue Query Builder in Web UI
In [src/ui/static/index.html](file:///d:/UIT/TX/doan/src/ui/static/index.html) and [src/ui/static/app.js](file:///d:/UIT/TX/doan/src/ui/static/app.js):
* Provide an interactive **Multi-Cue Query Builder**:
  * `[+ Add Visual Cue (EN)]`: Inserts an English visual attribute row (e.g. `"a blue truck"`).
  * `[+ Add OCR Text (VI/EN)]`: Inserts an on-screen text filter row (e.g. `"51C 456.78"`).
  * `[+ Add Next Scene (>>)]`: Appends a chronological follow-up stage for sequential KIS descriptions.
* Synchronizes two-way with the single power-user search bar (`v: ... | ocr: ... >> v: ...`).

---

## 3. Architecture & Data Flow

```text
[User Multi-Cue / Sequential Query]
  ├─► Stage 1 Visual Cue 1 (EN): "a blue truck"
  ├─► Stage 1 Visual Cue 2 (EN): "heavy rain"
  ├─► Stage 1 OCR Cue (VI/EN):   "51C 456.78"
  └─► Stage 2 (Optional >>):     "driver stepping out"
           │
           ▼
[src/retrieval/query_parser.py] (Rule-Based Decomposition < 1ms)
           │
           ├─► SigLIP2 Encode(Cue 1) ──► FAISS Search (Top 1500) ──► Ranked List R_v1
           ├─► SigLIP2 Encode(Cue 2) ──► FAISS Search (Top 1500) ──► Ranked List R_v2
           └─► Keyframe-Grouped FTS5 + Fuzzy("51C 456.78", Top 500) ► Ranked List R_ocr
                                   │
                                   ▼
[src/retrieval/score_fusion.py]
  1. Max-Per-Cue Window Score (5s window, 2.5s stride):
     Sum_{c} [ Max_{kf in W} RRF(kf, c) ] * Consensus_Multiplier
  2. Sequential Stage Linker (>> within 15s horizon)
  3. Temporal NMS (IoU >= 0.4) -> Merged [start_ms, end_ms]
                                   │
                                   ▼
[Top Ranked Video Moments] ──► Web UI Inspector & 1-Click DRES Submission
```

---

## 4. Verification & Acceptance Criteria
1. **Keyframe-Level OCR FTS5 Aggregation Test:**
   * Verify `ocr_fts` groups multi-box text by `keyframe_id` so multi-line banners match multi-word queries in `< 15ms`.
2. **Multi-Cue & Sequence Decomposition Test:**
   * Input: `v: blue truck | ocr: 51C 456.78 >> v: man in yellow raincoat`.
   * Verify parser extracts Stage 1 (1 visual cue + 1 OCR cue) and Stage 2 (1 visual cue).
3. **Anti-Double-Counting & Consensus Test:**
   * Verify a window with 3 keyframes matching only `Cue 1` scores strictly lower than a window with 1 keyframe matching `Cue 1` and 1 keyframe matching `Cue 2`.
4. **End-to-End Latency Benchmark:**
   * Multi-cue retrieval latency (`top_k_visual=1500`, 2 visual cues + 1 OCR cue across 726 videos) must complete in **< 150ms** on local machine.
5. **Ablation Matrix:**
   * Validate via [src/evaluation/evaluate.py](file:///d:/UIT/TX/doan/src/evaluation/evaluate.py): Pure Visual vs Pure OCR vs Multi-Cue Hybrid Fusion.
