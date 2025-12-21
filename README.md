# HA Add-ons

This repository is the umbrella for my Home Assistant add-ons. Each add-on gets its own directory, documentation, and build instructions so I can publish multiple packages from a single `ha-addons` repo.

## Add-ons

- `famly-to-babyconnect-sync/` – Famly → Baby Connect Sync add-on (Home Assistant + standalone Docker). See [its README](famly-to-babyconnect-sync/README.md) for install, automation, and API details.

## Development

1. `cd famly-to-babyconnect-sync`
2. Use the documentation there to build (`docker build -t ...`), run (`docker run ...`), or develop the FastAPI/React source.
3. Update `repository.json` at the repo root when the add-on metadata changes so Home Assistant sees the latest version.

## Integrations companion

Home Assistant integrations live in a separate repo: [https://github.com/JudeDowning/ha-integrations](https://github.com/JudeDowning/ha-integrations). That repo hosts custom components that can consume the add-on’s REST endpoints, sensors, and services.
