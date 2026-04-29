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
        """Bridge to Phase D-7 ``delivery_service.send_email_raw``.

        Per canon §3.26.15.5 Path 2: system-generated mail (briefings,
        document deliveries, signature requests, future state-change-
        generated drafts) routes through the existing transactional
        infrastructure. This bridge preserves D-7 patterns verbatim
        while letting the email primitive's outbound API surface
        return a coherent ProviderSendResult.

        The caller (``outbound_service``) injects the SQLAlchemy db
        session + tenant_id via ``account_config`` keys ``__db__`` and
        ``__company_id__`` because the EmailProvider ABC interface is
        stateless. This is a deliberate, documented hack confined to
        this provider — Gmail/MSGraph/IMAP don't need the db handle
        because they call out to external HTTP/SMTP. Future refactor
        could promote (db, company_id) to first-class ABC params if
        the pattern recurs.
        """
        from app.services.delivery import delivery_service

        db = self.account_config.get("__db__")
        company_id = self.account_config.get("__company_id__")
        if db is None or company_id is None:
            return ProviderSendResult(
                success=False,
                error_message=(
                    "TransactionalSendOnlyProvider requires __db__ + "
                    "__company_id__ in account_config — outbound_service "
                    "injects these. Direct provider invocation outside "
                    "outbound_service not supported."
                ),
                error_retryable=False,
            )

        # D-7 send_email_raw accepts a single recipient. For multi-
        # recipient transactional sends, the caller iterates. Step 3
        # ships single-recipient pass-through; multi-recipient is a
        # next-step refinement.
        if len(to) != 1:
            return ProviderSendResult(
                success=False,
                error_message=(
                    "TransactionalSendOnlyProvider currently supports "
                    "single-recipient sends (D-7 send_email_raw shape). "
                    "Multi-recipient transactional sends ship in Step 3.1."
                ),
                error_retryable=False,
            )
        primary_addr, primary_name = to[0]

        try:
            delivery = delivery_service.send_email_raw(
                db,
                company_id=company_id,
                to_email=primary_addr,
                to_name=primary_name,
                subject=subject,
                body_html=body_html or (body_text or ""),
                from_name=from_address,
                caller_module="email_primitive.transactional",
            )
        except Exception as exc:  # noqa: BLE001 — surface root cause
            return ProviderSendResult(
                success=False,
                error_message=f"Transactional send via DeliveryService failed: {exc}",
                error_retryable=False,
            )

        return ProviderSendResult(
            success=delivery.status in ("sent", "delivered"),
            provider_message_id=delivery.id,  # DocumentDelivery.id as stable handle
            error_message=delivery.error_message,
            error_retryable=False,
        )
