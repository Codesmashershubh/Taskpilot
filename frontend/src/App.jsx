import { Settings } from "lucide-react";
import { useState } from "react";
import { api, getSettings } from "./api/client.js";
import ApprovalQueue from "./components/ApprovalQueue.jsx";
import Hero from "./components/Hero.jsx";
import SettingsPanel from "./components/SettingsPanel.jsx";
import Timeline from "./components/Timeline.jsx";
import { usePolling } from "./hooks/usePolling.js";

export default function App() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const { apiKey } = getSettings();

  const { data: stats, refresh: refreshStats } = usePolling(() => api.stats(), 5000, [apiKey]);
  const { data: runs, refresh: refreshRuns } = usePolling(() => api.runs(undefined), 5000, [apiKey]);
  const { data: approvals, refresh: refreshApprovals, error: approvalsError } = usePolling(
    () => api.approvals(),
    5000,
    [apiKey]
  );

  const handleCheckNow = async () => {
    await api.poll();
    await Promise.all([refreshStats(), refreshRuns(), refreshApprovals()]);
  };

  const handleDecided = async () => {
    await Promise.all([refreshStats(), refreshRuns(), refreshApprovals()]);
  };

  if (!apiKey) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center px-6 text-center">
        <h1 className="text-3xl font-semibold tracking-tight text-ink">Connect TaskPilot</h1>
        <p className="mt-3 max-w-sm text-sm leading-relaxed text-muted">
          Add your backend URL and API key to get started. Both live in{" "}
          <code className="rounded bg-canvas px-1 py-0.5 font-mono text-xs">backend/.env</code>.
        </p>
        <button
          onClick={() => setSettingsOpen(true)}
          className="mt-6 rounded-pill bg-ink px-6 py-2.5 text-sm font-medium text-white transition hover:opacity-90"
        >
          Open settings
        </button>
        <SettingsPanel open={settingsOpen} onClose={() => setSettingsOpen(false)} />
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-hairline bg-canvas/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <span className="text-sm font-semibold tracking-tight text-ink">TaskPilot</span>
          <button
            onClick={() => setSettingsOpen(true)}
            className="rounded-full p-2 text-muted transition hover:bg-surface hover:text-ink"
            aria-label="Open settings"
          >
            <Settings className="h-4 w-4" />
          </button>
        </div>
      </header>

      {approvalsError?.status === 401 && (
        <div className="mx-auto mt-4 max-w-6xl px-6">
          <div className="rounded-lg border border-state-danger/30 bg-state-danger/5 px-4 py-3 text-sm text-state-danger">
            The backend rejected the API key — open Settings and check it matches{" "}
            <code className="font-mono">API_SECRET_KEY</code> in <code className="font-mono">backend/.env</code>.
          </div>
        </div>
      )}

      <main>
        <Hero stats={stats} onCheckNow={handleCheckNow} />
        <Timeline runs={runs} />
        <ApprovalQueue actions={approvals} onDecided={handleDecided} />
      </main>

      <footer className="mx-auto max-w-6xl px-6 py-10 text-center text-xs text-muted">
        TaskPilot never sends email on its own — every draft waits for you.
      </footer>

      <SettingsPanel open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}
