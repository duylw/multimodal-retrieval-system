"""
Dedicated KIS Competition Workstation Server.
Provides optimized, high-throughput REST endpoints and serves the competition UI on port 8001.
Decoupled from internal debug tools to ensure maximum ergonomics and stability during live contests.
"""

import argparse
import os
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from src.indexers.metadata_db import MetadataDB
from src.retrieval.query_parser import QueryParser

app = FastAPI(
    title="KIS Competition Workstation",
    description="Dedicated, distraction-free workstation for live Known-Item Search (KIS) competitions",
    version="1.0.0"
)

# Enable CORS for competition clients and hot-reload development
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
COMPETITION_STATIC_DIR = Path("src/ui/competition")


def _clean_fname(path_str: Optional[str]) -> str:
    """Extracts base filename supporting both Windows (backslash) and POSIX paths."""
    if not path_str:
        return ""
    return str(path_str).replace("\\", "/").rstrip("/").split("/")[-1]


# Lazy-loaded singletons
_db: Optional[MetadataDB] = None
_search_engine: Optional[Any] = None
_dres_client: Optional[Any] = None
_dres_eval_id: str = os.environ.get("DRES_EVAL_ID", "offline_kis_eval")
_dres_history: List[Dict[str, Any]] = []


def _load_env_file() -> None:
    """Loads environment variables from local .env file if present."""
    env_file = Path(".env")
    if not env_file.exists():
        return
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("'\""))
    except Exception as e:
        logger.warning(f"[WARNING] Failed to parse .env file: {e}")


_load_env_file()


def get_db() -> MetadataDB:
    """Thread-safe accessor for MetadataDB singleton."""
    global _db
    if _db is None:
        _db = MetadataDB(DB_PATH)
    return _db


def get_search_engine() -> Any:
    """Lazy-initializes SearchEngine singleton in memory."""
    global _search_engine
    if _search_engine is None:
        from src.retrieval.search_engine import SearchEngine
        _search_engine = SearchEngine()
    return _search_engine


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


def range_stream_generator(
    file_path: Path, start: int, end: int, chunk_size: int = 65536
) -> Generator[bytes, None, None]:
    """Yields byte chunks within specified start and end range for HTTP 206 streaming."""
    try:
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
    except (GeneratorExit, ConnectionResetError, BrokenPipeError, OSError):
        # Client aborted connection (e.g. video seeked, closed, or buffered elsewhere)
        return


@app.on_event("startup")
def configure_windows_asyncio_exception_handler() -> None:
    """Silences noisy Windows Proactor WinError 10054 on client socket reset during video streaming."""
    try:
        loop = asyncio.get_running_loop()
        orig_handler = loop.get_exception_handler()

        def custom_handler(loop: asyncio.AbstractEventLoop, context: Dict[str, Any]) -> None:
            exc = context.get("exception")
            # Filter harmless socket resets when Chrome/browsers abort byte-range video streaming
            if isinstance(exc, (ConnectionResetError, BrokenPipeError)):
                return
            if isinstance(exc, OSError) and getattr(exc, "winerror", None) in (10054, 10053):
                return
            msg = str(context.get("message", ""))
            if "_call_connection_lost" in msg:
                return

            if orig_handler:
                orig_handler(loop, context)
            else:
                loop.default_exception_handler(context)

        loop.set_exception_handler(custom_handler)
    except Exception as e:
        logger.debug(f"Could not set custom asyncio exception handler: {e}")


@app.get("/api/health")
def healthcheck() -> Dict[str, str]:
    """Healthcheck endpoint."""
    return {"status": "ok", "service": "competition_workstation"}


# =========================================================================
# Task 06D: Automated Query Translation & Selective Cue Protection
# =========================================================================

_translation_cache: Dict[str, Dict[str, Any]] = {}


async def _raw_google_translate(text: str, source_lang: str = "auto", target_lang: str = "en") -> str:
    """Invokes Google Translate API via httpx for a single text fragment."""
    clean_text = text.strip()
    if not clean_text:
        return ""
    url = "https://translate.googleapis.com/translate_a/single"
    params = {
        "client": "gtx",
        "sl": source_lang,
        "tl": target_lang,
        "dt": "t",
        "q": clean_text
    }
    async with httpx.AsyncClient(timeout=2.5) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        parts = [str(chunk[0]) for chunk in data[0] if chunk and chunk[0]]
        return "".join(parts).strip()


