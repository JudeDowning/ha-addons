"""
Sync service.
-------------

High-level orchestration for:

- Scraping Famly events
- Scraping Baby Connect events (optional)
- Normalising and storing them
- Matching via fingerprint
- Creating missing events in Baby Connect
"""

from __future__ import annotations

from typing import Dict, Any, List, Iterable, Set
from datetime import datetime

from .storage import get_session
from .models import Event, Credential, SyncLink, IgnoredEvent
from .normalisation import normalise_famly_event, RawFamlyEvent, RawBabyConnectEvent, normalise_babyconnect_event
from .famly_client import FamlyClient
from .babyconnect_client import BabyConnectClient
from .settings_store import get_sync_preferences, SYNC_INCLUDE_DEFAULT
from .progress_state import (
    start_progress,
    increment_progress,
    finish_progress,
    fail_progress,
    clear_progress,
    set_progress_total,
    set_progress_message,
)

def test_service_credentials(service_name: str) -> None:
    cred = get_credentials(service_name)
    if not cred:
        raise RuntimeError(f"No {service_name.replace('_', ' ').title()} credentials configured.")
    if service_name == "famly":
        client = FamlyClient(email=cred.email, password=cred.password_encrypted)
        client.verify_login()
    elif service_name == "baby_connect":
        client = BabyConnectClient(email=cred.email, password=cred.password_encrypted)
        client.verify_login()
    else:
        raise RuntimeError(f"Unsupported service '{service_name}'")

def get_credentials(service_name: str) -> Credential | None:
    with get_session() as session:
        return (
            session.query(Credential)
            .filter(Credential.service_name == service_name)
            .order_by(Credential.updated_at.desc())
            .first()
        )

def _get_ignored_fingerprints(session) -> Set[str]:
    return {
        row[0]
        for row in session.query(IgnoredEvent.fingerprint).all()
    }


def scrape_famly_and_store(days_back: int = 0) -> List[Event]:
    """
    Scrape events from Famly, normalise them, and save to the database.
    """
    cred = get_credentials("famly")
    if not cred:
        raise RuntimeError("No Famly credentials configured.")

    client = FamlyClient(email=cred.email, password=cred.password_encrypted)  # TODO: decrypt when encryption is added
    start_progress("famly", 0)
    set_progress_message("famly", "Preparing Famly scrape...")
    def _report(message: str) -> None:
        set_progress_message("famly", message)

    raw_events: List[RawFamlyEvent] = client.login_and_scrape(days_back=days_back, progress_callback=_report)
    normalised: List[Dict[str, Any]] = [normalise_famly_event(r) for r in raw_events]
    set_progress_total("famly", len(normalised))
    set_progress_message("famly", "Storing Famly events...")
    stored_events: List[Event] = []
    try:
        with get_session() as session:
            session.query(Event).filter(Event.source_system == "famly").delete()
            session.flush()
            for ev in normalised:
                new_ev = Event(**ev)
                session.add(new_ev)
                session.flush()  # assign id
                stored_events.append(new_ev)
                increment_progress("famly")
    except Exception as exc:
        fail_progress("famly", str(exc))
        clear_progress("famly")
        raise
    else:
        finish_progress("famly")
        clear_progress("famly")

    return stored_events

def get_events(source_system: str, limit: int = 100) -> List[Event]:
    """
    Return the most recent events for a given source system.
    """
    with get_session() as session:
        return (
            session.query(Event)
            .filter(Event.source_system == source_system)
            .order_by(Event.start_time_utc.desc())
            .limit(limit)
            .all()
        )

