from fastapi import APIRouter, Query, HTTPException, status

from ..core.storage import get_session
from ..core.models import Event

router = APIRouter(tags=["debug"])


def _serialize_event(event: Event) -> dict:
    return {
        "id": event.id,
        "source_system": event.source_system,
        "child_name": event.child_name,
        "event_type": event.event_type,
        "fingerprint": event.fingerprint,
        "start_time_utc": event.start_time_utc.isoformat(),
        "end_time_utc": event.end_time_utc.isoformat() if event.end_time_utc else None,
        "details_json": event.details_json,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


@router.get("/debug/events")
def list_events(source: str = Query(..., regex="^(famly|baby_connect)$"), limit: int = 200):
    try:
        limit = max(1, min(limit, 1000))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid limit")

    with get_session() as session:
        events = (
            session.query(Event)
            .filter(Event.source_system == source)
            .order_by(Event.start_time_utc.desc())
            .limit(limit)
            .all()
        )
    return {
        "source": source,
        "count": len(events),
        "events": [_serialize_event(ev) for ev in events],
    }


@router.post("/debug/events/clear", status_code=status.HTTP_204_NO_CONTENT)
def clear_events():
    """
    Delete all scraped Famly/Baby Connect events without touching credentials
    or mapping preferences.
    """
    with get_session() as session:
        session.query(Event).delete()
        session.commit()
