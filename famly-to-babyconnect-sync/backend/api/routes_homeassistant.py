import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func

from ..core.models import Event
from ..core.progress_state import get_progress_snapshot
from ..core.storage import get_session
from ..core.sync_service import (
    create_babyconnect_entries as create_entries_service,
    get_missing_famly_event_ids,
    scrape_famly_and_store,
)

router = APIRouter(tags=["homeassistant"])
logger = logging.getLogger(__name__)


def _format_timestamp(value: Any) -> str | None:
    if not value:
        return None
    return value.isoformat()


def _latest_event_timestamp(source_system: str) -> Any:
    with get_session() as session:
        return (
            session.query(func.max(Event.created_at))
            .filter(Event.source_system == source_system)
            .scalar()
        )


@router.get("/homeassistant/status")
def homeassistant_status():
    """
    Provide a lightweight Home Assistant-friendly snapshot for sensors.
    """
    progress_snapshot = get_progress_snapshot()
    in_progress = any(
        state.get("status") == "running"
        for state in progress_snapshot.values()
    )
    famly_last = _latest_event_timestamp("famly")
    baby_last = _latest_event_timestamp("baby_connect")
    last_sync_at = baby_last or famly_last
    return {
        "last_sync_at": _format_timestamp(last_sync_at),
        "famly_last_scrape_at": _format_timestamp(famly_last),
        "baby_connect_last_scrape_at": _format_timestamp(baby_last),
        "sync_in_progress": in_progress,
        "sync_status": "running" if in_progress else "idle",
        "progress": progress_snapshot,
    }


@router.post("/homeassistant/run")
def homeassistant_run(
    days_back: int = Query(
        1,
        ge=0,
        le=7,
        description="How many previous days of Famly history to scrape (defaults to last day).",
    )
):
    """
    Run a trimmed Famly scrape + sync process for Home Assistant automations.
    """
    logger.info("Home Assistant sync run requested (days_back=%s)", days_back)
    try:
        events = scrape_famly_and_store(days_back=days_back)
    except Exception as exc:
        logger.exception("Home Assistant run failed during Famly scrape")
        raise HTTPException(status_code=500, detail=f"Famly scrape failed: {exc}")

    try:
        missing_ids = get_missing_famly_event_ids()
    except Exception as exc:
        logger.exception("Home Assistant run failed while determining missing events")
        raise HTTPException(status_code=500, detail=f"Failed to determine missing events: {exc}")

    response: dict[str, Any] = {
        "scraped_count": len(events),
        "days_back": days_back,
        "missing_event_ids": missing_ids,
        "synced_event_ids": [],
        "status": "ok",
        "created": 0,
    }

    if missing_ids:
        try:
            result = create_entries_service(missing_ids)
        except Exception as exc:
            logger.exception("Home Assistant run failed while syncing missing events")
            raise HTTPException(status_code=500, detail=f"Syncing missing events failed: {exc}")
        response.update(result)
        response.setdefault("synced_event_ids", missing_ids)
    return response
