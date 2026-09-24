import os
import tempfile

os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("EMAIL_SOURCE", "mock")
os.environ.setdefault("API_SECRET_KEY", "test-key")
os.environ.setdefault("ENCRYPTION_KEY", "dGVzdC1lbmNyeXB0aW9uLWtleS0zMi1ieXRlcyEh")
os.environ["DATABASE_PATH"] = os.path.join(tempfile.mkdtemp(), "test_tools.db")

import pytest

from app.agent.tools.draft_reply_tool import DraftReplyTool
from app.agent.tools.log_to_sheet_tool import LogToSheetTool
from app.db import get_connection, init_db
from app.email_source.mock_source import MockEmailSource
from app.llm.mock_provider import MockProvider
from app.models import ClassificationResult, EmailMessage


@pytest.fixture(autouse=True)
def _fresh_db():
    init_db()
    yield
    conn = get_connection()
    conn.executescript("DELETE FROM tracking_sheet; DELETE FROM runs;")
    conn.commit()


def _make_run_row() -> int:
    """log_to_sheet writes rows with a foreign key to runs(id), so tests need
    a real parent run — this mirrors what the orchestrator always does first."""
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO runs (created_at, source_email_id, status) VALUES ('2026-01-01T00:00:00Z', 'x1', 'in_progress')"
    )
    conn.commit()
    return cur.lastrowid


EMAIL = EmailMessage(
    id="x1", thread_id="th-x1", sender="D <d@example.com>", reply_to="d@example.com",
    subject="Can we meet?", body="Are you free Tuesday for a quick call?",
    received_at="2026-01-01T00:00:00Z",
)
CLASSIFICATION = ClassificationResult(
    task_type="meeting_request", sender_intent="wants a call", key_dates=["Tuesday"], confidence=0.9
)


@pytest.mark.asyncio
async def test_draft_reply_tool_requires_approval_and_never_sends():
    tool = DraftReplyTool(MockProvider(), MockEmailSource())
    result = await tool.run(email=EMAIL, classification=CLASSIFICATION)
    assert result.requires_approval is True
    assert "draft_id" in result.output
    assert result.output["to"] == "d@example.com"
    assert len(result.output["body"]) > 20


@pytest.mark.asyncio
async def test_log_to_sheet_tool_writes_row_and_skips_approval():
    run_id = _make_run_row()
    tool = LogToSheetTool()
    result = await tool.run(run_id=run_id, email=EMAIL, classification=CLASSIFICATION)
    assert result.requires_approval is False

    conn = get_connection()
    row = conn.execute("SELECT * FROM tracking_sheet WHERE run_id = ?", (run_id,)).fetchone()
    assert row is not None
    assert row["task_type"] == "meeting_request"
    assert "Tuesday" in row["key_dates"]
