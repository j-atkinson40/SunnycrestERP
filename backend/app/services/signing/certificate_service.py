"""Certificate of Completion generator — Phase D-4.

Produces an ESIGN-compliant audit record as a canonical Document via
the `pdf.signature_certificate` managed template.

Certificate content:
- Envelope subject + description
- All parties with name, email, role, consent timestamp, signature
  timestamp, IP, user agent, signature thumbnail
- Original document hash + signed document hash (tamper detection)
- Full event timeline from signature_events
- ESIGN footer
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.canonical_document import Document
from app.models.signature import SignatureEnvelope, SignatureEvent, SignatureParty


def _fmt_timestamp(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def _party_signature_src(party: SignatureParty) -> str | None:
    """Return the data: URI to show the drawn signature image, or None
    if the party used a typed signature."""
    if party.signature_type == "drawn" and party.signature_data:
        return f"data:image/png;base64,{party.signature_data}"
    return None


def _build_context(
    db: Session, envelope: SignatureEnvelope
) -> dict[str, Any]:
    parties = sorted(envelope.parties, key=lambda p: p.signing_order)
    parties_ctx = []
    for p in parties:
        parties_ctx.append(
            {
                "display_name": p.display_name,
                "role": p.role.replace("_", " ").title(),
                "email": p.email,
                "signing_order": p.signing_order,
                "consented_at": _fmt_timestamp(p.consented_at),
                "signed_at": _fmt_timestamp(p.signed_at),
                "signing_ip_address": p.signing_ip_address or "",
                "signing_user_agent": (p.signing_user_agent or "")[:200],
                "signature_type": p.signature_type or "",
                "signature_image_src": _party_signature_src(p),
                "typed_signature_name": p.typed_signature_name,
            }
        )

    events = (
        db.query(SignatureEvent)
        .filter(SignatureEvent.envelope_id == envelope.id)
        .order_by(SignatureEvent.sequence_number)
        .all()
    )
    party_name_by_id = {p.id: p.display_name for p in parties}
    events_ctx = [
        {
            "sequence_number": e.sequence_number,
            "created_at": _fmt_timestamp(e.created_at),
            "event_type": e.event_type,
            "party_name": (
                party_name_by_id.get(e.party_id, "") if e.party_id else ""
            ),
            "ip_address": e.ip_address or "",
        }
        for e in events
    ]

    # Compute the signed PDF hash
    from app.services.signing.signature_renderer import compute_signed_pdf_hash

    signed_hash = compute_signed_pdf_hash(envelope)

    return {
        "envelope_id": envelope.id,
        "envelope_subject": envelope.subject,
        "envelope_description": envelope.description or "",
        "envelope_created_at": _fmt_timestamp(envelope.created_at),
        "envelope_completed_at": _fmt_timestamp(envelope.completed_at),
        "envelope_routing_type": envelope.routing_type,
        "parties": parties_ctx,
        "original_document_hash": envelope.document_hash,
        "signed_document_hash": signed_hash,
        "events": events_ctx,
    }


def generate_certificate(
    db: Session, envelope: SignatureEnvelope
) -> Document:
    """Render the certificate via the managed template and persist a
    canonical Document row. Returns the Document."""
    from app.services.documents import document_renderer

    context = _build_context(db, envelope)
    doc = document_renderer.render(
        db,
        template_key="pdf.signature_certificate",
        context=context,
        document_type="signature_certificate",
        title=f"Certificate of Completion — {envelope.subject}",
        company_id=envelope.company_id,
        entity_type="signature_envelope",
        entity_id=envelope.id,
        caller_module="signing.certificate_service.generate_certificate",
        description=(
            f"ESIGN Certificate of Completion for envelope "
            f"{envelope.subject!r}"
        ),
    )
    return doc
