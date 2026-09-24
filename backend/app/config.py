"""
Central configuration. All values come from environment variables / .env,
never hard-coded, so secrets never end up in source control.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # API access control
    api_secret_key: str = "change-me-to-a-long-random-string"
    encryption_key: str = ""
    frontend_origin: str = "http://localhost:5173"

    # LLM
    llm_provider: str = "mock"  # mock | groq | gemini
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"

    # Email source
    email_source: str = "mock"  # mock | gmail
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_redirect_uri: str = "http://localhost:8000/api/auth/gmail/callback"
    gmail_watch_label: str = "TaskPilot"

    # Agent behavior
    confidence_threshold: float = 0.7
    poll_interval_seconds: int = 60
    max_retries: int = 1

    # Storage
    database_path: str = "./taskpilot.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
