from contextlib import contextmanager
from datetime import datetime
import sys
from types import SimpleNamespace
import types

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.models import Base, Event, SyncClaim

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


def _build_test_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    @contextmanager
    def session_factory():
        session = TestingSessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return session_factory


def test_create_babyconnect_entries_records_claim_and_prevents_repost(monkeypatch):
    session_factory = _build_test_session()

    with session_factory() as session:
        session.add(
            Event(
                id=1,
                source_system="famly",
                fingerprint="famly-fp-1",
                child_name="Elijah Downing",
                event_type="sleep",
                start_time_utc=datetime(2026, 3, 26, 12, 0),
                end_time_utc=datetime(2026, 3, 26, 13, 0),
                details_json={"raw_text": "Nap", "raw_data": {"detail_lines": ["12:00 - 13:00"]}},
            )
        )

    class _FakeBabyConnectClient:
        calls = 0

        def __init__(self, email: str, password: str):
            self.email = email
            self.password = password

        def create_entries(self, entries):
            _FakeBabyConnectClient.calls += 1
            return {
                "status": "ok",
                "created": len(entries),
                "created_fingerprints": [entry["fingerprint"] for entry in entries],
                "failed_fingerprints": [],
            }

    monkeypatch.setattr(sync_service, "get_session", session_factory)
    monkeypatch.setattr(
        sync_service,
        "get_credentials",
        lambda service_name: SimpleNamespace(email="test@example.com", password_encrypted="secret"),
    )
    monkeypatch.setattr(sync_service, "BabyConnectClient", _FakeBabyConnectClient)
    monkeypatch.setattr(sync_service, "scrape_babyconnect_and_store", lambda days_back=0: [])

    first = sync_service.create_babyconnect_entries([1])
    second = sync_service.create_babyconnect_entries([1])
    missing_ids = sync_service.get_missing_famly_event_ids()

    assert first["created"] == 1
    assert second["created"] == 0
    assert missing_ids == []
    assert _FakeBabyConnectClient.calls == 1

    with session_factory() as session:
        claims = session.query(SyncClaim).all()

    assert len(claims) == 1
    assert claims[0].fingerprint == "famly-fp-1"
    assert claims[0].status == "synced"


def test_failed_claims_are_retryable(monkeypatch):
    session_factory = _build_test_session()

    with session_factory() as session:
        session.add(
            Event(
                id=2,
                source_system="famly",
                fingerprint="famly-fp-2",
                child_name="Elijah Downing",
                event_type="solid",
                start_time_utc=datetime(2026, 3, 26, 14, 0),
                end_time_utc=None,
                details_json={"raw_text": "Lunch", "raw_data": {"detail_lines": ["pasta"]}},
            )
        )

    class _FlakyBabyConnectClient:
        calls = 0

        def __init__(self, email: str, password: str):
            self.email = email
            self.password = password

        def create_entries(self, entries):
            _FlakyBabyConnectClient.calls += 1
            if _FlakyBabyConnectClient.calls == 1:
                return {
                    "status": "ok",
                    "created": 0,
                    "created_fingerprints": [],
                    "failed_fingerprints": [entry["fingerprint"] for entry in entries],
                }
            return {
                "status": "ok",
                "created": len(entries),
                "created_fingerprints": [entry["fingerprint"] for entry in entries],
                "failed_fingerprints": [],
            }

    monkeypatch.setattr(sync_service, "get_session", session_factory)
    monkeypatch.setattr(
        sync_service,
        "get_credentials",
        lambda service_name: SimpleNamespace(email="test@example.com", password_encrypted="secret"),
    )
    monkeypatch.setattr(sync_service, "BabyConnectClient", _FlakyBabyConnectClient)
    monkeypatch.setattr(sync_service, "scrape_babyconnect_and_store", lambda days_back=0: [])

    first = sync_service.create_babyconnect_entries([2])
    missing_after_failure = sync_service.get_missing_famly_event_ids()
    second = sync_service.create_babyconnect_entries([2])

    assert first["created"] == 0
    assert first["failed"] == 1
    assert missing_after_failure == [2]
    assert second["created"] == 1
    assert _FlakyBabyConnectClient.calls == 2
