import { ServiceName, SyncPreferences } from "./types";

interface CredentialResponse {
  service_name: ServiceName;
  email: string | null;
}

export const INGRESS_PREFIX = (() => {
  if (typeof window === "undefined") return "";
  const match = window.location.pathname.match(/^\/api\/hassio_ingress\/[A-Za-z0-9_-]+/);
  return match ? match[0] : "";
})();

export function apiUrl(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  if (!path.startsWith("/")) {
    return `${INGRESS_PREFIX}/${path}`;
  }
  return `${INGRESS_PREFIX}${path}`;
}

export function assetUrl(path: string): string {
  if (!path.startsWith("/")) {
    path = `/${path}`;
  }
  return `${INGRESS_PREFIX}${path}`;
}

async function handleResponse(res: Response) {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = body?.detail || res.statusText || "Request failed";
    throw new Error(detail);
  }
  return (await res.json()) as CredentialResponse;
}

export async function loadCredentials(service: ServiceName): Promise<CredentialResponse> {
  const res = await fetch(apiUrl(`/api/credentials/${service}`));
  return handleResponse(res);
}

export async function saveCredentials(
  service: ServiceName,
  email: string,
  password: string,
): Promise<CredentialResponse> {
  const res = await fetch(apiUrl(`/api/credentials/${service}`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return handleResponse(res);
}

export async function testCredentials(service: ServiceName): Promise<void> {
  const res = await fetch(apiUrl(`/api/credentials/${service}/test`), { method: "POST" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail || "Failed to test credentials");
  }
}

export async function fetchEventMapping(): Promise<Record<string, string>> {
  const res = await fetch(apiUrl("/api/settings/event-mapping"));
  if (!res.ok) {
    throw new Error("Failed to load event mapping");
  }
  const data = await res.json();
  return data.mapping || {};
}

export async function saveEventMapping(mapping: Record<string, string>): Promise<void> {
  const res = await fetch(apiUrl("/api/settings/event-mapping"), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mapping }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail || "Failed to save mapping");
  }
}

export async function fetchFamlyEventTypes(): Promise<string[]> {
  const res = await fetch(apiUrl("/api/settings/famly-event-types"));
  if (!res.ok) {
    throw new Error("Failed to load Famly event types");
  }
  const data = await res.json();
  return Array.isArray(data.types) ? data.types : [];
}

export async function syncEventsToBabyConnect(eventIds: number[]): Promise<any> {
  if (!eventIds.length) return { created: 0, synced_event_ids: [] };
  const res = await fetch(apiUrl("/api/sync/baby_connect/entries"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ event_ids: eventIds }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail || "Failed to sync entry to Baby Connect");
  }
  return res.json();
}

export async function fetchMissingEventIds(): Promise<number[]> {
  const res = await fetch(apiUrl("/api/events/missing"));
  if (!res.ok) {
    throw new Error("Failed to load missing events");
  }
  const data = await res.json();
  return Array.isArray(data.missing_event_ids) ? data.missing_event_ids : [];
}

export async function syncAllMissingEvents(): Promise<any> {
  const res = await fetch(apiUrl("/api/sync/missing"), { method: "POST" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail || "Failed to sync missing entries");
  }
  return res.json();
}

export async function fetchSyncPreferences(): Promise<SyncPreferences> {
  const res = await fetch(apiUrl("/api/settings/sync-preferences"));
  if (!res.ok) {
    throw new Error("Failed to load sync preferences");
  }
  const data = await res.json();
  const includeTypes = Array.isArray(data.include_types)
    ? data.include_types
    : Array.isArray(data.preferences?.include_types)
    ? data.preferences.include_types
    : [];
  return { include_types: includeTypes };
}

export async function saveSyncPreferences(
  prefs: SyncPreferences,
): Promise<SyncPreferences> {
  const res = await fetch(apiUrl("/api/settings/sync-preferences"), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(prefs),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail || "Failed to save sync preferences");
  }
  const data = await res.json();
  if (data.preferences && Array.isArray(data.preferences.include_types)) {
    return { include_types: data.preferences.include_types };
  }
  if (Array.isArray(data.include_types)) {
    return { include_types: data.include_types };
  }
  return prefs;
}

export async function fetchDebugEvents(source: ServiceName): Promise<any> {
  const res = await fetch(apiUrl(`/api/debug/events?source=${source}`));
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail || "Failed to load debug events");
  }
  return res.json();
}

interface ScrapeProgressSnapshot {
  service: string;
  total: number;
  processed: number;
  message?: string;
}

export async function clearScrapedEvents(): Promise<void> {
  const res = await fetch(apiUrl("/api/debug/events/clear"), { method: "POST" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail || "Failed to clear scraped data");
  }
}

export async function fetchScrapeProgress(): Promise<Record<string, ScrapeProgressSnapshot>> {
  const res = await fetch(apiUrl("/api/scrape/progress"));
  if (!res.ok) {
    throw new Error("Failed to load scrape progress");
  }
  return res.json();
}

export async function setEventIgnored(eventId: number, ignored: boolean): Promise<void> {
  const res = await fetch(apiUrl(`/api/events/${eventId}/ignore`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ignored }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail || "Failed to update ignore state");
  }
}
