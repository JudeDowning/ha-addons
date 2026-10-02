import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import routes_homeassistant
from backend.api.sync_lock import acquire_sync_lock, release_sync_lock


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(routes_homeassistant.router, prefix="/api")
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("query, expected_days", [("", 0), ("?days_back=0", 0), ("?days_back=1", 1)])
def test_run_scrapes_requested_entry_days_then_syncs_missing(client, monkeypatch, query, expected_days):
    calls = []

    def scrape(days_back):
        calls.append(("scrape", days_back))
        return [object()]

    def missing():
        calls.append(("missing",))
        return [42]

    def create(event_ids):
        calls.append(("create", event_ids))
        return {"created": 1, "synced_event_ids": event_ids}

    monkeypatch.setattr(routes_homeassistant, "scrape_famly_and_store", scrape)
    monkeypatch.setattr(routes_homeassistant, "get_missing_famly_event_ids", missing)
    monkeypatch.setattr(routes_homeassistant, "create_entries_service", create)

    response = client.post(f"/api/homeassistant/run{query}")

    assert response.status_code == 200
    assert calls == [("scrape", expected_days), ("missing",), ("create", [42])]
    assert response.json()["created"] == 1
    assert response.json()["synced_event_ids"] == [42]
    assert response.json()["days_back"] == expected_days


def test_run_rejects_overlapping_sync(client):
    acquire_sync_lock()
    try:
        assert client.post("/api/homeassistant/run?days_back=0").status_code == 409
    finally:
        release_sync_lock()


def test_failed_scrape_releases_lock_and_does_not_sync(client, monkeypatch):
    def fail_scrape(days_back):
        raise RuntimeError("Scrape unavailable")

    def unexpected_sync():
        pytest.fail("Must not sync stale events after a failed scrape")

    monkeypatch.setattr(routes_homeassistant, "scrape_famly_and_store", fail_scrape)
    monkeypatch.setattr(routes_homeassistant, "get_missing_famly_event_ids", unexpected_sync)

    response = client.post("/api/homeassistant/run?days_back=0")
    assert response.status_code == 500
    assert "Scrape unavailable" in response.json()["detail"]
    acquire_sync_lock()
    release_sync_lock()
