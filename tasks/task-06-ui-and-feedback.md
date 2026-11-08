# Task 06: Multimodal Search Web Application, Explainable Pipeline Inspector & Interactive Feedback

## 1. Objectives (What)
* Develop a production-grade, highly responsive web interface using **FastAPI** (Backend) and **Vanilla HTML5/CSS3/JavaScript (Single Page Application)** (Frontend) supporting the full **Visual + OCR Multimodal Pipeline** implemented in Task 05.
* **Explainability & Pipeline Traceability (Core Requirement):** Provide complete visibility into the multimodal retrieval and fusion process so contestants and reviewers can verify and trust each stage:
  * **Per-Cue Candidate Breakdown:** Visually display what each individual cue (Visual SigLIP2 vs OCR FTS5) retrieved independently before fusion (Top candidates, keyframe thumbnails, raw similarity scores, detected text, and execution latency).
  * **Fusion Step-by-Step Inspector:** Present the sliding window grouping (5s window, 2.5s stride), anti-double-counting decisions, and multi-cue consensus multipliers (`1.0 + 0.25 * (K - 1)`) that explain why a specific video moment ranked #1.
  * **Moment Card Evidence Accordion:** On each candidate moment card, allow users to expand and view the exact keyframes inside that temporal window that triggered each cue, with timestamp and detected text badges.
* **Human-in-the-Loop Multi-Cue Query Builder:**
  * Intuitive UI pills allowing users to dynamically add/remove Visual Cues (in English), OCR Cues (in Vietnamese/Latin), and Chronological Sequence Stages (`>>`).
  * Bidirectional synchronization between interactive pills and power-user query text (`v: ... | ocr: ... >> ...`).
* **HTML5 Video Player & Instant Seeking:**
  * Seamless integration with HTTP 206 Partial Content Range streaming.
  * Clicking any candidate moment or trigger keyframe instantly seeks the player to that exact timestamp (`currentTime = start_sec`).
* **Interactive Relevance Feedback (Rocchio Algorithm):**
  * Allow users to mark candidate keyframes as "Relevant / Find Similar" (Positive) or "Not Relevant" (Negative).
  * Update visual query vector via the Rocchio formulation and re-rank results in real-time (< 100ms) without re-encoding text.

---

## 2. Technical Specifications & Implementation Steps (How)

