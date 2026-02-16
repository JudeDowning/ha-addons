# HA Add-ons

This repository is the umbrella for my Home Assistant add-ons. Each add-on gets its own directory and documentation so I can publish multiple packages from a single `ha-addons` repo.

## Add-ons

- `famly-to-babyconnect-sync/` - Famly to Baby Connect Sync add-on (Home Assistant + standalone Docker). See [its README](famly-to-babyconnect-sync/README.md).
- `taraassistant/` - Tara Assistant Home Assistant add-on wrapper. See [its README](taraassistant/README.md).

## Development

1. `cd` into the add-on directory you want to work on.
2. Follow that add-on's README for local build/run/development instructions.
3. Update root repository metadata (`repository.json` and `repository.yaml`) when needed.

## Integrations companion

Home Assistant integrations live in a separate repo: [https://github.com/JudeDowning/ha-integrations](https://github.com/JudeDowning/ha-integrations).