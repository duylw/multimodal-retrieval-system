# Task 06B: KIS Interactive Scrubber & DRES Live Submission Console

## 1. Objectives (What)
* Develop an interactive **Human-in-the-Loop Video Scrubber & Range Selector** within the web interface to support Known-Item Search (KIS) final round workflows.
* Enable contestants to jump immediately from search candidate hits (discrete keyframes or rough shot bounds) to the target video moment and scrub forward/backward to pinpoint exact event boundaries.
* Implement professional **Mark In / Mark Out** boundary markers and fine-tuning steppers (`[-5s]`, `[-1s]`, `[-frame]`, `[+frame]`, `[+1s]`, `[+5s]`) with keyboard hotkey shortcuts (`I`, `O`, `J`, `L`, `Space`, arrow keys).
* Integrate pre-submission interval playback (`[▶ Play Range]`) so contestants can visually verify the complete event within `[start_ms, end_ms]` prior to submitting, eliminating the severe -10 point penalty for incorrect guesses.
* Provide seamless **1-Click Live DRES Submission** integrated with [src/submission/dres_client.py](file:///d:/UIT/TX/doan/src/submission/dres_client.py), complete with duplicate submission guards, real-time score decay estimation, and server response banners.

---

## 2. Technical Specifications & Implementation Steps (How)

### Step 2.1: Backend DRES Proxy Endpoints in [src/ui/debug_server.py](file:///d:/UIT/TX/doan/src/ui/debug_server.py)
1. **Submit Endpoint (`POST /api/dres/submit`):**
   * Accepts JSON body: `{ "video_id": str, "start_sec": float, "end_sec": float, "evaluation_id": Optional[str] }`.
   * Invokes `DRESClient.submit_kis()` from [src/submission/dres_client.py](file:///d:/UIT/TX/doan/src/submission/dres_client.py).
   * Validates boundaries (`0 <= start_sec <= end_sec`, non-empty video ID, maximum duration <= 60s).
   * Returns server status, HTTP status, and updated submission attempt count for the active query.
2. **Session & Status Endpoint (`GET /api/dres/status`):**
   * Returns current DRES connection status, active session ID, active evaluation ID, and submitted moment history.
3. **Session Configuration Endpoint (`POST /api/dres/session`):**
   * Allows setting or refreshing the team session token and discovering active evaluations via `DRESClient.get_active_evaluation()`.

### Step 2.2: Interactive Video Scrubber & Fine Stepper Controls
Add fine-stepping navigation directly below the video player in [src/ui/static/index.html](file:///d:/UIT/TX/doan/src/ui/static/index.html):
* **Stepping Buttons:**
  * Fast Seek: `[-5s]` and `[+5s]`
  * Medium Seek: `[-1s]` and `[+1s]`
  * Frame Stepping: `[-0.04s]` and `[+0.04s]` (corresponding to 1 frame at 25 fps)
* **Keyboard Hotkeys:**
  * `J`: Seek backward 1 second.
  * `L`: Seek forward 1 second.
  * `Left Arrow`: Step backward 1 frame (0.04s).
  * `Right Arrow`: Step forward 1 frame (0.04s).
  * `Space`: Toggle play / pause.
  * `I`: Mark In (set current video timestamp as Start Time).
  * `O`: Mark Out (set current video timestamp as End Time).

### Step 2.3: Mark In / Mark Out Range Selection Panel
Create a dedicated range selector panel below the scrubber controls:
1. **Timestamp Inputs & Stamping:**
   * `Start Time` input (seconds / formatted `MM:SS.ss`) with button `[⏱️ Set In (I)]`.
   * `End Time` input (seconds / formatted `MM:SS.ss`) with button `[⏱️ Set Out (O)]`.
   * `Duration` display: `(End - Start) seconds`.
2. **Quick Preset Fillers:**
   * `[Use Shot Bounds]`: Fills `start_sec` and `end_sec` directly from the enclosing shot record in [data/metadata.db](file:///d:/UIT/TX/doan/data/metadata.db).
   * `[Window ±2.5s]`: Centers a 5-second interval around the current playhead position `[currentTime - 2.5s, currentTime + 2.5s]`.
3. **Visual Timeline Range Highlight:**
   * Render an interactive colored overlay on `#shotTimeline` spanning from `start_sec` to `end_sec` to give instant visual feedback of the selected submission interval.

### Step 2.4: Pre-submission Interval Preview Player
* **Preview Action (`[▶ Play Selected Range]`):**
  * Seeks video player to `start_sec` and plays continuously.
  * Attaches a time-update listener that automatically pauses playback when `currentTime >= end_sec`.
  * Allows the contestant to confirm with 100% certainty that the target event is fully contained within the interval.

### Step 2.5: 1-Click Submission & Live Competition Score Widget
1. **Submission Trigger (`[🚀 Submit to DRES]`):**
   * Prominently displays: `Target: {video_id} | Range: {start_ms}ms - {end_ms}ms ({duration}s)`.
   * Formats payload via `create_kis_submission_payload()` in [src/submission/dres_client.py](file:///d:/UIT/TX/doan/src/submission/dres_client.py).
   * Checks local duplicate cache before sending HTTP request to prevent server rejection.
2. **Live Query Timer & Score Predictor Widget:**
   * Stopwatch timer tracking elapsed seconds `t` for the current query (out of `t_L = 300s` for Textual KIS or `240s` for Video KIS).
   * Real-time score calculator using `calculate_kis_score()`:
     `S_acc = max(0, 50 - 10 * w_s)`
     `S_time = 50 * (1 - t / t_L)`
     `Estimated Total = S_acc + S_time`
   * Displays wrong submission counter `w_s` with warning badges.
3. **Response Toast Banner:**
   * Green banner: `[OK] Submission ACCEPTED / CORRECT! (Score: +88.5 pts)`.
   * Red banner: `[WRONG] Server response: INCORRECT (-10 point penalty. Wrong attempts: 1)`.
   * Yellow banner: `[DUPLICATE] Moment already submitted for this query. No penalty incurred.`

---

## 3. Architecture & Data Flow

```text
[Search Result Hit (Keyframe / Shot)]
                 │
                 ▼ Click candidate card
[Video Player seeks to t = timestamp_sec]
[Auto-fill default range: shot.start_sec -> shot.end_sec]
                 │
                 ▼ User fine-tunes with Stepper / Hotkeys (J, L, Frame, I, O)
[Mark In (start_sec)] ───► [Mark Out (end_sec)]
                 │
                 ▼ Click [▶ Play Selected Range]
[Player plays [start_sec -> end_sec] and auto-pauses]
                 │
                 ▼ Contestant confirms visual match
[Click [🚀 Submit to DRES] ]
                 │
                 ▼ POST /api/dres/submit
[src/submission/dres_client.py]
  ├─► Format mediaItemName (strip .mp4)
  ├─► Convert to integer milliseconds (start_ms, end_ms)
  ├─► Check duplicate cache
  └─► POST /api/v2/submit/{evalID}?session={sessionID}
                 │
                 ▼
[DRES Server Response displayed on UI toast & history log]
```

---

## 4. Verification & Acceptance Criteria
1. **Frame-Accurate Seeking Test:**
   * Click `[+0.04s]` / `[-0.04s]` and verify video timestamp increments/decrements by exactly `0.04s` without player crash or audio glitch.
2. **Hotkey Action Test:**
   * Press `I` and verify `Start Time` updates to current playback time.
   * Press `O` and verify `End Time` updates to current playback time.
   * Verify timeline overlay displays the highlighted range matching `[Start, End]`.
3. **Range Preview Test:**
   * Set range `[10.0s, 15.0s]`. Click `[▶ Play Range]`.
   * Verify playback starts at `10.0s` and automatically stops at `15.0s`.
4. **Submission Validation & Duplicate Guard Test:**
   * Set `end_sec < start_sec` -> Verify UI blocks submission with validation warning.
   * Submit `L13_V001 [63500ms - 68200ms]` in dry-run mode -> Verify payload complies with DRES schema.
   * Re-submit same range -> Verify client suppresses duplicate and displays warning banner.
5. **Score Decay Simulator Test:**
   * Verify elapsed timer ticks upwards and live estimated score decays linearly according to competition rules.
