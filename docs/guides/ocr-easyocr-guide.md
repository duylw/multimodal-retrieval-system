# User Guide: On-Screen Text Extraction with EasyOCR & SQLite FTS5 (Stage 4)

## 1. Feature Overview
* **What it does:** Extracts visible on-screen text (news banners, tickers, street signs, subtitles, logos, scores) appearing on video keyframes using Vietnamese EasyOCR. A lightweight morphological edge-density pre-filter screens frames in under 10ms to prune 70-80% of natural/action scenes without calling deep neural networks.
* **Why it matters:** Text channels provide precise, exact-match semantic cues for names, locations, prices, temperatures, and dates that visual embeddings (SigLIP2) cannot discern.
* **Architecture:**
  * **Engine:** [src/extractors/ocr.py](file:///d:/UIT/TX/doan/src/extractors/ocr.py) (`OCRExtractor`)
  * **CLI Runner:** [src/extractors/run_ocr.py](file:///d:/UIT/TX/doan/src/extractors/run_ocr.py)
  * **Centralized Storage:** Model weights (`craft_mlt_25k.pth`, `latin_g2.pth`) stored in `models/easyocr/`.
  * **Index & Database:** [src/indexers/metadata_db.py](file:///d:/UIT/TX/doan/src/indexers/metadata_db.py) (relational `ocr_records` + full-text search `ocr_fts` virtual table using `unicode61 remove_diacritics 2` with Vietnamese d-stroke folding).

---

## 2. Quick Start CLI

### Process a Single Video:
```powershell
uv run python -m src.extractors.run_ocr --video-id L13_V001
```

### Process an Entire Video Directory:
```powershell
uv run python -m src.extractors.run_ocr --video-dir data/raw_videos
```

### Force Overwrite Existing OCR Data:
```powershell
uv run python -m src.extractors.run_ocr --video-id L13_V001 --force
```

### Bypass Edge-Density Filter (Run on every keyframe):
```powershell
uv run python -m src.extractors.run_ocr --video-id L13_V001 --skip-filter
```

---

## 3. CLI Arguments Table

| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--video-id` | `str` | *None* | Target single video ID to process (mutually exclusive with `--video-dir`). |
| `--video-dir` | `str` | *None* | Path to folder of videos to batch process. |
| `--config` | `str` | `configs/default_config.yaml` | System configuration file. |
| `--force` | `flag` | `False` | Overwrite existing OCR records for the video. |
| `--skip-filter` | `flag` | `False` | Bypass morphological edge-density pre-filter and evaluate EasyOCR on every keyframe. |

---

## 4. Inputs & Outputs

### Inputs:
* **Keyframes:** Extracted JPEG keyframes from Stage 1 stored at `data/keyframes/<video_id>/*.jpg`.
* **Metadata Database:** Existing entries in `keyframes` table in `data/metadata.db`.

### Outputs:
* **Relational Table (`ocr_records`):**
  * `ocr_id`: Composite unique ID (e.g. `L13_V001_00001_ocr_000`).
  * `video_id`, `keyframe_id`, `timestamp_sec`.
  * `text_detected`: Cleaned Vietnamese / alphanumeric text string.
  * `confidence`: Model confidence score (0.0 - 1.0).
  * `bbox_json`: JSON coordinates of the bounding polygon.
* **Virtual Full-Text Table (`ocr_fts`):**
  * Fast BM25 keyword matching with diacritic stripping and d-stroke folding (`đ`/`Đ` -> `d`/`D`).
* **Checkpoint Status:** Marked `COMPLETED` for stage `ocr` in `pipeline_checkpoints`.

---

## 5. Hardware Constraints & Troubleshooting

* **Zero GPU VRAM Impact:** EasyOCR is explicitly configured with `use_gpu=False`. It executes purely on CPU threads without interfering with SigLIP2 visual embeddings on the NVIDIA GTX 1650.
* **Centralized Model Storage:** Weights are downloaded once into `models/easyocr/` (~95MB total), avoiding redundant downloads or scattered caches in user home directories.
* **Pre-Filter Tuning:** Edge-density threshold defaults to `0.08` in `configs/default_config.yaml`. Lowering it includes more candidate keyframes; raising it increases speed.

