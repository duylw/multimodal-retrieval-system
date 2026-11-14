# Multimodal Video Moment Retrieval System

## 1. Overview
The **Multimodal Video Moment Retrieval System** is an offline ingestion, indexing, and interactive search workstation designed to locate precise temporal moments in large-scale video collections from natural language queries.

The architecture combines vision-language semantic embeddings (Google SigLIP2) and Vietnamese/English on-screen optical character recognition (EasyOCR) over a **two-tier decoupled storage model** that prevents VRAM exhaustion on hardware-constrained GPUs (4GB VRAM) and delivers sub-second retrieval latency across tens of thousands of video shots.

### Core Capabilities
* **Adaptive Scene & Keyframe Ingestion:** Automated shot boundary detection with PySceneDetect and motion blur/darkness-filtered adaptive keyframe extraction.
* **Dual-Modality Indexing:** 768-dimensional normalized keyframe embeddings indexed via FAISS (`IndexFlatIP`) paired with keyframe-aggregated full-text search indexed in SQLite FTS5 (BM25).
* **Multi-Cue Query Understanding & Automated Translation:** Parser supporting English visual descriptors (`v:`), Vietnamese on-screen text (`ocr:`), negative visual filtering (`-v:`), and multi-stage chronological sequence chaining (`>>`). Includes real-time automated Google Translate middleware (`VI ➜ EN`) that translates visual descriptions while preserving Vietnamese OCR tokens intact for SQLite FTS5.
* **Temporal Sliding-Window Fusion:** 5-second overlapping window grouping using Max-Per-Cue Reciprocal Rank Fusion (RRF), cross-modality consensus boosting, and temporal Non-Maximum Suppression (NMS).
* **Dedicated KIS Competition Workstation (Port 8001):** High-density contestant interface with dual-zone layout, session query history chips, 1-click playhead submission (`+-0.5s`, hotkey `S`), fine-stepper frame scrubbers (`0.04s` / 25 fps), live score decay simulator, and automated DRES API v2 competition submission.
* **Developer Debug Inspector (Port 8000):** Deep explainability interface featuring per-cue hits breakdown, instant 30-second context filmstrips (`+-15s` neighbor keyframes), and in-memory Rocchio relevance feedback (`< 50ms`).

---

## 2. System Architecture & End-to-End Flow

```text
====================================================================================================
OFFLINE INGESTION & DECOUPLED FEATURE INDEXING PIPELINE
====================================================================================================

 [ Raw Videos in data/raw_videos/ ]
               │
               ▼
 [ Stage 1: Shot Detection ] ──────────────────────────► SQLite metadata.db (shots table)
   (PySceneDetect ContentDetector)
               │
               ▼
 [ Stage 2: Adaptive Keyframe Extraction ] ────────────► data/keyframes/{video_id}/*.jpg
   (Laplacian blur filter, color distance)               SQLite metadata.db (keyframes table)
               │
               ├───────────────────────────────────────────────────────┐
               ▼ (GPU / CPU Sequential Stage: Batch Size 16)          ▼ (CPU Worker Stage)
 [ Stage 3: SigLIP2 Feature Extraction ]                [ Stage 4: EasyOCR Text Extraction ]
   (google/siglip2-base-patch16-256)                      (Vietnamese + English recognition)
               │                                                       │
               ▼                                                       ▼
 [ Per-Video Feature Cache: .npz ]                      [ Per-Video Text Cache: .json ]
               │                                                       │
               ▼                                                       ▼
 [ Decoupled FAISS Index Builder ]                      [ Keyframe Document SQLite FTS5 ]
   (IndexFlatIP: data/indices/visual_siglip2.index)       (BM25: metadata.db ocr_fts index)


====================================================================================================
ONLINE MULTI-CUE RETRIEVAL & INTERACTIVE WORKSTATIONS
====================================================================================================

 [ Contestant Query: xe buyt mau xanh | ocr: 51B ]
               │
               ▼
 [ Automated Translation Middleware (POST /api/translate) ]
   ├── Visual Cues: "xe buyt mau xanh" ──► "blue bus"
   └── Preserved OCR Cues: "ocr: 51B" (Unmodified Vietnamese)
               │
               ▼
 [ Structured Multi-Cue Query: v: blue bus | ocr: 51B ]
               │
               ├───────────────────────────────┐
               ▼                               ▼
 [ FAISS SigLIP2 Vector Search ]    [ SQLite FTS5 Text Search ]
   (Top 1500 keyframes per cue)       (Top 500 keyframes per cue)
               │                               │
               └───────────────┬───────────────┘
                               ▼
 [ Sliding Window Temporal Aggregator (5.0s Windows) ]
                               │
                               ▼
 [ Max-Per-Cue Reciprocal Rank Fusion (RRF) & Consensus Boost ]
                               │
                               ▼
 [ Temporal Non-Maximum Suppression (NMS, IoU >= 0.4) ]
                               │
                               ▼
 [ Ranked Video Moments: Video ID + Interval [Start, End] + Fused Score ]
                               │
               ┌───────────────┴───────────────┐
               ▼                               ▼
 [ KIS Competition Workstation ]     [ Developer Debug Inspector ]
   (http://127.0.0.1:8001)             (http://127.0.0.1:8000)
   - High-Density Frame Grid           - Per-Cue Hits Trace
   - Recent Query Chips                - Multi-Cue Visual Builder
   - 1-Click Submit @ Playhead (S)     - Rocchio Relevance Feedback
   - Live DRES API v2 Integration      - Two-Way Shot Sync
```

