"""
Unit tests for retrieval modules (QueryParser, ScoreFusion, SearchEngine).
"""

from src.retrieval.query_parser import QueryParser


def test_query_parser():
    # Test 1: Power-user prefix
    p1 = QueryParser.parse("v: a blue truck | v: heavy rain | ocr: 51C 456.78")
    assert len(p1.stages) == 1
    assert p1.stages[0].visual_queries == ["a blue truck", "heavy rain"]
    assert p1.stages[0].ocr_queries == ["51C 456.78"]
    assert not p1.is_sequential

    # Test 2: Sequence syntax (>>)
    p2 = QueryParser.parse("v: woman entering supermarket >> v: close up of cashier | ocr: HOA DON")
    assert p2.is_sequential
    assert len(p2.stages) == 2
    assert p2.stages[0].visual_queries == ["woman entering supermarket"]
    assert p2.stages[1].visual_queries == ["close up of cashier"]
    assert p2.stages[1].ocr_queries == ["HOA DON"]

    # Test 3: Inline ocr:"..."
    p3 = QueryParser.parse('a blue truck in heavy rain ocr:"51C 456.78"')
    assert p3.stages[0].visual_queries == ["a blue truck in heavy rain"]
    assert p3.stages[0].ocr_queries == ["51C 456.78"]

    # Test 4: Quoted text fallback
    p4 = QueryParser.parse('xe tai chay qua nga tu "51B 12345"')
    assert p4.stages[0].visual_queries == ["xe tai chay qua nga tu"]
    assert p4.stages[0].ocr_queries == ["51B 12345"]

    # Test 5: License plate regex fallback
    p5 = QueryParser.parse("xe cuu thuong 51B-123.45 vuot den do")
    assert "51B-123.45" in p5.stages[0].ocr_queries

    # Test 6: Dict payload
    p6 = QueryParser.parse({"visual_queries": ["truck"], "ocr_queries": ["sign"]})
    assert p6.stages[0].visual_queries == ["truck"]
    assert p6.stages[0].ocr_queries == ["sign"]

    # Test 7: Negative visual cue (-v:)
    p7 = QueryParser.parse("v: man speaking | -v: studio news anchor | ocr: VTV1")
    assert p7.stages[0].visual_queries == ["man speaking"]
    assert p7.stages[0].negative_visual_queries == ["studio news anchor"]
    assert p7.stages[0].ocr_queries == ["VTV1"]

    # Test 8: 3-stage chronological sequence (A >> B >> C)
    p8 = QueryParser.parse("v: wide shot street >> v: car collision >> ocr: 51B")
    assert p8.is_sequential
    assert len(p8.stages) == 3
    assert p8.stages[0].visual_queries == ["wide shot street"]
    assert p8.stages[1].visual_queries == ["car collision"]
    assert p8.stages[2].ocr_queries == ["51B"]

    print("[OK] All QueryParser tests passed successfully!")


