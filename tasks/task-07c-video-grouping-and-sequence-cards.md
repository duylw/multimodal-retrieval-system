# Task 07C: Video Grouping View & Dual-Frame Sequential Result Cards

**Status:** `[DONE]` Completed
**Target Milestone:** Milestone 5 (Competition Retrieval & Cockpit Optimization)
**Core Modules:** [src/common/types.py](file:///d:/UIT/TX/doan/src/common/types.py), [src/retrieval/search_engine.py](file:///d:/UIT/TX/doan/src/retrieval/search_engine.py)
**Server Component:** [src/ui/competition_server.py](file:///d:/UIT/TX/doan/src/ui/competition_server.py)
**Frontend Client:** [src/ui/competition/index.html](file:///d:/UIT/TX/doan/src/ui/competition/index.html), [src/ui/competition/style.css](file:///d:/UIT/TX/doan/src/ui/competition/style.css), [src/ui/competition/app.js](file:///d:/UIT/TX/doan/src/ui/competition/app.js)
**Unit Tests:** [tests/test_competition_workstation.py](file:///d:/UIT/TX/doan/tests/test_competition_workstation.py)

---

## 1. Problem Statement & Objectives (What)
During high-speed KIS scanning on the 726-video repository, a flat grid of 300 candidate moments exhibits two visual scanning bottlenecks:

1. **Same-Video Grid Flooding:** When one broadcast video contains 15-25 visually similar frames (e.g., recurring news segments or repetitive camera angles), those moments fill the top 3-4 rows of the grid, burying distinct candidate videos underneath.
2. **Sequential Blindness:** When running a 2-stage sequential query (`Stage 1 >> Stage 2`), each result card displays only a single keyframe thumbnail (usually Stage 1), forcing the contestant to open the video player blindly to check whether Stage 2 actually follows.

### Objectives
* Add a **Group by Video** (`Video Strips`) view mode allowing contestants to scan 30-50 distinct videos in seconds, each displaying its top chronologically ordered moment thumbnails in a horizontal strip.
* Add **Dual-Frame Sequence Cards** whenever sequential search (`Task 07A`) returns paired stage evidence, showing `[Stage 1 Thumbnail] -> (+Δt sec) -> [Stage 2 Thumbnail]` directly on the grid card.
* Provide a 1-click view switcher (`[Frames | By Video]`) in the canvas header with persistent preference.

---

## 2. Technical Specifications & Implementation Steps (How)

### Step 2.1: Structured Stage Evidence Serialization
In [src/ui/competition_server.py](file:///d:/UIT/TX/doan/src/ui/competition_server.py):
1. Ensure every moment serialized in `POST /api/search/multimodal` exposes normalized `stage_hits` (list of `{ stage_index, keyframe_id, timestamp_sec, score, thumbnail_url }` sorted by `stage_index`) whenever `is_sequential == True`.
2. Add optional query grouping helper (either returned alongside `results` as `grouped_videos` or computed deterministically on frontend from returned candidates + per-video cap) preserving top peak score ordering and sorting thumbnails within each video chronologically (`timestamp_sec` ascending).

### Step 2.2: Frontend Video Strip Renderer (`Group by Video`)
In [src/ui/competition/index.html](file:///d:/UIT/TX/doan/src/ui/competition/index.html), [src/ui/competition/style.css](file:///d:/UIT/TX/doan/src/ui/competition/style.css), and [src/ui/competition/app.js](file:///d:/UIT/TX/doan/src/ui/competition/app.js):
1. Add `[View: Frames | By Video]` segmented toggle in `.canvas-view-tools`.
2. In `By Video` mode, render one horizontal **Video Strip Card** per unique `video_id` ordered by highest candidate score:
   * Left metadata column: Rank badge (`#1`, `#2`, ...), `video_id`, top score, hit count (`N hits`), and quick `[Hide]` / `[Only]` buttons.
   * Right horizontal film-row: up to 6-7 temporally sorted candidate thumbnails from that video, each labeled with its timestamp (`01:24.5`), match score, and 1-click inspect/submit actions.

### Step 2.3: Frontend Dual-Frame Sequence Card Renderer
In [src/ui/competition/app.js](file:///d:/UIT/TX/doan/src/ui/competition/app.js) and [src/ui/competition/style.css](file:///d:/UIT/TX/doan/src/ui/competition/style.css):
1. When a candidate has `stage_hits.length >= 2`, render a **Split Dual-Frame Preview** instead of a single thumbnail:
   * Left image: Stage 1 keyframe (`t1`).
   * Center temporal delta badge: `+12.4s`.
   * Right image: Stage 2 keyframe (`t2`).
2. Clicking either thumbnail opens/seeks the player directly to that stage's exact timestamp (`t1` or `t2`), while `Submit Range` defaults cleanly to `[t1, t2]` (capped safely inside competition limits) and `Submit Head` targets the clicked frame.

---

## 3. Verification & Acceptance Criteria
* **Visual & Functional Verification:**
  * Toggling between `Frames` and `By Video` re-renders existing results instantaneously (`< 30ms`) with zero extra backend requests.
  * Clicking any thumbnail inside a `By Video` row seeks accurately to that exact `timestamp_sec` and highlights the active target coordinates.
  * Sequential search payloads containing `stage_hits` render paired side-by-side thumbnails and accurate `+Δt` interval badges; verified via payload contract tests in [tests/test_competition_workstation.py](file:///d:/UIT/TX/doan/tests/test_competition_workstation.py).
