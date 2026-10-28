---
name: fault-tolerant-checkpointing
description: >-
  Use this skill whenever implementing, modifying, or running offline extraction pipelines, data
  processors, batch video jobs, and indexing tasks. Enforces pre-flight dependency guards, atomic
  stage execution, automatic failure rollback, idempotent resumption, resource cleanup, and corrupt
  file isolation across single-video and full dataset directory processing.
---

# Fault-Tolerant Checkpointing & Pipeline Resilience Runbook

This skill establishes strict engineering standards for data integrity, error resilience, and crash recovery across all extraction and indexing pipelines in the **Multimodal Video Moment Retrieval** system.

---

## 1. Core Engineering Principles

1. **Atomic Stage Execution:**
   * A processing stage for any given video must either complete 100% successfully or roll back completely.
   * Never leave partial, corrupted artifacts (e.g. half-written keyframe images, truncated `.npz` feature arrays, dangling SQLite rows) on disk or in the database.
2. **Pre-Flight Dependency Guard:**
   * Before executing Stage $N$, always verify that Stage $N-1$ has completed successfully for that video.
   * If prerequisites are missing, exit gracefully with clear guidance rather than crashing with unhandled tracebacks.
3. **Idempotent Resumption:**
   * Re-running any pipeline stage over a video or dataset folder must skip already completed items (`[SKIP]`) by default.
   * Provide a `--force` flag to explicitly purge existing stage artifacts and re-run when requested.
4. **Failure Isolation in Batch Runs:**
   * When processing an entire dataset directory, a corrupt or invalid video file must never crash the entire batch.
   * Catch errors per video, roll back the failed item's partial data, record `FAILED` status in SQLite, log `[ERROR]`, and proceed to the next video.
5. **Resource Safeguard in `finally` Blocks:**
   * Ephemeral intermediate files (e.g. extracted 16kHz WAV audio) must be deleted immediately after their consuming step completes.
   * GPU VRAM must be explicitly released (`safe_unload()`, `torch.cuda.empty_cache()`, `gc.collect()`) upon completion or failure.

---

## 2. Stage Dependency Hierarchy

Every stage must validate its explicit predecessor before beginning work:

```
[Raw Video: data/raw_videos/{video_id}.mp4]
   │
   ▼ Stage 1: Shot Boundary Detection (src/extractors/shots.py)
   ├── Pre-flight: File exists, readable, valid duration (> 0s)
   └── Artifacts:  SQLite `shots` table entries
   │
   ▼ Stage 2: Keyframe Extraction (src/extractors/keyframes.py)
   ├── Pre-flight: Stage 1 `shots` exists in SQLite for {video_id}
   └── Artifacts:  JPEG files in `data/keyframes/{video_id}/`, SQLite `keyframes` table
   │
   ├───────────────────────────────┬───────────────────────────────┐
   ▼ Stage 3A: Visual SigLIP2      ▼ Stage 3B: Whisper ASR         ▼ Stage 3C: PaddleOCR
   ├── Pre-flight: Keyframes exist ├── Pre-flight: Raw video exists├── Pre-flight: Keyframes exist
   └── Artifacts:                  └── Artifacts:                  └── Artifacts:
       `data/features/visual/`         SQLite `transcripts` table      SQLite `ocr_texts` table
       `{video_id}.npz` cache          (Ephemeral WAV deleted)         (FTS5 searchable)
   │                               │                               │
   └───────────────────────────────┴───────────────────────────────┘
                                   │
                                   ▼ Stage 4: Unified Indexing (src/indexers/build_indices.py)
                                   ├── Pre-flight: Validates feature caches & transcripts exist
                                   └── Artifacts:  `visual_siglip2.index`, `asr.index`, `ocr.index`
```

---

## 3. Database Checkpoint Tracking Schema

