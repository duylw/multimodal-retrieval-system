# User Guide: SigLIP2 Visual Feature Extraction & FAISS Indexing

## 1. Feature Overview
* **What it does:** Extracts dense L2-normalized 1152-dimensional semantic embeddings from keyframe images and natural language text queries using Google's **SigLIP2** foundation model (`google/siglip2-so400m-patch14-384`). Computes intra-shot arithmetic mean pooling to encapsulate continuous shot semantics, and builds high-speed nearest-neighbor search indices using **FAISS** (`IndexFlatIP`).
* **When to use:** Stage 2 of the ingestion pipeline, executed immediately after shot detection and keyframe extraction (Task 01) and prior to speech/OCR extraction (Task 03/04).
* **Value provided:**
  * **Dual-Granularity Indexing:** Indexes both individual representative keyframe vectors and shot-level mean-pooled vectors to maximize retrieval recall for both instantaneous actions and extended scene queries.
  * **Hardware-Disciplined FP16 Inference:** Uses safe micro-batching (`batch_size=4`) occupying ~2.95 GB VRAM on the GTX 1650 (below the 3.2 GB ceiling).
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

# Force re-extraction
uv run python -m src.extractors.run_visual --video-id L13_V001 --force
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

# 2. Extract text query embedding (1, 1152)
query_vec = extractor.extract_text_embedding("a close-up shot of food preparation")

# 3. Load FAISS index and search top 5 candidates
index = VectorIndex({}, embedding_dim=1152)
index.load("data/indices/visual_siglip2.index", "data/indices/visual_siglip2.json")
results = index.search(query_vec, top_k=5)

for r in results:
    print(f"Rank #{r['rank']}: Shot #{r['shot_id']} at t={r['timestamp_sec']}s (Score: {r['score']:.4f})")

# 4. Mandatory VRAM release
extractor.safe_unload()
```

---

## 3. CLI Arguments Table

| Argument | Short Flag | Type | Default Value | Description |
|---|---|---|---|---|
| `--video-id` | `-v` | `str` | `"L13_V001"` | Target video ID whose keyframes will be processed from `metadata.db` |
| `--query` | `-q` | `str` | `"cooking and food preparation"` | Natural language query string to benchmark retrieval accuracy |
| `--eval-gt` | *(flag)* | `bool` | `False` | When set, evaluates queries from `data/ground_truth.json` and prints Recall@K and MRR table |
| `--force` | `-f` | `bool` | `False` | Overwrites existing FAISS index on disk and recomputes embeddings from scratch |

---

## 4. Inputs & Outputs

* **Inputs:**
  * Keyframe images: `data/keyframes/{video_id}/*.jpg` (from Task 01).
  * SQLite metadata: [data/metadata.db](file:///d:/UIT/TX/doan/data/metadata.db) (`shots` and `keyframes` records).
  * Ground truth benchmark (optional): [data/ground_truth.json](file:///d:/UIT/TX/doan/data/ground_truth.json) *(Note: Currently a synthetic schema template for pipeline integration; metrics against this file serve as baseline test runs only)*.
* **Outputs:**
  * FAISS Binary Index: [data/indices/visual_siglip2.index](file:///d:/UIT/TX/doan/data/indices/visual_siglip2.index) (IndexFlatIP containing 636 L2-normalized 1152D vectors).
  * Metadata Mapping JSON: [data/indices/visual_siglip2.json](file:///d:/UIT/TX/doan/data/indices/visual_siglip2.json) (maps FAISS IDs to timestamps, shot boundaries, and pooled flags).
  * SQLite Checkpoint: [data/metadata.db](file:///d:/UIT/TX/doan/data/metadata.db) (`checkpoints` table updated with `visual_embedding = done`).

---

## 5. Technical Notes & Troubleshooting

* **Hardware Constraints & VRAM Safety:**
  * **GPU Target:** NVIDIA GeForce GTX 1650 (4GB VRAM).
  * **Measured Peak VRAM:** ~2,950 MiB in FP16 at `batch_size = 4`.
  * **Automatic Fallback:** If VRAM exceeds 3.2 GB or throughput drops below 4 FPS on larger resolutions, the extractor automatically falls back to `google/siglip2-base-patch16-256` (~700 MB VRAM, 25-40 FPS).
* **Sequential Staging Rule:**
  * Never load the audio speech model (faster-whisper) while `VisualExtractor` is in memory. Always call `extractor.safe_unload()` or wrap inference in `try...finally`.
* **Windows Console Unicode:**
  * The CLI pipeline automatically configures UTF-8 standard output wrapper on Windows systems to cleanly display Vietnamese queries and evaluations without character encoding errors.
