# Task 04: On-Screen Text Extraction with EasyOCR on CPU

## 1. Objectives (What)
* Extract on-screen text appearing in video frames: News banners, tickers, street signboards, dish names, ingredient lists, sports scores, and subtitles.
* Implement a lightweight **Text Presence Pre-Filter** using morphological edge density to prune 70-80% of non-text keyframes before calling deep neural networks.
* Run **EasyOCR (Vietnamese)** purely on **CPU multi-processing** with centralized model storage in `models/easyocr/`, consuming **0MB GPU VRAM** and preserving the GTX 1650 for deep visual models (SigLIP2).
* Index extracted text and timestamps into SQLite FTS5 with accent and Vietnamese d-stroke folding for high-speed BM25 full-text search.

---

## 2. Implementation Steps (How)

### Step 2.1: Text Presence Pre-Filter (Morphological & Edge Density)
* Use spatial edge gradient analysis (Sobel / Canny) on grayscale keyframes:
  * Text regions exhibit localized clusters of high vertical edge density and variance.
  * If edge density in candidate text bands falls below threshold (`0.08`), flag keyframe as `no_text` and skip deep OCR.
  * In a full dataset of 100,000+ keyframes, this reduces OCR execution to approximately 20,000 - 30,000 text-rich frames, saving hours of computation.

### Step 2.2: Text Recognition with EasyOCR
1. **CPU Engine Initialization & Centralized Storage:**
   ```python
   import easyocr
   reader = easyocr.Reader(
       lang_list=['vi'],
       gpu=False,
       model_storage_directory="models/easyocr",
       download_enabled=True,
       verbose=False
   )
   ```
2. **Recognition & Post-Processing:**
   * Input: Keyframe JPEG image.
   * Confidence threshold: Retain detections with `confidence >= 0.60`.
   * Text normalization: Strip non-printable noise characters and collapse whitespace.
3. **Database Storage:**
   * Populate SQLite `ocr_records`:
     `ocr_id`, `video_id`, `keyframe_id`, `timestamp_sec`, `text_detected`, `bbox`, `confidence`.

### Step 2.3: Full-Text Search Indexing & Two-Stage Hybrid Retrieval
* Construct virtual table supporting unicode Vietnamese queries with accent and d-stroke folding:
  ```sql
  CREATE VIRTUAL TABLE IF NOT EXISTS ocr_fts USING fts5(
      ocr_id UNINDEXED,
      video_id UNINDEXED,
      keyframe_id UNINDEXED,
      timestamp_sec UNINDEXED,
      text_detected,
      tokenize = 'unicode61 remove_diacritics 2'
  );
  ```
* Queries fold `đ`/`Đ` to `d`/`D` and strip diacritics, matching unaccented, accented, uppercase, or lowercase text uniformly.
* **Two-Stage Hybrid Search Engine:**
  * **Stage 1 (Coarse Candidate Retrieval via SQLite FTS5 Soft OR):** Uses disjunctive `OR` wildcard matching (`"word1"* OR "word2"*`) to retrieve candidate keyframes (top 50-100) even when OCR mistranscribes individual words, preventing strict conjunction filtering failures.
  * **Stage 2 (Fine-Grained Token-Level Fuzzy Rescoring via Python):** Uses `difflib.SequenceMatcher` with Vietnamese diacritic folding (`fold_vietnamese()`) to compute word-by-word alignment similarities and substring bonuses.
  * **Final Score:** Blends BM25 term frequency with token-level character similarity:
    `Final_Score = 0.35 * Normalized_BM25 + 0.65 * Token_Fuzzy_Score`.
  * Guarantees high Recall and Precision on Known-Item Search (KIS) queries even under extreme OCR character confusion (e.g. `Irùng` vs `trùng`, `Quôc` vs `Quốc`, `lón` vs `lớn`).

---

## 3. Verification & Acceptance Criteria
1. **Unit Test on Benchmark Frame Set:**
   * Test across sample keyframes.
   * Verify pre-filter discards non-text frames in < 10ms.
   * Verify EasyOCR captures complex Vietnamese diacritics and tone marks accurately.
2. **CPU Throughput & VRAM Benchmark:**
   * 0MB GPU VRAM allocation.
3. **Retrieval Verification:**
   * Query news ticker phrases (e.g. `"nắng nóng"`, `"nhiệt độ"`, `"miền đông"`).
   * Confirm FTS5 returns exact timestamps where the text appears.

