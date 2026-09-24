import time

from app.llm.base import LLMProvider, LLMResponse


class GeminiProvider(LLMProvider):
    """Google Gemini free tier (https://aistudio.google.com) — the PRD's fallback provider."""

    name = "gemini"

    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        import google.generativeai as genai  # lazy import, mirrors GroqProvider

        genai.configure(api_key=api_key)
        self._genai = genai
        self._model_name = model

    async def complete(self, system: str, user: str, json_mode: bool = False, max_tokens: int = 800) -> LLMResponse:
        start = time.perf_counter()
        generation_config = {"max_output_tokens": max_tokens, "temperature": 0.2}
        if json_mode:
            generation_config["response_mime_type"] = "application/json"
        model = self._genai.GenerativeModel(model_name=self._model_name, system_instruction=system)
        resp = await model.generate_content_async(user, generation_config=generation_config)
        latency_ms = (time.perf_counter() - start) * 1000
        usage = getattr(resp, "usage_metadata", None)
        return LLMResponse(
            text=resp.text or "",
            latency_ms=latency_ms,
            input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
            output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
            cost_estimate=0.0,  # free tier
        )
