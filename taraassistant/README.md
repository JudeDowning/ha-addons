# Tara Assistant Home Assistant Add-on Wrapper

This add-on is a Home Assistant wrapper for the upstream Tara Assistant project.

Upstream project: https://github.com/TaraHome/taraassistant-public

This wrapper pulls and runs the prebuilt multi-arch image:

- `ghcr.io/judedowning/taraassistant:v0.1.0`

## Install in Home Assistant

1. In Home Assistant, go to **Settings -> Add-ons -> Add-on Store**.
2. Open the overflow menu and select **Repositories**.
3. Add this repository URL: `https://github.com/JudeDowning/ha-addons`.
4. Find **Tara Assistant** in the store and install it.
5. In add-on configuration, set `home_assistant_token` to a Home Assistant long-lived access token.
6. Start the add-on.
7. Open the UI from the add-on page using **Open Web UI** (Ingress).

## Persistence

Persistent storage for this add-on is mounted at:

- `/data`