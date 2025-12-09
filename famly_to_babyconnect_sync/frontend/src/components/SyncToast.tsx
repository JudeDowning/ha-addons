import React from "react";

interface Props {
  mode: "single" | "bulk" | null;
}

export const SyncToast: React.FC<Props> = ({ mode }) => {
  if (!mode) return null;
  const message =
    mode === "bulk"
      ? "Syncing entries to Baby Connect…"
      : "Syncing entry to Baby Connect…";

  return (
    <div className="sync-toast">
      <span className="sync-toast__spinner" aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
};
