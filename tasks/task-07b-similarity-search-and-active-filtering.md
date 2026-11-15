# Task 07B: Instant Keyframe Similarity Search, Negative Visuals & Active Filtering

**Status:** `[DONE]` Completed
**Target Milestone:** Milestone 5 (Competition Retrieval & Cockpit Optimization)
**Core Modules:** [src/retrieval/search_engine.py](file:///d:/UIT/TX/doan/src/retrieval/search_engine.py)
**Server Component:** [src/ui/competition_server.py](file:///d:/UIT/TX/doan/src/ui/competition_server.py)
**Frontend Client:** [src/ui/competition/](file:///d:/UIT/TX/doan/src/ui/competition)
**Unit Tests:** [tests/test_competition_workstation.py](file:///d:/UIT/TX/doan/tests/test_competition_workstation.py), [tests/test_retrieval.py](file:///d:/UIT/TX/doan/tests/test_retrieval.py)

---

## 1. Problem Statement & Objectives (What)
All 243,732 keyframe embeddings (768-dim) are already stored in [data/indices/visual_siglip2.index](file:///d:/UIT/TX/doan/data/indices/visual_siglip2.index), and [src/retrieval/search_engine.py](file:///d:/UIT/TX/doan/src/retrieval/search_engine.py) already implements negative vector subtraction (`-v:`). However, the Competition Workstation UI currently exposes neither **Image-to-Image Similarity ("More Like This")** nor practical **Interactive Result Pruning**:

1. Contestants frequently locate a visually similar scene (same news broadcast, camera angle, or event) via text search, but cannot jump immediately to visually matching frames without re-typing text prompts.
2. There is no dedicated input for **Negative Visual Exclusion** (`-v:`) on the UI bar, even though the backend supports it.
3. Eliminated wrong videos still occupy slots in subsequent refinements, and the `DRES Batches` toggle is statically hardcoded to `L01` through `L24` on the frontend without reflecting actual competition batch subsets or filtering at query time.

### Objectives
* Implement **0ms-Inference Keyframe-to-Keyframe Similarity Search** (`More Like This`) directly using FAISS `IndexFlatIP.reconstruct()` with optional text steering and negative subtraction.
* Expose an explicit **Exclude (`-v`)** field in the search bar (with optional auto-translation VI -> EN).
* Add **1-Click Session Video Blacklist (`Hide Video`)** and **Target Lock (`Only This`)** actions directly on candidate cards.
* Replace the static `DRES Batches` checkbox with a **Configurable Competition Batch Scope Selector** passed to the backend so non-target batches never consume top-K result slots.

---

## 2. Technical Specifications & Implementation Steps (How)

### Step 2.1: Backend Keyframe Similarity Search (`search_similar`)
In [src/retrieval/search_engine.py](file:///d:/UIT/TX/doan/src/retrieval/search_engine.py):
1. Add `keyframe_id_to_faiss_id` lookup map initialized once when loading `VectorIndex` (`O(1)` lookup).
2. Implement `search_by_keyframe(keyframe_id: str, steer_text: Optional[str] = None, steer_alpha: float = 0.3, negative_cues: Optional[List[str]] = None, top_k: int = 300, allowed_batches: Optional[Set[str]] = None, excluded_videos: Optional[Set[str]] = None) -> Tuple[List[CandidateMoment], Dict[str, Any]]`:
   * Reconstruct the 768-dim normalized embedding `v_img = vec_idx.index.reconstruct(faiss_id)` (0ms SigLIP2 inference when `steer_text` is empty).
   * If `steer_text` is provided, encode `v_txt` and compute `v_q = normalize((1 - steer_alpha) * v_img + steer_alpha * v_txt)`.
   * Apply optional negative vector subtraction (`- 0.35 * mean(neg_vecs)`) and L2-normalize.
   * Search FAISS `IndexFlatIP`, apply batch and excluded-video filters cleanly (oversampling when filters are active), fuse into temporal windows via `TemporalMomentFusor`, and decorate thumbnails.

### Step 2.2: Backend Batch Scope & Video Exclusion Filtering
In [src/retrieval/search_engine.py](file:///d:/UIT/TX/doan/src/retrieval/search_engine.py) and [src/ui/competition_server.py](file:///d:/UIT/TX/doan/src/ui/competition_server.py):
1. Extend `SearchEngine.search_with_trace()` to accept `allowed_batches: Optional[List[str]] = None` and `excluded_videos: Optional[List[str]] = None`.
2. Add `POST /api/search/similar` endpoint accepting `{ "keyframe_id": str, "steer_text": Optional[str], "steer_alpha": float, "negative_visual_queries": List[str], "top_k": int, "allowed_batches": List[str], "excluded_videos": List[str] }`.
3. Update `POST /api/search/multimodal` to pass `allowed_batches`, `excluded_videos`, and `negative_visual_queries` cleanly into `SearchEngine`.

### Step 2.3: Frontend Similarity Chip, Exclude Input & Card Pruning Actions
In [src/ui/competition/index.html](file:///d:/UIT/TX/doan/src/ui/competition/index.html), [src/ui/competition/style.css](file:///d:/UIT/TX/doan/src/ui/competition/style.css), and [src/ui/competition/app.js](file:///d:/UIT/TX/doan/src/ui/competition/app.js):
1. **Reference Image Chip:**
   * Add a `Similar` action button on every candidate card and filmstrip frame.
   * Clicking `Similar` pins a removable `[Ref: L18_V004 @ 01:24 (x)]` pill inside the search bar and triggers `POST /api/search/similar` immediately (if text also exists in the Visual box, uses text as steering direction).
2. **Exclude (`-v`) Input:**
   * Add a compact red-tinted input (`Exclude visual...`) next to the search bar; automatically translates Vietnamese terms via `/api/translate` when `Auto VI->EN` is enabled.
3. **Session Blacklist (`Hide Video`) & Target Lock:**
   * Add `[Hide]` button on each card (removes all cards of that `video_id` immediately from view and appends it to `state.excludedVideos` with a clickable chip counter `Hidden: N videos [Reset]`).
   * Add quick `[Only]` button to toggle single-video drilldown without manual typing.
4. **Configurable Batch Scope Modal/Popover:**
   * Replace the static `DRES Batches` toggle with a `[Batches: All (L01-L24)]` selector popover featuring presets (`All L01-L24`, `L01-L12`, `L13-L24`, custom range/selection persisted in `localStorage`).

---

## 3. Verification & Acceptance Criteria
* **Functionality Tests:**
  * `POST /api/search/similar` with a valid `keyframe_id` returns rank #1 self-match (or immediate neighbors) and discovers cross-video visually similar scenes in `< 50ms` without loading SigLIP2 text encoder when `steer_text` is empty.
  * Passing `excluded_videos` and `allowed_batches` enforces strict inclusion/exclusion in returned `CandidateMoment` objects without reducing requested result count prematurely.
  * Unit tests added in [tests/test_competition_workstation.py](file:///d:/UIT/TX/doan/tests/test_competition_workstation.py) and [tests/test_retrieval.py](file:///d:/UIT/TX/doan/tests/test_retrieval.py).
