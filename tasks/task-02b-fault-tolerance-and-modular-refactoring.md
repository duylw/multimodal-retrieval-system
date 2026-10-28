# Task 02B: Architecture Refactoring & Pipeline Fault-Tolerance Infrastructure

## 1. Objectives (What)
* Resolve architectural technical debt identified after Milestone 1 by applying the two standardized skills:
  * **`fault-tolerant-checkpointing`** ([.agents/skills/fault-tolerant-checkpointing/SKILL.md](file:///d:/UIT/TX/doan/.agents/skills/fault-tolerant-checkpointing/SKILL.md))
  * **`modular-code-architecture`** ([.agents/skills/modular-code-architecture/SKILL.md](file:///d:/UIT/TX/doan/.agents/skills/modular-code-architecture/SKILL.md))
* Establish persistent stage tracking in SQLite via the `pipeline_checkpoints` table.
* Decouple pure processing engines (Layer 2) from CLI runners (Layer 3) across existing extractors (`shots.py`, `keyframes.py`, `visual.py`).
* Decouple per-video feature extraction caching (`data/features/{modality}/{video_id}.npz`) from unified index construction (`src/indexers/build_indices.py`).
* Enforce pre-flight dependency guards, atomic failure rollbacks, idempotent resumption (`[SKIP]`), and corrupt file isolation across single-video and full dataset directory processing.
* Synchronize project tracking and feature documentation.

---

## 2. Implementation Steps (How)

### Step 2B.1: Database Checkpoint Tracking Schema
* Update [src/indexers/metadata_db.py](file:///d:/UIT/TX/doan/src/indexers/metadata_db.py) to manage the `pipeline_checkpoints` table:
  ```sql
  CREATE TABLE IF NOT EXISTS pipeline_checkpoints (
      video_id TEXT NOT NULL,
      stage_name TEXT NOT NULL,
      status TEXT NOT NULL,
      artifact_count INTEGER DEFAULT 0,
      error_message TEXT,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (video_id, stage_name),
      FOREIGN KEY (video_id) REFERENCES videos(video_id) ON DELETE CASCADE
  );
  ```
* Implement CRUD helper methods:
  * `set_checkpoint(video_id: str, stage_name: str, status: str, artifact_count: int = 0, error_msg: Optional[str] = None)`
  * `get_checkpoint(video_id: str, stage_name: str) -> Optional[Dict[str, Any]]`
  * `is_stage_completed(video_id: str, stage_name: str) -> bool`
  * `reset_stage(video_id: str, stage_name: str)`

### Step 2B.2: Layer 2 Engine Refactoring
* **`src/extractors/shots.py`**:
  * Strip top-level CLI argument parsing (`argparse`, `sys.argv`).
  * Preserve the pure `ShotDetector` class with clean method signatures returning `List[ShotBoundary]`.
* **`src/extractors/keyframes.py`**:
  * Strip top-level CLI argument parsing.
  * Preserve the pure `KeyframeExtractor` class with clean method signatures returning `List[KeyframeMetadata]`.
* **`src/extractors/visual.py`**:
  * Ensure `VisualExtractor` focuses solely on model lifecycle (`load_model`, `safe_unload`) and tensor extraction (`extract_keyframe_embeddings`, `extract_text_embedding`, `pool_shot_embeddings`).

### Step 2B.3: Layer 3 Runner Standardization
Create standardized CLI runners supporting `--video-id` and `--video-dir`, pre-flight dependency guards, atomic rollbacks, and batch progress summaries:
* **`src/extractors/run_shots.py`**: Standalone runner for shot boundary detection.
* **`src/extractors/run_keyframes.py`**: Standalone runner for keyframe extraction (validates shots exist).
* **`src/extractors/run_visual.py`**: Standalone runner for SigLIP2 feature extraction (validates keyframes exist; saves `.npz` feature cache).

### Step 2B.4: Decouple Feature Caching from Index Construction
* Refactor visual extraction runner to output per-video dense feature caches to `data/features/visual/{video_id}.npz`.
* Implement standalone index builder [src/indexers/build_indices.py](file:///d:/UIT/TX/doan/src/indexers/build_indices.py):
  * Accepts `--modality [visual|speech|ocr|all]` and `--output-dir`.
  * Scans all `.npz` caches, stacks dense vectors, and writes binary FAISS index and metadata JSON in a single atomic pass.

### Step 2B.5: Verification & Acceptance Criteria
1. **Single-Video Verification (`L13_V001`):**
   * Re-run `run_shots`, `run_keyframes`, `run_visual`, and `build_indices` on `L13_V001`.
   * Verify idempotency: running a second time outputs `[SKIP]` for all stages.
   * Verify `--force` successfully purges previous artifacts and re-executes cleanly.
2. **Directory Batch Verification:**
   * Test batch processing with `--video-dir data/raw_videos/`.
   * Verify corrupt file handling and summary report output (`Total / Completed / Skipped / Failed`).
3. **Rollback Verification:**
   * Trigger an intentional exception during keyframe extraction; verify that partial keyframe images are deleted and stage status is marked `FAILED`.

### Step 2B.6: Documentation & Tracking Updates
* Update [TRACKING.md](file:///d:/UIT/TX/doan/TRACKING.md) to record Task 02B.
* Update [docs/guides/shot-detection-and-keyframes.md](file:///d:/UIT/TX/doan/docs/guides/shot-detection-and-keyframes.md) and [docs/guides/visual-siglip-faiss.md](file:///d:/UIT/TX/doan/docs/guides/visual-siglip-faiss.md) with standardized runner commands.

