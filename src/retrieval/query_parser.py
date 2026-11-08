"""
Query Parser and Router for Multimodal Video Moment Retrieval.
Decomposes user queries into modality-specific retrieval paths (Visual SigLIP2 and OCR text),
supporting multi-cue composition, chronological sequence operators (>>), and rule-based fallback.
"""

import re
from typing import Any, Dict, List, Optional, Union
from loguru import logger

from src.common.types import ParsedMultiCueQuery, QueryStage


class QueryParser:
    """
    Parses and routes natural language queries, prefix-annotated strings,
    and structured payloads into typed ParsedMultiCueQuery instances.
    """

    # Regex to detect Vietnamese vehicle license plate formats (e.g., '59-P1 123.45', '51C-456.78', '51A 12345')
    LICENSE_PLATE_REGEX = re.compile(
        r"\b\d{2}[A-Z][0-9A-Z]?\s*[-.]?\s*\d{3,5}(?:\.\d{2})?\b",
        re.IGNORECASE
    )

    # Keywords indicating on-screen text in natural language descriptions
    OCR_TRIGGER_KEYWORDS = [
        "chữ", "biển số", "biển hiệu", "bảng", "tiêu đề", "dòng chữ",
        "text", "license plate", "signboard", "banner", "title"
    ]

    @classmethod
    def parse(cls, query_input: Union[str, Dict[str, Any]]) -> ParsedMultiCueQuery:
        """
        Decomposes raw user query into structured multi-cue stages.

        Args:
            query_input: Either a formatted string (with prefixes 'v:', 'ocr:', '>>')
                         or a structured dictionary.

        Returns:
            ParsedMultiCueQuery containing ordered stages and modality-specific queries.

        Raises:
            ValueError: If query_input is empty or invalid.
        """
        if isinstance(query_input, dict):
            return cls._parse_dict(query_input)

        if not isinstance(query_input, str):
            raise ValueError(f"Expected str or dict, received {type(query_input).__name__}")

        raw_text = query_input.strip()
        if not raw_text:
            raise ValueError("Query string cannot be empty.")

        # Check for chronological sequence operator (>>)
        if ">>" in raw_text:
            return cls._parse_sequence(raw_text)

        # Parse single-stage query
        stage = cls._parse_stage(raw_text)
        return ParsedMultiCueQuery(stages=[stage], is_sequential=False)

    @classmethod
    def _parse_dict(cls, data: Dict[str, Any]) -> ParsedMultiCueQuery:
        """Parses structured JSON dictionary into ParsedMultiCueQuery."""
        weights = data.get("weights", {"visual": 1.0, "ocr": 1.5})

        # Check for sequence stages
        seq_stages_data = data.get("sequence_stages")
        if seq_stages_data and isinstance(seq_stages_data, list):
            stages: List[QueryStage] = []
            for st in seq_stages_data:
                v_q = [str(q).strip() for q in st.get("visual_queries", []) if str(q).strip()]
                o_q = [str(q).strip() for q in st.get("ocr_queries", []) if str(q).strip()]
                if v_q or o_q:
                    stages.append(QueryStage(visual_queries=v_q, ocr_queries=o_q))

            if stages:
                return ParsedMultiCueQuery(stages=stages, is_sequential=len(stages) > 1, weights=weights)

        # Flat visual and OCR queries
        visual_queries = [str(q).strip() for q in data.get("visual_queries", []) if str(q).strip()]
        ocr_queries = [str(q).strip() for q in data.get("ocr_queries", []) if str(q).strip()]

        single_stage = QueryStage(visual_queries=visual_queries, ocr_queries=ocr_queries)
        return ParsedMultiCueQuery(stages=[single_stage], is_sequential=False, weights=weights)

    @classmethod
    def _parse_sequence(cls, raw_text: str) -> ParsedMultiCueQuery:
        """Splits query by sequence operator (>>) into ordered QueryStages."""
        raw_stages = [s.strip() for s in raw_text.split(">>") if s.strip()]
        if not raw_stages:
            raise ValueError("Sequential query contains no valid stages.")

        stages = [cls._parse_stage(s) for s in raw_stages]
        logger.info(f"[INFO] Parsed chronological sequence query with {len(stages)} stages.")
        return ParsedMultiCueQuery(stages=stages, is_sequential=True)

    @classmethod
    def _parse_stage(cls, stage_text: str) -> QueryStage:
        """Parses a single query segment into visual and OCR cues."""
        text = stage_text.strip()

        # Check for Google-style inline ocr:"..." or quoted terms first
        inline_ocr = cls._extract_inline_ocr(text)
        if inline_ocr is not None:
            return inline_ocr

        # Check for multi-cue separated by '|' or explicitly starting with 'v:' or 'ocr:'
        if "|" in text or re.match(r"^(?:v|ocr):\s*", text, re.IGNORECASE):
            return cls._parse_prefixed_cues(text)

        # Fallback to pure natural language parsing
        return cls._parse_natural_language(text)

    @classmethod
    def _parse_prefixed_cues(cls, text: str) -> QueryStage:
        """Parses multi-cue tokens separated by '|' using 'v:' and 'ocr:' prefixes."""
        visuals: List[str] = []
        ocrs: List[str] = []

        tokens = [t.strip() for t in text.split("|") if t.strip()]
        for token in tokens:
            if re.match(r"^ocr:\s*", token, re.IGNORECASE):
                val = re.sub(r"^ocr:\s*", "", token, flags=re.IGNORECASE).strip().strip('"').strip("'")
                if val:
                    ocrs.append(val)
            elif re.match(r"^v:\s*", token, re.IGNORECASE):
                val = re.sub(r"^v:\s*", "", token, flags=re.IGNORECASE).strip()
                if val:
                    visuals.append(val)
            else:
                # Default non-prefixed cue to visual description
                visuals.append(token)

        return QueryStage(visual_queries=visuals, ocr_queries=ocrs)

    @classmethod
    def _extract_inline_ocr(cls, text: str) -> Optional[QueryStage]:
        """Extracts inline ocr:"..." and leaves remaining text as visual description."""
        # Pattern 1: explicit ocr:"..."
        ocr_pattern = r'ocr:\s*"([^"]+)"|ocr:\s*\'([^\']+)\''
        matches = re.findall(ocr_pattern, text, re.IGNORECASE)
        if matches:
            ocrs = [m[0] or m[1] for m in matches if m[0] or m[1]]
            clean_text = re.sub(ocr_pattern, "", text, flags=re.IGNORECASE).strip()
            visuals = [clean_text] if clean_text else []
            return QueryStage(visual_queries=visuals, ocr_queries=ocrs)

        # Pattern 2: quoted phrase + non-quoted text (e.g. 'a truck "51C 456.78"')
        quoted_pattern = r'"([^"]+)"'
        quoted_matches = re.findall(quoted_pattern, text)
        if quoted_matches:
            # If quotes exist, treat quoted strings as OCR text and unquoted as visual
            unquoted_text = re.sub(quoted_pattern, "", text).strip()
            visuals = [unquoted_text] if unquoted_text else []
            return QueryStage(visual_queries=visuals, ocr_queries=quoted_matches)

        return None

    @classmethod
    def _parse_natural_language(cls, text: str) -> QueryStage:
        """
        Rule-based triage for natural language descriptions without explicit syntax (< 1ms).
        Detects vehicle plates or text cues automatically.
        """
        ocrs: List[str] = []
        plate_matches = cls.LICENSE_PLATE_REGEX.findall(text)
        if plate_matches:
            ocrs.extend(plate_matches)

        # Detect OCR trigger words (e.g. 'biển số 51B 12345')
        for kw in cls.OCR_TRIGGER_KEYWORDS:
            pattern = rf"{kw}\s+([A-Za-z0-9\s.-]+)"
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted = match.group(1).strip()
                # Stop at common sentence separators
                extracted = re.split(r"[,.;]|\b(?:đang|chạy|vào|và)\b", extracted, flags=re.IGNORECASE)[0].strip()
                if extracted and len(extracted) >= 3 and extracted not in ocrs:
                    ocrs.append(extracted)

        # The full natural language description serves as the visual context
        return QueryStage(visual_queries=[text], ocr_queries=ocrs)
