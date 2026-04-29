"""IMAPProvider stub — Phase W-4b Layer 1 Step 1.

IMAP is the universal fallback when neither Gmail API nor MSGraph fit
(self-hosted mail, custom domains without modern API). Step 1 ships
the stub + IMAP credential entry form scaffolding (UI captures
server / port / username / password to ``provider_config``). Step 2
wires real IMAP IDLE polling + SMTP send.
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


class IMAPProvider(EmailProvider):
    provider_type = "imap"
    display_label = "IMAP / SMTP (custom)"
    supports_inbound = True
    supports_realtime = False  # IMAP polls; no realtime subscription

    def connect(
        self, oauth_redirect_payload: dict[str, Any] | None = None
    ) -> ProviderConnectResult:
        # Step 1: validate that minimum config fields are present;
        # don't actually open a socket. Step 2 opens a test connection
        # and verifies credentials before returning success.
        required_fields = {
            "imap_server",
            "imap_port",
            "smtp_server",
            "smtp_port",
            "username",
        }
        # Note: password is captured separately via encrypted_credentials
        # in Step 2; Step 1 just sanity-checks the config shape.
        missing = required_fields - set(self.account_config.keys())
        if missing:
            return ProviderConnectResult(
                success=False,
                error_message=(
                    f"IMAP config missing required fields: {sorted(missing)}. "
                    "Real connection test lands in Step 2."
                ),
            )
        return ProviderConnectResult(
            success=True,
            provider_account_id=self.account_config.get("username"),
            error_message=(
                "IMAP config accepted (Step 1 stub). Real socket "
                "connection + credential validation lands in Step 2."
            ),
            config_to_persist={
                "stub_connect_at": "step_1_placeholder",
            },
        )

    def disconnect(self) -> None:
        return None

    def sync_initial(self, *, max_messages: int = 1000) -> ProviderSyncResult:
        raise NotImplementedError(
            "IMAP initial sync ships in Phase W-4b Layer 1 Step 2."
        )

    def subscribe_realtime(self) -> bool:
        # IMAP doesn't support webhook-style realtime; Step 2 wires
        # IMAP IDLE polling (long-poll) as a near-realtime substitute.
        return False

    def fetch_message(self, provider_message_id: str) -> ProviderFetchedMessage:
        raise NotImplementedError(
            "IMAP message fetch ships in Phase W-4b Layer 1 Step 2."
        )

    def fetch_attachment(
        self, provider_message_id: str, provider_attachment_id: str
    ) -> bytes:
        raise NotImplementedError(
            "IMAP attachment fetch ships in Phase W-4b Layer 1 Step 2."
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
        raise NotImplementedError(
            "IMAP/SMTP send ships in Phase W-4b Layer 1 Step 3."
        )
