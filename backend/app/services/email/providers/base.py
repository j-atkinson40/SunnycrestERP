"""Email provider abstract base class + registry — §3.26.15.6.

The ``EmailProvider`` ABC defines the contract every provider
implementation conforms to. Step 1 ships the ABC + 4 stub
subclasses. Step 2 implements real OAuth + sync atop these stubs.
Step N+ adds a native-transport provider behind the same contract
per the integrate-now-make-native-later framework (§3.26.15.1).

Pattern parallels the existing Phase D-7 ``DeliveryChannel`` Protocol
in ``app.services.delivery.channels.base`` — both abstract over
"transport implementation" so callers stay clean.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# ─────────────────────────────────────────────────────────────────────
# Result dataclasses — provider operations return these typed shapes
# ─────────────────────────────────────────────────────────────────────


@dataclass
class ProviderConnectResult:
    """Returned from ``EmailProvider.connect()``."""

    success: bool
    provider_account_id: str | None = None
    error_message: str | None = None
    # Provider-specific config to persist on EmailAccount.provider_config.
    # E.g. Gmail watch resource_id; MSGraph subscription_id; IMAP server config.
    config_to_persist: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderSyncResult:
    """Returned from ``EmailProvider.sync_initial()`` and incremental sync."""

    success: bool
    messages_synced: int = 0
    threads_synced: int = 0
    last_sync_at: datetime | None = None
    last_history_id: str | None = None
    last_delta_token: str | None = None
    last_uid: int | None = None
    error_message: str | None = None


@dataclass
class ProviderMessageRef:
    """Lightweight reference returned by realtime subscription callbacks."""

    provider_message_id: str
    provider_thread_id: str | None = None
    received_at: datetime | None = None


@dataclass
class ProviderFetchedMessage:
    """Full-fidelity message payload returned by ``fetch_message()``."""

    provider_message_id: str
    provider_thread_id: str | None
    sender_email: str
    sender_name: str | None
    to: list[tuple[str, str | None]]  # [(email, display_name), ...]
    cc: list[tuple[str, str | None]] = field(default_factory=list)
    bcc: list[tuple[str, str | None]] = field(default_factory=list)
    reply_to: list[tuple[str, str | None]] = field(default_factory=list)
    subject: str | None = None
    body_html: str | None = None
    body_text: str | None = None
    sent_at: datetime | None = None
    received_at: datetime | None = None
    in_reply_to_provider_id: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    attachments: list[ProviderAttachment] = field(default_factory=list)


@dataclass
class ProviderAttachment:
    """Attachment metadata returned by message fetch."""

    provider_attachment_id: str
    filename: str
    content_type: str | None = None
    size_bytes: int | None = None
    content_id: str | None = None  # for inline images
    is_inline: bool = False


@dataclass
class ProviderSendResult:
    """Returned from ``EmailProvider.send_message()``."""

    success: bool
    provider_message_id: str | None = None
    provider_thread_id: str | None = None
    error_message: str | None = None
    error_retryable: bool = False


# ─────────────────────────────────────────────────────────────────────
# Abstract base class
# ─────────────────────────────────────────────────────────────────────


class EmailProvider(ABC):
    """Contract every email provider implementation must satisfy.

    Each provider gets instantiated per-account when needed. The
    ``account_config`` dict is the persisted ``EmailAccount.provider_config``;
    each provider interprets its slice of that config differently (Gmail
    expects ``credentials_json``, MSGraph expects ``tenant_id`` +
    ``client_id``, IMAP expects ``server`` + ``port`` + ``username``,
    transactional expects nothing — it routes through DeliveryService).

    Step 1 stubs implement ``provider_type`` + ``__init__`` cleanly;
    other methods raise ``NotImplementedError`` with a Step-2-pointer
    message so missed calls fail loud rather than silently.
    """

    #: Identifier matching ``EmailAccount.provider_type`` and the
    #: PROVIDER_REGISTRY key.
    provider_type: str = ""

    #: Human-readable label shown in the UI provider picker.
    display_label: str = ""

    #: Whether this provider supports inbound sync. ``transactional`` is
    #: outbound-only.
    supports_inbound: bool = True

    #: Whether this provider supports realtime subscription callbacks
    #: (Gmail watch, MSGraph subscriptions). IMAP polls; transactional
    #: doesn't sync at all.
    supports_realtime: bool = False

    def __init__(self, account_config: dict[str, Any]) -> None:
        self.account_config = account_config

    # ── Connect / disconnect lifecycle ────────────────────────────────

    @abstractmethod
    def connect(self, oauth_redirect_payload: dict[str, Any] | None = None) -> ProviderConnectResult:
        """Establish a connection to the provider.

        For OAuth providers, ``oauth_redirect_payload`` carries the
        post-redirect tokens that need exchange. For IMAP, the
        ``account_config`` already carries credentials. For transactional,
        connection is a no-op (returns success immediately).

        Step 1 stubs: gmail/msgraph raise NotImplementedError(step_2_oauth);
        imap stub returns success with a placeholder; transactional
        stub returns success with no config to persist.
        """

    @abstractmethod
    def disconnect(self) -> None:
        """Tear down provider-side subscriptions / watches.

        Idempotent. Called when an EmailAccount is disabled or deleted.
        """

    # ── Sync operations ───────────────────────────────────────────────

    @abstractmethod
    def sync_initial(self, *, max_messages: int = 1000) -> ProviderSyncResult:
        """Initial backfill of recent messages on first connect.

        Step 1 stubs: all raise NotImplementedError(step_2_sync).
        """

    @abstractmethod
    def subscribe_realtime(self) -> bool:
        """Establish a realtime subscription if the provider supports it.

        Returns True if subscribed, False if the provider doesn't support
        realtime (e.g. IMAP). Stubs raise NotImplementedError(step_2_sync).
        """

    @abstractmethod
    def fetch_message(self, provider_message_id: str) -> ProviderFetchedMessage:
        """Fetch the full payload of a single message by provider id.

        Used by inbound webhook handlers when a realtime callback brings
        a ``ProviderMessageRef`` and the system needs full content.
        Stubs raise NotImplementedError(step_2_sync).
        """

    @abstractmethod
    def fetch_attachment(
        self, provider_message_id: str, provider_attachment_id: str
    ) -> bytes:
        """Fetch attachment bytes for a single attachment.

        Used by attachment-promote-to-Vault flow. Stubs raise
        NotImplementedError(step_2_sync).
        """

    # ── Outbound ──────────────────────────────────────────────────────

    @abstractmethod
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
        """Send a message through this provider.

        For provider types that support inbound (gmail/msgraph/imap), the
        sent message ends up in the connected account's Sent folder and
        gets re-synced on next inbound poll. For ``transactional``, the
        send is fire-and-forget (no return-trip; the message never lands
        in any inbox the provider can see).

        Stubs raise NotImplementedError(step_3_outbound).
        """


# ─────────────────────────────────────────────────────────────────────
# Provider registry — provider_type string → provider class
# ─────────────────────────────────────────────────────────────────────


PROVIDER_REGISTRY: dict[str, type[EmailProvider]] = {}


def register_provider(provider_type: str, provider_class: type[EmailProvider]) -> None:
    """Register a provider implementation in the global registry.

    Called from ``app.services.email.providers.__init__`` at import time
    for the 4 Step-1 stubs. Future native provider gets registered the
    same way. Re-registering an existing key replaces the previous
    implementation.
    """
    PROVIDER_REGISTRY[provider_type] = provider_class


def get_provider_class(provider_type: str) -> type[EmailProvider]:
    """Resolve a registered provider class by ``provider_type``.

    Raises ``KeyError`` if the provider is not registered. Callers
    should validate ``provider_type`` against
    ``app.models.email_primitive.PROVIDER_TYPES`` before calling.
    """
    return PROVIDER_REGISTRY[provider_type]
