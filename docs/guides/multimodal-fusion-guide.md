# User Guide: Temporal Multimodal Fusion, Query Routing & Multi-Cue Composition

## 1. Feature Overview
* **What it does:** Provides a unified search engine that parses natural language and multi-cue queries, decomposes them into modality-specific channels (English Visual SigLIP2 and Vietnamese/Latin EasyOCR text), and fuses them using **Max-Per-Cue Reciprocal Rank Fusion (RRF)** inside **5.0-second sliding windows** (2.5s stride). Automatically handles chronological transitions via the sequence operator (`>>`) and temporal Non-Maximum Suppression (NMS) to generate DRES-compliant candidate moments `[start_ms, end_ms]`.
* **When to use:** Phase 2 (Online Retrieval Phase), executed whenever answering Known-Item Search (KIS) queries (both Textual KIS and Video KIS).
* **Value provided:**
  * **Human-in-the-Loop Multi-Cue Composition:** Prevents semantic dilution by allowing contestants to decouple complex scene queries into distinct visual and OCR cues (`v: a blue truck | v: heavy rain | ocr: 51C 456.78`).
  * **Max-Per-Cue Anti-Double-Counting:** Prevents static scenes with multiple identical keyframes from falsely outranking true multi-attribute moments.
  * **Consensus Multiplier:** Automatically boosts moments co-satisfying multiple independent visual and OCR attributes directly to Rank #1.
  * **Chronological Sequence Alignment:** Supports ordered narrative stages (`Stage 1 >> Stage 2`) linked within a 15-second horizon.
  * **Keyframe-Aggregated OCR FTS5:** Evaluates multi-line banners and signboards holistically with deep candidate pools (`pool_limit >= 500`).
  * **High Throughput & Low Latency:** Multi-cue retrieval completes across 243,732 keyframes in **< 150 ms** on local hardware.

---

## 2. Quick Start CLI

### Step 1: Run Multi-Cue Search via Command Line
```powershell
# Auto mode with multi-cue prefix syntax (combining visual and OCR cues)
uv run python -m src.retrieval.search_engine --query "v: news anchor in studio | ocr: thoi su" --top-k 10

# Sequential search with chronological transition (Stage 1 >> Stage 2)
uv run python -m src.retrieval.search_engine --query "v: woman entering supermarket >> v: cashier desk | ocr: HOA DON" --top-k 5

# Pure OCR search (super-fast lexical + fuzzy lookup in < 15ms)
uv run python -m src.retrieval.search_engine --query "ocr: trùng biển số" --mode ocr --top-k 5

# Pure Visual search (SigLIP2 FAISS index only)
uv run python -m src.retrieval.search_engine --query "firefighter spraying water" --mode visual --top-k 5
```

### Python API Usage:
```python
from src.retrieval.search_engine import SearchEngine

# 1. Initialize search engine
engine = SearchEngine()

try:
    # 2. Execute multi-cue search
    moments = engine.search(
        query="v: a blue truck | v: heavy rain | ocr: 51C 456.78",
        mode="auto",
        top_k=10
    )

    # 3. Inspect results
    for rank, m in enumerate(moments, start=1):
        print(f"Rank #{rank}: {m.video_id} [{m.start_sec}s - {m.end_sec}s] ({m.start_ms}ms - {m.end_ms}ms) | Score: {m.score:.4f}")
        print(f"  Matched Cues: {m.matched_cues} | Keyframe: {m.keyframe_id}")
finally:
    # 4. Mandatory GPU memory release
    engine.safe_unload()
```

---

## 3. CLI Arguments Table

| Argument | Type | Default Value | Description |
|---|---|---|---|
| `--query`, `-q` | `str` | *Required* | Query string, multi-cue prefix string (`v:`, `ocr:`), or sequence (`>>`). |
| `--mode` | `str` | `"auto"` | Retrieval mode: `"auto"` (hybrid fusion), `"visual"` (SigLIP2 only), or `"ocr"` (FTS5 only). |
| `--top-k` | `int` | `10` | Maximum number of ranked candidate moments to retrieve. |
| `--video-id` | `str` | `None` | Optional video ID filter to restrict search to a single video. |

