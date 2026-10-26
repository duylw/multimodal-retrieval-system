# User Guide: Shot & Keyframe Debug Inspector

## 1. Feature Overview
* **What it does:** Provides a local web-based inspection tool to visually debug, inspect, and evaluate video shot boundary detection and extracted keyframes across all processed videos.
* **When to use:** Use immediately following offline shot segmentation and keyframe extraction to visually verify cut transitions and keyframe representativeness before initiating deep embedding extraction with SigLIP2.
* **Value provided:**
  * Two-way synchronization between HTML5 Video Player, Shot Boundary Timeline, and Shot Inspector Cards.
  * Instant seeking on heavy MP4 video files via HTTP 206 Partial Content Range streaming with minimal RAM usage.
  * Isolated container scrolling: Shot list scrolls independently without dragging or shifting the outer window or video player.

---

## 2. Quick Start CLI

### 2.1. Launch Server (Default Port 8000):
```powershell
uv run python -m src.ui.debug_server
```

Once launched, access the web interface in your browser at: **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

### 2.2. Launch Server on Custom Port:
```powershell
$env:PORT="8080"; uv run python -m src.ui.debug_server
```

---

## 3. Parameters & Environment Variables

| Parameter / Flag | Data Type | Default Value | Required | Description |
|---|---|---|---|---|
| `$env:PORT` | `int` | `8000` | No | TCP listening port for the Uvicorn ASGI server |
| `video_id` | `str` | Dropdown UI | No | Selected on UI dropdown to inspect different videos |
| Search Box | `str` | Empty | No | Filter shot cards by specific shot ID (e.g. `15`) |
| Filter Dropdown | `enum` | `all` | No | Filter shots by duration: `all`, `short` (<3s), `medium` (3-8s), `long` (>8s), `multi-kf` (>1 frame) |
| Auto-scroll Checkbox | `bool` | `checked` | No | Enable/disable auto-scrolling shot cards as video advances |

---

## 4. Inputs & REST Endpoints

* **Inputs:**
  * Raw video source: [data/raw_videos/{video_id}.mp4](file:///d:/UIT/TX/doan/data/raw_videos)
  * Metadata Database: [data/metadata.db](file:///d:/UIT/TX/doan/data/metadata.db)
  * Extracted Keyframes: `data/keyframes/{video_id}/*.jpg`
* **REST API Endpoints:**
  * `GET /`: Serves Single-Page Application (HTML/CSS/JS).
  * `GET /api/videos`: Returns JSON list of cataloged videos.
  * `GET /api/videos/{video_id}`: Returns shot boundaries with nested keyframes metadata.
  * `GET /api/stream/{video_id}`: Streams local MP4 video supporting HTTP 206 Partial Content.
  * `GET /api/keyframes/{video_id}/{filename}`: Serves static keyframe JPEG images.

---

## 5. Technical Notes & Troubleshooting

* **Hardware Constraints:**
  * Operates 100% on CPU and system RAM, consuming **0MB GPU VRAM**.
* **Port Conflict Handling:**
  * If port 8000 is occupied, verify with:
    ```powershell
    Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
    ```
  * Switch to an alternate port via:
    ```powershell
    $env:PORT="8080"; uv run python -m src.ui.debug_server
    ```
* **Refreshing Frontend Assets:**
  * Uvicorn runs in auto-reload mode. If CSS or JS files are updated, press **`Ctrl + F5`** in the browser to clear cached assets.
