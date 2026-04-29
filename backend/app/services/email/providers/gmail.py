"""GmailAPIProvider stub — Phase W-4b Layer 1 Step 1.

Step 1 ships the stub conforming to ``EmailProvider`` ABC. The OAuth
exchange + initial sync + realtime watch + send all raise
``NotImplementedError`` pointing at the Step where the real implementation
lands. The UI in Settings → Email Accounts can still create EmailAccount
records pointing at this provider; backend stubs handle the OAuth redirect
URL shape so the flow can be visually verified end-to-end without
real Google credentials.
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


class GmailAPIProvider(EmailProvider):
    provider_type = "gmail"
    display_label = "Gmail / Google Workspace"
    supports_inbound = True
    supports_realtime = True

    def connect(
        self, oauth_redirect_payload: dict[str, Any] | None = None
    ) -> ProviderConnectResult:
        # Step 1 stub: when the OAuth redirect lands in Step 2, this
        # method exchanges the authorization code for refresh + access
        # tokens, persists encrypted tokens to provider_config, and
        # registers the account's Gmail watch resource.
        if oauth_redirect_payload is None:
            return ProviderConnectResult(
                success=False,
                error_message=(
                    "Gmail OAuth not yet implemented (Step 2). "
                    "EmailAccount can be created with a placeholder; "
                    "real OAuth exchange lands in Step 2."
                ),
            )
        raise NotImplementedError(
            "Gmail OAuth exchange ships in Phase W-4b Layer 1 Step 2 "
            "(inbound sync infrastructure)."
        )

    def disconnect(self) -> None:
        # Idempotent: called when account is disabled. Step 2+ wires
        # gmail.users.stop() to retire the watch resource.
        return None

    def sync_initial(self, *, max_messages: int = 1000) -> ProviderSyncResult:
        raise NotImplementedError(
            "Gmail initial sync ships in Phase W-4b Layer 1 Step 2."
        )

    def subscribe_realtime(self) -> bool:
        raise NotImplementedError(
            "Gmail watch subscription ships in Phase W-4b Layer 1 Step 2."
        )

    def fetch_message(self, provider_message_id: str) -> ProviderFetchedMessage:
        raise NotImplementedError(
            "Gmail message fetch ships in Phase W-4b Layer 1 Step 2."
        )

    def fetch_attachment(
        self, provider_message_id: str, provider_attachment_id: str
    ) -> bytes:
        raise NotImplementedError(
            "Gmail attachment fetch ships in Phase W-4b Layer 1 Step 2."
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
            "Gmail send ships in Phase W-4b Layer 1 Step 3 "
            "(outbound infrastructure)."
        )

    @staticmethod
    def oauth_authorize_url(state: str, redirect_uri: str) -> str:
        """Build the Google OAuth authorization URL.

        Used by Settings → Email Accounts UI to redirect the user to
        Google's consent screen. Step 1 returns a placeholder URL
        shape; Step 2 wires real client_id + scopes from settings.
        """
        # Placeholder: real implementation reads GOOGLE_OAUTH_CLIENT_ID
        # from settings and includes the required Gmail scopes
        # (gmail.readonly + gmail.send + gmail.modify + gmail.labels).
        client_id_placeholder = "REPLACE_IN_STEP_2"
        scopes = "https://www.googleapis.com/auth/gmail.modify"
        return (
            "https://accounts.google.com/o/oauth2/v2/auth"
            f"?client_id={client_id_placeholder}"
            f"&redirect_uri={redirect_uri}"
            f"&response_type=code&scope={scopes}"
            f"&access_type=offline&prompt=consent&state={state}"
        )
