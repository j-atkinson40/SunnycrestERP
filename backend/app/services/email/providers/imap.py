"""IMAPProvider — polling-only implementation, Phase W-4b Layer 1 Step 2.

Per Step 2 canon-clarification: IMAP IDLE long-lived connections are
deferred to Step 2.1 / Step 4 (when inbox UI surfaces real-time
freshness pressure). Step 2 ships **polling-only** matching canon
§3.26.15.4 "polling 5-min fallback" — APScheduler sweep over active
IMAP accounts, per-account UIDVALIDITY + UIDNEXT cursor.

Connection model:
  - Open imaplib connection per ``sync_initial`` / ``fetch_message``
    call; close at end. No long-lived connection state.
  - Step 2.1 (deferred): persistent IDLE worker thread per account.

Credential resolution:
  - imap_password decrypted at provider construction time from
    ``account_config["imap_password"]`` (caller injects via
    ``oauth_service``-equivalent IMAP credential decryption).
  - server / port / username live in plaintext provider_config.

Tests inject a mock ``imaplib.IMAP4_SSL``-shaped object via the
``imap_client_factory`` injection seam to verify the wire format
without a real IMAP server.
"""

from __future__ import annotations

import email
import imaplib
import logging
from datetime import datetime, timezone
from email.message import Message as EmailMimeMessage
from email.utils import getaddresses, parseaddr, parsedate_to_datetime
from typing import Any, Callable

from app.services.email.providers.base import (
    EmailProvider,
    ProviderAttachment,
    ProviderConnectResult,
    ProviderFetchedMessage,
    ProviderSendResult,
    ProviderSyncResult,
)


logger = logging.getLogger(__name__)


# Test seam: tests can monkey-patch this to inject a mock IMAP client.
def _default_imap_factory(server: str, port: int):
    return imaplib.IMAP4_SSL(server, port)


class IMAPProvider(EmailProvider):
    provider_type = "imap"
    display_label = "IMAP / SMTP (custom)"
    supports_inbound = True
    supports_realtime = False  # Step 2 is polling-only

    # Class-level test seam (monkey-patchable in tests)
    imap_client_factory: Callable[[str, int], Any] = staticmethod(
        _default_imap_factory
    )

    def __init__(self, account_config: dict[str, Any]) -> None:
        super().__init__(account_config)
        self._connection = None

    def _connect(self):
        if self._connection is not None:
            return self._connection
        server = self.account_config.get("imap_server")
        port = int(self.account_config.get("imap_port", 993))
        username = self.account_config.get("username")
        password = self.account_config.get("imap_password")
        if not all([server, port, username, password]):
            raise RuntimeError(
                "IMAPProvider requires imap_server, imap_port, username, "
                "imap_password in account_config."
            )
        client = type(self).imap_client_factory(server, port)
        client.login(username, password)
        client.select("INBOX")
        self._connection = client
        return client

    def connect(
        self, oauth_redirect_payload: dict[str, Any] | None = None
    ) -> ProviderConnectResult:
        # Validate config + try a real connection. On success, persist
        # uidvalidity into config_to_persist for sync state seed.
        required_fields = {
            "imap_server",
            "imap_port",
            "smtp_server",
            "smtp_port",
            "username",
            "imap_password",
        }
        missing = required_fields - set(self.account_config.keys())
        if missing:
            return ProviderConnectResult(
                success=False,
                error_message=(
                    f"IMAP config missing required fields: {sorted(missing)}."
                ),
            )
        try:
            client = self._connect()
            typ, data = client.status("INBOX", "(UIDVALIDITY UIDNEXT)")
            if typ != "OK":
                return ProviderConnectResult(
                    success=False,
                    error_message=f"IMAP STATUS returned {typ}",
                )
            return ProviderConnectResult(
                success=True,
                provider_account_id=self.account_config.get("username"),
                config_to_persist={
                    "imap_status_at_connect": data[0].decode("utf-8")
                    if data
                    else None,
                },
            )
        except Exception as exc:  # noqa: BLE001
            return ProviderConnectResult(
                success=False, error_message=f"IMAP connect failed: {exc}"
            )
        finally:
            self.disconnect()

    def disconnect(self) -> None:
        if self._connection is not None:
            try:
                self._connection.logout()
            except Exception:  # noqa: BLE001
                pass
            self._connection = None

    def sync_initial(self, *, max_messages: int = 1000) -> ProviderSyncResult:
        """Initial backfill via UID search.

        Strategy: SELECT INBOX → UID SEARCH SINCE <30-days-ago> →
        return count + UIDVALIDITY + UIDNEXT cursor. The caller's
        ingestion pipeline fetches each message via ``fetch_message``.
        """
        from datetime import timedelta

        try:
            client = self._connect()
            # Compute 30-day-ago in IMAP date format
            since_date = (
                datetime.now(timezone.utc) - timedelta(days=30)
            ).strftime("%d-%b-%Y")
            typ, data = client.uid("SEARCH", None, f"(SINCE {since_date})")
            if typ != "OK":
                return ProviderSyncResult(
                    success=False, error_message=f"UID SEARCH returned {typ}"
                )
            uids = data[0].split() if data and data[0] else []
            uids = uids[-max_messages:] if len(uids) > max_messages else uids

            # Get UIDVALIDITY + UIDNEXT for cursor
            typ, status = client.status("INBOX", "(UIDVALIDITY UIDNEXT)")
            uidvalidity = None
            uidnext = None
            if typ == "OK" and status:
                # Parse "INBOX (UIDVALIDITY 123 UIDNEXT 456)"
                line = status[0].decode("utf-8", errors="replace")
                if "UIDVALIDITY" in line:
                    parts = line.split()
                    for i, p in enumerate(parts):
                        if p == "UIDVALIDITY" and i + 1 < len(parts):
                            try:
                                uidvalidity = int(parts[i + 1].rstrip(")"))
                            except ValueError:
                                pass
                        if p == "UIDNEXT" and i + 1 < len(parts):
                            try:
                                uidnext = int(parts[i + 1].rstrip(")"))
                            except ValueError:
                                pass

            return ProviderSyncResult(
                success=True,
                messages_synced=len(uids),
                threads_synced=len(uids),  # IMAP doesn't surface thread groups
                last_sync_at=datetime.now(timezone.utc),
                last_uid=uidnext,
            )
        except Exception as exc:  # noqa: BLE001
            return ProviderSyncResult(
                success=False, error_message=f"IMAP sync_initial failed: {exc}"
            )
        finally:
            self.disconnect()

    def subscribe_realtime(self) -> bool:
        # Step 2: polling-only. Step 2.1 ships IDLE.
        return False

    def fetch_message(self, provider_message_id: str) -> ProviderFetchedMessage:
        """Fetch a single message by UID + parse via stdlib email."""
        try:
            client = self._connect()
            typ, data = client.uid("FETCH", provider_message_id, "(RFC822)")
            if typ != "OK" or not data or not data[0]:
                raise RuntimeError(
                    f"IMAP UID FETCH returned {typ} for UID "
                    f"{provider_message_id}"
                )
            raw_bytes = data[0][1]
            mime = email.message_from_bytes(raw_bytes)
            return _parse_imap_mime(provider_message_id, mime, raw_bytes)
        finally:
            self.disconnect()

    def fetch_attachment(
        self, provider_message_id: str, provider_attachment_id: str
    ) -> bytes:
        """Fetch attachment bytes for an IMAP message.

        IMAP doesn't have stable attachment IDs; we use the part
        index (0, 1, 2, ...) as the attachment id. The fetch_message
        path records the index in ProviderAttachment.provider_attachment_id.
        """
        try:
            client = self._connect()
            typ, data = client.uid("FETCH", provider_message_id, "(RFC822)")
            if typ != "OK" or not data or not data[0]:
                raise RuntimeError(
                    f"IMAP UID FETCH returned {typ}"
                )
            raw_bytes = data[0][1]
            mime = email.message_from_bytes(raw_bytes)
            target_idx = int(provider_attachment_id)
            for idx, part in enumerate(mime.walk()):
                if part.get_content_disposition() == "attachment" and idx == target_idx:
                    payload = part.get_payload(decode=True)
                    return payload or b""
            raise RuntimeError(
                f"Attachment index {target_idx} not found in message"
            )
        finally:
            self.disconnect()

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
            "IMAP/SMTP send ships in Phase W-4b Layer 1 Step 3 (outbound)."
        )


