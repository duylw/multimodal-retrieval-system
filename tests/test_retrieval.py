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

    print("[OK] All QueryParser tests passed successfully!")


def test_score_fusion():
    from src.retrieval.score_fusion import TemporalMomentFusor, MaxPerCueRRFStrategy

    strategy = MaxPerCueRRFStrategy(k_rrf=60, consensus_boost_per_cue=0.25)
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

    print("[OK] Max-Per-Cue and Consensus Multiplier test passed!")


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


if __name__ == "__main__":
    test_query_parser()
    test_score_fusion()
    test_search_with_trace()
