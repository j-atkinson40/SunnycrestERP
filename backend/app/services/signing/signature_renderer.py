"""Apply captured signatures to the document PDF — Phase D-5 overlay path.

D-5 replaces the D-4 cover-page approach with anchor-based inline
overlay. Each signature is placed at its field's `anchor_string`
position (covering the invisible anchor text from the template) OR at
an explicit page+x/y if the field doesn't use anchors.

The overlay is a single-pass PDF write: one PyMuPDF document open,
all signatures placed, single save. Signatures applied to the current
version's bytes so multi-party envelopes composite correctly.

Degraded paths (kept for resilience):
- If PyMuPDF overlay fails, the renderer falls back to the D-4
  cover-page approach so a signed copy still exists.
- If a field has no anchor AND no explicit position, the signature is
  skipped (warning logged to signature_events).
"""

from __future__ import annotations

import hashlib
import io
import logging
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.canonical_document import Document, DocumentVersion
from app.models.signature import (
    SignatureEnvelope,
    SignatureField,
    SignatureParty,
)
from app.services import legacy_r2_client
from app.services.signing._overlay_engine import OverlaySpec, apply_overlays
from app.services.signing._signature_image import (
    DEFAULT_SIG_HEIGHT_PT,
    DEFAULT_SIG_WIDTH_PT,
    signature_image_for_party,
)

logger = logging.getLogger(__name__)


def _signed_storage_key(
    company_id: str, document_id: str, version_number: int
) -> str:
    return (
        f"tenants/{company_id}/documents/{document_id}/v{version_number}.pdf"
    )


# ── Overlay builder ──────────────────────────────────────────────────


def _build_overlays(envelope: SignatureEnvelope) -> list[OverlaySpec]:
    """Map each SignatureField + its party's signature data into an
    OverlaySpec. Skips fields that aren't signatures or whose party
    hasn't signed yet (shouldn't happen when called on a completed
    envelope, but defensive)."""
    specs: list[OverlaySpec] = []
    party_by_id: dict[str, SignatureParty] = {
        p.id: p for p in envelope.parties
    }
    for f in envelope.fields:
        # Only apply signature + initial fields via image overlay.
        # Text / checkbox / date fields are meta and don't render as
        # signature images (D-5+ may add text-field rendering).
        if f.field_type not in ("signature", "initial", "typed_name"):
            continue
        party = party_by_id.get(f.party_id)
        if party is None or party.status != "signed":
            continue

        width_pt = float(f.width or DEFAULT_SIG_WIDTH_PT)
        height_pt = float(f.height or DEFAULT_SIG_HEIGHT_PT)
        # Initials render smaller
        if f.field_type == "initial":
            width_pt = min(width_pt, 60.0)
            height_pt = min(height_pt, 30.0)

        image_bytes = signature_image_for_party(
            signature_type=party.signature_type,
            signature_data=party.signature_data,
            typed_name=party.typed_signature_name,
            width_pt=width_pt,
            height_pt=height_pt,
        )
        if image_bytes is None:
            logger.warning(
                "No signature image for party %s; skipping field %s",
                party.id,
                f.id,
            )
            continue

        specs.append(
            OverlaySpec(
                image_bytes=image_bytes,
                anchor_string=f.anchor_string,
                explicit_page=f.page_number,
                explicit_x_pt=f.position_x,
                explicit_y_pt=f.position_y,
                x_offset_pt=float(f.anchor_x_offset or 0.0),
                y_offset_pt=float(f.anchor_y_offset or 0.0),
                width_pt=width_pt,
                height_pt=height_pt,
                label=f"{party.role}:{f.field_type}",
            )
        )
    return specs


# ── Fallback cover page (D-4 approach) ─────────────────────────────────


