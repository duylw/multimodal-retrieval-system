# User Guide: SigLIP2 Visual Feature Extraction & FAISS Indexing

## 1. Feature Overview
* **What it does:** Extracts dense L2-normalized 768-dimensional semantic embeddings from keyframe images and natural language text queries using Google's **SigLIP2-Base** foundation model (`google/siglip2-base-patch16-256`). Computes intra-shot arithmetic mean pooling to encapsulate continuous shot semantics, and builds high-speed nearest-neighbor search indices using **FAISS** (`IndexFlatIP`).
* **When to use:** Stage 3 of the ingestion pipeline, executed immediately after shot detection and keyframe extraction (Task 01) and prior to speech/OCR extraction (Task 03/04).
* **Value provided:**
  * **Dual-Granularity Indexing:** Indexes both individual representative keyframe vectors and shot-level mean-pooled vectors to maximize retrieval recall for both instantaneous actions and extended scene queries.
  * **Hardware-Disciplined FP16 Inference:** Uses PyTorch `DataLoader` batching (`batch_size=16`) occupying under 600 MB VRAM on the GTX 1650 (vastly below the 3.5 GB ceiling).
  * **Model Weights Centralization:** Model weights are stored exclusively in `models/` on drive D:, preventing system C: drive disk pollution.
  * **High-Speed Throughput:** Operates at 20-35 keyframes/second on GTX 1650, completing an 18-minute video (~250 frames) in under 25 seconds.
  * **Zero-Shot Multilingual Search:** Matches natural language text queries (Vietnamese and English) directly against visual content without translation.
  * **Strict GPU VRAM Release:** Automatically calls `safe_unload()` to purge model weights and PyTorch CUDA caches, freeing memory for subsequent stages.

---

## 2. Quick Start CLI

### Step 1: Extract visual embeddings and save per-video feature cache (.npz):
```powershell
# Single video execution (requires Stage 2 keyframes completed)
uv run python -m src.extractors.run_visual --video-id L13_V001

# Batch directory execution
uv run python -m src.extractors.run_visual --video-dir data/raw_videos/

# Force re-extraction with custom batch size or worker count
uv run python -m src.extractors.run_visual --video-id L13_V001 --force --batch-size 16
```

### Step 2: Build unified FAISS index from all feature caches (one-pass build):
```powershell
uv run python -m src.indexers.build_indices --modality visual
```

### Python API Usage:
```python
from src.extractors.visual import VisualExtractor
from src.indexers.vector_index import VectorIndex

# 1. Initialize extractor
extractor = VisualExtractor()

# 2. Extract text query embedding (1, 768)
query_vec = extractor.extract_text_embedding("a close-up shot of food preparation")

# 3. Load FAISS index and search top 5 candidates
index = VectorIndex({}, embedding_dim=768)
index.load("data/indices/visual_siglip2.index", "data/indices/visual_siglip2.json")
results = index.search(query_vec, top_k=5)

for r in results:
    print(f"Rank #{r['rank']}: Shot #{r['shot_id']} at t={r['timestamp_sec']}s (Score: {r['score']:.4f})")

# 4. Mandatory VRAM release
extractor.safe_unload()
```

---

## 3. CLI Arguments Table

| Argument | Type | Default Value | Description |
|---|---|---|---|
| `--video-id` | `str` | `None` | Process a single video ID (e.g. `L13_V001`). |
| `--video-dir` | `str` | `None` | Process all video files in directory. |
| `--config` | `str` | `"configs/default_config.yaml"` | Path to YAML configuration file. |
| `--force` | `bool` | `False` | Overwrite existing feature cache and force re-extraction. |
| `--batch-size` | `int` | `16` | Batch size for visual embedding extraction. |
| `--num-workers` | `int` | `0` | Number of worker processes for DataLoader image loading. |

---

## 4. Inputs & Outputs

* **Inputs:**
  * Keyframe images: `data/keyframes/{video_id}/*.jpg` (from Task 01).
  * SQLite metadata: [data/metadata.db](file:///d:/UIT/TX/doan/data/metadata.db) (`shots` and `keyframes` records).
  * Centralized Model Cache: `models/models--google--siglip2-base-patch16-256`.
* **Outputs:**
  * Per-video Feature Cache: `data/features/visual/{video_id}.npz` (contains 768-dim embeddings array + metadata JSON).
  * FAISS Binary Index: [data/indices/visual_siglip2.index](file:///d:/UIT/TX/doan/data/indices/visual_siglip2.index) (IndexFlatIP containing 768D L2-normalized vectors).
  * Metadata Mapping JSON: [data/indices/visual_siglip2.json](file:///d:/UIT/TX/doan/data/indices/visual_siglip2.json).
  * SQLite Checkpoint: [data/metadata.db](file:///d:/UIT/TX/doan/data/metadata.db) (`pipeline_checkpoints` table updated with `visual = COMPLETED`).

---

## 5. Technical Notes & Troubleshooting

* **Hardware Constraints & VRAM Safety:**
  * **GPU Target:** NVIDIA GeForce GTX 1650 (4GB VRAM).
  * **Measured Peak VRAM:** ~500-600 MiB in FP16 at `batch_size = 16`.
  * **Throughput:** ~20-35 keyframes/sec on GTX 1650.
* **Sequential Staging Rule:**
  * Never load the audio speech model (faster-whisper) while `VisualExtractor` is in memory. Always call `extractor.safe_unload()` or wrap inference in `try...finally`.
* **Windows Console Unicode:**
  * The CLI pipeline automatically configures UTF-8 standard output wrapper on Windows systems to cleanly display Vietnamese queries and evaluations without character encoding errors.
