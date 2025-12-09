import React, { useMemo } from "react";
import { NormalisedEvent } from "../types";
import { assetUrl } from "../api";

interface Props {
  title: string;
  events: NormalisedEvent[];
}

interface DayGroup {
  dateLabel: string;
  dateKey: string;
  events: NormalisedEvent[];
  timestamp: number;
}

const formatDateLabel = (ev: NormalisedEvent) => {
  const label = ev.raw_data?.day_label;
  if (label) return label;
  const date = new Date(ev.start_time_utc);
  return date.toLocaleDateString(undefined, {
    weekday: "long",
    month: "short",
    day: "numeric",
  });
};

const formatTime = (iso: string) => {
  const d = new Date(iso);
  return d.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  });
};

const getEventTime = (ev: NormalisedEvent) => {
  if (ev.raw_data?.author) {
    return ev.raw_data.author;
  }
  return formatTime(ev.start_time_utc);
};

const dedupeSequential = (lines: string[]) => {
  const result: string[] = [];
  lines.forEach((line) => {
    if (!line) return;
    if (result[result.length - 1] === line) return;
    result.push(line);
  });
  return result;
};

const ICON_MAP: Record<string, string> = {
  nappy: assetUrl("/icons/diapers_v2.svg"),
  diaper: assetUrl("/icons/diapers_v2.svg"),
  "nappy change": assetUrl("/icons/diapers_v2.svg"),
  bottle: assetUrl("/icons/bib_v2.svg"),
  solid: assetUrl("/icons/eat_v2.svg"),
  meal: assetUrl("/icons/eat_v2.svg"),
  meals: assetUrl("/icons/eat_v2.svg"),
  sleep: assetUrl("/icons/sleep_v2.svg"),
  medicine: assetUrl("/icons/medicine_v2.svg"),
  temperature: assetUrl("/icons/temperature_v2.svg"),
  bath: assetUrl("/icons/bath_v2.svg"),
  potty: assetUrl("/icons/potty_v2.svg"),
};

const getIconForType = (type: string | undefined) => {
  if (!type) return null;
  const key = type.toLowerCase();
  if (ICON_MAP[key]) {
    return ICON_MAP[key];
  }
  return null;
};

const SectionHeading: React.FC<{ title: string; type?: string }> = ({ title, type }) => {
  const iconSrc = getIconForType(type || title);
  return (
    <h5 className="font-semibold flex items-center gap-2">
      {iconSrc && (
        <img
          src={iconSrc}
          alt=""
          style={{ width: 50, height: 50, objectFit: "contain" }}
        />
      )}
      {title}
    </h5>
  );
};

const classifyEvents = (dayEvents: NormalisedEvent[]) => {
    const lower = (value: string) => value.toLowerCase();
    const nappy = dayEvents.filter((ev) => lower(ev.event_type).includes("nappy"));
    const meals = dayEvents.filter((ev) => lower(ev.event_type).includes("meal"));
    const sleep = dayEvents.filter((ev) => lower(ev.event_type).includes("sleep"));
    const others = dayEvents.filter(
      (ev) =>
        !nappy.includes(ev) &&
        !meals.includes(ev) &&
        !sleep.includes(ev) &&
        !lower(ev.event_type).includes("expected pick up"),
    );
    return { nappy, meals, sleep, others };
  };

