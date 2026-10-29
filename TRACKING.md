# TRACKING.md - Project Execution & Milestone Tracking

> **Project:** Natural Language Multimodal Video Moment Retrieval System  
> **Institution:** University of Information Technology (UIT)  
> **Target Environment:** NVIDIA GeForce GTX 1650 (4GB VRAM), 16GB RAM, ~150GB Free Disk (D:).  
> **Last Updated:** October 26, 2026

---

## 1. Overall Status

* **Current Stage:** **Milestone 2: On-Screen Text Channel (PaddleOCR & SQLite FTS5)**
* **Overall Progress:** `50%`
* **Current Focus:** Completed Task 02C Visual Extraction Optimization & Pure Keyframe Embedding refactoring (removed redundant shot pooling, saving ~40% FAISS vectors). Ingested batch 1 videos, expanding full dataset to 726 videos (~116 GB). Excluded audio/speech channels (Whisper ASR, CLAP) per competition environment constraints. Ready for Task 04 (On-screen Text extraction with PaddleOCR and SQLite FTS5).

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
| **Task 04** | On-screen Text PaddleOCR | Text keyframe detector, PaddleOCR on CPU, SQLite FTS5 | **Ready** | [task-04](file:///d:/UIT/TX/doan/tasks/task-04-ocr-paddle.md) | `ocr.py`, `run_ocr.py`, SQLite `ocr_fts` virtual table |
| **Task 05** | Multimodal Fusion & Temporal NMS | Query router, RRF score normalization, 5s sliding window | **Pending** | [task-05](file:///d:/UIT/TX/doan/tasks/task-05-temporal-fusion.md) | `score_fusion.py`, `search_engine.py` |
| **Task 06** | Web Interface & Relevance Feedback | FastAPI search API, Range 206 video stream, Rocchio feedback | **Pending** | [task-06](file:///d:/UIT/TX/doan/tasks/task-06-ui-and-feedback.md) | `app.py`, `src/ui/static/` |

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
* [ ] **Milestone 2: On-Screen Text Channel Integration (PaddleOCR + SQLite FTS5)**
  * On-screen text extraction with PaddleOCR running on CPU.
  * SQLite FTS5 full-text search index and BM25 ranking for scene text, subtitles, and captions.
* [ ] **Milestone 3: Temporal Multimodal Fusion & Scientific Ablation Study**
  * Sliding window score aggregation (5s) and Reciprocal Rank Fusion (RRF) between Visual and OCR channels.
  * Ablation study tables measuring incremental contributions across Visual Only, Text Only, and Full Fusion.
* [ ] **Milestone 4: Web Application Delivery & Thesis Defense**
  * Search UI with timestamp-accurate video playback and relevance feedback.
  * Clean packaged codebase and thesis demonstration materials.

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
    * Centralized all Hugging Face model weights to `models/` on drive D: (`configs/default_config.yaml`).
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

---

## 5. Next Action
* **Execute [Task 04: On-screen Text Extraction with PaddleOCR & SQLite FTS5](file:///d:/UIT/TX/doan/tasks/task-04-ocr-paddle.md):**
  1. Implement `OCRExtractor` engine in `src/extractors/ocr.py` using PaddleOCR on CPU with edge-density heuristic filtering.
  2. Implement standardized CLI runner `src/extractors/run_ocr.py` with pre-flight guards and SQLite checkpointing.
  3. Create SQLite FTS5 virtual table for full-text keyword search over detected on-screen signage, banners, and subtitles.
  4. Build standalone indexer integration in `src/indexers/build_indices.py` for OCR text.
