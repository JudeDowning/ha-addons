from fastapi import APIRouter
from sqlalchemy import func

from ..core.storage import get_session
from ..core.models import Credential, Event

router = APIRouter(tags=["status"])

@router.get("/status")
def get_status():
    """
    Return a lightweight status snapshot for the dashboard.
    """
    with get_session() as session:
        famly_cred = (
            session.query(Credential)
            .filter(Credential.service_name == "famly")
            .first()
        )
        bc_cred = (
            session.query(Credential)
            .filter(Credential.service_name == "baby_connect")
            .first()
        )
        famly_events_count = (
            session.query(Event)
            .filter(Event.source_system == "famly")
            .count()
        )
        bc_events_count = (
            session.query(Event)
            .filter(Event.source_system == "baby_connect")
            .count()
        )
        famly_last_scrape = (
            session.query(func.max(Event.created_at))
            .filter(Event.source_system == "famly")
            .scalar()
        )
        bc_last_scrape = (
            session.query(func.max(Event.created_at))
            .filter(Event.source_system == "baby_connect")
            .scalar()
        )

    return {
        "famly": {
            "has_credentials": bool(famly_cred),
            "email": famly_cred.email if famly_cred else None,
            "last_connected_at": famly_cred.updated_at.isoformat() if famly_cred and famly_cred.updated_at else None,
            "last_scraped_at": famly_last_scrape.isoformat() if famly_last_scrape else None,
        },
        "baby_connect": {
            "has_credentials": bool(bc_cred),
            "email": bc_cred.email if bc_cred else None,
            "last_connected_at": bc_cred.updated_at.isoformat() if bc_cred and bc_cred.updated_at else None,
            "last_scraped_at": bc_last_scrape.isoformat() if bc_last_scrape else None,
        },
        "counts": {
            "famly_events": famly_events_count,
            "baby_connect_events": bc_events_count,
        },
    }
