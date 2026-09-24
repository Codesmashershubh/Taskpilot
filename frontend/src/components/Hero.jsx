import { RefreshCw } from "lucide-react";
import { useState } from "react";
import StatusIndicator from "./StatusIndicator.jsx";
import { useScrollReveal } from "../hooks/useScrollReveal.js";

export default function Hero({ stats, onCheckNow }) {
  const { ref, visible } = useScrollReveal(0);
  const [checking, setChecking] = useState(false);

  const handleCheckNow = async () => {
    setChecking(true);
    try {
      await onCheckNow();
    } finally {
      setChecking(false);
    }
  };

  return (
    <section
      ref={ref}
      className={`mx-auto max-w-4xl px-6 pb-20 pt-28 text-center transition-all duration-700 ${
        visible ? "animate-fade-up" : "opacity-0"
      }`}
    >
      <div className="mb-8 flex justify-center">
        <StatusIndicator status={stats?.agent_status ?? "idle"} size="lg" />
      </div>

      <h1 className="text-balance text-6xl font-semibold tracking-tight text-ink sm:text-7xl">
        Your inbox,
        <br />
        handled.
      </h1>
      <p className="mx-auto mt-6 max-w-xl text-balance text-lg leading-relaxed text-muted">
        TaskPilot reads new messages, drafts a reply, and logs the details —
        then waits for your yes before anything goes out.
      </p>

      <div className="mt-10 flex justify-center">
        <button
          onClick={handleCheckNow}
          disabled={checking}
          className="inline-flex items-center gap-2 rounded-pill bg-ink px-6 py-3 text-sm font-medium text-white shadow-soft transition hover:opacity-90 disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${checking ? "animate-spin" : ""}`} />
          {checking ? "Checking inbox…" : "Check inbox now"}
        </button>
      </div>

      {stats && (
        <dl className="mx-auto mt-16 grid max-w-2xl grid-cols-3 gap-6 border-t border-hairline pt-10">
          <Stat label="Success rate" value={`${Math.round((stats.success_rate ?? 0) * 100)}%`} />
          <Stat label="Runs handled" value={stats.total_runs ?? 0} />
          <Stat label="Avg. decision time" value={`${Math.round(stats.avg_latency_ms ?? 0)}ms`} />
        </dl>
      )}
    </section>
  );
}

function Stat({ label, value }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-muted">{label}</dt>
      <dd className="mt-1 font-mono text-2xl font-medium text-ink">{value}</dd>
    </div>
  );
}
