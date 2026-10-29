# Project Overview: Multimodal Video Moment Retrieval System

## 1. Problem Formulation
The system addresses the problem of **Natural Language Video Moment Retrieval (NLVR)**:
* **Input:**
  * Offline Video Repository: 726 broadcast and real-world video files (~116 GB, approximately 70-80 hours) from the HCMAI24 dataset (batches `L01` through `L24`), covering diverse topics: news, documentaries, cooking, lifestyle, traffic, interviews, and public safety.
  * Online User Query: Natural language query (scene descriptions, visual actions, or on-screen signage/captions in Vietnamese or English).
  * *Operational Constraint:* Audio and speech channels (ASR / CLAP) are explicitly excluded as competition and evaluation environments operate without audio listening equipment or headphones. The system relies strictly on **Visual (SigLIP2)** and **On-Screen Text (EasyOCR)** modalities.
* **Output:**
  * A ranked list of candidate moments: **Video ID + Shot ID + Start Time (seconds) + End Time (seconds) + Confidence Score**.
  * Interactive playback enabling users to seek directly to matching moments and explore surrounding context.

---

## 2. Scientific Evaluation Metrics
To support academic thesis requirements, the system evaluates against a Ground Truth Benchmark of 20-50 queries with validated temporal boundaries:
1. **Recall@K (K = 1, 5, 10):** Percentage of queries whose ground truth moment appears in the top K retrieved results.
2. **Mean Reciprocal Rank (MRR):** Mean inverse rank of the first hit.
3. **Hit Condition:** A prediction at timestamp T is considered a hit if:
   * Timestamp T falls within the true boundary: `[Start_true - 5s, End_true + 5s]`.
   * Or the temporal Intersection over Union (IoU) between predicted segment and ground truth segment is >= 0.3.
4. **Ablation Study Matrix:**
   * Visual Only (SigLIP2 Keyframe Embeddings)
   * Text Only (EasyOCR On-Screen Text with SQLite FTS5 / BM25)
   * Multimodal Fusion (Visual SigLIP2 + On-Screen Text EasyOCR via RRF)

---

## 3. Multimodal System Architecture

The pipeline uses a **Two-Tier Storage Architecture** that decouples deep learning feature extraction (per-video compressed caching) from atomic index building:

```
OFFLINE PHASE (DATA INGESTION, FEATURE CACHING & DECOUPLED INDEXING)
[Raw Video Files (726 videos)]
        │
        ├─► [Video Decoder] ──► [Adaptive Shot Detector] ──► [Adaptive Keyframe Extractor]
        │                                                           │
        │                                                           ├─► [SigLIP2-Base (768-dim, DataLoader)]
        │                                                           │   (Pure Keyframe Embeddings: 1 KF = 1 Vector)
        │                                                           │   │
        │                                                           │   ▼
        │                                                           │   [Per-Video Feature Cache: .npz]
        │                                                           │   │
        │                                                           │   ▼ (Decoupled Index Builder)
        │                                                           │   [FAISS Index: Visual (IndexFlatIP)]
        │                                                           │
        │                                                           ▼
        └─► [Text-rich Keyframes] ──► [EasyOCR (Vietnamese, CPU)]
                                                    │
                                                    ▼
                                       [Per-Video Text Metadata]
                                                    │
                                                    ▼
                                       [SQLite FTS5 Full-Text Search Index]


ONLINE PHASE (QUERY UNDERSTANDING & TEMPORAL FUSION)
[User Query (Text / Visual Description)]
        │
        ▼
[Query Parser & Router] ── (Rule-based Regex + Translation Fallback)
        │
        ├─► [Visual Description (EN)] ──► FAISS SigLIP2 Search (Top 200)
        │
        └─► [On-screen Text / Signage] ──► SQLite FTS5 OCR Search (Top 200)
        │
        ▼
[Score Normalization: Min-Max / Reciprocal Rank Fusion (RRF)]
        │
        ▼
[Temporal Fusion: 5-second Sliding Window]
        │
        ▼
[Temporal Non-Maximum Suppression (NMS) & Final Ranking]
        │
        ▼
[Web UI: Search Results + Range 206 Video Streaming + Relevance Feedback]
```

---

## 4. Codebase Directory Layout

The repository enforces a **4-Layer Modular Architecture** with strict engine-runner decoupling, atomic checkpointing in SQLite, and centralized model cache management:

