# Task 01B: Shot & Keyframe Debug Inspector Web UI

## 1. Objectives (What)
* Build a lightweight, local web-based debugging and inspection tool for verifying video shot segmentation and adaptive keyframe extraction:
  * **Video Selection:** Dynamically list all processed videos cataloged in SQLite `metadata.db`.
  * **Video Playback with HTTP 206 Range Requests:** Stream local raw video files (`data/raw_videos/{video_id}.mp4`) with smooth, instant seeking across frames and seconds without loading the entire video into RAM.
  * **Interactive Shot Boundary Timeline:** Render a proportional timeline representing video duration with color-coded shot segments, displaying exact start/end timestamps and durations on hover.
  * **Shot & Keyframe Inspection Cards:** Display all keyframes nested within their respective shots, accompanied by thumbnails, timestamps (`timestamp_sec`), classification tags (`Center` vs `Dynamic`), and Laplacian blur variance scores.
  * **Two-Way Synchronization:**
    * Clicking a shot segment on the timeline or card header jumps video playback to the shot's start timestamp.
    * Clicking a keyframe thumbnail jumps video playback directly to that keyframe's exact timestamp.
    * During playback, the timeline scrubber tracks current time, the active shot card highlights with a glowing border, and the list scrolls smoothly within its isolated container.
* Guarantee **0MB GPU VRAM** usage (operates purely on CPU and system RAM via a standard ASGI web server) to keep the GTX 1650 completely free.

---

## 2. Technical Architecture & Design (How)

### 2.1. Backend Server ([src/ui/debug_server.py](file:///d:/UIT/TX/doan/src/ui/debug_server.py))
Utilizes **FastAPI** with `uvicorn` to provide high-performance RESTful APIs:
* `GET /api/videos`: Queries `videos` and `checkpoints` tables from `metadata.db` to return cataloged videos with shot and keyframe counts.
* `GET /api/videos/{video_id}`: Queries `shots` and `keyframes` tables, returning a structured JSON hierarchy:
  ```json
  {
    "video": {"video_id": "L13_V001", "duration_sec": 1133.0, "fps": 25.0},
    "total_shots": 292,
    "total_keyframes": 344,
    "shots": [
      {
        "shot_id": 1,
        "start_sec": 0.0,
        "end_sec": 16.6,
        "duration_sec": 16.6,
        "keyframes": [
          {"keyframe_id": "kf_0001", "timestamp_sec": 3.32, "is_shot_center": false, "blur_score": 417.7, "image_url": "/api/keyframes/L13_V001/shot_0001_t0003.32.jpg"},
          {"keyframe_id": "kf_0002", "timestamp_sec": 6.64, "is_shot_center": true, "blur_score": 606.6, "image_url": "/api/keyframes/L13_V001/shot_0001_t0006.64.jpg"}
        ]
      }
    ]
  }
  ```
* `GET /api/stream/{video_id}`: Streams local MP4 files supporting HTTP `Range` header requests (`HTTP 206 Partial Content`), delivering 64KB chunks on demand.
* `GET /api/keyframes/{video_id}/{filename}`: Serves static keyframe JPEG images.
* `GET /`: Serves the Single-Page Application (SPA) HTML.

### 2.2. Frontend Architecture ([src/ui/static/](file:///d:/UIT/TX/doan/src/ui/static/))
Built with semantic HTML5, Vanilla CSS3 (Dark Mode), and modern JavaScript:
* **Header Bar:** Video selector dropdown, duration badge, FPS, total shots count, total keyframes count.
* **Left Pane (Video Player & Interactive Timeline):**
  * HTML5 video element with responsive 16:9 aspect ratio.
  * Real-time playback timestamp display and active shot indicator badge.
  * Quick navigation buttons: `[Prev Shot]`, `[Next Shot]`, `[Jump Center Keyframe]`.
  * Interactive shot boundary timeline with hover tooltips and live progress scrubber.
* **Right Pane (Shot & Keyframe Inspector):**
  * Fixed-height container with isolated scrollbar (`overflow-y: auto`), preventing outer window dragging.
  * Search filter by shot ID and duration category (`<3s`, `3-8s`, `>8s`, `multi-kf`).
  * Smooth container-isolated auto-scroll (`shotList.scrollTo`) syncing with video playback.

---

## 3. Data Flow Diagram (ASCII)

```
[Local Web Browser]
       │
       ├─► (1) GET /api/videos ──────────► [FastAPI Server] ──► [metadata.db] (Read catalog)
       │
       ├─► (2) GET /api/videos/{id} ─────► [FastAPI Server] ──► [metadata.db] (Group shots & keyframes)
       │
       ├─► (3) GET /api/stream/{id} ─────► [FastAPI Server] ──► [data/raw_videos/{id}.mp4] (Stream Range 206)
       │
       └─► (4) GET /api/keyframes/... ───► [FastAPI Server] ──► [data/keyframes/{id}/*.jpg]
```

---

## 4. Acceptance Criteria & Test Results
* [x] Server launches via `uv run python -m src.ui.debug_server` at `http://127.0.0.1:8000`.
* [x] Successfully queries `L13_V001` (292 shots, 344 keyframes).
* [x] Video streams smoothly with HTTP 206 Partial Content Range requests.
* [x] Clicking timeline segments or keyframe thumbnails seeks video to exact timestamps.
* [x] Scrolling is isolated to `.shot-list`; page layout remains fixed at 100vh viewport height.
* [x] GPU VRAM consumption is 0MB.

---

## 5. Deliverables
1. Backend Server: [src/ui/debug_server.py](file:///d:/UIT/TX/doan/src/ui/debug_server.py).
2. Frontend Assets: [src/ui/static/index.html](file:///d:/UIT/TX/doan/src/ui/static/index.html), [src/ui/static/style.css](file:///d:/UIT/TX/doan/src/ui/static/style.css), [src/ui/static/app.js](file:///d:/UIT/TX/doan/src/ui/static/app.js).
3. Usage Guide: [docs/guides/shot-keyframe-inspector.md](file:///d:/UIT/TX/doan/docs/guides/shot-keyframe-inspector.md).
