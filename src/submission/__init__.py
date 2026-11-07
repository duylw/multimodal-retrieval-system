"""
DRES submission module for VBS / AI Challenge Known-Item Search.
"""

from src.submission.dres_client import (
    DRESClient,
    calculate_kis_score,
    create_kis_submission_payload,
    format_media_item_name,
    seconds_to_ms,
)

__all__ = [
    "DRESClient",
    "calculate_kis_score",
    "create_kis_submission_payload",
    "format_media_item_name",
    "seconds_to_ms",
]
