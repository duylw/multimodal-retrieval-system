# Task 07D: Zero-Popup Split Cockpit Layout & Timeline Hit Markers

**Status:** `[PENDING]` Pending
**Target Milestone:** Milestone 5 (Competition Retrieval & Cockpit Optimization)
**Server Component:** [src/ui/competition_server.py](file:///d:/UIT/TX/doan/src/ui/competition_server.py)
**Frontend Client:** [src/ui/competition/index.html](file:///d:/UIT/TX/doan/src/ui/competition/index.html), [src/ui/competition/style.css](file:///d:/UIT/TX/doan/src/ui/competition/style.css), [src/ui/competition/app.js](file:///d:/UIT/TX/doan/src/ui/competition/app.js)
**Documentation:** [docs/guides/competition-workstation-guide.md](file:///d:/UIT/TX/doan/docs/guides/competition-workstation-guide.md)
**Unit Tests:** [tests/test_competition_workstation.py](file:///d:/UIT/TX/doan/tests/test_competition_workstation.py)

---

## 1. Problem Statement & Objectives (What)
In the current Task 06C layout ([src/ui/competition/index.html](file:///d:/UIT/TX/doan/src/ui/competition/index.html)), two structural UX constraints slow down rapid verification under 240s-300s KIS time pressure:

1. The left sidebar devotes ~25-30% of horizontal screen width to a large Competition Stopwatch, Predicted Score Decay Breakdown, Target Coordinates, and Submission Stream cards, squeezing the candidate grid even during initial search scanning.
2. Inspecting frames defaults to a full-screen Pop-up Modal that obscures the candidate grid and forces open/close context switching between every candidate inspection; meanwhile, the timeline scrubber gives no visual indication of where other search hits occur inside the active video.

### Objectives
* Re-architect the workstation into a **Zero-Popup Dual-Zone Cockpit Layout** defaulting to a persistent right-side Verification & Submit Inspector while reserving ~65% width on the left for high-density candidate scanning.
* Condense the Competition Stopwatch (`04:18`) and Wrong Attempt Counter (`Wrong: 0`) into a **Compact Top-Header Timer Capsule** (with expandable breakdown popover).
* Render **Timeline Hit Markers** along the video scrubber showing every matched search timestamp inside the currently loaded video so contestants can jump between hits in a single click.
* Embed a compact **Inline Neighbor Filmstrip (`+-10s`)** directly beneath the docked player so adjacent shots can be skimmed visually faster than scrubbing MP4 bytes.
* Update [docs/guides/competition-workstation-guide.md](file:///d:/UIT/TX/doan/docs/guides/competition-workstation-guide.md) with the updated layout, cockpit controls, and manual verification steps.

---

## 2. Technical Specifications & Implementation Steps (How)

### Step 2.1: Compact Header Timer & Score Capsule
In [src/ui/competition/index.html](file:///d:/UIT/TX/doan/src/ui/competition/index.html), [src/ui/competition/style.css](file:///d:/UIT/TX/doan/src/ui/competition/style.css), and [src/ui/competition/app.js](file:///d:/UIT/TX/doan/src/ui/competition/app.js):
1. Move the `00:00` countdown timer, `Text (300s) / Video (240s)` toggle, Start/Reset controls, and `+1 Wrong` badge into a compact pill inside `.app-header`.
2. Keep the detailed predicted score breakdown (`S_acc + S_time`) available on click/hover inside a lightweight popover instead of permanently occupying left-sidebar vertical real estate.

### Step 2.2: Default Split Cockpit Workspace (`65% Scan | 35% Verify & Submit`)
In [src/ui/competition/](file:///d:/UIT/TX/doan/src/ui/competition):
1. Remove the fixed left sidebar bottleneck and adopt a two-column workspace:
   * **Left / Main Zone (~65% width):** Query accelerators bar + high-density 5-column Candidate Grid / `By Video` strips.
   * **Right Docked Inspector (~35% width, collapsible / expandable to Modal):**
     * **Player Zone:** Always-mounted HTML5 `<video>` stream + fine-stepper bar (`-5s`, `-1s`, `-1f`, `Play`, `+1f`, `+1s`, `+5s`) + `[Expand Popup]` button if fullscreen zoom is desired.
     * **Inline Neighbor Filmstrip:** Horizontal strip of `+-10s` neighbor keyframes loaded via `GET /api/videos/{video_id}/context` directly below the scrubber; clicking any frame seeks the player instantly.
     * **Target Coordinates & Submit Zone:** Video ID, Start/End numeric boxes, Presets (`Tight`, `Shot`, `Window`), prominent **`Submit Playhead (S)`** and **`Submit Range`** buttons, plus a compact 3-row recent DRES response feed.
2. Clicking any candidate card on the left immediately seeks and plays the right-hand video at that exact timestamp without overlaying a backdrop over the grid.

### Step 2.3: Video Timeline Hit Markers
In [src/ui/competition/app.js](file:///d:/UIT/TX/doan/src/ui/competition/app.js) and [src/ui/competition/style.css](file:///d:/UIT/TX/doan/src/ui/competition/style.css):
1. Whenever a video is loaded into the player, collect all search results matching `c.video_id === activeVideoId` from `state.allCandidates`.
2. Once `video.duration` metadata loads, render clickable **Amber Hit Marker Ticks** positioned proportionally (`(ts / duration) * 100%`) over `.transport-scrubber-wrapper`.
3. Hovering a marker shows score & timestamp tooltip; clicking seeks directly to that matched moment.

### Step 2.4: Documentation & Manual UI Verification Checklist
1. Update [docs/guides/competition-workstation-guide.md](file:///d:/UIT/TX/doan/docs/guides/competition-workstation-guide.md) following the `feature-documentation-guide` skill.
2. Verify all existing REST contracts remain intact via `.venv\Scripts\python.exe -m tests.test_competition_workstation`, and provide manual browser UI verification steps per `AGENTS.md` Section 6 (no browser subagents).

---

## 3. ASCII Cockpit Layout Blueprint

```text
+---------------------------------------------------------------------------------------------------+
| [KIS] | Visual Query | OCR [Boost|Filter] | Exclude (-v) | [+Scene] | [Batches] | [Search] | 04:12|
+---------------------------------------------------------------------------------------------------+
| Recent: [dog] [bus | 51B] ...                                           | DRES: LIVE | Free VRAM  |
+---------------------------------------------------+-----------------------------------------------+
| CANDIDATES (300)        [View: Frames | By Video] | ACTIVE INSPECTOR: L18_V004 @ 01:24.5 [Popup]  |
| +--------+ +--------+ +--------+ +--------+       | +-------------------------------------------+ |
| | #1     | | #2     | | #3     | | #4     |       | |         HTML5 Video Player (HTTP 206)     | |
| | L18_V4 | | L05_V2 | | L21_V9 | | L12_V1 |       | +-------------------------------------------+ |
| | [Sim]  | | [Sim]  | | [Sim]  | | [Sim]  |       | ====|======|============|================     |
| +--------+ +--------+ +--------+ +--------+       |     ^ Hit Markers (matching timestamps)       |
| +--------+ +--------+ +--------+ +--------+       | [-5s][-1s][-1f][Play][+1f][+1s][+5s] [I] [O]  |
| | #5     | | #6     | | #7     | | #8     |       | [Neighbor Filmstrip -10s ... +10s]            |
| | ...    | | ...    | | ...    | | ...    |       | [ ][ ][ ][*][ ][ ][ ]                         |
| +--------+ +--------+ +--------+ +--------+       | Target: L18_V004 [84.00 - 85.00] [Tight][Shot]|
|                                                   | [ SUBMIT PLAYHEAD (S) ]  [ SUBMIT RANGE ]     |
|                                                   | Recent Submissions (last 3)                   |
+---------------------------------------------------+-----------------------------------------------+
```

---

## 4. Verification & Acceptance Criteria
* Zero backdrop popup required during standard scan -> seek -> submit cycles; single-click card loads video smoothly without layout shift or lost scroll position in the candidate grid.
* Timeline Hit Markers appear accurately on loaded videos that have multiple candidate hits and seek precisely when clicked.
* Single-hand hotkeys (`/`, `Enter`, `Space`, `J`/`L`, `Left`/`Right`, `I`, `O`, `S`, `Esc`) remain 100% functional in both Docked Cockpit and Expanded Popup modes.
