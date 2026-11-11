"""
DRES submission module for VBS / AI Challenge Known-Item Search.
"""

from typing import Any

__all__ = [
    "DRESClient",
    "calculate_kis_score",
    "create_kis_submission_payload",
    "format_media_item_name",
    "seconds_to_ms",
]


def __getattr__(name: str) -> Any:
    if name in __all__:
        import src.submission.dres_client as dc
        return getattr(dc, name)
    raise AttributeError(f"module 'src.submission' has no attribute '{name}'")

