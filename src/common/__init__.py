"""
Common abstractions, data models, and configuration utilities.
"""

from src.common.types import (
    ShotRecord,
    KeyframeRecord,
    SpeechRecord,
    OCRRecord,
    AudioEventRecord,
    SearchResult,
)
from src.common.base import BaseExtractor, BaseIndexer
from src.common.config import ConfigManager

__all__ = [
    "ShotRecord",
    "KeyframeRecord",
    "SpeechRecord",
    "OCRRecord",
    "AudioEventRecord",
    "SearchResult",
    "BaseExtractor",
    "BaseIndexer",
    "ConfigManager",
]