def test_score_fusion():
    from src.retrieval.score_fusion import TemporalMomentFusor, MaxPerCueRRFStrategy

    strategy = MaxPerCueRRFStrategy(k_rrf=60, consensus_boost_per_cue=0.25, story_boost_per_cue=0.08)
    fusor = TemporalMomentFusor(strategy=strategy)

    # Test Case 1: Anti-Double-Counting vs Multi-Cue Consensus
    # Video A: 3 hits for 'v1' at 10.0s, 11.0s, 12.0s inside [10.0, 15.0]
    # Video B: 1 hit for 'v1' at 10.0s and 1 hit for 'ocr1' at 11.0s inside [10.0, 15.0]
    hits_by_cue = {
        "v1": [
            {"video_id": "V_A", "keyframe_id": "kf_a1", "timestamp_sec": 10.0, "score": 0.3},
            {"video_id": "V_A", "keyframe_id": "kf_a2", "timestamp_sec": 11.0, "score": 0.28},
            {"video_id": "V_A", "keyframe_id": "kf_a3", "timestamp_sec": 12.0, "score": 0.25},
            {"video_id": "V_B", "keyframe_id": "kf_b1", "timestamp_sec": 10.0, "score": 0.29},
        ],
        "ocr1": [
            {"video_id": "V_B", "keyframe_id": "kf_b2", "timestamp_sec": 11.0, "score": 0.9, "text_detected": "51C 456"},
        ]
    }
    cue_types = {"v1": "visual", "ocr1": "ocr"}
    weights = {"visual": 1.0, "ocr": 1.5}

    moments = fusor.fuse_and_nms([hits_by_cue], cue_types, weights, top_k=5)
    assert len(moments) >= 2

    # V_B must rank #1 because it has both 'v1' and 'ocr1' (Consensus Boost)
    # whereas V_A only has 'v1' (even though it had 3 keyframes, Max-Per-Cue prevented inflation)
    assert moments[0].video_id == "V_B"
    assert moments[0].start_sec == 7.5
    assert moments[0].end_sec == 15.0
    assert moments[0].start_ms == 7500
    assert moments[0].end_ms == 15000
    assert "v1" in moments[0].matched_cues and "ocr1" in moments[0].matched_cues
    assert moments[1].video_id == "V_A"

    # Test Case 2: 3-Stage Chronological Sequence Linking (Stage 1 >> Stage 2 >> Stage 3)
    s1_hits = {"s1_v": [{"video_id": "V_SEQ", "keyframe_id": "kf1", "timestamp_sec": 10.0, "score": 0.8}]}
    s2_hits = {"s2_v": [{"video_id": "V_SEQ", "keyframe_id": "kf2", "timestamp_sec": 18.0, "score": 0.85}]}
    s3_hits = {"s3_o": [{"video_id": "V_SEQ", "keyframe_id": "kf3", "timestamp_sec": 26.0, "score": 0.9, "text_detected": "END"}]}
    seq_types = {"s1_v": "visual", "s2_v": "visual", "s3_o": "ocr"}
    seq_moments = fusor.fuse_and_nms([s1_hits, s2_hits, s3_hits], seq_types, weights, top_k=5)
    assert len(seq_moments) == 1
    assert seq_moments[0].video_id == "V_SEQ"
    assert seq_moments[0].start_sec <= 10.0
    assert seq_moments[0].end_sec >= 26.0
    assert set(seq_moments[0].matched_cues) == {"s1_v", "s2_v", "s3_o"}

    print("[OK] Max-Per-Cue, Consensus Multiplier, and 3-Stage Sequence Linking tests passed!")


def test_search_with_trace():
    from src.retrieval.search_engine import SearchEngine

    engine = SearchEngine()
    try:
        moments, trace = engine.search_with_trace(
            query="ocr: trùng biển số",
            mode="ocr",
            top_k=5,
            trace_top_hits=3
        )
        assert len(moments) > 0
        assert "cues" in trace
        assert len(trace["cues"]) == 1
        assert trace["cues"][0]["modality"] == "ocr"
        assert len(trace["cues"][0]["top_hits"]) > 0
        assert moments[0].start_ms < moments[0].end_ms
        assert len(moments[0].cue_evidence) > 0
        print("[OK] Search with explainability trace test passed!")
    finally:
        engine.safe_unload()


def test_kis_endpoints():
    from src.ui.debug_server import (
        get_video_temporal_context,
        get_dres_status,
        submit_to_dres,
        clear_dres_cache,
    )

    # 1. Test Temporal Context Filmstrip (+-15s Neighbor Keyframes)
    ctx = get_video_temporal_context(video_id="L13_V001", timestamp_sec=30.0, window_sec=15.0)
    assert ctx["video_id"] == "L13_V001"
    assert ctx["total_frames"] > 0
    assert len(ctx["frames"]) == ctx["total_frames"]
    assert any(abs(f["delta_sec"]) <= 15.0 for f in ctx["frames"])

    # 2. Test DRES Submission & Duplicate Guard
    clear_dres_cache()
    payload = {
        "video_id": "L13_V001.mp4",
        "start_sec": 25.0,
        "end_sec": 26.0,
        "dry_run": True,
    }
    res1 = submit_to_dres(payload)
    assert res1["status"] == "DRY_RUN_ACCEPTED"
    assert res1["video_id"] == "L13_V001"
    assert res1["start_ms"] == 25000
    assert res1["end_ms"] == 26000

    # Submitting the exact same interval should trigger duplicate protection
    res2 = submit_to_dres(payload)
    assert res2["status"] == "DUPLICATE_PREVENTED"

    status = get_dres_status()
    assert status["submitted_count"] == 1
    clear_dres_cache()
    print("[OK] Task 06B KIS Context Filmstrip and DRES Submission tests passed!")


