import time

from app.llm.base import LLMProvider, LLMResponse


class GroqProvider(LLMProvider):
    """
    Groq's free tier (https://console.groq.com) hosts open-weight Llama
    models with generous free rate limits and very low latency, which is
    why it's the PRD's recommended default cloud provider. $0 cost, so the
    cost_estimate below is always 0.0 — it's only useful for showing what
    the equivalent metered cost *would* be if you moved off the free tier.
    """

    name = "groq"

    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set")
        from groq import AsyncGroq  # imported lazily so `mock` mode never needs this package installed

        self._client = AsyncGroq(api_key=api_key)
        self._model = model

    async def complete(self, system: str, user: str, json_mode: bool = False, max_tokens: int = 800) -> LLMResponse:
        start = time.perf_counter()
        kwargs = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=max_tokens,
            temperature=0.2,
            **kwargs,
        )
        latency_ms = (time.perf_counter() - start) * 1000
        usage = resp.usage
        return LLMResponse(
            text=resp.choices[0].message.content or "",
            latency_ms=latency_ms,
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            cost_estimate=0.0,  # free tier
        )
