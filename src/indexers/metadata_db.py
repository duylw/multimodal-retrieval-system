"""
SQLite database manager for video metadata, shot boundaries, keyframes, and pipeline checkpoints.
Handles persistence, retrieval, fault-tolerant state tracking, and atomic rollbacks.
"""

import json
import re
import sqlite3
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
from loguru import logger

from src.common.types import ShotRecord, KeyframeRecord, OCRRecord

_WORD_TOKEN_RE = re.compile(r"[a-z0-9]+")


def fold_vietnamese(text: str) -> str:
    """Folds Vietnamese diacritics and d-stroke to base unaccented Latin characters."""
    if not text:
        return ""
    nfd = unicodedata.normalize("NFD", text)
    unaccented = re.sub(r"[\u0300-\u036f]", "", nfd)
    return unaccented.replace("đ", "d").replace("Đ", "D").lower().strip()


def expand_ocr_terms(raw_query: str) -> List[str]:
    """
    Expands OCR query into comprehensive lexical tokens for FTS5 & fuzzy search:
    1. Preserves original words (accented Vietnamese).
    2. Adds diacritic-folded unaccented forms (e.g. 'kế hoạch' -> 'ke hoach').
    3. Splits alphanumeric boundaries (e.g. 'HTV9' -> 'HTV', '9', '51B' -> '51', 'B').
    4. Normalizes punctuation.
    """
    terms: List[str] = []
    seen: set = set()
    clean_q = raw_query.replace('"', '""').replace("đ", "d").replace("Đ", "D")
    for word in clean_q.split():
        clean_w = word.strip('"\'.,:;!?()[]{}<>-')
        if not clean_w:
            continue
        if clean_w not in seen:
            seen.add(clean_w)
            terms.append(clean_w)
        folded = fold_vietnamese(clean_w)
        if folded and folded not in seen:
            seen.add(folded)
            terms.append(folded)
        # Split letter/digit transitions (HTV9 -> HTV, 9; 51B -> 51, B)
        sub_tokens = re.findall(r"[a-zA-ZÀ-ỹ]+|\d+", clean_w)
        if len(sub_tokens) > 1:
            for st in sub_tokens:
                if (len(st) >= 2 or st.isdigit()) and st not in seen:
                    seen.add(st)
                    terms.append(st)
                st_folded = fold_vietnamese(st)
                if st_folded and st_folded not in seen:
                    seen.add(st_folded)
                    terms.append(st_folded)
    return terms


