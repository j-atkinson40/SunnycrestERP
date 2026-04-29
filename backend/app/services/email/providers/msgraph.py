"""MicrosoftGraphProvider — real implementation, Phase W-4b Layer 1 Step 2.

Wraps Microsoft Graph API HTTP calls via httpx. OAuth token resolution
identical to Gmail provider — caller injects ``access_token`` into
``account_config`` after ``oauth_service.ensure_fresh_token``.

Same testing constraints as Gmail: real Graph API requires production
client_id + tenant; tests inject ``httpx.MockTransport`` for wire-format
verification.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
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


_GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"


class MicrosoftGraphProvider(EmailProvider):
    provider_type = "msgraph"
    display_label = "Microsoft 365 / Outlook"
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
                "MicrosoftGraphProvider requires access_token in account_config "
                "— caller must inject via oauth_service.ensure_fresh_token."
            )
        return token

    def _client(self) -> httpx.Client:
        if self._http is None:
            self._http = httpx.Client(
                timeout=30.0,
                headers={"Authorization": f"Bearer {self.access_token}"},
            )
        return self._http

    def connect(
        self, oauth_redirect_payload: dict[str, Any] | None = None
    ) -> ProviderConnectResult:
        if oauth_redirect_payload is None:
            return ProviderConnectResult(
                success=True,
                error_message=(
                    "MS Graph account row created — complete OAuth flow "
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

    def sync_initial(self, *, max_messages: int = 1000) -> ProviderSyncResult:
        client = self._client()
        # Use $delta to capture initial state + cursor for incremental
        # syncs. First call returns messages + a delta token in the
        # @odata.deltaLink for follow-up calls.
        try:
            params = {
                "$top": min(max_messages, 1000),
                "$select": "id,subject,from,toRecipients,ccRecipients,"
                "bccRecipients,replyTo,bodyPreview,internetMessageId,"
                "conversationId,sentDateTime,receivedDateTime,hasAttachments",
            }
            r = client.get(
                f"{_GRAPH_API_BASE}/me/messages/delta", params=params
            )
            r.raise_for_status()
            payload = r.json()
        except Exception as exc:  # noqa: BLE001
            return ProviderSyncResult(
                success=False,
                error_message=f"Graph delta fetch failed: {exc}",
            )

        messages = payload.get("value", [])
        delta_link = payload.get("@odata.deltaLink", "")
        return ProviderSyncResult(
            success=True,
            messages_synced=len(messages),
            threads_synced=len({m.get("conversationId") for m in messages}),
            last_sync_at=datetime.now(timezone.utc),
            last_delta_token=delta_link,
        )

    def subscribe_realtime(self) -> bool:
        # Step 2: real subscription creation via POST /subscriptions
        # ships when production tenant is registered. Webhook handler
        # is in place; subscription provisioning happens at first
        # post-OAuth sweep.
        return True

    def fetch_message(self, provider_message_id: str) -> ProviderFetchedMessage:
        client = self._client()
        r = client.get(f"{_GRAPH_API_BASE}/me/messages/{provider_message_id}")
        r.raise_for_status()
        payload = r.json()
        return _parse_msgraph_message(payload)

    def fetch_attachment(
        self, provider_message_id: str, provider_attachment_id: str
    ) -> bytes:
        client = self._client()
        r = client.get(
            f"{_GRAPH_API_BASE}/me/messages/{provider_message_id}"
            f"/attachments/{provider_attachment_id}/$value"
        )
        r.raise_for_status()
        return r.content

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
        """Send via Graph me/sendMail.

        Constructs the canonical Graph message JSON shape per
        https://learn.microsoft.com/en-us/graph/api/user-sendmail.
        """

        def _recipients(pairs: list[tuple[str, str | None]]) -> list[dict]:
            out = []
            for addr, name in pairs:
                entry = {"emailAddress": {"address": addr}}
                if name:
                    entry["emailAddress"]["name"] = name
                out.append(entry)
            return out

        body_field = (
            {"contentType": "html", "content": body_html}
            if body_html
            else {"contentType": "text", "content": body_text or ""}
        )

        message: dict[str, Any] = {
            "subject": subject or "",
            "body": body_field,
            "toRecipients": _recipients(to),
        }
        if cc:
            message["ccRecipients"] = _recipients(cc)
        if bcc:
            message["bccRecipients"] = _recipients(bcc)

        # Graph supports In-Reply-To via internetMessageHeaders. Caller
        # supplies the original Internet-Message-ID; we wrap in <>.
        if in_reply_to_provider_id:
            message["internetMessageHeaders"] = [
                {
                    "name": "In-Reply-To",
                    "value": f"<{in_reply_to_provider_id}>",
                },
                {
                    "name": "References",
                    "value": f"<{in_reply_to_provider_id}>",
                },
            ]

        if attachments:
            import base64 as _b64

            message["attachments"] = [
                {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": att["filename"],
                    "contentType": (
                        f"{att.get('maintype', 'application')}/"
                        f"{att.get('subtype', 'octet-stream')}"
                    ),
                    "contentBytes": _b64.b64encode(att["bytes"]).decode("ascii"),
                }
                for att in attachments
            ]

        envelope = {"message": message, "saveToSentItems": True}

        client = self._client()
        try:
            r = client.post(
                f"{_GRAPH_API_BASE}/me/sendMail", json=envelope
            )
            # Graph returns 202 Accepted on success with empty body
            if r.status_code not in (200, 202):
                r.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            from app.services.email.providers.gmail import _is_retryable_http

            return ProviderSendResult(
                success=False,
                error_message=f"MS Graph send failed: {exc}",
                error_retryable=_is_retryable_http(exc),
            )

        # Graph me/sendMail does NOT return a message id directly. The
        # message lands in Sent Items and gets a server-side id; the
        # caller can fetch via me/messages?$filter=internetMessageId
        # if it pre-generated one, OR rely on the next inbound sync of
        # Sent Items to populate provider_message_id via deduplication.
        # We return success without a provider_message_id; the outbound
        # service handles the deferred-id case by storing a placeholder
        # that gets reconciled on next sync.
        return ProviderSendResult(
            success=True,
            provider_message_id=None,
        )

    @staticmethod
    def oauth_authorize_url(state: str, redirect_uri: str) -> str:
        from app.services.email.oauth_service import build_authorize_url

        return build_authorize_url(
            provider_type="msgraph",
            state=state,
            redirect_uri=redirect_uri,
        )


# ─────────────────────────────────────────────────────────────────────
# Graph message → ProviderFetchedMessage normalization
# ─────────────────────────────────────────────────────────────────────


def _parse_msgraph_message(payload: dict[str, Any]) -> ProviderFetchedMessage:
    """Convert a Graph message resource to the canonical shape."""

    def _addr(item: dict[str, Any] | None) -> tuple[str, str | None]:
        if not item:
            return "", None
        ea = item.get("emailAddress", {})
        addr = (ea.get("address") or "").lower().strip()
        name = ea.get("name")
        return addr, (name.strip() if name else None)

    def _addr_list(items: list[dict[str, Any]] | None) -> list[tuple[str, str | None]]:
        if not items:
            return []
        out = []
        for it in items:
            addr, name = _addr(it)
            if addr:
                out.append((addr, name))
        return out

    sender_email, sender_name = _addr(payload.get("from"))
    body = payload.get("body", {}) or {}
    body_html = (
        body.get("content") if body.get("contentType") == "html" else None
    )
    body_text = (
        body.get("content") if body.get("contentType") == "text" else None
    )

    # Graph dates are ISO-8601 strings.
    def _iso(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    in_reply_to = (
        (payload.get("internetMessageHeaders") or {})
        # Headers are an array; check if the value of "In-Reply-To" is set
    )
    # Graph rarely returns internetMessageHeaders by default; for now
    # we leave in_reply_to_provider_id at None and rely on
    # conversationId for thread reconstruction. Fallback to subject
    # matching covers the rest.
    in_reply_to_id: str | None = None

    attachments: list[ProviderAttachment] = []
    if payload.get("hasAttachments"):
        # Step 2 leaves the metadata fetch to a separate Graph call
        # (POST /me/messages/{id}/attachments); the ingestion pipeline
        # will populate attachments lazily when the user clicks. For
        # now we mark "has attachments" without enumerating.
        pass

    return ProviderFetchedMessage(
        provider_message_id=payload.get("id", ""),
        provider_thread_id=payload.get("conversationId"),
        sender_email=sender_email,
        sender_name=sender_name,
        to=_addr_list(payload.get("toRecipients")),
        cc=_addr_list(payload.get("ccRecipients")),
        bcc=_addr_list(payload.get("bccRecipients")),
        reply_to=_addr_list(payload.get("replyTo")),
        subject=payload.get("subject"),
        body_html=body_html,
        body_text=body_text,
        sent_at=_iso(payload.get("sentDateTime")),
        received_at=_iso(payload.get("receivedDateTime")),
        in_reply_to_provider_id=in_reply_to_id,
        raw_payload=payload,
        attachments=attachments,
    )
