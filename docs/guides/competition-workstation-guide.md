# User Guide: Dedicated KIS Competition Workstation UI & Modal Video Inspector

## 1. Feature Overview
* **What it does:** The KIS Competition Workstation is a standalone, distraction-free web interface dedicated to live Known-Item Search (KIS) contest performance. It decouples high-speed contest submission workflows from internal debug inspectors, providing a dual-zone ergonomic layout: a persistent Left KIS Command Center Drawer and a Right High-Density Frame Grid with an instant Pop-up Video Modal Player.
* **When to use:** Use during live competition rounds (VBS, AI Challenge) or contest rehearsal sessions when submitting target moments directly to the DRES API v2 server under strict time limits (300s for Textual KIS, 240s for Video KIS).
* **Value provided:** Delivers lightning-fast visual browsing (12-20 candidate frames visible simultaneously), automated query translation (`VI ➜ EN`) with selective OCR preservation, competition session query history chips, 1-click Playhead submission (`+-0.5s`, hotkey `S`), fine-stepper frame scrubbers (`40ms` per frame), live score decay prediction, and duplicate submission suppression in `< 150ms`.

---

## 2. Quick Start CLI

Launch the dedicated competition server on port `8001`:

```powershell
uv run --extra gpu python -m src.ui.competition_server --port 8001
```

Or using `--no-sync` (skips dependency resolution checks):

```powershell
uv run --no-sync python -m src.ui.competition_server --port 8001
```

Or using the direct environment executable:

```powershell
.venv\Scripts\python.exe -m src.ui.competition_server --port 8001
```

Expected terminal output:
```text
2026-11-14 16:17:30.124 | INFO     | src.ui.competition_server:main:670 - [INFO] Launching KIS Competition Workstation on http://127.0.0.1:8001
INFO:     Started server process [18924]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8001 (Press CTRL+C to quit)
```

Access the workstation in your browser at:
`http://127.0.0.1:8001`

---

## 3. CLI Arguments & Configuration Parameters

