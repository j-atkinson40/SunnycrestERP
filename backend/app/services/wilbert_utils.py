"""Wilbert engraving form utilities.

Handles form field mapping, PDF generation, and email composition
for Wilbert engraving submissions.
"""

import io
import logging
from collections import OrderedDict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Ordered dict mapping Wilbert physical form field names → data sources.
# Keys are the field labels as they appear on Wilbert's physical form.
WILBERT_FORM_FIELDS = OrderedDict([
    ("Licensee", "tenant_name"),
    ("Order Number", "order_id"),
    ("Date", "submission_date"),
    ("Funeral Home", "funeral_home_name"),
    ("FH Contact", "fh_contact_email"),
    ("Decedent Name", "engraving_line_1"),
    ("Urn Model", "product_name"),
    ("Urn SKU", "product_sku"),
    ("Color", "color_selection"),
    ("Piece", "piece_label"),
    ("Line 1", "engraving_line_1"),
    ("Line 2", "engraving_line_2"),
    ("Line 3", "engraving_line_3"),
    ("Line 4", "engraving_line_4"),
    ("Font", "font_selection"),
    ("Photo Etch", "has_photo"),
    ("Need By Date", "need_by_date"),
    ("Delivery Method", "delivery_method"),
    ("Special Instructions", "notes"),
])


def generate_form_data(order, jobs) -> list[dict]:
    """Assemble structured form data dicts from order + engraving jobs.

    Returns one dict per piece (main + companions).
    """
    pieces = []
    for job in jobs:
        piece = OrderedDict()
        piece["Licensee"] = ""  # Populated by caller with tenant name
        piece["Order Number"] = str(order.id)[:8] if order else ""
        piece["Date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        piece["Funeral Home"] = ""  # Populated by caller
        piece["FH Contact"] = order.fh_contact_email or ""
        piece["Urn Model"] = ""  # Populated by caller with product name
        piece["Urn SKU"] = ""  # Populated by caller with product sku
        piece["Color"] = job.color_selection or ""
        piece["Piece"] = job.piece_label or "main"
        piece["Line 1"] = job.engraving_line_1 or ""
        piece["Line 2"] = job.engraving_line_2 or ""
        piece["Line 3"] = job.engraving_line_3 or ""
        piece["Line 4"] = job.engraving_line_4 or ""
        piece["Font"] = job.font_selection or ""
        piece["Photo Etch"] = "Yes" if job.photo_file_id else "No"
        piece["Need By Date"] = (
            order.need_by_date.isoformat() if order.need_by_date else ""
        )
        piece["Delivery Method"] = order.delivery_method or ""
        piece["Special Instructions"] = order.notes or ""
        pieces.append(piece)
    return pieces


def _piece_context(piece: dict) -> dict:
    """Convert a raw piece dict (from `generate_form_data`) into the
    shape the `urn.wilbert_engraving_form` Jinja template expects.

    Splits the field/value pairs into engraving vs non-engraving so
    the template can render them in separate sections."""
    engraving_fields = {"Line 1", "Line 2", "Line 3", "Line 4", "Font"}
    non_engraving = [
        (k, v) for k, v in piece.items() if k not in engraving_fields
    ]
    engraving = [(k, v) for k, v in piece.items() if k in engraving_fields]
    return {
        "piece_label": piece.get("Piece", "Main"),
        "non_engraving": non_engraving,
        "engraving": engraving,
    }


def render_form_pdf(form_data: list[dict], *, db=None, company_id: str | None = None) -> bytes:
    """Render Wilbert engraving form as print-ready PDF.

    Phase D-9: routes through the managed template registry
    (`urn.wilbert_engraving_form`) rather than inline HTML + WeasyPrint.
    The content is fundamentally transient (one-time physical form
    printout) so no Document row is persisted — `render_pdf_bytes`
    returns raw bytes. Callers that need an audit trail should call
    `urn_engraving_service.submit_to_wilbert` which wraps this in a
    DocumentDelivery.

    `db` and `company_id` are optional — the managed registry lookup
    falls back to a platform-global template when tenant scope can't
    be resolved. Most callers DO thread tenant scope (see
    `urn_engraving_service`).
    """
    from app.services.documents import document_renderer

    pieces = [_piece_context(p) for p in form_data]

    try:
        return document_renderer.render_pdf_bytes(
            db,
            template_key="urn.wilbert_engraving_form",
            context={"pieces": pieces},
            company_id=company_id,
        )
    except document_renderer.DocumentRenderError as exc:
        # Legacy contract preserved: on render failure, return the HTML
        # string encoded as bytes so the caller can still see *something*.
        logger.warning(
            "Wilbert form PDF render failed (%s) — returning HTML fallback",
            exc,
        )
        return (
            "<html><body><p>PDF generation unavailable. "
            f"Error: {exc}</p></body></html>"
        ).encode("utf-8")


def build_submission_email(
    order, pdf_bytes: bytes, tenant_slug: str, decedent_name: str,
) -> dict:
    """Build email dict for Wilbert engraving submission.

    Returns dict with: subject, body_html, attachment_name, attachment_bytes.
    """
    order_id_short = str(order.id)[:8]
    subject = (
        f"[{tenant_slug}-URN-{order_id_short}] "
        f"Engraving Order - {decedent_name}"
    )
    body_html = (
        f"<p>Please find attached the engraving order form for:</p>"
        f"<ul>"
        f"<li><strong>Order:</strong> {order_id_short}</li>"
        f"<li><strong>Decedent:</strong> {decedent_name}</li>"
        f"</ul>"
        f"<p>Please process and return proofs at your earliest convenience.</p>"
    )
    return {
        "subject": subject,
        "body_html": body_html,
        "attachment_name": f"engraving-order-{order_id_short}.pdf",
        "attachment_bytes": pdf_bytes,
    }


def build_correction_email(
    job, correction_summary: dict, tenant_slug: str,
) -> dict:
    """Build email dict for Wilbert resubmission after rejection/changes."""
    order_id_short = str(job.urn_order_id)[:8]
    round_num = job.resubmission_count + 1
    subject = (
        f"[{tenant_slug}-URN-{order_id_short}] "
        f"Engraving Correction - Revision {round_num}"
    )
    notes_parts = []
    if correction_summary.get("rejection_notes"):
        notes_parts.append(
            f"<li><strong>Staff notes:</strong> "
            f"{correction_summary['rejection_notes']}</li>"
        )
    if correction_summary.get("fh_change_request_notes"):
        notes_parts.append(
            f"<li><strong>Funeral home notes:</strong> "
            f"{correction_summary['fh_change_request_notes']}</li>"
        )
    notes_html = "<ul>" + "".join(notes_parts) + "</ul>" if notes_parts else ""

    body_html = (
        f"<p>Revision {round_num} requested for order {order_id_short}:</p>"
        f"{notes_html}"
        f"<p>Please update the proof and return at your earliest convenience.</p>"
    )
    return {
        "subject": subject,
        "body_html": body_html,
    }