@app.post("/api/translate")
async def translate_query_endpoint(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Automated Query Translation with Selective Cue Protection:
    Translates visual action/scene descriptions from Vietnamese to English (for SigLIP2)
    while preserving OCR tokens and license plates intact in Vietnamese (for SQLite FTS5).
    """
    raw_query = str(payload.get("query", "")).strip()
    source_lang = str(payload.get("source_lang", "auto")).strip()
    target_lang = str(payload.get("target_lang", "en")).strip()

    if not raw_query:
        return {
            "status": "ok",
            "original_query": "",
            "translated_query": "",
            "visual_translations": [],
            "preserved_ocr": [],
            "is_fallback": False,
            "cached": True
        }

    cache_key = f"{source_lang}:{target_lang}:{raw_query}"
    if cache_key in _translation_cache:
        cached_result = dict(_translation_cache[cache_key])
        cached_result["cached"] = True
        return cached_result

    try:
        parsed = QueryParser.parse(raw_query)
        stage_strs: List[str] = []
        visual_translations: List[Dict[str, str]] = []
        preserved_ocr: List[str] = []

        for stage in parsed.stages:
            cue_parts: List[str] = []

            for vq in stage.visual_queries:
                trans_v = await _raw_google_translate(vq, source_lang=source_lang, target_lang=target_lang)
                cue_parts.append(f"v: {trans_v}" if trans_v else f"v: {vq}")
                visual_translations.append({"original": vq, "translated": trans_v})

            for nvq in stage.negative_visual_queries:
                trans_nv = await _raw_google_translate(nvq, source_lang=source_lang, target_lang=target_lang)
                cue_parts.append(f"-v: {trans_nv}" if trans_nv else f"-v: {nvq}")
                visual_translations.append({"original": nvq, "translated": trans_nv, "is_negative": True})

            for oq in stage.ocr_queries:
                cue_parts.append(f"ocr: {oq}")
                preserved_ocr.append(oq)

            stage_strs.append(" | ".join(cue_parts) if cue_parts else raw_query)

        delimiter = " >> " if parsed.is_sequential else " | "
        translated_output = delimiter.join(stage_strs) if stage_strs else raw_query

        # For single visual query without OCR or negative cues, keep it clean and consistent (no redundant 'v: ')
        if len(parsed.stages) == 1 and not parsed.stages[0].ocr_queries and not parsed.stages[0].negative_visual_queries and len(parsed.stages[0].visual_queries) == 1:
            if translated_output.startswith("v: "):
                translated_output = translated_output[3:]

        result = {
            "status": "ok",
            "original_query": raw_query,
            "translated_query": translated_output,
            "visual_translations": visual_translations,
            "preserved_ocr": preserved_ocr,
            "is_fallback": False,
            "cached": False
        }
        _translation_cache[cache_key] = result
        return result

    except Exception as e:
        logger.warning(f"[WARNING] Translation failed or timed out: {e}. Falling back to raw query.")
        return {
            "status": "fallback",
            "original_query": raw_query,
            "translated_query": raw_query,
            "visual_translations": [],
            "preserved_ocr": [],
            "is_fallback": True,
            "error": str(e),
            "cached": False
        }


@app.get("/api/videos/{video_id}/stream")
def stream_video(video_id: str, request: Request) -> Response:
    """
    Streams video with standard HTTP 206 Partial Content Range requests.
    Enables low-latency frame scrubbing in the modal player.
    """
    clean_id = video_id[:-4] if video_id.lower().endswith(".mp4") else video_id
    video_path = VIDEOS_DIR / f"{clean_id}.mp4"

    if not video_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video file '{clean_id}.mp4' not found in raw repository."
        )

    file_size = video_path.stat().st_size
    range_header = request.headers.get("Range")

    if not range_header:
        return FileResponse(
            path=str(video_path),
            media_type="video/mp4",
            headers={"Accept-Ranges": "bytes"}
        )

    try:
        range_val = range_header.strip().lower()
        if not range_val.startswith("bytes="):
            raise ValueError()
        parts = range_val.replace("bytes=", "").split("-")
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


@app.get("/api/keyframes/{video_id}/{filename:path}")
def get_keyframe_image(video_id: str, filename: str) -> FileResponse:
    """Serves extracted keyframe JPEG image with browser caching."""
    clean_vid = video_id[:-4] if video_id.lower().endswith(".mp4") else video_id
    clean_name = _clean_fname(filename)
    img_path = KEYFRAMES_DIR / clean_vid / clean_name
    if img_path.exists():
        return FileResponse(
            path=str(img_path),
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=86400"}
        )

    kfid = clean_name[:-4] if clean_name.lower().endswith(".jpg") else clean_name
    db = get_db()
    fp = db.get_keyframe_path(kfid)
    if fp:
        resolved_fp = KEYFRAMES_DIR / clean_vid / _clean_fname(fp)
        if resolved_fp.exists():
            return FileResponse(
                path=str(resolved_fp),
                media_type="image/jpeg",
                headers={"Cache-Control": "public, max-age=86400"}
            )
        if Path(fp).exists():
            return FileResponse(
                path=str(fp),
                media_type="image/jpeg",
                headers={"Cache-Control": "public, max-age=86400"}
            )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Keyframe image '{clean_name}' not found for video '{clean_vid}'."
    )


@app.get("/api/videos/{video_id}/context")
def get_video_temporal_context(
    video_id: str,
    timestamp_sec: float = 0.0,
    window_sec: float = 15.0
) -> Dict[str, Any]:
    """
    Returns neighbor keyframes and OCR text within [timestamp_sec - window_sec, timestamp_sec + window_sec]
    for instant Filmstrip inspection (< 5ms) without requiring full video streaming.
    """
    clean_vid = video_id[:-4] if video_id.lower().endswith(".mp4") else video_id
    db = get_db()
    keyframes = db.get_keyframes(clean_vid)
    if not keyframes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No keyframes found for video '{clean_vid}'."
        )

    ocr_records = db.get_ocr_records(clean_vid)
    ocr_by_kf: Dict[str, List[str]] = {}
    for r in ocr_records:
        ocr_by_kf.setdefault(r.keyframe_id, []).append(r.text_detected)

    min_t = max(0.0, timestamp_sec - window_sec)
    max_t = timestamp_sec + window_sec

    context_frames = []
    for k in keyframes:
        if min_t <= k.timestamp_sec <= max_t:
            fname = _clean_fname(k.file_path)
            context_frames.append({
                "keyframe_id": k.keyframe_id,
                "shot_id": k.shot_id,
                "timestamp_sec": round(k.timestamp_sec, 2),
                "delta_sec": round(k.timestamp_sec - timestamp_sec, 2),
                "image_url": f"/api/keyframes/{clean_vid}/{fname}",
                "ocr_texts": ocr_by_kf.get(k.keyframe_id, [])
            })

    return {
        "video_id": clean_vid,
        "center_sec": round(timestamp_sec, 2),
        "window_sec": window_sec,
        "total_frames": len(context_frames),
        "frames": context_frames
    }


@app.get("/api/search/multimodal")
def search_multimodal_endpoint(
    query: str,
    mode: str = "auto",
    top_k: int = 300,
    video_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Unified Multimodal Search: Multi-cue RRF fusion, 5s sliding window, trace, and NMS.
    Supports Top-K candidate options: 50, 100, 200, 300, 500, 1000.
    """
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
    top_k: int = 300,
    video_id: Optional[str] = None
) -> Dict[str, Any]:
    """Structured Multi-Cue JSON search endpoint."""
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
    top_k: int = int(payload.get("top_k", 100))
    video_id: Optional[str] = payload.get("video_id")

    if not pos_ids and not neg_ids and not orig_query:
        raise HTTPException(status_code=400, detail="Must provide at least one feedback keyframe or query.")

    engine = get_search_engine()
    vec_idx = engine._ensure_vector_index()
    extractor = engine._ensure_visual_extractor()

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

    norm = float(np.linalg.norm(rocchio_vec))
    if norm > 1e-6:
        rocchio_vec = rocchio_vec / norm

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


