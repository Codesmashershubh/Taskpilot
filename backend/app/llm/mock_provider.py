"""
A deterministic, offline "LLM" so the whole agent loop (perceive -> plan ->
act -> reflect) runs end-to-end with zero setup: no API key, no network
call, no cost. This is what LLM_PROVIDER=mock uses, and it's also what the
eval script runs against by default so `python eval/run_eval.py` works the
moment you clone the repo.

It works by pattern-matching on a `[TASK=...]` marker that each call site
(classifier / draft_reply_tool / rubric) puts at the start of its system
prompt — see those files. Swapping to Groq or Gemini requires zero code
changes elsewhere, only LLM_PROVIDER in .env, because every provider
implements the same `complete(system, user, json_mode)` interface.
"""
import json
import re
import time

from app.llm.base import LLMProvider, LLMResponse

DATE_PATTERN = re.compile(
    r"\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*\b|"
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(st|nd|rd|th)?\b|"
    r"\b\d{1,2}/\d{1,2}(/\d{2,4})?\b|"
    r"\bnext week\b|\btomorrow\b|\btoday\b",
    re.IGNORECASE,
)
AMOUNT_PATTERN = re.compile(r"\$\s?[\d,]+(\.\d{2})?")

INVOICE_KEYWORDS = ["invoice", "payment due", "amount due", "balance due", "invoice #", "please remit"]
MEETING_KEYWORDS = ["meeting", "schedule a call", "are you available", "calendar", "sync up", "book some time"]
SUPPORT_KEYWORDS = ["issue", "error", "not working", "help", "support", "bug", "trouble", "broken"]


class MockProvider(LLMProvider):
    name = "mock"

    async def complete(self, system: str, user: str, json_mode: bool = False, max_tokens: int = 800) -> LLMResponse:
        start = time.perf_counter()
        task = _extract_task(system)

        if task == "classify":
            text = _mock_classify(user)
        elif task == "draft_reply":
            text = _mock_draft_reply(user)
        elif task == "reflect":
            text = _mock_reflect(user)
        else:
            text = "{}" if json_mode else ""

        latency_ms = (time.perf_counter() - start) * 1000
        return LLMResponse(
            text=text,
            latency_ms=latency_ms,
            input_tokens=len(user.split()),
            output_tokens=len(text.split()),
            cost_estimate=0.0,
        )


def _extract_task(system: str) -> str:
    m = re.match(r"\[TASK=(\w+)\]", system)
    return m.group(1) if m else "unknown"


def _mock_classify(user: str) -> str:
    lower = user.lower()
    dates = list({m.group(0) for m in DATE_PATTERN.finditer(user)})[:3]
    amounts = AMOUNT_PATTERN.findall(user)
    amount_match = AMOUNT_PATTERN.search(user)

    if any(k in lower for k in INVOICE_KEYWORDS) or amount_match:
        result = {
            "task_type": "invoice",
            "sender_intent": "Requesting payment for an invoice",
            "key_dates": dates,
            "amount": amount_match.group(0) if amount_match else None,
            "confidence": 0.92 if amount_match else 0.78,
        }
    elif any(k in lower for k in MEETING_KEYWORDS):
        result = {
            "task_type": "meeting_request",
            "sender_intent": "Proposing a meeting or call",
            "key_dates": dates,
            "amount": None,
            "confidence": 0.88 if dates else 0.65,
        }
    elif any(k in lower for k in SUPPORT_KEYWORDS):
        result = {
            "task_type": "support_question",
            "sender_intent": "Asking a question or reporting a problem",
            "key_dates": dates,
            "amount": None,
            "confidence": 0.8,
        }
    else:
        result = {
            "task_type": "other",
            "sender_intent": "Unclear intent — does not match a known pattern",
            "key_dates": dates,
            "amount": None,
            "confidence": 0.4,
        }
    return json.dumps(result)


def _mock_draft_reply(user: str) -> str:
    try:
        ctx = json.loads(user)
    except json.JSONDecodeError:
        ctx = {}

    sender_name = (ctx.get("sender") or "there").split("<")[0].strip().split(" ")[0] or "there"
    task_type = ctx.get("task_type", "other")
    subject = ctx.get("subject", "your message")
    dates = ctx.get("key_dates") or []
    amount = ctx.get("amount")

    if task_type == "meeting_request":
        when = f" for {dates[0]}" if dates else ""
        body = (
            f"Hi {sender_name},\n\n"
            f"Thanks for reaching out about \"{subject}\". That time works{when} — "
            f"I've noted it and will send a calendar invite shortly. Let me know if "
            f"anything changes on your end.\n\nBest,\n"
        )
    elif task_type == "invoice":
        amt = f" of {amount}" if amount else ""
        body = (
            f"Hi {sender_name},\n\n"
            f"Thanks for sending over the invoice for \"{subject}\". I've logged the "
            f"amount{amt} for processing and it's now in our tracking sheet for "
            f"follow-up. I'll reach out if anything looks off.\n\nBest,\n"
        )
    elif task_type == "support_question":
        body = (
            f"Hi {sender_name},\n\n"
            f"Thanks for the note on \"{subject}\" — I've read through the details "
            f"and I'm looking into it. I'll follow up with next steps shortly.\n\n"
            f"Best,\n"
        )
    else:
        body = (
            f"Hi {sender_name},\n\n"
            f"Thanks for your message about \"{subject}\". I've flagged this for a "
            f"closer look since it doesn't match a routine request, and I'll follow "
            f"up personally.\n\nBest,\n"
        )
    return body


def _mock_reflect(user: str) -> str:
    try:
        ctx = json.loads(user)
    except json.JSONDecodeError:
        ctx = {}
    draft = ctx.get("draft", "") or ""
    placeholder_markers = ["TODO", "[placeholder]", "{{", "}}", "XXX"]
    has_placeholder = any(marker.lower() in draft.lower() for marker in placeholder_markers)
    too_short = len(draft.strip()) < 40
    greets = draft.strip().lower().startswith(("hi", "hello", "dear"))

    if has_placeholder:
        result = {"passed": False, "confidence": 0.2, "notes": "Draft still contains placeholder text."}
    elif too_short:
        result = {"passed": False, "confidence": 0.35, "notes": "Draft is too short to be a complete reply."}
    elif not greets:
        result = {"passed": False, "confidence": 0.5, "notes": "Draft is missing a greeting / doesn't read as a complete message."}
    else:
        result = {"passed": True, "confidence": 0.9, "notes": "Draft addresses the sender's message with an appropriate greeting and closing."}
    return json.dumps(result)