---

## 3. Recommended Documentation Reading Order

To understand the architecture, algorithms, and operation, follow this reading sequence:

| Step | Document | Purpose & Core Content |
| :---: | :--- | :--- |
| **1** | [PROJECT_OVERVIEW.md](file:///d:/UIT/TX/doan/PROJECT_OVERVIEW.md) | High-level system architecture, problem formulation, scientific metrics, and two-tier decoupled storage model. |
| **2** | [docs/GLOSSARY.md](file:///d:/UIT/TX/doan/docs/GLOSSARY.md) | Domain terminology definitions: Shots, Keyframes, Sliding Windows, RRF, IoU, and DRES KIS protocols. |
| **3** | [docs/guides/competition-workstation-guide.md](file:///d:/UIT/TX/doan/docs/guides/competition-workstation-guide.md) | Standalone KIS Competition Workstation guide: UI layout, auto-translation, history chips, hotkeys, and DRES submission. |
| **4** | [docs/guides/shot-detection-and-keyframes.md](file:///d:/UIT/TX/doan/docs/guides/shot-detection-and-keyframes.md) | Stage 1 and Stage 2 guide: PySceneDetect parameters, adaptive time sampling, and blur filtering. |
| **5** | [docs/guides/visual-siglip-faiss.md](file:///d:/UIT/TX/doan/docs/guides/visual-siglip-faiss.md) | Stage 3 guide: SigLIP2 embedding extraction, GPU memory management, and FAISS `IndexFlatIP` construction. |
| **6** | [docs/guides/ocr-easyocr-guide.md](file:///d:/UIT/TX/doan/docs/guides/ocr-easyocr-guide.md) | Stage 4 guide: CPU-based EasyOCR extraction, text normalization, and SQLite FTS5 full-text indexing. |
| **7** | [docs/guides/multimodal-fusion-guide.md](file:///d:/UIT/TX/doan/docs/guides/multimodal-fusion-guide.md) | Stage 5 guide: Query parsing rules, sliding window aggregation, Max-Per-Cue RRF, and temporal NMS. |
| **8** | [docs/guides/multimodal-search-ui-guide.md](file:///d:/UIT/TX/doan/docs/guides/multimodal-search-ui-guide.md) | Stage 6 guide: Web UI features, per-cue explainability trace inspector, and instant Rocchio feedback. |
| **9** | [docs/guides/submission-protocol-guide.md](file:///d:/UIT/TX/doan/docs/guides/submission-protocol-guide.md) | External integration guide: DRES REST API v2 contract, session management, and payload formatting. |
| **10** | [docs/GIT_GUIDELINES.md](file:///d:/UIT/TX/doan/docs/GIT_GUIDELINES.md) | Development standards: Git branching, Conventional Commits, and binary exclusion rules. |

---

## 4. Environment Setup & Execution Modes (GPU vs CPU)

The system supports two environment execution modes through [pyproject.toml](file:///d:/UIT/TX/doan/pyproject.toml):

### Option A: GPU Acceleration (Recommended for Ingestion & Fast SigLIP2)
Requires an NVIDIA GPU with `>= 4GB` VRAM (tested on NVIDIA GeForce GTX 1650 with CUDA 12.1).

```powershell
# 1. Install dependencies with GPU PyTorch (CUDA 12.1)
uv sync --extra gpu

# 2. Run any command using GPU acceleration
uv run --extra gpu python -m src.ui.competition_server --port 8001
```

### Option B: Pure CPU Mode (No Dedicated GPU Required)
Runs inference and search entirely on CPU. Suitable for workstations without an NVIDIA GPU, laptops, or review environments.

```powershell
# 1. Install dependencies with CPU-only PyTorch
uv sync --extra cpu

# 2. Run any command in CPU mode
uv run --extra cpu python -m src.ui.competition_server --port 8001
```

### Option C: Generic / No-Sync Run
If dependencies are already installed in `.venv`, skip dependency resolution checks with `--no-sync` or call the Python executable directly:

```powershell
# Fast launch without index sync
uv run --no-sync python -m src.ui.competition_server --port 8001

# Or via direct environment executable
.venv\Scripts\python.exe -m src.ui.competition_server --port 8001
```

---

## 5. Directory Structure Setup

Create the required local data layout:
```powershell
mkdir -p data/raw_videos data/keyframes data/indices data/cache models
```

Place your target `.mp4` video files inside [data/raw_videos/](file:///d:/UIT/TX/doan/data/raw_videos).

---

## 6. Offline Ingestion Pipeline Execution

Execute the pipeline stages strictly in sequence to adhere to the memory safety protocol:

### Stage 1: Shot Boundary Detection (PySceneDetect)
Detects camera cut points and transitions:
```powershell
# GPU / Standard
uv run --extra gpu python -m src.extractors.run_shots --video-dir data/raw_videos/

# CPU Mode
uv run --extra cpu python -m src.extractors.run_shots --video-dir data/raw_videos/
```

### Stage 2: Adaptive Keyframe Extraction
Extracts representative keyframes with Laplacian motion-blur filtering:
```powershell
# GPU / Standard
uv run --extra gpu python -m src.extractors.run_keyframes --video-dir data/raw_videos/

# CPU Mode
uv run --extra cpu python -m src.extractors.run_keyframes --video-dir data/raw_videos/
```

### Stage 3: SigLIP2 Feature Extraction & FAISS Indexing
Extracts 768-dimensional visual vectors and builds the atomic FAISS index:
```powershell
# GPU Mode (FP16, batch size 16 on GTX 1650)
uv run --extra gpu python -m src.extractors.run_visual_pipeline --video-dir data/raw_videos/

# CPU Mode (FP32, PyTorch CPU)
uv run --extra cpu python -m src.extractors.run_visual_pipeline --video-dir data/raw_videos/
```

### Stage 4: EasyOCR Extraction & SQLite FTS5 Indexing
Extracts Vietnamese/English on-screen text and builds keyframe-level full-text search indices:
```powershell
# EasyOCR executes multi-threaded on CPU in both modes
uv run --extra gpu python -m src.extractors.run_ocr_pipeline --video-dir data/raw_videos/

# CPU Mode
uv run --extra cpu python -m src.extractors.run_ocr_pipeline --video-dir data/raw_videos/
```

---

## 7. Interactive Workstations & Retrieval Interfaces

### A. Dedicated KIS Competition Workstation (Port 8001)
The primary contest interface designed for live VBS / AI Challenge competition:

```powershell
# Launch on GPU
uv run --extra gpu python -m src.ui.competition_server --port 8001

# Launch on CPU
uv run --extra cpu python -m src.ui.competition_server --port 8001
```

Access in your browser: `http://127.0.0.1:8001`

**Core Competition Features:**
* **Automated Query Translation:** Natural Vietnamese queries (e.g. `xe buyt mau xanh | ocr: 51B`) automatically translate visual cues to English (`blue bus`) while preserving Vietnamese license plates/signage for FTS5. Includes `[VI➜EN]` explicit button, `[Revert]` button, and `[x] Auto VI➜EN` toggle.
* **Session Query History Chips:** Top 15 queries stored in `localStorage` with 1-click execution chips.
* **High-Density Frame Grid:** Browsing with 12-20 moments simultaneously, rank badges (`#1`, `#2`, `#3`), overlaid consensus badges, and direct emerald `[Submit KIS]` buttons.
* **Single-Hand Ergonomics & Hotkeys:**
  * `/`: Jump to search bar.
  * `Enter`: Trigger translation and search.
  * `Esc`: Close modal or blur input.
  * `Space`: Toggle play/pause.
  * `J` / `L`: Seek backward / forward 1.0 second.
  * `Left` / `Right` Arrow: Step backward / forward 1 exact frame (`0.04s`). Hold `Shift` for `5.0s`.
  * `I` / `O`: Mark In / Mark Out timestamp.
  * `S`: Instant 1-click submit at playhead (`+-0.5s`) to DRES API v2.

### B. Developer Debug Inspector (Port 8000)
Detailed explainability console for algorithm tuning, fusion weights, and deep diagnostics:

```powershell
# Launch on GPU
uv run --extra gpu python -m src.ui.debug_server --port 8000

# Launch on CPU
uv run --extra cpu python -m src.ui.debug_server --port 8000
```

Access in your browser: `http://127.0.0.1:8000`

### C. Terminal CLI Search with Diagnostics
Run test queries from the command line to inspect per-cue candidate hits and fusion diagnostics:

```powershell
# Multi-cue search with trace diagnostics (GPU)
uv run --extra gpu python -m src.retrieval.search_engine --query "v: woman speaking | ocr: HTV9" --trace

# Multi-cue search with trace diagnostics (CPU)
uv run --extra cpu python -m src.retrieval.search_engine --query "v: woman speaking | ocr: HTV9" --trace
```

---

## 8. Verification & Benchmark Evaluation

### Run Unit Test Suite
```powershell
uv run --extra gpu python -m tests.test_competition_workstation
uv run --extra gpu python -m tests.test_retrieval
```

### Run Benchmark Evaluation & Scientific Metrics
Compute Recall@K (K=1, 5, 10) and Mean Reciprocal Rank (MRR) against ground-truth benchmarks:
```powershell
# Temporal tolerance evaluation (+-5 seconds)
uv run --extra gpu python -m src.evaluation.evaluate --gt data/ground_truth.json --pred data/predictions.json

# Temporal IoU evaluation (IoU >= 0.3)
uv run --extra gpu python -m src.evaluation.evaluate --gt data/ground_truth.json --pred data/predictions.json --iou --min_iou 0.3
```

---

## 9. Hardware Constraints & VRAM Safety Rules

* **Target Hardware Profile:** NVIDIA GeForce GTX 1650 (4GB VRAM) | RAM: 16GB.
* **Strict Sequential Staging:** Never load deep learning vision models (SigLIP2) and OCR models concurrently on GPU. Visual extraction executes on GPU with explicit VRAM garbage collection; OCR runs strictly on CPU with multi-threading.
* **Decoupled Two-Tier Storage:** Raw feature representations are cached as compressed per-video files (`.npz` for vectors, `.json` for OCR). The global FAISS index and SQLite database are constructed atomically from cache, allowing instant resumption if interrupted without recomputing deep learning models.
* **Online Search Footprint:** The web server, FAISS vector search, and SQLite FTS5 operate within `< 200MB` RAM and `0MB` GPU VRAM, ensuring instant responsiveness (`< 50ms` query latency). Model weights can be released dynamically using the `[Free VRAM]` button in the workstation header.
