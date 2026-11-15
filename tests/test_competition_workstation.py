"""
Unit tests for Task 06C: Dedicated KIS Competition Workstation UI and Server.
"""

from fastapi.testclient import TestClient
from src.ui.competition_server import app


def test_competition_server_endpoints():
    client = TestClient(app)

    # 1. Healthcheck
    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    assert res_health.json().get("status") == "ok"

    # 2. Serve static index.html and assets
    res_index = client.get("/")
    assert res_index.status_code == 200
    assert "KIS Competition Workstation" in res_index.text

    res_css = client.get("/style.css")
    assert res_css.status_code == 200

    res_js = client.get("/app.js")
    assert res_js.status_code == 200

    # 3. DRES Status Endpoint
    res_status = client.get("/api/dres/status")
    assert res_status.status_code == 200
    assert "is_authenticated" in res_status.json()

    # 4. Temporal context filmstrip
    res_ctx = client.get("/api/videos/L01_V001/context?timestamp_sec=20.0&window_sec=15.0")
    assert res_ctx.status_code == 200
    ctx_data = res_ctx.json()
    assert ctx_data.get("video_id") == "L01_V001"
    assert "frames" in ctx_data

    # 5. DRES Submit dry-run and duplicate suppression
    client.post("/api/dres/clear-cache")
    payload = {
        "video_id": "L05_V014.mp4",
        "start_sec": 10.0,
        "end_sec": 15.0,
        "dry_run": True
    }
    res_sub1 = client.post("/api/dres/submit", json=payload)
    assert res_sub1.status_code == 200
    assert res_sub1.json().get("status") == "DRY_RUN_ACCEPTED"

    res_sub2 = client.post("/api/dres/submit", json=payload)
    assert res_sub2.status_code == 200
    assert res_sub2.json().get("status") == "DUPLICATE_PREVENTED"

    client.post("/api/dres/clear-cache")
    print("[OK] Task 06C Competition Server endpoint tests passed!")


def test_translate_endpoint():
    client = TestClient(app)

    # 1. Empty query
    res_empty = client.post("/api/translate", json={"query": ""})
    assert res_empty.status_code == 200
    assert res_empty.json().get("translated_query") == ""

    # 2. Visual query with OCR preservation
    payload = {
        "query": "xe buýt màu xanh | ocr: 51B-501.62",
        "source_lang": "auto",
        "target_lang": "en"
    }
    res_trans = client.post("/api/translate", json=payload)
    assert res_trans.status_code == 200
    data = res_trans.json()
    assert data.get("status") in ("ok", "fallback")
    assert "ocr: 51B-501.62" in data.get("translated_query")
    assert "51B-501.62" in data.get("preserved_ocr")

    # 3. Consistency between plain visual and 'v:' prefix
    r1 = client.post("/api/translate", json={"query": "con chó"}).json()
    r2 = client.post("/api/translate", json={"query": "v: con chó"}).json()
    assert r1.get("translated_query") == r2.get("translated_query") == "dog"

    # 4. Cache verification (second call must have cached: True)
    res_cached = client.post("/api/translate", json=payload)
    assert res_cached.status_code == 200
    assert res_cached.json().get("cached") is True

    print("[OK] Task 06D Translation endpoint tests passed!")


def test_dres_collection_name_payload():
    """Verify optional mediaItemCollectionName support in DRES session & submit endpoints."""
    client = TestClient(app)

    # Clear cache first
    client.post("/api/dres/clear-cache")

    # 1. Configure collection_name via /api/dres/session
    res_cfg = client.post("/api/dres/session", json={"collection_name": "AIC24_Batch1"})
    assert res_cfg.status_code == 200
    assert res_cfg.json().get("collection_name") == "AIC24_Batch1"

    # 2. Submit dry-run and verify mediaItemCollectionName is present
    res_sub = client.post("/api/dres/submit", json={
        "video_id": "L15_V015",
        "start_sec": 10.0,
        "end_sec": 15.0,
        "dry_run": True
    })
    assert res_sub.status_code == 200
    answer = res_sub.json()["payload"]["answerSets"][0]["answers"][0]
    assert answer["mediaItemName"] == "L15_V015"
    assert answer["mediaItemCollectionName"] == "AIC24_Batch1"

    # 3. Clear collection_name and verify mediaItemCollectionName is omitted
    res_clear_cfg = client.post("/api/dres/session", json={"collection_name": ""})
    assert res_clear_cfg.status_code == 200
    assert res_clear_cfg.json().get("collection_name") is None

    res_sub2 = client.post("/api/dres/submit", json={
        "video_id": "L15_V015",
        "start_sec": 20.0,
        "end_sec": 25.0,
        "dry_run": True
    })
    assert res_sub2.status_code == 200
    answer2 = res_sub2.json()["payload"]["answerSets"][0]["answers"][0]
    assert "mediaItemCollectionName" not in answer2

    print("[OK] DRES mediaItemCollectionName tests passed!")


