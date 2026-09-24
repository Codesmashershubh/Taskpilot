from app.agent.tools.base_tool import Tool, ToolResult
from app.db import get_connection, now_iso
from app.models import ClassificationResult, EmailMessage


class LogToSheetTool(Tool):
    """
    Appends a structured row to the `tracking_sheet` table — the app's
    equivalent of the PRD's "calendar-style entry in a tracking sheet".
    This is purely internal bookkeeping (nothing external-facing sent on
    the user's behalf), so unlike draft_reply it does NOT require human
    approval before completing.
    """

    name = "log_to_sheet"

    async def run(self, *, run_id: int, email: EmailMessage, classification: ClassificationResult) -> ToolResult:
        conn = get_connection()
        conn.execute(
            """
            INSERT INTO tracking_sheet (run_id, sender, subject, task_type, key_dates, amount, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                email.sender,
                email.subject,
                classification.task_type,
                ", ".join(classification.key_dates) if classification.key_dates else "",
                classification.amount or "",
                classification.sender_intent,
                now_iso(),
            ),
        )
        conn.commit()
        return ToolResult(
            output={"row": "tracking_sheet", "task_type": classification.task_type},
            requires_approval=False,
            summary=f"Logged {classification.task_type.replace('_', ' ')} to the tracking sheet",
        )
