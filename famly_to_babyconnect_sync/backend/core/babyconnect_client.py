"""
Baby Connect client (automation).
---------------------------------

This module uses Playwright to:

- Log into Baby Connect
- Open the appropriate activity entry forms (meal, nap, nappy, etc.)
- Fill them based on a normalised event
- Submit the forms to create events as if a user did it manually
"""

from __future__ import annotations

from typing import Callable, Dict, Any, List
import logging
import re
from datetime import datetime, timedelta, date

from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeoutError

from .config import BABYCONNECT_PROFILE_DIR, HEADLESS
from .normalisation import RawBabyConnectEvent

BABYCONNECT_LOGIN_URL = "https://app.babyconnect.com/login"
BABYCONNECT_HOME_URL = "https://app.babyconnect.com/home2"

# Login selectors (confirmed)
BC_EMAIL_SELECTOR = "#username"
BC_PASSWORD_SELECTOR = "#password"
BC_LOGIN_BUTTON_SELECTOR = "#save"

CHILD_NAME_SELECTOR = ".name a"


# Today’s status list selectors
STATUS_LIST_CONTAINER = "#status_list_container"
STATUS_LIST_WRAP = "#status_list_wrap"
STATUS_LIST_SELECTOR = "#status_list"
BC_EVENT_SELECTOR = ".st"
BC_EVENT_ICON_SELECTOR = ".st_img img"
BC_EVENT_TITLE_SELECTOR = ".st_body .st_tl"
BC_EVENT_NOTE_SELECTOR = ".st_body .st_note"
BC_POSTED_BY_CONTAINER_SELECTOR = ".posted_by"
DATE_DISPLAY_SELECTOR = "#kid_date"
DATE_LEFT_SELECTOR = "#dateLeft"

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], None]

