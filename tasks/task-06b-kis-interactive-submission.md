# Task 06B: KIS Interactive Scrubber, Competition Accelerators & DRES Live Submission Console

## 1. Objectives (What)
* Develop an interactive **Human-in-the-Loop Video Scrubber & Range Selector** within the web interface to support Known-Item Search (KIS) final round workflows.
* Enable contestants to jump immediately from search candidate hits to the target video moment and scrub forward/backward to pinpoint exact event boundaries.
* Implement professional **Mark In / Mark Out** boundary markers and fine-tuning steppers (`[-5s]`, `[-1s]`, `[-0.04s]`, `[+0.04s]`, `[+1s]`, `[+5s]`) with keyboard hotkey shortcuts (`I`, `O`, `J`, `L`, `S`, `Space`, arrow keys).
* Integrate **1-Click Quick Submit @ Playhead (`+-0.5s`)** (`[Quick Submit @ Playhead]` and hotkey `S`) alongside full range submission (`[Submit Range]`) so contestants can bank points immediately upon visually confirming a frame without risking wide-interval boundary overflow.
* Implement a **Temporal Context Filmstrip Drawer (`+-15s Neighbor Keyframes`)** on candidate cards and player controls, enabling contestants to visually scan 10-15 surrounding keyframes in `< 0.5s` without waiting for video buffer streaming.
* Add **Negative Visual Filtering (`-v:`)** (e.g. `v: man speaking | -v: television news anchor in studio`) via vector orthogonal/Rocchio subtraction, and **Story-Level Video Coverage Boosting** to surface videos matching multiple clues dispersed across a broadcast report.
* Fix `video_id` filter starvation in [src/retrieval/search_engine.py](file:///d:/UIT/TX/doan/src/retrieval/search_engine.py) and generalize multi-stage sequence chaining (`N >= 2` stages) in [src/retrieval/score_fusion.py](file:///d:/UIT/TX/doan/src/retrieval/score_fusion.py).
* Provide seamless **1-Click Live DRES Submission** integrated with [src/submission/dres_client.py](file:///d:/UIT/TX/doan/src/submission/dres_client.py), complete with duplicate submission guards, dry-run/live mode toggle, real-time score decay estimation, and server response banners.

---

## 2. Technical Specifications & Implementation Steps (How)

### Step 2.0: Retrieval Bug Fixes, Negative Visual Cues (`-v:`) & Story-Level Video Boost
1. **Fix `video_id` Filter Starvation in [src/retrieval/search_engine.py](file:///d:/UIT/TX/doan/src/retrieval/search_engine.py):**
   * In `_search_visual_cue()`, when `video_id` is specified, pre-filter or search across the full index (`self._vector_index.total_vectors`) before slicing `top_k` so single-video searches never return 0 hits when that video's frames rank outside the global Top 1500.
2. **Generalize N-Stage Sequential Linking in [src/retrieval/score_fusion.py](file:///d:/UIT/TX/doan/src/retrieval/score_fusion.py):**
   * Upgrade `_link_sequential_stages()` to fold iteratively across `N >= 2` stages (`Stage 1 >> Stage 2 >> Stage 3 ...`), chaining each stage `k` with stage `k+1` within `max_sequence_gap_sec`.
3. **Negative Visual Cues (`-v:`) in [src/common/types.py](file:///d:/UIT/TX/doan/src/common/types.py), [src/retrieval/query_parser.py](file:///d:/UIT/TX/doan/src/retrieval/query_parser.py), and [src/retrieval/search_engine.py](file:///d:/UIT/TX/doan/src/retrieval/search_engine.py):**
   * Add `negative_visual_queries: List[str]` to `QueryStage` in [src/common/types.py](file:///d:/UIT/TX/doan/src/common/types.py).
   * Parse `-v: <negative_cue>` in [src/retrieval/query_parser.py](file:///d:/UIT/TX/doan/src/retrieval/query_parser.py).
   * In `_search_visual_cue()`, if the stage contains negative visual cues, compute their mean embedding `v_neg_mean`, subtract `0.35 * v_neg_mean` from each positive visual query vector `q_vec`, and L2-normalize before querying FAISS.
4. **Story-Level Video Coverage Boost in [src/retrieval/score_fusion.py](file:///d:/UIT/TX/doan/src/retrieval/score_fusion.py):**
   * Track the set of distinct cues matched across the **entire duration** of each `video_id` (`video_matched_cues[vid]`).
   * Apply a mild story-coherence bonus (`1.0 + 0.08 * (len(video_matched_cues[vid]) - 1)`) so videos containing multiple hints from a long Textual KIS prompt rise above isolated single-clue coincidences.

---

### Step 2.1: Backend DRES Proxy & Temporal Filmstrip Endpoints in [src/ui/debug_server.py](file:///d:/UIT/TX/doan/src/ui/debug_server.py)
1. **Temporal Context Filmstrip Endpoint (`GET /api/videos/{video_id}/context`):**
   * Query parameters: `timestamp_sec: float`, `window_sec: float = 15.0`.
   * Returns all keyframes and OCR snippets from [data/metadata.db](file:///d:/UIT/TX/doan/data/metadata.db) for `video_id` within `[timestamp_sec - window_sec, timestamp_sec + window_sec]` in `< 5ms`.
2. **Submit Endpoint (`POST /api/dres/submit`):**
   * Accepts JSON body: `{ "video_id": str, "start_sec": float, "end_sec": float, "evaluation_id": Optional[str], "dry_run": bool }`.
   * Invokes `DRESClient.submit_kis()` from [src/submission/dres_client.py](file:///d:/UIT/TX/doan/src/submission/dres_client.py) (or simulates submission in `dry_run` mode when testing offline).
   * Validates boundaries (`0 <= start_sec <= end_sec`, non-empty video ID).
   * Records submission in server history and returns status (`ACCEPTED`, `WRONG`, `DUPLICATE_PREVENTED`, or `DRY_RUN_OK`), payload, and updated score calculation.
3. **Session & Status Endpoints (`GET /api/dres/status`, `POST /api/dres/session`, `POST /api/dres/clear-cache`):**
   * Manages DRES base URL, session token, active evaluation discovery, username/password login, and duplicate cache reset for a new competition query.

---

### Step 2.2: Interactive Video Scrubber & Fine Stepper Controls
Add fine-stepping navigation directly below the video player in [src/ui/static/index.html](file:///d:/UIT/TX/doan/src/ui/static/index.html):
* **Stepping Buttons:**
  * Fast Seek: `[-5s]` and `[+5s]`
  * Medium Seek: `[-1s]` and `[+1s]`
  * Frame Stepping: `[-0.04s]` and `[+0.04s]` (corresponding to 1 frame at 25 fps)
* **Keyboard Hotkeys (Active when not typing in an input field):**
  * `J`: Seek backward 1 second.
  * `L`: Seek forward 1 second.
  * `Left Arrow`: Step backward 1 frame (`0.04s`).
  * `Right Arrow`: Step forward 1 frame (`0.04s`).
  * `Space`: Toggle play / pause.
  * `I`: Mark In (set current video timestamp as Start Time).
  * `O`: Mark Out (set current video timestamp as End Time).
  * `S`: Quick Submit at current playhead (`[currentTime - 0.5s, currentTime + 0.5s]`).

---

### Step 2.3: Mark In / Mark Out Range Selection & Interval Preview Panel
Create a dedicated range selector and KIS submission console in the player pane:
1. **Timestamp Inputs & Stamping:**
   * `Start Time (s)` numeric input with button `[Set In (I)]`.
   * `End Time (s)` numeric input with button `[Set Out (O)]`.
   * `Duration` badge: `(End - Start)s` and millisecond range `[start_ms - end_ms]`.
2. **Quick Preset Fillers:**
   * `[Shot Bounds]`: Fills `start_sec` and `end_sec` from the active shot in [data/metadata.db](file:///d:/UIT/TX/doan/data/metadata.db).
   * `[Playhead +-0.5s]`: Sets tight 1-second interval `[currentTime - 0.5s, currentTime + 0.5s]`.
   * `[Playhead +-2.5s]`: Centers a 5-second interval `[currentTime - 2.5s, currentTime + 2.5s]`.
3. **Visual Timeline Range Highlight:**
   * Render a highlighted range overlay (`#timelineRangeOverlay`) on `#shotTimeline` spanning from `start_sec` to `end_sec`.
4. **Pre-submission Interval Preview Player (`[Play Range]`):**
   * Seeks video player to `start_sec`, plays continuously, and automatically pauses when `currentTime >= end_sec`.

---

### Step 2.4: 1-Click DRES Submission, Filmstrip Drawer & Live Score Widget
1. **Dual Submission Triggers:**
   * **`[Quick Submit @ Playhead (S)]`:** Immediately submits `[currentTime - 0.5s, currentTime + 0.5s]` for the active video in 1 click.
   * **`[Submit Selected Range]`:** Submits the explicit `[start_sec, end_sec]` range configured in the Mark In/Out inputs.
   * **Card-Level Actions:** Every candidate moment card includes `[Filmstrip +-15s]`, `[Filter Video]`, and `[Quick Submit]` buttons.
2. **Live Query Timer & Score Predictor Widget:**
   * Stopwatch timer tracking elapsed seconds `t` for the active query (selectable `t_L = 300s` Textual KIS or `240s` Video KIS) with `[Start/Reset Timer]` and `[-10pt Wrong Attempt]` controls.
   * Real-time score display using `calculate_kis_score()`:
     `S_acc = max(0, 50 - 10 * w_s)`, `S_time = 50 * (1 - t / t_L)`, `Total = S_acc + S_time`.
3. **Response Toast Banner & Submission Log:**
   * Displays immediate visual confirmation (`[OK]`, `[WARNING]`, `[ERROR]`) and maintains a collapsible session submission history.

---

## 3. Architecture & Data Flow

```text
[Search Candidate Card]
   ├─► Click [Filmstrip +-15s] ──► GET /api/videos/{id}/context ──► Instant 15-Frame Strip (< 5ms)
   ├─► Click [Quick Submit]    ──► POST /api/dres/submit        ──► Immediate 1s Center Submit
   └─► Click Card              ──► Video Player seeks to start_sec & fills [start_sec, end_sec]
                                            │
                                            ▼
                      [Fine Stepper (-5s, -1s, -0.04s, +0.04s, +1s, +5s)]
                      [Hotkeys: J, L, Arrows, I (In), O (Out), S (Quick Submit)]
                                            │
                                            ▼
                      [Click [Play Range] -> Verifies [start_sec, end_sec]]
                                            │
                                            ▼
                      [Click [Submit Range] or [Quick Submit @ Playhead]]
                                            │
                                            ▼
                      [src/submission/dres_client.py] (Duplicate Guard & Millisecond Format)
```

---

## 4. Verification & Acceptance Criteria
1. **Retrieval Bug Fixes & Negative Cue Test:**
   * Verify `QueryParser.parse("v: man speaking | -v: studio news anchor")` extracts positive and negative visual cues.
   * Verify 3-stage sequential query `A >> B >> C` chains all 3 stages in `TemporalMomentFusor`.
   * Verify single-video search (`video_id="L13_V001"`) returns matching keyframes even when they rank outside global Top 1500.
2. **Filmstrip Context Endpoint Test:**
   * Call `GET /api/videos/L13_V001/context?timestamp_sec=50.0&window_sec=15.0` and verify surrounding keyframes are returned in chronological order.
3. **Frame-Accurate Seeking & Range Preview Test:**
   * Verify steppers (`+-0.04s`, `+-1s`, `+-5s`), hotkeys (`I`, `O`, `J`, `L`), timeline range overlay, and auto-pause on `[Play Range]`.
4. **DRES Submission & Duplicate Suppression Test:**
   * Submit via `POST /api/dres/submit` in dry-run mode -> Verify compliant DRES payload and duplicate suppression on second click.
