"""GmailAPIProvider — real implementation, Phase W-4b Layer 1 Step 2.

Provider-side methods wrap Gmail API HTTP calls via httpx. OAuth
token resolution goes through ``oauth_service.ensure_fresh_token``
which the caller passes in via ``account_config["access_token"]``
(injected at call site to keep the provider class stateless).

**Step 2 testing constraint:** real Gmail API calls require
production OAuth credentials I can't provision. Tests inject a mock
``httpx.MockTransport`` via the ``http_client`` injection seam so
the wire format is verifiable without real API access.
"""

from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone
from email.utils import parseaddr, parsedate_to_datetime
from typing import Any

import httpx

from app.services.email.providers.base import (
    EmailProvider,
    ProviderAttachment,
    ProviderConnectResult,
    ProviderFetchedMessage,
    ProviderSendResult,
    ProviderSyncResult,
)


logger = logging.getLogger(__name__)


_GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"


class GmailAPIProvider(EmailProvider):
    provider_type = "gmail"
    display_label = "Gmail / Google Workspace"
    supports_inbound = True
    supports_realtime = True

    def __init__(self, account_config: dict[str, Any]) -> None:
        super().__init__(account_config)
        self._http: httpx.Client | None = None

    @property
    def access_token(self) -> str:
        token = self.account_config.get("access_token")
        if not token:
            raise RuntimeError(
                "GmailAPIProvider requires access_token in account_config "
                "— caller must inject via oauth_service.ensure_fresh_token "
                "before calling provider methods."
            )
        return token

    def _client(self) -> httpx.Client:
        if self._http is None:
            self._http = httpx.Client(
                timeout=30.0,
                headers={"Authorization": f"Bearer {self.access_token}"},
            )
        return self._http

    # ── Lifecycle ────────────────────────────────────────────────────

    def connect(
        self, oauth_redirect_payload: dict[str, Any] | None = None
    ) -> ProviderConnectResult:
        # Step 2: connection lifecycle handled centrally by
        # oauth_service.complete_oauth_exchange. This stub stays
        # simple — when called with a payload it would forward into
        # oauth_service; when called without it returns success
        # indicating the row can be created with credentials persisted
        # later via OAuth callback.
        if oauth_redirect_payload is None:
            return ProviderConnectResult(
                success=True,
                error_message=(
                    "Gmail account row created — complete OAuth flow "
                    "to persist credentials."
                ),
            )
        return ProviderConnectResult(
            success=True,
            provider_account_id=oauth_redirect_payload.get("email"),
        )

    def disconnect(self) -> None:
        if self._http is not None:
            self._http.close()
            self._http = None

    # ── Sync ─────────────────────────────────────────────────────────

    def sync_initial(self, *, max_messages: int = 1000) -> ProviderSyncResult:
        """Initial backfill — fetches recent messages from inbox.

        Strategy: list message ids → fetch each (full payload) →
        return as a ProviderSyncResult shape with cursor (Gmail
        ``historyId`` from profile endpoint as the realtime cursor).
        Caller's ingestion pipeline persists each message.

        Note: this method returns counts only. The caller is
        responsible for fetching + ingesting individual messages
        via ``fetch_message``. We capture the latest historyId for
        future incremental syncs.
        """
        client = self._client()
        # Get historyId for incremental sync cursor
        try:
            r = client.get(f"{_GMAIL_API_BASE}/users/me/profile")
            r.raise_for_status()
            history_id = str(r.json().get("historyId", ""))
        except Exception as exc:  # noqa: BLE001
            return ProviderSyncResult(
                success=False,
                error_message=f"Gmail profile fetch failed: {exc}",
            )

        # List recent messages
        try:
            params = {"maxResults": min(max_messages, 500)}
            r = client.get(
                f"{_GMAIL_API_BASE}/users/me/messages", params=params
            )
            r.raise_for_status()
            messages = r.json().get("messages", [])
        except Exception as exc:  # noqa: BLE001
            return ProviderSyncResult(
                success=False,
                error_message=f"Gmail message list failed: {exc}",
            )

        return ProviderSyncResult(
            success=True,
            messages_synced=len(messages),
            threads_synced=len({m.get("threadId") for m in messages}),
            last_sync_at=datetime.now(timezone.utc),
            last_history_id=history_id,
        )

    def subscribe_realtime(self) -> bool:
        """Set up Gmail Pub/Sub watch.

        Step 2 records the intent (returns True). Real Pub/Sub topic
        configuration + watch.users API call ships in Step 2.1 when
        Pub/Sub topic is provisioned. The webhook handler endpoint is
        in place; the watch subscription is the provisioning gap.
        """
        return True

    def fetch_message(self, provider_message_id: str) -> ProviderFetchedMessage:
        client = self._client()
        r = client.get(
            f"{_GMAIL_API_BASE}/users/me/messages/{provider_message_id}",
            params={"format": "full"},
        )
        r.raise_for_status()
        payload = r.json()
        return _parse_gmail_message(payload)

    def fetch_attachment(
        self, provider_message_id: str, provider_attachment_id: str
    ) -> bytes:
        client = self._client()
        r = client.get(
            f"{_GMAIL_API_BASE}/users/me/messages/"
            f"{provider_message_id}/attachments/{provider_attachment_id}"
        )
        r.raise_for_status()
        data_b64 = r.json().get("data", "")
        # Gmail uses URL-safe base64 without padding
        return base64.urlsafe_b64decode(data_b64 + "=" * (-len(data_b64) % 4))

    def send_message(
        self,
        *,
        from_address: str,
        to: list[tuple[str, str | None]],
        cc: list[tuple[str, str | None]] | None = None,
        bcc: list[tuple[str, str | None]] | None = None,
        subject: str,
        body_html: str | None = None,
        body_text: str | None = None,
        in_reply_to_provider_id: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> ProviderSendResult:
        """Send via Gmail API users.messages.send.

        Constructs an RFC 5322 message + base64-url-safe encodes the
        raw bytes per Gmail API spec. Returns the provider message id
        for outbound deduplication on the next inbound sync of the
        Sent folder.
        """
        # Build RFC 5322 message via stdlib email — handles headers,
        # multipart bodies, In-Reply-To threading.
        from email.message import EmailMessage as MimeMessage

        mime = MimeMessage()
        mime["From"] = _format_address(from_address, None)
        mime["To"] = ", ".join(_format_address(a, n) for a, n in to)
        if cc:
            mime["Cc"] = ", ".join(_format_address(a, n) for a, n in cc)
        if bcc:
            mime["Bcc"] = ", ".join(_format_address(a, n) for a, n in bcc)
        mime["Subject"] = subject or ""
        if in_reply_to_provider_id:
            # RFC 5322 In-Reply-To header — Gmail uses this for threading.
            mime["In-Reply-To"] = f"<{in_reply_to_provider_id}>"
            mime["References"] = f"<{in_reply_to_provider_id}>"

        if body_html and body_text:
            mime.set_content(body_text)
            mime.add_alternative(body_html, subtype="html")
        elif body_html:
            mime.set_content(body_html, subtype="html")
        else:
            mime.set_content(body_text or "")

        for att in attachments or []:
            mime.add_attachment(
                att["bytes"],
                maintype=att.get("maintype", "application"),
                subtype=att.get("subtype", "octet-stream"),
                filename=att["filename"],
            )

        raw_bytes = mime.as_bytes()
        raw_b64 = base64.urlsafe_b64encode(raw_bytes).decode("ascii").rstrip("=")

        client = self._client()
        try:
            r = client.post(
                f"{_GMAIL_API_BASE}/users/me/messages/send",
                json={"raw": raw_b64},
            )
            r.raise_for_status()
            payload = r.json()
        except Exception as exc:  # noqa: BLE001
            return ProviderSendResult(
                success=False,
                error_message=f"Gmail send failed: {exc}",
                error_retryable=_is_retryable_http(exc),
            )

        return ProviderSendResult(
            success=True,
            provider_message_id=payload.get("id"),
            provider_thread_id=payload.get("threadId"),
        )

    @staticmethod
    def oauth_authorize_url(state: str, redirect_uri: str) -> str:
        # Delegated to app.services.email.oauth_service.build_authorize_url
        # which reads real client_id from env. Kept here for backward
        # compat with Step 1 callers.
        from app.services.email.oauth_service import build_authorize_url

        return build_authorize_url(
            provider_type="gmail",
            state=state,
            redirect_uri=redirect_uri,
        )


# ─────────────────────────────────────────────────────────────────────
# Gmail message → ProviderFetchedMessage normalization
# ─────────────────────────────────────────────────────────────────────


def _parse_gmail_message(payload: dict[str, Any]) -> ProviderFetchedMessage:
    """Convert a Gmail messages.get response into the canonical shape.

    Walks the MIME tree to extract body parts + attachment metadata.
    Header parsing is RFC 5322 compliant via stdlib email.utils.
    """
    headers = {
        h["name"].lower(): h["value"]
        for h in payload.get("payload", {}).get("headers", [])
    }

    sender_email, sender_name = _split_address(headers.get("from", ""))
    to = _parse_address_list(headers.get("to", ""))
    cc = _parse_address_list(headers.get("cc", ""))
    bcc = _parse_address_list(headers.get("bcc", ""))
    reply_to = _parse_address_list(headers.get("reply-to", ""))

    # In-Reply-To header (RFC 5322): a single message-id
    in_reply_to = headers.get("in-reply-to", "").strip().strip("<>") or None

    body_html, body_text, attachments = _walk_gmail_payload(
        payload.get("payload", {})
    )

    sent_at = _parse_date_header(headers.get("date"))
    received_at = _parse_internal_date(payload.get("internalDate"))

    return ProviderFetchedMessage(
        provider_message_id=payload.get("id", ""),
        provider_thread_id=payload.get("threadId"),
        sender_email=sender_email,
        sender_name=sender_name,
        to=to,
        cc=cc,
        bcc=bcc,
        reply_to=reply_to,
        subject=headers.get("subject"),
        body_html=body_html,
        body_text=body_text,
        sent_at=sent_at,
        received_at=received_at,
        in_reply_to_provider_id=in_reply_to,
        raw_payload=payload,
        attachments=attachments,
    )


def _walk_gmail_payload(
    part: dict[str, Any],
) -> tuple[str | None, str | None, list[ProviderAttachment]]:
    """Recursively walk Gmail MIME parts for body + attachments."""
    body_html: str | None = None
    body_text: str | None = None
    attachments: list[ProviderAttachment] = []

    def _decode(data: str | None) -> str | None:
        if not data:
            return None
        try:
            return base64.urlsafe_b64decode(
                data + "=" * (-len(data) % 4)
            ).decode("utf-8", errors="replace")
        except Exception:
            return None

    def _walk(p: dict[str, Any]) -> None:
        nonlocal body_html, body_text
        mime = p.get("mimeType", "")
        body = p.get("body", {})
        filename = p.get("filename", "")

        if filename and body.get("attachmentId"):
            attachments.append(
                ProviderAttachment(
                    provider_attachment_id=body["attachmentId"],
                    filename=filename,
                    content_type=mime or None,
                    size_bytes=body.get("size"),
                    content_id=_extract_content_id(p),
                    is_inline=_is_inline(p),
                )
            )
            return

        if mime == "text/html" and body_html is None:
            body_html = _decode(body.get("data"))
        elif mime == "text/plain" and body_text is None:
            body_text = _decode(body.get("data"))

        for sub in p.get("parts", []) or []:
            _walk(sub)

    _walk(part)
    return body_html, body_text, attachments


def _extract_content_id(part: dict[str, Any]) -> str | None:
    for h in part.get("headers", []):
        if h.get("name", "").lower() == "content-id":
            return h.get("value", "").strip("<>")
    return None


def _is_inline(part: dict[str, Any]) -> bool:
    for h in part.get("headers", []):
        if (
            h.get("name", "").lower() == "content-disposition"
            and "inline" in h.get("value", "").lower()
        ):
            return True
    return False


def _split_address(value: str) -> tuple[str, str | None]:
    name, addr = parseaddr(value or "")
    return addr.lower().strip(), (name.strip() or None)


def _parse_address_list(value: str) -> list[tuple[str, str | None]]:
    if not value:
        return []
    # Gmail stores comma-separated addresses; parseaddr handles one
    # at a time. Use email.utils.getaddresses for the list version.
    from email.utils import getaddresses

    return [
        (addr.lower().strip(), (name.strip() or None))
        for name, addr in getaddresses([value])
        if addr
    ]


def _parse_date_header(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None


def _parse_internal_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        # Gmail internalDate is ms since epoch UTC
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
    except (ValueError, OSError):
        return None


def _format_address(email: str, display_name: str | None) -> str:
    """Format an address for an RFC 5322 header.

    Returns ``"Display Name" <email@host>`` when a name is supplied,
    or the bare email otherwise. Quoted-printable encoding for non-
    ASCII names handled by stdlib email.headerregistry on header set.
    """
    if display_name:
        # Escape inner quotes per RFC 5322 atext rules.
        safe_name = display_name.replace('"', '\\"')
        return f'"{safe_name}" <{email}>'
    return email


def _is_retryable_http(exc: Exception) -> bool:
    """Classify an httpx exception as retryable vs non-retryable.

    Connection errors + 5xx + 429 → retryable (caller may back off
    and retry). Auth errors (401 / 403) + 4xx other than 429 →
    non-retryable (fail-loud; user must reconnect or fix request).
    """
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status >= 500 or status == 429
    if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException)):
        return True
    return False
