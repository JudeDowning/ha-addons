import json
from pathlib import Path
from typing import Any, Dict, List

from .config import DATA_DIR

SETTINGS_DIR = DATA_DIR
SETTINGS_PATH = SETTINGS_DIR / "settings.json"
SYNC_INCLUDE_DEFAULT = [
    "solid",
    "nappy",
    "sleep",
    "message",
    "bottle",
    "medicine",
    "temperature",
    "bath",
]
DEFAULT_SETTINGS: Dict[str, Any] = {
    "sync_preferences": {
        "include_types": SYNC_INCLUDE_DEFAULT.copy(),
    }
}

_settings_cache: Dict[str, Any] | None = None


def _ensure_loaded() -> Dict[str, Any]:
    global _settings_cache
    if _settings_cache is not None:
        return _settings_cache

    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    if SETTINGS_PATH.exists():
        try:
            with SETTINGS_PATH.open("r", encoding="utf-8") as f:
                _settings_cache = json.load(f)
        except json.JSONDecodeError:
            _settings_cache = DEFAULT_SETTINGS.copy()
    else:
        _settings_cache = DEFAULT_SETTINGS.copy()
        _save()

    changed = False
    if "sync_preferences" not in _settings_cache or not isinstance(
        _settings_cache.get("sync_preferences"), dict
    ):
        _settings_cache["sync_preferences"] = DEFAULT_SETTINGS["sync_preferences"].copy()
        changed = True
    prefs = _settings_cache["sync_preferences"]
    include_types = prefs.get("include_types")
    if not isinstance(include_types, list) or not include_types:
        prefs["include_types"] = SYNC_INCLUDE_DEFAULT.copy()
        changed = True
    if changed:
        _save()

    return _settings_cache


def _save() -> None:
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    data = _settings_cache or DEFAULT_SETTINGS.copy()
    with SETTINGS_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_settings() -> Dict[str, Any]:
    return _ensure_loaded()


def get_sync_preferences() -> Dict[str, Any]:
    data = _ensure_loaded()
    prefs = data.get("sync_preferences", {})
    include_types = prefs.get("include_types") or []
    if not isinstance(include_types, list) or not include_types:
        include_types = SYNC_INCLUDE_DEFAULT.copy()
        data["sync_preferences"] = {"include_types": include_types}
        _save()
    return {"include_types": include_types.copy()}


def set_sync_preferences(include_types: List[str]) -> Dict[str, Any]:
    cleaned = sorted({value.strip().lower() for value in include_types if value.strip()})
    if not cleaned:
        cleaned = SYNC_INCLUDE_DEFAULT.copy()
    data = _ensure_loaded()
    data["sync_preferences"] = {"include_types": cleaned}
    _save()
    return {"include_types": cleaned.copy()}
