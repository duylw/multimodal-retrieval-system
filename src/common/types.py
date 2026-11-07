"""
Data transfer objects and schemas for the multimodal video retrieval pipeline.
All structures use standard Python dataclasses for strong typing and immutability.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class ShotRecord:
    """Represents a single continuous video shot detected by boundary models."""
    video_id: str
    shot_id: int
    start_frame: int
    end_frame: int
    start_sec: float
    end_sec: float
    duration_sec: float


@dataclass
class KeyframeRecord:
    """Represents an extracted keyframe image associated with a shot."""
    keyframe_id: str
    video_id: str
    shot_id: int
    frame_idx: int
    timestamp_sec: float
    file_path: str
    is_shot_center: bool
    blur_score: float = 0.0


@dataclass
class SpeechRecord:
    """Represents a speech segment transcribed via ASR."""
    segment_id: str
    video_id: str
    start_sec: float
    end_sec: float
    text_raw: str
    text_normalized: str
    confidence: float = 1.0


@dataclass
class OCRRecord:
    """Represents text detected and recognized on a video keyframe."""
    ocr_id: str
    video_id: str
    keyframe_id: str
    timestamp_sec: float
    text_detected: str
    bbox: List[Tuple[int, int]] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class AudioEventRecord:
    """Represents an audio event window categorized via CLAP."""
    event_id: str
    video_id: str
    start_sec: float
    end_sec: float
    faiss_id: int


@dataclass
class SearchResult:
    """Represents an aggregated video moment returned to the user."""
    video_id: str
    start_sec: float
    end_sec: float
    confidence_score: float
    matched_modalities: List[str] = field(default_factory=list)
    representative_keyframe_path: Optional[str] = None
    matched_text_snippet: Optional[str] = None


@dataclass
class DRESAnswer:
    """Represents a single video moment answer for DRES KIS submission."""
    mediaItemName: str
    start: int  # Timestamp in milliseconds
    end: int    # Timestamp in milliseconds


@dataclass
class DRESAnswerSet:
    """Represents an answer set wrapper required by DRES API v2."""
    answers: List[DRESAnswer] = field(default_factory=list)


@dataclass
class DRESSubmissionPayload:
    """Represents the complete submission envelope for DRES API v2."""
    answerSets: List[DRESAnswerSet] = field(default_factory=list)

