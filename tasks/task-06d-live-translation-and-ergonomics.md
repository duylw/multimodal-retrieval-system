# Task 06D: Automated Query Translation & Ergonomic Competition Accelerators

**Status:** `[DONE]` Completed
**Target Milestone:** Milestone 4 Extension
**Server Component:** [src/ui/competition_server.py](file:///d:/UIT/TX/doan/src/ui/competition_server.py) (Port 8001)
**Frontend Client:** [src/ui/competition/](file:///d:/UIT/TX/doan/src/ui/competition)
**Unit Tests:** [tests/test_competition_workstation.py](file:///d:/UIT/TX/doan/tests/test_competition_workstation.py)
**Documentation:** [docs/guides/competition-workstation-guide.md](file:///d:/UIT/TX/doan/docs/guides/competition-workstation-guide.md)

---

## 1. Objectives (What)
* Equip the KIS Competition Workstation with **High-Speed Automated Query Translation (Google Translate)**:
  * Enable contestants to type natural Vietnamese queries (e.g., `xe buyt mau xanh chay qua nga tu | ocr: 51B`) and have the visual descriptions automatically translated into English (`a blue bus driving through an intersection | ocr: 51B`) to match SigLIP2's English WebLI training distribution, while preserving Vietnamese OCR tokens intact for SQLite FTS5.
  * Implement both an explicit `[Translate VI -> EN]` button and an automatic background translation toggle (`[x] Auto-translate on search`).
* Implement **Modality-Aware Auto-Triage**:
  * Automatically parse natural language queries, separating visual action/object keywords for English translation from on-screen text, license plates, and TV channel labels that must remain in Vietnamese.
* Add **Competition Query History & Iteration Chips**:
  * Store search queries entered during the competition session in client memory (`localStorage`).
  * Render clickable history chips below the search bar for 1-click query restoration, parameter tweaking, and rapid backtracking.
* Implement **Comprehensive Single-Hand Keyboard Ergonomics**:
  * Allow full competition search, scrubbing, previewing, and submission without forcing the contestant to repeatedly shift between mouse and keyboard.
* Author a practical feature usage guide in [docs/guides/competition-workstation-guide.md](file:///d:/UIT/TX/doan/docs/guides/competition-workstation-guide.md).

---

## 2. Technical Specifications & Implementation Steps (How)

### Step 2.0: Backend Google Translation Service
In [src/ui/competition_server.py](file:///d:/UIT/TX/doan/src/ui/competition_server.py):
1. **Endpoint `POST /api/translate`:**
   * Accepts JSON payload: `{ "query": str, "source_lang": str = "vi", "target_lang": str = "en" }`.
   * Uses asynchronous `httpx.AsyncClient` to query the lightweight Google Translate service:
     `https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=en&dt=t&q={text}`
   * Operates with 0 additional package dependencies (leveraging existing `httpx`).
2. **Selective Cue Translation (Protecting OCR blocks):**
   * If the query contains explicit `ocr:` or `-v:` prefixes:
     * Extract and isolate the OCR tokens (e.g. `ocr: "Bản tin 19h"`, `ocr: 51B-12345`).
     * Translate only the visual portions into English.
     * Recombine into a structured multi-cue query string: `v: {translated_english} | ocr: {original_vietnamese}`.
3. **In-Memory Translation Cache:**
   * Maintain an in-memory LRU dictionary cache mapping raw queries to translated outputs for instantaneous (0ms) response on repeated requests.
4. **Graceful Offline Fallback:**
   * If the network is restricted or the translation endpoint times out (> 2.0s), fall back seamlessly to the raw input string with a warning badge `[WARN: Using Raw Query]`.

---

### Step 2.1: Frontend Translation Controls & Real-Time Feedback
In `src/ui/competition/index.html` and `src/ui/competition/app.js`:
1. **Search Form Controls:**
   * Add a `[Translate (VI -> EN)]` button directly inside the query bar.
   * Add a toggle checkbox: `[x] Auto-translate on search` (checked by default).
2. **Translation Preview & Diff Pill:**
   * When a query is translated, display an expandable badge showing both the original Vietnamese prompt and the English visual query used for SigLIP2.
   * Allow contestants to manually edit the translated English text if they want to fine-tune adjectives or verbs before searching.

---

### Step 2.2: Competition Query History & Fast Refinement Chips
In `src/ui/competition/`:
1. **Session Query Storage:**
   * Save successful search queries to browser `localStorage` under key `kis_competition_query_history`.
   * Cap history at 15 recent unique queries.
2. **History Chips Bar:**
   * Render horizontal chips directly under the search bar:
     `[v: blue truck | ocr: 51B]`, `[v: woman supermarket]`, `[ocr: HTV9]`
   * Clicking a chip immediately populates the query input and runs the search in 1 click.
   * Include a small `[Clear History]` button.

---

### Step 2.3: Global Keyboard Shortcuts & Ergonomic Accelerator Workflow
Implement global hotkey listeners active across the competition workstation:
* `/`: Jump focus directly into the search input bar.
* `Enter` (inside search bar): Trigger translation and execute search immediately.
* `Esc`: Close the video pop-up modal and restore focus to candidate grid.
* `Space`: Toggle play/pause for video modal player.
* `J` / `L`: Seek video backward / forward 1.0 second.
* `Left` / `Right` Arrow: Step video backward / forward 1 frame (`0.04s`).
* `I`: Mark In (sets current playhead as target Start Time).
* `O`: Mark Out (sets current playhead as target End Time).
* `S`: Instant 1-click Quick Submit at playhead (`+-0.5s`) for the active video.

---

### Step 2.4: Comprehensive Competition Guide
Author practical documentation in [docs/guides/competition-workstation-guide.md](file:///d:/UIT/TX/doan/docs/guides/competition-workstation-guide.md) following the `feature-documentation-guide` skill:
* Overview of KIS Competition Workstation vs Debug Inspector.
* CLI Quick Start: `uv run python -m src.ui.competition_server --port 8001`.
* Contestant Workflow: Query input -> Auto-translation -> Grid scanning -> Modal verification -> 1-click DRES submission.
* Keyboard hotkey reference table.
* Troubleshooting & DRES submission guardrails.

---

## 3. Architecture & Data Flow

```text
[Contestant Vietnamese Query]
          │
          ▼
[Translation Middleware (POST /api/translate)]
  ├── Preserve OCR Cues: "ocr: 51B" (Unchanged Vietnamese)
  └── Translate Visual Cues: "xe buyt mau xanh" ──► "blue bus"
          │
          ▼
[Parsed Multi-Cue Query: "v: blue bus | ocr: 51B"]
          │
          ▼
[Search Engine (SigLIP2 Vector Index + SQLite FTS5)]
          │
          ▼
[High-Density Frame Grid (Top-to-Bottom, Left-to-Right)]
          ├── Contestant scans 12-20 moments simultaneously
          ├── 1-Click Card Submit ──► DRES Live API v2 (< 150ms)
          └── Click Thumbnail ──► [Modal Video Player @ Exact Timestamp]
                                        ├── Fine-stepper scrubbing (J/L, Left/Right)
                                        └── Hotkey S Submit ──► DRES Live API v2
```

---

## 4. Hardware Constraints & Verification Criteria
* **Hardware Budget (GTX 1650 4GB):**
  * Translation runs via asynchronous HTTP requests on CPU (0MB GPU VRAM).
  * Video modal and grid rendering consume standard browser memory (< 200MB RAM).
* **Latency & Performance Criteria:**
  * Translation turnaround: `< 250ms` (cached queries: `< 1ms`).
  * Hotkey reaction time: `< 20ms`.
  * Total time from typing query to viewing 100 candidate frames in grid: `< 800ms`.
* **Deliverables:**
  * Backend translation service in [src/ui/competition_server.py](file:///d:/UIT/TX/doan/src/ui/competition_server.py).
  * Frontend query translator, history chips, and hotkey accelerators in `src/ui/competition/`.
  * Usage documentation in [docs/guides/competition-workstation-guide.md](file:///d:/UIT/TX/doan/docs/guides/competition-workstation-guide.md).
