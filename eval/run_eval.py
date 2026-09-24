#!/usr/bin/env python3
"""
Runs every email in eval_emails.json through the REAL agent orchestrator
(same code path as production, not a simulation) and scores each run
against an expected outcome. This is what backs the PRD's success-rate
metric and resume bullet.

Usage (from the `eval/` directory, with the backend venv active):
    python run_eval.py                      # uses LLM_PROVIDER from backend/.env (or mock if unset)
    LLM_PROVIDER=groq python run_eval.py     # re-run the same fixture against Groq for comparison

Writes eval_results.json (machine-readable) and eval_report.md (human-readable)
next to this script.
"""
import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path

EVAL_DIR = Path(__file__).parent
BACKEND_DIR = EVAL_DIR.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

# Isolated, throwaway DB for the eval run so it never touches your real data.
os.environ.setdefault("DATABASE_PATH", os.path.join(tempfile.mkdtemp(), "eval.db"))
os.environ.setdefault("API_SECRET_KEY", "eval-run-not-a-real-secret")
os.environ.setdefault("ENCRYPTION_KEY", "dGVzdC1lbmNyeXB0aW9uLWtleS0zMi1ieXRlcyEh")
# Load backend/.env for LLM_PROVIDER / API keys if present, without overriding
# anything already set in the eval run's own environment.
_env_file = BACKEND_DIR / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())

from app.agent.orchestrator import Orchestrator  # noqa: E402
from app.db import get_connection, init_db  # noqa: E402
from app.email_source.factory import get_email_source  # noqa: E402
from app.email_source.mock_source import MockEmailSource  # noqa: E402
from app.llm.factory import get_llm_provider  # noqa: E402
from app.models import EmailMessage  # noqa: E402
from app.sanitize import extract_email_address, sanitize_text  # noqa: E402


def load_fixture() -> list[dict]:
    return json.loads((EVAL_DIR / "eval_emails.json").read_text())


def to_email_message(row: dict) -> EmailMessage:
    return EmailMessage(
        id=row["id"],
        thread_id=f"thread-{row['id']}",
        sender=sanitize_text(row["sender"]),
        reply_to=extract_email_address(row["sender"]),
        subject=sanitize_text(row["subject"]),
        body=sanitize_text(row["body"]),
        received_at="2026-01-01T00:00:00+00:00",
    )


async def main() -> None:
    init_db()
    llm = get_llm_provider()
    # Always use the mock email source for eval — we're feeding it a fixed
    # fixture directly rather than pulling from a real/mock inbox.
    email_source = MockEmailSource() if not isinstance(get_email_source(), MockEmailSource) else get_email_source()
    orchestrator = Orchestrator(llm=llm, email_source=email_source)

    fixture = load_fixture()
    results = []
    start_all = time.perf_counter()

    for row in fixture:
        email = to_email_message(row)
        run_id = await orchestrator.process_email(email)

        conn = get_connection()
        run = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()

        actual_status = run["status"]
        actual_task_type = run["task_type"]
        expected_status = "awaiting_approval" if row["expected_outcome"] == "drafted" else "escalated"

        passed = actual_task_type == row["expected_task_type"] and actual_status == expected_status
        results.append(
            {
                "id": row["id"],
                "expected_task_type": row["expected_task_type"],
                "actual_task_type": actual_task_type,
                "expected_outcome": row["expected_outcome"],
                "actual_status": actual_status,
                "confidence": run["confidence"],
                "latency_ms": run["latency_ms"],
                "passed": passed,
                "error_reason": run["error_reason"],
            }
        )

    total_wall_ms = (time.perf_counter() - start_all) * 1000
    passed_count = sum(1 for r in results if r["passed"])
    success_rate = passed_count / len(results) if results else 0.0
    avg_latency = sum(r["latency_ms"] or 0 for r in results) / len(results) if results else 0.0

    summary = {
        "llm_provider": llm.name,
        "total": len(results),
        "passed": passed_count,
        "failed": len(results) - passed_count,
        "success_rate": round(success_rate, 4),
        "avg_latency_ms": round(avg_latency, 1),
        "total_wall_ms": round(total_wall_ms, 1),
    }

    (EVAL_DIR / "eval_results.json").write_text(json.dumps({"summary": summary, "results": results}, indent=2))
    write_markdown_report(summary, results)

    print(f"\nProvider: {llm.name}")
    print(f"Success rate: {passed_count}/{len(results)} ({success_rate:.0%})")
    print(f"Avg latency per email: {avg_latency:.1f}ms")
    print(f"Wrote eval_results.json and eval_report.md in {EVAL_DIR}")

    if success_rate < 0.9:
        print("\n⚠ Below the PRD's 90% target — see eval_report.md for which cases failed and why.")
        sys.exit(1)


def write_markdown_report(summary: dict, results: list[dict]) -> None:
    lines = [
        "# TaskPilot Evaluation Report",
        "",
        f"- **LLM provider:** {summary['llm_provider']}",
        f"- **Success rate:** {summary['passed']}/{summary['total']} ({summary['success_rate']:.0%})",
        f"- **Avg latency per email:** {summary['avg_latency_ms']}ms",
        f"- **Total wall time:** {summary['total_wall_ms']}ms",
        "",
        "Success = the agent's task-type classification matched the expected "
        "label AND it reached the expected terminal state (a queued, "
        "approvable draft for actionable emails; an escalation for ambiguous "
        "or low-confidence ones).",
        "",
        "| ID | Expected type | Actual type | Expected outcome | Actual status | Confidence | Result |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        mark = "✅" if r["passed"] else "❌"
        conf = f"{r['confidence']:.2f}" if r["confidence"] is not None else "-"
        lines.append(
            f"| {r['id']} | {r['expected_task_type']} | {r['actual_task_type']} | "
            f"{r['expected_outcome']} | {r['actual_status']} | {conf} | {mark} |"
        )

    failures = [r for r in results if not r["passed"]]
    if failures:
        lines += ["", "## Failures", ""]
        for r in failures:
            lines.append(f"- **{r['id']}**: expected `{r['expected_task_type']}`/`{r['expected_outcome']}`, "
                          f"got `{r['actual_task_type']}`/`{r['actual_status']}`"
                          + (f" — {r['error_reason']}" if r["error_reason"] else ""))

    (EVAL_DIR / "eval_report.md").write_text(
    "\n".join(lines) + "\n",
    encoding="utf-8"
)


if __name__ == "__main__":
    asyncio.run(main())
