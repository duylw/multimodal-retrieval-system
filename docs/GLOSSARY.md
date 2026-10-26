# Technical Glossary & Conceptual Guide

This document provides in-depth explanations of the core technical concepts, algorithms, and AI model mechanisms employed throughout the **Multimodal Video Moment Retrieval** system.

---

## 1. Video Processing Concepts

### 1.1. Frame
* **Definition:** A video is fundamentally a sequence of static raster images displayed rapidly at a constant frame rate (typically 24, 25, 30, or 60 Frames Per Second - FPS). Each static image is referred to as a **Frame**.
* **Significance:** A 1-hour video at 30 FPS contains approximately 108,000 frames. Feeding every raw frame into deep neural networks causes severe hardware bottlenecks and memory exhaustion; selective extraction is mandatory.

### 1.2. Shot
* **Definition:** A **Shot** is an uninterrupted sequence of frames captured by a single continuous camera take from start to stop (or until a viewpoint transition).
* **Shot vs Scene Distinction:**
  * *Shot:* A camera angle cut from an interviewer to an interviewee represents two distinct shots.
  * *Scene:* The entire dialogue occurring within that physical room constitutes a single scene (comprising multiple shots).
* **Hard Cut Transition:** An instantaneous switch in viewpoint from one frame to the next.
* **Dissolve / Fade Transition:** Gradual transitions where outgoing frames fade out while incoming frames fade in over a span of 5 to 15 frames.

### 1.3. Keyframe
* **Definition:** A representative frame selected to encapsulate the visual semantics of an entire shot.
* **Why Uniform Sampling (e.g. "1 frame every 3s") is Inefficient:**
  * In static shots (e.g., a person reading a book for 30s), extracting 10 frames produces 9 redundant duplicates.
  * In rapid action shots (e.g., a 3-second car collision), a single fixed frame may miss the critical impact moment.
  * Therefore, the system utilizes **Adaptive Time-Interval Keyframe Selection**: static shots yield 1 central frame, whereas dynamic, longer shots yield 2 to 6 keyframes.

### 1.4. Laplacian Blur Detection
* **Definition:** The Laplacian operator is a 2D second-order spatial derivative used to measure rapid intensity changes across an image.
* **Mechanism:** Sharp images contain crisp edges, generating a high Laplacian variance (`cv2.Laplacian(gray, cv2.CV_64F).var()`). Blurry frames resulting from camera shake or rapid motion lack defined high frequencies and yield low variance values (< 80.0), allowing defective frames to be filtered out before embedding extraction.

---

## 2. AI Models & Execution Mechanics

### 2.1. Shot Boundary Detection (PySceneDetect / TransNetV2)
* **Objective:** Detect precise start and end boundaries for every shot across raw video streams.
* **Mechanism:**
  * Avoids naive pixel-by-pixel comparisons which are easily fooled by camera pans or flashing lighting.
  * Utilizes content-aware frame difference metrics or 3D Spatio-Temporal Convolutional Networks (3D CNNs) analyzing sliding frame buffers to classify cut transitions and dissolve fades accurately.

### 2.2. SigLIP2 (Vision-Language Foundation Model)
* **Definition:** SigLIP2 (Sigmoid Loss for Language-Image Pre-training version 2) developed by Google is an advanced architectural evolution of OpenAI's CLIP.
* **Objective:** Projects raw keyframe images and natural language text queries into a **Shared Multimodal Embedding Space**.
* **Mechanism:**
  * Dual-encoder architecture: Vision Transformer (ViT) and Text Transformer.
  * The vision branch partitions 384x384 images into discrete patches, processing them as a sequence of visual tokens to produce normalized embeddings (e.g., 1152 dimensions).
  * **Sigmoid Contrastive Loss:** Unlike CLIP's Softmax loss (which requires batch-wide normalization, sensitive to batch sizes and VRAM-heavy), SigLIP2 evaluates pairwise image-text logits independently via Sigmoid loss, improving fine-grained zero-shot classification while conserving GPU memory.
