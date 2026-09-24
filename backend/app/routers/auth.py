"""
Gmail OAuth endpoints.

These two routes are reached by browser navigation/redirect (the user
clicks a link, Google redirects back), so they can't carry an
`Authorization: Bearer` header the way the rest of the API does. Two
different protections are used instead:

- /gmail/login accepts the API key as a `?key=` query param as well as a
  header, so the dashboard can render it as a plain link.
- /gmail/callback never trusts the bearer token at all; it trusts a
  single-use, time-limited `state` value that *this server* generated a
  moment earlier, which is the standard CSRF defense for OAuth redirects.

This app is meant for local/personal use (see README "Security Notes").
If you deploy it somewhere multi-user, put real session auth in front of
these routes.
"""
import hmac
import secrets
import time

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import get_settings
from app.security import limiter, verify_api_key

router = APIRouter(prefix="/api/auth", tags=["auth"])

_STATE_TTL_SECONDS = 600
_pending_states: dict[str, float] = {}


def _check_key(key: str | None, request: Request) -> None:
    settings = get_settings()
    header = request.headers.get("authorization", "")
    header_token = header.removeprefix("Bearer ").strip() if header.startswith("Bearer ") else None
    supplied = key or header_token
    if not supplied or not hmac.compare_digest(supplied, settings.api_secret_key):
        raise HTTPException(status_code=401, detail="Missing or invalid key")


@router.get("/gmail/login")
@limiter.limit("10/minute")
def gmail_login(request: Request, key: str | None = Query(default=None)):
    _check_key(key, request)
    from app.email_source.gmail_client import build_authorization_url  # lazy import: optional dependency

    state = secrets.token_urlsafe(24)
    _pending_states[state] = time.time()
    _prune_states()
    url = build_authorization_url(state)
    return RedirectResponse(url)


@router.get("/gmail/callback")
def gmail_callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None):
    if error:
        return HTMLResponse(f"<h3>Gmail connection cancelled</h3><p>{error}</p>", status_code=400)
    if not code or not state or state not in _pending_states:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    created_at = _pending_states.pop(state)
    if time.time() - created_at > _STATE_TTL_SECONDS:
        raise HTTPException(status_code=400, detail="OAuth state expired, please try connecting again")

    from app.email_source.gmail_client import exchange_code_for_token  # lazy import: optional dependency

    exchange_code_for_token(code, state)
    return HTMLResponse(
        "<h3>Gmail connected</h3><p>TaskPilot can now read the watched label and create draft "
        "replies. It will never send email automatically. You can close this tab.</p>"
    )


@router.get("/gmail/status", dependencies=[Depends(verify_api_key)])
@limiter.limit("60/minute")
def gmail_status(request: Request):
    from app.email_source.gmail_client import is_connected  # lazy import: optional dependency

    return {"connected": is_connected()}


def _prune_states() -> None:
    cutoff = time.time() - _STATE_TTL_SECONDS
    expired = [s for s, ts in _pending_states.items() if ts < cutoff]
    for s in expired:
        _pending_states.pop(s, None)
