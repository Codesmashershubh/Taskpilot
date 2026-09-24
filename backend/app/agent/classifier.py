import json
import logging

from app.llm.base import LLMProvider
from app.models import ClassificationResult, EmailMessage

logger = logging.getLogger("taskpilot.agent.classifier")

SYSTEM_PROMPT = """[TASK=classify]
You are an email triage assistant for a personal inbox agent. Read the
email and respond with ONLY a JSON object (no prose, no markdown fences):

{
  "task_type": "meeting_request" | "invoice" | "support_question" | "other",
  "sender_intent": "<one sentence describing what the sender wants>",
  "key_dates": ["<any dates/times mentioned, as written>"],
  "amount": "<a dollar amount if present, else null>",
  "confidence": <float 0-1, how confident you are in this classification>
}
"""


async def classify_email(llm: LLMProvider, email: EmailMessage) -> ClassificationResult:
    user_prompt = f"Subject: {email.subject}\nFrom: {email.sender}\n\n{email.body}"
    response = await llm.complete(system=SYSTEM_PROMPT, user=user_prompt, json_mode=True, max_tokens=300)
    try:
        data = json.loads(_strip_fences(response.text))
        return ClassificationResult(**data)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning("Classifier returned unparseable output, defaulting to low-confidence 'other': %s", exc)
        return ClassificationResult(task_type="other", sender_intent="Could not be classified", confidence=0.0)


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return text.strip()
