import React, { useMemo } from "react";
import { NormalisedEvent } from "../types";
import { assetUrl } from "../api";

type DateFormat = "weekday-mon-dd" | "weekday-dd-mon";

interface Props {
  famlyEvents: NormalisedEvent[];
  babyEvents: NormalisedEvent[];
  dateFormat: DateFormat;
  onSyncEvent?: (eventId: number) => void;
  onToggleIgnore?: (eventId: number, ignored: boolean) => void;
  syncingEventId?: number | null;
  isBulkSyncing?: boolean;
  showMissingOnly?: boolean;
  onToggleMissing?: () => void;
  controlsSlot?: React.ReactNode;
  failedEventIds?: number[];
  selectedEventIds?: number[];
  onToggleSelection?: (eventId: number, selected: boolean) => void;
}

interface PairedRow {
  key: string;
  famly?: NormalisedEvent;
  baby?: NormalisedEvent;
  dayLabel: string;
  dayIso: string;
  timestamp: number;
}

const icon = (path: string) => assetUrl(path);

const defaultIconMap: Record<string, string> = {
  nappy: icon("/icons/diapers_v2.svg"),
  diaper: icon("/icons/diapers_v2.svg"),
  bottle: icon("/icons/bib_v2.svg"),
  solid: icon("/icons/eat_v2.svg"),
  meal: icon("/icons/eat_v2.svg"),
  meals: icon("/icons/eat_v2.svg"),
  sleep: icon("/icons/sleep_v2.svg"),
  medicine: icon("/icons/medicine_v2.svg"),
  temperature: icon("/icons/temperature_v2.svg"),
  bath: icon("/icons/bath_v2.svg"),
  message: icon("/icons/msg_v2.svg"),
  potty: icon("/icons/potty_v2.svg"),
};

const famlyIconMap: Record<string, string> = {
  nappy: icon("/icons/famly_diaper.svg"),
  "nappy change": icon("/icons/famly_diaper.svg"),
  diaper: icon("/icons/famly_diaper.svg"),
  solid: icon("/icons/famly_meals.svg"),
  meals: icon("/icons/famly_meals.svg"),
  meal: icon("/icons/famly_meals.svg"),
  sleep: icon("/icons/famly_sleep.svg"),
  "signed in": icon("/icons/famly_sign_in.svg"),
  "sign in": icon("/icons/famly_sign_in.svg"),
  "signed out": icon("/icons/famly_sign_out.svg"),
  "sign out": icon("/icons/famly_sign_out.svg"),
  ill: icon("/icons/famly_sick.svg"),
  sick: icon("/icons/famly_sick.svg"),
};

const SIGN_EVENT_TYPES = ["signed in", "sign in", "signed out", "sign out"];

const inferFamlyEventType = (event?: NormalisedEvent): string | undefined => {
  if (!event) return undefined;
  const base = (event.event_type || "").toLowerCase();
  if (SIGN_EVENT_TYPES.includes(base)) {
    return base;
  }
  const original = event.raw_data?.original_title?.toLowerCase() || "";
  if (original.includes("signed into") || original.includes("signed in")) {
    return "signed in";
  }
  if (original.includes("signed out")) {
    return "signed out";
  }
  return base || undefined;
};

const getIcon = (
  type: string | undefined | null,
  sourceLabel: string,
) => {
  if (!type) return null;
  const lower = type.toLowerCase();
  if (sourceLabel === "Baby Connect" && SIGN_EVENT_TYPES.includes(lower)) {
    return defaultIconMap["message"];
  }
  if (sourceLabel === "Famly") {
    return famlyIconMap[lower] || defaultIconMap[lower] || null;
  }
  return defaultIconMap[lower] || null;
};

const famlyDisplayMap: Record<string, string> = {
  solid: "Meals",
  meals: "Meals",
  meal: "Meals",
  nappy: "Nappy change",
  "nappy change": "Nappy change",
  sleep: "Sleep",
  "signed in": "Signed in",
  "sign in": "Signed in",
  "signed out": "Signed out",
  "sign out": "Signed out",
};

