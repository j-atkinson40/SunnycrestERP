"""S-2 (§4.3) quote-preview assembler — the money-math behind the
floating quote-preview contextual surface.

CORRECTNESS DISCIPLINE (ruled decision 3, hand-proven in
tests/test_quote_preview.py):

  - The preview reuses the ORDER pricing resolver
    ``order_pricing_service.get_effective_price(product, order_lines, db)``
    — the SAME resolver quote/order creation uses. It shows what the
    order will actually CHARGE, never the tiered publication display
    (``price_list_items.standard_price``). The two are maintained
    independently and legitimately diverge; the price-list REFERENCE
    surface is the correct home for the tiered display, not the preview.

  - Customer identity does NOT select a price tier (the
    standard/contractor/homeowner columns are a publication artifact).
    ``customer_id`` here affects TAX only.

  - ``is_call_office`` products render "Price on request" — never a
    fabricated number.

  - Tax that does not resolve (no jurisdiction / cemetery mid-draft)
    yields NO confident grand total: the document's Total row is hidden
    (``total_formatted=""``) and the widget chrome surfaces the honest
    "Subtotal $X · calculated at order". A preview must not invent tax.

  - ``money.round_money`` (banker's rounding, ROUND_HALF_EVEN) at the
    line boundary via ``money.line_total``; the total is
    ``subtotal + tax_amount`` (both already at the cent, not re-rounded)
    — matching ``quote_service.create_quote`` exactly.

RENDER DISCIPLINE (ruled decision 2): renders through the REAL pipeline
via ``document_renderer.render_preview_html(template_key="quote.standard")``
— the identical ``body_template`` + Jinja env the final PDF uses, minus
only the separable WeasyPrint print step. No second renderer; drift is
impossible by construction. Missing fields render blank (default Jinja
``Undefined``). No persisted Document, no materialized Quote — a preview
must not create data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.product import Product
from app.services import tax_service
from app.services.documents import document_renderer
from app.services.money import line_total as money_line_total
from app.services.order_pricing_service import get_effective_price

# The exact template both the preview and the final quote PDF load. Kept
# as a module constant so the drift-guard test can assert preview and
# final document share this one source (they cannot diverge — same key,
# same body_template, same Jinja env; the PDF path only adds WeasyPrint).
QUOTE_TEMPLATE_KEY = "quote.standard"


def _money(value) -> str:
    """Format a Decimal/number as ``$1,250.00``.

    Deliberately identical to ``quote_service._money`` — the preview's
    figures must format byte-for-byte like the final quote's. Duplicated
    (rather than importing a private name) so the anti-drift contract is
    legible here; the shared source of truth is the shape, asserted in
    tests. Returns ``—`` on bad input.
    """
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "—"


@dataclass
class DraftLine:
    """One in-flight quote line as lifted from the NL extraction:
    a product reference (name string — the NL extract does NOT resolve
    products to rows), an optional already-resolved product_id, and a
    quantity."""

    product_ref: str
    quantity: float = 1.0
    product_id: Optional[str] = None


@dataclass
class AmbiguousRef:
    """A product ref that matched MULTIPLE catalog products above the
    similarity threshold. The preview refuses to guess — it surfaces the
    candidates so the user disambiguates."""

    product_ref: str
    candidates: list[str]


@dataclass
class ProductResolution:
    """Three-state result of resolving a product ref. ``ambiguous`` is
    the correctness-critical state: a preview must never guess a product
    when several could match — a wrong price is worse than no price."""

    status: str  # "resolved" | "unresolved" | "ambiguous"
    product: Optional[Product] = None
    candidates: list[str] = field(default_factory=list)


@dataclass
class QuotePreviewResult:
    html: str
    context: dict
    subtotal: Decimal
    subtotal_formatted: str
    tax_resolved: bool
    total: Optional[Decimal]
    total_formatted: Optional[str]
    has_call_office: bool
    unresolved_products: list[str]
    ambiguous_products: list[AmbiguousRef]
    line_count: int


def resolve_product(
    db: Session,
    company_id: str,
    product_ref: str,
    product_id: Optional[str] = None,
) -> ProductResolution:
    """Resolve a product reference to a tenant-scoped active Product row —
    fuzzy-with-refusal (S-2 staging-witness fix, 2026-07-28).

    Order:
      1. Exact by product_id (if given).
      2. FAST PATH — substring ``ilike`` (+ trailing-plural), unchanged.
         Clean names ("Monticello") still resolve exactly as before.
      3. On a substring MISS, FUZZY FALLBACK via the shared pg_trgm
         resolver (``command_bar.resolver.resolve``, the same matcher the
         command-bar/query search uses — REUSED, not re-implemented; its
         ``similarity >= threshold`` filter is the "clears the threshold"
         gate). This handles qualifier-suffixed AI names ("Monticello
         Standard" → "Monticello") whose substring can't match the shorter
         catalog name.

    REFUSAL RULE (the correctness core): resolve ONLY if EXACTLY ONE
    candidate clears the threshold. Zero → unresolved. TWO OR MORE →
    ``ambiguous`` (DO NOT PICK) — a wrong price is worse than no price.
    """
    if product_id:
        p = (
            db.query(Product)
            .filter(
                Product.id == product_id,
                Product.company_id == company_id,
                Product.is_active.is_(True),
            )
            .first()
        )
        if p:
            return ProductResolution("resolved", product=p)

    name = (product_ref or "").strip()
    if not name:
        return ProductResolution("unresolved")

    # 2. Fast path — substring / sku match (+ trailing plural). Unchanged.
    patterns = [name]
    if len(name) > 3 and name.lower().endswith("s"):
        patterns.append(name[:-1])
    for pat in patterns:
        p = (
            db.query(Product)
            .filter(
                Product.company_id == company_id,
                Product.is_active.is_(True),
                or_(
                    Product.name.ilike(f"%{pat}%"),
                    Product.sku.ilike(f"%{pat}%"),
                ),
            )
            .order_by(Product.name.asc())
            .first()
        )
        if p:
            return ProductResolution("resolved", product=p)

    # 3. Fuzzy fallback with refusal. Lazy import keeps the resolver off
    #    the fast (import-time + substring-hit) path.
    from app.services.command_bar import resolver as _resolver

    hits = _resolver.resolve(
        db,
        query_text=name,
        company_id=company_id,
        entity_types=("product",),
        limit=5,
    )
    if not hits:
        return ProductResolution("unresolved")
    if len(hits) >= 2:
        # Multiple products cleared the similarity threshold — refuse.
        return ProductResolution(
            "ambiguous", candidates=[h.primary_label for h in hits]
        )
    only = hits[0]
    p = (
        db.query(Product)
        .filter(
            Product.id == only.entity_id,
            Product.company_id == company_id,
            Product.is_active.is_(True),
        )
        .first()
    )
    if p:
        return ProductResolution("resolved", product=p)
    return ProductResolution("unresolved")


def assemble_quote_preview(
    db: Session,
    company_id: str,
    *,
    customer_id: Optional[str] = None,
    customer_name: Optional[str] = None,
    lines: list[DraftLine],
) -> QuotePreviewResult:
    """Price the in-flight draft lines through the order resolver, build
    the ``quote.standard`` context, and render it to HTML through the
    real document pipeline. No persistence, no materialized quote."""
    company = db.query(Company).filter(Company.id == company_id).first()
    company_name = company.name if company else ""

    # Pass 1 — resolve every product. Three outcomes: priced, unresolved
    # (couldn't find), or ambiguous (multiple candidates — refuse to guess).
    resolved: list[tuple[DraftLine, Product]] = []
    unresolved: list[str] = []
    ambiguous: list[AmbiguousRef] = []
    for dl in lines:
        res = resolve_product(db, company_id, dl.product_ref, dl.product_id)
        ref = (dl.product_ref or "").strip()
        if res.status == "resolved" and res.product is not None:
            resolved.append((dl, res.product))
        elif res.status == "ambiguous" and ref:
            ambiguous.append(
                AmbiguousRef(product_ref=ref, candidates=res.candidates)
            )
        elif ref:
            unresolved.append(ref)

    # The line collection conditional pricing / vault detection reads
    # (get_effective_price → has_vault_on_order inspect line.product_id).
    order_lines = [
        SimpleNamespace(
            product_id=product.id,
            quantity=dl.quantity,
            unit_price=None,
            line_total=None,
        )
        for dl, product in resolved
    ]

    line_contexts: list[dict] = []
    tax_lines: list[dict] = []
    has_call_office = False
    subtotal = Decimal("0.00")

    for dl, product in resolved:
        qty = dl.quantity or 0
        unit = get_effective_price(product, order_lines, db)
        if unit is None:
            # Call-office product — price on request, never a fabricated number.
            has_call_office = True
            line_contexts.append(
                {
                    "description": product.name,
                    "quantity": float(qty),
                    "unit_price_formatted": "Price on request",
                    "line_total_formatted": "—",
                }
            )
            continue
        lt = money_line_total(qty, unit)
        subtotal = subtotal + lt
        line_contexts.append(
            {
                "description": product.name,
                "quantity": float(qty),
                "unit_price_formatted": _money(unit),
                "line_total_formatted": _money(lt),
            }
        )
        tax_lines.append(
            {"product_id": product.id, "amount": lt, "description": product.name}
        )

    # Tax — resolved deterministically or honestly deferred. A preview
    # mid-draft usually has no cemetery/jurisdiction, so this frequently
    # does not resolve; that yields NO grand total (require_resolution=False
    # returns a tolerated zero-tax result we detect via .resolved).
    tax_resolved = False
    total: Optional[Decimal] = None
    if tax_lines:
        res = tax_service.resolve_line_tax(
            db,
            company_id,
            lines=tax_lines,
            customer_id=customer_id,
            require_resolution=False,
        )
        if res.resolved:
            tax_resolved = True
            total = subtotal + res.tax_amount

    # The document's Total row appears ONLY with a real, tax-resolved
    # total (template guards on `{% if total_formatted %}`). Otherwise the
    # widget chrome shows subtotal + "calculated at order".
    context = {
        "company_name": company_name,
        "quote_number": "DRAFT",
        "quote_date": datetime.now(timezone.utc).strftime("%B %-d, %Y"),
        "customer_name": customer_name or "",
        "expiry_date": "",
        "lines": line_contexts,
        "total_formatted": _money(total) if (tax_resolved and total is not None) else "",
        "notes": "",
    }

    html = document_renderer.render_preview_html(
        db,
        template_key=QUOTE_TEMPLATE_KEY,
        context=context,
        company_id=company_id,
    )

    return QuotePreviewResult(
        html=html,
        context=context,
        subtotal=subtotal,
        subtotal_formatted=_money(subtotal) if tax_lines else "",
        tax_resolved=tax_resolved,
        total=total,
        total_formatted=(_money(total) if total is not None else None),
        has_call_office=has_call_office,
        unresolved_products=unresolved,
        ambiguous_products=ambiguous,
        line_count=len(line_contexts),
    )
