"""Disinterment PDF generation — now routes through DocumentRenderer.

Phase D-1 migrated this service to use the canonical Document layer.
The public interface (`generate_release_form_pdf`,
`generate_release_form_base64`) is unchanged — callers (including the
DocuSign integration in `docusign_service.py`) keep working without
modification.

Under the hood, every call:
  1. Renders via `app.services.documents.document_renderer.render()`
  2. Creates a Document + DocumentVersion row in the canonical table
  3. Stores the PDF in R2 at
     `tenants/{company_id}/documents/{document_id}/v1.pdf`

The Document has `disinterment_case_id` populated, so you can query
"all documents for this case" with a simple FK lookup.
"""

from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload

from app.models.canonical_document import Document
from app.models.company import Company
from app.models.disinterment_case import DisintermentCase
from app.services.documents import document_renderer

logger = logging.getLogger(__name__)


def _build_context(db: Session, case: DisintermentCase, company: Company | None) -> dict:
    """Build the Jinja context for the disinterment release form.

    Unchanged from the pre-D-1 implementation — just extracted so the
    public function is easier to read and `rerender` can reuse it.
    """
    return {
        "company_name": company.name if company else "",
        "case_number": case.case_number,
        "generated_date": datetime.now(timezone.utc).strftime("%B %d, %Y"),
        "decedent_name": case.decedent_name,
        "date_of_death": case.date_of_death.strftime("%B %d, %Y") if case.date_of_death else None,
        "date_of_burial": case.date_of_burial.strftime("%B %d, %Y") if case.date_of_burial else None,
        "vault_description": case.vault_description,
        "cemetery_name": case.cemetery.name if case.cemetery else None,
        "cemetery_lot_section": case.cemetery_lot_section,
        "cemetery_lot_space": case.cemetery_lot_space,
        "reason": case.reason,
        "destination": case.destination,
        "next_of_kin": case.next_of_kin or [],
        "accepted_quote_amount": case.accepted_quote_amount,
    }


def generate_release_form_document(
    db: Session, case_id: str, company_id: str,
) -> Document:
    """Render the release form and return the persisted Document row.

    Phase D-1 API. Prefer this over the legacy byte-returning function
    for new code — it gives you a Document with full linkage.
    """
    case = (
        db.query(DisintermentCase)
        .options(
            joinedload(DisintermentCase.cemetery),
            joinedload(DisintermentCase.funeral_home),
        )
        .filter(
            DisintermentCase.id == case_id,
            DisintermentCase.company_id == company_id,
        )
        .first()
    )
    if not case:
        raise ValueError(f"Disinterment case {case_id} not found")

    company = db.query(Company).filter(Company.id == company_id).first()
    context = _build_context(db, case, company)

    doc = document_renderer.render(
        db,
        template_key="disinterment.release_form",
        context=context,
        document_type="disinterment_release_form",
        title=f"Disinterment Release — {case.case_number}",
        description=f"Release authorization form for disinterment case {case.case_number}",
        company_id=company_id,
        entity_type="disinterment_case",
        entity_id=case_id,
        disinterment_case_id=case_id,
        caller_module="disinterment_pdf_service.generate_release_form_document",
    )
    logger.info(
        "Generated release form Document %s for case %s (%d bytes)",
        doc.id,
        case.case_number,
        doc.file_size_bytes or 0,
    )
    return doc


def generate_release_form_pdf(db: Session, case_id: str, company_id: str) -> bytes:
    """Legacy API — returns PDF bytes.

    Routes through the Documents layer, then fetches bytes from R2. The
    extra round-trip is negligible vs actual WeasyPrint render time and
    keeps us with a single PDF pipeline.
    """
    try:
        doc = generate_release_form_document(db, case_id, company_id)
    except document_renderer.DocumentRenderError as exc:
        logger.warning(
            "DocumentRenderer failed for case %s — returning placeholder: %s",
            case_id,
            exc,
        )
        # Maintain the legacy "graceful fallback" behavior
        return b"%PDF-1.4 placeholder"

    return document_renderer.download_bytes(doc)


def generate_release_form_base64(db: Session, case_id: str, company_id: str) -> str:
    """Legacy API — returns the PDF base64-encoded (for DocuSign)."""
    pdf_bytes = generate_release_form_pdf(db, case_id, company_id)
    return base64.b64encode(pdf_bytes).decode("utf-8")
