---
name: modular-code-architecture
description: >-
  Use this skill whenever designing, structuring, or refactoring codebase modules, extractors,
  runners, indexers, and services. Enforces a strict 4-layer architecture, separation of core engine
  logic from CLI runners, one-way downward import rules, standalone tool execution (Unix philosophy),
  and standard CLI contracts.
---

# Modular Code Architecture & Separation of Concerns Runbook

This skill establishes architectural boundaries, module responsibilities, import conventions, and execution patterns for the **Multimodal Video Moment Retrieval** system.

---

## 1. Architectural Blueprint: The 4-Layer Hierarchy

To maintain clean code and prevent tight coupling, every Python module in `src/` must belong to exactly one layer:

```
┌────────────────────────────────────────────────────────────────────────┐
│ Layer 4: Serving & Evaluation Layer                                    │
│   src/ui/debug_server.py, src/evaluation/evaluate.py                   │
│   --> Fast APIs, web endpoints, benchmark harness                      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (Imports Layer 2 & 1)
┌───────────────────────────────────▼────────────────────────────────────┐
│ Layer 3: Stage Orchestrators & Runners                                 │
│   src/extractors/run_shots.py, run_keyframes.py, run_visual.py, ...    │
│   --> Standalone CLI tools, batch directory crawler, checkpoint guard  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (Imports Layer 2 & 1)
┌───────────────────────────────────▼────────────────────────────────────┐
│ Layer 2: Core Processing Engines                                       │
│   src/extractors/shots.py, visual.py, speech.py, ocr.py                │
│   src/indexers/vector_index.py, metadata_db.py                         │
│   src/fusion/score_fusion.py                                           │
│   --> Pure functional classes, explicit inputs/outputs, model lifecycle│
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (Imports Layer 1 only)
┌───────────────────────────────────▼────────────────────────────────────┐
│ Layer 1: Common Schemas & Infrastructure                               │
│   src/common/dataclasses.py, src/common/config.py, src/common/errors.py│
│   --> Domain models, configuration manager, base exceptions            │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Layer Responsibilities & Rules

### Layer 1: Common Schemas & Config (`src/common/`)
* **Allowed Contents:**
  * Dataclasses (`VideoMetadata`, `ShotBoundary`, `KeyframeMetadata`, `CandidateMoment`).
  * Configuration loader (`ConfigManager`).
  * Custom exceptions (`SystemConfigError`, `PrerequisiteNotMetError`).
* **Strict Prohibitions:**
  * Never import heavy machine learning frameworks (`torch`, `transformers`, `cv2`, `faster_whisper`, `paddleocr`) in Layer 1.
  * Must have zero dependencies on higher layers.

### Layer 2: Core Processing Engines (`src/extractors/`, `src/indexers/`, `src/fusion/`)
* **Allowed Contents:**
  * Encapsulated engine classes (e.g. `VisualExtractor`, `WhisperExtractor`, `VectorIndex`).
  * Pure methods taking explicit arguments (file paths, frame lists, audio arrays) and returning typed objects or dataclasses.
  * Model lifecycle management (`load_model()`, `extract()`, `safe_unload()`).
* **Strict Prohibitions:**
  * Never parse command-line arguments (`argparse`, `sys.argv`) inside Layer 2.
  * Never contain batch dataset loops or folder directory crawlers.
  * Never hardcode file paths or database operations unrelated to the engine's core purpose.

### Layer 3: Stage Orchestrators & Runners (`src/extractors/run_*.py`, `src/pipelines/`)
* **Allowed Contents:**
  * Standalone executable entry points (`if __name__ == "__main__":`).
  * CLI argument parsing (`--video-id`, `--video-dir`, `--force`, `--config`).
  * Pre-flight dependency validation, database checkpoint logging, and failure rollback handlers adhering to `fault-tolerant-checkpointing`.
* **Strict Prohibitions:**
  * Never implement raw model inference or low-level algorithms directly in runner scripts; always delegate to Layer 2 classes.

### Layer 4: Serving & Evaluation (`src/ui/`, `src/evaluation/`)
* **Allowed Contents:**
  * FastAPI endpoints, static file serving, query search routers.
  * Benchmark evaluation scripts (`evaluate.py`) calculating Recall@K, MRR.
* **Strict Prohibitions:**
  * Never duplicate extractor logic; import Layer 2 engines directly and reuse their methods.

---

## 3. Strict Import Guidelines (One-Way Downward Rule)

1. **Downward Dependencies Only:**
   * Layer 4 may import from Layers 3, 2, and 1.
   * Layer 3 may import from Layers 2 and 1.
   * Layer 2 may import from Layer 1.
   * Layer 1 must NOT import from any other layer in `src/`.
2. **Zero Circular Imports:**
   * Modules in the same layer should avoid circular cross-imports. If two modules require shared types, move those types down to `src/common/dataclasses.py`.
3. **Lazy Imports for Heavy DL Libraries:**
   * In multi-purpose modules (such as Web UI debug server or evaluation scripts), import heavy deep learning packages (`transformers`, `faster_whisper`) inside functions or behind lazy-loaded singletons to ensure fast server startup.

---

## 4. Standalone CLI Contract Standard

Every stage runner in Layer 3 must follow a consistent CLI interface:

```bash
# Process a single video
uv run python -m src.extractors.run_<stage> --video-id <video_id>

# Process an entire dataset directory
uv run python -m src.extractors.run_<stage> --video-dir data/raw_videos/

# Optional flags supported across all runners
--config configs/default_config.yaml  # Custom configuration path
--force                               # Overwrite/rerun even if already COMPLETED
--dry-run                             # Validate prerequisites without running models
```

### Standard Argument Parsing Pattern:
```python
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage runner for <stage_name>.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--video-id", type=str, help="Process a single video ID (e.g. L13_V001)")
    group.add_argument("--video-dir", type=str, help="Process all videos in directory")
    parser.add_argument("--config", type=str, default="configs/default_config.yaml", help="Path to config YAML")
    parser.add_argument("--force", action="store_true", help="Force re-extraction even if stage was completed")
    return parser.parse_args()
```

---

## 5. Decoupling Feature Extraction from Indexing

To prevent corrupting large index files and eliminate redundant file I/O:

1. **Extraction Stage (Per-Video Isolation):**
   * Output per-video feature caches to `data/features/<modality>/<video_id>.npz`.
   * Never mutate the global FAISS index or SQLite FTS5 index during per-video feature extraction.
2. **Indexing Stage (Atomic One-Pass Build):**
   * Run a separate indexing tool: `uv run python -m src.indexers.build_indices --modality visual`.
   * Reads all available `.npz` caches, stacks vectors in memory, and persists the binary `.index` and metadata `.json` atomically in a single pass.
   * Adding new videos requires only extracting their `.npz` files and running a fast index rebuild.