class BabyConnectClient:
    def __init__(self, email: str, password: str) -> None:
        self.email = email
        self.password = password

    def login_and_scrape(
        self,
        days_back: int = 0,
        allowed_days: list[str] | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> List[RawBabyConnectEvent]:
        events: List[RawBabyConnectEvent] = []
        allowed_set = {day for day in (allowed_days or []) if day}

        def _report(message: str) -> None:
            if progress_callback:
                progress_callback(message)

        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=str(BABYCONNECT_PROFILE_DIR),
                headless=HEADLESS,
            )
            page = browser.new_page()

            # 1. Login (if session not already stored)
            _report("Logging in to Baby Connect...")
            logger.info("BabyConnect: opening home page")
            page.goto(BABYCONNECT_HOME_URL, wait_until="networkidle")

            if "login" in page.url:
                logger.info("BabyConnect: redirected to login, performing login flow")
                page.wait_for_selector(BC_EMAIL_SELECTOR)
                page.fill(BC_EMAIL_SELECTOR, self.email)
                page.fill(BC_PASSWORD_SELECTOR, self.password)
                page.click(BC_LOGIN_BUTTON_SELECTOR)
                page.wait_for_load_state("networkidle")
                logger.info("BabyConnect: login complete, returning to home")
                page.goto(BABYCONNECT_HOME_URL, wait_until="networkidle")
            else:
                logger.info("BabyConnect: existing session active")

            page.wait_for_selector(DATE_DISPLAY_SELECTOR, timeout=10000)
            child_name = self._read_child_name(page) or "Baby Connect"

            collected_days = 0
            seen_dates: set[str] = set()
            _report("Collecting Baby Connect events...")

            while True:
                status_list = self._get_status_list(page)
                if not status_list:
                    logger.warning("BabyConnect: status list missing for current day")
                    break

                day_label, day_iso = self._get_current_day_info(page)
                if day_iso in seen_dates:
                    logger.info("BabyConnect: already collected date %s, stopping", day_iso)
                    break
                seen_dates.add(day_iso)

                if allowed_set and day_iso not in allowed_set:
                    logger.info("BabyConnect: skipping day %s (not requested)", day_iso)
                else:
                    daily_events = self._collect_events_for_day(
                        status_list=status_list,
                        child_name=child_name,
                        day_label=day_label,
                        day_iso=day_iso,
                    )
                    events.extend(daily_events)
                    logger.info("BabyConnect: collected %d events for %s", len(daily_events), day_label)
                    if allowed_set:
                        allowed_set.discard(day_iso)

                if allowed_set and not allowed_set:
                    logger.info("BabyConnect: collected all requested days")
                    break
                if collected_days >= days_back:
                    break

                if not self._go_to_previous_day(page, day_label):
                    break

                collected_days += 1

            browser.close()
            logger.info("BabyConnect: scraped %d events across %d days", len(events), len(seen_dates))
            _report(f"Collected {len(events)} Baby Connect events")

        return events

    def verify_login(self) -> None:
        """
        Lightweight login check used by the API test endpoint.
        """
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=str(BABYCONNECT_PROFILE_DIR),
                headless=HEADLESS,
            )
            page = browser.new_page()
            logger.info("BabyConnect: verifying login")
            page.goto(BABYCONNECT_HOME_URL, wait_until="networkidle")
            if "login" in page.url:
                page.wait_for_selector(BC_EMAIL_SELECTOR)
                page.fill(BC_EMAIL_SELECTOR, self.email)
                page.fill(BC_PASSWORD_SELECTOR, self.password)
                page.click(BC_LOGIN_BUTTON_SELECTOR)
                page.wait_for_load_state("networkidle")
                page.goto(BABYCONNECT_HOME_URL, wait_until="networkidle")
            page.wait_for_selector(DATE_DISPLAY_SELECTOR, timeout=10000)
            browser.close()
            logger.info("BabyConnect: login verification successful")

    def create_entries(self, entries: List[Dict[str, Any]]) -> None:
        """
        Create new entries inside Baby Connect based on the provided list.

        Each entry should contain at minimum an "event_type" key. Optional keys such as
        start_time_utc, end_time_utc, note, quantity, etc. will be used when filling the dialogs.
        """
        if not entries:
            logger.info("BabyConnect: no entries to create")
            return

        logger.info("BabyConnect: creating %d entries", len(entries))

        any_success = False

        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=str(BABYCONNECT_PROFILE_DIR),
                headless=HEADLESS,
            )
            page = browser.new_page()

            logger.info("BabyConnect: opening home page for entry creation")
            page.goto(BABYCONNECT_HOME_URL, wait_until="networkidle")

            if "login" in page.url:
                logger.info("BabyConnect: performing login before creating entries")
                page.wait_for_selector(BC_EMAIL_SELECTOR)
                page.fill(BC_EMAIL_SELECTOR, self.email)
                page.fill(BC_PASSWORD_SELECTOR, self.password)
                page.click(BC_LOGIN_BUTTON_SELECTOR)
                page.wait_for_load_state("networkidle")
                page.goto(BABYCONNECT_HOME_URL, wait_until="networkidle")

            page.wait_for_selector("#new_entries_panel", timeout=10000)

            for entry in entries:
                event_type = (entry.get("event_type") or "").lower()
                try:
                    logger.info("BabyConnect: creating entry type=%s payload=%s", event_type, entry)
                    if event_type in {"nappy", "diaper"}:
                        self._create_diaper_entry(page, entry)
                    elif event_type == "sleep":
                        self._create_sleep_entry(page, entry)
                    elif event_type in {"solid", "meal", "food"}:
                        self._create_solid_entry(page, entry)
                    elif event_type in {"message", "note"}:
                        self._create_message_entry(page, entry)
                    else:
                        logger.warning("BabyConnect: unsupported entry type %s", event_type)
                        continue
                    any_success = True
                except Exception:
                    logger.exception("BabyConnect: failed to create entry %s", entry)

            browser.close()

        if any_success:
            try:
                recent_days = _recent_famly_dates(30)
                refresh_days_back = max(0, len(recent_days) - 1)
                refreshed = scrape_babyconnect_and_store(days_back=refresh_days_back)
                refreshed_count = len(refreshed)
            except Exception:
                refreshed_count = 0
        else:
            refreshed_count = 0

        return {"status": "ok", "created": len(entries) if any_success else 0, "refreshed": refreshed_count}

    def _wait_for_overlay_clear(self, page: Page, timeout: int = 5000) -> None:
        """
        Ensure modal overlays are not blocking interactions.
        """
        try:
            page.wait_for_function(
                """() => {
                    const overlays = Array.from(document.querySelectorAll('.ui-widget-overlay'));
                    return overlays.every((el) => {
                        const style = window.getComputedStyle(el);
                        return style.visibility === 'hidden' || style.display === 'none' || el.offsetParent === null;
                    });
                }""",
                timeout=timeout,
            )
        except PlaywrightTimeoutError:
            logger.debug("BabyConnect: overlay still visible after waiting, continuing anyway")

    def _close_any_open_dialog(self, page: Page) -> None:
        """
        Close any existing modal dialog so the overlay disappears before opening a new one.
        """
        close_buttons = page.locator(".ui-dialog .ui-dialog-titlebar-close")
        if close_buttons.count():
            try:
                close_buttons.last.click()
                page.wait_for_timeout(200)
                last_dialog = page.locator(".ui-dialog").last
                try:
                    last_dialog.wait_for(state="detached", timeout=4000)
                except PlaywrightTimeoutError:
                    logger.debug("BabyConnect: previous dialog still attached after close attempt")
            except Exception:
                logger.debug("BabyConnect: error while closing prior dialog", exc_info=True)
        self._wait_for_overlay_clear(page)

    def _open_entry_dialog(self, page: Page, callback_fragment: str) -> Page:
        self._close_any_open_dialog(page)
        link = page.locator(f"#new_entries_panel a[href*='{callback_fragment}']").first
        link.scroll_into_view_if_needed()
        self._wait_for_overlay_clear(page)
        existing_dialogs = page.locator(".ui-dialog").count()
        link.click()
        new_dialog = page.locator(".ui-dialog").nth(existing_dialogs)
        try:
            new_dialog.wait_for(state="attached", timeout=6000)
            dialog = new_dialog
        except PlaywrightTimeoutError:
            dialog = page.locator(".ui-dialog").last
            logger.debug("BabyConnect: new dialog did not attach within window, falling back to last handle")
        try:
            dialog.wait_for(state="visible", timeout=8000)
        except PlaywrightTimeoutError:
            logger.debug("BabyConnect: dialog stayed hidden after click, proceeding cautiously")
        try:
            dialog.locator("#timeinput").wait_for(state="visible", timeout=5000)
        except PlaywrightTimeoutError:
            logger.debug("BabyConnect: dialog time input not visible yet, continuing anyway")
        self._wait_for_overlay_clear(page)
        return dialog

    def _format_time_for_input(self, value: str | None) -> str:
        if not value:
            return ""
        try:
            cleaned = value.replace("Z", "+00:00")
            dt = datetime.fromisoformat(cleaned)
        except ValueError:
            return value
        return dt.strftime("%I:%M %p").lstrip("0")

    def _format_date_for_input(self, entry: Dict[str, Any]) -> str:
        candidate = entry.get("start_time_utc") or entry.get("start_time")
        dt: datetime | None = None
        if candidate:
            cleaned = candidate.replace("Z", "+00:00")
            try:
                dt = datetime.fromisoformat(cleaned)
            except ValueError:
                dt = None
        if not dt:
            day_iso = (
                entry.get("raw_data", {}).get("day_date_iso")
                if entry.get("raw_data")
                else None
            )
            if day_iso:
                try:
                    dt = datetime.combine(date.fromisoformat(day_iso), datetime.min.time())
                except ValueError:
                    dt = None
        if not dt:
            return ""
        return dt.strftime("%m/%d/%Y")

    def _fill_date_field(self, dialog: Page, entry: Dict[str, Any]) -> None:
        formatted = self._format_date_for_input(entry)
        if not formatted:
            return
        try:
            target_date = datetime.strptime(formatted, "%m/%d/%Y").date()
        except ValueError:
            logger.warning("BabyConnect: invalid date format %s", formatted)
            return

        logger.info("BabyConnect: preparing to set date %s", target_date.isoformat())

        today = datetime.now().date()
        try:
            date_link = dialog.locator("#dateinput")
            if date_link.count():
                date_link.click()
                dialog.page.wait_for_selector("#ui-datepicker-div", state="visible", timeout=2000)
                logger.info("BabyConnect: date picker opened")
            else:
                logger.warning("BabyConnect: date link not found in dialog")
                return
        except Exception:
            logger.warning("BabyConnect: unable to open date picker", exc_info=True)
            return

        months = [
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ]

        def current_month_index() -> int:
            element = dialog.page.locator("#ui-datepicker-div .ui-datepicker-title .ui-datepicker-month")
            month_text = element.inner_text().strip().lower()
            return months.index(month_text)

        def current_year() -> int:
            element = dialog.page.locator("#ui-datepicker-div .ui-datepicker-title .ui-datepicker-year")
            return int(element.inner_text().strip())

        target_month = target_date.month - 1
        target_year = target_date.year

        try:
            for step in range(24):
                year = current_year()
                if year == target_year:
                    break
                button = "#ui-datepicker-div .ui-datepicker-prev" if year > target_year else "#ui-datepicker-div .ui-datepicker-next"
                dialog.page.locator(button).click()
                dialog.page.wait_for_timeout(200)
                logger.info("BabyConnect: adjust year step=%s heading=%s", step, current_year())
            else:
                logger.warning("BabyConnect: unable to reach target year %s", target_year)
                return

            for step in range(12):
                month_idx = current_month_index()
                if month_idx == target_month:
                    break
                button = "#ui-datepicker-div .ui-datepicker-prev" if month_idx > target_month else "#ui-datepicker-div .ui-datepicker-next"
                dialog.page.locator(button).click()
                dialog.page.wait_for_timeout(200)
                logger.info("BabyConnect: adjust month step=%s heading=%s", step, current_month_index())
            else:
                logger.warning("BabyConnect: unable to reach target month %s", target_month)
                return

            day_locator = dialog.page.locator(
                f"#ui-datepicker-div td[data-year='{target_year}'][data-month='{target_month}'] a",
                has_text=str(target_date.day),
            )
            day_locator.first.click()
            dialog.page.wait_for_selector("#ui-datepicker-div", state="hidden", timeout=2000)
            logger.info("BabyConnect: date picker closed and date selected")
        except Exception:
            logger.warning("BabyConnect: failed to select date", exc_info=True)

    def _fill_time_fields(
        self,
        dialog: Page,
        entry: Dict[str, Any],
        use_start_for_end: bool = False,
    ) -> None:
        start = self._format_time_for_input(entry.get("start_time_utc") or entry.get("start_time"))

        
        if start:
            dialog.locator("#timeinput").fill(start)
        end = self._format_time_for_input(entry.get("end_time_utc") or entry.get("end_time"))
        if use_start_for_end and not end:
            end = start
        if dialog.locator("#endtimeinput").count():
            handle = dialog.locator("#endtimeinput")
            handle.fill("")
            if end:
                handle.fill(end)

    def _fill_sleep_end_from_detail(self, dialog: Page, entry: Dict[str, Any]) -> None:
        if not dialog.locator("#endtimeinput").count():
            return
        if entry.get("end_time_utc") or entry.get("end_time"):
            return
        raw_data = entry.get("raw_data") or {}
        detail_lines = raw_data.get("detail_lines") or []
        pattern = re.compile(
            r"(\d{1,2}:\d{2}\s*(?:am|pm)?)\s*(?:-|to)\s*(\d{1,2}:\d{2}\s*(?:am|pm)?)",
            re.IGNORECASE,
        )
        candidate = None
        for line in detail_lines:
            match = pattern.search(line)
            if match:
                candidate = match.group(2)
                break
        if not candidate:
            text = entry.get("summary") or entry.get("raw_text") or ""
            match = pattern.search(text)
            if match:
                candidate = match.group(2)
        base_end = entry.get("end_time_utc") or entry.get("end_time")
        day_iso = raw_data.get("day_date_iso")
        if not day_iso and (entry.get("start_time_utc") or entry.get("start_time")):
            start = entry.get("start_time_utc") or entry.get("start_time")
            if start and "T" in start:
                day_iso = start.split("T")[0]

        def combine_token(token: str) -> datetime | None:
            if not day_iso:
                return None
            return self._combine_date_with_time(day_iso, token)

        end_dt = None
        if base_end:
            try:
                cleaned = base_end.replace("Z", "+00:00")
                end_dt = datetime.fromisoformat(cleaned)
            except ValueError:
                end_dt = None

        if not end_dt and candidate:
            end_dt = combine_token(candidate)

        if not end_dt:
            return
        formatted = end_dt.strftime("%I:%M %p").lstrip("0")
        dialog.locator("#endtimeinput").fill(formatted)

    def _ensure_note_visible(self, dialog: Page) -> None:
        if dialog.locator("#notelnk").count() and dialog.locator("#notesub").count():
            display = dialog.locator("#notesub").first.evaluate(
                "(node) => window.getComputedStyle(node).display",
            )
            if display == "none":
                dialog.locator("#notelnk").click()

    def _append_sync_marker(self, text: str | None) -> str:
        if text:
            cleaned = text.rstrip()
            spacer = "" if cleaned.endswith(" ") else " "
            return f"{cleaned}{spacer}[Sync]"
        return "[Sync]"

    def _entry_raw_data(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        if entry.get("raw_data"):
            return entry["raw_data"]
        details = entry.get("details_json")
        if isinstance(details, dict) and isinstance(details.get("raw_data"), dict):
            return details["raw_data"]
        return {}

    def _detail_payload_lines(self, entry: Dict[str, Any]) -> List[str]:
        raw_data = self._entry_raw_data(entry)
        detail_lines = raw_data.get("detail_lines")
        if not isinstance(detail_lines, list):
            return []
        payload: List[str] = []
        for idx, line in enumerate(detail_lines):
            if not line:
                continue
            text = line.strip()
            if idx == 0 and re.search(r"\d{1,2}:\d{2}", text):
                stripped = re.sub(
                    r"^\s*\d{1,2}:\d{2}\s*(?:am|pm)?\s*[:\-]?\s*",
                    "",
                    text,
                    flags=re.IGNORECASE,
                ).strip()
                if stripped:
                    payload.append(stripped)
                continue
            payload.append(text)
        return payload

    def _note_body_from_entry(self, entry: Dict[str, Any]) -> str | None:
        payload = self._detail_payload_lines(entry)
        event_type = (entry.get("event_type") or "").lower()
        if payload:
            if event_type == "sleep":
                payload_body: list[str] = []
            elif event_type in {"nappy", "diaper"}:
                if len(payload) > 1:
                    payload_body = payload[1:]
                    return " | ".join(payload_body)
                else:
                    return None
            elif event_type in {"solid", "meal", "food"} and len(payload) > 1:
                payload_body = payload[1:]
            else:
                payload_body = payload
            if payload_body:
                return " | ".join(payload_body)
        raw_data = self._entry_raw_data(entry)
        if event_type == "sleep":
            return None
        for candidate in (
            raw_data.get("original_title"),
            raw_data.get("note"),
            entry.get("note"),
            entry.get("summary"),
            entry.get("raw_text"),
        ):
            if candidate and candidate.strip():
                return candidate.strip()
        return None

    def _create_diaper_entry(self, page: Page, entry: Dict[str, Any]) -> None:
        logger.info("BabyConnect: opening diaper dialog for entry %s", entry.get("id") or entry.get("summary"))
        dialog = self._open_entry_dialog(page, "showDiaperDlg")
        self._fill_date_field(dialog, entry)
        self._fill_time_fields(dialog, entry)

        diaper_type = (entry.get("diaper_type") or entry.get("subtype") or "wet").lower()
        radio_map = {
            "bm": "#diaper1",
            "bm_wet": "#diaper2",
            "wet": "#diaper3",
            "dry": "#diaper4",
        }
        target_selector = radio_map.get(diaper_type, "#diaper3")
        target = dialog.locator(target_selector)
        try:
            target.check()
        except PlaywrightTimeoutError:
            # If radio is hidden, trigger via associated label or force
            label = dialog.locator(f"label[for='{target_selector.lstrip('#')}']")
            if label.count():
                label.first.click()
            else:
                target.check(force=True)

        quantity = entry.get("quantity")
        if quantity is not None and dialog.locator("#qtycombo").count():
            dialog.select_option("#qtycombo", str(quantity))

        self._fill_sleep_end_from_detail(dialog, entry)

        self._ensure_note_visible(dialog)
        note_body = self._note_body_from_entry(entry)
        note_text = self._append_sync_marker(note_body)
        dialog.locator("#notetxt").fill(note_text)

        dialog.locator(".defaultDlgButtonSave").click()
        try:
            dialog.wait_for(state="hidden", timeout=10000)
        except PlaywrightTimeoutError:
            logger.warning("BabyConnect: diaper dialog did not hide after save, continuing")
        try:
            dialog.wait_for(state="detached", timeout=5000)
        except PlaywrightTimeoutError:
            logger.warning("BabyConnect: diaper dialog still attached, continuing anyway")
        logger.info("BabyConnect: diaper entry saved")

    def _create_sleep_entry(self, page: Page, entry: Dict[str, Any]) -> None:
        logger.info("BabyConnect: opening sleep dialog for entry %s", entry.get("id") or entry.get("summary"))
        dialog = self._open_entry_dialog(page, "showSleepDlg")
        self._fill_date_field(dialog, entry)
        self._fill_time_fields(dialog, entry)

        napped_label = dialog.locator("label", has_text="napped")
        slept_label = dialog.locator("label", has_text="slept")
        target_label = napped_label if napped_label.count() else slept_label
        if target_label.count():
            target_for = target_label.get_attribute("for")
            if target_for and dialog.locator(f"#{target_for}").count():
                target = dialog.locator(f"#{target_for}")
                target.scroll_into_view_if_needed()
                target.check(force=True)

        self._fill_sleep_end_from_detail(dialog, entry)

        self._ensure_note_visible(dialog)
        dialog.locator("#notetxt").fill(
            self._append_sync_marker(self._note_body_from_entry(entry))
        )

        dialog.locator(".defaultDlgButtonSave").click()
        try:
            dialog.wait_for(state="hidden", timeout=8000)
        except PlaywrightTimeoutError:
            logger.warning("BabyConnect: sleep dialog did not hide after save, continuing")
        try:
            dialog.wait_for(state="detached", timeout=4000)
        except PlaywrightTimeoutError:
            logger.warning("BabyConnect: sleep dialog still attached, continuing anyway")
        logger.info("BabyConnect: sleep entry saved")

    def _create_solid_entry(self, page: Page, entry: Dict[str, Any]) -> None:
        logger.info("BabyConnect: opening solid dialog for entry %s", entry.get("id") or entry.get("summary"))
        dialog = self._open_entry_dialog(page, "showEatDlg")
        self._fill_date_field(dialog, entry)
        self._fill_time_fields(dialog, entry, use_start_for_end=True)

        solid_type = str(entry.get("solid_type") or "201")
        if solid_type.isdigit():
            dialog.locator(f"#input{solid_type}").check()

        quantity_label = entry.get("quantity_label") or entry.get("quantity")
        if quantity_label:
            dialog.select_option("#qtyDDown", str(quantity_label))

        unit = entry.get("unit")
        if unit:
            dialog.select_option("#unitDDown", str(unit))

        reaction = entry.get("reaction")
        if reaction:
            dialog.locator(f"#reaction-{reaction}").check()

        note_body = self._note_body_from_entry(entry)
        if not note_body:
            note_body = entry.get("note") or entry.get("summary") or entry.get("raw_text")

        self._ensure_note_visible(dialog)
        dialog.locator("#notetxt").fill(self._append_sync_marker(note_body))

        dialog.locator(".defaultDlgButtonSave").click()
        try:
            dialog.wait_for(state="hidden", timeout=8000)
        except PlaywrightTimeoutError:
            logger.warning("BabyConnect: solid dialog did not hide after save, continuing")
        try:
            dialog.wait_for(state="detached", timeout=4000)
        except PlaywrightTimeoutError:
            logger.warning("BabyConnect: solid dialog still attached, continuing anyway")
        logger.info("BabyConnect: solid entry saved")

    def _create_message_entry(self, page: Page, entry: Dict[str, Any]) -> None:
        logger.info("BabyConnect: opening message dialog for entry %s", entry.get("id") or entry.get("summary"))
        dialog = self._open_entry_dialog(page, "showMsgDlg")
        self._fill_date_field(dialog, entry)
        self._fill_time_fields(dialog, entry)

        message = (
            entry.get("message")
            or entry.get("note")
            or self._note_body_from_entry(entry)
            or entry.get("summary")
            or entry.get("raw_text")
        )
        dialog.locator("#txt").fill(self._append_sync_marker(message))
        dialog.locator(".defaultDlgButtonSave").click()
        try:
            dialog.wait_for(state="hidden", timeout=10000)
        except PlaywrightTimeoutError:
            logger.warning("BabyConnect: message dialog did not hide after save, continuing anyway")
        try:
            dialog.wait_for(state="detached", timeout=5000)
        except PlaywrightTimeoutError:
            logger.warning("BabyConnect: message dialog still attached, continuing anyway")
        logger.info("BabyConnect: message entry saved")


    def _extract_time_and_author(self, node) -> tuple[str, str]:
        container = node.query_selector(BC_POSTED_BY_CONTAINER_SELECTOR)
        if not container:
            return "", ""

        spans = container.query_selector_all("span")
        time_str = ""
        author = ""
        if spans:
            time_str = spans[0].inner_text().strip()
            if len(spans) > 1:
                author_raw = spans[1].inner_text().strip()
                m = re.search(r"by\s+(.*)", author_raw, re.IGNORECASE)
                author = m.group(1).strip() if m else author_raw

        return time_str, author

    def _infer_event_type(self, title: str, icon_src: str) -> str:
        t = title.lower()
        s = (icon_src or "").lower()

        if "eat_v2" in s:
            return "solid"
        if "diapers_v2" in s:
            return "nappy"
        if "bib_v2" in s:
            return "bottle"
        if "sleep_v2" in s:
            return "sleep"
        if "medicine_v2" in s:
            return "medicine"
        if "temperature_v2" in s:
            return "temperature"
        if "bath_v2" in s:
            return "bath"
        if "potty_v2" in s:
            return "potty"
        if "msg_v2" in s:
            return "message"

        if "diaper" in t or "nappy" in t:
            return "nappy"
        if "sleep" in t:
            return "sleep"
        if "medicine" in t or "calpol" in t:
            return "medicine"
        if "temperature" in t:
            return "temperature"
        if "breakfast" in t or "lunch" in t or "dinner" in t or "meal" in t or "ate" in t or "drank" in t or "food" in t:
            return "solid"
        if "bottle" in t or "formula" in t:
            return "bottle"
        if "bath" in t:
            return "bath"
        if "signed in" in t or "signed out" in t or "message" in t:
            return "message"

        return "other"

    def _read_child_name(self, page) -> str:
        try:
            name_el = page.query_selector(CHILD_NAME_SELECTOR)
            if name_el:
                return name_el.inner_text().strip()
        except Exception:
            logger.exception("BabyConnect: failed to read child name")
        return ""

    def _get_status_list(self, page: Page):
        try:
            page.wait_for_selector(STATUS_LIST_CONTAINER, timeout=10000)
            status_container = page.query_selector(STATUS_LIST_CONTAINER)
            if not status_container:
                return None
            status_wrap = status_container.query_selector(STATUS_LIST_WRAP)
            if not status_wrap:
                return None
            return status_wrap.query_selector(STATUS_LIST_SELECTOR)
        except Exception:
            logger.exception("BabyConnect: error locating status list")
            return None

    def _get_current_day_info(self, page: Page) -> tuple[str, str]:
        text = page.inner_text(DATE_DISPLAY_SELECTOR).strip()
        lower = text.lower()
        today = datetime.now()
        if lower == "today":
            dt = today
        elif lower == "yesterday":
            dt = today - timedelta(days=1)
        else:
            try:
                dt = datetime.strptime(text, "%A, %d %B, %Y")
            except ValueError:
                dt = today
        iso = dt.date().isoformat()
        label = text if lower not in {"today", "yesterday"} else dt.strftime("%A, %d %B %Y")
        return label, iso

    def _go_to_previous_day(self, page: Page, current_label: str) -> bool:
        try:
            page.click(DATE_LEFT_SELECTOR)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(800)
            page.wait_for_selector(DATE_DISPLAY_SELECTOR, timeout=5000)
            logger.info("BabyConnect: moved to previous day from %s", current_label)
            return True
        except Exception:
            logger.exception("BabyConnect: failed to move to previous day")
            return False

    def _collect_events_for_day(
        self,
        status_list,
        child_name: str,
        day_label: str,
        day_iso: str,
    ) -> List[RawBabyConnectEvent]:
        if not status_list:
            return []

        rows = status_list.query_selector_all(BC_EVENT_SELECTOR)
        collected: List[RawBabyConnectEvent] = []

        for node in rows:
            icon_src = ""
            icon_el = node.query_selector(BC_EVENT_ICON_SELECTOR)
            if icon_el:
                icon_src = icon_el.get_attribute("src") or ""

            title_el = node.query_selector(BC_EVENT_TITLE_SELECTOR)
            if not title_el:
                continue
            title_text = title_el.inner_text().strip()

            note_el = node.query_selector(BC_EVENT_NOTE_SELECTOR)
            note_text = note_el.inner_text().strip() if note_el else ""

            time_str, author = self._extract_time_and_author(node)
            event_type = self._infer_event_type(title_text, icon_src)
            start_iso, end_iso, display_range = self._parse_time_range(day_iso, time_str)
            detail_lines = self._build_detail_lines(
                event_type=event_type,
                title_text=title_text,
                note_text=note_text,
                display_range=display_range,
            )

            raw_data = {
                "icon_src": icon_src,
                "author": time_str,
                "posted_by": author,
                "note": note_text,
                "raw_html": node.inner_html(),
                "day_label": day_label,
                "day_date_iso": day_iso,
            }
            if end_iso:
                raw_data["end_event_datetime_iso"] = end_iso
            if detail_lines:
                raw_data["detail_lines"] = detail_lines

            collected.append(
                RawBabyConnectEvent(
                    child_name=child_name,
                    event_type=event_type,
                    time_str=time_str,
                    raw_text=title_text,
                    raw_data=raw_data,
                    event_datetime_iso=start_iso,
                )
            )

        return collected

    def _combine_date_with_time(self, day_iso: str, token: str) -> datetime | None:
        match = re.match(r"(\d{1,2}):(\d{2})\s*(am|pm)?", token.strip(), re.IGNORECASE)
        if not match:
            return None
        hour = int(match.group(1))
        minute = int(match.group(2))
        meridiem = match.group(3)
        if meridiem:
            meridiem = meridiem.lower()
            if meridiem == "pm" and hour < 12:
                hour += 12
            if meridiem == "am" and hour == 12:
                hour = 0
        try:
            date_part = datetime.strptime(day_iso, "%Y-%m-%d").date()
            return datetime.combine(date_part, datetime.min.time()).replace(hour=hour, minute=minute)
        except Exception:
            return None

    def _parse_time_range(
        self,
        day_iso: str,
        time_str: str,
    ) -> tuple[str | None, str | None, str | None]:
        if not day_iso or not time_str:
            return None, None, None

        matches = re.findall(r"\d{1,2}:\d{2}\s*(?:am|pm)?", time_str, re.IGNORECASE)
        if not matches:
            return None, None, None

        start_dt = self._combine_date_with_time(day_iso, matches[0])
        end_dt = None
        if len(matches) > 1:
            end_dt = self._combine_date_with_time(day_iso, matches[1])
            if start_dt and end_dt and end_dt <= start_dt:
                end_dt = end_dt + timedelta(days=1)

        display = None
        if len(matches) >= 2:
            display = f"{matches[0]} - {matches[1]}"
        else:
            display = matches[0]

        return (
            start_dt.isoformat() if start_dt else None,
            end_dt.isoformat() if end_dt else None,
            display,
        )

    def _build_detail_lines(
        self,
        event_type: str,
        title_text: str,
        note_text: str,
        display_range: str | None,
    ) -> List[str]:
        seen: set[str] = set()
        lines: List[str] = []

        def add_line(value: str | None):
            if not value:
                return
            cleaned = value.strip()
            if not cleaned:
                return
            normalized = cleaned.lower()
            if normalized in seen:
                return
            seen.add(normalized)
            lines.append(cleaned)

        def add_note_lines() -> bool:
            if not note_text:
                return False
            note_clean = re.sub(r"\[sync\]", "", note_text, flags=re.IGNORECASE).strip()
            if not note_clean:
                return False
            added = False
            for part in re.split(r"\s*\|\s*", note_clean):
                segment = part.strip()
                if segment:
                    add_line(segment)
                    added = True
            return added

        etype = (event_type or "").lower()
        if etype == "sleep":
            if display_range:
                add_line(display_range)
            if not add_note_lines():
                add_line(title_text)
        elif etype in {"nappy", "diaper"}:
            if not add_note_lines():
                add_line(title_text)
        elif etype in {"solid", "meal", "food", "bottle", "temperature", "medicine", "potty"}:
            if not add_note_lines():
                add_line(title_text)
        elif etype in {"message", "note"}:
            if not add_note_lines():
                add_line(title_text)
        else:
            if display_range:
                add_line(display_range)
            if not add_note_lines():
                add_line(title_text)

        return lines
