# Task 02C: Visual Extraction Optimization with SigLIP2-Base, PyTorch DataLoader & Model Centralization

## 1. Objectives (What)
* **Adopt SigLIP2-Base as Primary Visual Model:** Completely drop the heavy `google/siglip2-so400m-patch14-384` (400M params, 384x384 resolution, ~5-6 min/video) in favor of the lightweight, fast `google/siglip2-base-patch16-256` (86M params, 256x256 resolution, 768-dim embeddings).
* **Centralize Model Weights:** Store all Hugging Face and deep learning models exclusively under `models/` on drive D:, preventing system C: drive pollution.
* **PyTorch DataLoader Pipeline:** Implement multithreaded PyTorch `DataLoader` with `KeyframeDataset` using background prefetching (`num_workers=2`, `pin_memory=True`) in [src/extractors/visual.py](file:///d:/UIT/TX/doan/src/extractors/visual.py).
* **High-Throughput Extraction on GTX 1650 (4GB VRAM):**
  * Increase batch size from 4 to 16 (or 32), running in FP16 with minimal VRAM footprint (~500MB).
  * Reduce visual extraction time per 18-minute video from ~330 seconds down to < 30 seconds (> 10x speedup, ~15-25 FPS).
  * Enable batch processing of all 600 repository videos in under 5 hours.
* **Evaluation Quality Safeguard:** Rebuild the FAISS index (768-dim) and run [src/evaluation/evaluate.py](file:///d:/UIT/TX/doan/src/evaluation/evaluate.py) on [data/ground_truth.json](file:///d:/UIT/TX/doan/data/ground_truth.json) to measure baseline Recall@K and MRR.
* **Architecture Alignment:** Fully adhere to skills:
  * **`vram-safe-embedding`** ([.agents/skills/vram-safe-embedding/SKILL.md](file:///d:/UIT/TX/doan/.agents/skills/vram-safe-embedding/SKILL.md))
  * **`modular-code-architecture`** ([.agents/skills/modular-code-architecture/SKILL.md](file:///d:/UIT/TX/doan/.agents/skills/modular-code-architecture/SKILL.md))
  * **`fault-tolerant-checkpointing`** ([.agents/skills/fault-tolerant-checkpointing/SKILL.md](file:///d:/UIT/TX/doan/.agents/skills/fault-tolerant-checkpointing/SKILL.md))

---

## 2. Implementation Steps (How)

### Step 2C.1: Model Configuration & Cache Centralization
* Set `visual_model.primary_model: "google/siglip2-base-patch16-256"` and `batch_size: 16` in [configs/default_config.yaml](file:///d:/UIT/TX/doan/configs/default_config.yaml). Remove so400m references.
* Ensure `paths.models_dir: "models"` points to the D: drive directory.
* Set `os.environ["HF_HOME"] = os.path.abspath(models_dir)` and pass `cache_dir=models_dir` when loading `AutoProcessor` and `AutoModel`.

### Step 2C.2: PyTorch DataLoader Implementation in VisualExtractor
* Implement `KeyframeDataset(torch.utils.data.Dataset)` in [src/extractors/visual.py](file:///d:/UIT/TX/doan/src/extractors/visual.py):
  * Lazy loading of image files via PIL (`Image.open(p).convert("RGB")`).
  * Robust fallback to blank black 256x256 image if a frame is unreadable.
* Implement `collate_fn` using `processor(images=..., return_tensors="pt")`.
* Configure `DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=num_workers, pin_memory=True)`:
  * Overlap CPU disk I/O and preprocessing with GPU forward passes.
  * Windows compatibility: ensure clean worker termination.
* Update `extract_image_embeddings` in [src/extractors/visual.py](file:///d:/UIT/TX/doan/src/extractors/visual.py) to consume the `DataLoader`.

### Step 2C.3: Single-Video Verification & Benchmarking
* Re-extract keyframes with `max_keyframes_per_shot: 3`:
  ```powershell
  uv run python -m src.extractors.run_keyframes --video-id L13_V001 --force
  ```
* Run visual feature extraction with SigLIP2-Base:
  ```powershell
  uv run python -m src.extractors.run_visual --video-id L13_V001 --force
  ```
* Record extraction time, Peak VRAM, and FPS (target: < 30 seconds for ~250 frames).

### Step 2C.4: Index Rebuild & Scientific Evaluation
* Rebuild FAISS visual index (768-dim) via:
  ```powershell
  uv run python -m src.indexers.build_indices --modality visual
  ```
* Evaluate retrieval metrics:
  ```powershell
  uv run python -m src.evaluation.evaluate --ground-truth data/ground_truth.json
  ```
* Record Recall@1, Recall@5, Recall@10, and MRR.

### Step 2C.5: Documentation & Guide Synchronization
* Update [docs/guides/visual-siglip-faiss.md](file:///d:/UIT/TX/doan/docs/guides/visual-siglip-faiss.md) with SigLIP2-Base specs (768-dim, batch size 16, performance metrics).
* Update [TRACKING.md](file:///d:/UIT/TX/doan/TRACKING.md).

---

## 3. Acceptance Criteria
1. `google/siglip2-base-patch16-256` operates as the primary visual model; no references or downloads of so400m.
2. Models are downloaded and cached exclusively in `models/` on drive D:.
3. Multithreaded PyTorch `DataLoader` runs without errors on Windows.
4. Total extraction runtime for `L13_V001` drops to < 30 seconds (down from ~330 seconds, > 10x speedup).
5. FAISS index rebuilt with 768-dim vectors; baseline evaluation completes successfully.
