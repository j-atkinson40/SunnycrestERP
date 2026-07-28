"""S-2 (§4.3) price-list-reference assembler — the tenant's PUBLISHED
tiered price list for the products the user is quoting.

This surface is a REFERENCE display (§4.3 purpose 2 — "Customer's recent
order pattern when quoting"), so the tiered ``price_list_items``
(standard / contractor / homeowner) columns are the CORRECT source HERE:
they are what the published price list shows. This is the deliberate
counterpart to the quote-preview surface, which must instead use the
order resolver — see quote_preview.py. The two surfaces read two
different, independently-maintained price sources ON PURPOSE.

Active-version selection mirrors ``command_bar_data_search``: the
``status="active"`` row with the most recent ``activated_at``, falling
back to the most-recently-activated row of any status when none is
active.
"""

from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.price_list_item import PriceListItem
from app.models.price_list_version import PriceListVersion
from app.services.command_bar.quote_preview import _money, resolve_product


def _active_version(db: Session, company_id: str) -> PriceListVersion | None:
    base = db.query(PriceListVersion).filter(
        PriceListVersion.tenant_id == company_id
    )
    active = (
        base.filter(PriceListVersion.status == "active")
        .order_by(PriceListVersion.activated_at.desc().nullslast())
        .first()
    )
    if active:
        return active
    # Fallback: most-recently-activated version regardless of status.
    return base.order_by(
        PriceListVersion.activated_at.desc().nullslast()
    ).first()


def build_price_list_reference(
    db: Session,
    company_id: str,
    *,
    product_refs: list[str],
    customer_id: str | None = None,
) -> dict:
    """Return the published tiered prices for each resolved product.

    ``customer_id`` is accepted for surface-contract symmetry (a future
    slice may highlight the customer's applicable tier) but does NOT
    select a price today — tier selection is not a customer property.
    """
    version = _active_version(db, company_id)
    rows: list[dict] = []
    seen: set[str] = set()

    for ref in product_refs:
        # Only show a published row for a CLEANLY resolved product;
        # ambiguous / unresolved refs are silently skipped here (the
        # quote-preview surface owns surfacing those states).
        res = resolve_product(db, company_id, ref)
        product = res.product if res.status == "resolved" else None
        if not product or product.id in seen:
            continue
        seen.add(product.id)

        item = None
        if version:
            item = (
                db.query(PriceListItem)
                .filter(
                    PriceListItem.version_id == version.id,
                    or_(
                        PriceListItem.product_code == product.sku,
                        PriceListItem.product_name.ilike(product.name),
                    ),
                )
                .first()
            )

        rows.append(
            {
                "product_name": product.name,
                "on_list": item is not None,
                "standard_price_formatted": (
                    _money(item.standard_price)
                    if item and item.standard_price is not None
                    else "—"
                ),
                "contractor_price_formatted": (
                    _money(item.contractor_price)
                    if item and item.contractor_price is not None
                    else "—"
                ),
                "homeowner_price_formatted": (
                    _money(item.homeowner_price)
                    if item and item.homeowner_price is not None
                    else "—"
                ),
                "unit": (item.unit if item else "") or "",
            }
        )

    version_label = None
    if version:
        version_label = version.label or f"v{version.version_number}"

    return {"version_label": version_label, "rows": rows}
