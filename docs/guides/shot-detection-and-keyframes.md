# User Guide: Shot Detection & Adaptive Keyframe Extraction

## 1. Feature Overview
* **What it does:** Automatically segments long raw videos into coherent continuous camera takes (shots) using `ContentDetector`, then applies adaptive time-based sampling to extract sharp, representative keyframes while filtering out blurry, dark, and duplicate frames.
* **When to use:** Mandatory initial stage of the offline ingestion pipeline prior to visual embedding extraction with SigLIP2.
* **Value provided:**
  * Massive data compression: Condenses tens of thousands of raw frames down to hundreds of high-quality representative keyframes.
  * Quality filtering: Automatically discards camera-shake motion blur (Laplacian variance < 80.0), dark frames, and color-redundant frames within the same shot.
  * Persistence: Stores complete shot boundaries and keyframe metadata in SQLite `metadata.db` with checkpoint resume support.

---

## 2. Quick Start CLI

### Execute shot boundary detection (Stage 1):
```powershell
# Single video execution
uv run python -m src.extractors.run_shots --video-id L13_V001

# Batch directory execution
uv run python -m src.extractors.run_shots --video-dir data/raw_videos/

# Force re-execution (overwrites previous stage artifacts)
uv run python -m src.extractors.run_shots --video-id L13_V001 --force
```

### Execute adaptive keyframe extraction (Stage 2):
```powershell
# Single video execution (requires Stage 1 shots completed)
uv run python -m src.extractors.run_keyframes --video-id L13_V001

# Batch directory execution
uv run python -m src.extractors.run_keyframes --video-dir data/raw_videos/

# Force re-extraction
uv run python -m src.extractors.run_keyframes --video-id L13_V001 --force
```

---

## 3. Configuration Parameters

Configured via [configs/default_config.yaml](file:///d:/UIT/TX/doan/configs/default_config.yaml):

| Parameter Name | Config Key | Data Type | Default Value | Description |
|---|---|---|---|---|
| `threshold` | `shot_detection.threshold` | `float` | `27.0` | Content change sensitivity threshold between consecutive frames |
| `min_scene_len` | `shot_detection.min_scene_len` | `int` | `15` | Minimum shot frame count (prevents fragmented cuts under 0.6s) |
| `frame_skip` | `shot_detection.frame_skip` | `int` | `1` | Frame skipping factor during detection (auto-scaled by FPS) |
| `blur_threshold` | `keyframes.blur_threshold` | `float` | `80.0` | Minimum Laplacian variance; lower values are filtered as blurry |
| `min_brightness` | `keyframes.min_brightness` | `float` | `15.0` | Minimum mean grayscale brightness (0-255); lower values filtered as dark |
| `similarity_thresh` | `keyframes.similarity_thresh` | `float` | `0.95` | HSV color histogram correlation threshold; higher values filtered as duplicate |

---

## 4. Inputs & Outputs

* **Inputs:**
  * Source video: [data/raw_videos/{video_id}.mp4](file:///d:/UIT/TX/doan/data/raw_videos)
* **Outputs:**
  * Metadata Database: [data/metadata.db](file:///d:/UIT/TX/doan/data/metadata.db) (populates `videos`, `shots`, `keyframes`, `checkpoints` tables).
  * Extracted JPEG Keyframes: `data/keyframes/{video_id}/shot_{shot_id:04d}_t{timestamp:07.2f}.jpg`.

---

## 5. Technical Notes & Troubleshooting

* **Hardware Constraints:**
  * Runs entirely on CPU with OpenCV decoding, consuming **0MB GPU VRAM**. Throughput reaches ~470 FPS on standard multi-core CPUs.
* **Resume Capability:**
  * If a video was previously processed, the extractor queries SQLite and returns in `0.002s` without re-processing.
  * To force re-extraction: Clear the corresponding checkpoint row in `checkpoints` table or delete `data/metadata.db`.