### Step 2.1: Backend Explainability Trace in SearchEngine & API Endpoints
1. **Extend [src/retrieval/search_engine.py](file:///d:/UIT/TX/doan/src/retrieval/search_engine.py):**
   * Implement `search_with_trace(query, mode, top_k, video_id, trace_top_hits=10)` returning both `List[CandidateMoment]` and a detailed `Dict[str, Any]` execution trace:
     * `parsed_stages`: Structured breakdown of stages, visual cues, and OCR cues.
     * `cues`: Array of per-cue execution traces:
       * `cue_id`: Unique identifier (e.g. `s0_v0`, `s0_ocr0`).
       * `modality`: `"visual"` or `"ocr"`.
       * `query_text`: Extracted query string.
       * `hits_count`: Total candidate hits retrieved (e.g. 1500 for visual, 48 for OCR).
       * `latency_ms`: Execution time for this specific cue.
       * `top_hits`: Top N candidates retrieved for this cue before fusion, each with `keyframe_id`, `video_id`, `timestamp_sec`, `score`, `thumbnail_url`, and `text_detected` (for OCR).
     * `fusion_summary`:
       * `total_windows_formed`: Number of 5-second sliding windows evaluated.
       * `consensus_windows_count`: Windows satisfying multiple cues simultaneously.
       * `suppressed_by_nms`: Count of redundant windows merged via temporal NMS (`IoU >= 0.3`).
       * `total_time_ms`: Overall pipeline turnaround time.
2. **Update FastAPI Endpoints in [src/ui/debug_server.py](file:///d:/UIT/TX/doan/src/ui/debug_server.py):**
   * Upgrade `GET /api/search/multimodal` and `POST /api/search/multimodal` to include `trace` in the response JSON whenever requested (default: `trace=true`).
   * Implement `POST /api/search/feedback` for Rocchio relevance feedback:
     * Parameters: `positive_keyframe_ids: List[str]`, `negative_keyframe_ids: List[str]`, `original_query: Optional[str]`.
     * Calculates Rocchio vector: `v' = alpha * v_orig + beta * mean(v_pos) - gamma * mean(v_neg)`.
     * Re-queries FAISS index and returns re-ranked candidate moments within 50ms.

---

### Step 2.2: Frontend Multi-Cue Builder & Explainable Trace UI
1. **Multi-Cue Query Builder Bar ([src/ui/static/index.html](file:///d:/UIT/TX/doan/src/ui/static/index.html)):**
   * Modality mode selector toggle:
     * `[Hybrid Multi-Cue (SigLIP2 + EasyOCR)]` (Default).
     * `[Visual Only (SigLIP2)]`.
     * `[OCR Text Only (FTS5)]`.
   * Dynamic Cue Builder Pills:
     * `[+ Add Visual Cue (EN)]` -> Creates an editable visual prompt pill with tag icon.
     * `[+ Add OCR Cue (VI)]` -> Creates an editable text prompt pill.
     * `[+ Add Sequence Stage (>>)]` -> Creates a chronological transition separator.
   * Power-user text input synchronization: Typing `v: ... | ocr: ...` auto-updates pills, and editing pills auto-updates the input string.
2. **Pipeline Execution Trace & Per-Cue Inspector Panel:**
   * A prominent diagnostic drawer / accordion right above the search results:
     * **Summary Header:** "Pipeline Trace: Parsed X Cues in Y ms | Evaluated Z Windows | Found K Consensus Moments".
     * **Interactive Cue Tabs:**
       * Tab for each cue (e.g. `Cue 1 [Visual: "news anchor"] (1,500 hits)`, `Cue 2 [OCR: "thoi su"] (48 hits)`).
       * Inside each tab: A horizontal or grid carousel of the Top 10 keyframes retrieved exclusively by that cue, with thumbnail, score badge, timestamp, and detected text snippet.
     * **Fusion Logic Breakdown:** Text explanation detailing which window received the consensus multiplier and why it outranked single-cue moments.
3. **Candidate Moment Card Enhancements:**
   * Prominent consensus badge: `[Consensus: Visual + OCR]` (golden highlight).
   * Matched cue tags: `[Visual: "news anchor"]`, `[OCR: "thoi su"]`.
   * **"Show Cue Evidence & Trigger Keyframes" Toggle:**
     * Expands to reveal the individual keyframes within that 5s window that triggered the cues.
     * Clicking any trigger keyframe seeks the video player directly to that keyframe's exact millisecond.
4. **Relevance Feedback Actions:**
   * Thumbs Up ("Find Similar") and Thumbs Down ("Exclude Scene") buttons on each candidate card.
   * Instant AJAX call to `/api/search/feedback` triggering instant re-ranking.

---

## 3. Verification & Acceptance Criteria
1. **Explainability & Per-Cue Trace Verification:**
   * Search query: `v: news anchor in television studio | ocr: thoi su`.
   * Open Pipeline Trace Inspector:
     * Verify `Cue 1 (Visual)` displays its independent Top 10 visual keyframe candidates.
     * Verify `Cue 2 (OCR)` displays its independent Top 10 text keyframe candidates matching `"thoi su"`.
     * Verify the fusion step clearly documents how window `L16_V022 [09:42 - 09:50]` combined them with the consensus multiplier.
2. **Candidate Card Evidence Verification:**
   * On candidate card #1, click "Show Cue Evidence".
   * Verify the visual trigger keyframe and OCR trigger keyframe are shown with correct timestamps and text detected.
3. **Interactive Multi-Cue Builder Verification:**
   * Add a visual pill `"blue truck"`, add an OCR pill `"51C 456"`.
   * Verify the search executes seamlessly against `/api/search/multimodal`.
4. **Instant Video Seeking Test:**
   * Click on candidate moment card; verify the HTML5 video player jumps immediately to `start_sec` and begins streaming via HTTP 206 Partial Content.
5. **Relevance Feedback Test:**
   * Click "Find Similar" on a candidate keyframe; verify re-ranked moments refresh in < 150ms without reloading the page.
