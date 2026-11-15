# User Guide: Dedicated KIS Competition Workstation UI & Modal Video Inspector

## 1. Feature Overview
* **What it does:** The KIS Competition Workstation is a standalone, distraction-free web interface dedicated to live Known-Item Search (KIS) contest performance. It decouples high-speed contest submission workflows from internal debug inspectors, providing a Zero-Popup Split Cockpit layout: a Compact Top-Header Timer Capsule, a `~65%` Left Candidate Scan Canvas (`Frames` / `By Video`), and a `~35%` Persistent Right Verification & Submit Dock (with optional Pop-up Modal expansion).
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
+---------------------------------------------------------------------------------------------------+
| [KIS] | Visual Query [VI->EN][X] | [Search] | [04:12/05:00 Start Reset +1W 100pts] [DRY-RUN] [VRAM]|
| OCR [Boost|Filter] | [-v Exclude] | [+Scene] | [Hybrid|Visual|OCR] [Batches(24)] [Limit]        |
+---------------------------------------------------------------------------------------------------+
| [Recent: [v: blue bus | ocr: 51B] [v: woman supermarket] [Clear] ]                                 |
+---------------------------------------------------+-----------------------------------------------+
| CANDIDATES (300)        [View: Frames | By Video] | INSPECTOR: L18_V004 @ 01:24.5 [Popup] [Hide]  |
| +--------+ +--------+ +--------+ +--------+       | +-------------------------------------------+ |
| | #1     | | #2     | | #3     | | #4     |       | |         HTML5 Video Player (HTTP 206)     | |
| | L18_V4 | | L05_V2 | | L21_V9 | | L12_V1 |       | +-------------------------------------------+ |
| | [Sim]  | | [Sim]  | | [Sim]  | | [Sim]  |       | ====|======|============|================     |
| +--------+ +--------+ +--------+ +--------+       |     ^ Amber Timeline Hit Markers (1-click seek) |
| +--------+ +--------+ +--------+ +--------+       | [-5s][-1s][-1f][Play][+1f][+1s][+5s] [I] [O]  |
| | #5     | | #6     | | #7     | | #8     |       | Neighbor Filmstrip (+-10s): [ ][ ][*][ ][ ]   |
| | ...    | | ...    | | ...    | | ...    |       | Target: L18_V004 [84.00 - 85.00] [Tight][Shot]|
| +--------+ +--------+ +--------+ +--------+       | [ SUBMIT PLAYHEAD (S) ]  [ SUBMIT RANGE ]     |
|                                                   | Recent Submissions (Stream)                   |
+---------------------------------------------------+-----------------------------------------------+
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
* **Visual-First OCR (`Boost` vs `Filter`) & Sequential `+ Scene` Search (Task 07A):**
  * Use the inline **OCR text** field next to the main query bar to keep on-screen text untranslated in Vietnamese while `Auto VI➜EN` translates only visual cues. Choose **`Boost`** when text is uncertain (visual ranking stays primary with a quality-gated bonus) or **`Filter`** when an exact plate/title must appear in the video.
  * Click **`+ Scene`** to open **Scene 2**, pick which scene is the **Anchor** (rarest/clearest scene), and set the chronological **Gap** (`1-15s`, `1-30s`, `1-60s`, `2-120s`) to run Two-Phase Anchor-then-Scan linking.
* **Instant Keyframe Similarity, Exclude (`-v`), Video Blacklist & Batch Scope (Task 07B):**
  * Click **`Sim`** on any candidate card or hover a temporal filmstrip frame and click **`Sim`** to pin a `[Ref: <video> @ <time>]` pill in the search bar and query visually similar frames (`POST /api/search/similar`) via `0ms` FAISS `reconstruct()` without loading SigLIP2 text inference when the visual box is empty. Adding visual text while a Ref pill is pinned steers the similarity vector (`steer_alpha = 0.3`).
  * Use the red **`-v Exclude...`** box next to OCR to push away unwanted concepts (comma-separated, automatically translated when `Auto VI➜EN` is enabled).
  * Click **`Hide`** on any candidate card to remove wrong videos from the grid and exclude them from future server searches (`Hidden: N videos [Reset]`), or toggle **`Only`** to drill down inside a single video.
* **Configurable Batch Scope (Task 07B):**
  * Click **`Batches: All (24)`** in the search controls bar to scope searches to specific competition batches (`All`, `L01-L12`, `L13-L24`, or custom selections persisted in `localStorage`) directly at retrieval time so non-target batches never waste top-K slots.
* **Video Grouping Strips (`By Video`) & Dual-Frame Sequential Cards (Task 07C):**
  * Toggle **`[Frames | By Video]`** in the canvas header to switch instantaneously (client-side `< 30ms`, persisted in `localStorage`) between the flat candidate grid and a per-video strip view ordered by peak score with up to 7 chronologically sorted hit thumbnails per video.
  * When running sequential (`+ Scene` / `>>`) searches, cards automatically split into side-by-side **Stage 1 / Stage 2** thumbnails with a centered `+Δt` interval pill. Clicking either thumbnail opens the video player seeked directly to that stage's timestamp while setting default Mark In/Out bounds to the `[t1, t2]` sequence span (capped at 20s).
* **Zero-Popup Split Cockpit Layout & Timeline Hit Markers (Task 07D):**
  * Competition stopwatch, `+1W` wrong-attempt badge, and expandable predicted score breakdown sit cleanly in the top header capsule, leaving ~65% width for candidate scanning and ~35% for the persistent Right Verification & Submit Dock (`Layout: Cockpit`).
  * Clicking any candidate card loads the stream directly inside the Right Inspector alongside an inline `+-10s` neighbor filmstrip and Target Submit controls without throwing a backdrop modal over the grid (click **`Popup`** anytime for full-screen expansion).
  * Amber **Timeline Hit Markers** appear automatically along the scrubber bar at every matched candidate timestamp inside the active video so contestants can jump between intra-video hits in 1 click.
