import json
import logging

from app.llm.base import LLMProvider
from app.models import ReflectResult

logger = logging.getLogger("taskpilot.agent.rubric")

SYSTEM_PROMPT = """[TASK=reflect]
You are a quality reviewer checking a draft email reply before a human
approves it. Check the draft against this rubric:
1. It directly addresses the sender's request/question.
2. It contains no placeholder text (TODO, [x], {{...}}) or unfinished sentences.
3. Tone is professional and matches a normal work email.
4. It's an appropriate length (not a one-liner, not an essay).

Respond with ONLY a JSON object:
{"passed": true|false, "confidence": <float 0-1>, "notes": "<one sentence>"}
"""


async def reflect_on_draft(llm: LLMProvider, draft: str, task_type: str, sender_intent: str) -> ReflectResult:
    user_prompt = json.dumps({"draft": draft, "task_type": task_type, "sender_intent": sender_intent})
    response = await llm.complete(system=SYSTEM_PROMPT, user=user_prompt, json_mode=True, max_tokens=200)
    try:
        data = json.loads(_strip_fences(response.text))
        return ReflectResult(**data)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning("Reflect step returned unparseable output, failing closed: %s", exc)
        return ReflectResult(passed=False, confidence=0.0, notes="Reflect step could not parse a verdict.")


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return text.strip()
