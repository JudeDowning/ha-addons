import React, { useEffect, useState } from "react";
import { loadCredentials, saveCredentials, testCredentials } from "../api";
import { ConnectionStatus, ServiceName } from "../types";

interface Props {
  status: ConnectionStatus;
  onTestConnection: (service: ServiceName) => void;
  onSaved?: (service: ServiceName) => void;
}

export const ConnectionCard: React.FC<Props> = ({
  status,
  onTestConnection,
  onSaved,
}) => {
  const label = status.service === "famly" ? "Famly (Source)" : "Baby Connect (Target)";
  const [email, setEmail] = useState(status.email ?? "");
  const [password, setPassword] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [testMessage, setTestMessage] = useState<string | null>(null);

  useEffect(() => {
    setEmail(status.email ?? "");
  }, [status.email]);

  useEffect(() => {
    let cancelled = false;
    async function fetchCredential() {
      setIsLoading(true);
      setError(null);
      try {
        const data = await loadCredentials(status.service);
        if (!cancelled) {
          setEmail(data.email ?? "");
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load credentials");
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }
    fetchCredential();
    return () => {
      cancelled = true;
    };
  }, [status.service]);

  const handleSave = async () => {
    if (!email || !password) {
      setError("Email and password are required");
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      await saveCredentials(status.service, email, password);
      onSaved?.(status.service);
      setPassword("");
      setTestMessage("Credentials saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save credentials");
      setTestMessage(null);
    } finally {
      setIsSaving(false);
    }
  };

  const handleTest = async () => {
    setIsTesting(true);
    setError(null);
    setTestMessage(null);
    try {
      await testCredentials(status.service);
      setTestMessage("Connection successful.");
      onTestConnection(status.service);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to test credentials");
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <div className="credential-card">
      <div>
        <h3>{label}</h3>
        <p className="status-card__meta">
          {status.email ? `Credentials stored for ${status.email}` : "No credentials stored"}
        </p>
        {status.lastConnectedAt && (
          <p className="status-card__meta">
            Last connected: {new Date(status.lastConnectedAt).toLocaleString()}
          </p>
        )}
      </div>
      <div>
        <label htmlFor={`${status.service}-email`}>Email</label>
        <input
          id={`${status.service}-email`}
          type="email"
          className="input-field"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </div>
      <div>
        <label htmlFor={`${status.service}-password`}>Password</label>
        <input
          id={`${status.service}-password`}
          type="password"
          className="input-field"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </div>
      {error && <p className="error-text">{error}</p>}
      {testMessage && !error && <p className="loading-text">{testMessage}</p>}
      {isLoading && <p className="loading-text">Loading…</p>}
      <div className="credential-card__actions">
        <button
          className="credential-card__btn credential-card__btn--primary"
          onClick={handleSave}
          disabled={isSaving}
        >
          {isSaving ? "Saving..." : "Save"}
        </button>
        <button
          className="credential-card__btn"
          onClick={handleTest}
          disabled={isTesting}
        >
          Test
        </button>
      </div>
    </div>
  );
};
