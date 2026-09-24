import { Inbox } from "lucide-react";
import ActionCard from "./ActionCard.jsx";
import { useScrollReveal } from "../hooks/useScrollReveal.js";

export default function Timeline({ runs }) {
  const { ref, visible } = useScrollReveal();

  return (
    <section
      ref={ref}
      className={`mx-auto max-w-6xl px-6 py-16 transition-all duration-700 ${visible ? "animate-fade-up" : "opacity-0"}`}
    >
      <div className="mb-6 flex items-baseline justify-between">
        <h2 className="text-2xl font-semibold tracking-tight text-ink">Recent activity</h2>
        <span className="font-mono text-xs text-muted">{runs?.length ?? 0} runs</span>
      </div>

      {!runs?.length ? (
        <div className="flex flex-col items-center justify-center rounded-card border border-dashed border-hairline py-16 text-center">
          <Inbox className="h-6 w-6 text-muted" />
          <p className="mt-3 text-sm text-muted">
            Nothing yet — click "Check inbox now" to run TaskPilot against your inbox.
          </p>
        </div>
      ) : (
        <div className="timeline-scroll -mx-6 flex gap-4 overflow-x-auto px-6 pb-4">
          {runs.map((run) => (
            <ActionCard key={run.id} run={run} />
          ))}
        </div>
      )}
    </section>
  );
}
