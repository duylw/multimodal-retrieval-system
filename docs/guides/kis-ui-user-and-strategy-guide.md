# KIS UI User & Competition Strategy Guide

## 1. Feature Overview
The **KIS Interactive Search & Live Submission Console** ([src/ui/static/index.html](file:///d:/UIT/TX/doan/src/ui/static/index.html), [src/ui/static/app.js](file:///d:/UIT/TX/doan/src/ui/static/app.js), [src/ui/debug_server.py](file:///d:/UIT/TX/doan/src/ui/debug_server.py)) is a competition-grade human-in-the-loop workstation designed for **Known-Item Search (KIS)** competitions (e.g., Video Browser Showdown - VBS, Lifelog Search Challenge - LSC, and AI Challenge HCMC).

This guide provides a clear breakdown of every UI feature, explains the underlying DRES scoring rules, and outlines the recommended competition strategy to maximize team score.

---

## 2. Interactive UI Layout

```text
+--------------------------------------------------------------------------------------------------+
| MULTIMODAL VIDEO MOMENT RETRIEVAL - KIS WORKSTATION                                             |
+--------------------------------------------------------------------------------------------------+
| Query Input: [ v: woman presenting report | ocr: HTV9 ] [✨ Hybrid] [📷 Visual] [📝 OCR] [Search] |
+--------------------------------------------------------------------------------------------------+
| TOP SEARCH CANDIDATES (Ranked Moments)      | VIDEO PLAYER & TEMPORAL CONSOLE                    |
| +-----------------------------------------+ | +------------------------------------------------+ |
| | Rank #1 - L13_V001 [24.5s - 29.5s]     | | | [ VIDEO CANVAS ]                               | |
| | [Keyframe Thumbnail]                     | | |                                                | |
| | Score: 0.0321 | Cues: Visual, OCR        | | | Current Time: 00:27.48 / 03:45.00              | |
| | Triggers: [shot_0120_t0026.00.jpg]      | | +------------------------------------------------+ |
| | [Inspect/Play] [+-15s Strip] [Submit]   | | Frame Steppers: [-5s] [-1s (J)] [-0.04s]         | |
| | Feedback: [👍 Similar] [👎 Exclude]     | |                 [+0.04s] [+1s (L)] [+5s]         | |
| +-----------------------------------------+ | Range: In: [26.00s] [Set In] Out: [27.00s] [Set Out| |
| | Rank #2 - L13_V005 [110.0s - 115.0s]   | | Presets: [Shot Bounds] [Playhead +-0.5s] [Win 5s]| |
| | ...                                     | | Actions: [Play Range] [Submit KIS Range]         | |
| +-----------------------------------------+ | Filmstrip: [+-15s Surrounding Keyframe Cards]    | |
| PIPELINE EXECUTION TRACE (Explainability)   | DRES Live Score: Time=48.2 | Acc=50.0 | Total=98.2 | |
+--------------------------------------------------------------------------------------------------+
```

---

## 3. UI Controls & Feature Reference

### A. Modality Selectors & Query Syntax
* `[✨ Hybrid Multi-Cue]`: Combines visual semantic embeddings (SigLIP2) and Vietnamese on-screen text (EasyOCR SQLite BM25) across 5-second sliding windows using Max-Per-Cue Reciprocal Rank Fusion (RRF).
* `[📷 Visual Only]`: Bypasses OCR to perform pure FAISS vector retrieval using English natural language visual queries.
* `[📝 OCR Only]`: Bypasses SigLIP2 to search strictly on Vietnamese/English on-screen text recognized via EasyOCR.
* **Negative Visual Cues (`-v:`)**: Excludes false positives (e.g., `v: man speaking | -v: television studio anchor`).
* **Chronological Sequence (`>>`)**: Chains temporal events in chronological order (e.g., `v: car driving >> v: person exits car >> ocr: VinFast`).

### B. Candidate Cards
* **Thumbnail & Rank Badge**: Shows the representative keyframe for the candidate 5-second window.
* **Trigger Keyframes Accordion**: Expands to reveal which exact keyframes triggered the visual or OCR hits.
* **`[Inspect / Play]`**: Loads the video into the player and seeks directly to the candidate start time.
* **`[+-15s Filmstrip]`**: Opens the 30-second context window showing neighboring keyframes.
* **`[Submit KIS]`**: Submits the candidate's active keyframe window to DRES with 1 click.
* **Relevance Feedback (`[👍 Similar]` / `[👎 Exclude]`):** Runs Rocchio feedback directly in memory (`< 50ms`) using FAISS vector reconstruction, pulling similar moments to the top of the ranking.

### C. Player Scrubber & Boundary Presets
* **Playhead**: The current playback position in seconds (represented by the timeline scrubber).
* **Steppers**:
  * `[-5s]`, `[+5s]`: Coarse navigation jumps.
  * `[-1s]` (Hotkey `J`), `[+1s]` (Hotkey `L`): 1-second fine scrubbing.
  * `[-0.04s]`, `[+0.04s]`: Single-frame stepping at 25 fps (`40ms` per step).
* **Mark In & Mark Out**:
  * `In (s)` / `[Set In (I)]` (Hotkey `I`): Sets the submission start time to the current playhead.
  * `Out (s)` / `[Set Out (O)]` (Hotkey `O`): Sets the submission end time to the current playhead.
  * `[Play Range]`: Loops or plays strictly between `Mark In` and `Mark Out` and auto-pauses.
* **Range Presets**:
  * `[Shot Bounds]`: Auto-fills `In` and `Out` using the pre-computed shot boundaries detected by PySceneDetect in Task 01.
  * `[Playhead +-0.5s]` (Hotkey `S`): Centers a tight 1.0-second interval `[currentTime - 0.5s, currentTime + 0.5s]` around the playhead.
  * `[Window +-2.5s]`: Centers a 5.0-second interval `[currentTime - 2.5s, currentTime + 2.5s]` matching the sliding window unit.

### D. Temporal Context Filmstrip
* **What it is**: A horizontal drawer displaying all keyframes extracted within `+-15s` (`30s` total window) around the active playhead.
* **Why it matters**: Contestants can inspect 10 to 15 neighboring keyframes and their OCR text in `< 0.5s` without waiting for video streaming, buffering, or seeking latency.

---

## 4. DRES KIS Scoring Rules Explained

In live Known-Item Search competitions governed by DRES (VBS, LSC, AIC HCMC):

### Ground-Truth Hit Criteria: Strict Inclusion
The competition ground truth is an interval:
`[GT_start, GT_end]` (typically 10 to 30 seconds long).

A team submission is an interval:
`[S_start, S_end]`.

1. **CORRECT Verdict (Full Coordinate Hit):**
   * Condition: `GT_start <= S_start <= S_end <= GT_end`
   * The submission must fall **entirely inside** the ground-truth interval.
   * **Crucial Rule:** Overlap percentage (IoU) does **NOT** increase points. A 1.0-second submission fully inside receives the exact same score as a 20-second submission covering the full ground truth.

2. **WRONG Verdict (Boundary Spillover Penalty):**
   * Condition: `S_start < GT_start` OR `S_end > GT_end`
   * If even 0.1s spills outside the ground-truth interval, DRES judges the submission as **WRONG**.
   * **Consequences:**
     * 0 points awarded for this submission.
     * **-10 point penalty** deducted from the task's Accuracy pool.
     * Cooldown lock (3-5 seconds) before another submission is accepted.

### Total Task Score Formulation
```text
Total_Score = Time_Score + Accuracy_Score
```
* **Time Score (0 - 50 points):** Decays linearly from 50 to 0 across the task time limit `t_limit` (e.g. 300 seconds):
  `Time_Score = 50 * (1 - t / t_limit)`
* **Accuracy Score (0 - 50 points):** Penalized by previous wrong attempts:
  `Accuracy_Score = max(0, 50 - 10 * num_wrong_submissions)`

[INFO] Summary: You score high by submitting **fast** and **never guessing outside boundaries**. Overlap percentage does not reward you.

---

## 5. Recommended Competition Strategy

```text
+-------------------------------------------------------------------------------+
|                        OPTIMAL KIS COMPETITION PLAYBOOK                       |
+-------------------------------------------------------------------------------+
| 1. DUAL QUERY: Enter Visual (EN) + OCR (VI) -> Click [Search]                 |
| 2. QUICK SCAN: Scan top 5 cards; expand [+-15s Filmstrip] to verify context   |
| 3. JUMP: Click [Inspect/Play] on matching candidate                           |
| 4. CONFIRM & SUBMIT: Hit Hotkey 'S' ([Playhead +-0.5s])                       |
|    -> Submits [t - 0.5s, t + 0.5s] strictly inside GT                         |
|    -> Secures 100% Coordinate Hit + Maximum Time Points + Zero Spill Risk     |
| 5. REFINE (Optional): If close but not exact, click [👍 Similar] to re-rank   |
+-------------------------------------------------------------------------------+
```

### Strategic Rules:
1. **Never use `[Shot Bounds]` blindly:**
   * A camera shot may last 35 seconds (e.g., 00:05 to 00:40), but the target event specified by the jury might only span 00:15 to 00:30.
   * Submitting the full shot will spill over the start (`00:05 < 00:15`), causing an immediate **WRONG (-10 points)** verdict.
2. **Always prefer `[Playhead +-0.5s]` (Hotkey `S`):**
   * When your eye confirms the target frame on screen, pressing `S` submits a tight 1.0-second interval centered at that instant.
   * Because the ground-truth interval is almost always >= 10 seconds, this 1.0-second slice is virtually guaranteed to sit safely inside `[GT_start, GT_end]`.
3. **Use the Filmstrip to save critical seconds:**
   * Video buffering over the network can take 1-3 seconds. The Filmstrip loads instantly from extracted keyframes (`< 0.1s`), letting you confirm the moment before the video even starts playing.
4. **Use Negative Visual Filtering (`-v:`) for Studio News Clips:**
   * If searching for a street scene or outdoor interview, news anchor studio shots often dominate visual retrieval. Adding `-v: studio news anchor` removes these distractors immediately.

---

## 6. Keyboard Shortcuts Cheat Sheet

| Key / Hotkey | Action | Strategic Purpose |
| :--- | :--- | :--- |
| `S` | **Quick Submit @ Playhead (`+-0.5s`)** | Primary submission action. 1-click safe submission inside GT interval. |
| `Space` | **Play / Pause Video** | Quick toggle of playback. |
| `J` | **Step Backward 1.0s** | Fast reverse search. |
| `L` | **Step Forward 1.0s** | Fast forward search. |
| `,` (`<`) | **Step Backward 1 Frame (`0.04s`)** | Frame-accurate positioning. |
| `.` (`>`) | **Step Forward 1 Frame (`0.04s`)** | Frame-accurate positioning. |
| `I` | **Mark In** | Sets submission start time to current playhead. |
| `O` | **Mark Out** | Sets submission end time to current playhead. |
| `R` | **Play Range** | Previews selected `[In, Out]` interval. |

---

## 7. Verification & Launch Commands

### Launch the Workstation
```powershell
uv run python -m src.ui.debug_server
```

### Run Retrieval Test Suite
```powershell
uv run python -m tests.test_retrieval
```
Expected output:
```text
[OK] Test 1 Passed: Multi-cue retrieval and score fusion successful.
[OK] Test 2 Passed: Negative visual cue filtering successful.
[OK] Test 3 Passed: 3-stage sequence chaining successful.
```
