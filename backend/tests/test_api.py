from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from fastapi.testclient import TestClient
import pytest

from .conftest import PRACTICAL_II


@pytest.fixture()
def client(tmp_path: Path, seed_dir: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("SEED_DIR", str(seed_dir))
    monkeypatch.setenv("SYNC_ENABLED", "0")
    monkeypatch.setenv("SETTINGS_PASSWORD", "Pielęgniarstwo")
    monkeypatch.setenv("SOURCE_PAGE_URL", "https://example.invalid/plan/?fbclid=abc")

    from app import config, main

    config.get_settings.cache_clear()
    main.get_service.cache_clear()
    app = main.create_app()
    with TestClient(app) as test_client:
        yield test_client
    config.get_settings.cache_clear()
    main.get_service.cache_clear()


def test_plan_endpoint_with_etag(client: TestClient) -> None:
    response = client.get("/api/v1/plan")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["events"]) == 544
    assert {source["kind"] for source in payload["sources"]} == {"main", "practical"}
    etag = response.headers["etag"]

    cached = client.get("/api/v1/plan", headers={"If-None-Match": etag})
    assert cached.status_code == 304

    gzipped = client.get("/api/v1/plan", headers={"Accept-Encoding": "gzip"})
    assert gzipped.headers.get("content-encoding") == "gzip"


def test_status_endpoint(client: TestClient) -> None:
    payload = client.get("/api/v1/status").json()
    assert payload["version"]
    assert payload["sync"]["page_url"] == "https://example.invalid/plan/"
    assert payload["sync"]["interval_seconds"] == 300
    assert len(payload["sources"]) == 2


def test_calendar_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/calendar.ics", params={"group": "1a", "lek": "A", "cw-a": "I", "download": "1"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    assert 'filename="plan-zajec-1a-A-I.ics"' in response.headers["content-disposition"]
    assert "BEGIN:VEVENT" in response.text


def test_admin_upload_requires_password(client: TestClient) -> None:
    files = {"file": (PRACTICAL_II.name, PRACTICAL_II.read_bytes(), "application/octet-stream")}
    assert client.post("/api/v1/admin/upload", files=files).status_code == 401
    assert client.post("/api/v1/admin/upload", files=files, headers={"x-settings-password": "zle"}).status_code == 401

    ok = client.post("/api/v1/admin/upload", files=files, headers={"x-settings-password": quote("Pielęgniarstwo")})
    assert ok.status_code == 200, ok.text
    assert ok.json()["kind"] == "practical"
    plan = client.get("/api/v1/plan").json()
    assert any(source["origin"] == "manual" for source in plan["sources"])

    bad = client.post(
        "/api/v1/admin/upload",
        files={"file": ("x.xlsx", b"nope", "application/octet-stream")},
        headers={"x-settings-password": quote("Pielęgniarstwo")},
    )
    assert bad.status_code == 422

    cleared = client.delete("/api/v1/admin/manual", headers={"x-settings-password": quote("Pielęgniarstwo")})
    assert cleared.status_code == 200
    plan = client.get("/api/v1/plan").json()
    assert all(source["origin"] != "manual" for source in plan["sources"])


def test_force_sync_is_throttled(client: TestClient) -> None:
    first = client.post("/api/v1/sync").json()
    second = client.post("/api/v1/sync").json()
    assert first["accepted"] is True
    assert second["accepted"] is False


def test_health(client: TestClient) -> None:
    payload = client.get("/api/v1/health").json()
    assert payload["status"] == "ok"
    assert payload["events"] == 544
