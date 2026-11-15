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


if __name__ == "__main__":
    test_competition_server_endpoints()
    test_translate_endpoint()
    test_dres_collection_name_payload()
    test_task_07a_workstation_ui_and_post_search()