def _render_signed_cover_page_html(envelope: SignatureEnvelope) -> str:
    """D-4 cover page — used as fallback if overlay fails entirely."""
    rows = []
    for p in sorted(envelope.parties, key=lambda x: x.signing_order):
        sig_block = ""
        if p.signature_type == "drawn" and p.signature_data:
            sig_block = (
                f'<img src="data:image/png;base64,{p.signature_data}" '
                f'style="max-width:280px;max-height:90px;border:1px solid #ccc;'
                f'padding:4px;background:white;" alt="signature" />'
            )
        elif p.typed_signature_name:
            sig_block = (
                f'<div style="font-family:\'Caveat\',\'Brush Script MT\',cursive;'
                f'font-size:28pt;padding:8px 12px;border:1px solid #ccc;'
                f'display:inline-block;background:#fffef8;">'
                f"{p.typed_signature_name}</div>"
            )
        signed_at = (
            p.signed_at.strftime("%Y-%m-%d %H:%M:%S UTC")
            if p.signed_at
            else ""
        )
        rows.append(
            f"""
            <div class="party">
              <div class="party-head">
                <span class="role">{p.role.replace('_', ' ').title()}</span>
                <span class="order">Order {p.signing_order}</span>
              </div>
              <div class="meta"><strong>{p.display_name}</strong> &lt;{p.email}&gt;</div>
              <div class="meta">Signed {signed_at} from {p.signing_ip_address or 'unknown IP'}</div>
              <div class="sig">{sig_block}</div>
            </div>
            """
        )
    rows_html = "".join(rows)
    return f"""<!DOCTYPE html><html><head>
<meta charset="utf-8"/>
<style>
  @page {{ size: letter portrait; margin: 0.75in; }}
  body {{ font-family: 'Helvetica Neue', Arial, sans-serif; color:#1a1a1a; }}
  h1 {{ font-size:16pt; color:#1a365d; border-bottom:2px solid #1a365d; padding-bottom:6px; margin:0 0 16px; }}
  .env-meta {{ font-size:10pt; margin-bottom:16px; color:#333; }}
  .party {{ border:1px solid #ccc; border-radius:4px; padding:12px; margin:10px 0; background:#fafafa; }}
  .party-head {{ display:flex; justify-content:space-between; margin-bottom:6px; }}
  .role {{ text-transform:uppercase; font-size:9pt; letter-spacing:0.5px; color:#555; }}
  .order {{ font-size:9pt; color:#888; }}
  .meta {{ font-size:10pt; margin:3px 0; }}
  .sig {{ margin-top:10px; }}
  .footer {{ margin-top:20px; font-size:8.5pt; color:#666; border-top:1px solid #ddd; padding-top:8px; }}
</style>
</head><body>
<h1>Electronic Signatures (fallback)</h1>
<div class="env-meta">
  <div><strong>{envelope.subject}</strong></div>
  <div>Envelope ID: <code>{envelope.id}</code></div>
  <div>Completed: {envelope.completed_at.strftime('%Y-%m-%d %H:%M:%S UTC') if envelope.completed_at else ''}</div>
</div>
{rows_html}
<div class="footer">
Anchor-based overlay was not possible for this document. This fallback
cover page is an integral part of the signed record. See the attached
Certificate of Completion for the full audit trail.
</div>
</body></html>"""


def _render_fallback_cover_page(envelope: SignatureEnvelope) -> bytes:
    from app.services.documents.document_renderer import _html_to_pdf

    html = _render_signed_cover_page_html(envelope)
    return _html_to_pdf(html)


# ── Main entry point ────────────────────────────────────────────────


def _fetch_current_pdf(doc: Document) -> bytes | None:
    try:
        return legacy_r2_client.download_bytes(doc.storage_key)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "R2 download failed for %s: %s", doc.storage_key, exc
        )
        return None


