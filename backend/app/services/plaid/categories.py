"""Plaid category → platform expense-category resolution (B-2).

Two-tier read (TenantGLMapping pattern): platform rows (`tenant_id IS
NULL`, seeded by seed_plaid_b2.py) overridden by tenant rows at the same
`plaid_category` key. DETAILED keys win over PRIMARY keys at resolve time.

NEVER SILENTLY CONFIDENT: unmapped resolves to None — the honest
uncategorized, counted in every sync summary. RE-CATEGORIZATION IS
FORWARD-ONLY: the map applies at ingest (and when Plaid itself modifies
a transaction); a mapping change does NOT rewrite history — surfaced as
an open spec decision in the B-2 STATE entry.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.plaid import PlaidCategoryMapping

# The platform vocabulary (mirrors EXPENSE_CATEGORIES in
# expense_categorization_agent.py — the 15-value platform set).
PLATFORM_EXPENSE_CATEGORIES = (
    "vault_materials", "direct_labor", "delivery_costs", "other_cogs",
    "rent", "utilities", "insurance", "payroll", "office_supplies",
    "vehicle_expense", "repairs_maintenance", "depreciation",
    "professional_fees", "advertising", "other_expense",
)


def load_map(db: Session, tenant_id: str) -> dict[str, str]:
    """One query, tenant rows overlaying platform rows — call once per
    pipeline run, not per transaction."""
    rows = (
        db.query(PlaidCategoryMapping)
        .filter(
            PlaidCategoryMapping.is_active.is_(True),
            (PlaidCategoryMapping.tenant_id.is_(None))
            | (PlaidCategoryMapping.tenant_id == tenant_id),
        )
        .all()
    )
    out: dict[str, str] = {}
    # Platform first, tenant second — the overlay order.
    for row in sorted(rows, key=lambda r: r.tenant_id is not None):
        out[row.plaid_category] = row.expense_category
    return out


def resolve(mapping: dict[str, str], primary: str | None,
            detailed: str | None) -> str | None:
    """Detailed wins over primary; unmapped = honest None."""
    if detailed and detailed in mapping:
        return mapping[detailed]
    if primary and primary in mapping:
        return mapping[primary]
    return None