const babyDisplayMap: Record<string, string> = {
  nappy: "Diaper",
  diaper: "Diaper",
  solid: "Solid",
  meals: "Solid",
  meal: "Solid",
  sleep: "Sleep",
  bottle: "Bottle",
  medicine: "Medicine",
  temperature: "Temperature",
  bath: "Bath",
  message: "Message",
  potty: "Potty",
};

const getEventTitle = (type: string, sourceLabel: string) => {
  const lower = type.toLowerCase();
  if (sourceLabel === "Famly") {
    return famlyDisplayMap[lower] || type;
  }
  if (sourceLabel === "Baby Connect") {
    return babyDisplayMap[lower] || type;
  }
  return type;
};

const toDateKey = (iso: string) => new Date(iso).toISOString().slice(0, 10);

const getDayIso = (ev: NormalisedEvent) =>
  ev.raw_data?.day_date_iso || toDateKey(ev.start_time_utc);

const getSortTimestamp = (ev: NormalisedEvent) => {
  const start = new Date(ev.start_time_utc);
  const endUtc = ev.end_time_utc ? new Date(ev.end_time_utc) : null;
  const dayIso = getDayIso(ev);
  const isBabySleep =
    ev.source_system === "baby_connect" &&
    (ev.event_type || "").toLowerCase().includes("sleep");

  if (isBabySleep && endUtc) {
    let sortDate = endUtc;
    if (dayIso) {
      const base = new Date(`${dayIso}T00:00:00Z`);
      if (!Number.isNaN(base.getTime())) {
        sortDate = new Date(base.getTime());
        sortDate.setUTCHours(
          endUtc.getUTCHours(),
          endUtc.getUTCMinutes(),
          endUtc.getUTCSeconds(),
          endUtc.getUTCMilliseconds(),
        );
      }
    }
    return sortDate.getTime();
  }

  return start.getTime();
};

const formatDayDisplay = (
  iso: string,
  fallback: string,
  format: DateFormat,
) => {
  if (!iso) return fallback;
  const date = new Date(`${iso}T00:00:00`);
  const weekday = date.toLocaleDateString(undefined, { weekday: "short" });
  const month = date.toLocaleDateString(undefined, { month: "short" });
  const day = date.toLocaleDateString(undefined, { day: "2-digit" });
  return format === "weekday-dd-mon"
    ? `${weekday} ${day} ${month}`
    : `${weekday} ${month} ${day}`;
};

const getEntrySplits = (event: NormalisedEvent) => {
  const detailLines = Array.isArray(event.raw_data?.detail_lines)
    ? event.raw_data!.detail_lines!
    : [];
  const splits: string[][] = [];
  let current: string[] = [];
  detailLines.forEach((line) => {
    if (/\d{1,2}:\d{2}/.test(line)) {
      if (current.length) splits.push(current);
      current = [line];
    } else {
      current.push(line);
    }
  });
  if (current.length) splits.push(current);
  if (!splits.length) {
    splits.push([]);
  }
  return splits;
};

const applyDegreeSymbol = (text: string) =>
  text.replace(/(\d+(?:\.\d+)?)\s*C\b/gi, "$1\u00B0C");