def test_task_07a_workstation_ui_and_post_search():
    """Verify Task 07A UI controls and structured POST /api/search/multimodal contract."""
    client = TestClient(app)

    res_html = client.get("/")
    assert res_html.status_code == 200
    html = res_html.text
    for elem_id in ("ocrQueryInput", "ocrRoleSelect", "toggleSequenceBtn", "scene2Input", "sequenceAnchorSelect", "sequenceGapSelect"):
        assert elem_id in html, f"Missing Task 07A element {elem_id} in index.html"

    # Structured OCR-only POST search via ocr_text + mode="ocr"
    res_post = client.post("/api/search/multimodal", json={
        "ocr_text": "trùng biển số",
        "mode": "ocr",
        "top_k": 5
    })
    assert res_post.status_code == 200
    body = res_post.json()
    assert body["total_results"] > 0
    assert "stage_hits" in body["candidates"][0]

    print("[OK] Task 07A Competition Workstation UI & POST search contract tests passed!")


def test_task_07b_similarity_endpoint_and_ui():
    """Verify Task 07B UI controls, batch scope, video blacklist, and 0ms POST /api/search/similar."""
    client = TestClient(app)

    # 1. Verify UI HTML includes Task 07B controls
    res_html = client.get("/")
    assert res_html.status_code == 200
    html = res_html.text
    for elem_id in (
        "refKeyframePill",
        "clearRefKeyframeBtn",
        "negativeQueryInput",
        "batchScopeBtn",
        "batchScopePopover",
        "excludedVideosBar",
        "resetExcludedVideosBtn",
        "simActiveBar",
        "exitSimModeBtn",
    ):
        assert elem_id in html, f"Missing Task 07B element {elem_id} in index.html"

    # 2. Validation checks on /api/search/similar
    res_bad = client.post("/api/search/similar", json={"keyframe_id": ""})
    assert res_bad.status_code == 400

    res_missing = client.post("/api/search/similar", json={"keyframe_id": "L99_V999_99999"})
    assert res_missing.status_code == 404

    # 3. Live 0ms similarity search on indexed keyframe from L01_V001
    res_ctx = client.get("/api/videos/L01_V001/context?timestamp_sec=10.0&window_sec=15.0")
    assert res_ctx.status_code == 200
    frames = res_ctx.json().get("frames", [])
    assert frames, "Expected frames in L01_V001 temporal context"
    target_kfid = frames[0]["keyframe_id"]

    res_sim = client.post("/api/search/similar", json={
        "keyframe_id": target_kfid,
        "top_k": 10
    })
    assert res_sim.status_code == 200
    sim_body = res_sim.json()
    assert sim_body["mode"] == "similar"
    assert sim_body["total_results"] > 0
    assert sim_body["candidates"][0]["video_id"] == "L01_V001"
    assert sim_body["candidates"][0]["keyframe_id"] == target_kfid

    # 4. Active exclusion + batch scope filtering via /api/search/similar
    res_filtered = client.post("/api/search/similar", json={
        "keyframe_id": target_kfid,
        "excluded_videos": ["L01_V001"],
        "allowed_batches": ["L02", "L03"],
        "top_k": 5
    })
    assert res_filtered.status_code == 200
    filt_body = res_filtered.json()
    for c in filt_body["candidates"]:
        assert c["video_id"] != "L01_V001"
        assert c["video_id"].startswith(("L02_", "L03_"))

    print("[OK] Task 07B Similarity Search Endpoint & Workstation UI tests passed!")


