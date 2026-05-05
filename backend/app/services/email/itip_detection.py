"""iTIP detection helper — Phase W-4b Layer 1 Calendar Step 3.

Cross-primitive boundary support for §3.26.16.5 Path 3: Email primitive
inspects inbound messages for iTIP REPLY content. When detected, the
calendar primitive's ``itip_inbound.process_inbound_reply`` is invoked
with the extracted VCALENDAR text.

**Two detection paths** per RFC 5546 transport conventions:
  1. ``Content-Type: text/calendar; method=REPLY`` MIME part — common
     for Outlook + Apple Mail iTIP responses
  2. ``application/ics`` attachment with ``METHOD:REPLY`` line — common
     for Gmail iTIP responses

Both paths return the canonical VCALENDAR text (UTF-8 decoded) when
detected. Returns None when no iTIP REPLY content present.

**Cross-primitive discipline**: this module lives in the email
primitive's service package because it operates on
``ProviderFetchedMessage`` shape (email primitive's data model).
The downstream call into ``app.services.calendar.itip_inbound``
hands off to the calendar primitive's semantic processing.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.email.providers.base import ProviderFetchedMessage

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────


def extract_itip_reply_text(
    provider_message: ProviderFetchedMessage,
) -> str | None:
    """Detect iTIP REPLY content in a fetched email + return VCALENDAR text.

    Two detection paths (RFC 5546 transport conventions):
      1. raw_payload MIME tree contains a ``text/calendar`` part with
         ``method=REPLY`` parameter → return the part's body
      2. attachments include a ``.ics`` file (application/ics or
         application/octet-stream + .ics extension) — Step 3 ships
         the part-based detection only; attachment-based detection
         requires fetched binary content which providers don't supply
         in the lightweight ``ProviderFetchedMessage`` shape (deferred)

    Returns None when no iTIP REPLY content present (most messages).

    **Step 3 boundary**: only Path 1 (Content-Type part) ships at
    Step 3. Path 2 (attachment-with-METHOD:REPLY) requires lazy
    attachment fetching + parsing of the .ics body — defer to Step 3.1
    if operator signal warrants. Most clients use Path 1 anyway
    (Outlook + Gmail + Apple Mail).
    """
    # raw_payload shape varies per provider; we check defensively.
    raw_payload: dict[str, Any] = (
        getattr(provider_message, "raw_payload", None) or {}
    )

    # Provider-agnostic detection: look for any nested dict with
    # mimeType containing "text/calendar" + body data + optional
    # METHOD=REPLY marker. Different providers nest differently:
    #   - Gmail: payload.parts[].mimeType + parts[].body.data (base64)
    #   - MS Graph: bodyPreview + attachments[].contentType + content
    #   - IMAP: nested multipart structure as parsed by email lib

    # Try Gmail-style nested parts first.
    text = _try_gmail_parts(raw_payload)
    if text:
        return text

    # Try MS Graph-style nested attachments.
    text = _try_msgraph_attachments(raw_payload)
    if text:
        return text

    return None


# ─────────────────────────────────────────────────────────────────────
# Provider-specific detection paths
# ─────────────────────────────────────────────────────────────────────


def _try_gmail_parts(raw_payload: dict[str, Any]) -> str | None:
    """Detect iTIP REPLY in Gmail-shape raw_payload.

    Gmail message resource structure (events.list raw payload via
    Gmail API):
      ``{payload: {mimeType, parts: [{mimeType, headers, body: {data}}]}}``

    Walk the parts tree looking for ``mimeType == "text/calendar"`` with
    ``method=REPLY`` in the part's headers OR in the body content.
    """
    payload = raw_payload.get("payload") or {}
    return _walk_part_tree_for_itip_reply(payload)


def _walk_part_tree_for_itip_reply(part: dict[str, Any]) -> str | None:
    """Recursively walk a MIME part tree looking for iTIP REPLY content."""
    mime_type = (part.get("mimeType") or part.get("contentType") or "").lower()

    if "text/calendar" in mime_type:
        # Check headers OR mime-type params for method=REPLY.
        is_reply = False
        headers = part.get("headers") or []
        for header in headers:
            name = (header.get("name") or "").lower()
            value = (header.get("value") or "")
            if name == "content-type" and "method=reply" in value.lower():
                is_reply = True
                break
        # Also check the bare mimeType string for ``method=REPLY`` (some
        # APIs flatten mimeType to a single string with parameters).
        if not is_reply and "method=reply" in mime_type:
            is_reply = True

        if is_reply:
            body_data = (part.get("body") or {}).get("data")
            if body_data:
                return _decode_base64_url(body_data)

        # If we can't determine method from headers, parse the body to
        # check for METHOD:REPLY line.
        body_data = (part.get("body") or {}).get("data")
        if body_data:
            decoded = _decode_base64_url(body_data)
            if decoded and "METHOD:REPLY" in decoded.upper():
                return decoded

    # Recurse into nested parts.
    for sub_part in (part.get("parts") or []):
        result = _walk_part_tree_for_itip_reply(sub_part)
        if result:
            return result

    return None


def _try_msgraph_attachments(raw_payload: dict[str, Any]) -> str | None:
    """Detect iTIP REPLY in MS Graph-shape raw_payload.

    MS Graph message resource:
      ``{attachments: [{contentType, contentBytes (base64)}]}``

    iTIP messages from Outlook arrive as ``application/ics`` attachments
    with the VCALENDAR text in contentBytes (base64-encoded).
    """
    attachments = raw_payload.get("attachments") or []
    for att in attachments:
        content_type = (att.get("contentType") or "").lower()
        if "calendar" not in content_type and "ics" not in content_type:
            continue
        content_bytes = att.get("contentBytes")
        if not content_bytes:
            continue
        try:
            import base64

            decoded = base64.b64decode(content_bytes).decode("utf-8")
        except Exception:  # noqa: BLE001
            continue
        if "METHOD:REPLY" in decoded.upper():
            return decoded
    return None


def _decode_base64_url(data: str) -> str | None:
    """Decode Gmail's base64url-encoded body data."""
    if not data:
        return None
    try:
        import base64

        # Gmail uses URL-safe base64 with possible missing padding.
        padding = "=" * (4 - len(data) % 4)
        decoded_bytes = base64.urlsafe_b64decode(data + padding)
        return decoded_bytes.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return None
