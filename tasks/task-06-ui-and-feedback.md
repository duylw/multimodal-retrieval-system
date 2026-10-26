# Task 06: Search Web Application & Interactive Relevance Feedback

## 1. Objectives (What)
* Develop a search web application using **FastAPI** (Backend) and **Vanilla HTML/CSS/JavaScript** (Frontend).
* Allow users to enter natural language queries, toggle modality search channels, and explore ranked video moments.
* Integrate an HTML5 video player with instant timestamp seeking (`currentTime = start_sec`) upon clicking candidate moments.
* Implement **Interactive Relevance Feedback** via the Rocchio algorithm:
  * "Relevant Moment / Find Similar" (Positive Feedback).
  * "Not Relevant" (Negative Feedback).
  * Re-rank candidate results instantaneously without re-running heavy neural networks.

---

## 2. Implementation Steps (How)

### Step 2.1: FastAPI Backend Endpoints
1. **Search Endpoint (`/api/search`):**
   * Accepts query text, channel filter flags, and `top_k`.
   * Invokes `search_engine.py` and returns structured JSON candidate moments with start/end timestamps, confidence scores, and contributing channel badges.
2. **Video Streaming Endpoint (`/api/stream/{video_id}`):**
   * Employs **HTTP 206 Partial Content (Range Requests)** to allow browsers to seek to arbitrary timestamps instantly without loading full video files into RAM.
3. **Relevance Feedback Endpoint (`/api/feedback`):**
   * Receives `positive_keyframe_ids` and `negative_keyframe_ids`.
   * Updates the query vector via the Rocchio formulation:
     `new_vector = 1.0 * old_vector + 0.75 * avg(positive_vectors) - 0.25 * avg(negative_vectors)`
   * Re-applies L2 normalization and queries FAISS for immediate re-ranking.

### Step 2.2: Frontend User Interface
* **Search Bar:** Centered search input with example query pills.
* **Modality Toggles:** Checkboxes to enable/disable channels: `[x] Visual`, `[x] Speech (ASR)`, `[x] On-screen Text (OCR)`.
* **Results Grid:**
  * Candidate moment cards with keyframe thumbnail, video ID, timestamp range (`02:15 - 02:28`), channel badges (`[Visual] [ASR]`), and confidence score bar.
  * Direct action buttons: "Play from this timestamp" and "Find Similar".
* **Video Player Pane:** Responsive video player with synchronized temporal playback and range scrubbers.

---

## 3. Verification & Acceptance Criteria
1. **HTTP 206 Streaming Test:**
   * Verify HTTP response code `206 Partial Content` with `Content-Range` headers when scrubbing video playback.
2. **End-to-End Latency Benchmark:**
   * Overall search response latency from query submission to result card rendering must be **< 1.5 seconds**.
3. **Relevance Feedback Test:**
   * Query: `"crowded street during daytime"`.
   * Mark negative feedback on a night scene and positive feedback on a daytime street frame.
   * Verify re-ranked results suppress night scenes and promote similar daytime street candidates to the top.
