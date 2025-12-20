# Famly → Baby Connect Sync  
Home Assistant Add-on & Docker Service  
![Project Stage: Alpha](https://img.shields.io/badge/stage-alpha-orange)
![Home Assistant Add-on](https://img.shields.io/badge/Home%20Assistant-Addon-41BDF5)
![Architecture](https://img.shields.io/badge/amd64-arm64-blue)

Automatically synchronise nursery activity logs from **Famly** into **Baby Connect**.  
This add-on uses Playwright browser automation to scrape events from Famly, normalise them, and recreate missing entries inside Baby Connect — all through an intuitive web dashboard built into Home Assistant.

> **Status:** Alpha — UI, selectors, and sync behaviour are still evolving.

## ⭐ Features

- Automated Famly → Baby Connect event sync  
- Headless Playwright scraping + Baby Connect form submission  
- Unified event model (meals, nappies/diapers, sleep, sign-in/out, etc.)  
- Detects missing entries and offers one-click “Sync All”  
- Home Assistant Ingress support — fully integrated UI  
- SQLite persistence under `/data` (events, credentials, mappings)  
- Built-in dashboard for:
  - Credential management (Famly + Baby Connect)
  - Event comparison (side-by-side)
  - Event mapping configuration
  - Manual sync and bulk sync actions
- Also available as a standalone Docker container  

## 📘 About API Access

This project uses **browser automation** because neither platform currently offers public APIs.

I have formally requested API access from both **Famly** and **Baby Connect**.  
Both companies responded confirming:

> **They do not offer public API access at this time, and may not provide it in the future.**

If official APIs ever become available, this project will migrate away from scraping.

## 📦 Installation (Home Assistant Add-on)

### Option A — Add Repository (recommended)

1. In Home Assistant, go to **Settings → Add-ons → Add-on Store**
2. Click **⋮ → Repositories**
3. Add your GitHub repository URL
4. Locate **Famly → Baby Connect Sync**
5. Install → Start
6. Open the dashboard via the sidebar (Ingress)

### Option B — Manual installation

Place the add-on folder into:

```
/addons/famly_to_babyconnect_sync/
```

Then install via the HA Add-on Store.

## 🖥️ Accessing the UI (Ingress)

- Accessible from the **Home Assistant sidebar**
- No ports or networking config required
- Fully proxied & authenticated by Home Assistant
- All settings stored internally in `/data`

If the port is exposed externally, secure it behind authentication.

## 🔑 Credentials & Settings

All configuration is performed **within the UI**, not YAML.

You can configure:

- Famly email + password  
- Baby Connect email + password  
- Event mappings  
- Sync preferences  

Stored securely inside `/data/db.sqlite`.

## 🐳 Quick Start (Standalone Docker)

```
docker build -t famly-sync famly_to_babyconnect_sync

docker run   -p 8000:8000   -v "$(pwd)/data:/data"   famly-sync
```

Then open:  
`http://localhost:8000`

## 🔁 Home Assistant Automations & REST Commands

### Example `rest_command` entries

```yaml
rest_command:
  famly_scrape:
    url: "http://ADDON_HOST:ADDON_PORT/api/scrape/famly?days_back=0"
    method: POST

  babyconnect_scrape:
    url: "http://ADDON_HOST:ADDON_PORT/api/scrape/baby_connect?days_back=0"
    method: POST

  famly_sync_missing:
    url: "http://ADDON_HOST:ADDON_PORT/api/sync/missing"
    method: POST

  nursery_sync_last_day:
    url: "http://ADDON_HOST:ADDON_PORT/api/homeassistant/run"
    method: POST
    timeout: 120
```

### Example nightly automation

```yaml
automation:
  - alias: "Nightly Famly → Baby Connect Sync"
    trigger:
      - platform: time
        at: "22:30:00"
    action:
      - service: rest_command.nursery_sync_last_day
```

> For Supervisor calls (including the `rest_command` above), include: `Authorization: Bearer ${SUPERVISOR_TOKEN}`

### Example sensor for the last sync

```yaml
sensor:
  - platform: rest
    name: "Nursery Sync Status"
    resource: "http://ADDON_HOST:ADDON_PORT/api/homeassistant/status"
    scan_interval: 300
    value_template: "{{ value_json.last_sync_at or 'unknown' }}"
    json_attributes:
      - sync_status
      - sync_in_progress
      - famly_last_scrape_at
      - baby_connect_last_scrape_at
      - progress
    headers:
      Authorization: Bearer ${SUPERVISOR_TOKEN}
```

The `status` endpoint exposes `last_sync_at`, the most recent Famly/Baby Connect scrapes, and `progress` metadata so you can surface whether a sync is running or idle inside Home Assistant.

## 🧱 Architecture Overview

### Backend (FastAPI + Playwright)

- Scrapes Famly  
- Creates events in Baby Connect  
- Normalises & fingerprints events  
- Persists to SQLite

### Frontend (React + Vite)

- Credentials UI  
- Event comparison  
- Sync controls  
- Mapping editor  

### Home Assistant Add-on Integration

- Ingress UI  
- Persistent `/data`  
- Bundled frontend + backend  

## 📅 Roadmap

- Multi-child support  
- Conflict resolution UI  
- Automatic scheduled sync  
- Improved mapping tools  
- HA service schema  

## 🔐 Disclaimer

This project is **not affiliated** with Famly or Baby Connect.  
It uses browser automation because **no public API exists**.  
Future updates to either platform may break selectors.

## 📄 License

MIT License  
