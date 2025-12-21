FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

ENV PYTHONUNBUFFERED=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000 \
    HEADLESS=true \
    DATA_DIR=/data \
    DB_PATH=/data/db.sqlite \
    FAMLY_PROFILE_DIR=/data/famly-profile \
    BABYCONNECT_PROFILE_DIR=/data/babyconnect-profile \
    LOG_DIR=/data/logs \
    LOG_FILE=/data/logs/famly_sync.log \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium

COPY backend ./backend
COPY frontend/dist ./frontend/dist
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && mkdir -p /data

VOLUME ["/data"]
EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
