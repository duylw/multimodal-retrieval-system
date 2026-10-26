"""
Feature extraction modules for multimodal video retrieval.
"""

from src.extractors.shots import ShotDetector
from src.extractors.keyframes import KeyframeExtractor

__all__ = ["ShotDetector", "KeyframeExtractor"]