def test_task_07c_video_grouping_and_dual_frame_contracts() -> None:
    """Verifies Task 07C grouped_videos contract, normalized stage_hits, and view-switcher UI assets."""
    from src.common.types import CandidateMoment
    from src.ui.competition_server import _group_results_by_video, _serialize_moments, app

    client = TestClient(app)

    # 1. Verify UI HTML & JS view switcher / dual-frame / strip symbols
    html = client.get("/").text
    for elem_id in ("viewModeSwitch", "viewModeFramesBtn", "viewModeVideoBtn"):
        assert elem_id in html, f"Missing Task 07C element {elem_id} in index.html"

    js_res = client.get("/app.js")
    assert js_res.status_code == 200
    js_src = js_res.text
    for marker in ("groupCandidatesByVideo", "createVideoStripCard", "dual-frame-wrapper"):
        assert marker in js_src, f"Missing Task 07C frontend symbol {marker} in app.js"

    # 2. Unit-check normalized stage_hits serialization for sequential moments
    m_seq = CandidateMoment(
        video_id="L01_V001",
        start_sec=10.0,
        end_sec=22.4,
        start_ms=10000,
        end_ms=22400,
        score=0.9123,
        matched_cues=["s0_v0", "s1_v0"],
        keyframe_id="L01_V001_00010",
        thumbnail_url="/api/keyframes/L01_V001/L01_V001_00010.jpg",
        cue_evidence={
            "sequence_stages": [
                {"stage_index": 1, "keyframe_id": "L01_V001_00022", "video_id": "L01_V001", "timestamp_sec": 22.4, "score": 0.72},
                {"stage_index": 0, "keyframe_id": "L01_V001_00010", "video_id": "L01_V001", "timestamp_sec": 10.0, "score": 0.88},
            ]
        }
    )
    m_single_high = CandidateMoment(
        video_id="L01_V001",
        start_sec=4.0,
        end_sec=6.0,
        start_ms=4000,
        end_ms=6000,
        score=0.65,
        keyframe_id="L01_V001_00004",
        thumbnail_url="/api/keyframes/L01_V001/L01_V001_00004.jpg",
    )
    m_other_vid = CandidateMoment(
        video_id="L02_V003",
        start_sec=30.0,
        end_sec=35.0,
        start_ms=30000,
        end_ms=35000,
        score=0.80,
        keyframe_id="L02_V003_00030",
        thumbnail_url="/api/keyframes/L02_V003/L02_V003_00030.jpg",
    )
    serialized = _serialize_moments([m_seq, m_other_vid, m_single_high])
    assert serialized[0]["is_sequential"] is True
    assert [s["stage_index"] for s in serialized[0]["stage_hits"]] == [0, 1]
    assert serialized[0]["stage_hits"][1]["thumbnail_url"] == "/api/keyframes/L01_V001/L01_V001_00022.jpg"

    grouped = _group_results_by_video(serialized, max_hits_per_video=7)
    assert len(grouped) == 2
    assert grouped[0]["video_id"] == "L01_V001"
    assert grouped[1]["video_id"] == "L02_V003"
    # L01_V001 hits sorted chronologically (4.0 before 10.0)
    assert [h["start_sec"] for h in grouped[0]["hits"]] == [4.0, 10.0]

    # 3. Live endpoint check for grouped_videos field
    res_ctx = client.get("/api/videos/L01_V001/context?timestamp_sec=10.0&window_sec=15.0")
    frames = res_ctx.json().get("frames", [])
    res_sim = client.post("/api/search/similar", json={"keyframe_id": frames[0]["keyframe_id"], "top_k": 15})
    assert res_sim.status_code == 200
    sim_body = res_sim.json()
    assert "grouped_videos" in sim_body
    assert len(sim_body["grouped_videos"]) >= 1
    first_group = sim_body["grouped_videos"][0]
    assert first_group["rank"] == 1
    assert first_group["hits"] == sorted(first_group["hits"], key=lambda h: h["start_sec"])

    print("[OK] Task 07C Video Grouping & Dual-Frame Sequential Contract tests passed!")


