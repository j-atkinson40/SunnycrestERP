"""EmailChannel — Resend implementation of the DeliveryChannel protocol.

**This is the ONLY module in the codebase allowed to import `resend`.**
A ruff-style test (`tests/test_delivery_d7_lint.py`) enforces that rule;
any other module reaching for the Resend SDK is a regression.

Native email will ship as a separate channel (e.g. `NativeEmailChannel`);
at switchover, `delivery.__init__._CHANNELS["email"]` updates to the new
implementation and no caller changes.
"""

from __future__ import annotations

import base64
import logging
from typing import Any

from app.config import settings
from app.services.delivery.channels.base import (
    ChannelSendRequest,
    ChannelSendResult,
)

logger = logging.getLogger(__name__)


class EmailChannel:
    channel_type = "email"
    provider = "resend"

    def supports_attachments(self) -> bool:
        return True

    def supports_html_body(self) -> bool:
        return True

    def _is_test_mode(self) -> bool:
        key = getattr(settings, "RESEND_API_KEY", "")
        return not key or key == "test"

    def _from_address(self, from_name: str | None = None) -> str:
        name = from_name or getattr(settings, "FROM_NAME", "Bridgeable")
        addr = getattr(settings, "FROM_EMAIL", "noreply@getbridgeable.com")
        return f"{name} <{addr}>"

    def send(self, request: ChannelSendRequest) -> ChannelSendResult:
        if self._is_test_mode():
            logger.info(
                "[EMAIL test-mode] To: %s | Subject: %s",
                request.recipient.value,
                request.subject,
            )
            return ChannelSendResult(
                success=True,
                provider=self.provider,
                provider_message_id="test-mode",
                provider_response={"mode": "test"},
            )

        try:
            import resend  # type: ignore
        except ImportError as exc:
            return ChannelSendResult(
                success=False,
                provider=self.provider,
                error_message=f"resend SDK not installed: {exc}",
                error_code="SDK_NOT_INSTALLED",
                retryable=False,
            )

        try:
            resend.api_key = settings.RESEND_API_KEY

            params: dict[str, Any] = {
                "from": self._from_address(request.from_name),
                "to": [request.recipient.value],
                "subject": request.subject or "(no subject)",
                # Prefer HTML; plaintext body in `text` for multipart
                "html": request.body_html or request.body,
            }
            if request.body_html and request.body != request.body_html:
                params["text"] = request.body
            if request.reply_to:
                params["reply_to"] = request.reply_to
            if request.attachments:
                params["attachments"] = [
                    {
                        "filename": a.filename,
                        "content": base64.b64encode(a.content).decode(),
                        "content_type": a.content_type,
                    }
                    for a in request.attachments
                ]

            response = resend.Emails.send(params)
            message_id = (
                response.get("id", "")
                if isinstance(response, dict)
                else ""
            )
            return ChannelSendResult(
                success=True,
                provider=self.provider,
                provider_message_id=message_id or None,
                provider_response=(
                    response if isinstance(response, dict) else {"raw": str(response)}
                ),
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Resend send failed for %s: %s",
                request.recipient.value,
                exc,
            )
            # Classify the error — Resend's API raises for various
            # conditions. A conservative default: treat network errors
            # as retryable, auth/validation as not-retryable. Since
            # resend's exception taxonomy isn't highly structured, we
            # use message substrings.
            msg = str(exc)
            retryable = any(
                kw in msg.lower()
                for kw in ("timeout", "connection", "temporarily", "503", "502")
            )
            return ChannelSendResult(
                success=False,
                provider=self.provider,
                error_message=msg[:2000],
                error_code=type(exc).__name__,
                retryable=retryable,
            )
