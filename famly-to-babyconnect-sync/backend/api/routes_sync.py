import logging
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from ..core.sync_service import (
    scrape_famly_and_store,
    scrape_babyconnect_and_store,
    sync_to_babyconnect,
    create_babyconnect_entries as create_entries_service,
    get_missing_famly_event_ids,
)
from ..core.progress_state import get_progress_snapshot

router = APIRouter(tags=["sync"])
logger = logging.getLogger(__name__)

class CreateEntriesPayload(BaseModel):
    event_ids: list[int]


@router.get("/scrape/progress")
def scrape_progress():
    """
    Return the latest scrape progress snapshot for Famly/Baby Connect.
    """
    return get_progress_snapshot()

@router.post("/scrape/famly")
def scrape_famly(days_back: int = Query(0, ge=0, le=7, description="Number of previous days to include")):
    """
    Trigger a scrape of Famly events and persist them.

    Returns a simple summary (e.g. count of events).
    """
    logger.info("API: scrape Famly invoked days_back=%s", days_back)
    try:
        events = scrape_famly_and_store(days_back=days_back)
    except Exception as exc:
        logger.exception("API: Famly scrape failed")
        raise HTTPException(status_code=500, detail=str(exc))
    return {
        "status": "ok",
        "scraped_count": len(events),
        "days_back": days_back,
    }

@router.post("/scrape/baby_connect")
def scrape_baby_connect(days_back: int = Query(0, ge=0, le=14, description="Number of previous days to include")):
    logger.info("API: scrape Baby Connect invoked days_back=%s", days_back)
    try:
        events = scrape_babyconnect_and_store(days_back=days_back)
    except Exception as exc:
        logger.exception("API: Baby Connect scrape failed")
        raise HTTPException(status_code=500, detail=str(exc))
    return {
        "status": "ok",
        "scraped_count": len(events),
        "days_back": days_back,
    }

@router.post("/sync")
def sync():
    """
    Trigger synchronisation of unsynced Famly events into Baby Connect.

    Currently a stub until BabyConnectClient is fully implemented.
    """
    result = sync_to_babyconnect()
    return result

@router.post("/sync/baby_connect/entries")
def create_babyconnect_entries(payload: CreateEntriesPayload):
    logger.info("API: creating %d baby connect entries", len(payload.event_ids))
    try:
        result = create_entries_service(payload.event_ids)
        response = dict(result)
        response.setdefault("synced_event_ids", payload.event_ids)
        return response
    except Exception as exc:
        logger.exception("API: failed to create baby connect entries")
        raise HTTPException(status_code=500, detail=str(exc))

@router.post("/sync/missing")
def sync_missing_entries():
    """
    Compute missing Famly events and create them in Baby Connect.
    """
    try:
        missing_ids = get_missing_famly_event_ids()
    except Exception as exc:
        logger.exception("API: failed to compute missing events")
        raise HTTPException(status_code=500, detail=str(exc))
    if not missing_ids:
        return {"status": "ok", "created": 0, "missing_event_ids": []}
    try:
        result = create_entries_service(missing_ids)
        response = dict(result)
        response.setdefault("status", "ok")
        response["missing_event_ids"] = missing_ids
        response.setdefault("synced_event_ids", missing_ids)
        return response
    except Exception as exc:
        logger.exception("API: failed to sync missing entries")
        raise HTTPException(status_code=500, detail=str(exc))
