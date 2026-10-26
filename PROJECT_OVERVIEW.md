# Project Overview: Multimodal Video Moment Retrieval System

## 1. Problem Formulation
The system addresses the problem of **Natural Language Video Moment Retrieval (NLVR)**:
* **Input:**
  * Offline Video Repository: Approximately 100GB of video (equivalent to 40-50 hours) covering diverse topics: news, documentaries, cooking, lifestyle, vlogs, etc.
  * Online User Query: A natural language description (e.g., *"how to marinate beef before stir-frying"*, *"news anchor interviewing residents at fire scene"*, *"ambulance rushing through intersection with siren"*).
* **Output:**
  * A ranked list of candidate moments: **Video ID + Start Time (seconds) + End Time (seconds) + Confidence Score**.
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
   * Visual Only (SigLIP2)
   * Visual + ASR (Whisper)
   * Visual + OCR (PaddleOCR)
   * Full Multimodal Fusion (Visual + ASR + OCR + CLAP)

---

## 3. Multimodal System Architecture

Pipeline flow represented in ASCII:

```
OFFLINE PHASE (DATA INGESTION & MULTI-INDEXING)
[Raw Video Files]
        │
        ├─► [Video Decoder] ──► [SceneDetect / TransNetV2] ──► [Adaptive Keyframe Extractor]
        │                                                              │
        │                                                              ▼
        │                                                 [SigLIP2 Image Embedding]
        │                                                 + [Shot-level Mean Pooling]
        │                                                              │
        │                                                              ▼
        │                                                 [FAISS Index: Visual]
        │
        ├─► [Audio Extractor (16kHz WAV)] ──► [Silero VAD] ──► [faster-whisper int8]
        │                                                              │
        │                                                              ▼
        │                                                 [Transcripts with Timestamps]
        │                                                              │
        │                                          ┌───────────────────┴───────────────────┐
        │                                          ▼                                       ▼
        │                                 [BM25 Lexical Index]                    [bge-m3 Dense Index]
        │
        ├─► [Keyframes with Text] ──► [PaddleOCR (Vietnamese)]
        │                                          │
        │                                          ▼
        │                             [SQLite FTS5 Full-text Search]
        │
        └─► [Audio 10s Chunks] ──► [CLAP Audio Event Embedding] ──► [FAISS Index: Audio]


ONLINE PHASE (QUERY UNDERSTANDING & TEMPORAL FUSION)
[User Query]
        │
        ▼
[Query Parser & Router] ── (Rule-based Regex + Translation Fallback)
        │
        ├─► [Visual Description (EN)] ──► FAISS SigLIP2 Search (Top 200)
        ├─► [Spoken Keywords]          ──► BM25 + bge-m3 ASR Search (Top 200)
        ├─► [On-screen Text / Signage] ──► SQLite FTS5 OCR Search (Top 200)
        └─► [Ambient Sounds]           ──► FAISS CLAP Search (Top 200)
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

```
d:/UIT/TX/doan/
│
├── AGENTS.md                  # Assistant persona, operating rules, hardware constraints
├── PROJECT_OVERVIEW.md        # High-level architecture and system blueprint (this file)
├── TRACKING.md                # Task tracking board and project roadmap
│
├── .agents/                   # Assistant capabilities and specialized runbooks
│   └── skills/                # Progressive disclosure engineering skills
│       ├── video-benchmark-eval/
│       ├── vram-safe-embedding/
│       ├── temporal-multimodal-fusion/
│       └── feature-documentation-guide/
│
├── docs/                      # Technical documentation and team guidelines
│   ├── GLOSSARY.md            # Technical dictionary and AI model mechanics
│   ├── GIT_GUIDELINES.md      # Git workflow, conventional commits, and branching
│   └── guides/                # Step-by-step user and CLI feature guides
│
├── tasks/                     # Task specifications and implementation plans
│   ├── task-00-environment-and-eval.md
│   ├── task-01-shot-detection-keyframes.md
│   ├── task-01b-debug-ui-shots-keyframes.md
│   ├── task-02-visual-siglip-faiss.md
│   ├── task-03-asr-whisper.md
│   ├── task-04-ocr-paddle.md
│   ├── task-05-temporal-fusion.md
│   ├── task-06-ui-and-feedback.md
│   └── task-07-audio-clap.md
│
├── configs/                   # System configuration files
│   └── default_config.yaml    # Storage paths, shot thresholds, model IDs, batch sizes
│
├── src/                       # Core system source code
│   ├── __init__.py
│   ├── pipeline.py            # Orchestrator for end-to-end offline pipeline with resume
│   │
│   ├── extractors/            # Feature extraction modules
│   │   ├── __init__.py
│   │   ├── shots.py           # Shot boundary detection (PySceneDetect / TransNetV2)
│   │   ├── keyframes.py       # Adaptive time-interval keyframe extraction and filters
│   │   ├── visual.py          # SigLIP2 visual embeddings
│   │   ├── speech.py          # Silero VAD + faster-whisper transcription
│   │   ├── ocr.py             # Keyframe text detection + PaddleOCR
│   │   └── audio_events.py    # CLAP audio event embeddings
│   │
│   ├── indexers/              # Database and index managers
│   │   ├── __init__.py
│   │   ├── vector_index.py    # FAISS indices for visual and audio embeddings
│   │   ├── text_index.py      # SQLite FTS5 and BM25 indexers
│   │   └── metadata_db.py     # SQLite manager for videos, shots, keyframes, checkpoints
│   │
│   ├── retrieval/             # Query routing and multimodal fusion
│   │   ├── __init__.py
│   │   ├── query_parser.py    # Intent parsing and query translation
│   │   ├── score_fusion.py    # RRF score normalization and 5s sliding window
│   │   └── search_engine.py   # Unified search orchestrator
│   │
│   ├── evaluation/            # Scientific benchmark harness
│   │   ├── __init__.py
│   │   ├── ground_truth.json  # Benchmark queries with ground truth timestamps
│   │   └── evaluate.py        # Evaluates Recall@K, MRR, IoU, and ablation tables
│   │
│   └── ui/                    # Search interface and debug tools
│       ├── debug_server.py    # FastAPI server for shot and keyframe inspection
│       ├── app.py             # Primary search FastAPI application
│       └── static/            # Frontend SPA assets (HTML/CSS/JS)
│
├── data/                      # Local data directory (excluded in .gitignore)
│   ├── raw_videos/            # Input video files
│   ├── keyframes/             # Extracted keyframe images
│   ├── audio_temp/            # Temporary audio files (auto-cleaned after ASR)
│   ├── indices/               # FAISS (.index) and SQLite (.db) storage
│   └── checkpoints/           # Execution state tracking
├── pyproject.toml             # Project dependencies and configuration (uv)
└── .python-version            # Python runtime version
```
