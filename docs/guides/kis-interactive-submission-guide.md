# KIS Interactive Verification & DRES Live Submission Guide

## 1. Overview
The **KIS Interactive Verification & DRES Live Submission Console** ([src/ui/debug_server.py](file:///d:/UIT/TX/doan/src/ui/debug_server.py), [src/ui/static/index.html](file:///d:/UIT/TX/doan/src/ui/static/index.html), [src/ui/static/app.js](file:///d:/UIT/TX/doan/src/ui/static/app.js)) provides a competition-grade human-in-the-loop (HITL) Known-Item Search (KIS) workstation for VBS, LSC, and AIC HCMC evaluations.

It combines:
* **1-Click Quick Submit @ Playhead (`+-0.5s`)** and hotkey `S` for immediate tight-interval submission (`[t_current - 500ms, t_current + 500ms]`), alongside 1-click `[Submit KIS]` directly on ranked candidate cards.
* **Temporal Context Filmstrip (`+-15s Neighbor Keyframes`)** on both candidate cards and the video player to inspect adjacent keyframes and OCR text in `< 0.5s` without waiting for video streaming.
* **Fine-Grained Frame Scrubber & Range Presets** (`[-5s]`, `[-1s (J)]`, `[-0.04s]`, `[+0.04s]`, `[+1s (L)]`, `[+5s]`, `Mark In (I)`, `Mark Out (O)`, `[Shot Bounds]`, `[Playhead +-0.5s]`, `[Window +-2.5s]`, `[Play Range]`).
* **Negative Visual Cue Filtering (`-v:`) & Story Coverage Boost** in [src/retrieval/search_engine.py](file:///d:/UIT/TX/doan/src/retrieval/search_engine.py) and [src/retrieval/score_fusion.py](file:///d:/UIT/TX/doan/src/retrieval/score_fusion.py), plus N-stage (`N >= 2`) chronological sequence linking (`Stage 1 >> Stage 2 >> Stage 3`).
* **Live KIS Score Decay Simulator & Duplicate Submission Guard** powered by [src/submission/dres_client.py](file:///d:/UIT/TX/doan/src/submission/dres_client.py).

---

## 2. Quick Start

### Launch the Interactive KIS Workstation
```powershell
uv run python -m src.ui.debug_server
```
Then open `http://127.0.0.1:8000` in your browser.

### Run the Retrieval & KIS Endpoint Test Suite
```powershell
uv run python -m tests.test_retrieval
```

### Example Multi-Cue & Negative Visual Queries
```text
v: man speaking | -v: studio news anchor | ocr: VTV1
v: wide shot street >> v: car collision >> ocr: 51B
```

---

## 3. CLI & API Endpoints

| Endpoint / Control | Method / Hotkey | Default | Description |
| :--- | :--- | :--- | :--- |
| `GET /api/videos/{video_id}/context` | HTTP `GET` | `window_sec=15.0` | Returns neighbor keyframes and OCR detections within `[timestamp_sec - window_sec, timestamp_sec + window_sec]`. |
| `POST /api/dres/submit` | HTTP `POST` | `dry_run=True` | Converts `[start_sec, end_sec]` to integer milliseconds, strips `.mp4`, checks duplicate cache, and submits to DRES API v2. |
| `GET /api/dres/status` | HTTP `GET` | N/A | Returns active DRES session state, evaluation ID, submitted cache count, and recent submission log. |
| `POST /api/dres/session` | HTTP `POST` | N/A | Updates DRES server URL, evaluation ID, or authenticates with session token / credentials. |
| `POST /api/dres/clear-cache` | HTTP `POST` | N/A | Clears the local duplicate submission guard cache and history for a new competition task. |
| `Quick Submit @ Playhead` | Key `S` | `+-0.5s` (`1000ms`) | Submits `[currentTime - 0.5s, currentTime + 0.5s]` around the current playhead immediately. |
| `Mark In` / `Mark Out` | Keys `I` / `O` | Active Shot Bounds | Sets the start or end boundary of the submission interval to the current video playhead. |
| `Fine Frame Step` | Keys `,` / `.` (`Arrows`) | `+-0.04s` (`25fps`) | Steps backward or forward by 1 frame (`0.04s`) or 1 second (`J` / `L`). |

---

## 4. Inputs & Outputs

* **Inputs:**
  * Relational metadata and keyframe records from [data/metadata.db](file:///d:/UIT/TX/doan/data/metadata.db).
  * Visual SigLIP2 FAISS index from [data/indices/visual_siglip2.index](file:///d:/UIT/TX/doan/data/indices/visual_siglip2.index) and [data/indices/visual_siglip2.json](file:///d:/UIT/TX/doan/data/indices/visual_siglip2.json).
  * Raw video streams from [data/raw_videos/](file:///d:/UIT/TX/doan/data/raw_videos) and extracted keyframe JPEGs from [data/keyframes/](file:///d:/UIT/TX/doan/data/keyframes).
* **Outputs:**
  * **DRES API v2 JSON Payload:**
    ```json
    {
      "answerSets": [
        {
          "answers": [
            {
              "mediaItemName": "L13_V001",
              "start": 25000,
              "end": 26000
            }
          ]
        }
      ]
    }
    ```
  * Real-time submission status toast (`DRY_RUN_ACCEPTED`, `DUPLICATE_PREVENTED`, or live DRES response) and estimated KIS score (`S_total(t, w) = max(0, 50 - 10*w) + 50 * (1 - t / T_limit)`).

---

## 5. Hardware Constraints & Notes

* **Zero Extra GPU Overhead:** Temporal Context Filmstrip (`GET /api/videos/{video_id}/context`), single-video vector reconstruction (`[Only {video_id}]`), and DRES submission operate strictly on SQLite and CPU RAM (`< 5ms` latency), keeping GPU VRAM usage well within the 4GB budget on NVIDIA GeForce GTX 1650.
* **Duplicate Penalty Protection:** Submitting the exact same `(evaluation_id, video_id, start_ms, end_ms)` tuple twice within the same query session is automatically blocked before any network call to prevent accidental `-10 point` DRES penalties. Use `[Clear Cache]` when advancing to a new competition query.
* **Tight Interval Strategy:** When a target scene is confirmed on the video player, prefer `[Quick Submit @ Playhead +-0.5s (S)]` over submitting a wide 5-second window so that both `start_ms` and `end_ms` fall strictly inside the ground-truth interval `[GT_start, GT_end]`.