```
d:/UIT/TX/doan/
│
├── AGENTS.md                  # Assistant persona, operating rules, hardware constraints
├── PROJECT_OVERVIEW.md        # High-level architecture and system blueprint (this file)
├── TRACKING.md                # Task tracking board, activity logs, and milestone progress
├── pyproject.toml             # Project dependencies and configuration (managed by uv)
├── .python-version            # Python runtime version (3.12)
│
├── .agents/                   # Specialized engineering skills
│   └── skills/
│       ├── fault-tolerant-checkpointing/  # Pre-flight guards, atomic rollbacks, idempotency
│       ├── modular-code-architecture/     # 4-layer architecture, engine-runner separation
│       ├── video-benchmark-eval/          # Ground truth benchmarks, Recall@K, MRR, IoU
│       ├── vram-safe-embedding/           # GTX 1650 4GB VRAM safety, sequential staging
│       ├── temporal-multimodal-fusion/    # RRF fusion, sliding windows, temporal NMS
│       └── feature-documentation-guide/   # Standardized CLI usage documentation
│
├── docs/                      # Technical documentation and guides
│   ├── GLOSSARY.md            # Technical dictionary and AI model mechanics
│   ├── GIT_GUIDELINES.md      # Conventional commits and Git branching standards
│   └── guides/                # Practical CLI and feature user guides
│       ├── shot-detection-and-keyframes.md
│       ├── shot-keyframe-inspector.md
│       ├── visual-siglip-faiss.md
│       └── debug-ui-guide.md
│
├── tasks/                     # Task specifications and implementation roadmaps
│   ├── task-00-environment-and-eval.md
│   ├── task-01-shot-detection-keyframes.md
│   ├── task-01b-debug-ui-shots-keyframes.md
│   ├── task-02-visual-siglip-faiss.md
│   ├── task-02b-fault-tolerance-and-modular-refactoring.md
│   ├── task-02c-visual-performance-dataloader.md
│   ├── task-04-ocr-easyocr.md
│   ├── task-05-temporal-fusion.md
│   └── task-06-ui-and-feedback.md
│
├── configs/                   # System configuration files
│   └── default_config.yaml    # Storage paths, shot thresholds, model IDs, batch sizes
│
├── models/                    # Centralized Hugging Face model cache (on D: drive to protect C:)
│
├── src/                       # Core system source code (4-layer modular hierarchy)
│   ├── __init__.py
│   │
│   ├── common/                # Layer 1: Foundation (interfaces, config, data schemas)
│   │   ├── __init__.py
│   │   ├── base.py            # BaseExtractor abstract base class
│   │   ├── config.py          # ConfigManager YAML loader
│   │   └── types.py           # Dataclasses (VideoRecord, ShotRecord, KeyframeRecord)
│   │
│   ├── extractors/            # Layer 2 (Core Engines) & Layer 3 (CLI Runners)
│   │   ├── __init__.py
│   │   ├── shots.py           # Engine: Adaptive shot boundary detection
│   │   ├── run_shots.py       # Runner: CLI for shot detection with checkpoint guards
│   │   ├── keyframes.py       # Engine: Adaptive keyframe extraction & blur filter
│   │   ├── run_keyframes.py   # Runner: CLI for keyframe extraction with rollback
│   │   ├── visual.py          # Engine: SigLIP2-Base pure keyframe embedding & DataLoader
│   │   ├── run_visual.py      # Runner: CLI for visual feature extraction to .npz caches
│   │   ├── ocr.py             # Engine: EasyOCR text extraction from keyframes (on CPU)
│   │   └── run_ocr.py         # Runner: CLI for OCR extraction to SQLite FTS5
│   │
│   ├── indexers/              # Database management & search index construction
│   │   ├── __init__.py
│   │   ├── metadata_db.py     # SQLite manager for videos, shots, keyframes, checkpoints
│   │   ├── vector_index.py    # FAISS IndexFlatIP manager for visual embeddings
│   │   ├── text_index.py      # SQLite FTS5 text indexer for OCR scene text
│   │   └── build_indices.py   # Standalone CLI tool to aggregate .npz caches into FAISS
│   │
│   ├── retrieval/             # Layer 4: Query processing & multimodal score fusion
│   │   ├── __init__.py
│   │   ├── query_parser.py    # Intent parsing and translation fallback
│   │   ├── score_fusion.py    # Reciprocal Rank Fusion (RRF) & 5s sliding window
│   │   └── search_engine.py   # Unified multimodal search orchestrator
│   │
│   ├── evaluation/            # Scientific benchmark harness
│   │   ├── __init__.py
│   │   ├── ground_truth.json  # Benchmark queries with ground truth timestamps
│   │   └── evaluate.py        # Recall@K, MRR, IoU calculation & ablation reporter
│   │
│   └── ui/                    # User interface & developer inspection services
│       ├── __init__.py
│       ├── debug_server.py    # FastAPI server (HTTP 206 video stream, visual search, monitor)
│       ├── app.py             # Production search web application
│       └── static/            # Frontend SPA assets (HTML5, modern CSS, vanilla JS)
│           ├── index.html
│           ├── style.css
│           └── app.js
│
└── data/                      # Local data artifacts (ignored in Git)
    ├── raw_videos/            # 726 raw MP4 files (batches L01 - L24, ~116 GB)
    ├── keyframes/             # Extracted JPEG keyframes organized by video ID
    ├── features/              # Per-video compressed numpy feature caches (.npz)
    │   └── visual/            # Dense SigLIP2 keyframe embeddings per video
    ├── indices/               # Unified FAISS indices (.index) and metadata mappings (.json)
    └── metadata.db            # SQLite relational database (videos, shots, keyframes, checkpoints)
```