def test_task_07d_cockpit_layout_and_hit_markers() -> None:
    """Verifies Task 07D Zero-Popup Split Cockpit layout, header timer capsule, and hit marker assets."""
    client = TestClient(app)

    html = client.get("/").text
    for marker in (
        "headerTimerCapsule",
        "timerDetailsBtn",
        "timerDetailsPopover",
        "stopwatchClock",
        "predictedTotalScore",
        "dockedPlayerPanel",
        "dockedPlayerTitle",
        "expandPopupBtn",
        "cockpitSubmitDock",
        "timelineHitMarkers",
        'id="layoutModeLabel">Cockpit<',
        'id="dockedPlayerPanel" class="docked-player-panel"',
    ):
        assert marker in html, f"Missing Task 07D cockpit marker {marker} in index.html"

    # Left command sidebar should no longer squeeze the canvas grid
    assert 'id="kisCommandSidebar"' not in html

    js_src = client.get("/app.js").text
    for js_symbol in (
        "layoutMode: 'docked'",
        "renderTimelineHitMarkers",
        "expandDockedToPopup",
        "window_sec=10.0",
    ):
        assert js_symbol in js_src, f"Missing Task 07D JS symbol {js_symbol} in app.js"

    css_src = client.get("/style.css").text
    for css_cls in (
        ".header-timer-capsule",
        ".cockpit-submit-dock",
        ".timeline-hit-marker",
    ):
        assert css_cls in css_src, f"Missing Task 07D CSS rule {css_cls} in style.css"

    print("[OK] Task 07D Split Cockpit Layout & Timeline Hit Markers tests passed!")


def test_dres_explicit_evaluation_id_preserved():
    """Verify explicit evaluation_id is not overwritten by auto-detection during login or submit."""
    import src.ui.competition_server as cs

    client = TestClient(app)
    dres = cs.get_dres_client()
    orig_login = dres.login
    orig_get_active = dres.get_active_evaluation
    orig_eval_id = cs._dres_eval_id
    orig_session_id = dres.session_id

    try:
        def fake_login(username: str, password: str) -> str:
            dres.set_session_id("mock_session_123")
            return "mock_session_123"

        dres.login = fake_login
        dres.get_active_evaluation = lambda: {"id": "bcb482c6-2b9e-4908-877a-e5ccd7c04640", "name": "Eval 1"}

        # 1. Default evaluation_id ("offline_kis_eval") auto-detects active evaluation on login
        res_auto = client.post("/api/dres/session", json={
            "evaluation_id": "offline_kis_eval",
            "username": "team06",
            "password": "secret"
        })
        assert res_auto.status_code == 200
        assert res_auto.json().get("evaluation_id") == "bcb482c6-2b9e-4908-877a-e5ccd7c04640"

        # 2. Explicit custom evaluation_id MUST NOT be overwritten even when username/password are sent
        res_explicit = client.post("/api/dres/session", json={
            "evaluation_id": "custom-eval-2222-3333",
            "username": "team06",
            "password": "secret"
        })
        assert res_explicit.status_code == 200
        assert res_explicit.json().get("evaluation_id") == "custom-eval-2222-3333"

        # 3. Submitting with an explicit evaluation_id persists it for subsequent /api/dres/status reads
        client.post("/api/dres/clear-cache")
        res_sub = client.post("/api/dres/submit", json={
            "video_id": "L15_V015",
            "start_sec": 12.0,
            "end_sec": 17.0,
            "evaluation_id": "submit-eval-7777",
            "dry_run": True
        })
        assert res_sub.status_code == 200
        assert res_sub.json().get("evaluation_id") == "submit-eval-7777"
        assert client.get("/api/dres/status").json().get("evaluation_id") == "submit-eval-7777"
    finally:
        dres.login = orig_login
        dres.get_active_evaluation = orig_get_active
        dres.set_session_id(orig_session_id)
        cs._dres_eval_id = orig_eval_id
        client.post("/api/dres/clear-cache")

    print("[OK] DRES explicit evaluation_id preservation tests passed!")


if __name__ == "__main__":
    test_competition_server_endpoints()
    test_translate_endpoint()
    test_dres_collection_name_payload()
    test_task_07a_workstation_ui_and_post_search()
    test_task_07b_similarity_endpoint_and_ui()
    test_task_07c_video_grouping_and_dual_frame_contracts()
    test_task_07d_cockpit_layout_and_hit_markers()
    test_dres_explicit_evaluation_id_preserved()
