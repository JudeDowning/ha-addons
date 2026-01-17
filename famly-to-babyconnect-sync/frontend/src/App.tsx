import React, { useCallback, useEffect, useRef, useState } from "react";
import { ConnectionStatus, NormalisedEvent, ServiceName, SyncPreferences } from "./types";
import { SettingsDrawer } from "./components/SettingsDrawer";
import { EventComparison } from "./components/EventComparison";
import { ProgressOverlay } from "./components/ProgressOverlay";
import { SyncToast } from "./components/SyncToast";
import {
  syncEventsToBabyConnect,
  fetchMissingEventIds,
  syncAllMissingEvents,
  fetchSyncPreferences,
  apiUrl,
  fetchScrapeProgress,
  setEventIgnored,
} from "./api";

type ProgressService = ServiceName | "sync";

type DateFormat = "weekday-mon-dd" | "weekday-dd-mon";

type ProgressMode = "scrape" | "sync" | null;

type ProgressState = {
  mode: ProgressMode;
  visible: boolean;
  label: string;
  currentStep: number;
  totalSteps: number;
  famlyProcessed: number;
  famlyTotal: number;
  babyProcessed: number;
  babyTotal: number;
  syncCurrent: number;
  syncTotal: number;
};

const App: React.FC = () => {
  const [famlyStatus, setFamlyStatus] = useState<ConnectionStatus>({
    service: "famly",
    email: null,
    status: "idle",
    lastConnectedAt: null,
    lastScrapedAt: null,
  });
  const [bcStatus, setBcStatus] = useState<ConnectionStatus>({
    service: "baby_connect",
    email: null,
    status: "idle",
    lastConnectedAt: null,
    lastScrapedAt: null,
  });
  const [famlyEvents, setFamlyEvents] = useState<NormalisedEvent[]>([]);
  const [bcEvents, setBcEvents] = useState<NormalisedEvent[]>([]);
  const [missingEventIds, setMissingEventIds] = useState<number[]>([]);
  const [syncPreferences, setSyncPreferences] = useState<SyncPreferences>({ include_types: [] });
  const [isSyncing, setIsSyncing] = useState(false);
  const [scrapeDaysBack, setScrapeDaysBack] = useState(0);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [dateFormat, setDateFormat] = useState<DateFormat>("weekday-mon-dd");
  const [progress, setProgress] = useState<ProgressState>({
    mode: null,
    visible: false,
    label: "",
    currentStep: 0,
    totalSteps: 0,
    famlyProcessed: 0,
    famlyTotal: 0,
    babyProcessed: 0,
    babyTotal: 0,
    syncCurrent: 0,
    syncTotal: 0,
  });
  const [syncingEventId, setSyncingEventId] = useState<number | null>(null);
  const [syncAllInFlight, setSyncAllInFlight] = useState(false);
  const [showMissingOnly, setShowMissingOnly] = useState(false);
  const [failedEventIds, setFailedEventIds] = useState<number[]>([]);
  const [selectedEventIds, setSelectedEventIds] = useState<number[]>([]);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const pollersRef = useRef<{ [key in ProgressService]?: () => void }>({});

  const registerSyncFailure = useCallback((ids: number[]) => {
    if (!ids.length) return;
    setFailedEventIds((prev) => {
      const merged = new Set(prev);
      ids.forEach((id) => merged.add(id));
      return Array.from(merged);
    });
  }, []);

  const clearSyncFailures = useCallback((ids: number[]) => {
    if (!ids.length) return;
    setFailedEventIds((prev) => prev.filter((id) => !ids.includes(id)));
  }, []);

  const toggleSelectedEntry = useCallback((eventId: number, select: boolean) => {
    setSelectedEventIds((prev) => {
      if (select) {
        return prev.includes(eventId) ? prev : [...prev, eventId];
      }
      return prev.filter((id) => id !== eventId);
    });
  }, []);

  const handleClearSelection = () => {
    setSelectedEventIds([]);
  };

  const fetchStatus = async () => {
    const res = await fetch(apiUrl("/api/status"));
    const data = await res.json();

    setFamlyStatus({
      service: "famly",
      email: data.famly.email,
      status: data.famly.has_credentials ? "ok" : "idle",
      message: undefined,
      lastConnectedAt: data.famly.last_connected_at,
      lastScrapedAt: data.famly.last_scraped_at,
    });

    setBcStatus({
      service: "baby_connect",
      email: data.baby_connect.email,
      status: data.baby_connect.has_credentials ? "ok" : "idle",
      message: undefined,
      lastConnectedAt: data.baby_connect.last_connected_at,
      lastScrapedAt: data.baby_connect.last_scraped_at,
    });
  };

  const loadMissingEventIds = useCallback(async () => {
    try {
      const ids = await fetchMissingEventIds();
      setMissingEventIds(ids);
    } catch (error) {
      console.error("Failed to load missing events", error);
      setMissingEventIds([]);
    }
  }, []);

  const loadSyncPreferences = useCallback(async () => {
    try {
      const prefs = await fetchSyncPreferences();
      setSyncPreferences(prefs);
    } catch (error) {
      console.error("Failed to load sync preferences", error);
    }
  }, []);

  const fetchEvents = async () => {
    const [famlyRes, bcRes] = await Promise.all([
      fetch(apiUrl("/api/events?source=famly")),
      fetch(apiUrl("/api/events?source=baby_connect")),
    ]);
    const famlyData = await famlyRes.json();
    const bcData = await bcRes.json();
    setFamlyEvents(famlyData);
    setBcEvents(bcData);
    await loadMissingEventIds();
  };

  const handleRefresh = async () => {
    try {
      setIsRefreshing(true);
      await Promise.all([fetchStatus(), fetchEvents()]);
    } catch (error) {
      console.error("Failed to refresh data", error);
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchEvents();
    loadSyncPreferences();
  }, [loadSyncPreferences]);

  useEffect(() => {
    if (!missingEventIds.length) {
      setSelectedEventIds([]);
      return;
    }
    setSelectedEventIds((prev) => prev.filter((id) => missingEventIds.includes(id)));
  }, [missingEventIds]);

  const handleTestConnection = async (service: ServiceName) => {
    // For now, just ping /api/status to simulate an update.
    await fetchStatus();
  };

  const scrapeFamly = async (daysBack: number) => {
    const res = await fetch(apiUrl(`/api/scrape/famly?days_back=${daysBack}`), {
      method: "POST",
    });
    if (!res.ok) {
      throw new Error("Failed to scrape Famly");
    }
    const data = await res.json();
    return typeof data.scraped_count === "number" ? data.scraped_count : 0;
  };

  const scrapeBabyConnect = async (daysBack: number) => {
    const res = await fetch(apiUrl(`/api/scrape/baby_connect?days_back=${daysBack}`), {
      method: "POST",
    });
    if (!res.ok) {
      throw new Error("Failed to scrape Baby Connect");
    }
    const data = await res.json();
    return typeof data.scraped_count === "number" ? data.scraped_count : 0;
  };

  const startScrapeWatcher = (service: ServiceName) => {
    let stopped = false;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;

    const poll = async () => {
      if (stopped) return;
      try {
        const snapshot = await fetchScrapeProgress();
        const data = snapshot?.[service];
        setProgress((prev) => {
          if (!prev.visible) return prev;
          if (prev.mode !== "scrape") return prev;
          if (!data) return prev;
          const updated = { ...prev };
          if (data.message) {
            updated.label = data.message;
          }
          if (service === "famly") {
            updated.famlyProcessed = data.processed ?? prev.famlyProcessed;
            updated.famlyTotal = data.total ?? prev.famlyTotal;
          } else {
            updated.babyProcessed = data.processed ?? prev.babyProcessed;
            updated.babyTotal = data.total ?? prev.babyTotal;
          }
          return updated;
        });
      } catch (error) {
        console.debug("Progress watch error", error);
      } finally {
        if (!stopped) {
          timeoutId = setTimeout(poll, 400);
        }
      }
    };

    const stop = () => {
      stopped = true;
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      if (pollersRef.current[service] === stop) {
        delete pollersRef.current[service];
      }
    };

    poll();
    pollersRef.current[service] = stop;
    return stop;
  };

  const stopPollers = (service?: ProgressService) => {
    if (service) {
      pollersRef.current[service]?.();
      delete pollersRef.current[service];
      return;
    }
    (Object.keys(pollersRef.current) as ProgressService[]).forEach((key) => {
      pollersRef.current[key]?.();
      delete pollersRef.current[key];
    });
  };

  const startSyncWatcher = () => {
    let stopped = false;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;

    const poll = async () => {
      if (stopped) return;
      try {
        const snapshot = await fetchScrapeProgress();
        const data = snapshot?.sync;
        setProgress((prev) => {
          if (!prev.visible) return prev;
          if (prev.mode !== "sync") return prev;
          if (!data) return prev;
          const updated = { ...prev };
          if (data.message) {
            updated.label = data.message;
          }
          updated.syncCurrent = data.processed ?? prev.syncCurrent;
          updated.syncTotal = data.total ?? prev.syncTotal;
          return updated;
        });
      } catch (error) {
        console.debug("Progress watch error", error);
      } finally {
        if (!stopped) {
          timeoutId = setTimeout(poll, 400);
        }
      }
    };

    const stop = () => {
      stopped = true;
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      if (pollersRef.current.sync === stop) {
        delete pollersRef.current.sync;
      }
    };

    poll();
    pollersRef.current.sync = stop;
    return stop;
  };

  const markConnectionError = (service: ServiceName) => {
    if (service === "famly") {
      setFamlyStatus((prev) => ({ ...prev, status: "error" }));
    } else {
      setBcStatus((prev) => ({ ...prev, status: "error" }));
    }
  };

  const runScrapeOperation = async (
    operation: () => Promise<void>,
    onError?: () => void,
  ) => {
    setIsSyncing(true);
    try {
      await operation();
      await fetchEvents();
      await fetchStatus();
    } catch (err) {
      console.error(err);
      onError?.();
    } finally {
      setIsSyncing(false);
    }
  };

  const beginSyncProgress = (total: number, label?: string) => {
    const safeTotal = Math.max(total, 1);
    setProgress({
      mode: "sync",
      visible: true,
      label: label || (safeTotal === 1 ? "Syncing entry..." : "Syncing entries..."),
      currentStep: 0,
      totalSteps: safeTotal,
      famlyProcessed: 0,
      famlyTotal: 0,
      babyProcessed: 0,
      babyTotal: 0,
      syncCurrent: 0,
      syncTotal: safeTotal,
    });
  };

  const finishSyncProgress = (completed: number, label?: string) => {
    setProgress((prev) => ({
      ...prev,
      syncCurrent: Math.min(completed, prev.syncTotal || 1),
      label: label || prev.label,
    }));
    setTimeout(() => {
      setProgress((prev) => ({
        ...prev,
        mode: null,
        visible: false,
      }));
    }, 600);
  };

  const handleScrapeFamly = async (daysBack: number) => {
    stopPollers();
    setProgress({
      mode: "scrape",
      visible: true,
      label: "Scraping Famly...",
      currentStep: 0,
      totalSteps: 1,
      famlyProcessed: 0,
      famlyTotal: 0,
      babyProcessed: 0,
      babyTotal: 0,
      syncCurrent: 0,
      syncTotal: 0,
    });
    const stopWatcher = startScrapeWatcher("famly");
    const safeStop = () => {
      stopWatcher?.();
    };
    try {
      await runScrapeOperation(
        async () => {
          const count = await scrapeFamly(daysBack);
          setProgress((prev) => ({
            ...prev,
            currentStep: 1,
            famlyProcessed: count,
            famlyTotal: count,
          }));
        },
        () => markConnectionError("famly"),
      );
    } finally {
      safeStop();
      await new Promise((resolve) => setTimeout(resolve, 500));
      setProgress((prev) => ({ ...prev, visible: false, mode: null }));
    }
  };

  const handleScrapeBabyConnect = async (daysBack: number = scrapeDaysBack) => {
    stopPollers();
    setProgress({
      mode: "scrape",
      visible: true,
      label: "Scraping Baby Connect...",
      currentStep: 0,
      totalSteps: 1,
      famlyProcessed: 0,
      famlyTotal: 0,
      babyProcessed: 0,
      babyTotal: 0,
      syncCurrent: 0,
      syncTotal: 0,
    });
    const stopWatcher = startScrapeWatcher("baby_connect");
    const safeStop = () => {
      stopWatcher?.();
    };
    try {
      await runScrapeOperation(
        async () => {
          const count = await scrapeBabyConnect(daysBack);
          setProgress((prev) => ({
            ...prev,
            currentStep: 1,
            babyProcessed: count,
            babyTotal: count,
          }));
        },
        () => markConnectionError("baby_connect"),
      );
    } finally {
      safeStop();
      await new Promise((resolve) => setTimeout(resolve, 500));
      setProgress((prev) => ({ ...prev, visible: false, mode: null }));
    }
  };

  const handleScrapeAll = async () => {
    stopPollers();
    setProgress({
      mode: "scrape",
      visible: true,
      label: "Scraping Famly...",
      currentStep: 0,
      totalSteps: 2,
      famlyProcessed: 0,
      famlyTotal: 0,
      babyProcessed: 0,
      babyTotal: 0,
      syncCurrent: 0,
      syncTotal: 0,
    });
    const stopFamlyWatcher = startScrapeWatcher("famly");
    let famlyWatcherStopped = false;
    const stopFamly = () => {
      if (!famlyWatcherStopped) {
        stopFamlyWatcher?.();
        famlyWatcherStopped = true;
      }
    };
    let stopBabyWatcher: (() => void) | null = null;
    let babyWatcherStopped = false;
    const stopBaby = () => {
      if (!babyWatcherStopped && stopBabyWatcher) {
        stopBabyWatcher();
        babyWatcherStopped = true;
        stopBabyWatcher = null;
      }
    };
    try {
      await runScrapeOperation(
        async () => {
          try {
            const famlyCount = await scrapeFamly(scrapeDaysBack);
            setProgress((prev) => ({
              ...prev,
              currentStep: 1,
              label: "Scraping Baby Connect...",
              famlyProcessed: famlyCount,
              famlyTotal: famlyCount,
            }));
          } finally {
            stopFamly();
          }
          stopBabyWatcher = startScrapeWatcher("baby_connect");
          try {
            const babyCount = await scrapeBabyConnect(scrapeDaysBack);
            setProgress((prev) => ({
              ...prev,
              currentStep: 2,
              babyProcessed: babyCount,
              babyTotal: babyCount,
            }));
          } finally {
            stopBaby();
          }
        },
        () => {
          markConnectionError("famly");
          markConnectionError("baby_connect");
        },
      );
    } finally {
      stopFamly();
      stopBaby();
      await new Promise((resolve) => setTimeout(resolve, 500));
      setProgress((prev) => ({ ...prev, visible: false, mode: null }));
    }
  };

  const handleSyncAll = async () => {
    if (!missingEventIds.length) return;
    const targetIds = [...missingEventIds];
    beginSyncProgress(targetIds.length);
    setSyncAllInFlight(true);
    const stopSyncWatcher = startSyncWatcher();
    try {
      const result = await syncAllMissingEvents();
      const syncedIds: number[] = Array.isArray(result?.synced_event_ids)
        ? result.synced_event_ids
        : targetIds;
      clearSyncFailures(syncedIds);
      await fetchEvents();
      finishSyncProgress(syncedIds.length, "Sync complete");
    } catch (err) {
      console.error(err);
      alert(err instanceof Error ? err.message : "Failed to sync entries");
      markConnectionError("baby_connect");
      registerSyncFailure(targetIds);
      finishSyncProgress(0, "Sync failed");
    } finally {
      stopSyncWatcher?.();
      setSyncAllInFlight(false);
    }
  };

  const handleSyncSelected = async () => {
    if (!selectedEventIds.length) return;
    const uniqueTargetIds = Array.from(new Set(selectedEventIds));
    const label =
      uniqueTargetIds.length === 1 ? "Syncing entry..." : "Syncing selected entries...";
    beginSyncProgress(uniqueTargetIds.length, label);
    setSyncAllInFlight(true);
    const stopSyncWatcher = startSyncWatcher();
    try {
      const result = await syncEventsToBabyConnect(uniqueTargetIds);
      const syncedIds: number[] = Array.isArray(result?.synced_event_ids)
        ? result.synced_event_ids
        : uniqueTargetIds;
      clearSyncFailures(syncedIds);
      setSelectedEventIds((prev) => prev.filter((id) => !syncedIds.includes(id)));
      await fetchEvents();
      finishSyncProgress(syncedIds.length, "Selected entries synced");
    } catch (err) {
      console.error(err);
      alert(err instanceof Error ? err.message : "Failed to sync entries");
      markConnectionError("baby_connect");
      registerSyncFailure(uniqueTargetIds);
      finishSyncProgress(0, "Sync failed");
    } finally {
      stopSyncWatcher?.();
      setSyncAllInFlight(false);
    }
  };

  const handleSyncSingleEvent = async (eventId: number) => {
    setSyncingEventId(eventId);
    beginSyncProgress(1);
    const stopSyncWatcher = startSyncWatcher();
    try {
      const result = await syncEventsToBabyConnect([eventId]);
      const syncedIds: number[] = Array.isArray(result?.synced_event_ids)
        ? result.synced_event_ids
        : [eventId];
      clearSyncFailures(syncedIds);
      await fetchEvents();
      finishSyncProgress(syncedIds.length, "Entry synced");
    } catch (err) {
      console.error(err);
      alert(err instanceof Error ? err.message : "Failed to sync entry");
      registerSyncFailure([eventId]);
      markConnectionError("baby_connect");
      finishSyncProgress(0, "Sync failed");
    } finally {
      stopSyncWatcher?.();
      setSyncingEventId(null);
    }
  };

  const handleToggleIgnore = async (eventId: number, ignored: boolean) => {
    try {
      await setEventIgnored(eventId, ignored);
      setFamlyEvents((prev) =>
        prev.map((ev) => (ev.id === eventId ? { ...ev, ignored } : ev)),
      );
      await loadMissingEventIds();
    } catch (err) {
      console.error(err);
      alert(err instanceof Error ? err.message : "Failed to update ignore flag");
    }
  };

  const handleSyncPreferencesSaved = useCallback(
    async (prefs: SyncPreferences) => {
      setSyncPreferences(prefs);
      await loadMissingEventIds();
    },
    [loadMissingEventIds],
  );

  const missingCount = missingEventIds.length;

  const hasScrapedData = famlyEvents.length > 0 || bcEvents.length > 0;
  const syncDisabled =
    isSyncing || syncAllInFlight || !hasScrapedData || missingCount === 0;
  const selectionDisabled =
    !selectedEventIds.length || isSyncing || syncAllInFlight || !hasScrapedData;

  const handleCredentialsSaved = async () => {
    await fetchStatus();
  };

  const formatDateTime = (iso?: string | null) => {
    if (!iso) return "Never";
    try {
      const date = new Date(iso);
      return date.toLocaleString(undefined, {
        day: "2-digit",
        month: "2-digit",
        year: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return "Never";
    }
  };

  return (
    <div className="app-shell">
      <div className="app-inner">
        <header className="hero hero--compact">
          <div>
            <h1 className="hero__title">Famly &rarr; Baby Connect</h1>
            <p className="hero__subtitle">
              Compare timelines, spot differences, and push missing events in a single view.
            </p>
          </div>
          <div className="hero__actions">
            <button className="btn btn--secondary" onClick={() => setIsSettingsOpen(true)}>
              Settings
            </button>
          </div>
        </header>
        <main className="main-content">
          <div className="workflow-steps">
            <div className="workflow-step">
              <p className="workflow-step__label">Step 1</p>
              <h3 className="workflow-step__title">Scrape latest data</h3>
              <p className="workflow-step__body">
                Choose how many recent entry days to include, then run the scrape to pull fresh
                Famly and Baby Connect records.
              </p>
            </div>
            <div className="workflow-arrow">→</div>
            <div className="workflow-step">
              <p className="workflow-step__label">Step 2</p>
              <h3 className="workflow-step__title">Compare timelines</h3>
              <p className="workflow-step__body">
                Review Famly vs Baby Connect entries, filter for missing ones, and inspect the icons
                for per-event details.
              </p>
            </div>
            <div className="workflow-arrow">→</div>
            <div className="workflow-step">
              <p className="workflow-step__label">Step 3</p>
              <h3 className="workflow-step__title">Sync anything missing</h3>
              <p className="workflow-step__body">
                Use the Sync All action or the per-event arrows to push outstanding entries into
                Baby Connect with one click.
              </p>
            </div>
          </div>
          <div className="connection-chips">
            <div className={`connection-chip connection-chip--${famlyStatus.status}`}>
              <span className="connection-chip__label">Famly</span>
              <span className="connection-chip__status">
                {famlyStatus.status === "ok"
                  ? "Connected"
                  : famlyStatus.status === "error"
                  ? "Error"
                  : "Not connected"}
              </span>
              <span className="connection-chip__meta">
                Last scrape: {formatDateTime(famlyStatus.lastScrapedAt)}
              </span>
            </div>
            <div className={`connection-chip connection-chip--${bcStatus.status}`}>
              <span className="connection-chip__label">Baby Connect</span>
              <span className="connection-chip__status">
                {bcStatus.status === "ok"
                  ? "Connected"
                  : bcStatus.status === "error"
                  ? "Error"
                  : "Not connected"}
              </span>
              <span className="connection-chip__meta">
                Last scrape: {formatDateTime(bcStatus.lastScrapedAt)}
              </span>
            </div>
          </div>
          <EventComparison
            controlsSlot={
              <div className="controls-bar">
                <div className="controls-bar__group controls-bar__group--left">
                  <select
                    className="control-select"
                    value={scrapeDaysBack}
                    onChange={(e) => setScrapeDaysBack(Number(e.target.value))}
                  >
                    <option value={0}>Last day with entries</option>
                    <option value={1}>Last 2 entry days</option>
                    <option value={2}>Last 3 entry days</option>
                    <option value={3}>Last 4 entry days</option>
                  </select>
                  <button className="btn btn--secondary" onClick={handleScrapeAll} disabled={isSyncing}>
                    Scrape Data
                  </button>
                  <button
                    type="button"
                    className="btn btn--secondary btn--refresh"
                    onClick={handleRefresh}
                    disabled={isSyncing || isRefreshing}
                    aria-label="Refresh data"
                  >
                    <span className="btn--refresh__icon" aria-hidden="true">⟳</span>
                    <span className="btn--refresh__label">Refresh</span>
                  </button>
                </div>
                <div className="controls-bar__center">
                  <div className="controls-bar__center-stack">
                    <button
                      className={`btn btn--primary${syncDisabled ? " btn--disabled" : ""}`}
                      onClick={handleSyncAll}
                      disabled={syncDisabled}
                    >
                      {isSyncing ? "Syncing..." : "Sync All"}
                    </button>
                    <div className="controls-bar__selection">
                      <button
                        className={`btn btn--secondary${
                          selectionDisabled ? " btn--disabled" : ""
                        }`}
                        onClick={handleSyncSelected}
                        disabled={selectionDisabled}
                      >
                        Sync Selected
                        {selectedEventIds.length ? ` (${selectedEventIds.length})` : ""}
                      </button>
                      <button
                        type="button"
                        className={`btn btn--secondary${
                          selectedEventIds.length ? "" : " btn--disabled"
                        }`}
                        onClick={handleClearSelection}
                        disabled={!selectedEventIds.length}
                      >
                        Clear selection
                      </button>
                      {selectedEventIds.length > 0 && (
                        <span className="controls-bar__selection-count">
                          {selectedEventIds.length} selected
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="controls-bar__group controls-bar__group--right">
                  <div className="controls-bar__right-buttons">
                    <button
                      type="button"
                      className="btn btn--secondary"
                      onClick={() => setShowMissingOnly((prev) => !prev)}
                    >
                      {showMissingOnly ? "Show all entries" : "Show only missing"}
                    </button>
                  </div>
                </div>
              </div>
            }
            selectedEventIds={selectedEventIds}
            onToggleSelection={toggleSelectedEntry}
            famlyEvents={famlyEvents}
            babyEvents={bcEvents}
            dateFormat={dateFormat}
            onSyncEvent={handleSyncSingleEvent}
            syncingEventId={syncingEventId}
            isBulkSyncing={syncAllInFlight}
            showMissingOnly={showMissingOnly}
            onToggleMissing={() => setShowMissingOnly((prev) => !prev)}
            failedEventIds={failedEventIds}
            onToggleIgnore={handleToggleIgnore}
          />
        </main>
      </div>
      <SettingsDrawer
        open={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        statuses={[famlyStatus, bcStatus]}
        onTestConnection={handleTestConnection}
        onCredentialsSaved={handleCredentialsSaved}
        onSyncPreferencesSaved={handleSyncPreferencesSaved}
        syncPreferences={syncPreferences}
        dateFormat={dateFormat}
        onChangeDateFormat={setDateFormat}
      />
      <ProgressOverlay progress={progress} />
      <SyncToast mode={syncAllInFlight ? "bulk" : syncingEventId ? "single" : null} />
    </div>
  );
};

export default App;
