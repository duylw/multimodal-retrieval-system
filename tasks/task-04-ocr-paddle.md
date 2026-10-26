# Task 04: On-Screen Text Extraction with PaddleOCR on CPU

## 1. Objectives (What)
* Extract on-screen text appearing in video frames: News banners, tickers, street signboards, dish names, ingredient lists, sports scores, etc.
* Implement a lightweight **Text Presence Pre-Filter** to prune 70-80% of non-text keyframes before calling OCR models.
* Run **PaddleOCR (Vietnamese)** purely on **CPU multi-processing**, consuming **0MB GPU VRAM** and preserving the GTX 1650 for deep visual and speech models.
* Index extracted text and timestamps into SQLite FTS5 for high-speed full-text search.

---

## 2. Implementation Steps (How)

### Step 2.1: Text Presence Pre-Filter (Morphological & Edge Density)
* Use spatial edge gradient analysis (Sobel / Canny) on grayscale keyframes:
  * Text regions exhibit localized clusters of high vertical edge density and variance.
  * If edge density in candidate text bands falls below threshold, flag keyframe as `no_text` and skip PaddleOCR.
  * In a repository of 80,000 keyframes, this reduces OCR execution to approximately 15,000 - 25,000 text-rich frames.

### Step 2.2: Text Recognition with PaddleOCR
1. **CPU Engine Initialization:**
   ```python
   from paddleocr import PaddleOCR
   ocr_engine = PaddleOCR(use_angle_cls=True, lang='vi', use_gpu=False, show_log=False)
   ```
2. **Recognition & Post-Processing:**
   * Input: Keyframe JPEG image.
   * Confidence threshold: Retain detections with `confidence >= 0.65`.
   * Text normalization: Strip non-printable noise characters and normalize Vietnamese diacritics.
3. **Database Storage:**
   * Populate SQLite `ocr_records`:
     `ocr_id`, `video_id`, `keyframe_id`, `timestamp_sec`, `text_detected`, `bbox`, `confidence`.

### Step 2.3: Full-Text Search Indexing (SQLite FTS5)
* Construct virtual table supporting unicode Vietnamese queries:
  ```sql
  CREATE VIRTUAL TABLE IF NOT EXISTS ocr_fts USING fts5(
      video_id UNINDEXED,
      timestamp_sec UNINDEXED,
      text_detected,
      tokenize = 'unicode61'
  );
  ```
* Support prefix and fuzzy searches to account for minor character dropouts in OCR outputs.

---

## 3. Verification & Acceptance Criteria
1. **Unit Test on Benchmark Frame Set:**
   * Test across 10 sample frames (5 text-rich frames and 5 nature/action frames without text).
   * Verify pre-filter discards all 5 non-text frames in < 10ms.
   * Verify OCR accuracy achieves >= 85% word accuracy on text-bearing frames.
2. **CPU Throughput Benchmark:**
   * Processing latency < 150ms per text frame on CPU; < 10ms per non-text frame.
3. **Retrieval Verification:**
   * Query a specific menu price or street name visible only on-screen (unspoken in audio).
   * Confirm FTS5 returns exact timestamp where the text appears.
