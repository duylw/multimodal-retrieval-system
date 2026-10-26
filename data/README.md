# Data Directory Guidelines & Specifications

## 1. Ground Truth Dataset (`ground_truth.json`)
* **Current Status:** `[TEMPLATE / SYNTHETIC MOCK]`
* **Disclaimer:**
  > [!IMPORTANT]
  > `data/ground_truth.json` is currently a **synthetic template schema** created to test data models, API contracts, evaluation scripts (`evaluate.py`), and CI/CD pipelines. It does **not** contain real ground-truth human annotations.
  > Running evaluation against this template is for baseline integration verification only and does not reflect actual retrieval quality or model capabilities.
* **Schema Contract:**
  Each evaluation item must adhere to:
  ```json
  {
    "query_id": "q01",
    "query": "cận cảnh đĩa thức ăn được bày biện trên bàn",
    "video_file": "L13_V001.mp4",
    "target_interval": [45.0, 75.0],
    "modality_expected": ["visual"],
    "description": "Visual query testing close-up shot of cooked food"
  }
  ```
* **Production Dataset Replacement:**
  Once actual graduation thesis annotated test datasets are finalized, replace this file with verified ground truth intervals.

---

## 2. Directory Layout & Persistence Rules

* `data/raw_videos/`: Contains original video files (`.mp4`). Ignored by Git.
* `data/keyframes/`: Output directory for extracted JPEG keyframes organized by video ID (`data/keyframes/{video_id}/`). Ignored by Git.
* `data/indices/`: FAISS index files (`.index`) and metadata mapping tables (`.json`). Ignored by Git.
* `data/metadata.db`: SQLite database storing shots, keyframe metadata, and pipeline checkpoints. Ignored by Git.
* `data/audio_temp/`: Temporary directory for extracted 16kHz WAV audio. Automatically deleted after Whisper transcription.
