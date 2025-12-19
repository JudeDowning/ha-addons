"""
Famly client (scraping).
------------------------

This module contains a thin wrapper around Playwright to:

- Launch a browser context (headless or not, depending on config)
- Log into Famly using email/password
- Navigate to the relevant activity view
- Extract a list of RawFamlyEvent objects
"""

from __future__ import annotations

from typing import List, Optional
import re
import logging
from datetime import datetime, date, time, timedelta

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from .config import FAMLY_PROFILE_DIR, HEADLESS, FAMLY_CHILD_ID
from .normalisation import RawFamlyEvent
from .event_mapping import normalize_famly_title

FAMLY_LOGIN_URL = "https://app.famly.co/#/login"

EMAIL_SELECTOR = "#email"
PASSWORD_SELECTOR = "#password"
LOGIN_BUTTON_SELECTOR = "#loginSubmit"

# Activity page selectors
DAY_SELECTOR = "div.ActivityDay"
DAY_HEADING_SELECTOR = "h3"
EVENT_SELECTOR = "div.Event"
EVENT_CONTENT_SELECTOR = "[data-e2e-class='event-content']"
EVENT_TITLE_SELECTOR = "[data-e2e-class='event-title']"
EVENT_DETAIL_LINES_SELECTOR = "small"

# Child selection
GENERIC_CHILD_LINK_SELECTOR = "a[data-e2e-id^='NavigationGroup-Child-']"
PROFILE_CHILD_LINK_SELECTOR = "a[href*='account/childProfile']"
CHILD_NAME_SELECTOR = "#personProfile h2.title-test-marker"

logger = logging.getLogger(__name__)


