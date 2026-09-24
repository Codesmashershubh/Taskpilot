from functools import lru_cache

from app.config import get_settings
from app.email_source.base import EmailSource
from app.email_source.mock_source import MockEmailSource


@lru_cache
def get_email_source() -> EmailSource:
    settings = get_settings()
    source = settings.email_source.lower()

    if source == "gmail":
        from app.email_source.gmail_client import GmailEmailSource

        return GmailEmailSource()
    if source == "mock":
        return MockEmailSource()

    raise ValueError(f"Unknown EMAIL_SOURCE '{settings.email_source}'. Use mock | gmail.")
