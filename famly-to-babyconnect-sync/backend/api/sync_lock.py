from threading import Lock

from fastapi import HTTPException

_SYNC_LOCK = Lock()


def acquire_sync_lock() -> None:
    if not _SYNC_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Sync already in progress. Please wait for it to finish.")


def release_sync_lock() -> None:
    if _SYNC_LOCK.locked():
        _SYNC_LOCK.release()
