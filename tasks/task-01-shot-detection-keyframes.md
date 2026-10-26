# Task 01: Shot Boundary Detection & Adaptive Keyframe Extraction

## 1. Objectives (What)
* Segment videos into continuous camera takes (shots) using `PySceneDetect` (or `TransNetV2`).
* **FPS Normalization:**
  * Support diverse input video frame rates (24, 25, 30, 50, 60 FPS).
  * Normalize scene detection to an effective 25 FPS scan rate via frame-skipping, cutting compute time on 60 FPS videos by 50% without loss of boundary accuracy.
* **Time-Based Adaptive Keyframe Selection:**
  * Sample candidate frames based strictly on actual shot duration in seconds, completely independent of native FPS.
  * Short shots (< 3.0s): Extract 1 frame at shot center (50% duration).
  * Medium shots (3.0s - 8.0s): Extract 2 frames at 33% and 66% duration.
  * Long shots (> 8.0s): Sample every 3.5 seconds (capped at 6 frames maximum).
  * Constrain overall keyframe volume across the entire 100GB repository to **60,000 - 80,000 images** to protect disk storage.
* **Frame Quality Filters:**
  * Filter dark frames (mean grayscale brightness < 15/255).
  * Filter motion blur (Laplacian variance < 80.0) with local search (+/- 0.2s) for sharper candidates.
  * Filter intra-shot color duplicates (HSV histogram correlation > 0.95).
* Store boundaries and keyframe metadata in SQLite [data/metadata.db](file:///d:/UIT/TX/doan/data/metadata.db).

---

## 2. Implementation Steps (How)

### Step 2.1: FPS Normalization and Video Decoding
1. **Time-Based Indexing Principle:**
   * Extract video metadata: `fps = cap.get(cv2.CAP_PROP_FPS)`.
   * Compute all timestamps in real seconds: `timestamp_sec = frame_idx / fps`.
   * Never use raw frame indices as search identifiers across heterogeneous video collections.
2. **Frame-Skipping for High FPS Videos:**
   * When `fps > 30` (e.g. 50 or 60 FPS):
     * Calculate stride: `stride = round(fps / 25.0)`.
     * Pass every `stride`-th frame to the detector.
     * Scale detected boundary timestamps back to exact seconds: `shot_start_sec = (sampled_idx * stride) / fps`.

### Step 2.2: Time-Interval Adaptive Keyframe Sampling
1. **Candidate Sampling by Real Duration (`duration_sec = end_sec - start_sec`):**
   * `duration_sec < 3.0s`: 1 frame at `start_sec + 0.5 * duration_sec`.
   * `3.0s <= duration_sec <= 8.0s`: 2 frames at `start_sec + 0.33 * duration` and `start_sec + 0.66 * duration`.
   * `duration_sec > 8.0s`: 1 frame every 3.5s (up to 6 frames max).
2. **Laplacian Blur Filtering:**
   * Compute variance: `cv2.Laplacian(gray_frame, cv2.CV_64F).var()`.
   * If variance < 80.0 -> Scan adjacent frames within +/- 0.2s to pick the sharpest alternative.
3. **Brightness & Dark Frame Filtering:**
   * Compute mean grayscale brightness. Discard frame if < 15/255.
4. **HSV Color Histogram Deduplication:**
   * Compute 3D HSV histogram and correlate across intra-shot frames. Retain unique frames with similarity <= 0.95.

### Step 2.3: Storage and Metadata Persistence
* Save keyframes as quality 85 JPEG images:
  `data/keyframes/{video_id}/shot_{shot_id:04d}_t{timestamp_sec:07.2f}.jpg`
* Populate SQLite tables in [data/metadata.db](file:///d:/UIT/TX/doan/data/metadata.db):
  * `shots`: `shot_id`, `video_id`, `start_frame`, `end_frame`, `start_sec`, `end_sec`, `duration_sec`, `fps`.
  * `keyframes`: `keyframe_id`, `video_id`, `shot_id`, `timestamp_sec`, `file_path`, `is_shot_center`, `blur_score`.
  * `checkpoints`: Track stage status `done` to guarantee resumption.

---

## 3. Verification & Acceptance Criteria
1. **Real-World Test on `L13_V001.mp4` (25 FPS, 28,347 frames):**
   * Scene detection achieves > 400 FPS throughput.
   * Produces 292 distinct shots and 344 sharp keyframes (~18.8MB total storage).
2. **Quality & Resume Verification:**
   * Inspect extracted keyframes: zero black or heavily blurred frames.
   * Second execution checks database checkpoints and resumes in < 0.01 seconds.