const buildPairs = (
  famlyEvents: NormalisedEvent[],
  babyEvents: NormalisedEvent[],
): PairedRow[] => {
  const map = new Map<string, PairedRow>();

  const makeHeuristicKey = (ev: NormalisedEvent) => {
    const day = getDayIso(ev);
    const time = new Date(ev.start_time_utc).toISOString().slice(0, 16);
    const child = (ev.child_name || "").toLowerCase();
    const type = (ev.event_type || "").trim().toLowerCase();
    const detail = canonicalDetailSignature(ev);
    return `hk:${day}-${type}-${time}-${child}-${detail}`;
  };

  const getFingerprintKey = (ev: NormalisedEvent) => {
    const fingerprint = (ev.fingerprint || "").trim();
    if (!fingerprint) return null;
    const splitIndex = ev.raw_data?.split_index;
    if (typeof splitIndex === "number") return null;
    return `fp:${fingerprint}`;
  };

  const deriveKey = (ev: NormalisedEvent) =>
    getFingerprintKey(ev) ?? makeHeuristicKey(ev);

  const addEvent = (ev: NormalisedEvent, which: "famly" | "baby") => {
    const key = deriveKey(ev);
    if (!map.has(key)) {
      map.set(key, {
        key,
        dayLabel: ev.raw_data?.day_label || getDayIso(ev),
        dayIso: getDayIso(ev),
        timestamp: getSortTimestamp(ev),
      });
    }
    map.get(key)![which] = ev;
  };

  famlyEvents.forEach((ev) => {
    const splits = getEntrySplits(ev);
    const multiSplit = splits.length > 1;
    splits.forEach((entry, idx) => {
      const clone: NormalisedEvent = {
        ...ev,
        summary: entry.join(" - ") || ev.summary || ev.raw_text || "",
        raw_data: {
          ...(ev.raw_data || {}),
          detail_lines: entry,
          source_event_id: ev.raw_data?.source_event_id ?? ev.id,
          split_index: multiSplit ? idx : null,
        },
      };
      addEvent(clone, "famly");
    });
  });

  babyEvents.forEach((ev) => addEvent(ev, "baby"));

  return Array.from(map.values()).sort((a, b) => b.timestamp - a.timestamp);
};

const formatClock = (date: Date) =>
  date.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

const to24Hour = (token: string) => {
  const trimmed = token.trim();
  const match = trimmed.match(/^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$/i);
  if (!match) return trimmed;
  let hour = parseInt(match[1], 10);
  const minute = match[2] ?? "00";
  const meridiem = match[3]?.toLowerCase();
  if (meridiem === "pm" && hour < 12) hour += 12;
  if (meridiem === "am" && hour === 12) hour = 0;
  return `${hour.toString().padStart(2, "0")}:${minute}`;
};

const formatRange24 = (range: string) => {
  const parts = range
    .split(/(?:-|to)/i)
    .map((part) => part.trim())
    .filter(Boolean);
  if (parts.length === 2) {
    return `${to24Hour(parts[0])} - ${to24Hour(parts[1])}`;
  }
  if (parts.length === 1) {
    return to24Hour(parts[0]);
  }
  return range.trim();
};

const stripTimePrefix = (
  text: string,
): { remaining: string | null; range: string | null } => {
  const trimmed = text.trim();
  const match = trimmed.match(
    /^(\d{1,2}:\d{2}(?:\s*[AaPp][Mm])?)(?:\s*(?:-|to)\s*(\d{1,2}:\d{2}(?:\s*[AaPp][Mm])?))?/i,
  );
  if (!match) {
    return { remaining: trimmed || null, range: null };
  }
  const [, startPart, endPart] = match;
  const range = endPart ? `${startPart} - ${endPart}` : startPart;
  const remainder = trimmed.slice(match[0].length).replace(/^[:\s-]+/, "");
  return { remaining: remainder || null, range };
};

const normalizeLineForDuplicate = (text: string) => {
  const { remaining } = stripTimePrefix(text);
  const base = (remaining || text).toLowerCase();
  return base
    .replace(/\[sync\]/gi, "")
    .replace(/\([^)]*\)/g, "")
    .replace(/\s+/g, " ")
    .trim();
};

const diaperTokenLabel = (token: string) => {
  switch (token.toLowerCase()) {
    case "bm":
      return "BM";
    case "poop":
    case "poopy":
      return "Poopy";
    case "wet":
      return "Wet";
    case "dry":
      return "Dry";
    case "soiled":
      return "Soiled";
    case "dirty":
      return "Dirty";
    default:
      return token.charAt(0).toUpperCase() + token.slice(1).toLowerCase();
  }
};

