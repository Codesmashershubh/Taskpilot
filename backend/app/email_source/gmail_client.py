"""
Real Gmail access via OAuth 2.0, using Google's free Gmail API.

Security-relevant choices:
- SCOPES is limited to `gmail.readonly` + `gmail.compose`. There is no
  `gmail.send` or `gmail.modify` scope requested anywhere, so even if this
  server were fully compromised, the attacker could not send email or
  delete/modify the user's mailbox through these credentials — only read
  messages and create (unsent) drafts. This is the technical backbone of
  the PRD's "zero irreversible actions without confirmation" requirement:
  sending is not just gated by app logic, it's outside what the OAuth
  grant even allows.
- The refresh token is encrypted at rest (see app.security) before being
  written to SQLite, and never logged in plaintext.
"""
import asyncio
import base64
import logging
from email.mime.text import MIMEText

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from app.config import get_settings
from app.db import get_connection, now_iso
from app.email_source.base import EmailSource
from app.models import EmailMessage
from app.sanitize import extract_email_address, sanitize_text
from app.security import decrypt_secret, encrypt_secret, redact

logger = logging.getLogger("taskpilot.email.gmail")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]


def _client_config() -> dict:
    settings = get_settings()
    return {
        "web": {
            "client_id": settings.gmail_client_id,
            "client_secret": settings.gmail_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.gmail_redirect_uri],
        }
    }


def build_authorization_url(state: str) -> str:
    settings = get_settings()
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, state=state)
    flow.redirect_uri = settings.gmail_redirect_uri
    url, _ = flow.authorization_url(access_type="offline", include_granted_scopes="true", prompt="consent")
    return url


def exchange_code_for_token(code: str, state: str) -> None:
    settings = get_settings()
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, state=state)
    flow.redirect_uri = settings.gmail_redirect_uri
    flow.fetch_token(code=code)
    creds = flow.credentials
    _store_credentials(creds)
    logger.info("Stored Gmail credentials (refresh token %s)", redact(creds.refresh_token or ""))


def _store_credentials(creds: Credentials) -> None:
    payload = encrypt_secret(creds.to_json())
    conn = get_connection()
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO oauth_tokens (provider, encrypted_token, created_at, updated_at)
        VALUES ('gmail', ?, ?, ?)
        ON CONFLICT(provider) DO UPDATE SET encrypted_token=excluded.encrypted_token, updated_at=excluded.updated_at
        """,
        (payload, ts, ts),
    )
    conn.commit()


def _load_credentials() -> Credentials | None:
    conn = get_connection()
    row = conn.execute("SELECT encrypted_token FROM oauth_tokens WHERE provider='gmail'").fetchone()
    if not row:
        return None
    creds = Credentials.from_authorized_user_info(__import__("json").loads(decrypt_secret(row["encrypted_token"])), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleAuthRequest())
        _store_credentials(creds)
    return creds


def is_connected() -> bool:
    return _load_credentials() is not None


class GmailEmailSource(EmailSource):
    name = "gmail"

    def _service(self):
        creds = _load_credentials()
        if creds is None:
            raise RuntimeError("Gmail is not connected yet. Visit /api/auth/gmail/login first.")
        return build("gmail", "v1", credentials=creds, cache_discovery=False)

    async def list_new_emails(self, label: str) -> list[EmailMessage]:
        return await asyncio.to_thread(self._list_new_emails_sync, label)

    def _list_new_emails_sync(self, label: str) -> list[EmailMessage]:
        service = self._service()
        label_id = self._resolve_label_id(service, label)
        if label_id is None:
            logger.warning("Gmail label '%s' not found — create it in Gmail first", label)
            return []

        conn = get_connection()
        processed = {row["email_id"] for row in conn.execute("SELECT email_id FROM processed_emails")}

        results = service.users().messages().list(userId="me", labelIds=[label_id], maxResults=25).execute()
        messages = results.get("messages", [])

        out: list[EmailMessage] = []
        for m in messages:
            if m["id"] in processed:
                continue
            full = service.users().messages().get(userId="me", id=m["id"], format="full").execute()
            out.append(self._parse_message(full))
        return out

    @staticmethod
    def _resolve_label_id(service, label_name: str) -> str | None:
        labels = service.users().labels().list(userId="me").execute().get("labels", [])
        for lab in labels:
            if lab["name"].lower() == label_name.lower():
                return lab["id"]
        return None

    @staticmethod
    def _parse_message(full: dict) -> EmailMessage:
        headers = {h["name"].lower(): h["value"] for h in full["payload"].get("headers", [])}
        body = GmailEmailSource._extract_plain_text(full["payload"])
        raw_sender = headers.get("from", "unknown")
        return EmailMessage(
            id=full["id"],
            thread_id=full["threadId"],
            sender=sanitize_text(raw_sender),
            reply_to=extract_email_address(raw_sender),
            subject=sanitize_text(headers.get("subject", "(no subject)")),
            body=sanitize_text(body or full.get("snippet", "")),
            received_at=headers.get("date", ""),
        )

    @staticmethod
    def _extract_plain_text(payload: dict) -> str:
        if payload.get("mimeType") == "text/plain" and "data" in payload.get("body", {}):
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
        for part in payload.get("parts", []) or []:
            text = GmailEmailSource._extract_plain_text(part)
            if text:
                return text
        return ""

    async def create_draft(self, thread_id: str, to: str, subject: str, body: str) -> str:
        return await asyncio.to_thread(self._create_draft_sync, thread_id, to, subject, body)

    def _create_draft_sync(self, thread_id: str, to: str, subject: str, body: str) -> str:
        service = self._service()
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        draft = (
            service.users()
            .drafts()
            .create(userId="me", body={"message": {"raw": raw, "threadId": thread_id}})
            .execute()
        )
        logger.info("Gmail draft created (not sent): %s", draft["id"])
        return draft["id"]
