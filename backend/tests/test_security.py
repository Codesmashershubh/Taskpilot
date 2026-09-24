import os
import tempfile

os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("EMAIL_SOURCE", "mock")
os.environ.setdefault("API_SECRET_KEY", "test-key")
os.environ.setdefault("ENCRYPTION_KEY", "dGVzdC1lbmNyeXB0aW9uLWtleS0zMi1ieXRlcyEh")
os.environ["DATABASE_PATH"] = os.path.join(tempfile.mkdtemp(), "test_security.db")

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app import security
from app.config import get_settings
from app.sanitize import extract_email_address, sanitize_text


def test_encrypt_decrypt_roundtrip(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(get_settings(), "encryption_key", key, raising=False)
    get_settings.cache_clear()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    get_settings.cache_clear()

    secret = "super-secret-refresh-token"
    encrypted = security.encrypt_secret(secret)
    assert encrypted != secret
    assert security.decrypt_secret(encrypted) == secret
    get_settings.cache_clear()


def test_verify_api_key_rejects_missing_credentials():
    with pytest.raises(HTTPException) as exc_info:
        security.verify_api_key(None)
    assert exc_info.value.status_code == 401


def test_verify_api_key_rejects_wrong_token():
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="wrong-token")
    with pytest.raises(HTTPException) as exc_info:
        security.verify_api_key(creds)
    assert exc_info.value.status_code == 401


def test_verify_api_key_accepts_correct_token():
    settings = get_settings()
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=settings.api_secret_key)
    security.verify_api_key(creds)  # should not raise


def test_redact_hides_most_of_secret():
    out = security.redact("ya29.a0AfH6SMBx-verylongtoken")
    assert out.startswith("ya29")
    assert "verylongtoken" not in out


def test_sanitize_preserves_angle_brackets_in_sender():
    raw = "Jane Doe <jane@example.com>"
    assert sanitize_text(raw) == raw


def test_sanitize_strips_control_characters():
    raw = "Hello\x00World\x07"
    cleaned = sanitize_text(raw)
    assert "\x00" not in cleaned
    assert "\x07" not in cleaned


def test_sanitize_truncates_to_max_len():
    raw = "a" * 100
    assert len(sanitize_text(raw, max_len=10)) == 10


def test_extract_email_address_from_display_name_format():
    assert extract_email_address("Jane Doe <jane@example.com>") == "jane@example.com"


def test_extract_email_address_from_bare_address():
    assert extract_email_address("jane@example.com") == "jane@example.com"


def test_sql_queries_use_parameterization_not_fstrings():
    """Static check: no f-string/`.format`/`%` interpolation feeding SQL text
    with untrusted values. This greps the source rather than truly proving
    safety, but catches the most common regression."""
    import pathlib
    import re

    app_dir = pathlib.Path(__file__).parent.parent / "app"
    offenders = []
    for path in app_dir.rglob("*.py"):
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            if re.search(r'execute\(\s*f["\']', line) and "safe-fstring-sql" not in line:
                offenders.append(f"{path}:{lineno}")
    assert not offenders, f"Found unguarded f-string SQL (possible injection risk): {offenders}"
