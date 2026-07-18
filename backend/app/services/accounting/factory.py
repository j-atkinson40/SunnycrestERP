"""Accounting provider factory — resolves the correct provider per tenant."""

from sqlalchemy.orm import Session

from app.services.accounting.base import AccountingProvider


def get_provider(
    db: Session,
    company_id: str,
    actor_id: str | None = None,
) -> AccountingProvider:
    """Resolve the accounting provider for a company.

    Reads the company's `accounting_provider` field and returns the
    corresponding provider instance.
    """
    from app.models.company import Company

    company = db.query(Company).filter(Company.id == company_id).first()
    provider_key = getattr(company, "accounting_provider", None) or "sage_csv"

    if provider_key == "quickbooks_online":
        # The QBO decommission (2026-07-18): the provider is deleted and
        # r134 reset every company off it — this branch is defense-in-depth
        # for a hand-edited row, answering honestly rather than erroring
        # into a void.
        from fastapi import HTTPException

        raise HTTPException(
            status_code=410,
            detail="QBO integration is retired — Bridgeable is the accounting system.",
        )

    # Default to Sage CSV
    from app.services.accounting.sage_provider import SageCSVProvider

    return SageCSVProvider(db, company_id, actor_id)


def get_available_providers() -> list[dict]:
    """List all supported accounting providers."""
    return [
        {
            "key": "none",
            "name": "None",
            "description": "No accounting integration",
            "supports_sync": False,
        },
        {
            "key": "sage_csv",
            "name": "Sage 100 (CSV Export)",
            "description": "Export data as Sage 100-compatible CSV files",
            "supports_sync": False,
        },
    ]