* **Matching Principle:** Semantically aligned image-text pairs yield acute angular proximity in vector space (Cosine similarity approaching 1.0).

### 2.3. faster-whisper & Silero-VAD (Speech Channel)
* **Whisper (OpenAI):** Encoder-Decoder Sequence-to-Sequence Transformer trained on over 680,000 hours of multilingual audio to generate timestamped transcriptions.
* **faster-whisper:** CTranslate2 reimplementation utilizing 8-bit integer quantization (int8), delivering 4x faster inference speed and reducing VRAM footprint from ~4GB down to 1.5GB.
* **Silero-VAD (Voice Activity Detection):**
  * Ultra-lightweight speech presence classifier separating human voice from silence, wind, or ambient noise.
  * Prevents Whisper hallucinations on non-speech audio segments where silent chunks often prompt spurious repetitive phrases.

### 2.4. PaddleOCR (On-Screen Text Channel)
* **Objective:** Detects and transcribes on-screen text (news tickers, signboards, presentation slides, titles) supporting full Vietnamese diacritics.
* **Two-Stage Pipeline:**
  1. *Text Detection (DBNet):* Locates text regions and produces bounding polygons.
  2. *Text Recognition (SVTR / CRNN):* Crops bounding regions and decodes character sequences.
* **CPU Multiprocessing:** Executed entirely on CPU with multi-core parallelism, reserving 100% of GPU VRAM for SigLIP2 and Whisper.

### 2.5. bge-m3 (Dense Text Embedding)
* **Definition:** BAAI General Embedding Multi-lingual, Multi-functionality, Multi-granularity.
* **Objective:** Encodes Vietnamese sentences into 1024-dimensional semantic dense vectors.
* **Difference from Lexical Search:** Captures semantic synonymy where lexical keywords differ (e.g., equating "automobile" with "car", or "discount" with "sale").

### 2.6. CLAP (Non-Speech Ambient Audio Channel)
* **Definition:** Contrastive Language-Audio Pretraining.
* **Mechanism:** Converts 10-second audio waveforms into log-mel spectrograms, encoding them via an Audio Transformer into vector space to recognize environmental sounds that speech models cannot detect (e.g., explosions, sirens, applause, rainfall).

---

## 3. Information Retrieval Concepts

### 3.1. Vector Embeddings
* **Definition:** High-dimensional arrays of floating-point numbers (e.g., 768, 1024, or 1152 dimensions) representing abstract semantic representations of multimodal artifacts.
* **Spatial Geometry:** Semantically similar entities cluster together closely within this geometric manifold.

### 3.2. L2 Normalization
* **Definition:** Scaling each vector component by its Euclidean norm (`norm = sqrt(sum(x_i^2))`), constraining its magnitude to exactly 1.0.
* **Significance:** For L2-normalized vectors, the Inner Product directly equals the Cosine Similarity, enabling FAISS to compute nearest-neighbor searches via accelerated matrix multiplications.

### 3.3. FAISS (Facebook AI Similarity Search)
* **Definition:** Meta AI's high-performance library for k-Nearest Neighbor (kNN) similarity search over dense vector collections.
* **`IndexFlatIP`:** Exact, uncompressed Inner Product index ensuring 100% search precision without lossy quantization artifacts, ideally scaled for 50,000 to 200,000 keyframes.

### 3.4. Lexical vs Dense vs Hybrid Search
* **Lexical Search (BM25 / SQLite FTS5):** Exact token matching scoring documents by Term Frequency (TF) and Inverse Document Frequency (IDF). Highly robust for proper nouns, serial numbers, and specialized acronyms.
* **Dense Search (bge-m3 / FAISS):** Continuous vector distance matching capable of generalizing across synonyms and paraphrases.
* **Hybrid Search:** Fuses lexical and dense retrieval channels to achieve optimal recall and precision.