const findDiaperTypeInText = (text?: string | null) => {
  if (!text) return null;
  const match = text.match(
    /\b(bm|wet|dry|poop(?:y)?|soiled|dirty)\b/i,
  );
  if (!match) return null;
  return diaperTokenLabel(match[1]);
};

const inferBabyDiaperType = (event: NormalisedEvent) => {
  const sources: Array<string | null | undefined> = [
    event.raw_data?.raw_text,
    event.summary,
    event.raw_text,
  ];
  for (const source of sources) {
    const type = findDiaperTypeInText(source);
    if (type) return type;
  }
  const detailLines = Array.isArray(event.raw_data?.detail_lines)
    ? event.raw_data!.detail_lines!
    : [];
  for (const line of detailLines) {
    const type = findDiaperTypeInText(line);
    if (type) return type;
  }
  return null;
};

const canonicalDetailSignature = (event: NormalisedEvent) => {
  const rawData = event.raw_data ?? {};
  const detailLines = Array.isArray(rawData.detail_lines)
    ? [...rawData.detail_lines]
    : [];
  const normalizedLines = detailLines
    .map((line) => {
      if (!line) return "";
      const stripped = stripTimePrefix(line);
      const candidate = stripped.remaining ?? line;
      return normalizeLineForDuplicate(candidate);
    })
    .filter(Boolean);

  const candidates = [
    normalizedLines.join("|"),
    rawData.original_title,
    rawData.note,
    event.summary,
    event.raw_text,
  ];

  for (const candidate of candidates) {
    if (!candidate) continue;
    const cleaned = normalizeLineForDuplicate(candidate);
    if (cleaned) {
      return cleaned;
    }
  }

  return "";
};

const extractEntryTimeToken = (event: NormalisedEvent): string => {
  const lines = Array.isArray(event.raw_data?.detail_lines)
    ? event.raw_data!.detail_lines!
    : [];
  for (const line of lines) {
    const match = line.match(/(\d{1,2}:\d{2}(?:\s*[AaPp][Mm])?)/);
    if (match) {
      return `${getDayIso(event)}T${to24Hour(match[1])}`;
    }
  }
  try {
    const date = new Date(event.start_time_utc);
    const hours = date.getUTCHours().toString().padStart(2, "0");
    const minutes = date.getUTCMinutes().toString().padStart(2, "0");
    return `${getDayIso(event)}T${hours}:${minutes}`;
  } catch {
    return `${getDayIso(event)}T00:00`;
  }
};

const duplicateKeyForEvent = (event: NormalisedEvent) => {
  const day = getDayIso(event);
  const type = (event.event_type || "").trim().toLowerCase();
  if (!day || !type) return null;
  const signature = canonicalDetailSignature(event);
  if (!signature) return null;
  return `${day}|${type}|${signature}`;
};

