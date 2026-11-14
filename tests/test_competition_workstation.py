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


if __name__ == "__main__":
    test_competition_server_endpoints()
    test_translate_endpoint()
