# User Guide: Multimodal Search Web Application & Explainable Pipeline Inspector

## 1. Feature Overview
* **What it does:** Provides an interactive web application ([src/ui/static/index.html](file:///d:/UIT/TX/doan/src/ui/static/index.html)) with an **Explainable Multimodal Pipeline Inspector (XIR)**, a **Human-in-the-Loop Multi-Cue Query Builder**, HTTP 206 Partial Content video streaming, and real-time **Rocchio Relevance Feedback**.
* **When to use:** Phase 2 (Online Retrieval Phase), during thesis demonstrations, evaluation benchmarking, and live Known-Item Search (KIS) competitions.
* **Core Value Provided:**
  * **100% Pipeline Transparency & Explainability:** Displays the exact intermediate candidate hits returned by each individual cue (Visual SigLIP2 vs OCR FTS5) before fusion, explaining why candidate moments won consensus multipliers and ranked #1.
  * **Candidate Keyframe Evidence Accordion:** Allows users to inspect and verify the exact keyframe within a 5-second window that triggered each cue, along with detected text and timestamps.
  * **Dynamic Query Composition Toolbar:** Fast composition with pills (`+ Visual (EN)`, `+ OCR Text (VI)`, `>> Sequence`) synchronized bidirectionally with the search input.
  * **Instant Sub-Second Feedback Re-Ranking:** Rocchio algorithm shifts visual query vectors in latent space using FAISS vector reconstruction in < 50ms without reloading neural networks.

---

## 2. Quick Start (Launching Web Application)

### Step 1: Start the FastAPI Backend Server
```powershell
uv run python -m src.ui.debug_server
```

### Step 2: Open Interface in Browser
* Navigate to: `http://127.0.0.1:8000`
* Swagger API Documentation: `http://127.0.0.1:8000/docs`

---

## 3. Web UI Controls & Explainability Inspection Guide

### 3.1 Multi-Cue Query Builder Toolbar
* **Mode Toggles:**
  * `[✨ Hybrid Multi-Cue (Visual + OCR)]` *(Default active)*: Decomposes and fuses both channels.
  * `[📷 Visual Only (SigLIP2)]`: Restricts search exclusively to dense visual vectors.
  * `[📝 On-Screen Text (OCR FTS5)]`: Restricts search exclusively to keyframe scene text.
* **Composition Buttons:**
  * Click `+ Visual (EN)` to append `| v: ` for English visual descriptors.
  * Click `+ OCR Text (VI)` to append `| ocr: ` for Vietnamese/Latin signage and license plates.
  * Click `>> Sequence` to insert chronological stage separators (`Stage 1 >> Stage 2`).

### 3.2 Explainable Pipeline Trace Panel
* Located right above the candidate cards on the `Ranked Candidates` tab.
* Click **"Inspect Per-Cue Hits & Fusion"** to expand:
  * **Stage Summary:** Visualizes parsed stages and cue assignments.
  * **Per-Cue Navigation Tabs:** Switch between `Cue #1 [VISUAL]` and `Cue #2 [OCR]`.
  * **Top Hits Gallery:** Displays the Top 10 independent keyframe candidates retrieved exclusively by that cue, including thumbnail, score, timestamp, and detected OCR text.
  * **Instant Verification:** Click any trace hit card to seek the video player immediately to that exact moment.

### 3.3 Candidate Moment Cards & Evidence Accordion
* **Consensus Badge:** Golden badge `[✨ Consensus (K Cues)]` marks moments satisfying multiple independent cues.
* **Inspect Trigger Keyframes:** Click the button to expand keyframe evidence within that 5-second window.
* **Interactive Seeking:** Clicking any candidate card or trigger keyframe jumps the HTML5 player instantly to that moment via HTTP 206 partial content streaming.
* **Rocchio Feedback:**
  * Click `👍 Similar` on a relevant moment to promote visually similar scenes.
  * Click `👎 Exclude` to penalize unwanted visual patterns.

---

## 4. API Endpoints Reference

| Endpoint | Method | Parameters | Description |
|---|---|---|---|
| `/api/search/multimodal` | `GET` / `POST` | `query: str`, `mode: str`, `top_k: int`, `video_id: Optional[str]` | Unified multimodal search returning candidate moments and full explainability trace. |
| `/api/search/feedback` | `POST` | `positive_keyframe_ids: List[str]`, `negative_keyframe_ids: List[str]`, `original_query: str` | Rocchio relevance feedback vector shift (< 50ms). |
| `/api/search/unload` | `POST` | *None* | Flushes SigLIP2 model and frees GPU VRAM. |
| `/api/stream/{video_id}` | `GET` | `Range: bytes=start-end` | HTTP 206 video byte range streaming. |

---

## 5. Hardware Constraints & Troubleshooting

| Error / Symptom | Root Cause | Resolution |
|---|---|---|
| `Trace panel is empty` | Query executed in single-modality mode with 0 cues. | Ensure query contains valid visual or OCR text; use `auto` mode. |
| `CUDA Out of Memory` | Other processes occupying GPU VRAM. | Execute `POST /api/search/unload` or use the "Release VRAM" control. |
| `Relevance feedback returns 400` | No positive/negative keyframe IDs supplied. | Ensure at least one keyframe is selected before triggering feedback. |