The SQLite database at [data/metadata.db](file:///d:/UIT/TX/doan/data/metadata.db) tracks execution state per video and stage:

```sql
CREATE TABLE IF NOT EXISTS pipeline_checkpoints (
    video_id TEXT NOT NULL,
    stage_name TEXT NOT NULL,         -- 'shots', 'keyframes', 'visual', 'speech', 'ocr'
    status TEXT NOT NULL,             -- 'PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED'
    artifact_count INTEGER DEFAULT 0, -- number of shots, frames, segments, or words
    error_message TEXT,               -- NULL if successful, error message if failed
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (video_id, stage_name),
    FOREIGN KEY (video_id) REFERENCES videos(video_id) ON DELETE CASCADE
);
```

### Stage Status Flow:
1. When starting: Set `status = 'IN_PROGRESS'`, `error_message = NULL`.
2. On clean finish: Set `status = 'COMPLETED'`, `artifact_count = count`, `updated_at = CURRENT_TIMESTAMP`.
3. On exception / interruption: Trigger rollback handler, set `status = 'FAILED'`, `error_message = str(e)`.

---

## 4. Failure Rollback Handlers

Each stage must implement a dedicated rollback function to purge partial artifacts:

| Stage Name | Clean-up Actions on Failure |
|---|---|
| `shots` | `DELETE FROM shots WHERE video_id = ?;` |
| `keyframes` | Delete all files in `data/keyframes/{video_id}/`; `DELETE FROM keyframes WHERE video_id = ?;` |
| `visual` | Delete incomplete `data/features/visual/{video_id}.npz` cache file if present. |
| `speech` | Delete temporary `data/audio_temp/{video_id}_16k.wav`; `DELETE FROM transcripts WHERE video_id = ?;` |
| `ocr` | `DELETE FROM ocr_texts WHERE video_id = ?;` |

---

## 5. Dataset Directory Processing Patterns

When processing an entire folder (e.g. `data/raw_videos/*.mp4`), follow this standardized execution structure:

```python
# Standardized Batch Loop Pattern with Fault Tolerance
def run_stage_on_directory(stage_name: str, video_dir: Path, force: bool = False) -> Dict[str, int]:
    summary = {"total": 0, "completed": 0, "skipped": 0, "failed": 0}
    video_files = sorted([f for f in video_dir.iterdir() if f.suffix.lower() in [".mp4", ".mkv", ".avi"]])
    summary["total"] = len(video_files)

    for vid_path in video_files:
        video_id = vid_path.stem
        
        # 1. Idempotency Check
        if not force and is_stage_completed(video_id, stage_name):
            logger.info(f"[SKIP] {stage_name} already COMPLETED for {video_id}")
            summary["skipped"] += 1
            continue

        # 2. Pre-flight Dependency Guard
        if not check_prerequisites(video_id, stage_name):
            logger.error(f"[ERROR] Prerequisites not met for {video_id}. Skipping.")
            summary["failed"] += 1
            continue

        # 3. Isolated Execution & Rollback Guard
        set_checkpoint(video_id, stage_name, "IN_PROGRESS")
        try:
            artifact_count = execute_stage(video_id, vid_path)
            set_checkpoint(video_id, stage_name, "COMPLETED", artifact_count=artifact_count)
            logger.info(f"[DONE] {stage_name} finished for {video_id} ({artifact_count} items)")
            summary["completed"] += 1
        except Exception as e:
            logger.error(f"[ERROR] Failed {stage_name} on {video_id}: {e}")
            rollback_stage(video_id, stage_name)
            set_checkpoint(video_id, stage_name, "FAILED", error_msg=str(e))
            summary["failed"] += 1
        finally:
            # 4. Mandatory Hardware & Resource Cleanup per item
            cleanup_ephemeral_resources(video_id)

    # 5. Batch Summary Report
    logger.info(
        f"[SUMMARY] {stage_name} Batch Finished | "
        f"Total: {summary['total']} | Completed: {summary['completed']} | "
        f"Skipped: {summary['skipped']} | Failed: {summary['failed']}"
    )
    return summary
```

---

## 6. Edge Cases & Safeguards

### A. Corrupt or 0-Byte Video File
* Validation: Check `file_size > 1024` bytes and `cv2.VideoCapture.isOpened()` before decoding.
* Action: Mark `FAILED`, log warning, skip to next video without raising an unhandled exception.

### B. Zero-Modality Fallback (Silent Audio or Textless Frames)
* Video with no speech: Whisper returns 0 segments.
  * Correct Behavior: Do NOT fail. Record `COMPLETED` with `artifact_count = 0`.
* Video with no text: PaddleOCR returns 0 text lines.
  * Correct Behavior: Do NOT fail. Record `COMPLETED` with `artifact_count = 0`.

### C. CUDA Out-Of-Memory (OOM) Recovery
* Wrap GPU inference in `try ... except torch.cuda.OutOfMemoryError:`.
* Action: Immediately call `torch.cuda.empty_cache()` and `gc.collect()`.
* If batch size was $> 1$, halve the batch size (`batch_size //= 2`) and retry the video once before failing.

### D. Interrupted Run (`Ctrl+C` / SIGINT)
* Register a signal handler or catch `KeyboardInterrupt`.
* Action: Trigger `rollback_stage(current_video_id, stage_name)` before exiting cleanly so the database is never left in an inconsistent `IN_PROGRESS` state.

