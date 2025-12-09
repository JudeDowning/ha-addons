from typing import List

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from ..core.sync_service import (
    get_events,
    get_missing_famly_event_ids,
    set_event_ignore_flag,
)
from ..core.storage import get_session
from ..core.models import IgnoredEvent, Event

router = APIRouter(tags=["events"])

class EventOut(BaseModel):
    id: int
    source_system: str
    child_name: str
    event_type: str
    fingerprint: str
    start_time_utc: str
    end_time_utc: str | None = None
    matched: bool = False
    summary: str | None = None
    raw_text: str | None = None
    raw_data: dict | None = None
    ignored: bool = False

class IgnorePayload(BaseModel):
    ignored: bool

def _ignored_fingerprints() -> set[str]:
    with get_session() as session:
        return {
            row[0]
            for row in session.query(IgnoredEvent.fingerprint).all()
        }

@router.get("/events", response_model=List[EventOut])
def list_events(source: str = Query(..., regex="^(famly|baby_connect)$")):
    """
    Return the most recent events for the given source system.

    This is used to populate the left (Famly) and right (Baby Connect) columns in the UI.
    """
    events = get_events(source)
    ignored = _ignored_fingerprints()
    # TODO: mark matched events based on SyncLink table
    output: List[EventOut] = []
    for e in events:
        output.append(EventOut(
            id=e.id,
            source_system=e.source_system,
            child_name=e.child_name,
            event_type=e.event_type,
            fingerprint=e.fingerprint,
            start_time_utc=e.start_time_utc.isoformat(),
            end_time_utc=e.end_time_utc.isoformat() if e.end_time_utc else None,
            matched=False,  # placeholder until matching is wired
            summary=e.details_json.get("raw_text") if isinstance(e.details_json, dict) else None,
            raw_text=e.details_json.get("raw_text") if isinstance(e.details_json, dict) else None,
            raw_data=e.details_json.get("raw_data") if isinstance(e.details_json, dict) else None,
            ignored=e.fingerprint in ignored,
        ))
    return output

@router.get("/events/missing")
def list_missing_events():
    missing_ids = get_missing_famly_event_ids()
    return {"missing_event_ids": missing_ids, "count": len(missing_ids)}

@router.post("/events/{event_id}/ignore")
def toggle_ignore_event(event_id: int, payload: IgnorePayload):
    try:
        result = set_event_ignore_flag(event_id, payload.ignored)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result
