# User Guide: On-Screen Text Extraction with PaddleOCR & SQLite FTS5 (Stage 4)

## 1. Feature Overview
* **What it does:** Extracts visible on-screen text (news banners, tickers, street signs, subtitles, logos, scores) appearing on video keyframes using Vietnamese PaddleOCR. A lightweight morphological edge-density pre-filter screens frames in under 10ms to prune 70-80% of natural/action scenes without calling deep neural networks.
* **When to use:** Offline indexing phase (Stage 4), right after Keyframe Extraction (Stage 2) or alongside Visual Embedding (Stage 3).
* **Value provided:** Enables instant keyword-based full-text moment retrieval via SQLite FTS5 with BM25 ranking, running 100% on CPU (0MB GPU VRAM), preserving GPU resources for visual models.

---

## 2. Quick Start CLI

### Single Video Extraction
```powershell
uv run python -m src.extractors.run_ocr --video-id L13_V001
```

### Full Dataset Batch Processing
```powershell
uv run python -m src.extractors.run_ocr --video-dir data/raw_videos
```

### Force Overwrite / Re-extraction
```powershell
uv run python -m src.extractors.run_ocr --video-id L13_V001 --force
```

### Expected Console Output
```text
2026-10-29 23:40:38.380 | INFO     | src.extractors.ocr:extract_video:183 - [INFO] Running on-screen text extraction for 348 keyframes of 'L13_V001'...
2026-10-29 23:40:38.387 | INFO     | src.extractors.ocr:load_model:61 - [INFO] Initializing PaddleOCR (lang='vi', use_gpu=False, min_confidence=0.65)...
2026-10-29 23:40:39.805 | INFO     | src.extractors.ocr:load_model:71 - [OK] PaddleOCR engine initialized successfully on CPU.
2026-10-29 23:41:55.120 | INFO     | src.extractors.ocr:extract_video:201 - [OK] Completed OCR for 'L13_V001': 245 text items detected across 92/348 text-bearing keyframes.
2026-10-29 23:41:55.145 | INFO     | __main__:process_video:112 - [DONE] Saved 245 on-screen text records to SQLite FTS5 for 'L13_V001'.
```

---

## 3. CLI Arguments Table

| Argument | Type | Default | Description |
|---|---|---|---|
| `--video-id` | `str` | `None` | Process a single video by ID (e.g. `L13_V001`). Mutually exclusive with `--video-dir`. |
| `--video-dir` | `str` | `None` | Process all video files in the specified directory. Mutually exclusive with `--video-id`. |
| `--config` | `str` | `configs/default_config.yaml` | Path to system configuration file. |
| `--force` | `flag` | `False` | Force re-extraction and overwrite existing OCR database entries even if stage is marked `COMPLETED`. |
| `--skip-filter` | `flag` | `False` | Bypass morphological edge-density pre-filter and evaluate PaddleOCR on every single keyframe. |

---

## 4. Inputs & Outputs

### Inputs
* **Keyframe Images:** JPEG images located at [data/keyframes/{video_id}/](file:///d:/UIT/TX/doan/data/keyframes).
* **Keyframe Metadata:** Database records from the `keyframes` table in [data/metadata.db](file:///d:/UIT/TX/doan/data/metadata.db).

### Outputs
* **Relational Table (`ocr_records`):**
  * `ocr_id`: Primary key formatted as `{keyframe_id}_ocr_{idx:03d}`.
  * `video_id`, `keyframe_id`, `timestamp_sec`.
  * `text_detected`: Normalized text string.
  * `confidence`: Model confidence score (filtered by `>= 0.65`).
  * `bbox_json`: JSON serialized bounding polygon coordinates.
* **Full-Text Search Virtual Table (`ocr_fts`):**
  * SQLite FTS5 index tokenized with `unicode61` supporting exact phrases and token prefix queries.
* **Pipeline Checkpoint:**
  * Updated record in `pipeline_checkpoints` (`video_id`, `stage_name='ocr'`, `status='COMPLETED'`, `artifact_count`).

---

## 5. Hardware Constraints & Troubleshooting

* **Zero GPU VRAM Impact:** PaddleOCR is explicitly configured with `use_gpu=False`. It executes purely on CPU threads without interfering with SigLIP2 visual embeddings on the NVIDIA GTX 1650.
* **Pre-flight Dependency Guard:** If the `keyframes` stage has not completed for a video, the runner aborts with an error badge `[ERROR]` and marks the stage `FAILED` to prevent corrupt partial indexing.
* **Windows OpenMP Conflict Workaround:** On Windows, PyTorch and PaddlePaddle both bundle conflicting OpenMP runtime libraries. [src/extractors/ocr.py](file:///d:/UIT/TX/doan/src/extractors/ocr.py) automatically imports `torch` prior to `paddleocr` to enforce safe library loading and prevent `WinError 127` in `shm.dll`.
* **Idempotency & Resumption:** The batch runner automatically skips videos already completed in [data/metadata.db](file:///d:/UIT/TX/doan/data/metadata.db). If interrupted with `Ctrl + C`, `rollback_ocr()` automatically purges partial records for the active video.

