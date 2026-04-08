"""Disinterment PDF generation — renders release form to PDF via WeasyPrint.

Uses Jinja2 template at backend/app/templates/disinterment/release_form.html.
"""

import base64
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session, joinedload

from app.models.company import Company
from app.models.disinterment_case import DisintermentCase

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates", "disinterment")


def _get_jinja_env():
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    return Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )


def generate_release_form_pdf(db: Session, case_id: str, company_id: str) -> bytes:
    """Generate a disinterment release form PDF from case data.

    Returns PDF as bytes. Falls back gracefully if WeasyPrint is not installed.
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

    context = {
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

    env = _get_jinja_env()
    template = env.get_template("release_form.html")
    html = template.render(**context)

    try:
        from weasyprint import HTML

        pdf_bytes = HTML(string=html).write_pdf()
        logger.info("Generated release form PDF for case %s (%d bytes)", case.case_number, len(pdf_bytes))
        return pdf_bytes
    except ImportError:
        logger.warning("WeasyPrint not installed — returning empty PDF placeholder")
        return b"%PDF-1.4 placeholder"


def generate_release_form_base64(db: Session, case_id: str, company_id: str) -> str:
    """Generate release form PDF and return as base64 string (for DocuSign)."""
    pdf_bytes = generate_release_form_pdf(db, case_id, company_id)
    return base64.b64encode(pdf_bytes).decode("utf-8")
