# Multimodal Video Moment Retrieval System

## 1. Overview
The **Multimodal Video Moment Retrieval System** is an offline ingestion, indexing, and interactive search workstation designed to locate precise temporal moments in large-scale video collections from natural language queries.

The architecture combines vision-language semantic embeddings (Google SigLIP2) and Vietnamese/English on-screen optical character recognition (EasyOCR) over a **two-tier decoupled storage model** that prevents VRAM exhaustion on hardware-constrained GPUs (4GB VRAM) and delivers sub-second retrieval latency across tens of thousands of video shots.

### Core Capabilities
* **Adaptive Scene & Keyframe Ingestion:** Automated shot boundary detection with PySceneDetect and motion blur/darkness-filtered adaptive keyframe extraction.
* **Dual-Modality Indexing:** 768-dimensional normalized keyframe embeddings indexed via FAISS (`IndexFlatIP`) paired with keyframe-aggregated full-text search indexed in SQLite FTS5 (BM25).
* **Multi-Cue Query Understanding:** Parser supporting English visual descriptors (`v:`), Vietnamese on-screen text (`ocr:`), negative visual filtering (`-v:`), and multi-stage chronological sequence chaining (`>>`).
* **Temporal Sliding-Window Fusion:** 5-second overlapping window grouping using Max-Per-Cue Reciprocal Rank Fusion (RRF), cross-modality consensus boosting, and temporal Non-Maximum Suppression (NMS).
* **Interactive KIS Workstation:** Web-based human-in-the-loop retrieval interface featuring instant 30-second context filmstrips (`+-15s` neighbor keyframes), frame-accurate stepping (`0.04s` / 25 fps), in-memory Rocchio relevance feedback (`< 50ms`), and automated DRES API v2 competition submission.

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
               ▼ (GPU Sequential Stage: Batch Size 16)                ▼ (CPU Worker Stage)
 [ Stage 3: SigLIP2 Feature Extraction ]                [ Stage 4: EasyOCR Text Extraction ]
   (google/siglip2-base-patch16-224)                      (Vietnamese + English recognition)
               │                                                       │
               ▼                                                       ▼
 [ Per-Video Feature Cache: .npz ]                      [ Per-Video Text Cache: .json ]
               │                                                       │
               ▼                                                       ▼
 [ Decoupled FAISS Index Builder ]                      [ Keyframe Document SQLite FTS5 ]
   (IndexFlatIP: data/indices/visual_siglip2.index)       (BM25: metadata.db ocr_fts index)