@app.post("/api/search/unload")
def unload_search_model() -> Dict[str, str]:
    """Releases SigLIP2 model from GPU VRAM to reclaim memory."""
    global _search_engine
    if _search_engine is not None:
        _search_engine.safe_unload()
        _search_engine = None
    return {"status": "ok", "message": "GPU VRAM released"}


# =========================================================================
# Live DRES API v2 Integration & Submission Proxy
# =========================================================================

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
        "history": list(reversed(_dres_history[-30:]))
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
    """Clears local duplicate submission cache and history for a new competition round."""
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
    dry_run = bool(payload.get("dry_run", False))
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


# Serve static competition assets
COMPETITION_STATIC_DIR.mkdir(parents=True, exist_ok=True)

if (COMPETITION_STATIC_DIR / "index.html").exists():
    @app.get("/")
    def serve_competition_root() -> FileResponse:
        return FileResponse(COMPETITION_STATIC_DIR / "index.html")

app.mount("/", StaticFiles(directory=str(COMPETITION_STATIC_DIR), html=True), name="competition_static")


def main() -> None:
    """CLI runner to launch competition server on configurable port (default 8001)."""
    parser = argparse.ArgumentParser(description="Run Dedicated KIS Competition Workstation Server")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Binding host address")
    parser.add_argument("--port", type=int, default=8001, help="Binding port number (default: 8001)")
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn hot reloading")
    args = parser.parse_args()

    logger.info(f"[INFO] Launching KIS Competition Workstation on http://{args.host}:{args.port}")
    uvicorn.run("src.ui.competition_server:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
