"""
The core agent loop: perceive -> plan -> act -> reflect.

This is a hand-rolled loop (per the PRD's explicit choice to avoid a heavy
agent framework) so every decision point is a plain, readable, auditable
Python function rather than a black box. Every step writes a `run_steps`
row with its reasoning trace, which is what powers both the dashboard's
"reasoning trace" view and the eval script's success/failure accounting.

Policy (mirrors PRD section 5 "User Flow"):
- confidence >= threshold and task_type in {meeting_request, invoice,
  support_question} -> log to tracking sheet (auto) + draft a reply
  (queued for human approval — drafts are never sent automatically).
- confidence >= threshold and task_type == "other" -> log to tracking
  sheet (auto), then escalate for manual review (no safe default action).
- confidence < threshold, for any task_type -> log to tracking sheet
  (auto, for audit purposes), then escalate for manual review.
- If the reflect step fails the rubric, the draft is regenerated once; if
  it still fails, the run is escalated with the reviewer's notes attached
  so a human knows exactly why the agent got stuck.
"""
import asyncio
import logging
import time

from app.agent.classifier import classify_email
from app.agent.rubric import reflect_on_draft
from app.agent.tools.draft_reply_tool import DraftReplyTool
from app.agent.tools.log_to_sheet_tool import LogToSheetTool
from app.config import get_settings
from app.db import get_connection, now_iso, to_json
from app.email_source.base import EmailSource
from app.email_source.mock_source import mark_processed
from app.llm.base import LLMProvider
from app.models import EmailMessage

logger = logging.getLogger("taskpilot.agent.orchestrator")

ACTIONABLE_TYPES = {"meeting_request", "invoice", "support_question"}


