from contextlib import contextmanager
from datetime import datetime
import sys
from types import SimpleNamespace
import types


fake_famly_module = types.ModuleType("backend.core.famly_client")
fake_babyconnect_module = types.ModuleType("backend.core.babyconnect_client")


class _ImportStubClient:
    def __init__(self, *args, **kwargs):
        pass


fake_famly_module.FamlyClient = _ImportStubClient
fake_babyconnect_module.BabyConnectClient = _ImportStubClient
sys.modules.setdefault("backend.core.famly_client", fake_famly_module)
sys.modules.setdefault("backend.core.babyconnect_client", fake_babyconnect_module)

from backend.core import sync_service


class _FakeQuery:
    def filter(self, *args, **kwargs):
        return self

    def delete(self):
        return None


class _FakeSession:
    def __init__(self):
        self.added = []

    def query(self, *args, **kwargs):
        return _FakeQuery()

    def flush(self):
        return None

    def add(self, event):
        self.added.append(event)


def test_scrape_famly_deduplicates_fingerprints_within_single_run(monkeypatch):
    fake_session = _FakeSession()

    @contextmanager
    def fake_get_session():
        yield fake_session

    class _FakeFamlyClient:
        def __init__(self, email: str, password: str):
            self.email = email
            self.password = password

        def login_and_scrape(self, days_back: int = 0, progress_callback=None):
            return ["event-1", "event-2", "event-3"]

    def fake_normalise(raw_event):
        base = {
            "source_system": "famly",
            "child_name": "Elijah Downing",
            "event_type": "Message",
            "start_time_utc": datetime(2026, 3, 26, 17, 43),
            "end_time_utc": None,
            "details_json": {"raw_text": str(raw_event), "raw_data": {}},
        }
        if raw_event in ("event-1", "event-2"):
            return {**base, "fingerprint": "duplicate-fingerprint"}
        return {**base, "fingerprint": "unique-fingerprint"}

    monkeypatch.setattr(
        sync_service,
        "get_credentials",
        lambda service_name: SimpleNamespace(email="test@example.com", password_encrypted="secret"),
    )
    monkeypatch.setattr(sync_service, "FamlyClient", _FakeFamlyClient)
    monkeypatch.setattr(sync_service, "normalise_famly_event", fake_normalise)
    monkeypatch.setattr(sync_service, "get_session", fake_get_session)
    monkeypatch.setattr(sync_service, "start_progress", lambda *args, **kwargs: None)
    monkeypatch.setattr(sync_service, "set_progress_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(sync_service, "set_progress_total", lambda *args, **kwargs: None)
    monkeypatch.setattr(sync_service, "increment_progress", lambda *args, **kwargs: None)
    monkeypatch.setattr(sync_service, "finish_progress", lambda *args, **kwargs: None)
    monkeypatch.setattr(sync_service, "fail_progress", lambda *args, **kwargs: None)
    monkeypatch.setattr(sync_service, "clear_progress", lambda *args, **kwargs: None)

    stored = sync_service.scrape_famly_and_store(days_back=0)

    assert len(stored) == 2
    assert len(fake_session.added) == 2
    assert {event.fingerprint for event in stored} == {
        "duplicate-fingerprint",
        "unique-fingerprint",
    }
