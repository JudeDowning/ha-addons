import os
from pathlib import Path

# Base directory for the project (inside the container or local checkout)
BASE_DIR = Path(os.getenv("BASE_DIR", Path(__file__).resolve().parents[2]))
# Dedicated data directory; defaults to <base>/data but can be overridden
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))

# Database path (override in container/HA with DB_PATH=/data/db.sqlite)
DB_PATH = Path(os.getenv("DB_PATH", DATA_DIR / "db.sqlite"))

# Playwright user data directories (persist browser sessions & cookies)
FAMLY_PROFILE_DIR = Path(os.getenv("FAMLY_PROFILE_DIR", DATA_DIR / "famly-profile"))
FAMLY_CHILD_ID = os.getenv("FAMLY_CHILD_ID", "4b0ce49e-6393-4c65-97ee-9c80ec71b177").strip() or ""
BABYCONNECT_PROFILE_DIR = Path(os.getenv("BABYCONNECT_PROFILE_DIR", DATA_DIR / "babyconnect-profile"))

# Headless mode for Playwright (set to "false" in dev to see the browser)
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"

# Uvicorn / server config
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))

# CORS origins for the frontend in dev; in production this can be more strict
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

# Simple helper for logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = Path(os.getenv("LOG_DIR", DATA_DIR / "logs"))
LOG_FILE = Path(os.getenv("LOG_FILE", LOG_DIR / "famly_sync.log"))