### 3.5. Reciprocal Rank Fusion (RRF)
* **Score Disparity Problem:** Cosine similarities range between [0, 0.4], while BM25 scores span [0, 30]. Direct summation causes lexical scores to dominate multimodal signals.
* **RRF Solution:** Aggregates results based on reciprocal rank positions across individual ranked lists:
  `RRF_Score = sum(weight_c / (60 + rank_c))`
  Ensures balanced, robust multimodal ranking without delicate score normalization tuning.

### 3.6. Temporal Sliding Window
* **Boundary Cut Issue:** Segmenting videos into fixed, disjoint 5-second blocks (`[0-5s]`, `[5-10s]`) fragments actions spanning across borders (e.g., seconds 4 to 7), penalizing both candidate segments.
* **Sliding Window Mechanism:** Windows of length 5s shift with a 50% overlap (2.5s stride):
  * Window 1: `[0.0 - 5.0s]`
  * Window 2: `[2.5 - 7.5s]` (completely covers the event from second 4 to 7)
  * Window 3: `[5.0 - 10.0s]`

### 3.7. Temporal Non-Maximum Suppression (NMS)
* **Objective:** Adjacent sliding windows overlapping a relevant event frequently return redundant hits. Temporal NMS clusters overlapping temporal candidates, suppresses lower-scoring windows within the temporal radius, and retains the single most representative moment boundary.

### 3.8. Interactive Relevance Feedback (Rocchio Algorithm)
* **Objective:** Enables users to refine search results in real time with a single click.
* **Mechanism:**
  * Clicking *"Relevant"* adds the candidate keyframe vector (positive centroid) to the query representation.
  * Clicking *"Irrelevant"* subtracts the negative vector component.
  * FAISS re-queries the updated query vector instantly without requiring manual text modification.

---

## 4. Scientific Evaluation Metrics

### 4.1. Recall@K
* **Definition:** Proportion of queries where the ground truth moment is successfully retrieved within the top K candidates:
  `Recall@K = (Number of Successful Hits in Top K) / (Total Number of Benchmark Queries)`
* System evaluations report `Recall@1`, `Recall@5`, and `Recall@10`.

### 4.2. Mean Reciprocal Rank (MRR)
* **Definition:** Average of reciprocal ranks of the first correct hit across all evaluated queries:
  `MRR = (1 / |Q|) * sum(1 / rank_i)`

### 4.3. Hit Condition
* A candidate moment at `T_pred` is scored as a **Hit** if:
  `T_pred` falls within `[T_start - 5.0s, T_end + 5.0s]`.
* Or if the temporal Intersection over Union (IoU) satisfies:
  `IoU = Intersection(T_pred, T_true) / Union(T_pred, T_true) >= 0.3`.

### 4.4. Ablation Study
* **Definition:** Controlled experimental methodology sequentially isolating or adding system channels to empirically prove their statistical contribution.

---

## 5. Hardware & Systems Engineering Terms

* **VRAM (Video RAM):** High-bandwidth memory on the discrete graphics card. The GTX 1650 provides 4096 MiB VRAM; model weights and frame tensors must fit comfortably within this ceiling.
* **OOM (Out Of Memory):** CUDA runtime crash triggered when tensor allocations exceed available physical VRAM.
* **FP16 / INT8 / FP32 (Numerical Precision):**
  * `FP32 (Single Precision):` 4 bytes per float.
  * `FP16 (Half Precision):` 2 bytes per float. Halves VRAM usage with negligible inference accuracy degradation.
  * `INT8 (Integer Quantization):` 1 byte per weight. Shrinks memory footprint by 75% for faster-whisper.
* **NVDEC (NVIDIA Video Decoder):** Dedicated hardware ASIC core on NVIDIA GPUs providing accelerated video decoding without utilizing CUDA compute cores.
* **Checkpoint & Resume:** State persistence recorded into SQLite after each video completes a pipeline stage, ensuring processing can resume seamlessly following unexpected interruptions.
