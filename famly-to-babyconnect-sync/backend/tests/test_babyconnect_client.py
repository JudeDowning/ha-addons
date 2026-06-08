from datetime import datetime, timezone

from backend.core.babyconnect_client import BabyConnectClient
from backend.core.normalisation import RawBabyConnectEvent, normalise_babyconnect_event


def test_verify_created_entries_confirms_matching_fingerprint(monkeypatch):
    client = BabyConnectClient(email="test@example.com", password="secret")
    start = datetime(2026, 6, 8, 8, 28, tzinfo=timezone.utc)
    entry = {
        "fingerprint": None,
        "event_type": "message",
        "start_time_utc": start.isoformat(),
        "message": "SYNC TEST verification",
        "note": "SYNC TEST verification",
        "summary": "SYNC TEST verification",
        "raw_text": "SYNC TEST verification",
        "raw_data": {"day_date_iso": "2026-06-08"},
    }
    raw_event = RawBabyConnectEvent(
        child_name="Elijah Downing",
        event_type="message",
        time_str="8:28AM by Jude",
        raw_text="SYNC TEST verification [Sync]",
        raw_data={
            "day_date_iso": "2026-06-08",
            "note": "",
            "detail_lines": ["SYNC TEST verification [Sync]"],
        },
        event_datetime_iso=start.isoformat(),
    )
    entry["fingerprint"] = normalise_babyconnect_event(raw_event)["fingerprint"]

    monkeypatch.setattr(client, "login_and_scrape", lambda days_back=0, allowed_days=None, progress_callback=None: [raw_event])

    verified, unverified = client._verify_created_entries([entry])

    assert verified == {entry["fingerprint"]}
    assert unverified == set()


def test_verify_created_entries_marks_missing_entries_unverified(monkeypatch):
    client = BabyConnectClient(email="test@example.com", password="secret")
    entry = {
        "fingerprint": "missing-fingerprint",
        "event_type": "message",
        "start_time_utc": "2026-06-08T08:28:00+00:00",
        "message": "Missing verification",
        "raw_data": {"day_date_iso": "2026-06-08"},
    }

    monkeypatch.setattr(client, "login_and_scrape", lambda days_back=0, allowed_days=None, progress_callback=None: [])

    verified, unverified = client._verify_created_entries([entry])

    assert verified == set()
    assert unverified == {"missing-fingerprint"}
