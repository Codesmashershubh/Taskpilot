import { ExternalLink, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api, getSettings, saveSettings } from "../api/client.js";

export default function SettingsPanel({ open, onClose }) {
  const [form, setForm] = useState(getSettings());
  const [gmailConnected, setGmailConnected] = useState(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!open) return;
    setForm(getSettings());
    setSaved(false);
    api
      .gmailStatus()
      .then((r) => setGmailConnected(r.connected))
      .catch(() => setGmailConnected(null));
  }, [open]);

  const handleSave = (e) => {
    e.preventDefault();
    saveSettings(form);
    setSaved(true);
    setTimeout(() => window.location.reload(), 400);
  };

  const connectUrl = form.apiKey
    ? `${form.baseUrl}/api/auth/gmail/login?key=${encodeURIComponent(form.apiKey)}`
    : null;

  return (
    <>
      <div
        className={`fixed inset-0 z-40 bg-ink/20 backdrop-blur-sm transition-opacity ${
          open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
        onClick={onClose}
      />
      <aside
        className={`fixed right-0 top-0 z-50 h-full w-full max-w-sm border-l border-hairline bg-surface p-6 shadow-lift transition-transform duration-300 ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-ink">Settings</h2>
          <button onClick={onClose} className="rounded-full p-1.5 text-muted hover:bg-canvas" aria-label="Close settings">
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={handleSave} className="mt-6 space-y-5">
          <Field
            label="Backend URL"
            value={form.baseUrl}
            onChange={(v) => setForm((f) => ({ ...f, baseUrl: v }))}
            placeholder="http://localhost:8000"
          />
          <Field
            label="API key"
            type="password"
            value={form.apiKey}
            onChange={(v) => setForm((f) => ({ ...f, apiKey: v }))}
            placeholder="Matches API_SECRET_KEY in backend/.env"
          />
          <button
            type="submit"
            className="w-full rounded-pill bg-ink py-2.5 text-sm font-medium text-white transition hover:opacity-90"
          >
            {saved ? "Saved — reloading…" : "Save"}
          </button>
        </form>

        <div className="mt-8 border-t border-hairline pt-6">
          <p className="text-xs font-medium uppercase tracking-wide text-muted">Gmail</p>
          <p className="mt-2 text-sm text-ink">
            {gmailConnected === null && "Status unknown — save settings to check."}
            {gmailConnected === true && "Connected. TaskPilot can read the watched label and create drafts."}
            {gmailConnected === false && "Not connected. Using the built-in demo inbox until you connect."}
          </p>
          {connectUrl && !gmailConnected && (
            <a
              href={connectUrl}
              target="_blank"
              rel="noreferrer"
              className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-accent hover:underline"
            >
              Connect Gmail <ExternalLink className="h-3.5 w-3.5" />
            </a>
          )}
        </div>

        <div className="mt-8 border-t border-hairline pt-6 text-xs leading-relaxed text-muted">
          Confidence threshold, poll interval, and LLM provider are set in{" "}
          <code className="rounded bg-canvas px-1 py-0.5 font-mono">backend/.env</code> — see the README.
        </div>
      </aside>
    </>
  );
}

function Field({ label, value, onChange, type = "text", placeholder }) {
  return (
    <label className="block">
      <span className="text-xs font-medium uppercase tracking-wide text-muted">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="mt-1.5 w-full rounded-lg border border-hairline bg-canvas px-3 py-2 text-sm text-ink outline-none focus:border-accent"
      />
    </label>
  );
}