class FamlyClient:
    def __init__(self, email: str, password: str, child_id: str | None = None) -> None:
        self.email = email
        self.password = password
        self.child_id = (child_id.strip() if child_id else FAMLY_CHILD_ID).strip()

    @property
    def child_link_selector(self) -> str | None:
        if self.child_id:
            return f"a[data-e2e-id='NavigationGroup-Child-{self.child_id}']"
        return None

    def login_and_scrape(self, days_back: int = 0) -> List[RawFamlyEvent]:
        """
        Main entrypoint: log into Famly (if necessary) and return a list of
        raw scraped events.

        In development, set HEADLESS = False to watch the flow and tweak selectors.
        """
        events: List[RawFamlyEvent] = []
        entry_day_limit = max(1, days_back + 1)
        reference_date = datetime.now().date()

        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=str(FAMLY_PROFILE_DIR),
                headless=HEADLESS,
            )
            page = browser.new_page()

            # 1. Go to login page
            logger.info("Famly scrape: navigating to login page")
            page.goto(FAMLY_LOGIN_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(500)

            # 2. If login fields are visible, login; otherwise verify the dashboard before assuming existing session
            if self.email and self.password:
                used_login_form = self._login_if_needed(page)
                if not used_login_form and not self._wait_for_dashboard(page):
                    logger.info("Famly scrape: dashboard not visible; reloading to surface login form")
                page.goto(FAMLY_LOGIN_URL, wait_until="domcontentloaded")
                    page.wait_for_timeout(500)
                    self._login_if_needed(page)
            else:
                logger.info("Famly scrape: skipping login (no credentials provided)")

            # At this point we should be on /account/feed/me

            # 3. Click the child icon/link in the sidebar
            self._select_child(page)

            # 4. Wait for navigation to child's activity feed
            logger.info("Famly scrape: waiting for child activity feed to load")
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_selector(CHILD_NAME_SELECTOR, timeout=10000)
            page.wait_for_selector(DAY_SELECTOR, timeout=10000)

            # 4b. Read child name from the profile header
            child_full_name = ""
            child_first_name = ""
            try:
                child_name_el = page.query_selector(CHILD_NAME_SELECTOR)
                if child_name_el:
                    child_full_name = child_name_el.inner_text().strip()
                    if child_full_name:
                        child_first_name = child_full_name.split()[0]
                logger.info("Famly scrape: detected child name %s", child_full_name or "Unknown")
            except Exception:
                # Non-fatal - we'll just leave child name blank if this fails
                logger.exception("Famly scrape: failed to read child name")
                pass
                
            # 5. Scrape days and events
            logger.info("Famly scrape: collecting day blocks")
            day_blocks = page.query_selector_all(DAY_SELECTOR)
            logger.info("Famly scrape: found %d day blocks", len(day_blocks))

            days_included = 0

            for day_block in day_blocks:
                # e.g. "Monday, Dec 1"
                day_heading_el = day_block.query_selector(DAY_HEADING_SELECTOR)
                day_label = (
                    day_heading_el.inner_text().strip()
                    if day_heading_el
                    else ""
                )
                day_date = self._parse_day_label(day_label, reference_date)

                event_blocks = day_block.query_selector_all(EVENT_SELECTOR)
                if not event_blocks:
                    continue

                logger.info(
                    "Famly scrape: processing %s with %d events",
                    day_label or "Unknown day",
                    len(event_blocks),
                )
                days_included += 1
                if entry_day_limit and days_included > entry_day_limit:
                    logger.info("Famly scrape: reached entry day limit (%d), stopping", entry_day_limit)
                    break
                for ev_block in event_blocks:
                    content = ev_block.query_selector(EVENT_CONTENT_SELECTOR)
                    if not content:
                        continue

                    title_el = content.query_selector(EVENT_TITLE_SELECTOR)
                    if not title_el:
                        continue

                    raw_title = title_el.inner_text().strip()
                    event_title = normalize_famly_title(raw_title)
                    if (event_title or raw_title).lower().find("expected pick up") != -1:
                        logger.debug("Famly scrape: skipping expected pick up entry")
                        continue

                    # Collect detail lines and split entries
                    detail_lines = self._extract_detail_lines(content)
                    entry_blocks = self._split_entry_blocks(detail_lines)

                    if not entry_blocks:
                        entry_blocks = [detail_lines]

                    for idx, entry in enumerate(entry_blocks):
                        entry_text = " | ".join(entry) if entry else ""
                        time_str = self._extract_time_string([day_label] + entry)
                        logger.debug(
                            "Famly scrape: entry %s - %s (%s)",
                            day_label,
                            event_title,
                            time_str,
                        )

                        event_dt = self._build_event_datetime(day_date, time_str)
                        event_end_dt = self._build_end_datetime(day_date, time_str, event_dt)

                        if (
                            event_title
                            and "sleep" in (event_title or "").lower()
                            and event_end_dt is None
                        ):
                            logger.debug(
                                "Famly scrape: skipping in-progress sleep entry without end time (%s - %s)",
                                day_label,
                                entry_text,
                            )
                            continue

                        preferred_name = child_full_name or child_first_name or "Unknown"
                        events.append(
                            RawFamlyEvent(
                                child_name=preferred_name.strip(),
                                event_type=event_title,
                                time_str=time_str,
                                raw_text=f"{day_label} - {event_title}: {entry_text or event_title}",
                                raw_data={
                                    "day_label": day_label,
                                    "detail_lines": entry,
                                    "child_full_name": child_full_name,
                                    "day_date_iso": day_date.isoformat() if day_date else None,
                                    "event_datetime_iso": event_dt.isoformat() if event_dt else None,
                                    "end_event_datetime_iso": event_end_dt.isoformat() if event_end_dt else None,
                                    "original_title": raw_title,
                                    "entry_index": idx,
                                },
                                event_datetime_iso=event_dt.isoformat() if event_dt else None,
                            )
                        )
                if entry_day_limit and days_included >= entry_day_limit:
                    break
            browser.close()
            logger.info("Famly scrape: finished with %d events", len(events))

        events.sort(key=lambda ev: ev.event_datetime_iso or "", reverse=True)
        limited = self._limit_events_by_entry_days(events, entry_day_limit)
        limited.sort(key=lambda ev: ev.event_datetime_iso or "")
        return limited

    def verify_login(self) -> None:
        """
        Lightweight login check used by the API test endpoint.
        """
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=str(FAMLY_PROFILE_DIR),
                headless=HEADLESS,
            )
            page = browser.new_page()
            logger.info("Famly client: verifying login")
            page.goto(FAMLY_LOGIN_URL, wait_until="networkidle")
            if page.is_visible(EMAIL_SELECTOR):
                page.fill(EMAIL_SELECTOR, self.email)
                page.fill(PASSWORD_SELECTOR, self.password)
                page.click(LOGIN_BUTTON_SELECTOR)
                page.wait_for_load_state("networkidle")
            self._select_child(page)
            browser.close()
            logger.info("Famly client: login verification successful")

    def _login_if_needed(self, page) -> bool:
        """
        Try to log into Famly if the login form is present.

        Returns True if we submitted the form, False if inputs were never visible.
        """
        email_input = page.locator(EMAIL_SELECTOR)
        password_input = page.locator(PASSWORD_SELECTOR)

        def _wait_for_login_fields(timeout: int = 5000) -> bool:
            try:
                email_input.wait_for(state="visible", timeout=timeout)
                password_input.wait_for(state="attached", timeout=timeout)
                return True
            except PlaywrightTimeoutError:
                return False

        if not _wait_for_login_fields():
            current_url = (page.url or "").lower()
            if "login" in current_url:
                logger.info(
                    "Famly scrape: login view detected but form hidden, reloading to surface fields"
                )
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(750)
                if not _wait_for_login_fields(timeout=8000):
                    logger.info(
                        "Famly scrape: login inputs still hidden after reload, assuming existing session"
                    )
                    return False
            else:
                logger.info("Famly scrape: login form not visible, assuming existing session")
                return False

        logger.info("Famly scrape: entering credentials")
        email_input.fill(self.email)
        password_input.fill(self.password)
        page.locator(LOGIN_BUTTON_SELECTOR).click()
        logger.info("Famly scrape: login submitted, waiting for dashboard")
        page.wait_for_load_state("networkidle")
        return True

    def _wait_for_dashboard(self, page, timeout: int = 2500) -> bool:
        """
        Confirm that a child profile element is rendered, indicating the dashboard loaded.
        """
        try:
            page.wait_for_selector(CHILD_NAME_SELECTOR, timeout=timeout)
            return True
        except PlaywrightTimeoutError:
            return False

    def _select_child(self, page) -> None:
        selectors_to_try = []
        if self.child_link_selector:
            selectors_to_try.append(self.child_link_selector)
        selectors_to_try.append(GENERIC_CHILD_LINK_SELECTOR)
        last_error = None
        for selector in selectors_to_try:
            try:
                logger.info("Famly scrape: selecting child link %s", selector)
                page.wait_for_selector(selector, timeout=15000)
                element = page.query_selector(selector)
                if element:
                    element.click()
                    return
            except PlaywrightTimeoutError as exc:
                last_error = exc
                logger.warning("Famly scrape: selector %s not found, trying fallback", selector)
        try:
            logger.info("Famly scrape: selecting first available child entry as fallback")
            fallback_locator = page.locator(GENERIC_CHILD_LINK_SELECTOR)
            fallback_locator.first.wait_for(state="visible", timeout=5000)
            fallback_locator.first.click()
            return
        except Exception as exc:
            last_error = exc if last_error is None else last_error
        try:
            logger.info("Famly scrape: attempting child profile link fallback")
            profile_link = page.locator(PROFILE_CHILD_LINK_SELECTOR).first
            profile_link.wait_for(state="visible", timeout=5000)
            profile_link.click()
            page.wait_for_load_state("networkidle")
            return
        except Exception as exc:
            last_error = exc if last_error is None else last_error
        raise RuntimeError(
            "Unable to locate child profile link in Famly. Set FAMLY_CHILD_ID env var if multiple children exist."
        ) from last_error

    def _extract_time_string(self, lines: list[str]) -> str:
        """
        Very simple heuristic:

        - If we find a pattern like 'HH:MM - HH:MM', return that.
        - Else if we find a pattern like 'HH:MM', return the first one.
        - Else just return the first non-empty line.
        """
        joined = " | ".join(lines)

        # Range like "12:11 - 13:16"
        m_range = re.search(r"\b\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}\b", joined)
        if m_range:
            return m_range.group(0)

        # Single time like "08:20" or "14:20"
        m_single = re.search(r"\b\d{1,2}:\d{2}\b", joined)
        if m_single:
            return m_single.group(0)

        # Fallback – at least something human-readable
        for line in lines:
            if line.strip():
                return line.strip()

        return ""

    def _extract_detail_lines(self, content) -> List[str]:
        detail_els = content.query_selector_all(EVENT_DETAIL_LINES_SELECTOR)
        lines: List[str] = []
        last_line: Optional[str] = None
        for el in detail_els:
            if not el:
                continue
            text = el.inner_text().strip()
            if not text:
                continue
            if text == last_line:
                continue
            lines.append(text)
            last_line = text
        return lines

    def _split_entry_blocks(self, lines: List[str]) -> List[List[str]]:
        blocks: List[List[str]] = []
        current: List[str] = []
        for line in lines:
            if self._is_time_line(line):
                if current:
                    blocks.append(current)
                current = [line]
            else:
                current.append(line)
        if current:
            blocks.append(current)
        return blocks

    def _is_time_line(self, line: str) -> bool:
        return bool(re.search(r"\b\d{1,2}:\d{2}\b", line or ""))
    def _limit_events_by_entry_days(
        self,
        events: List[RawFamlyEvent],
        extra_entry_days: int,
    ) -> List[RawFamlyEvent]:
        """
        Keep only events from the most recent (extra_entry_days + 1) days with entries.
        """
        if extra_entry_days <= 0:
            allowed_days = 1
        else:
            allowed_days = extra_entry_days + 1

        result: List[RawFamlyEvent] = []
        seen_days: list[str] = []

        for event in events:
            day_key = event.raw_data.get("day_date_iso") or event.raw_data.get("day_label") or ""
            if day_key not in seen_days:
                if len(seen_days) >= allowed_days:
                    continue
                seen_days.append(day_key)
            result.append(event)

        return result

    def _parse_day_label(self, label: str, reference: date) -> Optional[date]:
        """
        Attempt to parse labels like "Today", "Yesterday", or "Monday, Dec 1".
        """
        if not label:
            return reference

        slug = label.strip().lower()
        if slug == "today":
            return reference
        if slug == "yesterday":
            return reference - timedelta(days=1)

        patterns_with_year = [
            "%A, %d %B, %Y",
            "%A, %B %d, %Y",
            "%A %d %B %Y",
            "%A %B %d %Y",
        ]
        for pattern in patterns_with_year:
            try:
                return datetime.strptime(label, pattern).date()
            except ValueError:
                continue

        patterns = [
            "%A, %b %d",
            "%A, %B %d",
            "%A %b %d",
            "%A %B %d",
        ]
        for pattern in patterns:
            try:
                parsed = datetime.strptime(f"{label} {reference.year}", f"{pattern} %Y").date()
                # If parsing jumps into the future (e.g. December when it's January), assume last year.
                if parsed > reference + timedelta(days=1):
                    parsed = parsed.replace(year=parsed.year - 1)
                return parsed
            except ValueError:
                continue
        logger.debug("Famly scrape: unable to parse day label '%s'", label)
        return None

    def _build_event_datetime(self, day: Optional[date], time_str: str) -> Optional[datetime]:
        if not day:
            return None
        match = re.search(r"\b(\d{1,2}):(\d{2})\b", time_str or "")
        hour = 0
        minute = 0
        if match:
            hour = min(int(match.group(1)), 23)
            minute = min(int(match.group(2)), 59)
        return datetime.combine(day, time(hour=hour, minute=minute))

    def _build_end_datetime(
        self,
        day: Optional[date],
        time_str: str,
        start_dt: Optional[datetime],
    ) -> Optional[datetime]:
        if not day:
            return None
        matches = re.findall(r"(\d{1,2}):(\d{2})", time_str or "")
        if len(matches) < 2:
            return None
        hour = min(int(matches[1][0]), 23)
        minute = min(int(matches[1][1]), 59)
        end_dt = datetime.combine(day, time(hour=hour, minute=minute))
        if start_dt and end_dt <= start_dt:
            end_dt += timedelta(days=1)
        return end_dt
