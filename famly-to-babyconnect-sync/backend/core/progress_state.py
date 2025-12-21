from __future__ import annotations

from datetime import datetime
from threading import Lock
from typing import Dict, Any

_PROGRESS: Dict[str, Dict[str, Any]] = {}
_LOCK = Lock()


def _now() -> str:
    return datetime.utcnow().isoformat()


def start_progress(service: str, total: int) -> None:
    with _LOCK:
        _PROGRESS[service] = {
            "service": service,
            "total": max(total, 0),
            "processed": 0,
            "status": "running",
            "started_at": _now(),
            "updated_at": _now(),
            "message": None,
        }


def increment_progress(service: str, step: int = 1) -> None:
    with _LOCK:
        data = _PROGRESS.get(service)
        if not data:
            return
        total = data.get("total", 0)
        processed = min(total, data.get("processed", 0) + max(step, 0))
        data["processed"] = processed
        data["updated_at"] = _now()


def finish_progress(service: str) -> None:
    with _LOCK:
        data = _PROGRESS.get(service)
        if not data:
            return
        data["processed"] = data.get("total", data.get("processed", 0))
        data["status"] = "done"
        data["finished_at"] = _now()
        data["updated_at"] = data["finished_at"]


def fail_progress(service: str, error: str | None = None) -> None:
    with _LOCK:
        data = _PROGRESS.get(service)
        if not data:
            return
        data["status"] = "error"
        if error:
            data["error"] = error
        data["finished_at"] = _now()
        data["updated_at"] = data["finished_at"]


def set_progress_total(service: str, total: int) -> None:
    with _LOCK:
        data = _PROGRESS.get(service)
        if not data:
            return
        data["total"] = max(total, 0)
        data["updated_at"] = _now()


def set_progress_message(service: str, message: str) -> None:
    with _LOCK:
        data = _PROGRESS.get(service)
        if not data:
            return
        data["message"] = message
        data["updated_at"] = _now()


def clear_progress(service: str) -> None:
    with _LOCK:
        _PROGRESS.pop(service, None)


def get_progress_snapshot() -> Dict[str, Dict[str, Any]]:
    with _LOCK:
        return {key: value.copy() for key, value in _PROGRESS.items()}