const EventTile: React.FC<{
  event?: NormalisedEvent;
  label: string;
  ignored?: boolean;
  duplicate?: boolean;
}> = ({ event, label, ignored = false, duplicate = false }) => {
  if (!event) {
    return <div className="event-card event-card--placeholder">No entry</div>;
  }

  const isBaby = label === "Baby Connect";

  const effectiveType =
    label === "Famly"
      ? inferFamlyEventType(event) || event.event_type
      : event.event_type;

  const icon = getIcon(effectiveType, label);
  const displayTitle = getEventTitle(effectiveType, label);

  const detailLines = Array.isArray(event.raw_data?.detail_lines)
    ? [...event.raw_data!.detail_lines!]
    : [];

  const rawNoteText = event.raw_data?.note?.trim() || null;

  const normalizeBaseValue = (value: string | null) =>
    value
      ? value
          .replace(/\[sync\]/gi, "")
          .replace(/\s+/g, " ")
          .trim()
          .toLowerCase()
      : null;

  const normalizedNoteBase = normalizeBaseValue(rawNoteText);

  let displayTime = formatClock(
    new Date(
      event.source_system === "baby_connect" && event.end_time_utc
        ? event.end_time_utc
        : event.start_time_utc,
    ),
  );

  const isBabyDiaper =
    isBaby &&
    ((effectiveType || "").toLowerCase().includes("nappy") ||
      (effectiveType || "").toLowerCase().includes("diaper"));

  const cleanedEntries: string[] = [];
  detailLines.forEach((line) => {
    if (!line) return;
    const { remaining, range } = stripTimePrefix(line);
    if (range) {
      displayTime = formatRange24(range);
    }
    if (!remaining) {
      return;
    }
    cleanedEntries.push(remaining);
  });

  const isSignEvent = SIGN_EVENT_TYPES.includes(
    (effectiveType || "").toLowerCase(),
  );

  const baseEntries =
    cleanedEntries.length > 0
      ? cleanedEntries.map((line, idx) => ({
          key: `${event.id}-${idx}`,
          text: applyDegreeSymbol(line),
        }))
      : [
          {
            key: `${event.id}-summary`,
            text: applyDegreeSymbol(
              isSignEvent
                ? event.raw_data?.original_title ||
                    event.summary ||
                    event.raw_text ||
                    ""
                : event.summary || event.raw_text || "",
            ),
          },
        ];

  let entries = baseEntries;

  if (isBabyDiaper) {
    const diaperType = inferBabyDiaperType(event);
    if (diaperType) {
      entries = [
        {
          key: `${event.id}-diaper-type`,
          text: diaperType,
        },
      ];
    }
  }

  const isBabySolid =
    isBaby &&
    ["solid", "meal", "meals"].includes(
      (effectiveType || "").toLowerCase(),
    );

  if (isBabySolid) {
    entries = [
      {
        key: `${event.id}-solid-label`,
        text: "Food",
      },
    ];
  }

  // For ANY Baby Connect event, inline the note as a normal list entry
  // instead of showing it as a separate italic note.
  if (isBaby && rawNoteText) {
    const normalizedNote = normalizeBaseValue(
      applyDegreeSymbol(rawNoteText),
    );
    const hasEquivalent = entries.some((entry) => {
      return normalizeBaseValue(entry.text) === normalizedNote;
    });

    if (!hasEquivalent) {
      entries.push({
        key: `${event.id}-note-inline`,
        text: applyDegreeSymbol(rawNoteText),
      });
    }
  }

  const noteText = isBaby ? null : rawNoteText;

  const normalizeValue = (value: string | null) =>
    value
      ? value
          .replace(/\[sync\]/gi, "")
          .replace(/\s+/g, " ")
          .trim()
          .toLowerCase()
      : null;

  const noteMatchesEntry =
    noteText &&
    entries.some(
      (entry) =>
        normalizeValue(entry.text) ===
        normalizeValue(applyDegreeSymbol(noteText)),
    );

  const noteToShow = noteMatchesEntry
    ? null
    : noteText
    ? applyDegreeSymbol(noteText)
    : null;

  const cardClasses = ["event-card"];
  if (ignored) {
    cardClasses.push("event-card--ignored");
  }
  if (duplicate) {
    cardClasses.push("event-card--duplicate");
  }

  return (
    <div className={cardClasses.join(" ")}>
      <div className="event-card__meta">
        <p className="event-card__title-line">
          <span className="event-card__title">{displayTitle}</span>
          <span className="event-card__time">{displayTime}</span>
        </p>
        <div className="event-card__meta-icons">
          {ignored && <span className="event-card__badge">Ignored</span>}
          {duplicate && (
            <span className="event-card__badge event-card__badge--warning">
              Possible duplicate
            </span>
          )}
          {icon && <img src={icon} className="event-card__icon" alt="" />}
        </div>
      </div>
      <ul className="event-card__list">
        {entries.map((entry) => (
          <li key={entry.key} className="event-card__summary">
            {entry.text}
          </li>
        ))}
      </ul>
      {!isBaby && noteToShow && (
        <p className="event-card__note">{noteToShow}</p>
      )}
    </div>
  );
};

