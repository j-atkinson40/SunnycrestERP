"""SMSChannel stub — Phase D-7.

Interface-ready but returns a clean `NOT_IMPLEMENTED` error on send.
Native SMS ships as a separate workstream; when it does, this class is
replaced in `delivery.__init__._CHANNELS["sms"]`.

Callers that attempt SMS get a well-structured failure (status=rejected,
error_code=NOT_IMPLEMENTED) rather than a crash, so workflow steps and
admin manual sends surface the limitation cleanly.
"""

from __future__ import annotations

from app.services.delivery.channels.base import (
    ChannelSendRequest,
    ChannelSendResult,
)


class SMSChannel:
    channel_type = "sms"
    provider = "stub_sms"

    def supports_attachments(self) -> bool:
        return False

    def supports_html_body(self) -> bool:
        return False

    def send(self, request: ChannelSendRequest) -> ChannelSendResult:
        return ChannelSendResult(
            success=False,
            provider=self.provider,
            provider_message_id=None,
            provider_response={
                "recipient": request.recipient.value,
                "body_length": len(request.body or ""),
            },
            error_message=(
                "SMS delivery not yet implemented. Channel interface "
                "is ready; awaiting native SMS work."
            ),
            error_code="NOT_IMPLEMENTED",
            retryable=False,
        )
