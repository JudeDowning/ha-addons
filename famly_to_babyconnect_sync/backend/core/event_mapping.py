import json
from json import JSONDecodeError
from pathlib import Path
from typing import Dict, List

from .config import DATA_DIR

CONFIG_PATH = DATA_DIR / "event_mapping.json"

DEFAULT_EVENT_MAPPING: Dict[str, str] = {
    "meals": "Solid",
    "nappy": "Nappy",
    "sleep": "Sleep",
    "signed in": "Message",
    "signed out": "Message",
}
CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

# Canonical Famly event labels we expect to configure
CANONICAL_FAMLY_TYPES = [
    "meals",
    "nappy",
    "sleep",
    "signed in",
    "signed out",
    "ill",
]

# Simple keyword fallbacks so common Famly labels still align with canonical names
FALLBACK_KEYWORDS = {
    "meals": "meals",
    "meal": "meals",
    "breakfast": "meals",
    "lunch": "meals",
    "tea": "meals",
    "nappy": "nappy",
    "sleep": "sleep",
    "signed in": "signed in",
    "signed out": "signed out",
    "sick": "ill",
    "ill": "ill",
}


def _load_mapping() -> Dict[str, str]:
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(DEFAULT_EVENT_MAPPING, indent=2), encoding="utf-8")
        return DEFAULT_EVENT_MAPPING.copy()

    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not data:
            raise JSONDecodeError("invalid mapping", "", 0)
        cleaned = {str(k): str(v) for k, v in data.items() if str(k)}
    except JSONDecodeError:
        cleaned = DEFAULT_EVENT_MAPPING.copy()
        CONFIG_PATH.write_text(json.dumps(cleaned, indent=2), encoding="utf-8")
    return cleaned


_current_map: Dict[str, str] = _load_mapping()


def get_event_mapping() -> dict[str, str]:
    return _current_map.copy()


def set_event_mapping(mapping: dict[str, str]) -> None:
    global _current_map
    cleaned = {str(k).strip(): str(v).strip() for k, v in mapping.items() if str(k).strip()}
    _current_map = cleaned
    CONFIG_PATH.write_text(json.dumps(_current_map, indent=2), encoding="utf-8")


def get_known_famly_types() -> List[str]:
    known: Dict[str, str] = {}
    for label in CANONICAL_FAMLY_TYPES:
        known[label.lower()] = label

    for key in _current_map.keys():
        cleaned = key.strip()
        if not cleaned:
            continue
        lower = cleaned.lower()
        known.setdefault(lower, cleaned)

    return sorted(known.values())


def canonicalise_famly_label(raw: str) -> str | None:
    lower = raw.lower()
    for key, target in FALLBACK_KEYWORDS.items():
        if key in lower:
            return target
    return None


def normalize_famly_title(title: str) -> str:
    mapping = get_event_mapping()
    mapped = mapping.get(title) or mapping.get(title.lower())
    if mapped:
        return mapped

    lower = title.lower()

    for key, value in mapping.items():
        if key.lower() in lower:
            return value

    for key, value in FALLBACK_KEYWORDS.items():
        if key in lower:
            return value

    return title
