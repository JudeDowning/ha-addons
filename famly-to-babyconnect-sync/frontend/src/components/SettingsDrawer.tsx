import React, { useEffect, useMemo, useState } from "react";
import { ConnectionStatus, ServiceName, SyncPreferences } from "../types";
import { ConnectionCard } from "./ConnectionCard";
import {
  fetchEventMapping,
  fetchFamlyEventTypes,
  fetchSyncPreferences,
  saveEventMapping,
  saveSyncPreferences,
  fetchDebugEvents,
  clearScrapedEvents,
} from "../api";

type DateFormat = "weekday-mon-dd" | "weekday-dd-mon";

interface Props {
  open: boolean;
  onClose: () => void;
  statuses: ConnectionStatus[];
  onTestConnection: (service: ServiceName) => void;
  onCredentialsSaved: (service: ServiceName) => void;
  dateFormat: DateFormat;
  onChangeDateFormat: (format: DateFormat) => void;
  syncPreferences: SyncPreferences;
  onSyncPreferencesSaved: (prefs: SyncPreferences) => Promise<void> | void;
}

const canonicalOptions = [
  { value: "solid", label: "Solid" },
  { value: "nappy", label: "Nappy" },
  { value: "sleep", label: "Sleep" },
  // { value: "sign in", label: "Sign in" },
  // { value: "sign out", label: "Sign out" },
  { value: "message", label: "Message" },
  { value: "bottle", label: "Bottle" },
  { value: "medicine", label: "Medicine" },
  { value: "temperature", label: "Temperature" },
];
const canonicalLabel = (value: string) =>
  canonicalOptions.find((option) => option.value === value)?.label || value;

