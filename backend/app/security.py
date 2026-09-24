"""
Security primitives used across the app.

Design notes (also called out in the README):
- This app is built for a single, personal user running it locally or on a
  free hosting tier — NOT as a multi-tenant public service. Auth is a single
  shared bearer token, which is appropriate for that use case but is NOT
  sufficient if you ever expose this to multiple untrusted users. Swap in
  real session/OAuth-based auth per-user before doing that.
- Gmail OAuth refresh tokens are encrypted at rest with Fernet (symmetric,
  authenticated encryption) so a leaked SQLite file alone doesn't leak
  Gmail access.
- The Gmail scopes requested are read-only + compose ONLY. There is no
  "send" scope anywhere in this codebase, so even a fully compromised
  server cannot send email on the user's behalf — sending is always a
  manual, human action inside Gmail itself.
"""
import hmac
import logging

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings

logger = logging.getLogger("taskpilot.security")

bearer_scheme = HTTPBearer(auto_error=False)

# In-memory, per-process rate limiter. Fine for a single-instance local /
# free-tier deployment; swap for a shared backend (e.g. Redis) if you ever
# run multiple worker processes.
limiter = Limiter(key_func=get_remote_address)


def verify_api_key(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> None:
    """FastAPI dependency: require `Authorization: Bearer <API_SECRET_KEY>`."""
    settings = get_settings()
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    # Constant-time comparison to avoid timing side-channels.
    if not hmac.compare_digest(credentials.credentials, settings.api_secret_key):
        logger.warning("Rejected request with invalid API key")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")


def _fernet() -> Fernet:
    settings = get_settings()
    if not settings.encryption_key:
        raise RuntimeError(
            "ENCRYPTION_KEY is not set. Generate one with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(settings.encryption_key.encode())


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError("Could not decrypt stored token — ENCRYPTION_KEY may have changed") from exc


def redact(value: str, keep: int = 4) -> str:
    """Redact a secret for safe logging, e.g. 'ya29.a0AfH6...' -> 'ya29****'."""
    if not value:
        return ""
    if len(value) <= keep:
        return "*" * len(value)
    return value[:keep] + "*" * max(4, len(value) - keep)
