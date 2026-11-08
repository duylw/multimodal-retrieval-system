# Guide: Final Round Known-Item Search (KIS) Submission Protocol & Strategy

## 1. Overview & Competition Modalities

In the final round of the interactive video moment retrieval competition (following the Video Browser Showdown / VBS standard), evaluation is conducted on **Known-Item Search (KIS)** tasks. The goal is to rapidly locate a single target video moment within the full video collection stored in [data/raw_videos/](file:///d:/UIT/TX/doan/data/raw_videos).

There are two primary query modalities evaluated in the competition:

### 1.1 Textual Known-Item Search (Textual KIS)
* **Input:** A natural language description of an event, consisting of multiple descriptive sentences or conceptual clues.
* **Release Dynamic:** Clues are revealed **progressively over time** across the total query allocation window.
* **Time Allocation:** Maximum duration `t_L = 5 minutes` (300 seconds).
* **Operational Characteristics:**
  * Initial sentences give broad scene context (e.g. location, general action).
  * Subsequent sentences provide specific identifying details (e.g. clothing colors, distinctive on-screen text, specific actor interactions).
  * Contestants can submit immediately if confident from early clues to maximize the time score, or wait for subsequent sentences to verify candidates before submitting.

### 1.2 Video Known-Item Search (Video KIS)
* **Input:** Contestants view a short video clip (`<= 20 seconds`) extracted from an undisclosed moment in the video collection.
* **Capture Restrictions:** Filming, photographing, or capturing the screen with any electronic device is strictly prohibited.
* **Time Allocation:** Maximum duration `t_L = 4 minutes` (240 seconds).
* **Operational Characteristics:**
  * Human-in-the-loop inspection: Contestants quickly analyze visual cues (setting, objects, camera angle, actor movements) and transcribe on-screen text or vehicle plates.
  * Formulate multi-modal search queries: Execute zero-shot visual queries against [src/extractors/visual.py](file:///d:/UIT/TX/doan/src/extractors/visual.py) (SigLIP2 FAISS index) and exact text queries against [src/extractors/ocr.py](file:///d:/UIT/TX/doan/src/extractors/ocr.py) (SQLite FTS5 hybrid search).
  * Verify top candidate keyframes in the UI and submit the matching moment.

---

## 2. Mathematical Scoring Model & Strategic Trade-off

Every query has a maximum potential score of **100.0 points**, split into two equal components:
* **Accuracy Score (`S_acc`):** Up to 50.0 points.
* **Time Score (`S_time`):** Up to 50.0 points.

### 2.1 Formula Definitions

For a query with time limit `t_L` seconds, elapsed submission time `t` seconds (`0 <= t <= t_L`), and `w_s` incorrect submissions submitted before the correct answer:

```text
S_acc  = max(0, 50 - 10 * w_s)
S_time = 50 * (1 - t / t_L)

Total Score S = (S_acc + S_time)   [if correct answer submitted within t_L]
Total Score S = 0                  [if no correct answer submitted within t_L]
```

### 2.2 Accuracy Degradation Schedule

Each incorrect submission incurs an immediate **-10.0 point penalty** on the accuracy component:

| Wrong Submissions (`w_s`) | Accuracy Points (`S_acc`) | Penalty Incurred |
|---|---|---|
| `0` (Clean first submission) | `50.0` | `0.0` |
| `1` wrong attempt | `40.0` | `-10.0` |
| `2` wrong attempts | `30.0` | `-20.0` |
| `3` wrong attempts | `20.0` | `-30.0` |
| `4` wrong attempts | `10.0` | `-40.0` |
| `5` or more wrong attempts | `0.0` | `-50.0` (Accuracy depleted) |

### 2.3 Time Decay Schedule

The time score decays linearly from 50.0 to 0.0 over the allocated duration:

| Elapsed Time (`t`) | Textual KIS (`t_L = 300s`) Time Pts | Video KIS (`t_L = 240s`) Time Pts | Decay Rate |
|---|---|---|---|
| `15s` | `47.50` | `46.88` | Linear |
| `30s` | `45.00` | `43.75` | Linear |
| `60s` | `40.00` | `37.50` | Linear |
| `120s` | `30.00` | `25.00` | Linear |
| `180s` | `20.00` | `12.50` | Linear |
| `240s` | `10.00` | `0.00` | Linear |
| `300s` | `0.00` | `N/A` (Timed out) | Linear |

### 2.4 Strategic Decision Analysis: When to Submit vs When to Verify

> [!IMPORTANT]
> **A single incorrect submission (-10 points) is mathematically equivalent to wasting 60 seconds in Textual KIS, or wasting 48 seconds in Video KIS.**
>
> In Textual KIS:
> ```text
> Delta_t_equivalent = 10 / (50 / 300) = 60 seconds
> ```
> In Video KIS:
> ```text
> Delta_t_equivalent = 10 / (50 / 240) = 48 seconds
> ```

**Core Strategic Rules:**
1. **Never spam or guess:** Blindly submitting multiple candidate shots to "test" the server will rapidly drain 10 to 30 points. It is always superior to spend 10 to 15 seconds inspecting candidate keyframes and video playback in the UI than to submit an unconfirmed guess.
2. **Textual KIS Early Trigger:** If the first clue contains unique keywords (such as specific license plates, rare signage, or unique English/Vietnamese brand names), run hybrid OCR search via [src/indexers/metadata_db.py](file:///d:/UIT/TX/doan/src/indexers/metadata_db.py). If Rank #1 is a decisive match, submit immediately at `t <= 30s` to bank `> 90 points`.
3. **Textual KIS Ambiguous Trigger:** If early clues are generic (e.g. "a person walking on the street"), wait for subsequent sentences (e.g. "wearing a red raincoat and holding a yellow umbrella"). The cost of waiting 30-45 seconds for a disambiguating sentence is only 5-7.5 points, which is less than the 10-point penalty of a false guess.
4. **Video KIS Playback Verification:** Since Video KIS allows viewing a 20s clip, immediately identify 2-3 anchor features (e.g. text on banner, specific object interaction). Use the interactive timeline inspector in [src/ui/debug_server.py](file:///d:/UIT/TX/doan/src/ui/debug_server.py) to check the candidate video around `[start, end]`.

---

## 3. DRES REST API v2 Specification

The competition evaluation server uses **DRES (Distributed Retrieval Evaluation Server)** REST API v2.

### 3.1 Authentication (Step 1)
* **Endpoint:** `POST /api/v2/login`
* **Request Headers:** `Content-Type: application/json`
* **Request Body:**
```json
{
  "username": "<USERNAME>",
  "password": "<PASSWORD>"
}
```
* **Success Response (HTTP 200):**
```json
{
  "id": "<USER_ID>",
  "username": "<USERNAME>",
  "role": "PARTICIPANT",
  "sessionId": "<SESSION_ID>"
}
```

### 3.2 Active Evaluation Discovery (Step 2)
* **Endpoint:** `GET /api/v2/client/evaluation/list?session=<SESSION_ID>`
* **Success Response (HTTP 200):**
```json
[
  {
    "id": "<EVALUATION_ID>",
    "name": "<EVALUATION_NAME>",
    "type": "SYNCHRONOUS",
    "status": "ACTIVE"
  }
]
```

### 3.3 Known-Item Search Submission (Step 3)
* **Endpoint:** `POST /api/v2/submit/{evaluationID}?session={sessionID}`
* **Request Headers:** `Content-Type: application/json`
* **Request Body (KIS Format):**
```json
{
  "answerSets": [
    {
      "answers": [
        {
          "mediaItemName": "<VIDEO_ID>",
          "start": <TIME_IN_MS>,
          "end": <TIME_IN_MS>
        }
      ]
    }
  ]
}
```

---

## 4. Submission Payload Standards & Validation Rules

To prevent submission rejection or invalid status codes from DRES, the client must enforce the following validation rules:

| Field | Type | Unit | Standard Format | Prohibited / Invalid Formats |
|---|---|---|---|---|
| `mediaItemName` | `string` | N/A | Video ID without extension (e.g. `"L01_V001"`) | Filenames with extensions like `"L01_V001.mp4"`, or absolute paths |
| `start` | `integer` | Milliseconds | Integer ms (e.g. `12345` for `12.345s`) | Float seconds (e.g. `12.35`), strings, or negative integers |
| `end` | `integer` | Milliseconds | Integer ms (e.g. `15000` for `15.000s`) | Float seconds, values where `end < start` |
| `answerSets` | `array` | N/A | Array with 1 `answerSet` containing 1 `answer` | Empty array or multiple simultaneous guesses |

> [!WARNING]
> **Duplicate Submissions Prohibited:** The evaluation server will reject repeated submissions for the exact same video moment within a single query. The client implementation in [src/submission/dres_client.py](file:///d:/UIT/TX/doan/src/submission/dres_client.py) maintains an in-memory cache of submitted tuples `(eval_id, video_id, start_ms, end_ms)` to automatically prevent accidental double-clicks or repeated submissions.

---

## 5. Software Architecture & Implementation

The submission system is organized into modular dataclasses in [src/common/types.py](file:///d:/UIT/TX/doan/src/common/types.py) and a standalone REST client in [src/submission/dres_client.py](file:///d:/UIT/TX/doan/src/submission/dres_client.py).

### 5.1 Architecture Flow

```text
+-------------------------------------------------------------+
| User Query (Textual KIS hints or Video KIS visual cues)     |
+-------------------------------------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| Retrieval Pipeline: SigLIP2 FAISS + EasyOCR FTS5 Hybrid     |
+-------------------------------------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| Interactive Web UI: Visual Inspection & HTTP 206 Playback   |
| -> Contestant confirms matching moment                      |
+-------------------------------------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| [src/submission/dres_client.py]                             |
| 1. format_media_item_name(video_id) -> strips .mp4          |
| 2. seconds_to_ms(start_sec, end_sec) -> converts to ms      |
| 3. Local duplicate submission check                         |
+-------------------------------------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| DRES Server: POST /api/v2/submit/{evaluationID}             |
+-------------------------------------------------------------+
```

### 5.2 Python API Usage

```python
from src.submission import DRESClient, create_kis_submission_payload, calculate_kis_score

# 1. Initialize client
client = DRESClient(base_url="https://eventretrieval.one")

# 2. Login to retrieve active session ID
client.login(username="team_uit", password="secret_password")

# 3. Discover active evaluation
active_eval = client.get_active_evaluation()
eval_id = active_eval["id"]

# 4. Submit candidate moment (automatically converts seconds to ms and strips .mp4)
response = client.submit_kis(
    evaluation_id=eval_id,
    video_id="L13_V001.mp4",
    start_sec=63.5,
    end_sec=68.2
)

# 5. Check response
print("Submission response:", response)
```

### 5.3 CLI Execution

The DRES client provides a standalone command-line interface for testing payloads, querying evaluations, and submitting answers:

```powershell
# 1. Dry-run payload check (validates and prints payload without sending network requests)
uv run python -m src.submission.dres_client --dry-run --video-id "L01_V005.mp4" --start 12.345 --end 15.678

# 2. List available evaluations
uv run python -m src.submission.dres_client --username "team_uit" --password "secret_password" --list-evals

# 3. Submit directly using session token
uv run python -m src.submission.dres_client --session-id "<SESSION_TOKEN>" --eval-id "<EVAL_ID>" --video-id "L13_V001" --start 63.5 --end 68.2
```

---

## 6. Integration with Search Web Interface

In the upcoming interactive submission interface defined in [task-06b-kis-interactive-submission.md](file:///d:/UIT/TX/doan/tasks/task-06b-kis-interactive-submission.md) ([src/ui/debug_server.py](file:///d:/UIT/TX/doan/src/ui/debug_server.py)):
1. **Interactive Scrubber & Range Selector:** Provides frame-accurate steppers (`[-5s]`, `[-1s]`, `[-frame]`, `[+frame]`, `[+1s]`, `[+5s]`) and Mark In (`I`) / Mark Out (`O`) buttons to pinpoint exact moment bounds.
2. **Pre-submission Preview Player:** A `[▶ Play Range]` button plays exclusively within `[start_sec, end_sec]` so contestants verify the event before submission.
3. **1-Click DRES Submission:** Each card or range selector triggers immediate submission with integer milliseconds and extension-stripped video IDs.
4. **Duplicate Protection & Response Banner:** Immediate visual feedback shows whether the server accepted the submission, rejected it as wrong, or suppressed it as duplicate.
5. **Real-time Score Decay Calculator:** An on-screen widget computes real-time estimated scores using `calculate_kis_score()` based on elapsed query time and prior submission attempts.

---

## 7. Troubleshooting & Error Checklist

| Error / Symptom | Root Cause | Resolution |
|---|---|---|
| `HTTP 401 Unauthorized` | Invalid username/password or expired `sessionId`. | Call `login()` again to generate a fresh `sessionId`. |
| `HTTP 404 Evaluation Not Found` | Specified `evaluationID` does not exist or has closed. | Call `get_active_evaluation()` to find the current active competition round ID. |
| `HTTP 400 Bad Request` | Malformed JSON body, missing `answerSets`, or invalid types. | Use `create_kis_submission_payload()` to ensure compliant JSON schema. |
| `HTTP 409 Conflict / Duplicate` | Attempted to submit the same video moment twice for the same query. | Check `_submitted_cache` in [src/submission/dres_client.py](file:///d:/UIT/TX/doan/src/submission/dres_client.py). |
| `Wrong Answer Penalty (-10 pts)` | Contestant submitted candidate before verifying visual match. | Ensure user visually inspects keyframe and video segment before submitting. |
