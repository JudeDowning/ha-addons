from datetime import datetime

from backend.core.sync_service import _event_to_baby_payload
from backend.core.models import Event
from backend.core.babyconnect_client import BabyConnectClient
from backend.core.normalisation import RawBabyConnectEvent


def test_garden_event_maps_to_babyconnect_activity_payload():
    event = Event(
        id=1,
        source_system="famly",
        fingerprint="garden-fp",
        child_name="Elijah Downing",
        event_type="Garden",
        start_time_utc=datetime(2026, 6, 8, 10, 0),
        end_time_utc=datetime(2026, 6, 8, 10, 45),
        details_json={"raw_text": "Garden", "raw_data": {"detail_lines": ["10:00 - 10:45", "Garden"]}},
    )

    payload = _event_to_baby_payload(event)

    assert payload is not None
    assert payload["event_type"] == "activity"
    assert payload["activity_type"] == "702"
    assert payload["activity_text"] == "Elijah Downing is playing in the garden"
    assert payload["note"] == "Garden"


def test_babyconnect_activity_title_is_inferred_as_activity():
    client = BabyConnectClient(email="test@example.com", password="secret")

    assert client._infer_event_type("Playing with Others", "") == "activity"
    assert client._infer_event_type("Garden", "") == "activity"


def test_activity_detail_lines_preserve_note_text():
    client = BabyConnectClient(email="test@example.com", password="secret")
    lines = client._build_detail_lines(
        event_type="activity",
        title_text="Playing with Others",
        note_text="Garden [Sync]",
        display_range=None,
    )

    assert lines == ["Garden"]


def test_activity_verification_matches_note_text():
    client = BabyConnectClient(email="test@example.com", password="secret")
    entry = {
        "fingerprint": "missing-fingerprint",
        "event_type": "activity",
        "activity_type": "702",
        "activity_text": "Elijah Downing is playing in the garden",
        "note": "Garden",
        "start_time_utc": "2026-06-08T10:00:00+00:00",
        "end_time_utc": "2026-06-08T10:45:00+00:00",
        "raw_data": {"day_date_iso": "2026-06-08"},
    }
    raw_event = RawBabyConnectEvent(
        child_name="Elijah Downing",
        event_type="activity",
        time_str="10:00AM - 10:45AM by Jude",
        raw_text="Playing with Others",
        raw_data={
            "day_date_iso": "2026-06-08",
            "note": "Garden [Sync]",
            "detail_lines": ["Garden"],
        },
        event_datetime_iso="2026-06-08T10:00:00+00:00",
    )
    normalized = {
        "fingerprint": "different-fingerprint",
        "start_time_utc": datetime.fromisoformat("2026-06-08T10:00:00+00:00"),
        "end_time_utc": datetime.fromisoformat("2026-06-08T10:45:00+00:00"),
    }

    assert client._entry_matches_scraped_event(entry, raw_event, normalized) is True
