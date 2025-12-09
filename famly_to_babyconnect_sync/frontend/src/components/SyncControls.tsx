import React from "react";

interface Props {
  isSyncing: boolean;
  onSyncAll: () => void;
  onScrapeFamly: (daysBack: number) => void;
  onScrapeBabyConnect: () => void;
  scrapeDaysBack: number;
  onChangeScrapeDays: (daysBack: number) => void;
}

export const SyncControls: React.FC<Props> = ({
  isSyncing,
  onSyncAll,
  onScrapeFamly,
  onScrapeBabyConnect,
  scrapeDaysBack,
  onChangeScrapeDays,
}) => {
  const handleDaysChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    onChangeScrapeDays(Number(event.target.value));
  };

  return (
    <div className="flex flex-col items-center justify-center space-y-3">
      <div className="flex flex-col items-center text-xs">
        <label htmlFor="scrape-days" className="mb-1 uppercase">
          Days to include
        </label>
        <select
          id="scrape-days"
          className="border rounded px-2 py-1 text-sm"
          value={scrapeDaysBack}
          onChange={handleDaysChange}
        >
          <option value={0}>Today</option>
          <option value={1}>Today + 1 day</option>
          <option value={2}>Today + 2 days</option>
          <option value={3}>Today + 3 days</option>
        </select>
      </div>
      <button
        className="px-4 py-2 rounded-xl border shadow text-sm"
        onClick={() => onScrapeFamly(scrapeDaysBack)}
        disabled={isSyncing}
      >
        Scrape Famly
      </button>
      <button
        className="px-4 py-2 rounded-xl border shadow text-sm"
        onClick={onScrapeBabyConnect}
        disabled={isSyncing}
      >
        Scrape Baby Connect
      </button>
      <button
        className="px-4 py-2 rounded-xl border shadow text-sm"
        onClick={onSyncAll}
        disabled={isSyncing}
      >
        {isSyncing ? "Syncing…" : "Sync All"}
      </button>
    </div>
  );
};
