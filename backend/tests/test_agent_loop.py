"""
Run with: pytest tests/ -v
Uses LLM_PROVIDER=mock and EMAIL_SOURCE=mock (set in conftest.py-less fashion
via env vars below) so tests run with zero external dependencies or API keys.
"""
import os
import tempfile

os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("EMAIL_SOURCE", "mock")
os.environ.setdefault("API_SECRET_KEY", "test-key")
os.environ.setdefault("ENCRYPTION_KEY", "dGVzdC1lbmNyeXB0aW9uLWtleS0zMi1ieXRlcyEh")  # not used by these tests
os.environ["DATABASE_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")

import pytest

from app.agent.orchestrator import Orchestrator
from app.db import get_connection, init_db
from app.email_source.mock_source import MockEmailSource
from app.llm.mock_provider import MockProvider
from app.models import EmailMessage


@pytest.fixture(autouse=True)
def _fresh_db():
    init_db()
    yield
    conn = get_connection()
    conn.executescript("DELETE FROM runs; DELETE FROM run_steps; DELETE FROM actions; DELETE FROM tracking_sheet; DELETE FROM processed_emails;")
    conn.commit()


def _make_orchestrator() -> Orchestrator:
    return Orchestrator(llm=MockProvider(), email_source=MockEmailSource())


@pytest.mark.asyncio
async def test_meeting_request_reaches_awaiting_approval():
    orch = _make_orchestrator()
    email = EmailMessage(
        id="t1", thread_id="th1", sender="A <a@example.com>", reply_to="a@example.com",
        subject="Sync?", body="Are you available for a call next week? Monday works for me.",
        received_at="2026-01-01T00:00:00Z",
    )
    run_id = await orch.process_email(email)

    conn = get_connection()
    run = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    assert run["status"] == "awaiting_approval"
    assert run["task_type"] == "meeting_request"

    actions = conn.execute("SELECT * FROM actions WHERE run_id=?", (run_id,)).fetchall()
    tool_names = {a["tool_name"] for a in actions}
    assert "log_to_sheet" in tool_names
    assert "draft_reply" in tool_names


@pytest.mark.asyncio
async def test_low_confidence_email_escalates():
    orch = _make_orchestrator()
    email = EmailMessage(
        id="t2", thread_id="th2", sender="B <b@example.com>", reply_to="b@example.com",
        subject="Thoughts?", body="No real ask here, just sharing something.",
        received_at="2026-01-01T00:00:00Z",
    )
    run_id = await orch.process_email(email)

    conn = get_connection()
    run = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    assert run["status"] == "escalated"
    assert run["error_reason"] is not None


@pytest.mark.asyncio
async def test_invoice_extracts_amount_and_logs_to_sheet():
    orch = _make_orchestrator()
    email = EmailMessage(
        id="t3", thread_id="th3", sender="Billing <billing@vendor.example.com>", reply_to="billing@vendor.example.com",
        subject="Invoice due", body="Invoice #99 for $500.00 is now due. Please remit payment.",
        received_at="2026-01-01T00:00:00Z",
    )
    run_id = await orch.process_email(email)

    conn = get_connection()
    run = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    assert run["task_type"] == "invoice"

    sheet_row = conn.execute("SELECT * FROM tracking_sheet WHERE run_id=?", (run_id,)).fetchone()
    assert sheet_row is not None
    assert "$500.00" in sheet_row["amount"]


@pytest.mark.asyncio
async def test_reply_never_uses_send_only_draft():
    """Structural guarantee: the tool registry has no 'send' capability at all."""
    orch = _make_orchestrator()
    assert not hasattr(orch._email_source, "send")
    assert not hasattr(orch._email_source, "send_email")


@pytest.mark.asyncio
async def test_sender_display_preserves_angle_brackets():
    """Regression test: sanitization must not corrupt 'Name <email>' headers."""
    orch = _make_orchestrator()
    email = EmailMessage(
        id="t4", thread_id="th4", sender="C <c@example.com>", reply_to="c@example.com",
        subject="Quick question", body="Can you help me, I have an issue with login?",
        received_at="2026-01-01T00:00:00Z",
    )
    run_id = await orch.process_email(email)
    conn = get_connection()
    run = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    assert "<c@example.com>" in run["sender"]
