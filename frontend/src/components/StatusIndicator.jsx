const STATUS_META = {
  idle: { label: "Idle", color: "state-idle", pulse: false },
  working: { label: "Working…", color: "state-working", pulse: true },
  in_progress: { label: "Working…", color: "state-working", pulse: true },
  pending: { label: "Queued", color: "state-idle", pulse: false },
  awaiting_approval: { label: "Needs your approval", color: "state-approval", pulse: true },
  completed: { label: "Completed", color: "state-success", pulse: false },
  escalated: { label: "Escalated", color: "state-danger", pulse: false },
  failed: { label: "Failed", color: "state-danger", pulse: false },
  proposed: { label: "Awaiting decision", color: "state-approval", pulse: false },
  approved: { label: "Approved", color: "state-success", pulse: false },
  rejected: { label: "Rejected", color: "state-danger", pulse: false },
};

const DOT_COLOR = {
  "state-idle": "bg-state-idle",
  "state-working": "bg-state-working",
  "state-approval": "bg-state-approval",
  "state-success": "bg-state-success",
  "state-danger": "bg-state-danger",
};

const TEXT_COLOR = {
  "state-idle": "text-state-idle",
  "state-working": "text-state-working",
  "state-approval": "text-state-approval",
  "state-success": "text-state-success",
  "state-danger": "text-state-danger",
};

export default function StatusIndicator({ status, size = "md" }) {
  const meta = STATUS_META[status] || { label: status, color: "state-idle", pulse: false };
  const isLarge = size === "lg";

  return (
    <span
      className={`inline-flex items-center gap-2 rounded-pill border border-hairline bg-surface ${
        isLarge ? "px-4 py-2 text-sm" : "px-2.5 py-1 text-xs"
      } font-medium ${TEXT_COLOR[meta.color]}`}
    >
      <span className="relative flex h-2 w-2">
        {meta.pulse && (
          <span className={`absolute inline-flex h-full w-full animate-breathe rounded-full ${DOT_COLOR[meta.color]}`} />
        )}
        <span className={`relative inline-flex h-2 w-2 rounded-full ${DOT_COLOR[meta.color]}`} />
      </span>
      {meta.label}
    </span>
  );
}
