from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from ..core.config import CORS_ORIGINS, BASE_DIR
from ..core.storage import init_db
from ..core.logging_setup import configure_logging
from .routes_status import router as status_router
from .routes_events import router as events_router
from .routes_sync import router as sync_router
from .routes_credentials import router as credentials_router
from .routes_settings import router as settings_router
from .routes_debug import router as debug_router
from .routes_homeassistant import router as homeassistant_router


configure_logging()

app = FastAPI(title="Famly to Baby Connect Sync")

# Init DB on startup
@app.on_event("startup")
def startup() -> None:
    init_db()

# CORS (mainly for dev; tighten for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(status_router, prefix="/api")
app.include_router(events_router, prefix="/api")
app.include_router(sync_router, prefix="/api")
app.include_router(credentials_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(debug_router, prefix="/api")
app.include_router(homeassistant_router, prefix="/api")

# Serve frontend (if built)
frontend_dist = BASE_DIR / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