---

## 4. Query Syntax & Language Conventions

The parser in [src/retrieval/query_parser.py](file:///d:/UIT/TX/doan/src/retrieval/query_parser.py) enforces language conventions to maximize embedding alignment:

| Query Type | Syntax Example | Modality Destination | Language Requirement |
|---|---|---|---|
| **Multi-Cue Co-occurrence** | `v: red sports car \| v: police officer \| ocr: 51A 12345` | Fused across both channels | Visual in English; OCR in Vietnamese/Latin |
| **Chronological Sequence** | `v: police car arrives >> v: officer steps out` | Linked within 15s horizon | English visual descriptions |
| **Inline Quoted OCR** | `red sports car at intersection ocr:"51A 12345"` | Split into Visual and OCR | Visual in English; quoted text in Vietnamese/Latin |
| **Natural Language Fallback** | `xe cuu thuong bien so 51B-123.45 vuot den do` | Rule-based regex triage | Vietnamese or English natural language |

---

## 5. Inputs & Outputs

* **Inputs:**
  * FAISS Visual Index: [data/indices/visual_siglip2.index](file:///d:/UIT/TX/doan/data/indices/visual_siglip2.index) (768-dim embeddings across 243,732 keyframes).
  * SQLite Metadata & Keyframe FTS5: [data/metadata.db](file:///d:/UIT/TX/doan/data/metadata.db) (`ocr_fts` aggregated by `keyframe_id`).
  * Model Weights: [models/](file:///d:/UIT/TX/doan/models) (`google/siglip2-base-patch16-256`).
* **Outputs:**
  * Candidate Moments: List of `CandidateMoment` objects in [src/common/types.py](file:///d:/UIT/TX/doan/src/common/types.py).
  * Millisecond Boundaries: `{ video_id, start_sec, end_sec, start_ms, end_ms, score, matched_cues }` formatted for DRES KIS submission via [src/submission/dres_client.py](file:///d:/UIT/TX/doan/src/submission/dres_client.py).

---

## 6. Architecture & Data Flow

```text
[User Query: v: blue truck | v: heavy rain | ocr: 51C 456.78]
                                │
                                ▼
[src/retrieval/query_parser.py] (Rule-Based Decomposition < 1ms)
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
SigLIP2("blue truck")   SigLIP2("heavy rain")   FTS5+Fuzzy("51C 456.78")
FAISS (Top 1500)        FAISS (Top 1500)        SQLite (Top 500)
        │                       │                       │
        └───────────────────────┼───────────────────────┘
                                ▼
[src/retrieval/score_fusion.py]
  1. Max-Per-Cue Sliding Window (5s window, 2.5s stride):
     Window_Raw_Score(W) = Sum_{c} [ Max_{kf in W} RRF(kf, c) ]
  2. Multi-Cue Consensus Multiplier:
     Window_Score(W) = Window_Raw_Score(W) * (1.0 + 0.25 * (K_matched - 1))
  3. Temporal NMS (IoU >= 0.3) -> Unified [start_ms, end_ms]
                                │
                                ▼
[Candidate Moments List] ──► Web UI & DRES Submission
```

---

## 7. Hardware Constraints & Troubleshooting

| Error / Symptom | Root Cause | Resolution |
|---|---|---|
| `FileNotFoundError: Visual FAISS index not found` | Stage 3 index build has not been executed. | Run `uv run python -m src.indexers.build_indices --modality visual` to generate index. |
| `CUDA Out of Memory on GTX 1650` | GPU VRAM leaked or another model is running. | Call `engine.safe_unload()` or hit `POST /api/search/unload` to release VRAM. |
| `Slow first query latency (~15s)` | Cold start loading SigLIP2 model weights from disk into GPU. | Expected behavior on initial invocation; subsequent queries execute in `< 150ms`. |
| `Zero OCR matches on accented query` | Accented characters mistyped. | The hybrid OCR engine applies diacritic folding (`remove_diacritics 2` and `đ -> d`), so unaccented keywords match uniformly. |