def _parse_imap_mime(
    uid: str, mime: EmailMimeMessage, raw_bytes: bytes
) -> ProviderFetchedMessage:
    """Convert a stdlib email.message.Message into the canonical shape."""

    def _addr_list(value: str | None) -> list[tuple[str, str | None]]:
        if not value:
            return []
        return [
            (addr.lower().strip(), (name.strip() or None))
            for name, addr in getaddresses([value])
            if addr
        ]

    sender_raw = mime.get("From", "")
    sender_name, sender_addr = parseaddr(sender_raw)
    sender_email = sender_addr.lower().strip() if sender_addr else ""

    in_reply_to = mime.get("In-Reply-To", "").strip().strip("<>") or None

    body_html: str | None = None
    body_text: str | None = None
    attachments: list[ProviderAttachment] = []

    for idx, part in enumerate(mime.walk()):
        ctype = part.get_content_type()
        cdisp = part.get_content_disposition()
        if cdisp == "attachment":
            filename = part.get_filename() or f"attachment-{idx}"
            payload = part.get_payload(decode=True)
            attachments.append(
                ProviderAttachment(
                    provider_attachment_id=str(idx),
                    filename=filename,
                    content_type=ctype,
                    size_bytes=len(payload) if payload else None,
                    content_id=(part.get("Content-ID") or "").strip("<>")
                    or None,
                    is_inline=False,
                )
            )
        elif ctype == "text/html" and body_html is None:
            try:
                body_html = part.get_payload(decode=True).decode(
                    part.get_content_charset() or "utf-8", errors="replace"
                )
            except Exception:  # noqa: BLE001
                pass
        elif ctype == "text/plain" and body_text is None:
            try:
                body_text = part.get_payload(decode=True).decode(
                    part.get_content_charset() or "utf-8", errors="replace"
                )
            except Exception:  # noqa: BLE001
                pass

    sent_at = None
    if mime.get("Date"):
        try:
            sent_at = parsedate_to_datetime(mime.get("Date"))
        except (TypeError, ValueError):
            sent_at = None

    return ProviderFetchedMessage(
        provider_message_id=uid,
        provider_thread_id=None,  # IMAP doesn't surface thread ids
        sender_email=sender_email,
        sender_name=sender_name.strip() if sender_name else None,
        to=_addr_list(mime.get("To")),
        cc=_addr_list(mime.get("Cc")),
        bcc=_addr_list(mime.get("Bcc")),
        reply_to=_addr_list(mime.get("Reply-To")),
        subject=mime.get("Subject"),
        body_html=body_html,
        body_text=body_text,
        sent_at=sent_at,
        received_at=datetime.now(timezone.utc),
        in_reply_to_provider_id=in_reply_to,
        raw_payload={"message_id_header": mime.get("Message-ID")},
        attachments=attachments,
    )
