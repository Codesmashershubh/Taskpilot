from functools import lru_cache

from app.config import get_settings
from app.llm.base import LLMProvider
from app.llm.mock_provider import MockProvider


@lru_cache
def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    provider = settings.llm_provider.lower()

    if provider == "groq":
        from app.llm.groq_provider import GroqProvider

        return GroqProvider(api_key=settings.groq_api_key, model=settings.groq_model)
    if provider == "gemini":
        from app.llm.gemini_provider import GeminiProvider

        return GeminiProvider(api_key=settings.gemini_api_key, model=settings.gemini_model)
    if provider == "mock":
        return MockProvider()

    raise ValueError(f"Unknown LLM_PROVIDER '{settings.llm_provider}'. Use mock | groq | gemini.")
