"""
FastAPI Debug Server for Shot Boundaries and Keyframe Inspection.
Serves video streaming with HTTP 206 Range requests and interactive inspector web UI.
"""

import os
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from src.indexers.metadata_db import MetadataDB

app = FastAPI(
    title="Shot & Keyframe Debug Inspector",
    description="Inspection and debugging tool for video shot segmentation and adaptive keyframe extraction",
    version="1.0.0"
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "data/metadata.db"
VIDEOS_DIR = Path("data/raw_videos")
KEYFRAMES_DIR = Path("data/keyframes")
STATIC_DIR = Path("src/ui/static")

# Ensure static directory exists
STATIC_DIR.mkdir(parents=True, exist_ok=True)


def get_db() -> MetadataDB:
    """Instantiates MetadataDB connection."""
    return MetadataDB(DB_PATH)


def range_stream_generator(
    file_path: Path, start: int, end: int, chunk_size: int = 65536
) -> Generator[bytes, None, None]:
    """Yields chunks of bytes within specified start and end range."""
    with open(file_path, "rb") as f:
        f.seek(start)
        bytes_remaining = end - start + 1
        while bytes_remaining > 0:
            read_size = min(chunk_size, bytes_remaining)
            data = f.read(read_size)
            if not data:
                break
            bytes_remaining -= len(data)
            yield data


@app.get("/api/videos", response_model=List[Dict[str, Any]])
def list_videos() -> List[Dict[str, Any]]:
    """Returns all cataloged videos along with shot and keyframe counts."""
    db = get_db()
    with db._get_connection() as conn:
        rows = conn.execute("""
            SELECT 
                v.video_id,
                v.file_name,
                v.duration_sec,
                v.fps,
                v.width,
                v.height,
                v.total_frames,
                COUNT(DISTINCT s.shot_id) AS shot_count,
                COUNT(DISTINCT k.keyframe_id) AS keyframe_count
            FROM videos v
            LEFT JOIN shots s ON v.video_id = s.video_id
            LEFT JOIN keyframes k ON v.video_id = k.video_id
            GROUP BY v.video_id
            ORDER BY v.video_id ASC;
        """).fetchall()

    results = []
    for r in rows:
        vid = r["video_id"]
        raw_path = VIDEOS_DIR / f"{vid}.mp4"
        results.append({
            "video_id": vid,
            "file_name": r["file_name"] or f"{vid}.mp4",
            "duration_sec": r["duration_sec"] or 0.0,
            "fps": r["fps"] or 0.0,
            "width": r["width"] or 0,
            "height": r["height"] or 0,
            "total_frames": r["total_frames"] or 0,
            "shot_count": r["shot_count"],
            "keyframe_count": r["keyframe_count"],
            "video_exists": raw_path.exists(),
        })

    return results


@app.get("/api/videos/{video_id}")
def get_video_details(video_id: str) -> Dict[str, Any]:
    """Returns detailed shot boundaries and keyframes for a specific video."""
    db = get_db()
    video_info = db.get_video(video_id)
    if not video_info:
        raise HTTPException(status_code=404, detail=f"Video '{video_id}' not found in database.")

    shots = db.get_shots(video_id)
    keyframes = db.get_keyframes(video_id)
    ocr_records = db.get_ocr_records(video_id)

    # Group OCR text by keyframe_id
    ocr_by_kf: Dict[str, List[str]] = {}
    for r in ocr_records:
        ocr_by_kf.setdefault(r.keyframe_id, []).append(r.text_detected)

    # Group keyframes by shot_id
    shot_items = []
    shot_dict = {}

    for s in shots:
        shot_obj = {
            "shot_id": s.shot_id,
            "start_frame": s.start_frame,
            "end_frame": s.end_frame,
            "start_sec": round(s.start_sec, 2),
            "end_sec": round(s.end_sec, 2),
            "duration_sec": round(s.duration_sec, 2),
            "keyframes": [],
        }
        shot_dict[s.shot_id] = shot_obj
        shot_items.append(shot_obj)

    for k in keyframes:
        if k.shot_id in shot_dict:
            file_name = Path(k.file_path).name
            shot_dict[k.shot_id]["keyframes"].append({
                "keyframe_id": k.keyframe_id,
                "frame_idx": k.frame_idx,
                "timestamp_sec": round(k.timestamp_sec, 2),
                "is_shot_center": k.is_shot_center,
                "blur_score": round(k.blur_score, 1),
                "file_name": file_name,
                "image_url": f"/api/keyframes/{video_id}/{file_name}",
                "ocr_texts": ocr_by_kf.get(k.keyframe_id, []),
            })

    return {
        "video": video_info,
        "total_shots": len(shots),
        "total_keyframes": len(keyframes),
        "total_ocr_records": len(ocr_records),
        "shots": shot_items,
    }


@app.get("/api/stream/{video_id}")
def stream_video(video_id: str, request: Request) -> Response:
    """Streams local MP4 video file with HTTP 206 Partial Content support."""
    video_path = VIDEOS_DIR / f"{video_id}.mp4"
    if not video_path.exists():
        matching = list(VIDEOS_DIR.glob(f"{video_id}.*"))
        if matching:
            video_path = matching[0]
        else:
            raise HTTPException(status_code=404, detail=f"Video file '{video_id}' not found on disk.")

    file_size = video_path.stat().st_size
    range_header = request.headers.get("Range")

    if not range_header:
        # Full content response
        return FileResponse(
            path=str(video_path),
            media_type="video/mp4",
            headers={"Accept-Ranges": "bytes"}
        )

    # Parse Range: bytes=start-end
    try:
        range_val = range_header.strip().split("=")[1]
        parts = range_val.split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if parts[1] else file_size - 1
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail="Invalid Range header."
        )

    if start >= file_size or end >= file_size or start > end:
        raise HTTPException(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            headers={"Content-Range": f"bytes */{file_size}"},
            detail="Requested range out of bounds."
        )

    # Chunked range streaming
    content_length = end - start + 1
    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
        "Content-Type": "video/mp4",
    }

    return StreamingResponse(
        range_stream_generator(video_path, start, end),
        status_code=status.HTTP_206_PARTIAL_CONTENT,
        headers=headers,
    )