export const EventComparison: React.FC<Props> = ({
  famlyEvents,
  babyEvents,
  dateFormat,
  onSyncEvent,
  onToggleIgnore,
  syncingEventId = null,
  isBulkSyncing = false,
  showMissingOnly = false,
  onToggleMissing,
  controlsSlot,
  failedEventIds = [],
  selectedEventIds = [],
  onToggleSelection,
}) => {
  const rows = useMemo(
    () => buildPairs(famlyEvents, babyEvents),
    [famlyEvents, babyEvents],
  );

  const stats = useMemo(() => {
    const famlyTotal = famlyEvents.length;
    const babyTotal = babyEvents.length;
    const missing = rows.filter(
      (row) => row.famly && !row.baby && !row.famly?.ignored,
    ).length;
    const matched = rows.filter((row) => row.famly && row.baby).length;
    return { famlyTotal, babyTotal, missing, matched };
  }, [famlyEvents, babyEvents, rows]);

  const duplicateFamlyIds = useMemo(() => {
    const keyToEvents = new Map<string, NormalisedEvent[]>();

    rows.forEach((row) => {
      if (!row.famly) return;
      const key = duplicateKeyForEvent(row.famly);
      if (!key) return;
      if (!keyToEvents.has(key)) {
        keyToEvents.set(key, []);
      }
      keyToEvents.get(key)!.push(row.famly);
    });

    const duplicates = new Set<number>();
    keyToEvents.forEach((events) => {
      if (events.length <= 1) return;
      const uniqueTimes = new Set(
        events.map((ev) => extractEntryTimeToken(ev)),
      );
      if (uniqueTimes.size <= 1) return;
      events.forEach((ev) => {
        if (typeof ev.id === "number") {
          duplicates.add(ev.id);
        }
      });
    });

    return duplicates;
  }, [rows]);

  const filteredRows = showMissingOnly
    ? rows.filter((row) => row.famly && !row.baby && !row.famly?.ignored)
    : rows;

  const grouped = filteredRows.reduce<Record<string, PairedRow[]>>(
    (acc, row) => {
      acc[row.dayIso] = acc[row.dayIso] || [];
      acc[row.dayIso].push(row);
      return acc;
    },
    {},
  );

  const orderedGroups = Object.entries(grouped).sort(
    (a, b) => (b[1][0]?.timestamp || 0) - (a[1][0]?.timestamp || 0),
  );

  return (
    <>
      <div className="comparison-summary">
        <div>
          <p className="comparison-summary__label">Famly entries</p>
          <p className="comparison-summary__value">{stats.famlyTotal}</p>
        </div>
        <div>
          <p className="comparison-summary__label">Baby Connect entries</p>
          <p className="comparison-summary__value">{stats.babyTotal}</p>
        </div>
        <div>
          <p className="comparison-summary__label">Matched</p>
          <p className="comparison-summary__value">{stats.matched}</p>
        </div>
        <div>
          <p className="comparison-summary__label">Missing in Baby Connect</p>
          <p className="comparison-summary__value comparison-summary__value--alert">
            {stats.missing}
          </p>
        </div>
      </div>

      {controlsSlot && <div className="extra-controls">{controlsSlot}</div>}

      {showMissingOnly && filteredRows.length === 0 && (
        <p className="no-missing">No missing entries</p>
      )}

      {orderedGroups.map(([dayIso, entries]) => {
        const display = formatDayDisplay(
          dayIso,
          entries[0]?.dayLabel || dayIso,
          dateFormat,
        );

        return (
          <section key={dayIso} className="day-section">
            <div className="day-columns-header">
              <span className="day-columns-header__label">Famly</span>
              <span className="day-columns-header__day">{display}</span>
              <span className="day-columns-header__label day-columns-header__label--right">
                Baby Connect
              </span>
            </div>
            {entries.map((row) => {
              const isMatched = !!row.famly && !!row.baby;
              const famlyEventId =
                row.famly?.raw_data?.source_event_id ?? row.famly?.id;

              const showArrow =
                !!famlyEventId &&
                !!row.famly &&
                !row.baby &&
                !!onSyncEvent;

              const isSyncingThis =
                !!famlyEventId && syncingEventId === famlyEventId;

              const isFailed =
                !!famlyEventId && failedEventIds.includes(famlyEventId);

              const famlyIgnored = !!row.famly?.ignored;

              const famlyDuplicate =
                !!row.famly?.id && duplicateFamlyIds.has(row.famly.id);

              const canToggleIgnore = !!famlyEventId && !!onToggleIgnore;
              const isSelectable =
                !!famlyEventId && !row.baby && !famlyIgnored && !!onToggleSelection;
              const isSelected =
                isSelectable && famlyEventId && selectedEventIds.includes(famlyEventId);

              const arrowDisabled =
                !showArrow ||
                isBulkSyncing ||
                (syncingEventId !== null && !isSyncingThis);

              const arrowClasses = ["arrow-pill"];
              if (isMatched) {
                arrowClasses.push("arrow-pill--matched");
              }
              if (isFailed) {
                arrowClasses.push("arrow-pill--failed");
              }

              const glyph = isFailed
                ? "!"
                : isSyncingThis
                ? "…"
                : showArrow
                ? "→"
                : isMatched
                ? "✓"
                : "";

              return (
                <div
                  key={row.key}
                  className={`pair-row${
                    isMatched ? " pair-row--matched" : ""
                  }${isFailed ? " pair-row--failed" : ""}${
                    famlyIgnored ? " pair-row--ignored" : ""
                  }`}
                >
                  <div
                    className={`pair-row__tile-wrapper${
                      isSelectable ? " pair-row__tile-wrapper--selectable" : ""
                    }${isSelected ? " pair-row__tile-wrapper--selected" : ""}`}
                    onClick={() => {
                      if (famlyEventId && isSelectable) {
                        onToggleSelection?.(famlyEventId, !isSelected);
                      }
                    }}
                    role={isSelectable ? "button" : undefined}
                    aria-pressed={isSelectable ? isSelected : undefined}
                    tabIndex={isSelectable ? 0 : undefined}
                    onKeyDown={(event) => {
                      if (
                        isSelectable &&
                        famlyEventId &&
                        (event.key === " " || event.key === "Enter")
                      ) {
                        event.preventDefault();
                        onToggleSelection?.(famlyEventId, !isSelected);
                      }
                    }}
                  >
                    <EventTile
                      event={row.famly}
                      label="Famly"
                      ignored={famlyIgnored}
                      duplicate={famlyDuplicate}
                    />
                  </div>
                  <div className="pair-row__actions">
                    <button
                      type="button"
                      className={arrowClasses.join(" ")}
                      disabled={arrowDisabled}
                      onClick={() => {
                        if (showArrow && famlyEventId) {
                          onSyncEvent?.(famlyEventId);
                        }
                      }}
                      aria-label={
                        isFailed
                          ? "Previous sync attempt failed"
                          : isSyncingThis
                          ? "Syncing entry"
                          : showArrow
                          ? "Create this Famly entry in Baby Connect"
                          : isMatched
                          ? "Entry already synced"
                          : "No action"
                      }
                    >
                      {glyph}
                    </button>
                    {canToggleIgnore && (
                      <button
                        type="button"
                        className={`ignore-pill${
                          famlyIgnored ? " ignore-pill--active" : ""
                        }`}
                        onClick={() =>
                          famlyEventId &&
                          onToggleIgnore?.(famlyEventId, !famlyIgnored)
                        }
                      >
                        {famlyIgnored ? "Ignored" : "Ignore"}
                      </button>
                    )}
                  </div>
                  <EventTile event={row.baby} label="Baby Connect" />
                </div>
              );
            })}
          </section>
        );
      })}
    </>
  );
};
