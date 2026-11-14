# Task 06C: Dedicated KIS Competition Workstation UI & Modal Video Inspector

## 1. Objectives (What)
* Separate the competition workflow from internal debugging by building a standalone, distraction-free **KIS Competition Workstation** dedicated to live contest performance.
* Implement a dual-zone ergonomic layout optimized for speed, visual clarity, and muscle memory ("thuận tiện, thuận tay, thuận mắt"):
  * **Left Docked Sidebar / Drawer (KIS Command Center):** Persistent submission console displaying live DRES session/evaluation status, competition countdown timer (300s/240s) with live score decay estimation, active submission target coordinates, instant preset range setters (`Tight +-0.5s`, `Shot`, `Window +-2.5s`), and a real-time submission response history stream.
  * **Right Main Canvas (High-Density Frame Grid):** Full-bleed responsive multi-column grid displaying retrieved candidate moments top-to-bottom and left-to-right with high visual density (3 to 5 columns), large 16:9 thumbnail previews, rank badges (`#1`, `#2`, `#3`), moment timestamps, score pills, and detected OCR text snippets.
* Build an **Interactive Modal Video Inspector & Pop-up Player**:
  * Clicking any candidate frame instantly triggers a focused pop-up video player with the playhead positioned directly at that frame's exact timestamp, without losing the contestant's scroll position in the candidate grid.
  * Embed full fine-stepper scrubbers (`[-5s]`, `[-1s]`, `[-1f]`, `[+1f]`, `[+1s]`, `[+5s]`), Mark In (`I`), Mark Out (`O`), Range Playback, and Quick Submit (`S`).
  * Include a docked section toggle for contestants who prefer keeping video docked alongside candidate cards.
* Equip every candidate grid card with a prominent emerald green **`[Submit KIS]`** button for instant 1-click submission of `[start_ms, end_ms]` in `< 150ms`.

---

## 2. Technical Specifications & Implementation Steps (How)

