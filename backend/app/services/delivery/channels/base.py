"""DeliveryChannel protocol — Phase D-7.

Any new channel (native email, native SMS, webhook, push) implements
this interface. Swapping implementations is a single-line change in
`delivery.__init__._CHANNELS` — callers upstream never see the
difference.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class Recipient:
    """Who the send is going to. `type` controls how `value` is
    interpreted by the channel."""

    # email_address | phone_number | user_id | contact_id
    type: str
    value: str
    name: str | None = None


@dataclass
class Attachment:
    """One attachment to include with the send. Channels that don't
    support attachments (SMS, push) silently skip these."""

    filename: str
    content_type: str
    content: bytes


@dataclass
class ChannelSendRequest:
    """Input to `channel.send()`. Pre-resolved — no template rendering
    at this layer. Content is ready to ship."""

    recipient: Recipient
    subject: str | None
    body: str
    body_html: str | None = None
    attachments: list[Attachment] | None = None
    reply_to: str | None = None
    from_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChannelSendResult:
    """Output of `channel.send()`. The channel owns `provider` and
    `provider_message_id`; upstream DeliveryService stores them on the
    `document_deliveries` row."""

    success: bool
    provider: str
    provider_message_id: str | None = None
    provider_response: dict[str, Any] | None = None
    error_message: str | None = None
    error_code: str | None = None
    retryable: bool = False


@runtime_checkable
class DeliveryChannel(Protocol):
    """Protocol — duck-typed. Any class with these class attributes
    and `send()` method qualifies."""

    channel_type: str  # "email" | "sms" | ...
    provider: str  # "resend" | "stub_sms" | future values

    def send(self, request: ChannelSendRequest) -> ChannelSendResult: ...

    def supports_attachments(self) -> bool: ...

    def supports_html_body(self) -> bool: ...
