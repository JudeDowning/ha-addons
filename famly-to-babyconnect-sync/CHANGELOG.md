# Changelog

## 1.0.8
- Improved diaper type mapping so Famly Wet&BM entries sync to BM + Wet in Baby Connect.

## 1.0.7
- Added live sync progress updates so the UI counter increments as Baby Connect entries are written.

## 1.0.6
- Added Home Assistantâ€“friendly status (`/api/homeassistant/status`) and sync run (`/api/homeassistant/run`) endpoints so automations can monitor progress and trigger the latest-day scrape/sync.
- Documented the new endpoints including rest_command/sensor examples for the HA addon README.

## 1.0.5
- Added multi select functionality to allow multiple specified entries to be pushed into Baby Connect instead of just all missing or one by one

## 1.0.4
- Updated reporting in UI to show actual scrape steps, similar to the logs rather than "Scraping"

## 1.0.3
- Fixed broken code in 1.0.2

## 1.0.2
- Changed the timeout detection for Famly scraping

## 1.0.1
- Added a refresh button to UI

## 1.0.0
- First stable and fully operational release