class MetadataDB:
    """Manages SQLite storage for video catalog, shots, keyframes, and pipeline checkpoints."""

    def __init__(self, db_path: str = "data/metadata.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        """Returns a connection with foreign keys enabled, WAL journal mode, and row factory."""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
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

            # OCR text detection records table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ocr_records (
                    ocr_id TEXT PRIMARY KEY,
                    video_id TEXT NOT NULL,
                    keyframe_id TEXT NOT NULL,
                    timestamp_sec REAL NOT NULL,
                    text_detected TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    bbox_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (video_id) REFERENCES videos(video_id) ON DELETE CASCADE,
                    FOREIGN KEY (keyframe_id) REFERENCES keyframes(keyframe_id) ON DELETE CASCADE
                );
            """)

            # SQLite FTS5 full-text search virtual table for on-screen text (with automatic diacritic folding)
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS ocr_fts USING fts5(
                    ocr_id UNINDEXED,
                    video_id UNINDEXED,
                    keyframe_id UNINDEXED,
                    timestamp_sec UNINDEXED,
                    text_detected,
                    tokenize = 'unicode61 remove_diacritics 2'
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

    def get_keyframe_path(self, keyframe_id: str) -> Optional[str]:
        """Retrieves the file_path for a keyframe_id via indexed primary key lookup."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT file_path FROM keyframes WHERE keyframe_id = ? LIMIT 1;",
                (keyframe_id,)
            )
            row = cursor.fetchone()
            return row["file_path"] if row else None

    def get_keyframe_paths(self, keyframe_ids: Sequence[str]) -> Dict[str, str]:
        """Batch retrieves file_path mappings for multiple keyframe_ids using a single connection."""
        unique_ids = list(dict.fromkeys(kf for kf in keyframe_ids if kf))
        if not unique_ids:
            return {}

        paths: Dict[str, str] = {}
        chunk_size = 900
        with self._get_connection() as conn:
            for start in range(0, len(unique_ids), chunk_size):
                chunk = unique_ids[start:start + chunk_size]
                placeholders = ", ".join(["?"] * len(chunk))
                rows = conn.execute(
                    f"SELECT keyframe_id, file_path FROM keyframes WHERE keyframe_id IN ({placeholders});",
                    tuple(chunk),
                ).fetchall()
                for row in rows:
                    if row["file_path"]:
                        paths[row["keyframe_id"]] = row["file_path"]
        return paths

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

    def save_ocr_records(self, records: List[OCRRecord]) -> None:
        """Batch saves OCR detection records into SQLite relational and FTS5 tables atomically."""
        if not records:
            return
        video_id = records[0].video_id
        with self._get_connection() as conn:
            # Atomically purge existing records for this video to prevent duplicate rows in FTS5
            conn.execute("DELETE FROM ocr_records WHERE video_id = ?;", (video_id,))
            conn.execute("DELETE FROM ocr_fts WHERE video_id = ?;", (video_id,))

            conn.executemany("""
                INSERT INTO ocr_records (
                    ocr_id, video_id, keyframe_id, timestamp_sec, text_detected, confidence, bbox_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?);
            """, [
                (
                    r.ocr_id,
                    r.video_id,
                    r.keyframe_id,
                    r.timestamp_sec,
                    r.text_detected,
                    r.confidence,
                    json.dumps(r.bbox) if r.bbox else None
                )
                for r in records
            ])

            # Group detected texts per keyframe for keyframe-level FTS5 document aggregation
            kf_groups: Dict[str, Dict[str, Any]] = {}
            for r in records:
                if r.keyframe_id not in kf_groups:
                    kf_groups[r.keyframe_id] = {
                        "video_id": r.video_id,
                        "timestamp_sec": r.timestamp_sec,
                        "texts": []
                    }
                kf_groups[r.keyframe_id]["texts"].append(r.text_detected)

            conn.executemany("""
                INSERT INTO ocr_fts (ocr_id, video_id, keyframe_id, timestamp_sec, text_detected)
                VALUES (?, ?, ?, ?, ?);
            """, [
                (
                    k_id,
                    g["video_id"],
                    k_id,
                    g["timestamp_sec"],
                    " ".join(g["texts"]).replace('đ', 'd').replace('Đ', 'D')
                )
                for k_id, g in kf_groups.items()
            ])
            conn.commit()

    def rebuild_ocr_fts_by_keyframe(self) -> int:
        """
        Rebuilds ocr_fts table to aggregate text detections at the keyframe level
        (one FTS5 document per unique keyframe_id with space-concatenated text).
        Eliminates bounding-box fragmentation across multi-line signage and banners.
        Returns the number of aggregated keyframe documents inserted.
        """
        with self._get_connection() as conn:
            conn.execute("DROP TABLE IF EXISTS ocr_fts;")
            conn.execute("""
                CREATE VIRTUAL TABLE ocr_fts USING fts5(
                    ocr_id UNINDEXED,
                    video_id UNINDEXED,
                    keyframe_id UNINDEXED,
                    timestamp_sec UNINDEXED,
                    text_detected,
                    tokenize = 'unicode61 remove_diacritics 2'
                );
            """)
            cursor = conn.execute("""
                INSERT INTO ocr_fts (ocr_id, video_id, keyframe_id, timestamp_sec, text_detected)
                SELECT 
                    keyframe_id, 
                    video_id, 
                    keyframe_id, 
                    MIN(timestamp_sec), 
                    REPLACE(REPLACE(GROUP_CONCAT(text_detected, ' '), 'đ', 'd'), 'Đ', 'D')
                FROM ocr_records
                GROUP BY keyframe_id;
            """)
            count = cursor.rowcount
            conn.commit()
            logger.info(f"[OK] Rebuilt ocr_fts at keyframe level: {count} aggregated keyframes indexed.")
            return count

    def delete_ocr_records(self, video_id: str) -> None:
        """Deletes all OCR records for a video from both relational and FTS5 tables."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM ocr_records WHERE video_id = ?;", (video_id,))
            conn.execute("DELETE FROM ocr_fts WHERE video_id = ?;", (video_id,))
            conn.commit()

    def get_ocr_records(self, video_id: str) -> List[OCRRecord]:
        """Retrieves all OCR records for a given video sorted by timestamp."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM ocr_records WHERE video_id = ? ORDER BY timestamp_sec ASC;",
                (video_id,)
            )
            rows = cursor.fetchall()
            return [
                OCRRecord(
                    ocr_id=r["ocr_id"],
                    video_id=r["video_id"],
                    keyframe_id=r["keyframe_id"],
                    timestamp_sec=r["timestamp_sec"],
                    text_detected=r["text_detected"],
                    bbox=json.loads(r["bbox_json"]) if r["bbox_json"] else [],
                    confidence=r["confidence"]
                )
                for r in rows
            ]

    @staticmethod
    def _build_ocr_scope_sql(
        video_id: Optional[str] = None,
        allowed_batches: Optional[Set[str]] = None,
        excluded_videos: Optional[Set[str]] = None,
    ) -> Tuple[str, List[Any], bool]:
        """Builds parameterized SQL scope predicates for video_id, batch prefixes, and exclusions."""
        clauses: List[str] = []
        params: List[Any] = []

        if video_id:
            clauses.append("video_id = ?")
            params.append(video_id)

        if allowed_batches is not None:
            clean_batches = sorted({b.strip().upper() for b in allowed_batches if b and b.strip()})
            if not clean_batches:
                return "", [], True
            batch_parts: List[str] = []
            for batch in clean_batches:
                escaped = batch.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                batch_parts.append("(video_id LIKE ? ESCAPE '\\' OR UPPER(video_id) = ?)")
                params.extend([f"{escaped}\\_%", batch])
            clauses.append(f"({' OR '.join(batch_parts)})")

        if excluded_videos and len(excluded_videos) <= 500:
            sorted_excluded = sorted(excluded_videos)
            placeholders = ", ".join(["?"] * len(sorted_excluded))
            clauses.append(f"video_id NOT IN ({placeholders})")
            params.extend(sorted_excluded)

        return (" AND ".join(clauses)), params, False

    def search_ocr(
        self,
        query: str,
        video_id: Optional[str] = None,
        limit: int = 100,
        allowed_batches: Optional[Set[str]] = None,
        excluded_videos: Optional[Set[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Executes Two-Stage Hybrid Search across detected on-screen text:
        Stage 1: Coarse candidate retrieval via SQLite FTS5 with Soft OR expansion & BM25 ranking.
        Stage 2: Fine-grained fuzzy rescoring via token-level SequenceMatcher & diacritic folding.
        Provides robust resilience against OCR typos, character misrecognitions, and diacritic noise.
        """
        raw_query = query.strip()
        if not raw_query:
            return []

        scope_sql, scope_params, is_empty_scope = self._build_ocr_scope_sql(
            video_id=video_id,
            allowed_batches=allowed_batches,
            excluded_videos=excluded_videos,
        )
        if is_empty_scope:
            return []

        # Clean query, escape quotes, and fold Vietnamese 'đ' to Latin 'd' for FTS5 matching
        clean_query = raw_query.replace('"', '""').replace('đ', 'd').replace('Đ', 'D')

        # Expand query into multi-format lexical tokens (accented, unaccented, alphanumeric sub-tokens)
        expanded_tokens = expand_ocr_terms(raw_query)
        # Keep tokens with len >= 2 or digits to prevent noisy single-character FTS matching
        terms = [t for t in expanded_tokens if len(t) >= 2 or t.isdigit()]
        if not terms:
            terms = [t for t in clean_query.split() if t]
        if not terms:
            return []

        # Stage 1: Coarse Candidate Retrieval (Soft OR with prefix wildcard matching)
        # Using OR prevents dropping candidate frames when a single word has an OCR typo
        fts_query = " OR ".join([f'"{t}"*' for t in terms])

        where_clause = "WHERE ocr_fts MATCH ?"
        params: List[Any] = [fts_query]
        if scope_sql:
            where_clause += f" AND {scope_sql}"
            params.extend(scope_params)

        # Retrieve a bounded candidate pool for fuzzy reranking without triggering 10k+ row scans
        pool_limit = max(limit, min(max(limit * 4, 500), 2500))
        params.append(pool_limit)

        sql = f"""
            SELECT 
                ocr_id,
                video_id,
                keyframe_id,
                timestamp_sec,
                text_detected,
                -bm25(ocr_fts) AS bm25_score
            FROM ocr_fts
            {where_clause}
            ORDER BY bm25_score DESC
            LIMIT ?;
        """

        with self._get_connection() as conn:
            try:
                cursor = conn.execute(sql, tuple(params))
                rows = [dict(r) for r in cursor.fetchall()]
            except sqlite3.OperationalError:
                # Fallback to exact phrase match if complex prefix expression fails
                params[0] = f'"{clean_query}"'
                cursor = conn.execute(sql, tuple(params))
                rows = [dict(r) for r in cursor.fetchall()]

            # Substring LIKE fallback only when FTS returns sparse hits (e.g. hyphenated plates/codes)
            like_threshold = min(limit, 50)
            if len(rows) < like_threshold:
                seen_kf_ids = {r["keyframe_id"] for r in rows if r.get("keyframe_id")}
                like_candidates_to_try = [raw_query.strip()]
                for t in terms:
                    if len(t) >= 3 and t not in like_candidates_to_try:
                        like_candidates_to_try.append(t)

                like_scope_clause = f"AND {scope_sql}" if scope_sql else ""
                for term in like_candidates_to_try[:4]:
                    remaining = pool_limit - len(rows)
                    if remaining <= 0:
                        break
                    like_sql = f"""
                        SELECT ocr_id, video_id, keyframe_id, timestamp_sec, text_detected, 1.5 AS bm25_score
                        FROM ocr_records
                        WHERE text_detected LIKE ?
                        {like_scope_clause}
                        LIMIT ?;
                    """
                    like_params: List[Any] = [f"%{term}%"]
                    if scope_params:
                        like_params.extend(scope_params)
                    like_params.append(min(100, remaining))

                    try:
                        for r in conn.execute(like_sql, tuple(like_params)).fetchall():
                            rd = dict(r)
                            kf_id = rd.get("keyframe_id")
                            if kf_id and kf_id not in seen_kf_ids:
                                seen_kf_ids.add(kf_id)
                                rows.append(rd)
                    except Exception as e:
                        logger.warning(f"[WARNING] Substring LIKE fallback query failed: {e}")

        if not rows:
            return []

        # Stage 2: Fine-Grained Token-Level Fuzzy Rescoring (exact-match short-circuit + pair memoization)
        folded_query = fold_vietnamese(raw_query)
        query_words = _WORD_TOKEN_RE.findall(folded_query)
        spaceless_query = "".join(query_words)

        unique_qw = list(dict.fromkeys(query_words))
        # Pre-index seq2 once per query word so Difflib avoids rebuilding b2j dicts inside the row loop
        sm_by_qw = {qw: SequenceMatcher(None, "", qw) for qw in unique_qw}
        len_by_qw = {qw: len(qw) for qw in unique_qw}
        pair_sim_cache: Dict[Tuple[str, str], float] = {}

        max_bm25 = max((r.get("bm25_score", 1.0) for r in rows), default=1.0)
        if max_bm25 <= 0.0:
            max_bm25 = 1.0

        lq_full = len(folded_query)
        n_qwords = len(query_words)
        check_phrase_sim = lq_full >= 4

        for r in rows:
            text_detected = r.get("text_detected", "")
            folded_text = fold_vietnamese(text_detected)
            cand_words = _WORD_TOKEN_RE.findall(folded_text)
            spaceless_text = "".join(cand_words)

            # Word-level alignment similarity with O(1) exact check & upper-bound pruning
            if n_qwords and cand_words:
                cand_word_set = set(cand_words)
                total_w_sim = 0.0
                for qw in query_words:
                    if qw in cand_word_set:
                        total_w_sim += 1.0
                        continue
                    best_w_sim = 0.0
                    lq = len_by_qw[qw]
                    sm = sm_by_qw[qw]
                    for cw in cand_word_set:
                        pair_key = (qw, cw)
                        cached_sim = pair_sim_cache.get(pair_key)
                        if cached_sim is not None:
                            if cached_sim > best_w_sim:
                                best_w_sim = cached_sim
                            continue
                        lc = len(cw)
                        # Mathematical upper bound of SequenceMatcher.ratio() skips hopeless pairs
                        min_len = lq if lq < lc else lc
                        if (2.0 * min_len / (lq + lc)) <= best_w_sim:
                            continue
                        sm.set_seq1(cw)
                        if sm.quick_ratio() <= best_w_sim:
                            continue
                        sim = sm.ratio()
                        pair_sim_cache[pair_key] = sim
                        if sim > best_w_sim:
                            best_w_sim = sim
                    total_w_sim += best_w_sim
                word_score = total_w_sim / n_qwords
            else:
                word_score = 0.0

            # Substring bonus: exact, spaceless, or near phrase inclusion
            sub_bonus = 0.0
            if folded_query in folded_text:
                sub_bonus = 0.35
            elif len(spaceless_query) >= 3 and spaceless_query in spaceless_text:
                sub_bonus = 0.30
            elif check_phrase_sim:
                lt_full = len(folded_text)
                if lt_full > 0 and (2.0 * min(lq_full, lt_full) / (lq_full + lt_full)) >= 0.75:
                    if SequenceMatcher(None, folded_query, folded_text).ratio() >= 0.75:
                        sub_bonus = 0.20

            fuzzy_score = min(word_score + sub_bonus, 1.0)
            norm_bm25 = r.get("bm25_score", 0.0) / max_bm25

            # Combined score: 35% BM25 lexical frequency + 65% Token-level fuzzy similarity
            final_score = round(0.35 * norm_bm25 + 0.65 * fuzzy_score, 4)
            r["score"] = final_score
            r["fuzzy_score"] = round(fuzzy_score, 4)

        # Re-sort candidates by final hybrid score descending
        rows.sort(key=lambda x: (x["score"], x.get("bm25_score", 0.0)), reverse=True)
        return rows[:limit]

    def get_database_summary(self) -> Dict[str, Any]:
        """Returns aggregate row counts and checkpoint breakdown across all tables."""
        with self._get_connection() as conn:
            video_cnt = conn.execute("SELECT COUNT(*) FROM videos;").fetchone()[0]
            shot_cnt = conn.execute("SELECT COUNT(*) FROM shots;").fetchone()[0]
            kf_cnt = conn.execute("SELECT COUNT(*) FROM keyframes;").fetchone()[0]
            ocr_cnt = conn.execute("SELECT COUNT(*) FROM ocr_records;").fetchone()[0]
            cp_rows = conn.execute(
                "SELECT video_id, stage_name, status, artifact_count, updated_at FROM pipeline_checkpoints;"
            ).fetchall()

            return {
                "total_videos": video_cnt,
                "total_shots": shot_cnt,
                "total_keyframes": kf_cnt,
                "total_ocr_records": ocr_cnt,
                "checkpoints": [dict(r) for r in cp_rows],
            }
