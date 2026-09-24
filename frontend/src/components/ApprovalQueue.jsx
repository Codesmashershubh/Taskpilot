import { Check, MailCheck, X } from "lucide-react";
import { useState } from "react";
import { api } from "../api/client.js";
import { useScrollReveal } from "../hooks/useScrollReveal.js";

export default function ApprovalQueue({ actions, onDecided }) {
  const { ref, visible } = useScrollReveal();
  const [pendingId, setPendingId] = useState(null);

  const decide = async (id, decision) => {
    setPendingId(id);
    try {
      if (decision === "approve") await api.approve(id);
      else await api.reject(id);
      await onDecided();
    } finally {
      setPendingId(null);
    }
  };

  return (
    <section
      ref={ref}
      className={`mx-auto max-w-6xl px-6 py-16 transition-all duration-700 ${visible ? "animate-fade-up" : "opacity-0"}`}
    >
      <div className="rounded-card border border-hairline bg-gradient-to-b from-accent-soft/60 to-transparent p-8 sm:p-10">
        <div className="mb-8 flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-full bg-accent text-white">
            <MailCheck className="h-5 w-5" />
          </span>
          <div>
            <h2 className="text-2xl font-semibold tracking-tight text-ink">Needs your approval</h2>
            <p className="text-sm text-muted">
              Drafts are saved to Gmail but never sent — review, then approve or reject.
            </p>
          </div>
        </div>

        {!actions?.length ? (
          <p className="rounded-card border border-dashed border-hairline bg-surface/60 px-6 py-10 text-center text-sm text-muted">
            Nothing waiting on you right now.
          </p>
        ) : (
          <div className="space-y-4">
            {actions.map((action) => (
              <div key={action.id} className="rounded-card border border-hairline bg-surface p-5 shadow-soft">
                <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
                  <div className="min-w-0">
                    <p className="text-xs font-medium uppercase tracking-wide text-muted">
                      To {action.output?.to}
                    </p>
                    <p className="mt-0.5 font-medium text-ink">{action.output?.subject}</p>
                    <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-muted">
                      {action.output?.body}
                    </p>
                  </div>
                  <div className="flex shrink-0 gap-2 self-start">
                    <button
                      onClick={() => decide(action.id, "approve")}
                      disabled={pendingId === action.id}
                      className="inline-flex items-center gap-1.5 rounded-pill bg-state-success px-4 py-2 text-xs font-medium text-white transition hover:opacity-90 disabled:opacity-50"
                    >
                      <Check className="h-3.5 w-3.5" />
                      Approve
                    </button>
                    <button
                      onClick={() => decide(action.id, "reject")}
                      disabled={pendingId === action.id}
                      className="inline-flex items-center gap-1.5 rounded-pill border border-hairline px-4 py-2 text-xs font-medium text-muted transition hover:text-state-danger disabled:opacity-50"
                    >
                      <X className="h-3.5 w-3.5" />
                      Reject
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
