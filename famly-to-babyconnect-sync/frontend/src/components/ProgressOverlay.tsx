import React from "react";

interface Props {
  progress: {
    mode: "scrape" | "sync" | null;
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
}

export const ProgressOverlay: React.FC<Props> = ({ progress }) => {
  if (!progress.visible) return null;

  const isSyncMode = progress.mode === "sync";

  const percentage = isSyncMode
    ? progress.syncTotal > 0
      ? Math.min(
          100,
          Math.round((progress.syncCurrent / progress.syncTotal) * 100),
        )
      : 0
    : progress.totalSteps > 0
    ? Math.min(
        100,
        Math.round((progress.currentStep / progress.totalSteps) * 100),
      )
    : 0;

  return (
    <div className="progress-overlay">
      <div className="progress-panel">
        <h3>{isSyncMode ? "Syncing entries" : "Scraping data"}</h3>
        <p className="progress-panel__label">{progress.label}</p>
        <div className="progress-bar">
          <div
            className="progress-bar__fill"
            style={{ width: `${percentage}%` }}
          />
        </div>
        {isSyncMode ? (
          <div className="progress-stats progress-stats--sync">
            <div>
              <p>Processed</p>
              <strong>
                {Math.min(progress.syncCurrent, progress.syncTotal || 0)}
              </strong>
              <span> / {progress.syncTotal}</span>
            </div>
          </div>
        ) : (
          <div className="progress-stats">
          <div>
            <p>Famly entries</p>
            <strong>{progress.famlyProcessed}</strong>
            {progress.famlyTotal ? <span> / {progress.famlyTotal}</span> : null}
          </div>
          <div>
            <p>Baby Connect entries</p>
            <strong>{progress.babyProcessed}</strong>
            {progress.babyTotal ? <span> / {progress.babyTotal}</span> : null}
          </div>
        </div>
      )}
    </div>
  </div>
  );
};
