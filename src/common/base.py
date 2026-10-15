"""
Abstract base classes defining standard interfaces for all extractors and indexers.
Follows the Strategy and Template Method design patterns for clean extensibility.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pathlib import Path


class BaseExtractor(ABC):
    """
    Abstract interface for feature extraction modules.
    Every extractor takes a video file path (or extracted artifacts)
    and produces a structured list of domain records.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    def extract(self, video_path: str, **kwargs) -> List[Any]:
        """
        Executes the extraction process on a given video.

        Args:
            video_path: Absolute or relative path to the input video file.
            **kwargs: Optional execution parameters.

        Returns:
            A list of typed records (e.g., ShotRecord, KeyframeRecord, SpeechRecord).
        """
        pass

    @abstractmethod
    def is_already_processed(self, video_id: str) -> bool:
        """
        Checks whether the given video has already been processed and saved to database.
        Crucial for resuming interrupted pipelines without re-computing from scratch.

        Args:
            video_id: Unique identifier of the video.

        Returns:
            True if already processed, False otherwise.
        """
        pass


class BaseIndexer(ABC):
    """
    Abstract interface for database and vector index managers.
    Handles indexing records and executing low-latency retrieval.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    def add(self, records: List[Any], **kwargs) -> None:
        """
        Appends a list of structured records to the underlying index or database.

        Args:
            records: List of typed records to index.
            **kwargs: Extra parameters (e.g., embeddings tensor).
        """
        pass

    @abstractmethod
    def search(self, query: str, top_k: int = 50, **kwargs) -> List[Any]:
        """
        Searches the index for candidates matching the query string.

        Args:
            query: User search query.
            top_k: Number of highest-ranking results to return.

        Returns:
            List of candidate matches with similarity scores.
        """
        pass

    @abstractmethod
    def save(self, output_path: str) -> None:
        """Persists the index to disk."""
        pass

    @abstractmethod
    def load(self, index_path: str) -> None:
        """Loads the pre-built index from disk."""
        pass
