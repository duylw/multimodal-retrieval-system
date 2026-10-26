# Task 00: Environment Setup & Scientific Evaluation Harness

## 1. Objectives (What)
* Set up a Python 3.12 virtual environment with CUDA acceleration configured for an NVIDIA GeForce GTX 1650 (CUDA 12.1).
* Install base runtime libraries managed strictly through `uv` and `pyproject.toml`.
* Design a standardized Ground Truth Benchmark dataset (`data/ground_truth.json`) with multi-category queries and validated temporal boundaries (`video_id`, `start_sec`, `end_sec`).
* Implement an automated evaluation engine ([src/evaluation/evaluate.py](file:///d:/UIT/TX/doan/src/evaluation/evaluate.py)) computing Recall@1, Recall@5, Recall@10, and Mean Reciprocal Rank (MRR).

---

## 2. Implementation Steps (How)

### Step 2.1: Virtualenv Initialization and Package Management with `uv`
* Initialize virtual environment via `uv`:
  ```powershell
  uv venv
  .\.venv\Scripts\Activate.ps1
  ```
* Manage dependencies through `pyproject.toml`:
  * Install PyTorch with CUDA 12.1 support:
    ```powershell
    uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
    ```
  * Install core processing libraries:
    ```powershell
    uv add av opencv-python loguru pyyaml pydantic tqdm scenedetect
    ```
  * Verification command:
    ```powershell
    uv run python -c "import torch; print('[OK] CUDA:', torch.cuda.is_available(), '| GPU:', torch.cuda.get_device_name(0))"
    ```

### Step 2.2: Ground Truth Dataset Design (`data/ground_truth.json`)
* Construct representative benchmark queries across 4 distinct modality categories:
  * **Visual-dominant:** e.g., "close-up shot of beef stir-fry with bell peppers", "person wearing yellow shirt crossing intersection".
  * **Speech-dominant:** e.g., "anchor reading gold price market update", "chef reminding not to add too much salt".
  * **On-screen Text (OCR):** e.g., "restaurant menu price table", "football match score at corner of screen".
  * **Combined Multimodal:** e.g., "reporter holding microphone standing in front of municipal hall".
* JSON schema:
  ```json
  [
    {
      "query_id": "q01",
      "query": "instructions for marinating beef before stir-frying",
      "video_file": "L13_V001.mp4",
      "target_interval": [145.0, 180.0],
      "modality_expected": ["visual", "speech"]
    }
  ]
  ```

### Step 2.3: Evaluation Harness ([src/evaluation/evaluate.py](file:///d:/UIT/TX/doan/src/evaluation/evaluate.py))
* **Hit Condition Logic:** A prediction timestamp `t_pred` is scored as a Hit if:
  * Temporal tolerance: `t_pred >= (target_start - 5.0)` AND `t_pred <= (target_end + 5.0)`.
  * Or temporal IoU (Intersection over Union) >= 0.3.
* **Recall@K:** Percentage of queries with at least one Hit in the top K candidate moments.
* **MRR (Mean Reciprocal Rank):** Mean value of `1.0 / rank_first_hit` across all queries (0 if no hit occurs in the top results).

---

## 3. Verification & Acceptance Criteria
1. **GPU & CUDA Verification:**
   * Script outputs `True` and displays `NVIDIA GeForce GTX 1650`.
2. **Evaluation Harness Verification:**
   * Run automated tests with simulated dummy predictions:
     ```powershell
     uv run python src/evaluation/evaluate.py
     ```
   * Pass all mathematical assertions for Recall@1, Recall@5, Recall@10, and MRR.
