# Changelog

## 1.0.12
- Added support for syncing Famly `Garden` entries into Baby Connect `Activity` as `Playing with Others`, including note/text mapping and verification support.

## 1.0.11
- Added persistent sync claims and shared sync locking to reduce duplicate Baby Connect posts across overlapping or repeated sync attempts.
- Changed Baby Connect write confirmation to rescrape the feed and only treat entries as synced once they are visible on the page.
- Fixed the Famly scraper after a site markup change by updating event extraction and child-profile navigation selectors.

## 1.0.10
- Fixed a Famly scrape crash caused by duplicate event fingerprints in the same run (UNIQUE constraint failed: events.source_system, events.fingerprint).
- Added in-run deduplication for Famly events before database insert to keep scrape runs idempotent.

## 1.0.9
- Replaced the blocking progress modal with an inline status card that updates live.
- Added a "Scrape + Sync All" button to run the combined flow from the UI.


## 1.0.8
- Improved diaper type mapping so Famly Wet&BM entries sync to BM + Wet in Baby Connect.

## 1.0.7
- Added live sync progress updates so the UI counter increments as Baby Connect entries are written.

## 1.0.6
- Added Home Assistant–friendly status (`/api/homeassistant/status`) and sync run (`/api/homeassistant/run`) endpoints so automations can monitor progress and trigger the latest-day scrape/sync.
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



