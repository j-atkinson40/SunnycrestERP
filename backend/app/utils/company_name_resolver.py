"""Resolve the best display name for customers, vendors, and cemeteries.

Uses the enriched name from company_entities when linked via master_company_id,
falling back to the legacy table name otherwise.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.cemetery import Cemetery
    from app.models.customer import Customer
    from app.models.vendor import Vendor


def resolve_customer_name(customer: Customer | None) -> str:
    """Return company_entities.name if linked, else customer.name."""
    if customer is None:
        return "Unknown"
    if (
        customer.master_company_id
        and customer.company_entity
        and customer.company_entity.name
    ):
        return customer.company_entity.name
    return customer.name or "Unknown"


def resolve_vendor_name(vendor: Vendor | None) -> str:
    """Return company_entities.name if linked, else vendor.name."""
    if vendor is None:
        return "Unknown"
    if (
        vendor.master_company_id
        and vendor.company_entity
        and vendor.company_entity.name
    ):
        return vendor.company_entity.name
    return vendor.name or "Unknown"


def resolve_cemetery_name(cemetery: Cemetery | None) -> str:
    """Return company_entities.name if linked, else cemetery.name."""
    if cemetery is None:
        return "Unknown"
    if (
        cemetery.master_company_id
        and cemetery.company_entity
        and cemetery.company_entity.name
    ):
        return cemetery.company_entity.name
    return cemetery.name or "Unknown"
