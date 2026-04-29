"""TransactionalSendOnlyProvider stub — Phase W-4b Layer 1 Step 1.

Per BRIDGEABLE_MASTER §3.26.15.6, the transactional provider is
**outbound-only**. It wraps the existing Phase D-7 ``DeliveryService``
+ ``EmailChannel`` (Resend) so that drafted emails from
``state-changes-generate-communications`` (§3.26.15.17) can flow through
the email primitive's send pipeline without requiring a connected
inbox account.

Use cases:
  - Tenant has no Gmail/Office 365 connected but still wants the
    platform to send order-confirmation / invoice / statement / case
    notification emails.
  - State-change-generated drafts (per §3.26.15.17) need a send path
    even when no human is in the inbox loop.

Inbound sync is not applicable — there is no provider-side inbox to
poll. ``supports_inbound = False``. ``sync_initial / subscribe_realtime
/ fetch_message / fetch_attachment`` all raise NotImplementedError
because they're conceptually meaningless for this provider.

Step 1 stub: ``send_message`` returns a placeholder ``ProviderSendResult``
indicating Step 3 wires the actual DeliveryService bridge. The
architectural commitment is documented; the implementation lands in
Step 3 (outbound infrastructure).
"""

from __future__ import annotations

from typing import Any

from app.services.email.providers.base import (
    EmailProvider,
    ProviderConnectResult,
    ProviderFetchedMessage,
    ProviderSendResult,
    ProviderSyncResult,
)


class TransactionalSendOnlyProvider(EmailProvider):
    provider_type = "transactional"
    display_label = "Transactional (platform-routed, outbound only)"
    supports_inbound = False
    supports_realtime = False

    def connect(
        self, oauth_redirect_payload: dict[str, Any] | None = None
    ) -> ProviderConnectResult:
        # Transactional provider has no external connection to establish.
        # The "connection" is just the EmailAccount row pointing at the
        # platform's Resend infrastructure (Phase D-7). Returning success
        # immediately is correct.
        return ProviderConnectResult(
            success=True,
            provider_account_id=self.account_config.get("email_address"),
            config_to_persist={
                "routes_through": "delivery_service",
                "underlying_channel": "email",
            },
        )

    def disconnect(self) -> None:
        # No external resources to tear down.
        return None

    def sync_initial(self, *, max_messages: int = 1000) -> ProviderSyncResult:
        # Transactional is outbound-only — no inbox to sync.
        raise NotImplementedError(
            "TransactionalSendOnlyProvider is outbound-only — sync is not "
            "applicable. Use Gmail/MSGraph/IMAP for inbound."
        )

    def subscribe_realtime(self) -> bool:
        # No inbound side, no realtime subscription possible.
        return False

    def fetch_message(self, provider_message_id: str) -> ProviderFetchedMessage:
        raise NotImplementedError(
            "TransactionalSendOnlyProvider is outbound-only — fetch_message "
            "is not applicable."
        )

    def fetch_attachment(
        self, provider_message_id: str, provider_attachment_id: str
    ) -> bytes:
        raise NotImplementedError(
            "TransactionalSendOnlyProvider is outbound-only — fetch_attachment "
            "is not applicable."
        )

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
        # Step 3 wires this through to ``delivery_service.send_email_raw``
        # / ``delivery_service.send_email_with_template``. The bridge
        # captures the EmailMessage row + creates the corresponding
        # DocumentDelivery record so both audit trails stay coherent.
        raise NotImplementedError(
            "TransactionalSendOnlyProvider.send_message ships in Phase W-4b "
            "Layer 1 Step 3 (outbound infrastructure). Step 3 wires this "
            "method through to delivery_service.send_email_raw."
        )