[src/ui/competition_server.py](file:///d:/UIT/TX/doan/src/ui/competition_server.py) supports the following runtime arguments:

| Parameter Name | Short Flag | Data Type | Default Value | Required | Description |
|---|---|---|---|---|---|
| `--host` | None | `str` | `127.0.0.1` | No | Binding IP address for the HTTP server |
| `--port` | None | `int` | `8001` | No | TCP listening port (decoupled from debug server on 8000) |
| `--reload` | None | `bool` | `False` | No | Enables Uvicorn hot reloading for UI asset development |

### Environment Variables (.env)
The server automatically loads environment overrides from [.env](file:///d:/UIT/TX/doan/.env) if present:
* `DRES_BASE_URL`: Base URL of the competition server (default: `https://eventretrieval.one`).
* `DRES_SESSION_ID`: Active team session token for authenticated submissions.
* `DRES_EVAL_ID`: Target evaluation round identifier (default: `offline_kis_eval`).

---

## 4. UI Architecture & Keyboard Accelerators

### Workstation Layout Diagram

```text
+---------------------------------------------------------------------------------------------------------+
|                                    KIS COMPETITION WORKSTATION                                          |
| [Query: "xe buyt mau xanh | ocr: 51B"    ] [VI->EN] [X]  [x] Auto VI->EN  [x] DRES Batches  Limit:[ 100 v] |
+---------------------------------------------------------------------------------------------------------+
| [Recent: [v: blue bus | ocr: 51B] [v: woman supermarket] [ocr: HTV9] [Clear] ]                           |
| [VI->EN: "xe buyt mau xanh | ocr: 51B" -> "v: blue bus | ocr: 51B"                     [Revert] [X] ]   |
+------------------------------------+--------------------------------------------------------------------+
| LEFT: KIS COMMAND CENTER (DRAWER)  | RIGHT: HIGH-DENSITY FRAME GRID (TOP-DOWN, LEFT-TO-RIGHT)           |
|                                    |                                                                    |
| [LIVE DRES / DRY-RUN] [Config]     | +--------------------+ +--------------------+ +------------------+ |
| Timer: 03:42 / 05:00  Score: 82.5  | | #1  [THUMB 16:9]   | | #2  [THUMB 16:9]   | | #3 [THUMB 16:9]  | |
| [Start/Pause] [Reset] [Wrong: 0]   | | L05_V014   00:22.7 | | L13_V016   00:29.8 | | L21_V002 01:14.2 | |
|                                    | | [Text] "51B-501.62"| | [Text] "51B-318.88"| | [Consensus: 2]   | |
| Target: L05_V014                   | | [Play] [Filmstrip] | | [Play] [Filmstrip] | | [Play] [Strip]   | |
| Range: 22000ms - 27000ms (5.0s)    | | [ SUBMIT KIS ]     | | [ SUBMIT KIS ]     | | [ SUBMIT KIS ]   | |
| Presets: [+-0.5s] [Shot] [+-2.5s]  | +--------------------+ +--------------------+ +------------------+ |
|                                    | +--------------------+ +--------------------+ +------------------+ |
| [ SUBMIT TARGET RANGE ]            | | #4  [THUMB 16:9]   | | #5  [THUMB 16:9]   | | #6 [THUMB 16:9]  | |
| [ QUICK SUBMIT @ PLAYHEAD (S) ]    | | ...                | | ...                | | ...              | |
|                                    | +--------------------+ +--------------------+ +------------------+ |
| Real-time Submission Stream:       |                                                                    |
| - L05_V014 [22-27s] -> [WRONG]     |                                                                    |
| - L13_V016 [25-32s] -> [CORRECT]   |                                                                    |
+------------------------------------+--------------------------------------------------------------------+
| POP-UP MODAL VIDEO INSPECTOR (Triggered on candidate thumbnail click):                                  |
| +-----------------------------------------------------------------------------------------------------+ |
| | Video: L05_V014 @ 00:22.72 / 12:45.00                                                         [X]   | |
| | [                           VIDEO STREAM PLAYER (HTTP 206)                                        ] | |
| | Controls: [-5s] [-1s] [-1f] [ > Play ] [+1f] [+1s] [+5s]  | Mark In: 22.0s (I)  Mark Out: 23.0s (O) | |
| | [Play Range]  [ SUBMIT RANGE ]  [ SUBMIT PLAYHEAD (S) ]                                             | |
| | Context Filmstrip (+-15s): [ -12.4s ] [ -8.1s ] [ -3.2s ] [ CENTER ] [ +4.5s ] [ +9.8s ]             | |
| +-----------------------------------------------------------------------------------------------------+ |
+---------------------------------------------------------------------------------------------------------+
```

### Automated Query Translation & Selective Cue Protection
* **Modality Triage:** When Vietnamese natural language is entered, the server translates visual action/scene descriptions to English for SigLIP2 while strictly preserving `ocr:` and `-v:` prefixes and Vietnamese text tokens (e.g. license plates, Vietnamese banners) for SQLite FTS5.
* **Auto-Translation Toggle:** `[x] Auto VI->EN` is enabled by default. Typing Vietnamese text and hitting `Enter` or clicking `Search` translates automatically before querying the vector index.
* **Explicit Button:** Contestants can click `[VI➜EN]` inside the search bar to preview the English translation immediately.
* **Translation Diff Banner:** Displays the original prompt and the translated prompt with a 1-click `[Revert]` button to restore original phrasing and an `[X]` dismiss button.
* **In-Memory Cache:** Cached translations return in `< 1ms` on repeated queries.

### Session Query History Chips
* **Persistent History:** The 15 most recent unique queries are stored in browser `localStorage`.
* **Rapid Backtracking:** Contestants can click any history chip below the search bar to repopulate the search bar and immediately run the search with 1 click.
* **Clear History:** A `[Clear]` button allows contestants to wipe session history between contest rounds.

### Keyboard Shortcuts Reference

| Shortcut | Scope | Action |
|---|---|---|
| `/` | Global (Grid) | Focus and select search query input |
| `Enter` | Query Input | Trigger translation (if enabled) and execute multimodal search |
| `Esc` | Query Input | Blur query input |
| `Esc` | Modal Open | Close video inspector modal and return to candidate grid |
| `Space` | Modal Open | Play / Pause video playback |
| `J` / `L` | Modal Open | Seek backward / forward 1 second |
| `Left` / `Right` Arrow | Modal Open | Step backward / forward 1 exact frame (`40ms` at 25fps) |
| `I` | Modal Open | Set Mark In timestamp to current playhead |
| `O` | Modal Open | Set Mark Out timestamp to current playhead |
| `S` | Global & Modal | 1-Click submit current playhead interval `[currentTime - 0.5s, currentTime + 0.5s]` |

---

## 5. Inputs & Outputs

* **Inputs:**
  * Source video files: [data/raw_videos/](file:///d:/UIT/TX/doan/data/raw_videos) (726 videos, ~116 GB)
  * Pre-computed keyframe thumbnails: [data/keyframes/](file:///d:/UIT/TX/doan/data/keyframes) (243,732 JPEG files)
  * Metadata & FTS5 search index: [data/metadata.db](file:///d:/UIT/TX/doan/data/metadata.db)
  * FAISS SigLIP2 index: [data/indices/visual_siglip2.index](file:///d:/UIT/TX/doan/data/indices/visual_siglip2.index)
* **Outputs:**
  * REST API responses: Candidate moments array with thumbnails, timestamps, and confidence scores
  * Live DRES submissions: Formatted payload sent to `POST /api/v2/submit/{evalId}` with integer millisecond bounds and clean video ID
  * Submission stream: Persistent local history with duplicate suppression records

---

## 6. Technical Notes & Troubleshooting

* **Hardware Constraints & VRAM Safety:**
  * The dedicated competition server operates video streaming, translation proxying, and static asset delivery purely on CPU and system memory (0 MB additional GPU VRAM).
  * The search engine and SigLIP2 model share the same memory instance; contestants can click `[Free VRAM]` in the header at any time to release model weights.
* **Translation Network Timeout & Fallback:**
  * Translation requests timeout after 2.5s. If offline or if Google Translate is unreachable, the system automatically falls back to the raw query without crashing.
* **Port Separation:**
  * The competition workstation runs on port `8001` ([src/ui/competition_server.py](file:///d:/UIT/TX/doan/src/ui/competition_server.py)).
  * The developer debug inspector remains on port `8000` ([src/ui/debug_server.py](file:///d:/UIT/TX/doan/src/ui/debug_server.py)).
  * Both servers can run simultaneously without port conflicts.
* **Duplicate Prevention:**
  * Every submitted interval `(evaluation_id, video_id, start_ms, end_ms)` is cached in-memory. Resubmitting the exact same range within the same round is automatically intercepted with `DUPLICATE_PREVENTED` to prevent penalty score deductions.
* **Resetting for a New Round:**
  * Click `[DRES Config]` in the header and select `[Clear Round Cache]` to reset the duplicate cache and submission history when a new competition query begins.