export const SettingsDrawer: React.FC<Props> = ({
  open,
  onClose,
  statuses,
  onTestConnection,
  onCredentialsSaved,
  dateFormat,
  onChangeDateFormat,
  syncPreferences,
  onSyncPreferencesSaved,
}) => {
  const [eventMap, setEventMap] = useState<Array<{ raw: string; target: string }>>([]);
  const [famlyTypes, setFamlyTypes] = useState<string[]>([]);
  const [isMappingLoading, setIsMappingLoading] = useState(false);
  const [isMappingSaving, setIsMappingSaving] = useState(false);
  const [mappingError, setMappingError] = useState<string | null>(null);
  const [syncPrefs, setSyncPrefs] = useState<SyncPreferences>(syncPreferences);
  const [isSyncPrefsLoading, setIsSyncPrefsLoading] = useState(false);
  const [isSyncPrefsSaving, setIsSyncPrefsSaving] = useState(false);
  const [syncPrefsError, setSyncPrefsError] = useState<string | null>(null);
  const [debugData, setDebugData] = useState<{ famly?: any; baby_connect?: any }>({});
  const [debugError, setDebugError] = useState<string | null>(null);
  const [isDebugLoading, setIsDebugLoading] = useState(false);
  const [isClearingData, setIsClearingData] = useState(false);
  const [clearDataStatus, setClearDataStatus] = useState<string | null>(null);

  const normaliseTarget = (value: string) => {
    const lower = (value || "").toLowerCase();
    const match =
      canonicalOptions.find(
        (option) =>
          option.value === lower || option.label.toLowerCase() === lower,
      )?.value || lower || "solid";
    return match;
  };

  useEffect(() => {
    if (!open) return;
    (async () => {
      setIsMappingLoading(true);
      setMappingError(null);
      setIsSyncPrefsLoading(true);
      setSyncPrefsError(null);
      try {
        const [mapping, types, prefs] = await Promise.all([
          fetchEventMapping(),
          fetchFamlyEventTypes(),
          fetchSyncPreferences(),
        ]);
        const rows = Object.entries(mapping).map(([raw, target]) => ({
          raw,
          target: normaliseTarget(target),
        }));
        setEventMap(rows.length ? rows : [{ raw: "", target: "solid" }]);
        setFamlyTypes(types);
        setSyncPrefs(prefs);
        onSyncPreferencesSaved(prefs);
      } catch (err) {
        setMappingError(err instanceof Error ? err.message : "Failed to load mapping");
        setEventMap([{ raw: "", target: "solid" }]);
        setFamlyTypes([]);
        setSyncPrefs(syncPreferences);
        setSyncPrefsError(err instanceof Error ? err.message : "Failed to load sync preferences");
      } finally {
        setIsMappingLoading(false);
        setIsSyncPrefsLoading(false);
      }
    })();
  }, [open]);

  useEffect(() => {
    if (open) {
      setSyncPrefs(syncPreferences);
    }
  }, [syncPreferences, open]);

  const availableRawOptions = useMemo(() => {
    return (currentRaw: string) => {
      const used = eventMap
        .map((row) => row.raw.trim())
        .filter(Boolean)
        .filter((raw) => raw !== currentRaw);
      const usedSet = new Set(used);
      const options = famlyTypes.filter((type) => !usedSet.has(type));
      if (currentRaw && !options.includes(currentRaw)) {
        options.unshift(currentRaw);
      }
      return options;
    };
  }, [eventMap, famlyTypes]);

  const firstAvailableRaw = useMemo(() => {
    const used = new Set(eventMap.map((row) => row.raw.trim()).filter(Boolean));
    return famlyTypes.find((type) => !used.has(type));
  }, [eventMap, famlyTypes]);

  const updateRow = (index: number, field: "raw" | "target", value: string) => {
    setEventMap((rows) =>
      rows.map((row, idx) => (idx === index ? { ...row, [field]: value } : row)),
    );
  };


  const handleLoadDebug = async () => {
    setIsDebugLoading(true);
    setDebugError(null);
    setClearDataStatus(null);
    try {
      const [famly, bc] = await Promise.all([
        fetchDebugEvents("famly"),
        fetchDebugEvents("baby_connect"),
      ]);
      setDebugData({ famly, baby_connect: bc });
    } catch (err) {
      setDebugError(err instanceof Error ? err.message : "Failed to load debug data");
    } finally {
      setIsDebugLoading(false);
    }
  };

  const handleClearScrapedData = async () => {
    const confirmed = window.confirm(
      "This will delete all scraped Famly/Baby Connect events stored locally. Credentials, mappings, and preferences will remain. Continue?",
    );
    if (!confirmed) return;
    setIsClearingData(true);
    setClearDataStatus(null);
    setDebugError(null);
    try {
      await clearScrapedEvents();
      setDebugData({});
      setClearDataStatus("Scraped data cleared.");
    } catch (err) {
      setClearDataStatus(err instanceof Error ? err.message : "Failed to clear scraped data");
    } finally {
      setIsClearingData(false);
    }
  };

  const addRow = () => {
    setEventMap((rows) => [...rows, { raw: firstAvailableRaw || "", target: "solid" }]);
  };

  const removeRow = (index: number) => {
    setEventMap((rows) => rows.filter((_, idx) => idx !== index));
  };

  const handleSaveMapping = async () => {
    const mapping = eventMap.reduce<Record<string, string>>((acc, row) => {
      const raw = row.raw.trim();
      if (!raw) return acc;
      acc[raw] = row.target;
      return acc;
    }, {});
    setIsMappingSaving(true);
    setMappingError(null);
    try {
      await saveEventMapping(mapping);
    } catch (err) {
      setMappingError(err instanceof Error ? err.message : "Failed to save mapping");
    } finally {
      setIsMappingSaving(false);
    }
  };

  const toggleSyncType = (value: string) => {
    setSyncPrefs((prev) => {
      const set = new Set(prev.include_types.map((item) => item.toLowerCase()));
      if (set.has(value.toLowerCase())) {
        const filtered = prev.include_types.filter(
          (item) => item.toLowerCase() !== value.toLowerCase(),
        );
        return { include_types: filtered };
      }
      return { include_types: [...prev.include_types, value.toLowerCase()] };
    });
  };

  const handleSaveSyncPrefs = async () => {
    setIsSyncPrefsSaving(true);
    setSyncPrefsError(null);
    try {
      const updated = await saveSyncPreferences(syncPrefs);
      setSyncPrefs(updated);
      await onSyncPreferencesSaved(updated);
    } catch (err) {
      setSyncPrefsError(err instanceof Error ? err.message : "Failed to save sync preferences");
    } finally {
      setIsSyncPrefsSaving(false);
    }
  };

  if (!open) return null;

  return (
    <div className="settings-overlay" onClick={onClose}>
      <div className="settings-panel" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2>Configuration</h2>
          <button className="status-card__btn" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="credential-card">
          <label htmlFor="date-format">Date display format</label>
          <select
            id="date-format"
            className="control-select"
            value={dateFormat}
            onChange={(e) => onChangeDateFormat(e.target.value as DateFormat)}
          >
            <option value="weekday-mon-dd">Mon Dec 01</option>
            <option value="weekday-dd-mon">Mon 01 Dec</option>
          </select>
        </div>
        <div className="credential-card">
          <h3>Sync-all filters</h3>
          <p style={{ marginTop: 0, color: "rgba(248,250,252,0.75)" }}>
            Select which event types are included when running Sync All.
          </p>
          {isSyncPrefsLoading ? (
            <p className="loading-text">Loading preferences…</p>
          ) : (
            <>
              <div className="sync-pref-grid">
                {canonicalOptions.map((option) => {
                  const selected = syncPrefs.include_types
                    .map((item) => item.toLowerCase())
                    .includes(option.value);
                  return (
                    <label
                      key={option.value}
                      className={`sync-pref-pill${selected ? " sync-pref-pill--selected" : ""}`}
                    >
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={() => toggleSyncType(option.value)}
                      />
                      <span>{option.label}</span>
                    </label>
                  );
                })}
              </div>
              <button
                className="credential-card__btn credential-card__btn--primary"
                style={{ alignSelf: "flex-start" }}
                onClick={handleSaveSyncPrefs}
                disabled={isSyncPrefsSaving}
              >
                {isSyncPrefsSaving ? "Saving…" : "Save sync filters"}
              </button>
              {syncPrefsError && <p className="error-text">{syncPrefsError}</p>}
            </>
          )}
        </div>
        <div className="credential-card">
          <h3>Scraped data (debug)</h3>
          <p className="status-card__meta">View raw rows the scraper stored in the local database.</p>
          <button
            className="credential-card__btn"
            onClick={handleClearScrapedData}
            disabled={isClearingData}
            style={{ marginBottom: "8px" }}
          >
            {isClearingData ? "Clearing…" : "Clear scraped data"}
          </button>
          <button
            className="credential-card__btn credential-card__btn--primary"
            onClick={handleLoadDebug}
            disabled={isDebugLoading}
          >
            {isDebugLoading ? "Loading…" : "Load scraped data"}
          </button>
          {clearDataStatus && (
            <p
              className={
                clearDataStatus.toLowerCase().includes("fail") ? "error-text" : "status-card__meta"
              }
            >
              {clearDataStatus}
            </p>
          )}
          {debugError && <p className="error-text">{debugError}</p>}
          {(debugData.famly || debugData.baby_connect) && (
            <div className="debug-panel">
              {["famly", "baby_connect"].map((source) => {
                const payload = debugData[source as "famly" | "baby_connect"];
                if (!payload) return null;
                return (
                  <details key={source} open>
                    <summary>
                      {source === "famly" ? "Famly events" : "Baby Connect events"} ({payload.count})
                    </summary>
                    <pre>{JSON.stringify(payload.events, null, 2)}</pre>
                  </details>
                );
              })}
            </div>
          )}
        </div>
        <div className="credential-card">
          <h3>Famly event mappings</h3>
          {isMappingLoading ? (
            <p className="loading-text">Loading mapping…</p>
          ) : (
            <>
              <div className="mapping-summary-grid">
                <div>
                  <p className="mapping-summary-title">Current mappings</p>
                  {eventMap.some((row) => row.raw.trim()) ? (
                    <ul className="mapping-summary">
                      {eventMap
                        .filter((row) => row.raw.trim())
                        .map((row, idx) => (
                          <li key={`summary-${idx}`}>
                            <span className="mapping-summary-raw">{row.raw.trim()}</span>
                            <span className="mapping-summary-arrow">→</span>
                            <span className="mapping-summary-target">
                              {canonicalLabel(row.target)}
                            </span>
                          </li>
                        ))}
                    </ul>
                  ) : (
                    <p className="loading-text">No mappings yet</p>
                  )}
                </div>
                <div>
                  <p className="mapping-summary-title">Unmapped Famly events</p>
                  {firstAvailableRaw ? (
                    <ul className="mapping-unmapped">
                      {famlyTypes
                        .filter((type) => !eventMap.some((row) => row.raw.trim() === type))
                        .map((type) => (
                          <li key={`unmapped-${type}`}>{type}</li>
                        ))}
                    </ul>
                  ) : (
                    <p className="loading-text">All known events mapped</p>
                  )}
                </div>
              </div>
              {eventMap.map((row, idx) => (
                <div
                  key={idx}
                  style={{
                    display: "flex",
                    gap: "8px",
                    alignItems: "center",
                    marginBottom: "6px",
                  }}
                >
                  <select
                    className="control-select"
                    value={row.raw}
                    onChange={(e) => updateRow(idx, "raw", e.target.value)}
                  >
                    <option value="">Select Famly event…</option>
                    {availableRawOptions(row.raw).map((type) => (
                      <option key={type} value={type}>
                        {type}
                      </option>
                    ))}
                  </select>
                  <select
                    className="control-select"
                    value={row.target}
                    onChange={(e) => updateRow(idx, "target", e.target.value)}
                  >
                    {canonicalOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                  <button className="status-card__btn" onClick={() => removeRow(idx)}>
                    ✕
                  </button>
                </div>
              ))}
              <div style={{ display: "flex", gap: "8px" }}>
                <button
                  className="credential-card__btn"
                  onClick={addRow}
                  disabled={!firstAvailableRaw}
                >
                  Add row
                </button>
                <button
                  className="credential-card__btn credential-card__btn--primary"
                  onClick={handleSaveMapping}
                  disabled={isMappingSaving}
                >
                  {isMappingSaving ? "Saving…" : "Save mapping"}
                </button>
              </div>
              {mappingError && <p className="error-text">{mappingError}</p>}
            </>
          )}
        </div>
        {statuses.map((status) => (
          <ConnectionCard
            key={status.service}
            status={status}
            onTestConnection={onTestConnection}
            onSaved={onCredentialsSaved}
          />
        ))}
      </div>
    </div>
  );
};
