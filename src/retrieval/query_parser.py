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

    @staticmethod
    def _collect_global_negatives(data: Dict[str, Any]) -> List[str]:
        """Extracts top-level negative visual cues from either string or list fields."""
        negatives: List[str] = []
        raw_single = str(data.get("negative_visual") or "").strip()
        if raw_single:
            negatives.append(raw_single)
        raw_list = data.get("negative_visual_queries") or []
        if isinstance(raw_list, list):
            for item in raw_list:
                cleaned = str(item).strip()
                if cleaned and cleaned not in negatives:
                    negatives.append(cleaned)
        return negatives

    @classmethod
    def _parse_dict(cls, data: Dict[str, Any]) -> ParsedMultiCueQuery:
        """Parses structured JSON dictionary into ParsedMultiCueQuery."""
        weights = data.get("weights", {"visual": 1.0, "ocr": 1.5})
        raw_ocr_mode = str(data.get("ocr_mode", "boost")).strip().lower()
        ocr_mode = raw_ocr_mode if raw_ocr_mode in ("off", "boost", "filter") else "boost"
        ocr_boost_weight = float(data.get("ocr_boost_weight", 0.25))
        anchor_stage = max(0, int(data.get("anchor_stage", 0)))
        min_gap_sec = max(0.0, float(data.get("min_gap_sec", data.get("min_sequence_gap_sec", 1.0))))
        max_gap_sec = max(min_gap_sec + 1.0, float(data.get("max_gap_sec", data.get("max_sequence_gap_sec", 30.0))))

        global_ocr = str(data.get("ocr_text") or data.get("ocr_query") or "").strip()
        global_negs = cls._collect_global_negatives(data)

        # Check for UI Multi-Stage 'scenes' payload ([{visual, ocr, negative_visual}])
        scenes_data = data.get("scenes")
        if scenes_data and isinstance(scenes_data, list):
            stages: List[QueryStage] = []
            for idx, sc in enumerate(scenes_data):
                if isinstance(sc, str):
                    st = cls._parse_stage(sc)
                elif isinstance(sc, dict):
                    v_list = [str(sc.get("visual", "")).strip()] if str(sc.get("visual", "")).strip() else []
                    v_list.extend(str(q).strip() for q in sc.get("visual_queries", []) if str(q).strip())
                    o_list = [str(sc.get("ocr", "")).strip()] if str(sc.get("ocr", "")).strip() else []
                    o_list.extend(str(q).strip() for q in sc.get("ocr_queries", []) if str(q).strip())
                    n_list = [str(sc.get("negative_visual", "")).strip()] if str(sc.get("negative_visual", "")).strip() else []
                    n_list.extend(str(q).strip() for q in sc.get("negative_visual_queries", []) if str(q).strip())
                    if idx == 0 and global_ocr and ocr_mode != "off" and global_ocr not in o_list:
                        o_list.append(global_ocr)
                    if idx == 0 and global_negs:
                        for gn in global_negs:
                            if gn not in n_list:
                                n_list.append(gn)
                    st = QueryStage(visual_queries=v_list, ocr_queries=o_list, negative_visual_queries=n_list)
                else:
                    continue
                if st.visual_queries or st.ocr_queries:
                    stages.append(st)

            if stages:
                return ParsedMultiCueQuery(
                    stages=stages,
                    is_sequential=len(stages) > 1,
                    weights=weights,
                    ocr_mode=ocr_mode,
                    ocr_boost_weight=ocr_boost_weight,
                    anchor_stage=min(anchor_stage, len(stages) - 1),
                    min_sequence_gap_sec=min_gap_sec,
                    max_sequence_gap_sec=max_gap_sec
                )

        # Check for sequence stages
        seq_stages_data = data.get("sequence_stages")
        if seq_stages_data and isinstance(seq_stages_data, list):
            stages = []
            for idx, st in enumerate(seq_stages_data):
                v_q = [str(q).strip() for q in st.get("visual_queries", []) if str(q).strip()]
                o_q = [str(q).strip() for q in st.get("ocr_queries", []) if str(q).strip()]
                neg_v_q = [str(q).strip() for q in st.get("negative_visual_queries", []) if str(q).strip()]
                if idx == 0 and global_ocr and ocr_mode != "off" and global_ocr not in o_q:
                    o_q.append(global_ocr)
                if idx == 0 and global_negs:
                    for gn in global_negs:
                        if gn not in neg_v_q:
                            neg_v_q.append(gn)
                if v_q or o_q:
                    stages.append(QueryStage(
                        visual_queries=v_q,
                        ocr_queries=o_q,
                        negative_visual_queries=neg_v_q
                    ))

            if stages:
                return ParsedMultiCueQuery(
                    stages=stages,
                    is_sequential=len(stages) > 1,
                    weights=weights,
                    ocr_mode=ocr_mode,
                    ocr_boost_weight=ocr_boost_weight,
                    anchor_stage=min(anchor_stage, len(stages) - 1),
                    min_sequence_gap_sec=min_gap_sec,
                    max_sequence_gap_sec=max_gap_sec
                )

        # Flat visual and OCR queries (supporting string 'query'/'visual_query' + separate 'ocr_text')
        raw_query_str = str(data.get("query") or data.get("visual_query") or "").strip()
        if raw_query_str:
            parsed_str = cls.parse(raw_query_str)
            if global_ocr and ocr_mode != "off" and parsed_str.stages:
                if global_ocr not in parsed_str.stages[0].ocr_queries:
                    parsed_str.stages[0].ocr_queries.append(global_ocr)
            if global_negs and parsed_str.stages:
                for gn in global_negs:
                    if gn not in parsed_str.stages[0].negative_visual_queries:
                        parsed_str.stages[0].negative_visual_queries.append(gn)
            parsed_str.ocr_mode = ocr_mode
            parsed_str.ocr_boost_weight = ocr_boost_weight
            parsed_str.anchor_stage = min(anchor_stage, max(0, len(parsed_str.stages) - 1))
            parsed_str.min_sequence_gap_sec = min_gap_sec
            parsed_str.max_sequence_gap_sec = max_gap_sec
            return parsed_str

        visual_queries = [str(q).strip() for q in data.get("visual_queries", []) if str(q).strip()]
        ocr_queries = [str(q).strip() for q in data.get("ocr_queries", []) if str(q).strip()]
        if global_ocr and ocr_mode != "off" and global_ocr not in ocr_queries:
            ocr_queries.append(global_ocr)
        neg_visual_queries = list(global_negs)

        single_stage = QueryStage(
            visual_queries=visual_queries,
            ocr_queries=ocr_queries,
            negative_visual_queries=neg_visual_queries
        )
        return ParsedMultiCueQuery(
            stages=[single_stage],
            is_sequential=False,
            weights=weights,
            ocr_mode=ocr_mode,
            ocr_boost_weight=ocr_boost_weight,
            anchor_stage=0,
            min_sequence_gap_sec=min_gap_sec,
            max_sequence_gap_sec=max_gap_sec
        )

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

        # Check for multi-cue separated by '|' or explicitly starting with 'v:', '-v:', or 'ocr:'
        if "|" in text or re.match(r"^(?:-?v|ocr):\s*", text, re.IGNORECASE):
            return cls._parse_prefixed_cues(text)

        # Fallback to pure natural language parsing
        return cls._parse_natural_language(text)

    @classmethod
    def _parse_prefixed_cues(cls, text: str) -> QueryStage:
        """Parses multi-cue tokens separated by '|' using 'v:', '-v:', and 'ocr:' prefixes."""
        visuals: List[str] = []
        ocrs: List[str] = []
        neg_visuals: List[str] = []

        tokens = [t.strip() for t in text.split("|") if t.strip()]
        for token in tokens:
            if re.match(r"^ocr:\s*", token, re.IGNORECASE):
                val = re.sub(r"^ocr:\s*", "", token, flags=re.IGNORECASE).strip().strip('"').strip("'")
                if val:
                    ocrs.append(val)
            elif re.match(r"^-v:\s*", token, re.IGNORECASE):
                val = re.sub(r"^-v:\s*", "", token, flags=re.IGNORECASE).strip()
                if val:
                    neg_visuals.append(val)
            elif re.match(r"^v:\s*", token, re.IGNORECASE):
                val = re.sub(r"^v:\s*", "", token, flags=re.IGNORECASE).strip()
                if val:
                    visuals.append(val)
            else:
                # Default non-prefixed cue to visual description
                visuals.append(token)

        return QueryStage(
            visual_queries=visuals,
            ocr_queries=ocrs,
            negative_visual_queries=neg_visuals
        )

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
        Extracts strict vehicle plate formats automatically while avoiding noisy keyword hijacking.
        Explicit on-screen text must use quoted phrases, 'ocr:' syntax, or the dedicated UI OCR box.
        """
        ocrs: List[str] = []
        plate_matches = cls.LICENSE_PLATE_REGEX.findall(text)
        if plate_matches:
            ocrs.extend(plate_matches)

        # The full natural language description serves as the visual context
        return QueryStage(visual_queries=[text], ocr_queries=ocrs)
