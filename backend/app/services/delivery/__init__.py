"""Bridgeable delivery abstraction — Phase D-7.

Single entry point for every channel-send in the platform. Callers
invoke `delivery_service.send(...)`; the service:

1. Resolves content (templates render via DocumentRenderer when
   `template_key` supplied, else uses `body` / `body_html` directly).
2. Creates a `DocumentDelivery` row with status=pending.
3. Dispatches to the channel implementation via `get_channel()`.
4. Stores the provider's response + message id + status back on the row.
5. Retries inline for retryable errors (bounded by max_retries).

Channel implementations live under `channels/`. Adding a new channel:
1. Write a class with `channel_type` + `provider` class attrs and a
   `send(ChannelSendRequest) -> ChannelSendResult` method.
2. Register it in `_CHANNELS` below.

No caller upstream needs to change when a channel implementation
swaps (e.g. native email replacing Resend).
"""

from __future__ import annotations

from app.services.delivery.channels import (
    Attachment,
    ChannelSendRequest,
    ChannelSendResult,
    DeliveryChannel,
    EmailChannel,
    Recipient,
    SMSChannel,
)

# Singleton channel registry — one instance per type.
_CHANNELS: dict[str, DeliveryChannel] = {
    "email": EmailChannel(),
    "sms": SMSChannel(),
}


class UnknownChannelError(ValueError):
    """Raised when a caller asks for a channel that isn't registered."""


def get_channel(channel_type: str) -> DeliveryChannel:
    """Return the registered channel for `channel_type` or raise."""
    if channel_type not in _CHANNELS:
        raise UnknownChannelError(
            f"Unknown delivery channel: {channel_type!r}. "
            f"Registered: {sorted(_CHANNELS)}"
        )
    return _CHANNELS[channel_type]


def register_channel(
    channel_type: str, implementation: DeliveryChannel
) -> None:
    """Register or replace a channel implementation. Used by future
    native-email/native-SMS work to swap in a new provider without
    touching callers."""
    _CHANNELS[channel_type] = implementation


from app.services.delivery import delivery_service  # noqa: E402

__all__ = [
    "Attachment",
    "ChannelSendRequest",
    "ChannelSendResult",
    "DeliveryChannel",
    "EmailChannel",
    "Recipient",
    "SMSChannel",
    "UnknownChannelError",
    "delivery_service",
    "get_channel",
    "register_channel",
]
