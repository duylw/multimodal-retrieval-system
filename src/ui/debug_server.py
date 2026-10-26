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
    videos = db.get_videos()
    results = []

    for v in videos:
        vid = v["video_id"]
        shots = db.get_shots(vid)
        keyframes = db.get_keyframes(vid)
        raw_path = VIDEOS_DIR / f"{vid}.mp4"
        if not raw_path.exists():
            # Check for other extensions
            raw_path = next(VIDEOS_DIR.glob(f"{vid}.*"), raw_path)

        results.append({
            "video_id": vid,
            "file_name": v.get("file_name", f"{vid}.mp4"),
            "duration_sec": v.get("duration_sec", 0.0),
            "fps": v.get("fps", 0.0),
            "width": v.get("width", 0),
            "height": v.get("height", 0),
            "total_frames": v.get("total_frames", 0),
            "shot_count": len(shots),
            "keyframe_count": len(keyframes),
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
            })

    return {
        "video": video_info,
        "total_shots": len(shots),
        "total_keyframes": len(keyframes),
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
    """Serves extracted keyframe JPEG image."""
    img_path = KEYFRAMES_DIR / video_id / filename
    if not img_path.exists():
        raise HTTPException(status_code=404, detail="Keyframe image not found.")
    return FileResponse(path=str(img_path), media_type="image/jpeg")


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