class Orchestrator:
    def __init__(self, llm: LLMProvider, email_source: EmailSource):
        self._llm = llm
        self._email_source = email_source
        self._draft_tool = DraftReplyTool(llm, email_source)
        self._log_tool = LogToSheetTool()
        self._settings = get_settings()

    async def poll_and_process(self, label: str) -> list[int]:
        """Fetch new emails and run the agent loop on each. Returns the run ids created."""
        emails = await self._email_source.list_new_emails(label)
        run_ids = []
        for email in emails:
            run_id = await self.process_email(email)
            run_ids.append(run_id)
        return run_ids

    async def process_email(self, email: EmailMessage) -> int:
        start = time.perf_counter()
        run_id = self._create_run(email)
        try:
            self._step(run_id, "perceive", {"subject": email.subject, "sender": email.sender, "snippet": email.body[:280]})

            classification = await self._retry(lambda: classify_email(self._llm, email))
            self._step(run_id, "plan", classification.model_dump())
            self._update_run(run_id, task_type=classification.task_type, confidence=classification.confidence)

            # Always log to the tracking sheet — internal, non-external, auto-approved.
            log_result = await self._log_tool.run(run_id=run_id, email=email, classification=classification)
            self._record_action(run_id, self._log_tool.name, {}, log_result.output, status="completed")
            self._step(run_id, "act", {"tool": "log_to_sheet", "summary": log_result.summary})

            if classification.confidence < self._settings.confidence_threshold:
                self._escalate(run_id, f"Low classification confidence ({classification.confidence:.2f}) — flagged for manual review.")
                return run_id

            if classification.task_type not in ACTIONABLE_TYPES:
                self._escalate(run_id, f"Task type '{classification.task_type}' has no automated action — flagged for manual review.")
                return run_id

            draft_result, reflect_result = await self._draft_with_reflection(run_id, email, classification)
            action_id = self._record_action(
                run_id, self._draft_tool.name, {}, draft_result.output, status="proposed"
            )
            self._step(run_id, "act", {"tool": "draft_reply", "summary": draft_result.summary})
            self._step(run_id, "reflect", reflect_result.model_dump())

            if reflect_result.passed:
                self._update_run(run_id, status="awaiting_approval", confidence=reflect_result.confidence)
            else:
                self._escalate(
                    run_id,
                    f"Draft failed self-review after retry: {reflect_result.notes}",
                    keep_action_id=action_id,
                )

            mark_processed(email.id)
            return run_id
        except Exception as exc:  # noqa: BLE001 - the agent must never crash the poll loop
            logger.exception("Run %s failed", run_id)
            self._update_run(run_id, status="failed", error_reason=str(exc))
            return run_id
        finally:
            latency_ms = (time.perf_counter() - start) * 1000
            self._update_run(run_id, latency_ms=latency_ms)

    async def _draft_with_reflection(self, run_id: int, email: EmailMessage, classification):
        draft_result = await self._retry(lambda: self._draft_tool.run(email=email, classification=classification))
        reflect_result = await self._retry(
            lambda: reflect_on_draft(self._llm, draft_result.output["body"], classification.task_type, classification.sender_intent)
        )

        attempts = 1
        while not reflect_result.passed and attempts <= self._settings.max_retries:
            self._step(run_id, "reflect", {**reflect_result.model_dump(), "retry_attempt": attempts})
            draft_result = await self._retry(lambda: self._draft_tool.run(email=email, classification=classification))
            reflect_result = await self._retry(
                lambda: reflect_on_draft(self._llm, draft_result.output["body"], classification.task_type, classification.sender_intent)
            )
            attempts += 1

        return draft_result, reflect_result

    async def _retry(self, coro_factory):
        last_exc: Exception | None = None
        for attempt in range(self._settings.max_retries + 1):
            try:
                return await coro_factory()
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning("Attempt %s failed: %s", attempt + 1, exc)
                if attempt < self._settings.max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
        assert last_exc is not None
        raise last_exc

    # -- persistence helpers --------------------------------------------------

    def _create_run(self, email: EmailMessage) -> int:
        conn = get_connection()
        cur = conn.execute(
            """
            INSERT INTO runs (created_at, source_email_id, subject, sender, snippet, status)
            VALUES (?, ?, ?, ?, ?, 'in_progress')
            """,
            (now_iso(), email.id, email.subject, email.sender, email.body[:280]),
        )
        conn.commit()
        return cur.lastrowid

    # Every field _update_run is ever allowed to touch. Callers only ever pass
    # literal keyword arguments from our own code (never user input), but this
    # allowlist makes the dynamic SET clause provably safe rather than merely
    # safe-by-convention — an unexpected key raises instead of being interpolated.
    _UPDATABLE_RUN_FIELDS = {
        "status", "task_type", "confidence", "latency_ms", "cost_estimate", "error_reason",
    }

    def _update_run(self, run_id: int, **fields) -> None:
        if not fields:
            return
        unknown = set(fields) - self._UPDATABLE_RUN_FIELDS
        if unknown:
            raise ValueError(f"Refusing to update unrecognized run field(s): {unknown}")
        conn = get_connection()
        set_clause = ", ".join(f"{k} = ?" for k in fields)  # keys are allowlist-checked above, not user input
        conn.execute(f"UPDATE runs SET {set_clause} WHERE id = ?", (*fields.values(), run_id))  # noqa: safe-fstring-sql (keys allowlist-checked above)
        conn.commit()

    def _step(self, run_id: int, step_name: str, detail: dict) -> None:
        conn = get_connection()
        conn.execute(
            "INSERT INTO run_steps (run_id, step_name, detail, created_at) VALUES (?, ?, ?, ?)",
            (run_id, step_name, to_json(detail), now_iso()),
        )
        conn.commit()

    def _record_action(self, run_id: int, tool_name: str, input_data: dict, output_data: dict, status: str) -> int:
        conn = get_connection()
        cur = conn.execute(
            """
            INSERT INTO actions (run_id, tool_name, input, output, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (run_id, tool_name, to_json(input_data), to_json(output_data), status, now_iso()),
        )
        conn.commit()
        return cur.lastrowid

    def _escalate(self, run_id: int, reason: str, keep_action_id: int | None = None) -> None:
        self._step(run_id, "escalate", {"reason": reason})
        self._update_run(run_id, status="escalated", error_reason=reason)
        logger.info("Run %s escalated: %s", run_id, reason)
