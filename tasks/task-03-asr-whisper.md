# Task 03: Speech Processing with faster-whisper & Hybrid Indexing (BM25 + Dense)

## 1. Objectives (What)
* Demux audio tracks from raw video to 16kHz mono WAV format.
* Apply **Silero-VAD** (Voice Activity Detection) to prune silent segments and background music, eliminating Whisper hallucinations.
* Transcribe Vietnamese speech with accurate start and end boundaries (`start_sec`, `end_sec`) using **faster-whisper** (`large-v3-turbo` with `int8` quantization on GPU).
* Construct a **Hybrid Search Index**:
  * **Lexical Index:** SQLite FTS5 / BM25 for exact keyword matches.
  * **Dense Semantic Index:** `bge-m3` multilingual embeddings (1024-d) to handle semantic synonyms and paraphrases.
* Automatically delete temporary WAV files after processing to conserve disk storage.

---

## 2. Implementation Steps (How)

### Step 2.1: Audio Extraction & Silero-VAD Pre-Filtering
1. **Audio Extraction via PyAV:**
   * Extract 16kHz mono PCM stream directly to disk or memory buffer:
     `ffmpeg -i input.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 temp.wav`
2. **Speech Segmentation via Silero-VAD:**
   * Filter non-speech intervals to avoid passing silence to Whisper, accelerating processing by 30-50%.

### Step 2.2: Transcription with faster-whisper
1. **Model Initialization:**
   ```python
   from faster_whisper import WhisperModel
   model = WhisperModel("large-v3-turbo", device="cuda", compute_type="int8")
   ```
2. **Transcription Parameters:**
   * Language set to Vietnamese: `language="vi"`.
   * Extract timestamped segments: `[{start: 12.4, end: 16.8, text: "..."}]`.
3. **Database Persistence:**
   * Populate SQLite `transcripts` table: `segment_id`, `video_id`, `start_sec`, `end_sec`, `text_raw`, `text_normalized`.
4. **Immediate Cleanup:**
   * Call `os.remove("temp.wav")` immediately after persistence to enforce disk quotas.

### Step 2.3: Hybrid Index Construction
1. **Lexical Index (SQLite FTS5):**
   * Create full-text search virtual table `transcripts_fts` using `unicode61` tokenizer supporting diacritics.
2. **Dense Index (`bge-m3`):**
   * Generate 1024-dimensional embeddings using `BAAI/bge-m3`.
   * Store embeddings in FAISS index: `data/indices/asr_bge_m3.index`.

---

## 3. Verification & Acceptance Criteria
1. **Transcription Accuracy & Temporal Sync:**
   * Test on a sample video (3-5 minutes of speech).
   * Verify temporary WAV file is purged.
   * Verify Vietnamese diacritics and text quality.
   * Verify timestamp discrepancy between real video speech and `[start_sec, end_sec]` is under 1.0 second.
2. **Hybrid Retrieval Verification:**
   * Exact keyword query: `"weekend promotion"` -> BM25 hits exact spoken phrase.
   * Paraphrase query: `"seasoning guide"` -> `bge-m3` retrieves segment containing *"instructions for marinating meat"*.
