import json

from app.agent.tools.base_tool import Tool, ToolResult
from app.email_source.base import EmailSource
from app.llm.base import LLMProvider
from app.models import ClassificationResult, EmailMessage

SYSTEM_PROMPT = """[TASK=draft_reply]
You are drafting a reply on behalf of the inbox owner. You will be given
JSON context about the email and its classification. Write ONLY the body
text of the reply email (no subject line, no JSON, no markdown) — a
complete, professional, appropriately brief reply that a person could send
as-is. Never invent facts (dates, prices, commitments) that weren't in the
source email or classification context.
"""


class DraftReplyTool(Tool):
    """
    Generates a reply and saves it as a Gmail DRAFT — never sends. Per the
    PRD, this is exactly the kind of external-facing artifact that goes
    through the human approval queue before the user manually sends it.
    """

    name = "draft_reply"

    def __init__(self, llm: LLMProvider, email_source: EmailSource):
        self._llm = llm
        self._email_source = email_source

    async def run(self, *, email: EmailMessage, classification: ClassificationResult) -> ToolResult:
        context = {
            "sender": email.sender,
            "subject": email.subject,
            "task_type": classification.task_type,
            "sender_intent": classification.sender_intent,
            "key_dates": classification.key_dates,
            "amount": classification.amount,
        }
        response = await self._llm.complete(
            system=SYSTEM_PROMPT, user=json.dumps(context), json_mode=False, max_tokens=400
        )
        draft_text = response.text.strip()

        reply_to = email.reply_to
        draft_id = await self._email_source.create_draft(
            thread_id=email.thread_id,
            to=reply_to,
            subject=f"Re: {email.subject}",
            body=draft_text,
        )

        return ToolResult(
            output={"draft_id": draft_id, "to": reply_to, "subject": f"Re: {email.subject}", "body": draft_text},
            requires_approval=True,
            summary=f"Drafted a reply to {reply_to} (saved as an unsent Gmail draft, awaiting your approval)",
        )