export const EventsColumn: React.FC<Props> = ({ title, events }) => {
  const childHeader = events[0]?.raw_data?.child_full_name || events[0]?.child_name || title;

  const dayGroups = useMemo(() => {
    const map = new Map<string, DayGroup>();
    events.forEach((ev) => {
      const dateLabel = formatDateLabel(ev);
      const dateKey = ev.raw_data?.day_date_iso || dateLabel;
      const timestamp = new Date(ev.raw_data?.day_date_iso || ev.start_time_utc).getTime();
      if (!map.has(dateKey)) {
        map.set(dateKey, { dateLabel, dateKey, events: [], timestamp });
      }
      map.get(dateKey)!.events.push(ev);
    });
    return Array.from(map.values()).sort((a, b) => b.timestamp - a.timestamp);
  }, [events]);

  const renderNappy = (nappyEvents: NormalisedEvent[]) => {
    if (!nappyEvents.length) return null;
    return (
      <div>
        <SectionHeading title="Nappy change" type="nappy" />
        <ul className="text-sm space-y-1">
          {nappyEvents.map((ev) => {
            const lines = ev.raw_data?.detail_lines;
            const description = lines && lines.length ? lines.join(" - ") : ev.raw_data?.note || ev.summary || ev.raw_text || "";
            const time = getEventTime(ev);
            return (
              <li key={ev.id}>
                {time}
                {description ? ` - ${description}` : ""}
              </li>
            );
          })}
        </ul>
      </div>
    );
  };

  const renderMeals = (mealEvents: NormalisedEvent[]) => {
    if (!mealEvents.length) return null;
    const lines = mealEvents.flatMap((ev) => {
      if (ev.raw_data?.detail_lines?.length) {
        return ev.raw_data.detail_lines;
      }
      const desc = ev.raw_data?.note || ev.summary || ev.raw_text || "";
      return [getEventTime(ev), desc].filter(Boolean);
    });
    const deduped = dedupeSequential(lines);
    const items: { time: string; desc: string }[] = [];
    for (let i = 0; i < deduped.length; i += 2) {
      const timeLine = deduped[i];
      const desc = deduped[i + 1] ?? "";
      if (!timeLine) continue;
      items.push({ time: timeLine, desc });
    }
    if (!items.length) return null;
    return (
      <div>
        <SectionHeading title="Meals" type="solid" />
        <ul className="text-sm space-y-1">
          {items.map((item, idx) => (
            <li key={`${item.time}-${idx}`}>
              {item.time}
              {item.desc ? ` - ${item.desc}` : null}
            </li>
          ))}
        </ul>
      </div>
    );
  };

  const renderSleep = (sleepEvents: NormalisedEvent[]) => {
    if (!sleepEvents.length) return null;
    const stripPrefix = (summary: string | undefined | null) => {
      if (!summary) return "";
      return summary.replace(/^.*Sleep:\s*/, "");
    };
    return (
      <div>
        <SectionHeading title="Sleep" type="sleep" />
        <ul className="text-sm space-y-1">
          {sleepEvents.map((ev) => (
            <li key={ev.id}>
              {ev.raw_data?.author
                ? `${ev.raw_data.author} - ${
                    ev.raw_data?.note || stripPrefix(ev.summary ?? ev.raw_text ?? undefined)
                  }`
                : stripPrefix(ev.summary ?? ev.raw_text ?? undefined)}
            </li>
          ))}
        </ul>
      </div>
    );
  };

  const cleanEventLabel = (ev: NormalisedEvent) => {
    const label = ev.event_type.replace(ev.child_name, "").replace(/^[-–]\s*/, "").trim();
    if (label) {
      return label;
    }
    const summary = ev.summary || ev.raw_text || "";
    if (summary.includes(":")) {
      return summary.split(":").slice(1).join(":").trim();
    }
    return summary || ev.event_type;
  };

  const renderOthers = (otherEvents: NormalisedEvent[]) => {
    if (!otherEvents.length) return null;
    const sorted = [...otherEvents].sort(
      (a, b) => new Date(a.start_time_utc).getTime() - new Date(b.start_time_utc).getTime(),
    );
    return (
      <ul className="text-sm space-y-1">
        {sorted.map((ev) => {
          const icon = getIconForType(ev.event_type);
          return (
            <li key={ev.id} className="flex items-center gap-2">
              {icon && (
                <img
                  src={icon}
                  alt=""
                  style={{ width: 50, height: 50, objectFit: "contain" }}
                />
              )}
              <span>
                {getEventTime(ev)} - {cleanEventLabel(ev)}
              </span>
            </li>
          );
        })}
      </ul>
    );
  };


  return (
    <div>
      <h3 className="font-semibold mb-2">{childHeader}</h3>
      <div className="space-y-6 max-h-[60vh] overflow-auto pr-2">
        {dayGroups.map((group) => {
          const { nappy, meals, sleep, others } = classifyEvents(group.events);
          return (
            <div key={group.dateKey} className="border-b pb-4 last:border-b-0 last:pb-0">
              <h4 className="font-semibold text-base mb-2">{group.dateLabel}</h4>
              <div className="space-y-3">
                {renderOthers(others)}
                {renderNappy(nappy)}
                {renderMeals(meals)}
                {renderSleep(sleep)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