def get_missing_famly_event_ids() -> List[int]:
    """
    Compute Famly event IDs that are not present in Baby Connect.
    """
    prefs = get_sync_preferences()
    allowed_types = {
        value.strip().lower()
        for value in prefs.get("include_types", SYNC_INCLUDE_DEFAULT)
        if isinstance(value, str) and value.strip()
    } or {value for value in SYNC_INCLUDE_DEFAULT}

    def _canonical_sync_type(event: Event) -> str:
        base = (event.event_type or "").strip().lower()
        if base in ("meals", "meal"):
            return "solid"
        if base in ("nappy change", "diaper"):
            return "nappy"
        if base in ("signed in", "sign in", "signed out", "sign out"):
            return "message"
        return base or ""

    with get_session() as session:
        famly_events = (
            session.query(Event)
            .filter(Event.source_system == "famly")
            .order_by(Event.start_time_utc.desc())
            .all()
        )
        baby_events = (
            session.query(Event)
            .filter(Event.source_system == "baby_connect")
            .all()
        )
        ignored_fingerprints = _get_ignored_fingerprints(session)

    baby_fingerprints = {
        ev.fingerprint
        for ev in baby_events
        if isinstance(ev.fingerprint, str) and ev.fingerprint.strip()
    }
    missing_ids: List[int] = []
    for ev in famly_events:
        if not ev.fingerprint:
            continue
        if ev.fingerprint in ignored_fingerprints:
            continue
        canonical_type = _canonical_sync_type(ev)
        if canonical_type and canonical_type not in allowed_types:
            continue
        if ev.fingerprint not in baby_fingerprints:
            missing_ids.append(ev.id)
    return missing_ids

def _compute_babyconnect_days(days_back: int) -> int:
    today = datetime.utcnow().date()
    with get_session() as session:
        latest = (
            session.query(Event)
            .filter(Event.source_system == "famly")
            .order_by(Event.start_time_utc.desc())
            .first()
        )
    if not latest:
        return days_back
    diff = (today - latest.start_time_utc.date()).days
    base_offset = max(diff, 0)
    return base_offset + max(days_back, 0)

def _recent_famly_dates(limit_days: int) -> list[str]:
    if limit_days <= 0:
        return []
    unique: list[str] = []
    with get_session() as session:
        famly_events = (
            session.query(Event)
            .filter(Event.source_system == "famly")
            .order_by(Event.start_time_utc.desc())
            .all()
        )
    for ev in famly_events:
        day = ev.start_time_utc.date().isoformat()
        if day not in unique:
            unique.append(day)
        if len(unique) >= limit_days:
            break
    return unique

def scrape_babyconnect_and_store(days_back: int = 0) -> List[Event]:
    """
    Scrape events from Baby Connect and persist them.
    """
    cred = get_credentials("baby_connect")
    if not cred:
        raise RuntimeError("No Baby Connect credentials configured.")

    allowed_dates = _recent_famly_dates(days_back + 1)
    effective_days = _compute_babyconnect_days(days_back)
    if allowed_dates:
        oldest_allowed = min(datetime.fromisoformat(day).date() for day in allowed_dates)
        diff = (datetime.utcnow().date() - oldest_allowed).days
        effective_days = max(effective_days, diff)

    client = BabyConnectClient(email=cred.email, password=cred.password_encrypted)
    start_progress("baby_connect", 0)
    set_progress_message("baby_connect", "Preparing Baby Connect scrape...")
    def _report(message: str) -> None:
        set_progress_message("baby_connect", message)

    raw_events: List[RawBabyConnectEvent] = client.login_and_scrape(
        days_back=effective_days,
        allowed_days=allowed_dates,
        progress_callback=_report,
    )
    normalised: List[Dict[str, Any]] = [normalise_babyconnect_event(r) for r in raw_events]
    set_progress_total("baby_connect", len(normalised))
    set_progress_message("baby_connect", "Storing Baby Connect events...")

    stored_events: List[Event] = []
    seen_fingerprints: set[str] = set()
    try:
        with get_session() as session:
            session.query(Event).filter(Event.source_system == "baby_connect").delete()
            session.flush()
            for ev in normalised:
                if allowed_dates:
                    raw_data = (ev.get("details_json") or {}).get("raw_data") or {}
                    day_iso = raw_data.get("day_date_iso")
                    if not day_iso and ev.get("start_time_utc"):
                        day_iso = ev["start_time_utc"].date().isoformat()
                    if day_iso not in allowed_dates:
                        continue
                fp = ev["fingerprint"]
                if fp in seen_fingerprints:
                    continue
                seen_fingerprints.add(fp)
                new_ev = Event(**ev)
                session.add(new_ev)
                session.flush()
                stored_events.append(new_ev)
                increment_progress("baby_connect")
    except Exception as exc:
        fail_progress("baby_connect", str(exc))
        clear_progress("baby_connect")
        raise
    else:
        finish_progress("baby_connect")
        clear_progress("baby_connect")

    return stored_events

