"""Invoice settings — stored in companies.settings_json under 'invoice_settings'.

Provides defaults for every field so callers always get a fully-populated dict.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_DEFAULTS: dict[str, Any] = {
    # Template
    "template_key": "professional",
    # Content toggles
    "show_deceased_name": True,
    "show_payment_terms": True,
    "show_early_payment_discount": True,
    "show_finance_charge_notice": True,
    "show_cemetery_on_invoice": True,
    "show_service_date": True,
    "show_order_number": True,
    # Company contact on invoice
    "show_phone": True,
    "show_email": True,
    "show_website": False,
    # Remittance stub
    "show_remittance_stub": False,
    # Branding colors
    "primary_color": "#1B4F8A",
    "secondary_color": "#2D9B8A",
    # Remit-to overrides (None = use company defaults)
    "remit_to_name": None,
    "remit_to_address": None,
    # Footer
    "custom_footer_text": None,
    # Terms text overrides (None = use defaults)
    "payment_terms_text": None,
    "early_payment_text": None,
    "finance_charge_text": None,
}


def get_invoice_settings(db: Session, company_id: str) -> dict[str, Any]:
    """Return invoice settings merged with defaults."""
    from app.models.company import Company

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        return dict(_DEFAULTS)

    stored: dict[str, Any] = company.get_setting("invoice_settings") or {}
    # Merge: stored values override defaults
    result = dict(_DEFAULTS)
    result.update({k: v for k, v in stored.items() if k in _DEFAULTS})
    return result


def update_invoice_settings(
    db: Session, company_id: str, updates: dict[str, Any]
) -> dict[str, Any]:
    """Merge updates into stored invoice settings and persist."""
    from app.models.company import Company

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise ValueError(f"Company {company_id} not found")

    current: dict[str, Any] = company.get_setting("invoice_settings") or {}
    # Only allow known keys
    filtered = {k: v for k, v in updates.items() if k in _DEFAULTS}
    current.update(filtered)
    company.set_setting("invoice_settings", current)
    db.commit()

    return get_invoice_settings(db, company_id)


def build_terms_text(settings: dict[str, Any], company: Any) -> dict[str, str]:
    """Build the three terms text strings, using overrides or sensible defaults."""
    payment_terms_text = (
        settings.get("payment_terms_text")
        or (
            f"{company.default_payment_terms} from statement date"
            if getattr(company, "default_payment_terms", None)
            else "Net 30 days from statement date"
        )
    )
    early_payment_text = (
        settings.get("early_payment_text")
        or "5% discount if paid within 15 days of statement date"
    )
    finance_charge_text = (
        settings.get("finance_charge_text")
        or "Finance charge of 2% per month applied to balances over 30 days"
    )
    return {
        "payment_terms_text": payment_terms_text,
        "early_payment_text": early_payment_text,
        "finance_charge_text": finance_charge_text,
    }
