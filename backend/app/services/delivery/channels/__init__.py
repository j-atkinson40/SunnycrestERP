"""Delivery channel implementations — Phase D-7."""

from app.services.delivery.channels.base import (
    Attachment,
    ChannelSendRequest,
    ChannelSendResult,
    DeliveryChannel,
    Recipient,
)
from app.services.delivery.channels.email_channel import EmailChannel
from app.services.delivery.channels.sms_channel import SMSChannel

__all__ = [
    "Attachment",
    "ChannelSendRequest",
    "ChannelSendResult",
    "DeliveryChannel",
    "EmailChannel",
    "Recipient",
    "SMSChannel",
]
