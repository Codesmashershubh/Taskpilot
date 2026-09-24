import json
import logging
import uuid
from pathlib import Path

from app.db import get_connection, now_iso
from app.email_source.base import EmailSource
from app.models import EmailMessage
from app.sanitize import extract_email_address, sanitize_text

logger = logging.getLogger("taskpilot.email.mock")

SAMPLE_FILE = Path(__file__).parent / "sample_emails.json"


class MockEmailSource(EmailSource):
    """Reads a small bundled inbox fixture. No OAuth, no network — this is
    what EMAIL_SOURCE=mock uses, so the whole product works immediately
    after `pip install -r requirements.txt`, no Google Cloud project needed."""

    name = "mock"

    async def list_new_emails(self, label: str) -> list[EmailMessage]:
        raw = json.loads(SAMPLE_FILE.read_text(encoding="utf-8"))
        conn = get_connection()
        processed = {row["email_id"] for row in conn.execute("SELECT email_id FROM processed_emails")}
        return [
            EmailMessage(
                id=e["id"],
                thread_id=e["thread_id"],
                sender=sanitize_text(e["sender"]),
                reply_to=extract_email_address(e["sender"]),
                subject=sanitize_text(e["subject"]),
                body=sanitize_text(e["body"]),
                received_at=e["received_at"],
            )
            for e in raw
            if e["id"] not in processed
        ]

    async def create_draft(self, thread_id: str, to: str, subject: str, body: str) -> str:
        draft_id = f"mock-draft-{uuid.uuid4().hex[:8]}"
        logger.info("Mock draft created (not sent): %s -> %s | %s", draft_id, to, subject)
        return draft_id


def mark_processed(email_id: str) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO processed_emails (email_id, processed_at) VALUES (?, ?)",
        (email_id, now_iso()),
    )
    conn.commit()