### Step 2.0: Standalone Competition Server Entry Point
Create a dedicated server runner in [src/ui/competition_server.py](file:///d:/UIT/TX/doan/src/ui/competition_server.py):
* Dedicated FastAPI application separate from [src/ui/debug_server.py](file:///d:/UIT/TX/doan/src/ui/debug_server.py).
* Runs on a dedicated port (default `8001`, configurable via `--port` and `--host`) serving assets from `src/ui/competition/` (`index.html`, `style.css`, `app.js`).
* Imports and shares existing core engines from [src/retrieval/search_engine.py](file:///d:/UIT/TX/doan/src/retrieval/search_engine.py), [src/indexers/metadata_db.py](file:///d:/UIT/TX/doan/src/indexers/metadata_db.py), and [src/submission/dres_client.py](file:///d:/UIT/TX/doan/src/submission/dres_client.py).
* Exposes clean, competition-critical REST endpoints:
  * `GET /api/search/multimodal`: Multimodal multi-cue search with Top-K selection (25, 50, 100, 200).
  * `GET /api/videos/{video_id}/stream`: HTTP 206 partial content video streaming.
  * `GET /api/keyframes/{video_id}/{filename}`: Keyframe thumbnail serving with browser caching.
  * `GET /api/videos/{video_id}/context`: Temporal context filmstrip (`+-15s` neighbor keyframes).
  * `POST /api/dres/submit`: Live / dry-run DRES API v2 submission with duplicate suppression.
  * `GET /api/dres/status`: Current DRES connection status, active eval ID, and submission history.
  * `POST /api/dres/session`: DRES login credentials and session configuration.

---

### Step 2.1: Left KIS Command Center Drawer Layout
Construct the persistent left drawer in `src/ui/competition/index.html` and `src/ui/competition/style.css`:
1. **DRES Status Header:**
   * Active competition status badge: `[LIVE DRES]` (emerald) or `[DRY-RUN]` (amber).
   * Session ID, Evaluation ID (`inputDresEvalId`), and server base URL.
2. **Competition Stopwatch & Live Score Decay Simulator:**
   * Prominent digital countdown timer tracking elapsed seconds `t` against task limit `t_L = 300s` (Textual KIS) or `240s` (Visual KIS).
   * Single-click `[Start / Pause]` and `[Reset Timer]` buttons.
   * Wrong attempt counter (`+1 Wrong (-10 pts)`) with live score predictor:
     `S_acc = max(0, 50 - 10 * w_s)`, `S_time = 50 * (1 - t / t_L)`, `S_total = S_acc + S_time`.
3. **Active Submission Target Card:**
   * Displays targeted `Video ID`, `Start (s)`, `End (s)`, duration, and millisecond bounds `[start_ms - end_ms]`.
   * Presets: `[Tight +-0.5s]`, `[Shot Bounds]`, `[Window +-2.5s]`.
4. **Primary Submission Buttons:**
   * `[Submit Target Range]`: Submits the current Mark In/Out interval to DRES.
   * `[Submit Playhead +-0.5s (Hotkey S)]`: Instant submission centered around current video playhead.
5. **Real-time Submission Stream:**
   * Scrollable history feed of all submissions in the active round with status pills: `[CORRECT]`, `[WRONG]`, `[DUPLICATE]`, `[DRY-RUN OK]`.

---

### Step 2.2: Right Main Canvas - High-Density Frame Grid
Design the full-screen candidate results grid in `src/ui/competition/`:
1. **Top Search & Filter Bar:**
   * Clean search input with clear button `[X]`.
   * Quick modality toggles: `[Hybrid]`, `[Visual Only]`, `[OCR Only]`.
   * Scope toggles: `[x] DRES Batches Only` (defaults to active batches `L01-L12`, `L21-L23`), `[ ] Current Video Only`.
   * Results dropdown: `25`, `50`, `100` (selected), `200` moments.
2. **Top-to-Bottom, Left-to-Right Responsive Grid:**
   * CSS Grid layout: `grid-template-columns: repeat(auto-fill, minmax(280px, 1fr))` with 12px gap.
   * High density: displays 12-20 moments simultaneously on standard 1080p displays.
3. **Candidate Card Design:**
   * Large 16:9 thumbnail keyframe with lazy loading.
   * Rank badge pill: `#1` (gold), `#2` (silver), `#3` (bronze), `#4+` (dark slate).
   * Consensus badge (`[Consensus: 2 Cues]`) and DRES batch status pill.
   * Video ID, formatted time (`02:15.50 - 02:20.50`), and score pill.
   * Text snippet badge displaying detected OCR text with ellipsis.
   * Action buttons:
     * Full-width emerald green `[Submit KIS]` button at the bottom of the card.
     * Auxiliary pills: `[Play Video]`, `[Filmstrip +-15s]`, `[Only Video]`.

---

### Step 2.3: Interactive Modal Video Player & Pop-up Inspector
Implement the instant pop-up inspection player in `src/ui/competition/`:
1. **Modal Popup Window (`#videoModal`):**
   * Centered overlay dialog with backdrop blur, opened immediately upon clicking any candidate card thumbnail.
   * Video element configured with HTTP 206 streaming and plays immediately at the card's `start_sec`.
2. **Integrated Player Controls:**
   * Current timestamp display, total duration, and frame number.
   * Fine-stepper controls: `[-5s]`, `[-1s]`, `[-0.04s]`, `[Play/Pause]`, `[+0.04s]`, `[+1s]`, `[+5s]`.
   * Mark In (`[Set In (I)]`) and Mark Out (`[Set Out (O)]`) buttons with range slider bar.
   * `[Play Selected Range]` button to preview exact submission interval.
   * `[Submit Range]` and `[Submit Playhead (S)]` buttons directly inside modal.
3. **Keyboard Accelerators:**
   * `Esc`: Close modal and immediately restore focus to the candidate grid.
   * `Space`: Play / Pause video.
   * `J` / `L`: Seek backward / forward 1 second.
   * `Left` / `Right` Arrow: Step backward / forward 1 frame (40ms).
   * `I` / `O`: Set Mark In / Mark Out bounds.
   * `S`: Submit playhead interval `[currentTime - 0.5s, currentTime + 0.5s]`.
4. **Docked Section Mode:**
   * Header toggle allowing contestant to pin the video player to a top or right panel if they prefer a split view over a modal pop-up.

---

## 3. Architecture & UI Layout Diagram

```text
+---------------------------------------------------------------------------------------------------------+
|                                    KIS COMPETITION WORKSTATION                                          |
| [Query Input: "v: blue truck | ocr: 51B"                 ] [Search]  Results:[ 100 v ] [x] DRES Batches |
+------------------------------------+--------------------------------------------------------------------+
| LEFT: KIS COMMAND CENTER (DRAWER)  | RIGHT: HIGH-DENSITY FRAME GRID (TOP-DOWN, LEFT-TO-RIGHT)           |
|                                    |                                                                    |
| [LIVE DRES: team06_t4] [Eval ID]   | +--------------------+ +--------------------+ +------------------+ |
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
| Submission History:                |                                                                    |
| - L05_V014 [22-27s] -> [WRONG]     |                                                                    |
| - L13_V016 [25-32s] -> [CORRECT]   |                                                                    |
+------------------------------------+--------------------------------------------------------------------+
| OPTIONAL MODAL VIDEO POP-UP (Opens over grid on thumbnail click):                                       |
| +-----------------------------------------------------------------------------------------------------+ |
| | Video: L05_V014 @ 00:22.72 / 12:45.00                                                         [X]   | |
| | [                           VIDEO STREAM PLAYER (HTTP 206)                                        ] | |
| | Controls: [-5s] [-1s] [-1f] [ > Play ] [+1f] [+1s] [+5s]  | Mark In: 22.0s (I)  Mark Out: 23.0s (O) | |
| | [Play Range]  [ SUBMIT RANGE ]  [ SUBMIT PLAYHEAD (S) ]                                             | |
| +-----------------------------------------------------------------------------------------------------+ |
+---------------------------------------------------------------------------------------------------------+
```

---

## 4. Hardware Constraints & Verification Criteria
* **Hardware Budget (NVIDIA GTX 1650 4GB):**
  * The dedicated competition server uses zero additional GPU VRAM; video streaming and static asset delivery operate purely on CPU and memory.
  * Shared FAISS index and SigLIP2 singleton models remain managed by `SearchEngine` in memory.
* **Latency & Performance Criteria:**
  * Modal pop-up invocation: `< 50ms`.
  * Candidate card grid rendering for 100 moments: `< 100ms`.
  * DRES submission turnaround via client proxy: `< 200ms`.
* **Deliverables:**
  * [src/ui/competition_server.py](file:///d:/UIT/TX/doan/src/ui/competition_server.py)
  * [src/ui/competition/index.html](file:///d:/UIT/TX/doan/src/ui/competition/index.html)
  * [src/ui/competition/style.css](file:///d:/UIT/TX/doan/src/ui/competition/style.css)
  * [src/ui/competition/app.js](file:///d:/UIT/TX/doan/src/ui/competition/app.js)
  * [docs/guides/competition-workstation-guide.md](file:///d:/UIT/TX/doan/docs/guides/competition-workstation-guide.md)

---

## 5. Verification & Acceptance
* [x] **Status:** `COMPLETED` (Nov 14, 2026)
* [x] Dedicated FastAPI competition server running on port `8001` completely separate from developer debug server (`8000`).
* [x] Dual-zone layout with persistent Left KIS Command Center Drawer + Right High-Density Frame Grid displaying 12-20 moments simultaneously.
* [x] Interactive Modal Video Inspector auto-seeked on thumbnail click, with full stepper controls (`[-5s]`, `[-1s]`, `[-1f]`, `[+1f]`, `[+1s]`, `[+5s]`), Mark In/Out, range preview, and single-hand hotkeys (`Space`, `J`, `L`, `Left/Right`, `I`, `O`, `S`).
* [x] Direct 1-click `[Submit KIS]` button on every candidate card, plus duplicate prevention cache and live score decay simulation.