====================================================================================================
ONLINE MULTI-CUE RETRIEVAL & INTERACTIVE SEARCH WORKSTATION
====================================================================================================

 [ User Query: v: woman speaking | ocr: HTV9 | -v: studio anchor ]
                               │
                               ▼
                   [ Multi-Cue Query Parser ]
                               │
               ┌───────────────┴───────────────┐
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
 [ CLI Search Engine with Trace ]    [ Web Workstation & KIS Console ]
   (uv run python -m ...)              (http://127.0.0.1:8000)
                                       - Interactive Video Scrubber
                                       - +-15s Temporal Filmstrip
                                       - 1-Click Submit @ Playhead (Hotkey S)
                                       - DRES API v2 Integration
```

---

## 3. Recommended Documentation Reading Order

To understand the architecture, algorithms, and operation, follow this reading sequence:

| Step | Document | Purpose & Core Content |
| :---: | :--- | :--- |
| **1** | [PROJECT_OVERVIEW.md](file:///d:/UIT/TX/doan/PROJECT_OVERVIEW.md) | High-level system architecture, problem formulation, scientific metrics, and two-tier decoupled storage model. |
| **2** | [docs/GLOSSARY.md](file:///d:/UIT/TX/doan/docs/GLOSSARY.md) | Domain terminology definitions: Shots, Keyframes, Sliding Windows, RRF, IoU, and DRES KIS protocols. |
| **3** | [docs/guides/shot-detection-and-keyframes.md](file:///d:/UIT/TX/doan/docs/guides/shot-detection-and-keyframes.md) | Stage 1 and Stage 2 guide: PySceneDetect parameters, adaptive time sampling, and blur filtering. |
| **4** | [docs/guides/visual-siglip-faiss.md](file:///d:/UIT/TX/doan/docs/guides/visual-siglip-faiss.md) | Stage 3 guide: SigLIP2 embedding extraction, GPU memory management, and FAISS `IndexFlatIP` construction. |
| **5** | [docs/guides/ocr-easyocr-guide.md](file:///d:/UIT/TX/doan/docs/guides/ocr-easyocr-guide.md) | Stage 4 guide: CPU-based EasyOCR extraction, text normalization, and SQLite FTS5 full-text indexing. |
| **6** | [docs/guides/multimodal-fusion-guide.md](file:///d:/UIT/TX/doan/docs/guides/multimodal-fusion-guide.md) | Stage 5 guide: Query parsing rules, sliding window aggregation, Max-Per-Cue RRF, and temporal NMS. |
| **7** | [docs/guides/multimodal-search-ui-guide.md](file:///d:/UIT/TX/doan/docs/guides/multimodal-search-ui-guide.md) | Stage 6 guide: Web UI features, per-cue explainability trace inspector, and instant Rocchio feedback. |
| **8** | [docs/guides/kis-ui-user-and-strategy-guide.md](file:///d:/UIT/TX/doan/docs/guides/kis-ui-user-and-strategy-guide.md) | Stage 6B guide: KIS interactive scrubber, DRES scoring rules (Strict Inclusion), and competition playbook. |
| **9** | [docs/guides/submission-protocol-guide.md](file:///d:/UIT/TX/doan/docs/guides/submission-protocol-guide.md) | External integration guide: DRES REST API v2 contract, session management, and payload formatting. |
| **10** | [docs/GIT_GUIDELINES.md](file:///d:/UIT/TX/doan/docs/GIT_GUIDELINES.md) | Development standards: Git branching, Conventional Commits, and binary exclusion rules. |

---

## 4. Step-by-Step Reproduction Guide

### A. Prerequisites & Environment Setup
* **Operating System:** Windows 10/11 or Linux (Ubuntu 20.04+).
* **Python Runtime:** Python `>= 3.12`.
* **Package Manager:** [`uv`](https://docs.astral.sh/uv/) (installed and on system `PATH`).
* **Hardware:** NVIDIA GPU with `>= 4GB` VRAM (tested on GeForce GTX 1650) or CPU.

Clone the repository and install all dependencies in a virtual environment managed by `uv`:
```powershell
# Sync virtual environment from pyproject.toml
uv sync
```

### B. Directory Structure Setup
Create the required directory layout:
```powershell
mkdir -p data/raw_videos data/keyframes data/indices data/cache
```
Place your collection of target video files (`.mp4`) inside [data/raw_videos/](file:///d:/UIT/TX/doan/data/raw_videos).

---

### C. Offline Ingestion Pipeline Execution

Execute the pipeline stages strictly in sequence to adhere to the GPU memory safety protocol:

#### Stage 1: Shot Boundary Detection
Detect camera cut points and transitions using PySceneDetect:
```powershell
# Single video execution
uv run python -m src.extractors.run_shots --video-id L13_V001

# Batch directory execution
uv run python -m src.extractors.run_shots --video-dir data/raw_videos/
```

#### Stage 2: Adaptive Keyframe Extraction
Extract representative keyframes with Laplacian motion-blur filtering:
```powershell
# Single video execution
uv run python -m src.extractors.run_keyframes --video-id L13_V001

# Batch directory execution
uv run python -m src.extractors.run_keyframes --video-dir data/raw_videos/
```

#### Stage 3: SigLIP2 Visual Embeddings & FAISS Indexing
Extract 768-dimensional visual vectors on GPU (batch size 16) and build the atomic FAISS index:
```powershell
# Single video execution
uv run python -m src.extractors.run_visual_pipeline --video-id L13_V001

# Batch directory execution
uv run python -m src.extractors.run_visual_pipeline --video-dir data/raw_videos/
```

#### Stage 4: EasyOCR Extraction & SQLite FTS5 Indexing
Extract Vietnamese/English on-screen text on CPU and build keyframe-level full-text search indices:
```powershell
# Single video execution
uv run python -m src.extractors.run_ocr_pipeline --video-id L13_V001

# Batch directory execution
uv run python -m src.extractors.run_ocr_pipeline --video-dir data/raw_videos/
```

---

### D. Online Retrieval & Interactive Workstation

#### Terminal Search with Explainability Trace
Run test queries from the command line to inspect per-cue candidate hits and fusion diagnostics:
```powershell
# Multi-cue search with trace diagnostics
uv run python -m src.retrieval.search_engine --query "v: woman speaking | ocr: HTV9" --trace

# Chronological sequence query search
uv run python -m src.retrieval.search_engine --query "v: car driving >> v: person exits car" --trace
```

#### Launch Interactive Web Application & KIS Console
Start the high-performance FastAPI / Uvicorn server:
```powershell
uv run python -m src.ui.debug_server
```
Access the workstation in your browser at:
```text
http://127.0.0.1:8000
```

---

### E. Verification & Benchmark Evaluation

#### Run Unit Test Suite
Verify query parsing, sliding window grouping, Rocchio re-weighting, and DRES endpoints:
```powershell
uv run python -m tests.test_retrieval
```

#### Run Benchmark Evaluation & Scientific Metrics
Compute Recall@K (K=1, 5, 10) and Mean Reciprocal Rank (MRR) against ground-truth benchmarks:
```powershell
# Temporal tolerance evaluation (+-5 seconds)
uv run python -m src.evaluation.evaluate --gt data/ground_truth.json --pred data/predictions.json

# Temporal IoU evaluation (IoU >= 0.3)
uv run python -m src.evaluation.evaluate --gt data/ground_truth.json --pred data/predictions.json --iou --min_iou 0.3
```

---

## 5. Hardware Constraints & VRAM Safety Rules

* **Target Hardware Profile:** NVIDIA GeForce GTX 1650 (4GB VRAM) | RAM: 16GB.
* **Strict Sequential Staging:** Never load deep learning vision models (SigLIP2) and OCR models concurrently on GPU. Visual extraction executes on GPU with explicit VRAM garbage collection; OCR runs strictly on CPU with multi-threading.
* **Decoupled Two-Tier Storage:** Raw feature representations are cached as compressed per-video files (`.npz` for vectors, `.json` for OCR). The global FAISS index and SQLite database are constructed atomically from cache, allowing instant resumption if interrupted without recomputing deep learning models.
* **Online Search Footprint:** The web server, FAISS vector search, and SQLite FTS5 operate within `< 150MB` RAM and `0MB` GPU VRAM, ensuring instant responsiveness (`< 50ms` query latency).