def test_task_07a_visual_first_and_anchor_sequence():
    """Verify Task 07A: no noisy OCR hijack, Visual-First OCR boost/filter, and Anchor-then-Scan sequence."""
    import numpy as np
    import faiss
    from src.retrieval.search_engine import SearchEngine

    # 1. QueryParser must NOT trigger noisy OCR on generic keywords like 'bảng', 'chữ', 'tiêu đề'
    p_clean = QueryParser.parse("nguoi dan ong dung truoc bang mau do")
    assert p_clean.stages[0].ocr_queries == []
    assert p_clean.stages[0].visual_queries == ["nguoi dan ong dung truoc bang mau do"]

    # Task 07A structured scenes + ocr_mode + anchor_stage dict parsing
    p_seq = QueryParser.parse({
        "scenes": [{"visual": "red car"}, {"visual": "ambulance"}],
        "ocr_text": "HTV9",
        "ocr_mode": "filter",
        "anchor_stage": 1,
        "min_gap_sec": 2.0,
        "max_gap_sec": 45.0
    })
    assert p_seq.is_sequential
    assert len(p_seq.stages) == 2
    assert p_seq.stages[0].ocr_queries == ["HTV9"]
    assert p_seq.ocr_mode == "filter"
    assert p_seq.anchor_stage == 1
    assert p_seq.min_sequence_gap_sec == 2.0
    assert p_seq.max_sequence_gap_sec == 45.0

    # 2. Build tiny synthetic FAISS IndexFlatIP in memory (dim=4) to test fusion & Anchor-then-Scan
    class MockVecIndex:
        def __init__(self, vecs, metas):
            self.index = faiss.IndexFlatIP(4)
            self.index.add(vecs.astype(np.float32))
            self.id_to_metadata = metas
            self.total_vectors = len(metas)

        def search(self, q_vec, top_k=10):
            sims, idxs = self.index.search(q_vec.astype(np.float32), min(top_k, self.total_vectors))
            hits = []
            for rank, (s, i) in enumerate(zip(sims[0], idxs[0]), start=1):
                if i < 0:
                    continue
                item = dict(self.id_to_metadata[i])
                item["score"] = float(s)
                item["rank"] = rank
                hits.append(item)
            return hits

    # Basis vectors: e0=[1,0,0,0] (Stage 1 cue), e1=[0,1,0,0] (Stage 2 cue), e2=[0,0,1,0] (Boosted Vid)
    vecs = np.array([
        [1.0, 0.0, 0.0, 0.0],   # 0: V_SINGLE @ 10s (Stage 1 only, no Stage 2 partner)
        [0.95, 0.0, 0.0, 0.31], # 1: V_SAME_WIN @ 10s (Stage 1)
        [0.0, 0.95, 0.0, 0.31], # 2: V_SAME_WIN @ 10.3s (delta=0.3s < min_gap=1.0s -> must reject!)
        [0.85, 0.0, 0.52, 0.0], # 3: V_PAIR @ 10s (Stage 1)
        [0.0, 0.90, 0.43, 0.0], # 4: V_PAIR @ 22s (Stage 2 after 12s gap -> MUST WIN!)
        [0.82, 0.0, 0.57, 0.0], # 5: V_OCR_WIN @ 30s (Visual match + OCR match for boost/filter test)
    ], dtype=np.float32)
    vecs = vecs / np.linalg.norm(vecs, axis=1, keepdims=True)
    metas = [
        {"video_id": "V_SINGLE", "keyframe_id": "V_SINGLE_00001", "timestamp_sec": 10.0, "file_path": "V_SINGLE_1.jpg"},
        {"video_id": "V_SAME_WIN", "keyframe_id": "V_SAME_WIN_00001", "timestamp_sec": 10.0, "file_path": "V_SW_1.jpg"},
        {"video_id": "V_SAME_WIN", "keyframe_id": "V_SAME_WIN_00002", "timestamp_sec": 10.3, "file_path": "V_SW_2.jpg"},
        {"video_id": "V_PAIR", "keyframe_id": "V_PAIR_00001", "timestamp_sec": 10.0, "file_path": "V_PAIR_1.jpg"},
        {"video_id": "V_PAIR", "keyframe_id": "V_PAIR_00002", "timestamp_sec": 22.0, "file_path": "V_PAIR_2.jpg"},
        {"video_id": "V_OCR_WIN", "keyframe_id": "V_OCR_WIN_00001", "timestamp_sec": 30.0, "file_path": "V_OCR_1.jpg"},
    ]

    class MockExtractor:
        def extract_text_embedding(self, text: str):
            t = text.lower()
            if "stage1" in t:
                return np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32)
            if "stage2" in t:
                return np.array([[0.0, 1.0, 0.0, 0.0]], dtype=np.float32)
            return np.array([[0.8, 0.0, 0.6, 0.0]], dtype=np.float32)

    engine = SearchEngine()
    engine._vector_index = MockVecIndex(vecs, metas)
    engine._visual_extractor = MockExtractor()

    # Stub DB OCR responses to isolate fusion behavior deterministically
    engine.db.get_keyframe_path = lambda kfid: f"{kfid}.jpg"
    engine._search_ocr_cue = lambda q, top_k=500, video_id=None: [
        {"video_id": "V_SINGLE", "keyframe_id": "V_SINGLE_00001", "timestamp_sec": 10.0, "score": 0.20, "text_detected": "noise"},
        {"video_id": "V_OCR_WIN", "keyframe_id": "V_OCR_WIN_00001", "timestamp_sec": 30.0, "score": 0.92, "text_detected": "51B-999"},
    ]

    # 2a. OCR Boost: low-score noise (0.20 < 0.35) does NOT hijack, high-score OCR boosts V_OCR_WIN to #1
    m_boost, tr_boost = engine.search_with_trace(
        {"visual_queries": ["stage1"], "ocr_queries": ["51B-999"], "ocr_mode": "boost", "ocr_boost_weight": 0.5},
        mode="auto",
        top_k=5
    )
    assert len(m_boost) >= 2
    assert m_boost[0].video_id == "V_OCR_WIN"
    assert tr_boost["ocr_mode"] == "boost"

    # 2b. OCR Filter: restricts results exclusively to quality-matched OCR videos (V_OCR_WIN)
    m_filter, _ = engine.search_with_trace(
        {"visual_queries": ["stage1"], "ocr_queries": ["51B-999"], "ocr_mode": "filter"},
        mode="auto",
        top_k=5
    )
    assert len(m_filter) == 1
    assert m_filter[0].video_id == "V_OCR_WIN"

    # 2c. Forward Anchor-then-Scan (Anchor=Stage 0): rejects V_SINGLE and V_SAME_WIN, picks V_PAIR
    m_seq_fwd, _ = engine.search_with_trace(
        {"scenes": [{"visual": "stage1"}, {"visual": "stage2"}], "anchor_stage": 0, "min_gap_sec": 1.0, "max_gap_sec": 30.0},
        mode="auto",
        top_k=5
    )
    assert len(m_seq_fwd) == 1
    assert m_seq_fwd[0].video_id == "V_PAIR"
    assert len(m_seq_fwd[0].cue_evidence.get("sequence_stages", [])) == 2
    assert m_seq_fwd[0].start_sec <= 10.0 and m_seq_fwd[0].end_sec >= 22.0

    # 2d. Backward Anchor-then-Scan (Anchor=Stage 1): scans backward from t=22s and finds Stage 0 at t=10s
    m_seq_bwd, _ = engine.search_with_trace(
        {"scenes": [{"visual": "stage1"}, {"visual": "stage2"}], "anchor_stage": 1, "min_gap_sec": 1.0, "max_gap_sec": 30.0},
        mode="auto",
        top_k=5
    )
    assert len(m_seq_bwd) == 1
    assert m_seq_bwd[0].video_id == "V_PAIR"
    assert m_seq_bwd[0].cue_evidence["sequence_stages"][0]["timestamp_sec"] < m_seq_bwd[0].cue_evidence["sequence_stages"][1]["timestamp_sec"]

    print("[OK] Task 07A Visual-First OCR (Boost/Filter) & Anchor-then-Scan Sequential tests passed!")


if __name__ == "__main__":
    test_query_parser()
    test_score_fusion()
    test_search_with_trace()
    test_kis_endpoints()
    test_task_07a_visual_first_and_anchor_sequence()
