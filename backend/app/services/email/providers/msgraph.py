"""MicrosoftGraphProvider stub — Phase W-4b Layer 1 Step 1.

Step 1 ships the stub conforming to ``EmailProvider`` ABC. Real OAuth
+ MSGraph subscription + send infrastructure lands in Step 2-3. UI
flow scaffolding ships now so EmailAccount records pointing at the
``msgraph`` provider can be created and visually verified.
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


class MicrosoftGraphProvider(EmailProvider):
    provider_type = "msgraph"
    display_label = "Microsoft 365 / Outlook"
    supports_inbound = True
    supports_realtime = True

    def connect(
        self, oauth_redirect_payload: dict[str, Any] | None = None
    ) -> ProviderConnectResult:
        if oauth_redirect_payload is None:
            return ProviderConnectResult(
                success=False,
                error_message=(
                    "Microsoft Graph OAuth not yet implemented (Step 2). "
                    "EmailAccount can be created with a placeholder; "
                    "real OAuth exchange lands in Step 2."
                ),
            )
        raise NotImplementedError(
            "Microsoft Graph OAuth exchange ships in Phase W-4b Layer 1 Step 2."
        )

    def disconnect(self) -> None:
        return None

    def sync_initial(self, *, max_messages: int = 1000) -> ProviderSyncResult:
        raise NotImplementedError(
            "MSGraph initial sync ships in Phase W-4b Layer 1 Step 2."
        )

    def subscribe_realtime(self) -> bool:
        raise NotImplementedError(
            "MSGraph subscription ships in Phase W-4b Layer 1 Step 2."
        )

    def fetch_message(self, provider_message_id: str) -> ProviderFetchedMessage:
        raise NotImplementedError(
            "MSGraph message fetch ships in Phase W-4b Layer 1 Step 2."
        )

    def fetch_attachment(
        self, provider_message_id: str, provider_attachment_id: str
    ) -> bytes:
        raise NotImplementedError(
            "MSGraph attachment fetch ships in Phase W-4b Layer 1 Step 2."
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
            "MSGraph send ships in Phase W-4b Layer 1 Step 3."
        )

    @staticmethod
    def oauth_authorize_url(state: str, redirect_uri: str) -> str:
        """Build the Microsoft Identity Platform authorization URL.

        Step 1 returns a placeholder URL shape; Step 2 wires real
        tenant_id / client_id from settings + correct Graph scopes
        (Mail.ReadWrite + Mail.Send + offline_access).
        """
        client_id_placeholder = "REPLACE_IN_STEP_2"
        tenant = "common"
        scopes = "Mail.ReadWrite Mail.Send offline_access"
        return (
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
            f"?client_id={client_id_placeholder}"
            f"&response_type=code&redirect_uri={redirect_uri}"
            f"&response_mode=query&scope={scopes}&state={state}"
        )
