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


def render_form_pdf(form_data: list[dict]) -> bytes:
    """Render Wilbert engraving form as print-ready PDF using WeasyPrint.

    Returns PDF bytes.
    """
    html_parts = [
        "<!DOCTYPE html><html><head>",
        "<style>",
        "body { font-family: Arial, sans-serif; margin: 20px; }",
        ".form-page { page-break-after: always; border: 2px solid #333; "
        "padding: 24px; margin-bottom: 20px; }",
        ".form-page:last-child { page-break-after: auto; }",
        "h1 { font-size: 18px; text-align: center; margin: 0 0 16px; "
        "border-bottom: 2px solid #333; padding-bottom: 8px; }",
        ".field { display: flex; margin: 6px 0; font-size: 13px; }",
        ".label { font-weight: bold; width: 160px; flex-shrink: 0; }",
        ".value { flex: 1; border-bottom: 1px solid #ccc; min-height: 18px; "
        "padding-left: 4px; }",
        ".engraving-section { margin: 12px 0; padding: 12px; "
        "background: #f8f8f8; border: 1px solid #ddd; }",
        ".engraving-section h2 { font-size: 14px; margin: 0 0 8px; }",
        "</style></head><body>",
    ]

    for piece in form_data:
        html_parts.append('<div class="form-page">')
        html_parts.append("<h1>Wilbert Engraving Order Form</h1>")

        engraving_fields = {"Line 1", "Line 2", "Line 3", "Line 4", "Font"}
        non_engraving = [
            (k, v) for k, v in piece.items() if k not in engraving_fields
        ]
        engraving = [(k, v) for k, v in piece.items() if k in engraving_fields]

        for label, value in non_engraving:
            html_parts.append(
                f'<div class="field">'
                f'<span class="label">{label}:</span>'
                f'<span class="value">{value}</span></div>'
            )

        if engraving:
            html_parts.append('<div class="engraving-section">')
            html_parts.append(f"<h2>Engraving — {piece.get('Piece', 'Main')}</h2>")
            for label, value in engraving:
                html_parts.append(
                    f'<div class="field">'
                    f'<span class="label">{label}:</span>'
                    f'<span class="value">{value}</span></div>'
                )
            html_parts.append("</div>")

        html_parts.append("</div>")

    html_parts.append("</body></html>")
    html_str = "\n".join(html_parts)

    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=html_str).write_pdf()
        return pdf_bytes
    except ImportError:
        logger.warning("WeasyPrint not available — returning HTML as fallback")
        return html_str.encode("utf-8")


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
