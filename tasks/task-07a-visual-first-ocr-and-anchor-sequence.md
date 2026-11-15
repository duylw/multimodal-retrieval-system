# Task 07A: Visual-First OCR Fusion & Anchor-then-Scan Sequential Retrieval

**Status:** `[DONE]` Completed
**Target Milestone:** Milestone 5 (Competition Retrieval & Cockpit Optimization)
**Core Modules:** [src/indexers/metadata_db.py](file:///d:/UIT/TX/doan/src/indexers/metadata_db.py), [src/retrieval/query_parser.py](file:///d:/UIT/TX/doan/src/retrieval/query_parser.py), [src/retrieval/score_fusion.py](file:///d:/UIT/TX/doan/src/retrieval/score_fusion.py), [src/retrieval/search_engine.py](file:///d:/UIT/TX/doan/src/retrieval/search_engine.py)
**API & Frontend:** [src/ui/competition_server.py](file:///d:/UIT/TX/doan/src/ui/competition_server.py), [src/ui/competition/](file:///d:/UIT/TX/doan/src/ui/competition)
**Unit Tests:** [tests/test_retrieval.py](file:///d:/UIT/TX/doan/tests/test_retrieval.py)

---

## 1. Problem Statement & Objectives (What)
Real-world Known-Item Search (KIS) testing on the 726-video / 243,732-keyframe repository revealed two retrieval bottlenecks in the current [src/retrieval/search_engine.py](file:///d:/UIT/TX/doan/src/retrieval/search_engine.py) and [src/retrieval/score_fusion.py](file:///d:/UIT/TX/doan/src/retrieval/score_fusion.py) pipeline:

1. **Hybrid + OCR Degrades Visual Ranking:**
   * Vietnamese EasyOCR output in [data/metadata.db](file:///d:/UIT/TX/doan/data/metadata.db) frequently contains diacritic noise (e.g., `KỂ HOACH`, `nhân dip`, `dông bào`). Standalone `MetadataDB.search_ocr()` already handles this well via `unicode61 remove_diacritics 2`, `expand_ocr_terms()`, Soft OR pooling, and Stage 2 `SequenceMatcher` fuzzy rescoring — so standalone OCR search must be **preserved intact**.
   * However, in Hybrid fusion:
     * Implicit `OCR_TRIGGER_KEYWORDS` in [src/retrieval/query_parser.py](file:///d:/UIT/TX/doan/src/retrieval/query_parser.py) accidentally trigger OCR extraction on purely descriptive Vietnamese visual queries.
     * Rank-based RRF (`ocr` weight `1.5` vs `visual` weight `1.0`) in [src/retrieval/score_fusion.py](file:///d:/UIT/TX/doan/src/retrieval/score_fusion.py) discards the Stage 2 `fuzzy_score` computed by `search_ocr()`, allowing low-confidence Soft-OR OCR matches to override top SigLIP2 visual hits.
2. **Sequential Stage (`>>`) Starvation & Misalignment:**
   * Retrieving independent global Top-1500 pools per stage drops second-stage hits ranked outside the global Top-1500 before linking can occur.
   * Fallback preservation of unlinked single-stage windows pollutes sequential results, while `0.0 <= delta <= 15.0s` allows same-window (`delta = 0`) collisions and misses events separated by 20s-60s.

### Objectives
* Implement **Visual-First OCR Integration** with diacritic-folded text matching and two explicit user-controlled roles: `boost` (soft additive bonus on Visual ranking) and `filter` (OCR hard video shortlist followed by Visual scoring inside matching videos).
* Replace global Top-K intersection in sequential search with **Two-Phase Anchor-then-Scan Sequential Linking** using in-memory FAISS vector reconstruction (`index.reconstruct`) across the target temporal neighborhood `[t_anchor + min_gap, t_anchor + max_gap]`.
* Eliminate silent heuristic OCR triggering in Hybrid mode unless explicitly entered in the dedicated OCR input or explicit `ocr:` prefix.
* Expose **Multi-Stage Query Builder** rows (`+ Add Scene`, `Anchor` selector, `Gap` range selector) and separate `Visual` / `OCR` (`Boost | Filter`) inputs on the Competition Workstation UI.

---

## 2. Technical Specifications & Implementation Steps (How)

### Step 2.1: Preserve Standalone OCR & Apply Two Surgical Polishes
In [src/indexers/metadata_db.py](file:///d:/UIT/TX/doan/src/indexers/metadata_db.py):
1. Preserve the proven Two-Stage `search_ocr()` algorithm (`unicode61 remove_diacritics 2`, `expand_ocr_terms()`, `fold_vietnamese()`, Soft OR FTS5 pool, Stage 2 token alignment + substring bonus + `0.35 * BM25 + 0.65 * fuzzy`) and standalone `OCR` mode completely intact.
2. Apply two minimal, non-breaking precision polishes:
   * Deduplicate the `LIKE` fallback loop by `keyframe_id` (`seen_kf_ids`) instead of `ocr_id` so bounding-box rows in `ocr_records` cannot duplicate keyframe-aggregated `ocr_fts` hits.
   * Strip non-alphanumeric punctuation when building `spaceless_query` and `spaceless_text` (`"".join(query_words)` / `"".join(cand_words)`) so hyphenated/dotted codes like `51B-501.62` match `51B 50162`.

### Step 2.2: Explicit Query Structuring & Disabling Noisy Heuristic Hijack
In [src/retrieval/query_parser.py](file:///d:/UIT/TX/doan/src/retrieval/query_parser.py):
1. Extend structured query payload (`Dict[str, Any]`) and [src/common/types.py](file:///d:/UIT/TX/doan/src/common/types.py) dataclasses to carry:
   * `ocr_mode`: `"off"` | `"boost"` | `"filter"`
   * `ocr_weight`: float (default `0.25` in `boost` mode)
   * `sequence_config`: `{ "anchor_stage": int, "min_gap_sec": float, "max_gap_sec": float }`
2. Stop `_parse_natural_language()` from auto-generating noisy OCR cues on generic words (`bang`, `tieu de`, `chu`) unless explicit quotes, `ocr:` syntax, or license-plate regex matches are present (or disable implicit extraction when `ocr_mode == "off"`).

### Step 2.3: Visual-First + OCR Boost / Hard Filter Engine
In [src/retrieval/search_engine.py](file:///d:/UIT/TX/doan/src/retrieval/search_engine.py) and [src/retrieval/score_fusion.py](file:///d:/UIT/TX/doan/src/retrieval/score_fusion.py):
1. **OCR `boost` Mode (Visual-Primary):**
   * Run Visual SigLIP2 retrieval first to form the candidate windows.
   * Query OCR hits matching the `ocr` term; any visual window containing or adjacent (`+-5.0s`) to a matching OCR hit receives a bounded multiplicative boost (`score * (1.0 + ocr_boost * norm_ocr_conf)`), preventing ungrounded OCR noise from outranking true visual scenes.
2. **OCR `filter` Mode (Must Contain):**
   * Query matching `video_id` set (and keyframe timestamps) via OCR FTS5/fuzzy matching first.
   * If `matched_videos` is non-empty, restrict Visual SigLIP2 scoring directly to keyframes inside `matched_videos` using `_vid_to_int_ids` + `index.reconstruct()`, guaranteeing zero global Top-K starvation.

### Step 2.4: Two-Phase Anchor-then-Scan Sequential Linking
In [src/retrieval/search_engine.py](file:///d:/UIT/TX/doan/src/retrieval/search_engine.py) and [src/retrieval/score_fusion.py](file:///d:/UIT/TX/doan/src/retrieval/score_fusion.py):
1. **Phase 1 (Anchor Candidate Selection):**
   * Encode all stage cues (`stage_0`, `stage_1`, ...).
   * Execute global FAISS retrieval for the designated `anchor_stage` (default `0`, selectable to `1` if Stage 2 is visually more distinctive) to select the Top-N candidate anchor hits (e.g., top 200 distinct temporal windows across videos).
2. **Phase 2 (Local Neighborhood Scoring via FAISS Reconstruction):**
   * For each anchor hit `(video_id, t_anchor)`:
     * If linking forward (`Stage 0 -> Stage 1`), collect all indexed keyframes of `video_id` in `[t_anchor + min_gap_sec, t_anchor + max_gap_sec]` (requiring `min_gap_sec >= 1.0` by default to prevent same-window collisions).
     * If `anchor_stage == 1` (linking backward `Stage 1 -> Stage 0`), scan `[t_anchor - max_gap_sec, t_anchor - min_gap_sec]`.
   * Reconstruct the neighborhood keyframe vectors directly from FAISS (`index.reconstruct(f_id)`), compute exact Cosine dot product against the non-anchor stage text embedding, and pick the best matching transition frame `t_next`.
   * **Strict Sequence Rule:** Discard anchor hits that have no valid partner above minimal visual similarity inside `[min_gap_sec, max_gap_sec]` (no fallback single-stage pollution).
   * Attach both `stage_hits` evidence objects (thumbnails, timestamps, scores) to `CandidateMoment.cue_evidence` for dual-thumbnail card rendering.

### Step 2.5: API & Multi-Stage Query Builder UI
In [src/ui/competition_server.py](file:///d:/UIT/TX/doan/src/ui/competition_server.py) and [src/ui/competition/](file:///d:/UIT/TX/doan/src/ui/competition):
1. Accept structured fields (`ocr_text`, `ocr_mode`, `scenes[]`, `anchor_stage`, `min_gap_sec`, `max_gap_sec`) in `POST /api/search/multimodal` while preserving backward compatibility with string `q`.
2. Split the top search bar into:
   * Primary **Visual Description** input.
   * Secondary **OCR Text** input with `[Boost | Filter]` toggle pill.
   * **`+ Add Scene`** toggle opening **Scene 2** input with `Anchor` radio button and `Gap (2-15s | 2-45s | 5-120s)` selector.
3. Update `/api/translate` to translate each visual scene stage independently while keeping `ocr_text` untranslated.

---

## 3. Architecture Flow

```text
[User Inputs: Scene 1 (Visual) + Optional Scene 2 + Optional OCR + Mode]
         │
         ├──► Single-Stage + OCR=Boost:
         │      Visual Top-K (FAISS) ──► Add bounded OCR bonus (+-5s) ──► NMS
         │
         ├──► Single-Stage + OCR=Filter:
         │      OCR Video Shortlist (SQLite FTS5) ──► Rescore all KFs in shortlist (FAISS reconstruct) ──► NMS
         │
         └──► Multi-Stage Sequence (Anchor-then-Scan):
                Phase 1: Anchor Stage FAISS Search (Top 200 anchors)
                Phase 2: Reconstruct neighbor vectors in [t_anchor + min_gap, t_anchor + max_gap]
                         ──► Exact Cosine match with Partner Stage ──► Ranked Stage Pairs
```

---

## 4. Verification & Acceptance Criteria
* **Unit Tests ([tests/test_retrieval.py](file:///d:/UIT/TX/doan/tests/test_retrieval.py)):**
  * Anchor-then-Scan retrieves a valid `Stage 1 >> Stage 2` pair even when `Stage 2` falls outside global Top-1500, and rejects same-window (`delta < min_gap_sec`) self-matches.
  * OCR `boost` preserves pure visual winners when no OCR matches and promotes matching visual+OCR windows without promoting unrelated visual false positives.
  * OCR `filter` isolates search strictly to OCR-matched videos without Top-K cutoff starvation.
* **Latency Budget:**
  * Two-phase neighborhood reconstruction across 200 anchor windows completes in `< 60ms` on CPU RAM (0MB extra GPU VRAM).
