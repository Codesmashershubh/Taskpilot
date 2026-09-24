import { CalendarClock, ChevronDown, HelpCircle, LifeBuoy, Receipt } from "lucide-react";
import { useState } from "react";
import { api } from "../api/client.js";
import StatusIndicator from "./StatusIndicator.jsx";

const TYPE_ICON = {
  meeting_request: CalendarClock,
  invoice: Receipt,
  support_question: LifeBuoy,
  other: HelpCircle,
};

const TYPE_LABEL = {
  meeting_request: "Meeting request",
  invoice: "Invoice",
  support_question: "Support question",
  other: "Unclassified",
};

const STEP_LABEL = {
  perceive: "Perceive",
  plan: "Plan",
  act: "Act",
  reflect: "Reflect",
  escalate: "Escalate",
};

export default function ActionCard({ run }) {
  const [expanded, setExpanded] = useState(false);
  const [detail, setDetail] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const Icon = TYPE_ICON[run.task_type] || HelpCircle;

  const toggle = async () => {
    const next = !expanded;
    setExpanded(next);
    if (next && !detail) {
      setLoadingDetail(true);
      try {
        const full = await api.runDetail(run.id);
        setDetail(full);
      } catch {
        /* card still shows the summary even if the trace fails to load */
      } finally {
        setLoadingDetail(false);
      }
    }
  };

  return (
    <div className="w-[320px] flex-none rounded-card border border-hairline bg-surface p-5 shadow-soft transition hover:shadow-lift">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-accent-soft text-accent">
            <Icon className="h-4 w-4" />
          </span>
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-muted">
              {TYPE_LABEL[run.task_type] || "Unclassified"}
            </p>
            <p className="text-sm font-medium text-ink line-clamp-1">{run.subject || "(no subject)"}</p>
          </div>
        </div>
      </div>

      <p className="mt-3 text-sm leading-relaxed text-muted line-clamp-2">{run.snippet}</p>

      <div className="mt-4 flex items-center justify-between">
        <StatusIndicator status={run.status} />
        <time className="font-mono text-[11px] text-muted">{formatTime(run.created_at)}</time>
      </div>

      <button
        onClick={toggle}
        className="mt-4 flex w-full items-center justify-center gap-1 rounded-pill border border-hairline py-1.5 text-xs font-medium text-muted transition hover:text-ink"
      >
        {expanded ? "Hide reasoning" : "Show reasoning"}
        <ChevronDown className={`h-3.5 w-3.5 transition-transform ${expanded ? "rotate-180" : ""}`} />
      </button>

      {expanded && (
        <div className="mt-4 border-t border-hairline pt-4">
          {loadingDetail && <p className="font-mono text-xs text-muted">Loading trace…</p>}
          {!loadingDetail && detail && <ReasoningTrace steps={detail.steps} />}
        </div>
      )}
    </div>
  );
}

/** The signature element: perceive -> plan -> act -> reflect as a connected,
 * dotted node-thread in the mono face — the "control center", not "chat
 * bubble" idea made visible. */
function ReasoningTrace({ steps }) {
  if (!steps?.length) {
    return <p className="font-mono text-xs text-muted">No steps recorded.</p>;
  }
  return (
    <ol className="relative ml-1.5 space-y-4 border-l border-dashed border-hairline pl-5">
      {steps.map((step) => (
        <li key={step.id} className="relative">
          <span className="absolute -left-[23px] top-1 h-2 w-2 rounded-full bg-ink" />
          <p className="font-mono text-[11px] uppercase tracking-wide text-muted">
            {STEP_LABEL[step.step_name] || step.step_name}
          </p>
          <p className="mt-0.5 font-mono text-xs leading-relaxed text-ink">{formatStepDetail(step)}</p>
        </li>
      ))}
    </ol>
  );
}

function formatStepDetail(step) {
  const d = step.detail || {};
  switch (step.step_name) {
    case "perceive":
      return `"${d.subject}" from ${d.sender}`;
    case "plan":
      return `${d.task_type} · confidence ${Number(d.confidence ?? 0).toFixed(2)}`;
    case "act":
      return `${d.tool} — ${d.summary}`;
    case "reflect":
      return `${d.passed ? "passed" : "failed"} · confidence ${Number(d.confidence ?? 0).toFixed(2)} — ${d.notes}`;
    case "escalate":
      return d.reason;
    default:
      return JSON.stringify(d);
  }
}

function formatTime(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  return date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}
