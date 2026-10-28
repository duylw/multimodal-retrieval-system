# User Guide: Web Debug Inspector & Pipeline Monitor

> [!NOTE]
> This guide is also available at [docs/guides/shot-keyframe-inspector.md](file:///d:/UIT/TX/doan/docs/guides/shot-keyframe-inspector.md).

## 1. Feature Overview
* **What it does:** Provides a local, high-performance web-based inspection tool to visually debug, inspect, and monitor the entire multimodal video retrieval pipeline.
* **When to use:** Use throughout both offline ingestion and online retrieval phases to:
  1. Inspect shot boundaries and keyframe representativeness (Task 01/01B).
  2. Test natural language visual semantic search on the FAISS index with instant seeking (Task 02/02C).
  3. Monitor database tables, artifact counts, and pipeline execution checkpoints across all video stages (Task 02B).
* **Value provided:**
  * **Zero VRAM Idle Footprint:** Operates 100% on CPU and system RAM; GPU VRAM is only loaded on-demand during semantic queries and can be released with a single click.
  * **HTTP 206 Range Video Streaming:** Fast seeking across large MP4 video files with minimal buffering and memory usage.
  * **Two-Way Synchronization:** Seeking in the HTML5 video player auto-scrolls to the corresponding shot card; clicking any shot card or keyframe immediately seeks the video.
  * **Live Pipeline Matrix:** Visualizes the completion status (`COMPLETED`, `PENDING`, `FAILED`) of all 5 pipeline stages (`shots`, `keyframes`, `visual`, `speech`, `ocr`) for each video in the dataset.

---

## 2. Quick Start CLI

### 2.1. Launch Server (Default Port 8000)
From the project root directory (`D:\UIT\TX\doan`), run:
```powershell
uv run python -m src.ui.debug_server
```

Once started, open your web browser at:  
**[http://127.0.0.1:8000](http://127.0.0.1:8000)**

### 2.2. Launch Server on Custom Port
If port 8000 is occupied or you wish to run on a different port:
```powershell
$env:PORT="8080"; uv run python -m src.ui.debug_server
```
Then navigate to: **[http://127.0.0.1:8080](http://127.0.0.1:8080)**

---

## 3. Web UI Navigation & Features

The interface consists of three primary views accessible via the top navigation bar:

### Tab 1: Video & Shot Inspector
* **Video Selector:** Dropdown displaying all cataloged videos along with total duration, resolution, shot count, and keyframe count.
* **HTML5 Video Player:** Synchronized playback with real-time timestamp display and playback speed controls.
* **Timeline Bar:** Color-coded visual timeline marking all shot boundaries proportionally across the video duration.
* **Shot Filter Controls:**
  * Search Box: Filter shot cards by specific shot ID (e.g., `15`).
  * Duration Filter: Filter by duration: `All`, `Short (<3s)`, `Medium (3-8s)`, `Long (>8s)`, or `Multi-Keyframe (>1 frame)`.
  * Auto-Scroll Checkbox: Toggle automatic scrolling of shot cards as the video plays.
* **Shot Inspection Cards:** Each card displays:
  * Shot ID, time interval (`[start_sec - end_sec]`), and duration.
  * Extracted keyframe thumbnail(s) with sharpness blur score and center-frame badge.
  * Click to seek directly to the shot start time.

### Tab 2: Visual Semantic Search
* **Query Input:** Enter natural language search queries in Vietnamese or English (e.g. *"cận cảnh đĩa thức ăn"*, *"a close-up shot of food preparation"*).
* **Target Video Scope:** Search across all indexed videos or restrict candidate ranking to the currently selected video.
* **Search Results Grid:** Displays Top-K candidate shots/keyframes:
  * Similarity rank and cosine score (`IndexFlatIP`).
  * Representative thumbnail image.
  * Target timestamp and duration interval.
  * Granularity badge: `[Shot Pooled]` (intra-shot mean vector) vs `[Keyframe]` (discrete frame vector).
  * Click any result to seek the video player directly to that moment.
* **Release VRAM Button:** Click **"Unload Model"** to purge SigLIP2 weights and PyTorch CUDA cache from GPU VRAM immediately after testing queries.

### Tab 3: Pipeline & DB Inspector
* **Database Summary Cards:** Live counts of cataloged videos, detected shots, extracted keyframes, and pipeline checkpoints.
* **Pipeline Status Matrix:** A comprehensive table mapping each raw video against the 5 pipeline stages:
  * `shots`: Shot boundary detection status.
  * `keyframes`: Keyframe extraction status.
  * `visual`: SigLIP2 dense feature caching status.
  * `speech`: Whisper transcription status.
  * `ocr`: PaddleOCR text extraction status.
* **Stage Badges:** Color-coded badges:
  * `[COMPLETED]` (Green): Stage finished successfully, displays artifact count.
  * `[PENDING]` (Gray): Stage has not been run yet.
  * `[FAILED]` (Red): Stage encountered an error; hover to view the error message.

---

## 4. REST API Endpoints Reference

The backend FastAPI server exposes standard JSON and streaming endpoints:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serves Single-Page Application (HTML/CSS/JS). |
| `GET` | `/api/videos` | Returns list of all cataloged videos with summary metrics. |
| `GET` | `/api/videos/{video_id}` | Returns shot boundaries and keyframe metadata for a video. |
| `GET` | `/api/stream/{video_id}` | Streams video with HTTP 206 Partial Content Range support. |
| `GET` | `/api/keyframes/{video_id}/{filename}` | Serves static keyframe JPEG images. |
| `GET` | `/api/search/visual` | Performs SigLIP2 semantic search on FAISS visual index. Parameters: `query`, `video_id`, `top_k`. |
| `POST` | `/api/search/unload` | Releases SigLIP2 model and clears GPU VRAM. |
| `GET` | `/api/db/summary` | Returns SQLite table row counts and checkpoint matrix. |

---

## 5. Technical Notes & Troubleshooting

* **Hardware Footprint:**
  * When browsing shots and checkpoints: Consumes **0 MB GPU VRAM** and ~80 MB system RAM.
  * When performing visual queries: SigLIP2-Base temporarily consumes ~550 MB VRAM. Click "Unload Model" to free memory completely.
* **Port Conflict Handling:**
  * If port 8000 is already in use by another application:
    ```powershell
    # Check what process is using port 8000:
    Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
    # Or launch on port 8080:
    $env:PORT="8080"; uv run python -m src.ui.debug_server
    ```
* **Browser Cache Refresh:**
  * If frontend JavaScript or CSS does not update after editing, perform a hard refresh using **`Ctrl + F5`** (Windows) in Chrome/Edge.
* **Missing Video File in Player:**
  * Verify that raw MP4 videos exist in [data/raw_videos/](file:///d:/UIT/TX/doan/data/raw_videos) with exact filename matching `video_id` (e.g. `L13_V001.mp4`).