def _infer_diaper_type(detail_lines: Iterable[str]) -> str:
    for line in detail_lines:
        lower = line.lower()
        if "bm + wet" in lower:
            return "bm_wet"
        if "bm" in lower:
            return "bm"
        if "dry" in lower:
            return "dry"
        if "wet" in lower:
            return "wet"
    return "wet"

def _event_to_baby_payload(event: Event) -> Dict[str, Any] | None:
    details = event.details_json or {}
    raw_data = details.get("raw_data") or {}
    detail_lines: List[str] = raw_data.get("detail_lines") or []
    note = raw_data.get("note") or details.get("raw_text")
    base = {
        "event_type": event.event_type.lower(),
        "start_time_utc": event.start_time_utc.isoformat(),
        "end_time_utc": event.end_time_utc.isoformat() if event.end_time_utc else None,
        "note": note,
        "summary": details.get("raw_text"),
        "raw_text": details.get("raw_text"),
        "raw_data": raw_data,
    }
    etype = base["event_type"]
    if "nappy" in etype or "diaper" in etype:
        base["event_type"] = "nappy"
        base["diaper_type"] = _infer_diaper_type(detail_lines)
        return base
    if "sleep" in etype:
        base["event_type"] = "sleep"
        return base
    if any(key in etype for key in ("solid", "meal", "food")):
        base["event_type"] = "solid"
        return base
    if "signed in" in etype or "signed out" in etype or "message" in etype:
        base["event_type"] = "message"
        lower_raw = (details.get("raw_text") or "").lower()
        lower_original = (raw_data.get("original_title") or "").lower()
        if "signed out" in etype or "signed out" in lower_raw or "signed out" in lower_original:
            msg = "Famly - Signed out of nursery"
        elif "signed in" in etype or "signed in" in lower_raw or "signed in" in lower_original:
            msg = "Famly - Signed in to nursery"
        else:
            msg = details.get("raw_text") or base["note"]
        base["message"] = msg
        base["note"] = msg
        base["summary"] = msg
        base["raw_text"] = msg
        return base
    return None

def create_babyconnect_entries(event_ids: List[int]) -> Dict[str, Any]:
    """
    Take Famly events by ID and create corresponding entries in Baby Connect.
    """
    if not event_ids:
        return {"status": "ok", "created": 0}

    cred = get_credentials("baby_connect")
    if not cred:
        raise RuntimeError("No Baby Connect credentials configured.")

    with get_session() as session:
        events = (
            session.query(Event)
            .filter(Event.id.in_(event_ids), Event.source_system == "famly")
            .all()
        )

    payloads = []
    for ev in events:
        payload = _event_to_baby_payload(ev)
        if payload:
            payloads.append(payload)

    if not payloads:
        return {"status": "ok", "created": 0}

    client = BabyConnectClient(email=cred.email, password=cred.password_encrypted)
    client.create_entries(payloads)

    refreshed_count = 0
    if payloads:
        try:
            recent_days = _recent_famly_dates(30)
            refresh_days_back = max(0, len(recent_days) - 1)
            refreshed = scrape_babyconnect_and_store(days_back=refresh_days_back)
            refreshed_count = len(refreshed)
        except Exception:
            refreshed_count = 0

    return {"status": "ok", "created": len(payloads), "refreshed": refreshed_count}


def set_event_ignore_flag(event_id: int, ignored: bool) -> Dict[str, Any]:
    with get_session() as session:
        event = session.get(Event, event_id)
        if not event or event.source_system != "famly":
            raise ValueError("Only Famly events can be ignored")
        existing = (
            session.query(IgnoredEvent)
            .filter(IgnoredEvent.fingerprint == event.fingerprint)
            .first()
        )
        if ignored:
            if not existing:
                session.add(IgnoredEvent(fingerprint=event.fingerprint))
        else:
            if existing:
                session.delete(existing)
        session.flush()
    return {"event_id": event_id, "ignored": ignored}
def sync_to_babyconnect() -> Dict[str, Any]:
    """
    Placeholder for the main sync operation.
    Actual Baby Connect automation needs to be implemented.
    """
    # TODO: implement Baby Connect write-side automation
    return {
        "status": "not_implemented",
        "message": "Sync to Baby Connect is not implemented yet.",
    }
