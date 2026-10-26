# Task 07: Non-Speech Ambient Audio Events with CLAP (Phase 2 Reserve)

## 1. Objectives (What)
* Add a non-speech **Audio Event Retrieval Channel** using **CLAP (Contrastive Language-Audio Pretraining)**.
* Capture acoustic events that speech ASR models (Whisper) completely miss: Emergency vehicle sirens, rain/thunder, audience applause, musical instruments, sizzling cooking oil, etc.
* Segment raw audio tracks into 10-second chunks with 5-second stride (50% temporal overlap) and extract normalized audio embeddings.
* Construct an independent FAISS index for audio events and integrate with the temporal sliding window fusion engine.

---

## 2. Implementation Steps (How)

### Step 2.1: Audio Segmentation & CLAP Embedding Extraction
1. **Model Initialization:**
   ```python
   from transformers import ClapModel, ClapProcessor
   model = ClapModel.from_pretrained("laion/larger_clap_general").to("cuda")
   processor = ClapProcessor.from_pretrained("laion/larger_clap_general")
   ```
2. **10-Second Sliding Window Audio Extraction:**
   * Window size 10s, step size 5s (50% overlap).
   * Extract 512-dimensional audio embeddings and apply L2 normalization.
3. **Metadata Storage:**
   * Populate SQLite `audio_segments`:
     `segment_id`, `video_id`, `start_sec`, `end_sec`, `audio_clap_faiss_id`.

### Step 2.2: FAISS Indexing & Multimodal Query Integration
* Build `faiss.IndexFlatIP(512)` saved to `data/indices/audio_clap.index`.
* Query handling: When queries contain acoustic sound descriptors (e.g. *"siren sound"*, *"heavy rain"*), translate/route directly to the CLAP text encoder.
* Temporal Fusion: Audio candidate chunks contribute weighted scores to overlapping temporal sliding windows in Task 05.

---

## 3. Verification & Acceptance Criteria
1. **Acoustic Discrimination Test:**
   * Extract two 10s chunks: one containing an ambulance siren, one containing normal dialogue.
   * Query: `"sound of ambulance siren"`.
   * Verify similarity score for the siren chunk distinctly outperforms the dialogue segment.
2. **Benchmark Evaluation Contribution:**
   * Evaluate acoustic subset queries in `data/ground_truth.json`.
   * Verify adding CLAP yields >= 40% improvement in `Recall@10` for acoustic-specific benchmark queries.
