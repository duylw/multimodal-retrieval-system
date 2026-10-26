# Task 02: Visual SigLIP2 Feature Extraction & FAISS Indexing

## 1. Objectives (What)
* Convert extracted keyframe images into dense visual semantic embeddings using **SigLIP2** (`google/siglip2-so400m-patch14-384`, with fallback to `google/siglip2-base-patch16-256` if VRAM exceeds 3.2 GB).
* Compute **Shot-Level Average Embeddings (Mean Pooling)** to encapsulate the overall temporal and visual context of each camera take.
* Build high-speed nearest neighbor search indices using **FAISS** (`IndexFlatIP` - Inner Product over L2-normalized embeddings, mathematically identical to Cosine Similarity).
* Implement text-to-visual search capability supporting English and Vietnamese queries.

---

## 2. Implementation Steps (How)

### Step 2.1: VRAM Safety & Batch Inference Protocol
1. **Model Initialization (activate `vram-safe-embedding` skill):**
   * Load in `torch.float16` to minimize memory footprint:
     ```python
     from transformers import AutoModel, AutoProcessor
     model_name = "google/siglip2-so400m-patch14-384"  # Fallback: "google/siglip2-base-patch16-256"
     model = AutoModel.from_pretrained(model_name, torch_dtype=torch.float16).to("cuda")
     processor = AutoProcessor.from_pretrained(model_name)
     ```
2. **Safe Batching Rules:**
   * For SO400M: Configure `batch_size = 4` (or `8` if VRAM permits).
   * For Base: Configure `batch_size = 16` (or `32`).
   * Explicitly execute `gc.collect()` and `torch.cuda.empty_cache()` between video batches.
3. **L2 Normalization:**
   * Normalize every extracted vector: `vec = vec / np.linalg.norm(vec, axis=-1, keepdims=True)`.

### Step 2.2: Shot-Level Mean Pooling
* For shots containing multiple keyframes (2 to 6 keyframes):
  * Compute arithmetic mean of all keyframe vectors in the shot.
  * Re-apply L2 normalization to the pooled vector.
  * Index both individual keyframe vectors and shot-level pooled vectors to improve retrieval robustness for temporal action descriptions.

### Step 2.3: FAISS Index Construction
* Construct `faiss.IndexFlatIP(embedding_dim)`.
* Save index to disk: `data/indices/visual_siglip2.index`.
* Persist metadata mapping table (`faiss_visual_map` in SQLite or `id_map.json`):
  `faiss_id -> {video_id, shot_id, keyframe_id, timestamp_sec, is_shot_pooled}`.

---

## 3. Verification & Acceptance Criteria
1. **VRAM Footprint & Inference Speed Benchmark:**
   * Benchmark first 100 keyframes:
     * Peak VRAM must stay strictly below 3.2 GB on the GTX 1650.
     * Throughput: >= 4 keyframes/sec (SO400M) or >= 20 keyframes/sec (Base).
2. **Zero-Shot Semantic Search Test:**
   * Test sample queries:
     * Query: `"a close-up shot of chopping vegetables"`
     * Query: `"a vehicle turning at an intersection"`
   * Verify Top 5 retrieved keyframes match query semantics.
3. **Baseline Evaluation:**
   * Run [src/evaluation/evaluate.py](file:///d:/UIT/TX/doan/src/evaluation/evaluate.py) on visual-only retrieval to record baseline `Recall@10` and `MRR`.
