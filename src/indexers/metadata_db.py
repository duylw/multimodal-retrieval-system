"""
SQLite database manager for video metadata, shot boundaries, keyframes, and pipeline checkpoints.
Handles persistence, retrieval, fault-tolerant state tracking, and atomic rollbacks.
"""

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
from loguru import logger

from src.common.types import ShotRecord, KeyframeRecord


class MetadataDB:
    """Manages SQLite storage for video catalog, shots, keyframes, and pipeline checkpoints."""

    def __init__(self, db_path: str = "data/metadata.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        """Returns a connection with foreign keys enabled and row factory."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_tables(self) -> None:
        """Initializes relational schema if not already present."""
        with self._get_connection() as conn:
            # Video catalog table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS videos (
                    video_id TEXT PRIMARY KEY,
                    file_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    duration_sec REAL NOT NULL,
                    fps REAL NOT NULL,
                    width INTEGER NOT NULL,
                    height INTEGER NOT NULL,
                    total_frames INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Shot boundaries table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS shots (
                    shot_id INTEGER NOT NULL,
                    video_id TEXT NOT NULL,
                    start_frame INTEGER NOT NULL,
                    end_frame INTEGER NOT NULL,
                    start_sec REAL NOT NULL,
                    end_sec REAL NOT NULL,
                    duration_sec REAL NOT NULL,
                    PRIMARY KEY (video_id, shot_id),
                    FOREIGN KEY (video_id) REFERENCES videos(video_id) ON DELETE CASCADE
                );
            """)

            # Keyframes table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS keyframes (
                    keyframe_id TEXT PRIMARY KEY,
                    video_id TEXT NOT NULL,
                    shot_id INTEGER NOT NULL,
                    frame_idx INTEGER NOT NULL,
                    timestamp_sec REAL NOT NULL,
                    file_path TEXT NOT NULL,
                    is_shot_center INTEGER NOT NULL,
                    blur_score REAL DEFAULT 0.0,
                    FOREIGN KEY (video_id, shot_id) REFERENCES shots(video_id, shot_id) ON DELETE CASCADE
                );
            """)

            # Pipeline execution checkpoints for fault tolerance, status tracking, and resumption
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pipeline_checkpoints (
                    video_id TEXT NOT NULL,
                    stage_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    artifact_count INTEGER DEFAULT 0,
                    error_message TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (video_id, stage_name)
                );
            """)
            conn.commit()

    # =========================================================================
    # Pipeline Checkpointing & Fault Tolerance APIs
    # =========================================================================

    def is_stage_completed(self, video_id: str, stage_name: str) -> bool:
        """Checks whether a given pipeline stage has completed successfully for a video."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT status FROM pipeline_checkpoints WHERE video_id = ? AND stage_name = ?;",
                (video_id, stage_name)
            )
            row = cursor.fetchone()
            return row is not None and row["status"].upper() == "COMPLETED"

    def set_checkpoint(
        self,
        video_id: str,
        stage_name: str,
        status: str,
        artifact_count: int = 0,
        error_message: Optional[str] = None
    ) -> None:
        """Updates or inserts the status of a pipeline stage."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO pipeline_checkpoints (video_id, stage_name, status, artifact_count, error_message, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(video_id, stage_name) DO UPDATE SET
                    status = excluded.status,
                    artifact_count = excluded.artifact_count,
                    error_message = excluded.error_message,
                    updated_at = CURRENT_TIMESTAMP;
            """, (video_id, stage_name, status.upper(), artifact_count, error_message))
            conn.commit()

    def get_checkpoint(self, video_id: str, stage_name: str) -> Optional[Dict[str, Any]]:
        """Retrieves checkpoint info for a specific video and stage."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM pipeline_checkpoints WHERE video_id = ? AND stage_name = ?;",
                (video_id, stage_name)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_checkpoints(self, video_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves all pipeline checkpoints, optionally filtered by video_id."""
        with self._get_connection() as conn:
            if video_id:
                cursor = conn.execute(
                    "SELECT * FROM pipeline_checkpoints WHERE video_id = ? ORDER BY stage_name ASC;",
                    (video_id,)
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM pipeline_checkpoints ORDER BY video_id ASC, stage_name ASC;"
                )
            return [dict(row) for row in cursor.fetchall()]

    def reset_stage(self, video_id: str, stage_name: str) -> None:
        """Deletes checkpoint record for a given stage, resetting it to PENDING."""
        with self._get_connection() as conn:
            conn.execute(
                "DELETE FROM pipeline_checkpoints WHERE video_id = ? AND stage_name = ?;",
                (video_id, stage_name)
            )
            conn.commit()

    # =========================================================================
    # Atomic Rollback & Deletion Helpers
    # =========================================================================

    def delete_shots(self, video_id: str) -> None:
        """Deletes all shots for a given video (cascades to keyframes)."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM shots WHERE video_id = ?;", (video_id,))
            conn.commit()

    def delete_keyframes(self, video_id: str) -> None:
        """Deletes all keyframe records for a given video."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM keyframes WHERE video_id = ?;", (video_id,))
            conn.commit()

    def delete_video(self, video_id: str) -> None:
        """Deletes a video catalog record and all associated relational records."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM videos WHERE video_id = ?;", (video_id,))
            conn.commit()

    # =========================================================================
    # Data Access APIs (Videos, Shots, Keyframes)
    # =========================================================================

    def save_video(
        self,
        video_id: str,
        file_name: str,
        file_path: str,
        duration_sec: float,
        fps: float,
        width: int,
        height: int,
        total_frames: int
    ) -> None:
        """Inserts or updates a video record in the catalog."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO videos (video_id, file_name, file_path, duration_sec, fps, width, height, total_frames)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(video_id) DO UPDATE SET
                    file_name = excluded.file_name,
                    file_path = excluded.file_path,
                    duration_sec = excluded.duration_sec,
                    fps = excluded.fps,
                    width = excluded.width,
                    height = excluded.height,
                    total_frames = excluded.total_frames;
            """, (video_id, file_name, file_path, duration_sec, fps, width, height, total_frames))
            conn.commit()

    def save_shots(self, shots: List[ShotRecord]) -> None:
        """Batch saves shot boundary records into SQLite."""
        if not shots:
            return
        with self._get_connection() as conn:
            conn.executemany("""
                INSERT INTO shots (shot_id, video_id, start_frame, end_frame, start_sec, end_sec, duration_sec)
                VALUES (:shot_id, :video_id, :start_frame, :end_frame, :start_sec, :end_sec, :duration_sec)
                ON CONFLICT(video_id, shot_id) DO UPDATE SET
                    start_frame = excluded.start_frame,
                    end_frame = excluded.end_frame,
                    start_sec = excluded.start_sec,
                    end_sec = excluded.end_sec,
                    duration_sec = excluded.duration_sec;
            """, [s.__dict__ for s in shots])
            conn.commit()

    def get_shots(self, video_id: str) -> List[ShotRecord]:
        """Retrieves all shots for a given video, sorted chronologically."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM shots WHERE video_id = ? ORDER BY start_sec ASC;",
                (video_id,)
            )
            rows = cursor.fetchall()
            return [
                ShotRecord(
                    video_id=r["video_id"],
                    shot_id=r["shot_id"],
                    start_frame=r["start_frame"],
                    end_frame=r["end_frame"],
                    start_sec=r["start_sec"],
                    end_sec=r["end_sec"],
                    duration_sec=r["duration_sec"]
                )
                for r in rows
            ]

    def save_keyframes(self, keyframes: List[KeyframeRecord]) -> None:
        """Batch saves keyframe metadata into SQLite."""
        if not keyframes:
            return
        with self._get_connection() as conn:
            conn.executemany("""
                INSERT INTO keyframes (
                    keyframe_id, video_id, shot_id, frame_idx, timestamp_sec, file_path, is_shot_center, blur_score
                )
                VALUES (:keyframe_id, :video_id, :shot_id, :frame_idx, :timestamp_sec, :file_path, :is_shot_center, :blur_score)
                ON CONFLICT(keyframe_id) DO UPDATE SET
                    frame_idx = excluded.frame_idx,
                    timestamp_sec = excluded.timestamp_sec,
                    file_path = excluded.file_path,
                    is_shot_center = excluded.is_shot_center,
                    blur_score = excluded.blur_score;
            """, [k.__dict__ for k in keyframes])
            conn.commit()

    def get_keyframes(self, video_id: str) -> List[KeyframeRecord]:
        """Retrieves all keyframes for a given video, sorted by timestamp."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM keyframes WHERE video_id = ? ORDER BY timestamp_sec ASC;",
                (video_id,)
            )
            rows = cursor.fetchall()
            return [
                KeyframeRecord(
                    keyframe_id=r["keyframe_id"],
                    video_id=r["video_id"],
                    shot_id=r["shot_id"],
                    frame_idx=r["frame_idx"],
                    timestamp_sec=r["timestamp_sec"],
                    file_path=r["file_path"],
                    is_shot_center=bool(r["is_shot_center"]),
                    blur_score=r["blur_score"]
                )
                for r in rows
            ]

    def get_videos(self) -> List[Dict[str, Any]]:
        """Retrieves catalog list of all recorded videos."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM videos ORDER BY video_id ASC;")
            return [dict(row) for row in cursor.fetchall()]

    def get_video(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves metadata record for a specific video."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM videos WHERE video_id = ?;", (video_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_database_summary(self) -> Dict[str, Any]:
        """Returns aggregate row counts and checkpoint breakdown across all tables."""
        with self._get_connection() as conn:
            video_cnt = conn.execute("SELECT COUNT(*) FROM videos;").fetchone()[0]
            shot_cnt = conn.execute("SELECT COUNT(*) FROM shots;").fetchone()[0]
            kf_cnt = conn.execute("SELECT COUNT(*) FROM keyframes;").fetchone()[0]
            cp_rows = conn.execute(
                "SELECT video_id, stage_name, status, artifact_count, updated_at FROM pipeline_checkpoints;"
            ).fetchall()

            return {
                "total_videos": video_cnt,
                "total_shots": shot_cnt,
                "total_keyframes": kf_cnt,
                "checkpoints": [dict(r) for r in cp_rows],
            }
