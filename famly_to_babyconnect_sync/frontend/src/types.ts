export type ServiceName = "famly" | "baby_connect";

export type ServiceStatus = "idle" | "ok" | "error";

export interface ConnectionStatus {
  service: ServiceName;
  email: string | null;
  status: ServiceStatus;
  message?: string;
  lastConnectedAt?: string | null;
  lastScrapedAt?: string | null;
}

export interface NormalisedEvent {
  id: number;
  source_system: ServiceName;
  child_name: string;
  event_type: string;
  start_time_utc: string;
  end_time_utc?: string | null;
  fingerprint?: string | null;
  matched: boolean;
  ignored?: boolean;
  summary?: string | null;
  raw_text?: string | null;
  raw_data?: {
    day_label?: string;
    day_date_iso?: string | null;
    detail_lines?: string[];
    child_full_name?: string | null;
    event_datetime_iso?: string | null;
    end_event_datetime_iso?: string | null;
    original_title?: string | null;
    note?: string | null;
    author?: string | null;
    split_index?: number | null;
    source_event_id?: number | null;
  } | null;
}

export interface SyncPreferences {
  include_types: string[];
}
