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
from typing import Any, Dict, List, Optional
from loguru import logger

from src.common.types import ShotRecord, KeyframeRecord, OCRRecord


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

    def search_ocr(
        self,
        query: str,
        video_id: Optional[str] = None,
        limit: int = 100
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

        if video_id:
            where_clause += " AND video_id = ?"
            params.append(video_id)

        # Retrieve a deep candidate pool (up to 10x limit, min 500) for fuzzy reranking
        pool_limit = max(limit * 10, 500)
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

        # Substring LIKE fallback: if FTS returned few results or missed compound/hyphenated tokens
        if len(rows) < pool_limit:
            seen_ocr_ids = {r["ocr_id"] for r in rows}
            like_candidates_to_try = [raw_query.strip()]
            for t in terms:
                if len(t) >= 3 and t not in like_candidates_to_try:
                    like_candidates_to_try.append(t)

            with self._get_connection() as conn:
                for term in like_candidates_to_try[:4]:
                    remaining = pool_limit - len(rows)
                    if remaining <= 0:
                        break
                    like_sql = f"""
                        SELECT ocr_id, video_id, keyframe_id, timestamp_sec, text_detected, 1.5 AS bm25_score
                        FROM ocr_records
                        WHERE text_detected LIKE ?
                        {("AND video_id = ?" if video_id else "")}
                        LIMIT ?;
                    """
                    like_params = [f"%{term}%"]
                    if video_id:
                        like_params.append(video_id)
                    like_params.append(min(100, remaining))

                    try:
                        for r in conn.execute(like_sql, tuple(like_params)).fetchall():
                            rd = dict(r)
                            if rd["ocr_id"] not in seen_ocr_ids:
                                seen_ocr_ids.add(rd["ocr_id"])
                                rows.append(rd)
                    except Exception as e:
                        logger.warning(f"[WARNING] Substring LIKE fallback query failed: {e}")

        if not rows:
            return []

        # Stage 2: Fine-Grained Token-Level Fuzzy Rescoring
        folded_query = fold_vietnamese(raw_query)
        # Extract word and sub-token boundaries for robust alignment
        query_words = [w for w in re.findall(r"[a-z0-9]+", folded_query) if w]
        spaceless_query = folded_query.replace(" ", "")

        max_bm25 = max((r.get("bm25_score", 1.0) for r in rows), default=1.0)
        if max_bm25 <= 0.0:
            max_bm25 = 1.0

        for r in rows:
            text_detected = r.get("text_detected", "")
            folded_text = fold_vietnamese(text_detected)
            cand_words = [w for w in re.findall(r"[a-z0-9]+", folded_text) if w]
            spaceless_text = folded_text.replace(" ", "")

            # Word-level alignment similarity: for each query word, find best matching word in candidate text
            if query_words and cand_words:
                word_sims = []
                for qw in query_words:
                    best_w_sim = max((SequenceMatcher(None, qw, cw).ratio() for cw in cand_words), default=0.0)
                    word_sims.append(best_w_sim)
                word_score = sum(word_sims) / len(word_sims)
            else:
                word_score = 0.0

            # Substring bonus: exact, spaceless, or near phrase inclusion
            sub_bonus = 0.0
            if folded_query in folded_text:
                sub_bonus = 0.35
            elif len(spaceless_query) >= 3 and spaceless_query in spaceless_text:
                sub_bonus = 0.30
            elif len(folded_query) >= 4 and SequenceMatcher(None, folded_query, folded_text).ratio() >= 0.75:
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