def render_signed_pdf(envelope: SignatureEnvelope) -> tuple[bytes, list[str]]:
    """Produce signed-PDF bytes for the envelope.

    Strategy:
      1. Fetch current document PDF from R2.
      2. Build overlay specs from envelope fields + party signatures.
      3. Apply overlays via PyMuPDF in a single pass.
      4. If anything fails (R2 miss, overlay error, zero fields applied),
         fall back to the D-4 cover-page HTML → PDF path so the envelope
         still completes with a signed artifact.

    Returns (pdf_bytes, missed_anchors). missed_anchors is a list of
    anchor strings that couldn't be resolved; caller logs them as
    audit events.
    """
    from app.models.canonical_document import Document as _Doc
    from app.database import SessionLocal

    # Pull the document reference freshly — the caller's session may
    # not have it refreshed after other mutations in the completion
    # transaction. Use a lightweight local session.
    doc: Document | None = envelope.document  # relationship if loaded
    if doc is None:
        with SessionLocal() as lookup_db:
            doc = lookup_db.query(_Doc).filter_by(
                id=envelope.document_id
            ).first()

    source_pdf = _fetch_current_pdf(doc) if doc else None
    overlays = _build_overlays(envelope)

    if source_pdf is None or not overlays:
        logger.info(
            "Falling back to cover-page render for envelope %s "
            "(source_pdf=%s, overlay_count=%d)",
            envelope.id,
            "ok" if source_pdf else "missing",
            len(overlays),
        )
        return _render_fallback_cover_page(envelope), []

    try:
        signed_bytes, result = apply_overlays(source_pdf, overlays)
        if result.applied == 0:
            # All overlays missed — fall back
            logger.warning(
                "All overlays missed for envelope %s; falling back to cover page",
                envelope.id,
            )
            return _render_fallback_cover_page(envelope), result.missed_anchors
        return signed_bytes, result.missed_anchors
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Anchor overlay failed for envelope %s: %s; "
            "falling back to cover page",
            envelope.id,
            exc,
        )
        return _render_fallback_cover_page(envelope), []


def apply_signatures_as_new_version(
    db: Session, envelope: SignatureEnvelope
) -> Document:
    """Produce a new DocumentVersion on the envelope's Document with
    signatures applied via anchor overlay. Updates Document.storage_key
    mirror.

    Returns the Document (same shape as D-1 renderer)."""
    doc = (
        db.query(Document).filter_by(id=envelope.document_id).first()
    )
    if doc is None:
        raise ValueError(
            f"Envelope {envelope.id} document_id not found"
        )

    start = time.perf_counter()
    pdf_bytes, missed = render_signed_pdf(envelope)
    elapsed_ms = int((time.perf_counter() - start) * 1000)

    # Next version number
    current = (
        db.query(DocumentVersion)
        .filter(
            DocumentVersion.document_id == doc.id,
            DocumentVersion.is_current == True,  # noqa: E712
        )
        .first()
    )
    next_number = ((current.version_number if current else 0)) + 1
    storage_key = _signed_storage_key(doc.company_id, doc.id, next_number)

    try:
        legacy_r2_client.upload_bytes(
            pdf_bytes, storage_key, content_type="application/pdf"
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Signed PDF upload failed for envelope %s: %s",
            envelope.id,
            exc,
        )

    now = datetime.now(timezone.utc)
    if current is not None:
        current.is_current = False
    context_hash = hashlib.sha256(
        f"envelope:{envelope.id}:completed".encode()
    ).hexdigest()
    new_version = DocumentVersion(
        id=str(uuid.uuid4()),
        document_id=doc.id,
        version_number=next_number,
        storage_key=storage_key,
        mime_type="application/pdf",
        file_size_bytes=len(pdf_bytes),
        rendered_at=now,
        rendering_context_hash=context_hash,
        render_reason=f"signed:envelope:{envelope.id}",
        is_current=True,
    )
    db.add(new_version)

    doc.storage_key = storage_key
    doc.file_size_bytes = len(pdf_bytes)
    doc.rendered_at = now
    doc.rendering_duration_ms = elapsed_ms
    doc.rendering_context_hash = context_hash
    doc.updated_at = now

    db.flush()

    # Log any missed anchors so the envelope detail page shows them
    if missed:
        from app.services.signing.signature_service import record_event

        record_event(
            db,
            envelope_id=envelope.id,
            event_type="signed_pdf_anchors_missed",
            meta={"missed_anchors": missed[:20]},
        )
        db.flush()

    return doc


def compute_signed_pdf_hash(envelope: SignatureEnvelope) -> str:
    """Compute the SHA-256 of the rendered signed PDF without persisting.
    Used by the Certificate of Completion for tamper detection."""
    try:
        pdf_bytes, _ = render_signed_pdf(envelope)
        return hashlib.sha256(pdf_bytes).hexdigest()
    except Exception:
        return ""
