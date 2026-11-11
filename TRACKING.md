# TRACKING.md - Project Execution & Milestone Tracking

> **Project:** Natural Language Multimodal Video Moment Retrieval System  
> **Institution:** University of Information Technology (UIT)  
> **Target Environment:** NVIDIA GeForce GTX 1650 (4GB VRAM), 16GB RAM, ~150GB Free Disk (D:).  
> **Last Updated:** October 26, 2026

---

## 1. Overall Status

* **Current Stage:** **Milestone 4: Web Application Delivery & Thesis Defense (Completed)**
* **Overall Progress:** `100%`
* **Current Focus:** Completed Task 06B (KIS Interactive Scrubber, Competition Accelerators & DRES Live Submission Console). Implemented 1-Click Quick Submit @ Playhead (`+-0.5s`, hotkey `S`), Temporal Context Filmstrip Drawer (`+-15s` neighbor keyframes), Negative Visual Cue Filtering (`-v:`), Story-Level Video Coverage Boost, N-stage sequential linking (`N >= 2`), single-video search starvation fix, and live DRES API v2 submission with duplicate suppression.

---

## 2. Task Board

| Task ID | Task Title | Primary Focus | Status | Documentation | Deliverables |
|---|---|---|---|---|---|
| **Task 00** | Environment Setup & Eval Harness | uv virtualenv, CUDA 12.1, `ground_truth.json`, Recall@K/MRR script | **Completed** | [task-00](file:///d:/UIT/TX/doan/tasks/task-00-environment-and-eval.md) | `pyproject.toml`, `evaluate.py`, `ground_truth.json` |
| **Task 01** | Shot Detection & Keyframe Extraction | SceneDetect / TransNetV2, Laplacian blur filter, color deduplication | **Completed** | [task-01](file:///d:/UIT/TX/doan/tasks/task-01-shot-detection-keyframes.md) | `shots.py`, `keyframes.py`, SQLite `shots` table |
| **Task 01B** | Shot & Keyframe Debug Inspector | FastAPI + Range 206, video timeline sync, two-way shot & keyframe inspection | **Completed** | [task-01b](file:///d:/UIT/TX/doan/tasks/task-01b-debug-ui-shots-keyframes.md) | `debug_server.py`, SPA debug interface |
| **Task 02** | Visual SigLIP2 & FAISS | SigLIP2 embeddings, pure keyframe representation, FAISS indexing | **Completed** | [task-02](file:///d:/UIT/TX/doan/tasks/task-02-visual-siglip-faiss.md) | `visual.py`, `visual_siglip2.index` |
| **Task 02B** | Fault Tolerance & Modular Refactoring | Checkpointing DB table, engine-runner separation, decoupled index builder | **Completed** | [task-02b](file:///d:/UIT/TX/doan/tasks/task-02b-fault-tolerance-and-modular-refactoring.md) | `pipeline_checkpoints`, `run_*.py`, `build_indices.py` |
| **Task 02C** | Visual DataLoader & SigLIP2-Base | Switch to SigLIP2-Base, PyTorch DataLoader num_workers=2, models/ D: drive centralization | **Completed** | [task-02c](file:///d:/UIT/TX/doan/tasks/task-02c-visual-performance-dataloader.md) | SigLIP2-Base DataLoader pipeline, `models/`, benchmark report |
| **Task 04** | On-screen Text EasyOCR | Text keyframe detector, EasyOCR on CPU, SQLite FTS5 | **Completed** | [task-04](file:///d:/UIT/TX/doan/tasks/task-04-ocr-easyocr.md) | `ocr.py`, `run_ocr.py`, SQLite `ocr_fts` virtual table, `ocr-easyocr-guide.md` |
| **Task 05** | Multimodal Fusion & Query Routing | Keyframe-grouped OCR FTS5, Deep Top-K (1500), Max-Per-Cue RRF, 5s window, Sequence (`>>`), NMS | **Completed** | [task-05](file:///d:/UIT/TX/doan/tasks/task-05-temporal-fusion.md) | `score_fusion.py`, `query_parser.py`, `search_engine.py`, `multimodal-fusion-guide.md` |
| **Task 06** | Web Interface & Relevance Feedback | Explainable pipeline trace, per-cue hits breakdown, multi-cue builder, HTTP 206 video seeking, Rocchio feedback | **Completed** | [task-06](file:///d:/UIT/TX/doan/tasks/task-06-ui-and-feedback.md) | `search_engine.py`, `debug_server.py`, `src/ui/static/`, `multimodal-search-ui-guide.md` |
| **Task 06B** | KIS Scrubber & DRES Live Submission | 1-click playhead submit (`+-0.5s`), Filmstrip (`+-15s`), `-v:` negative cues, story boost, DRES submit | **Completed** | [task-06b](file:///d:/UIT/TX/doan/tasks/task-06b-kis-interactive-submission.md) | `debug_server.py`, `app.js`, `index.html`, `style.css`, `kis-interactive-submission-guide.md` |

---

## 3. Major Milestones

* [x] **Milestone 0: Architecture Formulation & Project Governance** (Completed Oct 15, 2026)
  * Operating rules and hardware constraints defined in [AGENTS.md](file:///d:/UIT/TX/doan/AGENTS.md).
  * System architecture and multimodal blueprint documented in [PROJECT_OVERVIEW.md](file:///d:/UIT/TX/doan/PROJECT_OVERVIEW.md).
  * Detailed task breakdowns and test criteria created in [tasks/](file:///d:/UIT/TX/doan/tasks).
* [x] **Milestone 1: Baseline Minimum (End-to-End Visual Retrieval)**
  * Environment setup and evaluation benchmark ready on GTX 1650.
  * [x] Shot boundary detection, adaptive keyframe extraction, and SQLite cataloging ([Task 01](file:///d:/UIT/TX/doan/tasks/task-01-shot-detection-keyframes.md)).
  * [x] Interactive debug inspector with HTTP 206 Range streaming and shot timeline synchronization ([Task 01B](file:///d:/UIT/TX/doan/tasks/task-01b-debug-ui-shots-keyframes.md)).
  * [x] Visual embeddings with SigLIP2 and initial `Recall@10` measurement on ground truth benchmark ([Task 02](file:///d:/UIT/TX/doan/tasks/task-02-visual-siglip-faiss.md)).
* [x] **Milestone 2: On-Screen Text Channel Integration (EasyOCR + SQLite FTS5)**
  * [x] On-screen text extraction with EasyOCR running purely on CPU (0MB GPU VRAM).
  * [x] Morphological edge-density pre-filter (~9ms/frame) pruning non-text frames.
  * [x] SQLite FTS5 full-text search index (`ocr_fts`) with `unicode61 remove_diacritics 2` for accent-insensitive search.
* [x] **Milestone 3: Temporal Multimodal Fusion & Query Routing** (Completed Nov 08, 2026)
  * [x] Keyframe-aggregated SQLite FTS5 migration (187,518 keyframes) and deep Top-K candidate pooling.
  * [x] Multi-cue and chronological sequence query parser (`v:`, `ocr:`, `>>`, inline quotes, structured dict).
  * [x] Max-Per-Cue Reciprocal Rank Fusion (RRF), consensus multipliers, and temporal Non-Maximum Suppression (NMS).
  * [x] Unified multimodal search orchestrator with lazy-loading and CLI runner.
  * [x] FastAPI REST endpoints (`/api/search/multimodal`) with VRAM unload lifecycle.
  * [x] Practical feature guide in [multimodal-fusion-guide.md](file:///d:/UIT/TX/doan/docs/guides/multimodal-fusion-guide.md).
* [x] **Milestone 4: Web Application Delivery & Thesis Defense** (Completed Nov 08, 2026)
  * [x] Multimodal Search UI with Explainable Pipeline Inspector, Multi-Cue Builder, and Rocchio feedback ([Task 06](file:///d:/UIT/TX/doan/tasks/task-06-ui-and-feedback.md)).
  * [x] KIS Interactive Scrubber, 1-Click Playhead Submit (`+-0.5s`), Temporal Filmstrip (`+-15s`), Negative Visual Cues (`-v:`), and live DRES submission console ([Task 06B](file:///d:/UIT/TX/doan/tasks/task-06b-kis-interactive-submission.md)).
  * [x] Clean packaged codebase and thesis demonstration materials.

---

## 4. Activity Log

* **Oct 15, 2026:**
  * Initial architectural review and technical bottleneck identification (GTX 1650 4GB VRAM limit, scale disparity between Cosine and BM25 scores, temporal fragmentation).
  * Standardized governance setup: [AGENTS.md](file:///d:/UIT/TX/doan/AGENTS.md), [PROJECT_OVERVIEW.md](file:///d:/UIT/TX/doan/PROJECT_OVERVIEW.md), [TRACKING.md](file:///d:/UIT/TX/doan/TRACKING.md).
  * Authored technical task specifications from [task-00](file:///d:/UIT/TX/doan/tasks/task-00-environment-and-eval.md) through [task-07](file:///d:/UIT/TX/doan/tasks/task-07-audio-clap.md).
  * Added [docs/GLOSSARY.md](file:///d:/UIT/TX/doan/docs/GLOSSARY.md) and [docs/GIT_GUIDELINES.md](file:///d:/UIT/TX/doan/docs/GIT_GUIDELINES.md).
  * Initialized 3 workspace skills (`video-benchmark-eval`, `vram-safe-embedding`, `temporal-multimodal-fusion`).
  * Completed [Task 00](file:///d:/UIT/TX/doan/tasks/task-00-environment-and-eval.md): Virtualenv via `uv`, PyTorch 2.5.1 CUDA 12.1, 20-query [ground_truth.json](file:///d:/UIT/TX/doan/data/ground_truth.json), and benchmark harness [evaluate.py](file:///d:/UIT/TX/doan/src/evaluation/evaluate.py).
  * Completed [Task 01](file:///d:/UIT/TX/doan/tasks/task-01-shot-detection-keyframes.md): Implemented [metadata_db.py](file:///d:/UIT/TX/doan/src/indexers/metadata_db.py), [shots.py](file:///d:/UIT/TX/doan/src/extractors/shots.py) (292 shots in 60s), and [keyframes.py](file:///d:/UIT/TX/doan/src/extractors/keyframes.py) (344 sharp keyframes in 25s, ~18.8MB).
* **Oct 26, 2026:**
  * Implemented and completed [Task 01B](file:///d:/UIT/TX/doan/tasks/task-01b-debug-ui-shots-keyframes.md): FastAPI backend in [src/ui/debug_server.py](file:///d:/UIT/TX/doan/src/ui/debug_server.py) with HTTP 206 Range video streaming and Single-Page Application in [src/ui/static/](file:///d:/UIT/TX/doan/src/ui/static/) featuring two-way timeline synchronization, auto-scroll isolation, and responsive keyframe inspection cards.
  * Added feature documentation runbook [.agents/skills/feature-documentation-guide/SKILL.md](file:///d:/UIT/TX/doan/.agents/skills/feature-documentation-guide/SKILL.md) and initial guides in [docs/guides/](file:///d:/UIT/TX/doan/docs/guides/).
  * Unified project language policy: User communicates in Vietnamese in chat, all generated documentation and codebase files are 100% English.
  * Completed [Task 02](file:///d:/UIT/TX/doan/tasks/task-02-visual-siglip-faiss.md):
    * Implemented [src/extractors/visual.py](file:///d:/UIT/TX/doan/src/extractors/visual.py) using `google/siglip2-so400m-patch14-384` in FP16 on GPU (Peak VRAM: 2.95 GB, safely within the 3.2 GB ceiling).
    * Extracted 344 keyframe embeddings and computed 292 shot-level mean pooled vectors for `L13_V001` (total 636 dense vectors, dimension 1152).
    * Built and persisted FAISS `IndexFlatIP` index ([data/indices/visual_siglip2.index](file:///d:/UIT/TX/doan/data/indices/visual_siglip2.index)) and metadata mapping JSON.
    * Evaluated baseline visual retrieval: Recall@1 = 0.3333, Recall@5 = 0.3333, Recall@10 = 0.6667, MRR = 0.3704.
    * Released GPU memory completely after inference via `safe_unload()`.
    * Documented feature usage in [docs/guides/visual-siglip-faiss.md](file:///d:/UIT/TX/doan/docs/guides/visual-siglip-faiss.md).
* **Oct 28, 2026:**
  * Defined two core engineering skills: `fault-tolerant-checkpointing` and `modular-code-architecture`.
  * Added Section 6 UI Testing Protocol to [AGENTS.md](file:///d:/UIT/TX/doan/AGENTS.md) strictly prioritizing manual testing over browser subagents.
  * Implemented and completed [Task 02B: Architecture Refactoring & Pipeline Fault-Tolerance Infrastructure](file:///d:/UIT/TX/doan/tasks/task-02b-fault-tolerance-and-modular-refactoring.md):
    * Upgraded [src/indexers/metadata_db.py](file:///d:/UIT/TX/doan/src/indexers/metadata_db.py) with `pipeline_checkpoints` table and CRUD methods.
    * Decoupled Layer 2 Core Engines (`shots.py`, `keyframes.py`, `visual.py`) from CLI parsing.
    * Built standardized Layer 3 Runners (`run_shots.py`, `run_keyframes.py`, `run_visual.py`) with pre-flight guards, atomic rollbacks, and batch progress summaries.
    * Created standalone index builder [src/indexers/build_indices.py](file:///d:/UIT/TX/doan/src/indexers/build_indices.py) to decouple dense feature caching (`.npz`) from FAISS indexing.
    * Verified single-video idempotency, dependency guards, and fast atomic FAISS rebuilding (0.06s).
    * Integrated interactive **Pipeline Checkpoints & DB Inspector** tab on Web Debug UI (`http://127.0.0.1:8000`).
  * Implemented and completed [Task 02C: Visual Feature Extraction Performance Optimization with SigLIP2-Base & DataLoader](file:///d:/UIT/TX/doan/tasks/task-02c-visual-performance-dataloader.md):
    * Completely eliminated the heavy `siglip2-so400m` model; established `google/siglip2-base-patch16-256` (86M params, 768-dim) as the primary visual model.
    * Centralized all Hugging Face model weights to [models/](file:///d:/UIT/TX/doan/models) on drive D: ([configs/default_config.yaml](file:///d:/UIT/TX/doan/configs/default_config.yaml)).
    * Implemented multithreaded PyTorch `DataLoader` with `KeyframeDataset` and `_collate_pil_images` in [src/extractors/visual.py](file:///d:/UIT/TX/doan/src/extractors/visual.py).
    * Added CLI arguments `--batch-size` and `--num-workers` to [src/extractors/run_visual.py](file:///d:/UIT/TX/doan/src/extractors/run_visual.py).
    * Extracted 338 keyframes for `L13_V001` in 27s; visual embedding for 338 keyframes + 292 shot-pooled vectors (630 total vectors) completed in 66s on GTX 1650 (down from ~330s, >5x speedup; peak VRAM < 600MB).
    * Rebuilt FAISS visual index in 0.05s with 768-dim vectors; verified dual-granularity search on Vietnamese and English queries.
    * Updated documentation [docs/guides/visual-siglip-faiss.md](file:///d:/UIT/TX/doan/docs/guides/visual-siglip-faiss.md).
* **Oct 29, 2026:**
  * Ingested batch 1 dataset (363 videos, ~62.3 GB) directly into [data/raw_videos/](file:///d:/UIT/TX/doan/data/raw_videos), expanding full repository to 726 videos (~116 GB, batches `L01` through `L24`).
  * Refactored [src/extractors/visual.py](file:///d:/UIT/TX/doan/src/extractors/visual.py) to eliminate shot-level mean pooling in favor of **Pure Keyframe Embeddings** (`1 Keyframe = 1 Vector`), eliminating ~40-50% redundant vectors and search duplicates. Verified on `L13_V001` (348 keyframes = 348 vectors).
  * Excluded audio and speech modalities (Whisper ASR, CLAP) due to competition conditions prohibiting audio playback. Removed `task-03-asr-whisper.md` and `task-07-audio-clap.md`; purged temporary audio directories and configurations.
  * Synchronized [PROJECT_OVERVIEW.md](file:///d:/UIT/TX/doan/PROJECT_OVERVIEW.md) and [TRACKING.md](file:///d:/UIT/TX/doan/TRACKING.md) to reflect the Visual + OCR multimodal architecture.
  * Implemented and completed [Task 04: On-Screen Text Extraction with EasyOCR & SQLite FTS5](file:///d:/UIT/TX/doan/tasks/task-04-ocr-easyocr.md):
    * Built core engine [src/extractors/ocr.py](file:///d:/UIT/TX/doan/src/extractors/ocr.py) with morphological edge-density pre-filter (~9ms/frame) and EasyOCR on CPU (0MB GPU VRAM, centralized storage in [models/easyocr/](file:///d:/UIT/TX/doan/models/easyocr)).
    * Replaced legacy PaddleOCR Latin model with native Vietnamese EasyOCR, eliminating Windows OpenMP DLL conflicts and vastly improving Vietnamese diacritics recognition.
    * Upgraded [src/indexers/metadata_db.py](file:///d:/UIT/TX/doan/src/indexers/metadata_db.py) with `ocr_records` and `ocr_fts` virtual table using `unicode61 remove_diacritics 2` and Vietnamese d-stroke folding (`đ`/`Đ` -> `d`/`D`) for accent-insensitive search.
    * Built standardized CLI runner [src/extractors/run_ocr.py](file:///d:/UIT/TX/doan/src/extractors/run_ocr.py) with pre-flight guards and rollback handlers.
    * Verified on `L13_V001` and integrated instant BM25 retrieval and OCR text badges into Web Debug UI.
    * Authored feature documentation guide [docs/guides/ocr-easyocr-guide.md](file:///d:/UIT/TX/doan/docs/guides/ocr-easyocr-guide.md).
* **Nov 01 - Nov 07, 2026:**
  * Completed full dataset batch extraction across **726/726 videos**:
    * Stage 1 (Shots): 726/726 COMPLETED.
    * Stage 2 (Keyframes): 726/726 COMPLETED (243,732 sharp keyframes, 5.65 GB).
    * Stage 3 (Visual SigLIP2): 726/726 COMPLETED; unified FAISS index built at [data/indices/visual_siglip2.index](file:///d:/UIT/TX/doan/data/indices/visual_siglip2.index) (321.6 MB).
    * Stage 4 (EasyOCR): 726/726 COMPLETED; indexed 568,562 text records in SQLite `ocr_records` and `ocr_fts` virtual tables.
  * Hardened pipeline fault-tolerance:
    * Enabled SQLite Write-Ahead Logging (`PRAGMA journal_mode = WAL;`) and 30s timeout to allow concurrent Web UI inspection during batch writes.
    * Bound deletion and re-insertion into the same atomic transaction in `save_ocr_records` to prevent duplicate rows in FTS5.
    * Added VRAM garbage collection and cache flushing inside exception handlers in [run_ocr.py](file:///d:/UIT/TX/doan/src/extractors/run_ocr.py).
  * Implemented **Two-Stage Fault-Tolerant Hybrid OCR Search** in [src/indexers/metadata_db.py](file:///d:/UIT/TX/doan/src/indexers/metadata_db.py):
    * Stage 1: Coarse candidate generation via FTS5 Soft OR (`"term1"* OR "term2"*`) preventing recall failure on single-term typos.
    * Stage 2: Token-level fuzzy rescoring via Python `difflib.SequenceMatcher` with Vietnamese diacritic folding (`fold_vietnamese()`).
    * Resolves Known-Item Search (KIS) queries under severe OCR character confusion (e.g. `tô Irùng biển số` matches `trùng biển số` at Rank #1).
    * Updated [tasks/task-04-ocr-easyocr.md](file:///d:/UIT/TX/doan/tasks/task-04-ocr-easyocr.md) and [docs/guides/ocr-easyocr-guide.md](file:///d:/UIT/TX/doan/docs/guides/ocr-easyocr-guide.md).
  * Formulated **Final Round Known-Item Search (KIS) Submission Protocol & DRES Integration**:
    * Documented comprehensive operational guide in [docs/guides/submission-protocol-guide.md](file:///d:/UIT/TX/doan/docs/guides/submission-protocol-guide.md) covering Textual KIS (5 min window, progressive hints), Video KIS (4 min window, <= 20s clip), mathematical scoring schedule (50 pts accuracy with -10 per wrong attempt, 50 pts time decaying linearly to 0), and trade-off optimization analysis.
    * Added DRES submission dataclasses to [src/common/types.py](file:///d:/UIT/TX/doan/src/common/types.py) (`DRESAnswer`, `DRESAnswerSet`, `DRESSubmissionPayload`).
    * Built standardized DRES API v2 client and CLI utility in [src/submission/dres_client.py](file:///d:/UIT/TX/doan/src/submission/dres_client.py) with automated payload formatting (integer milliseconds, video ID extension stripping) and duplicate submission prevention cache.
* **Nov 08, 2026:**
  * Formulated **[Task 06B: KIS Interactive Scrubber & DRES Live Submission Console](file:///d:/UIT/TX/doan/tasks/task-06b-kis-interactive-submission.md)**:
    * Defined human-in-the-loop temporal refinement workflow bridging search candidate keyframes with exact ground truth submission intervals.
    * Specified frame-accurate stepper controls (`[-5s]`, `[-1s]`, `[-0.04s]`, `[+0.04s]`, `[+1s]`, `[+5s]`) and keyboard hotkeys (`J`, `L`, arrow keys, `Space`).
    * Designed Mark In (`I`) and Mark Out (`O`) range selection, quick presets (shot bounds, +-2.5s window), and pre-submission range preview player.
    * Outlined 1-click live DRES API submission connector with duplicate suppression and real-time score decay simulator.
  * Enhanced **[Task 05: Temporal Multimodal Fusion, Query Routing & Multi-Cue Composition](file:///d:/UIT/TX/doan/tasks/task-05-temporal-fusion.md)**:
    * Upgraded query architecture with **Human-in-the-Loop Multi-Cue Composition** allowing users to combine arbitrary English visual cues (`+ Visual: "a blue truck"`, `+ Visual: "heavy rain"`), Vietnamese/Latin OCR text filters (`+ OCR: "51C 456.78"`), and chronological sequence stages (`>>`).
    * Eliminated bounding-box fragmentation in `ocr_fts` by planning in-place **Keyframe-Level OCR Aggregation** (`GROUP_CONCAT(text_detected, ' ')` per `keyframe_id`) and expanding Stage 1 Soft OR pool depth (`pool_limit >= 500`).
    * Expanded per-cue visual retrieval depth (`top_k_visual = 1500`) across the 243,732-keyframe index to preserve recall on multi-attribute intersections.
    * Formulated **Max-Per-Cue Reciprocal Rank Fusion (RRF)** and **Consensus Multiplier** inside 5s sliding windows to prevent intra-window double-counting bias.
    * Updated engineering skill runbook [.agents/skills/temporal-multimodal-fusion/SKILL.md](file:///d:/UIT/TX/doan/.agents/skills/temporal-multimodal-fusion/SKILL.md).
  * Initialized **[clean-code-patterns](file:///d:/UIT/TX/doan/.agents/skills/clean-code-patterns/SKILL.md)** engineering skill:
    * Codified strict static typing (100% parameter and return annotations), typed dataclass DTOs in [src/common/types.py](file:///d:/UIT/TX/doan/src/common/types.py), and standardized Google/Sphinx docstrings.
    * Mandated guard clauses (early return pattern) and function length/nesting limits (<= 40 lines, <= 2 indentation levels).
    * Enforced zero-raw-`print()` rule with structured `loguru` text badges (`[INFO]`, `[OK]`, `[WARNING]`, `[ERROR]`) and defensive exception handling.
    * Specified domain-specific Information Retrieval (IR) design patterns: Strategy Pattern for score fusion, Router/Factory Pattern for query decomposition, and Context Manager Pattern for safe resource protection.
    * Registered skill in [AGENTS.md](file:///d:/UIT/TX/doan/AGENTS.md) and [PROJECT_OVERVIEW.md](file:///d:/UIT/TX/doan/PROJECT_OVERVIEW.md).
  * Implemented and completed **[Task 05: Temporal Multimodal Fusion, Query Routing & Multi-Cue Composition](file:///d:/UIT/TX/doan/tasks/task-05-temporal-fusion.md)**:
    * Executed one-time migration `rebuild_ocr_fts_by_keyframe()` in [src/indexers/metadata_db.py](file:///d:/UIT/TX/doan/src/indexers/metadata_db.py): aggregated 568,562 OCR records into 187,518 keyframe-level FTS5 documents in 2.75s, enabling holistic banner and sign matching.
    * Expanded OCR candidate pool depth (`pool_limit = max(limit * 10, 500)`) preventing high-frequency word starvation.
    * Implemented `QueryParser` in [src/retrieval/query_parser.py](file:///d:/UIT/TX/doan/src/retrieval/query_parser.py) supporting power-user prefixes (`v:`, `ocr:`), sequence syntax (`>>`), Google-style quotes (`ocr:"..."`), vehicle plate regex, and structured JSON payloads.
    * Implemented `TemporalMomentFusor` and `MaxPerCueRRFStrategy` in [src/retrieval/score_fusion.py](file:///d:/UIT/TX/doan/src/retrieval/score_fusion.py) with anti-double-counting, multi-cue consensus multipliers, chronological sequence alignment within a 15s horizon, and temporal Non-Maximum Suppression (NMS with `IoU >= 0.3`).
    * Built unified `SearchEngine` in [src/retrieval/search_engine.py](file:///d:/UIT/TX/doan/src/retrieval/search_engine.py) with lazy-loaded singletons, CLI runner, and safe VRAM release.
    * Added REST endpoints `GET /api/search/multimodal` and `POST /api/search/multimodal` to [src/ui/debug_server.py](file:///d:/UIT/TX/doan/src/ui/debug_server.py) with automated candidate formatting and thumbnail resolution.
    * Authored comprehensive feature documentation guide in [docs/guides/multimodal-fusion-guide.md](file:///d:/UIT/TX/doan/docs/guides/multimodal-fusion-guide.md).
    * Created unit test suite in [tests/test_retrieval.py](file:///d:/UIT/TX/doan/tests/test_retrieval.py) verifying all parser patterns, anti-double-counting, and consensus boost.
  * Implemented and completed **[Task 06: Multimodal Search Web Application, Explainable Pipeline Inspector & Interactive Feedback](file:///d:/UIT/TX/doan/tasks/task-06-ui-and-feedback.md)**:
    * Implemented Explainable Multimodal Information Retrieval (XIR) with `search_with_trace` in [src/retrieval/search_engine.py](file:///d:/UIT/TX/doan/src/retrieval/search_engine.py) capturing per-cue independent candidate hits (Top 10), latency breakdown, and sliding window consensus diagnostics.
    * Added CLI flag `--trace` to `search_engine.py` displaying formatted step-by-step trace tables directly in the terminal.
    * Upgraded [src/ui/debug_server.py](file:///d:/UIT/TX/doan/src/ui/debug_server.py) with `/api/search/multimodal` returning structured `trace` objects and implemented instant Rocchio Relevance Feedback (`POST /api/search/feedback`, < 50ms) using FAISS in-memory vector reconstruction (`index.reconstruct`).
    * Built dynamic **Multi-Cue Query Builder** (`+ Visual (EN)`, `+ OCR (VI)`, `>> Sequence`) on the frontend ([src/ui/static/index.html](file:///d:/UIT/TX/doan/src/ui/static/index.html), [app.js](file:///d:/UIT/TX/doan/src/ui/static/app.js), [style.css](file:///d:/UIT/TX/doan/src/ui/static/style.css)).
    * Built collapsible **Pipeline Execution Trace & Per-Cue Inspector Panel** (`#pipelineTracePanel`) on the frontend with tabbed carousels showing individual candidate hits before fusion.
    * Added **Inspect Trigger Keyframes & Cue Evidence** expandable accordion to every candidate moment card, with 1-click video seek and Rocchio feedback buttons (`[+ Similar]`, `[- Exclude]`).
    * Authored comprehensive feature guide in [docs/guides/multimodal-search-ui-guide.md](file:///d:/UIT/TX/doan/docs/guides/multimodal-search-ui-guide.md).
  * Implemented and completed **[Task 06B: KIS Interactive Scrubber, Competition Accelerators & DRES Live Submission Console](file:///d:/UIT/TX/doan/tasks/task-06b-kis-interactive-submission.md)**:
    * Fixed `video_id` filter starvation in [src/retrieval/search_engine.py](file:///d:/UIT/TX/doan/src/retrieval/search_engine.py) by reconstructing and scoring all vectors of the target video directly (`< 0.5ms`), preventing global Top-1500 cutoff starvation.
    * Generalized `_link_sequential_stages()` in [src/retrieval/score_fusion.py](file:///d:/UIT/TX/doan/src/retrieval/score_fusion.py) to iteratively fold `N >= 2` chronological stages (`Stage 1 >> Stage 2 >> Stage 3 ...`).
    * Implemented **Negative Visual Cue Filtering (`-v:`)** in [src/retrieval/query_parser.py](file:///d:/UIT/TX/doan/src/retrieval/query_parser.py) and [src/retrieval/search_engine.py](file:///d:/UIT/TX/doan/src/retrieval/search_engine.py) via vector subtraction (`q_vec - 0.35 * mean(neg_vecs)`), and added **Story-Level Video Coverage Boost** (`story_boost_per_cue=0.08`) in [src/retrieval/score_fusion.py](file:///d:/UIT/TX/doan/src/retrieval/score_fusion.py).
    * Added backend endpoints `GET /api/videos/{video_id}/context`, `POST /api/dres/submit`, `GET /api/dres/status`, `POST /api/dres/session`, and `POST /api/dres/clear-cache` in [src/ui/debug_server.py](file:///d:/UIT/TX/doan/src/ui/debug_server.py).
    * Built **Fine-Grained Frame Scrubber**, **Mark In / Mark Out Range Console**, **1-Click Quick Submit @ Playhead (`+-0.5s`, hotkey `S`)**, **Temporal Context Filmstrip Drawer (`+-15s` neighbor keyframes)**, and **Live KIS Score Decay Simulator** in [src/ui/static/index.html](file:///d:/UIT/TX/doan/src/ui/static/index.html), [src/ui/static/app.js](file:///d:/UIT/TX/doan/src/ui/static/app.js), and [src/ui/static/style.css](file:///d:/UIT/TX/doan/src/ui/static/style.css).
    * Expanded unit tests in [tests/test_retrieval.py](file:///d:/UIT/TX/doan/tests/test_retrieval.py) and authored feature documentation in [docs/guides/kis-interactive-submission-guide.md](file:///d:/UIT/TX/doan/docs/guides/kis-interactive-submission-guide.md) and [docs/guides/kis-ui-user-and-strategy-guide.md](file:///d:/UIT/TX/doan/docs/guides/kis-ui-user-and-strategy-guide.md).
  * **Nov 11, 2026:**
    * Enhanced **OCR Search Retrieval (`search_ocr`)** in [src/indexers/metadata_db.py](file:///d:/UIT/TX/doan/src/indexers/metadata_db.py): implemented `expand_ocr_terms` with alphanumeric sub-token splitting (`HTV9` -> `HTV`, `9`, `51B` -> `51`, `B`), Vietnamese diacritic folding, spaceless substring matching, and fallback `LIKE` query on `ocr_records`.
    * Increased default candidate limits across [src/retrieval/search_engine.py](file:///d:/UIT/TX/doan/src/retrieval/search_engine.py), [src/retrieval/score_fusion.py](file:///d:/UIT/TX/doan/src/retrieval/score_fusion.py), and [src/ui/debug_server.py](file:///d:/UIT/TX/doan/src/ui/debug_server.py) from 25 to 50/100 candidates.
    * Added **Candidate Controls Bar** with **Grid View** & **List View** toggle, dynamic Results selector (25, 50, 100, 200 moments), and candidate statistics counter in [src/ui/static/index.html](file:///d:/UIT/TX/doan/src/ui/static/index.html), [src/ui/static/app.js](file:///d:/UIT/TX/doan/src/ui/static/app.js), and [src/ui/static/style.css](file:///d:/UIT/TX/doan/src/ui/static/style.css).
    * Restructured candidate cards for multi-column grid layout with large 16:9 keyframe thumbnails, overlaid rank/consensus badges, and prominent full-width emerald green `[Submit KIS]` buttons for rapid visual browsing and submission.

---

## 5. Next Action
* **All Planned Tasks Completed (100%):**
  1. Run final ablation benchmarks (`uv run python -m src.evaluation.evaluate`) or launch the interactive KIS workstation (`uv run python -m src.ui.debug_server`) for competition simulation and thesis defense demonstration.

