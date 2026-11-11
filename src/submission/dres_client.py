"""
DRES (Distributed Retrieval Evaluation Server) client and payload utilities.
Implements the VBS / AI Challenge REST API v2 specification for Known-Item Search (KIS).
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import requests
from loguru import logger

from src.common.types import DRESAnswer, DRESAnswerSet, DRESSubmissionPayload


def format_media_item_name(video_id: str) -> str:
    """
    Format a video identifier for DRES submission by stripping file extensions and whitespace.
    Example: 'L01_V005.mp4' -> 'L01_V005', 'L01_V005' -> 'L01_V005'.
    """
    cleaned = video_id.strip()
    p = Path(cleaned)
    if p.suffix:
        return p.stem
    return cleaned


def seconds_to_ms(seconds: float) -> int:
    """Convert float seconds to integer milliseconds (rounded to nearest int)."""
    return int(round(max(0.0, seconds) * 1000.0))


def create_kis_submission_payload(video_id: str, start_sec: float, end_sec: float) -> Dict[str, Any]:
    """
    Build a valid DRES API v2 KIS submission dictionary.
    
    Format:
    {
        "answerSets": [
            {
                "answers": [
                    {
                        "mediaItemName": "<VIDEO_ID>",
                        "start": <TIME_IN_MS>,
                        "end": <TIME_IN_MS>
                    }
                ]
            }
        ]
    }
    """
    clean_id = format_media_item_name(video_id)
    if not clean_id:
        raise ValueError("Video ID cannot be empty.")
    
    start_ms = seconds_to_ms(start_sec)
    end_ms = seconds_to_ms(end_sec)
    
    if start_ms > end_ms:
        raise ValueError(f"start_ms ({start_ms}) must be <= end_ms ({end_ms})")
    
    return {
        "answerSets": [
            {
                "answers": [
                    {
                        "mediaItemName": clean_id,
                        "start": start_ms,
                        "end": end_ms
                    }
                ]
            }
        ]
    }


def calculate_kis_score(
    elapsed_sec: float,
    time_limit_sec: float,
    wrong_attempts: int,
    is_correct: bool = True
) -> Dict[str, float]:
    """
    Calculate the official competition score for a KIS query based on accuracy and time.
    
    Formulation:
      S_acc  = max(0.0, 50.0 - 10.0 * wrong_attempts)
      S_time = 50.0 * (1.0 - elapsed_sec / time_limit_sec) if elapsed_sec <= time_limit_sec else 0.0
      Total  = S_acc + S_time (if is_correct) else 0.0
    """
    if not is_correct:
        return {
            "accuracy_score": 0.0,
            "time_score": 0.0,
            "total_score": 0.0
        }
    
    acc_score = max(0.0, 50.0 - 10.0 * max(0, wrong_attempts))
    
    t_clamped = max(0.0, min(elapsed_sec, time_limit_sec))
    time_score = 50.0 * (1.0 - t_clamped / time_limit_sec)
    
    return {
        "accuracy_score": round(acc_score, 2),
        "time_score": round(time_score, 2),
        "total_score": round(acc_score + time_score, 2)
    }


class DRESClient:
    """
    REST client for communicating with the DRES evaluation server.
    Handles authentication, session persistence, active evaluation lookup,
    and duplicate-guarded KIS submission.
    """

    def __init__(self, base_url: str = "https://eventretrieval.one", session_id: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.session_id = session_id
        self._submitted_cache: Set[Tuple[str, str, int, int]] = set()

    def set_session_id(self, session_id: str) -> None:
        """Set or update the active session ID token."""
        self.session_id = session_id.strip()

    def clear_cache(self) -> None:
        """Clear the submitted answers duplicate cache."""
        self._submitted_cache.clear()

    def login(self, username: str, password: str, timeout: float = 10.0) -> Dict[str, Any]:
        """
        Authenticate with DRES server via POST /api/v2/login.
        Returns the user profile and updates self.session_id upon success.
        """
        url = f"{self.base_url}/api/v2/login"
        payload = {"username": username, "password": password}
        headers = {"Content-Type": "application/json"}

        logger.info(f"[INFO] Logging in to DRES server at {url} as user '{username}'...")
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            sid = data.get("sessionId") or data.get("session") or data.get("id")
            if not sid:
                raise ValueError(f"No sessionId returned in response: {data}")
            self.session_id = sid
            logger.info(f"[OK] Authentication successful. Session ID: {self.session_id}")
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"[ERROR] Failed to authenticate with DRES: {e}")
            raise

    def get_evaluation_list(self, timeout: float = 10.0) -> List[Dict[str, Any]]:
        """
        Retrieve list of evaluations via GET /api/v2/client/evaluation/list?session=<sessionId>.
        """
        if not self.session_id:
            raise ValueError("No session_id configured. Call login() or set_session_id() first.")

        url = f"{self.base_url}/api/v2/client/evaluation/list"
        params = {"session": self.session_id}

        logger.info(f"[INFO] Fetching evaluations from {url}...")
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                return data
            return [data]
        except requests.exceptions.RequestException as e:
            logger.error(f"[ERROR] Failed to list evaluations: {e}")
            raise

    def get_active_evaluation(self, timeout: float = 10.0) -> Optional[Dict[str, Any]]:
        """
        Find the first evaluation with status 'ACTIVE', 'RUNNING', or 'OPEN'.
        Falls back to the first available evaluation in the list if none match.
        """
        evaluations = self.get_evaluation_list(timeout=timeout)
        for ev in evaluations:
            status = str(ev.get("status", "")).upper()
            if status in ["ACTIVE", "RUNNING", "OPEN"]:
                logger.info(f"[OK] Found active evaluation: id={ev.get('id')}, name={ev.get('name')}")
                return ev
        if evaluations:
            first_ev = evaluations[0]
            logger.info(f"[INFO] Using first available evaluation: id={first_ev.get('id')}, name={first_ev.get('name')}")
            return first_ev
        logger.warning("[WARNING] No evaluation found on server.")
        return None

    def submit_kis(
        self,
        evaluation_id: str,
        video_id: str,
        start_sec: float,
        end_sec: float,
        timeout: float = 10.0,
        allow_duplicate: bool = False
    ) -> Dict[str, Any]:
        """
        Submit a candidate video moment to DRES server via:
        POST /api/v2/submit/{evaluationID}?session={sessionID}

        Guards against duplicate submissions for the same (evaluation, video, start, end).
        """
        if not self.session_id:
            raise ValueError("No session_id configured. Call login() or set_session_id() first.")

        clean_id = format_media_item_name(video_id)
        start_ms = seconds_to_ms(start_sec)
        end_ms = seconds_to_ms(end_sec)
        cache_key = (evaluation_id, clean_id, start_ms, end_ms)

        if not allow_duplicate and cache_key in self._submitted_cache:
            warning_msg = (
                f"[WARNING] Duplicate submission prevented: {clean_id} "
                f"[{start_ms}ms - {end_ms}ms] already submitted for eval {evaluation_id}."
            )
            logger.warning(warning_msg)
            return {
                "status": "DUPLICATE_PREVENTED",
                "message": warning_msg,
                "payload": create_kis_submission_payload(clean_id, start_sec, end_sec)
            }

        payload = create_kis_submission_payload(clean_id, start_sec, end_sec)
        url = f"{self.base_url}/api/v2/submit/{evaluation_id}"
        params = {"session": self.session_id}
        headers = {"Content-Type": "application/json"}

        logger.info(
            f"[INFO] Submitting KIS answer: {clean_id} [{start_ms}ms - {end_ms}ms] "
            f"to evaluation '{evaluation_id}'..."
        )

        try:
            resp = requests.post(url, json=payload, params=params, headers=headers, timeout=timeout)
            resp.raise_for_status()
            result = resp.json() if resp.text else {"status": "SUCCESS", "http_status": resp.status_code}
            self._submitted_cache.add(cache_key)
            logger.info(f"[OK] DRES submission response: {result}")
            return result
        except requests.exceptions.RequestException as e:
            logger.error(f"[ERROR] Failed to submit answer to DRES: {e}")
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description="DRES Submission Client CLI for Video KIS and Textual KIS.")
    parser.add_argument("--base-url", default="https://eventretrieval.one", help="Base URL of DRES server.")
    parser.add_argument("--session-id", default=None, help="Existing DRES session ID token.")
    parser.add_argument("--username", default=None, help="DRES username for login.")
    parser.add_argument("--password", default=None, help="DRES password for login.")
    parser.add_argument("--list-evals", action="store_true", help="List available evaluations.")
    parser.add_argument("--eval-id", default=None, help="Evaluation ID to submit to.")
    parser.add_argument("--video-id", default=None, help="Video ID to submit (e.g. L01_V001).")
    parser.add_argument("--start", type=float, default=0.0, help="Start time in seconds.")
    parser.add_argument("--end", type=float, default=0.0, help="End time in seconds.")
    parser.add_argument("--dry-run", action="store_true", help="Format and print payload without sending HTTP POST.")
    args = parser.parse_args()

    # Dry-run payload check
    if args.dry_run:
        if not args.video_id:
            logger.error("[ERROR] --video-id required for --dry-run.")
            sys.exit(1)
        payload = create_kis_submission_payload(args.video_id, args.start, args.end)
        logger.info(f"[OK] Formatted Dry-Run KIS Payload:\n{payload}")
        return

    client = DRESClient(base_url=args.base_url, session_id=args.session_id)

    if args.username and args.password:
        client.login(args.username, args.password)

    if args.list_evals:
        evals = client.get_evaluation_list()
        print(evals)
        return

    if args.eval_id and args.video_id:
        res = client.submit_kis(
            evaluation_id=args.eval_id,
            video_id=args.video_id,
            start_sec=args.start,
            end_sec=args.end
        )
        print(res)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
