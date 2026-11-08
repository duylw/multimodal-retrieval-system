# User Guide: KIS UI Controls, DRES Scoring Mechanics & Competition Strategy

## 1. Feature Overview
* **What it does:** Provides a comprehensive human-in-the-loop (HITL) web workstation ([src/ui/debug_server.py](file:///d:/UIT/TX/doan/src/ui/debug_server.py), [src/ui/static/index.html](file:///d:/UIT/TX/doan/src/ui/static/index.html), [src/ui/static/app.js](file:///d:/UIT/TX/doan/src/ui/static/app.js)) for Known-Item Search (KIS) interactive video retrieval, moment verification, frame-accurate boundary scrubbing, and real-time DRES competition submission.
* **When to use:** Used during live retrieval competitions (Video Browser Showdown - VBS, Lifelog Search Challenge - LSC, AI Challenge HCMC) and interactive thesis defense demonstrations where operators query multimodal video databases, scrub candidate moments, and submit hit ranges against jury evaluation servers.
* **Value provided:**
  * Eliminates video buffer latency through instant 30-second Temporal Context Filmstrips (`+-15s` neighbor keyframes).
  * Prevents boundary-spillover penalties (`-10 points` per wrong attempt) via the 1-click tight 1.0-second submission shortcut (`[Playhead +-0.5s]`, Hotkey `S`).
  * Enables dynamic query re-ranking in `< 50ms` using in-memory FAISS vector reconstruction and Rocchio relevance feedback.
  * Protects teams from duplicate submission penalties with automated cache deduplication before transmitting API payloads.

---

## 2. Quick Start CLI

### Launch the Interactive KIS Workstation
Execute the debug server entrypoint using `uv`:
```powershell
uv run python -m src.ui.debug_server
```

Expected terminal log:
```text
2026-11-09 00:15:00.120 | INFO     | src.ui.debug_server:run:920 - [INFO] Starting Debug Server at http://127.0.0.1:8000
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [14208] using WatchFiles
```

Open the web interface in your browser:
```text
http://127.0.0.1:8000
```

### Run the Verification & Retrieval Test Suite
Verify that all query routing, negative visual cue filtering, sequence chaining, and DRES submission handlers function correctly:
```powershell
uv run python -m tests.test_retrieval
```

Expected test output:
```text
[OK] All QueryParser tests passed successfully!
[OK] Max-Per-Cue, Consensus Multiplier, and 3-Stage Sequence Linking tests passed!
[OK] Search with explainability trace test passed!
[OK] Task 06B KIS Context Filmstrip and DRES Submission tests passed!
```

---

## 3. UI Controls & Feature Reference

### Interface Architecture Layout

```text
+----------------------------------------------------------------------------------------------------+
| MULTIMODAL VIDEO MOMENT RETRIEVAL - KIS INTERACTIVE WORKSTATION                                    |
+----------------------------------------------------------------------------------------------------+
| Query Input: [ v: woman presenting report | ocr: HTV9 ] [Hybrid] [Visual] [OCR] [Search]           |
+----------------------------------------------------------------------------------------------------+
| TOP SEARCH CANDIDATES (Ranked Moments)        | VIDEO PLAYER & TEMPORAL CONSOLE                    |
| +-------------------------------------------+ | +------------------------------------------------+ |
| | Rank #1 - L13_V001 [24.5s - 29.5s]       | | | [ VIDEO CANVAS ]                               | |
| | [Keyframe Thumbnail]                       | | |                                                | |
| | Score: 0.0321 | Cues: Visual, OCR          | | | Current Time: 00:27.48 / 03:45.00              | |
| | Triggers: [shot_0120_t0026.00.jpg]        | | +------------------------------------------------+ |
| | [Inspect/Play] [+-15s Strip] [Submit KIS] | | Steppers: [-5s] [-1s (J)] [-0.04s]               | |
| | Feedback: [Similar] [Exclude]             | |           [+0.04s] [+1s (L)] [+5s]               | |
| +-------------------------------------------+ | Range: In: [26.00s] [Set In] Out: [27.00s] [Set Out| |
| | Rank #2 - L13_V005 [110.0s - 115.0s]     | | Presets: [Shot Bounds] [Playhead +-0.5s] [Win 5s]| |
| | ...                                       | | Actions: [Play Range] [Submit KIS Range]         | |
| +-------------------------------------------+ | Filmstrip: [+-15s Neighbor Keyframe Cards]       | |
| PIPELINE EXECUTION TRACE & PER-CUE HITS     | DRES Live Score: Time=48.2 | Acc=50.0 | Total=98.2 | |
+----------------------------------------------------------------------------------------------------+
```

### Detailed Component Functions

#### A. Query Builder & Modality Switchers
* **`[Hybrid Multi-Cue]`**: Blends visual semantic cues (SigLIP2) and Vietnamese text cues (EasyOCR SQLite BM25) across 5-second sliding windows using Max-Per-Cue Reciprocal Rank Fusion (RRF).
* **`[Visual Only]`**: Bypasses OCR text and runs pure FAISS vector retrieval using English natural language visual queries.
* **`[OCR Only]`**: Bypasses SigLIP2 and executes full-text search strictly on recognized on-screen text.
* **Negative Visual Cues (`-v:`)**: Filters out misleading visual classes via Rocchio vector orthogonalization (e.g. `v: man speaking | -v: television studio anchor`).
* **Chronological Sequence (`>>`)**: Enforces temporal succession across shots (e.g. `v: car driving >> v: person exits car >> ocr: VinFast`).

#### B. Candidate Moment Cards
* **Representative Thumbnail**: Displays the highest-scoring keyframe within the candidate 5-second window.
* **Trigger Keyframes Accordion**: Expands to show each individual keyframe that triggered visual or OCR matches.
* **`[Inspect / Play]`**: Loads the raw video stream from [data/raw_videos/](file:///d:/UIT/TX/doan/data/raw_videos) and seeks directly to the moment start time.
* **`[+-15s Filmstrip]`**: Opens the 30-second context drawer around this candidate moment.
* **`[Submit KIS]`**: Submits the candidate's active keyframe window with 1 click directly from the card.
* **Relevance Feedback (`[Similar]` / `[Exclude]`):** Performs Rocchio vector re-weighting in `< 50ms` using in-memory FAISS vector reconstruction, boosting or suppressing related video scenes.

#### C. Video Player, Scrubber & Presets
* **Playhead**: The active playback cursor representing current video time in seconds (e.g., `00:27.48`).
* **Fine Steppers**:
  * `[-5s]`, `[+5s]`: Coarse temporal seek.
  * `[-1s]` (Hotkey `J`), `[+1s]` (Hotkey `L`): 1-second navigation.
  * `[-0.04s]`, `[+0.04s]` (Hotkeys `,` and `.`): Single-frame stepping at 25 fps (`40ms` per frame).
* **Mark In & Mark Out**:
  * `In (s)` / `[Set In (I)]` (Hotkey `I`): Locks the submission start time to the current playhead.
  * `Out (s)` / `[Set Out (O)]` (Hotkey `O`): Locks the submission end time to the current playhead.
  * `[Play Range]` (Hotkey `R`): Plays exclusively between `Mark In` and `Mark Out` and automatically pauses at `Out`.
* **Range Presets**:
  * `[Shot Bounds]`: Automatically fills `In` and `Out` using the physical camera shot boundaries detected by PySceneDetect. *(Caution: Shots may be wider than the target ground truth event!)*
  * `[Playhead +-0.5s]` (Hotkey `S`): Centers a tight 1.0-second interval `[currentTime - 0.5s, currentTime + 0.5s]` around the playhead. **This is the primary scoring tool.**
  * `[Window +-2.5s]`: Centers a 5.0-second interval `[currentTime - 2.5s, currentTime + 2.5s]` matching the sliding window unit.

#### D. Temporal Context Filmstrip Drawer
* **Function:** A horizontal carousel presenting 10 to 15 keyframe thumbnails extracted within `+-15s` (`30s` window) around the active playhead, accompanied by their OCR text.
* **Value:** Contestants can visually inspect the surrounding scene context in `< 0.1s` without waiting for video streaming, decoding, or network buffering.

---

## 4. DRES KIS Scoring Mechanics & Ground-Truth Hit Rules

In live Known-Item Search competitions evaluated by the Distributed Retrieval Evaluation Server (DRES API v2):

### Ground-Truth Hit Condition: Strict Inclusion
The jury defines the ground-truth target as a time interval:
`[GT_start, GT_end]` (typically 10 to 30 seconds long).

The contestant submits an interval:
`[S_start, S_end]`.

1. **CORRECT Verdict (Full Hit):**
   * Condition: `GT_start <= S_start <= S_end <= GT_end`
   * The submitted interval must fall **entirely inside** the ground-truth interval.
   * **Crucial Rule:** Overlap percentage (IoU) does **NOT** increase the score. A tight 1.0-second submission fully inside receives the exact same score as a 20-second submission that matches the entire ground truth.

2. **WRONG Verdict (Boundary Spillover Penalty):**
   * Condition: `S_start < GT_start` OR `S_end > GT_end`
   * If even 0.1s spills outside the ground-truth boundaries, DRES judges the submission as **WRONG**.
   * **Penalties:**
     * 0 points awarded for that attempt.
     * **-10 points penalty** deducted from the task's Accuracy pool.
     * Cooldown lock (3 to 5 seconds) before the system allows another submission.

### Total Task Score Formulation
```text
Total_Score = Time_Score + Accuracy_Score
```
* **Time Score (0 to 50 points):** Decays linearly from 50 to 0 across the task time limit `t_limit` (typically 300 seconds):
  `Time_Score = 50 * (1 - t / t_limit)`
* **Accuracy Score (0 to 50 points):** Deducts 10 points for each wrong submission:
  `Accuracy_Score = max(0, 50 - 10 * num_wrong_submissions)`

[INFO] Summary: Success in KIS depends on **speed** and **zero boundary spillover**. Overlap percentage does not provide bonus points.

---

## 5. Recommended Competition Strategy & Operator Playbook

```text
+----------------------------------------------------------------------------------------------------+
|                                  OPTIMAL KIS COMPETITION PLAYBOOK                                  |
+----------------------------------------------------------------------------------------------------+
| 1. DUAL QUERY FORMULATION: Enter Visual (EN) + OCR (VI) -> Click [Search]                          |
| 2. INSTANT FILMSTRIP SCAN: Click [+-15s Filmstrip] on Top-3 cards; scan context in < 0.5s          |
| 3. MOMENT INSPECTION: Click [Inspect/Play] on candidate matching jury description                  |
| 4. CONFIRM & STRIKE: Press Hotkey 'S' ([Playhead +-0.5s]) immediately upon seeing target frame     |
|    -> Submits [t - 0.5s, t + 0.5s] strictly inside ground truth                                    |
|    -> Secures 100% Coordinate Hit + Maximum Time Points + Zero Spillover Risk                      |
| 5. RELEVANCE REFINE (Optional): If hits are close, click [Similar] to re-rank in < 50ms            |
+----------------------------------------------------------------------------------------------------+
```

### Strategic Rules:
1. **Never use `[Shot Bounds]` blindly:**
   * A continuous camera shot may run for 40 seconds (e.g. 00:05 to 00:45), but the specific target action requested by the jury might only span 00:15 to 00:30.
   * Submitting the full shot will spill over the start boundary (`00:05 < 00:15`), causing an immediate **WRONG (-10 points)** verdict.
2. **Always prefer `[Playhead +-0.5s]` (Hotkey `S`):**
   * As soon as the operator visually confirms the target action on the player, pressing `S` submits a tight 1.0-second interval centered at that timestamp.
   * Because ground-truth intervals are almost always >= 10 seconds, this 1.0-second window is virtually guaranteed to sit safely inside `[GT_start, GT_end]`.
3. **Use the Filmstrip to save critical seconds:**
   * Video buffering over the network can take 1 to 3 seconds. The Filmstrip loads instantly from pre-extracted keyframes in [data/keyframes/](file:///d:/UIT/TX/doan/data/keyframes), allowing confirmation before the video even buffers.
4. **Use Negative Visual Filtering (`-v:`) for Studio News Clips:**
   * In broadcast news datasets, news anchor studio shots often dominate visual retrieval. Adding `-v: studio news anchor` suppresses these false positives immediately.

---

## 6. Keyboard Shortcuts Cheat Sheet

| Key / Hotkey | Action | Strategic Value |
| :--- | :--- | :--- |
| **`S`** | **Quick Submit @ Playhead (`+-0.5s`)** | Primary submission action. 1-click safe submission strictly inside GT. |
| **`Space`** | **Play / Pause Video** | Quick toggle of playback state. |
| **`J`** | **Step Backward 1.0s** | Fast reverse search. |
| **`L`** | **Step Forward 1.0s** | Fast forward search. |
| **`,`** (`<`) | **Step Backward 1 Frame (`0.04s`)** | Frame-accurate positioning at 25 fps. |
| **`.`** (`>`) | **Step Forward 1 Frame (`0.04s`)** | Frame-accurate positioning at 25 fps. |
| **`I`** | **Mark In** | Sets submission start time to active playhead. |
| **`O`** | **Mark Out** | Sets submission end time to active playhead. |
| **`R`** | **Play Range** | Previews selected `[In, Out]` segment and auto-pauses. |

---

## 7. Inputs & Outputs

* **Inputs:**
  * Relational metadata and keyframe records from [data/metadata.db](file:///d:/UIT/TX/doan/data/metadata.db).
  * Pre-computed SigLIP2 embeddings from [data/indices/visual_siglip2.index](file:///d:/UIT/TX/doan/data/indices/visual_siglip2.index) and [data/indices/visual_siglip2.json](file:///d:/UIT/TX/doan/data/indices/visual_siglip2.json).
  * Video media files from [data/raw_videos/](file:///d:/UIT/TX/doan/data/raw_videos) and keyframe images from [data/keyframes/](file:///d:/UIT/TX/doan/data/keyframes).
  * Configuration defaults from [configs/default_config.yaml](file:///d:/UIT/TX/doan/configs/default_config.yaml).
* **Outputs:**
  * **DRES API v2 JSON Payload:**
    ```json
    {
      "answerSets": [
        {
          "answers": [
            {
              "mediaItemName": "L13_V001",
              "start": 26980,
              "end": 27980
            }
          ]
        }
      ]
    }
    ```
  * Real-time submission status toast (`DRY_RUN_ACCEPTED`, `DUPLICATE_PREVENTED`, or live server verdict) and live KIS decay score calculation.

---

## 8. Technical Notes & Troubleshooting

* **Hardware Constraints:**
  * The entire interactive search workstation, FAISS vector reconstruction, and DRES submission pipeline run strictly on CPU RAM and SQLite, consuming `< 100MB` RAM.
  * GPU VRAM remains at `0MB` during interactive search, completely avoiding conflicts on constrained GPUs (NVIDIA GeForce GTX 1650 4GB).
* **Duplicate Submission Prevention:**
  * The backend automatically caches all submitted `(evaluation_id, video_id, start_ms, end_ms)` tuples. Resubmitting an identical range is blocked locally before making any network call, preventing accidental `-10 points` penalties.
  * Click `[Clear Cache]` in the DRES panel when transitioning to a new competition task.
* **Common Issues & Fixes:**
  * *Broken Keyframe Thumbnails:* Ensure [src/indexers/metadata_db.py](file:///d:/UIT/TX/doan/src/indexers/metadata_db.py) resolves actual filenames on disk (`shot_XXXX_tYYYY.YY.jpg`) via `get_keyframe_path()`.
  * *Server Port Conflict:* If port 8000 is occupied, set `$env:PORT=8080` in PowerShell prior to launching `uv run python -m src.ui.debug_server`.
