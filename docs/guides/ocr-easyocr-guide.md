# User Guide: On-Screen Text Extraction with EasyOCR & SQLite FTS5 (Stage 4)

## 1. Feature Overview
* **What it does:** Extracts visible on-screen text (news banners, tickers, street signs, subtitles, logos, scores) appearing on video keyframes using Vietnamese EasyOCR. A lightweight morphological edge-density pre-filter screens frames in under 10ms to prune 70-80% of natural/action scenes without calling deep neural networks.
* **Why it matters:** Text channels provide precise, exact-match semantic cues for names, locations, prices, temperatures, and dates that visual embeddings (SigLIP2) cannot discern.
* **Architecture:**
  * **Engine:** [src/extractors/ocr.py](file:///d:/UIT/TX/doan/src/extractors/ocr.py) (`OCRExtractor`)
  * **CLI Runner:** [src/extractors/run_ocr.py](file:///d:/UIT/TX/doan/src/extractors/run_ocr.py)
  * **Centralized Storage:** Model weights (`craft_mlt_25k.pth`, `latin_g2.pth`) stored in [models/easyocr/](file:///d:/UIT/TX/doan/models/easyocr).
  * **Index & Database:** [src/indexers/metadata_db.py](file:///d:/UIT/TX/doan/src/indexers/metadata_db.py) (relational `ocr_records` + full-text search `ocr_fts` virtual table using `unicode61 remove_diacritics 2` with Vietnamese d-stroke folding).

---

## 2. Quick Start CLI

### Process a Single Video on GPU (Recommended for speed):
```powershell
uv run python -m src.extractors.run_ocr --video-id L13_V001 --gpu
```

### Process an Entire Video Directory on GPU:
```powershell
uv run python -m src.extractors.run_ocr --video-dir data/raw_videos --gpu
```

### Process on CPU (0MB GPU VRAM):
```powershell
uv run python -m src.extractors.run_ocr --video-id L13_V001 --cpu
```

### Force Overwrite Existing OCR Data:
```powershell
uv run python -m src.extractors.run_ocr --video-id L13_V001 --gpu --force
```

### Bypass Edge-Density Filter (Run on every keyframe):
```powershell
uv run python -m src.extractors.run_ocr --video-id L13_V001 --gpu --skip-filter
```

---

## 3. CLI Arguments Table

| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--video-id` | `str` | *None* | Target single video ID to process (mutually exclusive with `--video-dir`). |
| `--video-dir` | `str` | *None* | Path to folder of videos to batch process. |
| `--gpu` | `flag` | `False` | Run EasyOCR on GPU (CUDA) for 6-8x speedup (~275MB VRAM footprint). |
| `--cpu` | `flag` | `False` | Run EasyOCR strictly on CPU (0MB GPU VRAM). |
| `--config` | `str` | [configs/default_config.yaml](file:///d:/UIT/TX/doan/configs/default_config.yaml) | System configuration file. |
| `--force` | `flag` | `False` | Overwrite existing OCR records for the video. |
| `--skip-filter` | `flag` | `False` | Bypass morphological edge-density pre-filter and evaluate EasyOCR on every keyframe. |

---

## 4. Inputs & Outputs

### Inputs:
* **Keyframes:** Extracted JPEG keyframes from Stage 1 stored in [data/keyframes/](file:///d:/UIT/TX/doan/data/keyframes) (`<video_id>/*.jpg`).
* **Metadata Database:** Existing entries in `keyframes` table in [data/metadata.db](file:///d:/UIT/TX/doan/data/metadata.db).

### Outputs:
* **Relational Table (`ocr_records`):**
  * `ocr_id`: Composite unique ID (e.g. `L13_V001_00001_ocr_000`).
  * `video_id`, `keyframe_id`, `timestamp_sec`.
  * `text_detected`: Cleaned Vietnamese / alphanumeric text string.
  * `confidence`: Model confidence score (0.0 - 1.0).
  * `bbox_json`: JSON coordinates of the bounding polygon.
* **Virtual Full-Text Table (`ocr_fts`):**
  * Fast BM25 keyword matching with diacritic stripping and d-stroke folding (`đ`/`Đ` -> `d`/`D`).
  * Aggregates all bounding-box detections belonging to the same `keyframe_id` into a single unified keyframe document (`GROUP_CONCAT(text_detected, ' ')`) to support multi-line banner and signboard matching.
* **Checkpoint Status:** Marked `COMPLETED` for stage `ocr` in [pipeline_checkpoints](file:///d:/UIT/TX/doan/data/metadata.db).

---

## 5. Two-Stage Fault-Tolerant Hybrid Search

In real-world video competitions (e.g. VBS, AI Challenge) and video evaluation benchmarks, queries often specify exact on-screen banners (Text-in-Video Known-Item Search). When on-screen text suffers from slight OCR character recognition errors (e.g. `tô Irùng biển số` instead of `trùng biển số`, or `Quôc` instead of `Quốc`), standard BM25 with strict conjunction (`AND`) fails with 0 hits.

To resolve this, [MetadataDB.search_ocr()](file:///d:/UIT/TX/doan/src/indexers/metadata_db.py) employs a **Two-Stage Coarse-to-Fine Hybrid Search**:

```
[User Query: "trùng biển số"]
        │
        ▼ (Stage 1: Deep Coarse Retrieval via Keyframe-Aggregated SQLite FTS5)
[FTS5 Soft OR Query: "trung"* OR "bien"* OR "so"*]
        │
        ├─► Retrieves deep candidate pool (pool_limit >= 500) matching any query terms
        │
        ▼ (Stage 2: Fine-Grained Token-Level Fuzzy Rescoring via Python CPU)
[Token-Level SequenceMatcher & Vietnamese Diacritic Folding]
        │
        ├─► Folds query & candidate text to base Latin (fold_vietnamese())
        ├─► Computes word-by-word alignment similarity (difflib.SequenceMatcher)
        ├─► Adds substring / exact phrase inclusion bonus
        │
        ▼
[Final Score = 0.35 * Normalized_BM25 + 0.65 * Token_Fuzzy_Score]
        │
        ▼
=== TARGET IDENTIFIED: "tô Irùng biển số" shoots directly to Rank #1 ===
```

### Performance & Latency:
* **Latency:** ~2 to 4 milliseconds for reranking 50 candidates in Python.
* **Zero VRAM Footprint:** Executes entirely on CPU using Python standard library `difflib.SequenceMatcher` and `unicodedata`.
* **Zero Re-indexing Required:** Operates directly over existing SQLite FTS5 indices.

---

## 6. Hardware Constraints & Troubleshooting

* **Safe Execution on GPU or CPU:** EasyOCR supports execution on GPU (`--gpu`, ~275MB VRAM peak) for 6x faster batch extraction or strictly on CPU (`--cpu`, 0MB VRAM). Because visual extraction (SigLIP2) executes sequentially beforehand, running EasyOCR on GPU is 100% VRAM-safe.
* **Centralized Model Storage:** Weights are downloaded once into [models/easyocr/](file:///d:/UIT/TX/doan/models/easyocr) (`craft_mlt_25k.pth`, `latin_g2.pth`), avoiding redundant downloads or scattered caches in user home directories.
* **Pre-Filter Tuning:** Edge-density threshold defaults to `0.08` in [configs/default_config.yaml](file:///d:/UIT/TX/doan/configs/default_config.yaml). Lowering it includes more candidate keyframes; raising it increases speed.