@app.get("/api/keyframes/{video_id}/{filename}")
def get_keyframe_image(video_id: str, filename: str) -> FileResponse:
    """Serves extracted keyframe JPEG image by filename or keyframe_id."""
    img_path = KEYFRAMES_DIR / video_id / filename
    if img_path.exists():
        return FileResponse(path=str(img_path), media_type="image/jpeg")

    # If filename is a keyframe_id (e.g. L16_V022_00168.jpg or L16_V022_00168)
    kfid = filename[:-4] if filename.lower().endswith(".jpg") else filename
    db = get_db()
    fp = db.get_keyframe_path(kfid)
    if fp and Path(fp).exists():
        return FileResponse(path=str(fp), media_type="image/jpeg")

    raise HTTPException(status_code=404, detail=f"Keyframe image '{filename}' not found for video '{video_id}'.")


# Global lazy-loaded search components
_vector_index: Optional[Any] = None
_visual_extractor: Optional[Any] = None
_search_engine: Optional[Any] = None


def get_search_engine() -> Any:
    """Lazy-initializes SearchEngine singleton."""
    global _search_engine
    if _search_engine is None:
        from src.retrieval.search_engine import SearchEngine
        _search_engine = SearchEngine()
    return _search_engine


@app.get("/api/search/multimodal")
def search_multimodal_endpoint(
    query: str,
    mode: str = "auto",
    top_k: int = 25,
    video_id: Optional[str] = None
) -> Dict[str, Any]:
    """Unified Multimodal Search: Multi-Cue RRF fusion, 5s sliding window, trace, and NMS."""
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query string cannot be empty.")

    engine = get_search_engine()
    vid_filter = video_id.strip() if video_id and video_id.strip() else None
    moments, trace = engine.search_with_trace(
        query=query.strip(),
        mode=mode,
        top_k=top_k,
        video_id=vid_filter,
        trace_top_hits=10
    )

    results = []
    for rank, m in enumerate(moments, start=1):
        mins_s, secs_s = int(m.start_sec // 60), m.start_sec % 60
        mins_e, secs_e = int(m.end_sec // 60), m.end_sec % 60
        time_str = f"{mins_s:02d}:{secs_s:05.2f} - {mins_e:02d}:{secs_e:05.2f}"

        results.append({
            "rank": rank,
            "score": m.score,
            "video_id": m.video_id,
            "start_sec": m.start_sec,
            "end_sec": m.end_sec,
            "start_ms": m.start_ms,
            "end_ms": m.end_ms,
            "formatted_time": time_str,
            "matched_cues": m.matched_cues,
            "keyframe_id": m.keyframe_id,
            "thumbnail_url": m.thumbnail_url,
            "text_detected": m.text_snippet,
            "cue_evidence": m.cue_evidence,
            "is_multimodal": True
        })

    return {
        "query": query,
        "mode": mode,
        "total_results": len(results),
        "candidates": results,
        "trace": trace
    }


@app.post("/api/search/multimodal")
def search_multimodal_post_endpoint(
    payload: Dict[str, Any],
    mode: str = "auto",
    top_k: int = 25,
    video_id: Optional[str] = None
) -> Dict[str, Any]:
    """Structured Multi-Cue JSON search endpoint with execution trace."""
    engine = get_search_engine()
    vid_filter = video_id.strip() if video_id and video_id.strip() else None
    moments, trace = engine.search_with_trace(
        query=payload,
        mode=mode,
        top_k=top_k,
        video_id=vid_filter,
        trace_top_hits=10
    )

    results = []
    for rank, m in enumerate(moments, start=1):
        mins_s, secs_s = int(m.start_sec // 60), m.start_sec % 60
        mins_e, secs_e = int(m.end_sec // 60), m.end_sec % 60
        time_str = f"{mins_s:02d}:{secs_s:05.2f} - {mins_e:02d}:{secs_e:05.2f}"

        results.append({
            "rank": rank,
            "score": m.score,
            "video_id": m.video_id,
            "start_sec": m.start_sec,
            "end_sec": m.end_sec,
            "start_ms": m.start_ms,
            "end_ms": m.end_ms,
            "formatted_time": time_str,
            "matched_cues": m.matched_cues,
            "keyframe_id": m.keyframe_id,
            "thumbnail_url": m.thumbnail_url,
            "text_detected": m.text_snippet,
            "cue_evidence": m.cue_evidence,
            "is_multimodal": True
        })

    return {
        "mode": mode,
        "total_results": len(results),
        "candidates": results,
        "trace": trace
    }


@app.post("/api/search/feedback")
def relevance_feedback_endpoint(
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Rocchio Interactive Relevance Feedback:
    Takes positive and negative keyframe IDs, computes Rocchio shifted vector,
    and returns re-ranked candidate moments within 50ms without reloading neural networks.
    """
    pos_ids: List[str] = payload.get("positive_keyframe_ids", [])
    neg_ids: List[str] = payload.get("negative_keyframe_ids", [])
    orig_query: Optional[str] = payload.get("original_query", "")
    top_k: int = int(payload.get("top_k", 25))
    video_id: Optional[str] = payload.get("video_id")

    if not pos_ids and not neg_ids and not orig_query:
        raise HTTPException(status_code=400, detail="Must provide at least one feedback keyframe or query.")

    engine = get_search_engine()
    vec_idx = engine._ensure_vector_index()
    extractor = engine._ensure_visual_extractor()

    # Build reverse map if not cached
    if not hasattr(vec_idx, "_kfid_to_int_id"):
        vec_idx._kfid_to_int_id = {
            meta.get("keyframe_id"): idx
            for idx, meta in enumerate(vec_idx.id_to_metadata)
            if meta.get("keyframe_id")
        }

    import numpy as np

    if orig_query and orig_query.strip():
        q_vec = extractor.extract_text_embedding(orig_query.strip())[0].astype(np.float32)
    elif pos_ids and pos_ids[0] in vec_idx._kfid_to_int_id:
        q_vec = vec_idx.index.reconstruct(vec_idx._kfid_to_int_id[pos_ids[0]]).astype(np.float32)
    else:
        raise HTTPException(status_code=400, detail="Cannot initialize query vector for feedback.")

    alpha = 1.0
    beta = 0.75
    gamma = 0.25

    pos_vecs = []
    for pid in pos_ids:
        if pid in vec_idx._kfid_to_int_id:
            int_id = vec_idx._kfid_to_int_id[pid]
            pos_vecs.append(vec_idx.index.reconstruct(int_id))

    neg_vecs = []
    for nid in neg_ids:
        if nid in vec_idx._kfid_to_int_id:
            int_id = vec_idx._kfid_to_int_id[nid]
            neg_vecs.append(vec_idx.index.reconstruct(int_id))

    rocchio_vec = alpha * q_vec
    if pos_vecs:
        rocchio_vec += beta * np.mean(pos_vecs, axis=0)
    if neg_vecs:
        rocchio_vec -= gamma * np.mean(neg_vecs, axis=0)

    # L2 normalize
    norm = float(np.linalg.norm(rocchio_vec))
    if norm > 1e-6:
        rocchio_vec = rocchio_vec / norm

    # FAISS search
    raw_hits = vec_idx.search(rocchio_vec.reshape(1, -1), top_k=engine.top_k_visual)
    if video_id:
        raw_hits = [h for h in raw_hits if h.get("video_id") == video_id]

    cue_id = "feedback_v0"
    cue_types = {cue_id: "visual"}
    hits_by_cue = {cue_id: raw_hits}
    weights = {"visual": 1.0, "ocr": 1.0}

    moments = engine.fusor.fuse_and_nms(
        stage_results=[hits_by_cue],
        cue_types=cue_types,
        weights=weights,
        top_k=top_k
    )
    engine._decorate_moments(moments)

    results = []
    for rank, m in enumerate(moments, start=1):
        mins_s, secs_s = int(m.start_sec // 60), m.start_sec % 60
        mins_e, secs_e = int(m.end_sec // 60), m.end_sec % 60
        time_str = f"{mins_s:02d}:{secs_s:05.2f} - {mins_e:02d}:{secs_e:05.2f}"
        results.append({
            "rank": rank,
            "score": m.score,
            "video_id": m.video_id,
            "start_sec": m.start_sec,
            "end_sec": m.end_sec,
            "start_ms": m.start_ms,
            "end_ms": m.end_ms,
            "formatted_time": time_str,
            "matched_cues": m.matched_cues,
            "keyframe_id": m.keyframe_id,
            "thumbnail_url": m.thumbnail_url,
            "text_detected": m.text_snippet,
            "cue_evidence": m.cue_evidence,
            "is_multimodal": True,
            "is_feedback_rerank": True
        })

    return {
        "status": "ok",
        "total_results": len(results),
        "candidates": results,
        "positive_count": len(pos_vecs),
        "negative_count": len(neg_vecs)
    }


@app.get("/api/search/visual")
def search_visual(
    query: str,
    video_id: Optional[str] = None,
    top_k: int = 20,
    dedup: bool = True,
) -> Dict[str, Any]:
    """Searches visual index using natural language text query via SigLIP2."""
    global _vector_index, _visual_extractor

    if not query.strip():
        raise HTTPException(status_code=400, detail="Query string cannot be empty.")

    index_path = Path("data/indices/visual_siglip2.index")
    metadata_path = Path("data/indices/visual_siglip2.json")
    if not index_path.exists() or not metadata_path.exists():
        raise HTTPException(
            status_code=404,
            detail="FAISS index not found. Run Task 02 pipeline first to build index."
        )

    # Lazy-load vector index
    if _vector_index is None:
        from src.indexers.vector_index import VectorIndex
        _vector_index = VectorIndex({}, embedding_dim=768)
        _vector_index.load(str(index_path), str(metadata_path))

    # Lazy-load visual extractor for text embedding
    if _visual_extractor is None:
        from src.extractors.visual import VisualExtractor
        _visual_extractor = VisualExtractor()
        _visual_extractor.load_model()

    q_vec = _visual_extractor.extract_text_embedding(query.strip())
    raw_results = _vector_index.search(q_vec, top_k=150)

    db = get_db()
    kf_cache: Dict[str, List[Any]] = {}

    candidates = []
    seen_shots = set()
    rank = 1
    for r in raw_results:
        vid = r.get("video_id")
        if video_id and vid != video_id:
            continue

        shot_id = r.get("shot_id")
        # Deduplicate candidates by shot so the same shot does not repeat
        if dedup and shot_id is not None:
            shot_key = (vid, shot_id)
            if shot_key in seen_shots:
                continue
            seen_shots.add(shot_key)

        if vid not in kf_cache:
            kf_cache[vid] = db.get_keyframes(vid)

        # Resolve thumbnail image URL with fallback protection
        thumb_url = None
        if r.get("is_shot_pooled"):
            shot_id = r.get("shot_id")
            shot_kfs = [k for k in kf_cache[vid] if k.shot_id == shot_id]
            center_kf = next((k for k in shot_kfs if k.is_shot_center), (shot_kfs[0] if shot_kfs else None))
            if center_kf:
                thumb_url = f"/api/keyframes/{vid}/{Path(center_kf.file_path).name}"
        else:
            file_path = r.get("file_path")
            resolved = False
            if file_path:
                fp = Path(file_path)
                if fp.exists() or (KEYFRAMES_DIR / vid / fp.name).exists():
                    thumb_url = f"/api/keyframes/{vid}/{fp.name}"
                    resolved = True
            if not resolved:
                # Fallback to current shot keyframe from database
                shot_id = r.get("shot_id")
                shot_kfs = [k for k in kf_cache[vid] if k.shot_id == shot_id]
                center_kf = next((k for k in shot_kfs if k.is_shot_center), (shot_kfs[0] if shot_kfs else None))
                if center_kf:
                    thumb_url = f"/api/keyframes/{vid}/{Path(center_kf.file_path).name}"

        ts = float(r.get("timestamp_sec", 0.0))
        mins = int(ts // 60)
        secs = ts % 60
        formatted_time = f"{mins:02d}:{secs:05.2f}"

        candidates.append({
            "rank": rank,
            "score": round(float(r.get("score", 0.0)), 4),
            "video_id": vid,
            "shot_id": r.get("shot_id"),
            "keyframe_id": r.get("keyframe_id"),
            "timestamp_sec": round(ts, 2),
            "start_sec": round(float(r.get("start_sec", ts)), 2),
            "end_sec": round(float(r.get("end_sec", ts)), 2),
            "is_shot_pooled": r.get("is_shot_pooled", False),
            "thumbnail_url": thumb_url,
            "formatted_time": formatted_time,
        })
        rank += 1
        if len(candidates) >= top_k:
            break

    return {
        "query": query,
        "video_id": video_id,
        "total_results": len(candidates),
        "candidates": candidates,
    }


@app.get("/api/search/ocr")
def search_ocr_endpoint(
    query: str,
    video_id: Optional[str] = None,
    top_k: int = 25,
) -> Dict[str, Any]:
    """Searches on-screen text using SQLite FTS5 with BM25 ranking."""
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query string cannot be empty.")

    db = get_db()
    # Pass video_id directly to SQLite query for exact filtering without starving
    target_vid = video_id.strip() if video_id and video_id.strip() else None
    raw_hits = db.search_ocr(query, video_id=target_vid, limit=top_k)

    candidates = []
    kf_cache: Dict[str, Dict[str, Any]] = {}
    rank = 1

    for h in raw_hits:
        vid = h["video_id"]
        k_id = h["keyframe_id"]

        if vid not in kf_cache:
            kf_cache[vid] = {k.keyframe_id: k for k in db.get_keyframes(vid)}

        kf_obj = kf_cache[vid].get(k_id)
        thumb_url = None
        shot_id = kf_obj.shot_id if kf_obj else 0
        if kf_obj:
            thumb_url = f"/api/keyframes/{vid}/{Path(kf_obj.file_path).name}"

        ts = float(h.get("timestamp_sec", 0.0))
        mins = int(ts // 60)
        secs = ts % 60
        formatted_time = f"{mins:02d}:{secs:05.2f}"

        candidates.append({
            "rank": rank,
            "score": round(float(h.get("score", h.get("bm25_score", 0.0))), 4),
            "bm25_score": round(float(h.get("bm25_score", 0.0)), 4),
            "fuzzy_score": round(float(h.get("fuzzy_score", 0.0)), 4),
            "video_id": vid,
            "shot_id": shot_id,
            "keyframe_id": k_id,
            "timestamp_sec": round(ts, 2),
            "start_sec": round(ts, 2),
            "end_sec": round(ts, 2),
            "text_detected": h.get("text_detected", ""),
            "is_ocr": True,
            "thumbnail_url": thumb_url,
            "formatted_time": formatted_time,
        })
        rank += 1
        if len(candidates) >= top_k:
            break

    return {
        "query": query,
        "video_id": target_vid,
        "total_results": len(candidates),
        "candidates": candidates,
    }


@app.post("/api/search/unload")
def unload_search_model() -> Dict[str, str]:
    """Releases SigLIP2 model from GPU VRAM."""
    global _visual_extractor, _search_engine
    if _visual_extractor is not None:
        _visual_extractor.safe_unload()
        _visual_extractor = None
    if _search_engine is not None:
        _search_engine.safe_unload()
        _search_engine = None
    return {"status": "ok", "message": "GPU VRAM released"}


@app.get("/api/db/summary")
def get_db_summary() -> Dict[str, Any]:
    """Returns database summary, table counts, and all pipeline checkpoints."""
    db = get_db()
    summary = db.get_database_summary()

    raw_files = sorted([f.stem for f in VIDEOS_DIR.glob("*.mp4")]) if VIDEOS_DIR.exists() else []

    # Matrix of stages for each video
    stages_order = ["shots", "keyframes", "visual", "ocr"]
    cp_by_video: Dict[str, Dict[str, Any]] = {}
    for vid in raw_files:
        cp_by_video[vid] = {s: {"status": "PENDING", "count": 0} for s in stages_order}

    for cp in summary.get("checkpoints", []):
        v = cp["video_id"]
        s = cp["stage_name"]
        if v not in cp_by_video:
            cp_by_video[v] = {st: {"status": "PENDING", "count": 0} for st in stages_order}
        cp_by_video[v][s] = {
            "status": cp["status"],
            "count": cp.get("artifact_count", 0),
            "updated_at": cp.get("updated_at", ""),
            "error": cp.get("error_message")
        }

    matrix = []
    for vid, stages in cp_by_video.items():
        # Check if video has any completed stage
        has_completed = any(st.get("status") == "COMPLETED" for st in stages.values())
        matrix.append({"video_id": vid, "stages": stages, "has_completed": has_completed})

    # Sort matrix so videos with COMPLETED stages appear FIRST at the top of the table!
    matrix.sort(key=lambda x: (not x["has_completed"], x["video_id"]))

    summary["matrix"] = matrix
    return summary


# =========================================================================
# Task 06B: Temporal Context Filmstrip & DRES Live Submission Endpoints
# =========================================================================

def _load_env_file() -> None:
    """Loads environment variables from local .env file if present."""
    env_file = Path(".env")
    if env_file.exists():
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip("'\""))
        except Exception:
            pass

_load_env_file()

_dres_client: Optional[Any] = None
_dres_eval_id: str = os.environ.get("DRES_EVAL_ID", "offline_kis_eval")
_dres_history: List[Dict[str, Any]] = []


def get_dres_client() -> Any:
    """Lazy-initializes DRESClient singleton."""
    global _dres_client, _dres_eval_id
    if _dres_client is None:
        from src.submission.dres_client import DRESClient
        base_url = os.environ.get("DRES_BASE_URL", "https://eventretrieval.one")
        session_id = os.environ.get("DRES_SESSION_ID")
        eval_id = os.environ.get("DRES_EVAL_ID")
        if eval_id:
            _dres_eval_id = eval_id
        _dres_client = DRESClient(base_url=base_url, session_id=session_id)
    return _dres_client


@app.get("/api/videos/{video_id}/context")
def get_video_temporal_context(
    video_id: str,
    timestamp_sec: float = 0.0,
    window_sec: float = 15.0
) -> Dict[str, Any]:
    """
    Returns neighbor keyframes and OCR text within [timestamp_sec - window_sec, timestamp_sec + window_sec]
    for instant Filmstrip inspection (< 5ms) without loading full video stream.
    """
    db = get_db()
    keyframes = db.get_keyframes(video_id)
    if not keyframes:
        raise HTTPException(status_code=404, detail=f"No keyframes found for video '{video_id}'.")

    ocr_records = db.get_ocr_records(video_id)
    ocr_by_kf: Dict[str, List[str]] = {}
    for r in ocr_records:
        ocr_by_kf.setdefault(r.keyframe_id, []).append(r.text_detected)

    min_t = max(0.0, timestamp_sec - window_sec)
    max_t = timestamp_sec + window_sec

    context_frames = []
    for k in keyframes:
        if min_t <= k.timestamp_sec <= max_t:
            fname = Path(k.file_path).name
            context_frames.append({
                "keyframe_id": k.keyframe_id,
                "shot_id": k.shot_id,
                "timestamp_sec": round(k.timestamp_sec, 2),
                "delta_sec": round(k.timestamp_sec - timestamp_sec, 2),
                "image_url": f"/api/keyframes/{video_id}/{fname}",
                "ocr_texts": ocr_by_kf.get(k.keyframe_id, [])
            })

    return {
        "video_id": video_id,
        "center_sec": round(timestamp_sec, 2),
        "window_sec": window_sec,
        "total_frames": len(context_frames),
        "frames": context_frames
    }


@app.get("/api/dres/status")
def get_dres_status() -> Dict[str, Any]:
    """Returns current DRES connection state, active evaluation ID, and submission log."""
    client = get_dres_client()
    return {
        "base_url": client.base_url,
        "session_id": client.session_id,
        "evaluation_id": _dres_eval_id,
        "is_authenticated": bool(client.session_id),
        "submitted_count": len(client._submitted_cache),
        "history": list(reversed(_dres_history[-20:]))
    }


@app.post("/api/dres/session")
def configure_dres_session(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Configures DRES base URL, session token, or logs in with username/password."""
    global _dres_eval_id
    client = get_dres_client()

    base_url = str(payload.get("base_url", "")).strip()
    if base_url:
        client.base_url = base_url.rstrip("/")

    eval_id = str(payload.get("evaluation_id", "")).strip()
    if eval_id:
        _dres_eval_id = eval_id

    session_id = str(payload.get("session_id", "")).strip()
    if session_id:
        client.set_session_id(session_id)

    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", "")).strip()
    if username and password:
        try:
            client.login(username=username, password=password)
            active_ev = client.get_active_evaluation()
            if active_ev and active_ev.get("id"):
                _dres_eval_id = str(active_ev["id"])
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"DRES login failed: {e}")

    return get_dres_status()


@app.post("/api/dres/clear-cache")
def clear_dres_cache() -> Dict[str, Any]:
    """Clears local duplicate submission cache and history for a new competition query."""
    global _dres_history
    client = get_dres_client()
    client.clear_cache()
    _dres_history = []
    return {"status": "ok", "message": "Duplicate cache and submission history cleared."}


@app.post("/api/dres/submit")
def submit_to_dres(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Submits a KIS candidate moment to DRES API v2 (or simulates in dry-run mode)
    with millisecond conversion, extension stripping, and duplicate suppression.
    """
    from src.submission.dres_client import (
        create_kis_submission_payload,
        format_media_item_name,
        seconds_to_ms
    )

    video_id = str(payload.get("video_id", "")).strip()
    if not video_id:
        raise HTTPException(status_code=400, detail="video_id is required.")

    try:
        start_sec = float(payload.get("start_sec", 0.0))
        end_sec = float(payload.get("end_sec", 0.0))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="start_sec and end_sec must be valid numbers.")

    if start_sec < 0.0 or end_sec < start_sec:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid interval: start_sec ({start_sec}) must be >= 0 and <= end_sec ({end_sec})."
        )

    eval_id = str(payload.get("evaluation_id") or _dres_eval_id or "offline_kis_eval").strip()
    dry_run = bool(payload.get("dry_run", True))
    allow_duplicate = bool(payload.get("allow_duplicate", False))

    clean_id = format_media_item_name(video_id)
    start_ms = seconds_to_ms(start_sec)
    end_ms = seconds_to_ms(end_sec)
    dres_payload = create_kis_submission_payload(clean_id, start_sec, end_sec)

    client = get_dres_client()
    cache_key = (eval_id, clean_id, start_ms, end_ms)

    # Check duplicate submission cache
    if not allow_duplicate and cache_key in client._submitted_cache:
        msg = f"[DUPLICATE] {clean_id} [{start_ms}ms - {end_ms}ms] was already submitted for this query."
        logger.warning(msg)
        return {
            "status": "DUPLICATE_PREVENTED",
            "message": msg,
            "video_id": clean_id,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "payload": dres_payload
        }

    # Dry-run or offline mode when no live DRES server session is active
    if dry_run or not client.session_id:
        client._submitted_cache.add(cache_key)
        entry = {
            "mode": "DRY_RUN",
            "video_id": clean_id,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "evaluation_id": eval_id,
            "status": "DRY_RUN_ACCEPTED"
        }
        _dres_history.append(entry)
        logger.info(f"[OK] Dry-run KIS submission recorded: {clean_id} [{start_ms}ms - {end_ms}ms]")
        return {
            "status": "DRY_RUN_ACCEPTED",
            "message": f"[OK] Dry-Run Accepted: {clean_id} [{start_ms}ms - {end_ms}ms]",
            "video_id": clean_id,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "payload": dres_payload
        }

    # Live DRES server submission
    try:
        server_resp = client.submit_kis(
            evaluation_id=eval_id,
            video_id=clean_id,
            start_sec=start_sec,
            end_sec=end_sec,
            allow_duplicate=allow_duplicate
        )
        sub_status = str(server_resp.get("submission", server_resp.get("status", "SUBMITTED"))).upper()
        entry = {
            "mode": "LIVE",
            "video_id": clean_id,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "evaluation_id": eval_id,
            "status": sub_status,
            "response": server_resp
        }
        _dres_history.append(entry)
        return {
            "status": sub_status,
            "message": f"[OK] DRES Live Response ({sub_status}): {clean_id} [{start_ms}ms - {end_ms}ms]",
            "video_id": clean_id,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "payload": dres_payload,
            "server_response": server_resp
        }
    except Exception as e:
        logger.error(f"[ERROR] Live DRES submission failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# Mount static files and root SPA route
if (STATIC_DIR / "index.html").exists():
    @app.get("/")
    def serve_index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


def run() -> None:
    """Launches Uvicorn server."""
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"[INFO] Starting Debug Server at http://127.0.0.1:{port}")
    uvicorn.run("src.ui.debug_server:app", host="127.0.0.1", port=port, reload=True)


if __name__ == "__main__":
    run()
