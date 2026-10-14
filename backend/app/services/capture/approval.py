"""What the summary shows, and whether Approve may run.

⚠️ READ-ONLY AND SEPARATE FROM THE WRITE. This module answers "what would the order
look like, and is anything stopping it" without touching a row. `session_service`
calls it twice for two different purposes — to render the summary, and again inside
the approving transaction as the final gate — and a read-only assessor can be called
twice safely. A gate that lived inside the writer could only be tested by writing.

⚠️ EVERY BLOCKER IS A SENTENCE THE OFFICE CAN ACT ON, not a code. "A line would have
no price" is useless without saying which line and what is missing; the office
cannot add a product it cannot name.

⚠️ THE PRICE COMES FROM THE TENANT'S OWN `products` ROW, MATCHED ON AN EXACT NAME,
by dispatch. There is no other route: measured 2026-10-13, `variant_template_id` is
NULL on every tenant product on production (0 of 4 on sunnycrest, 0 of 25 on
testco), so the platform catalog the capture resolves against has no link to the
tenant catalog the order must bill from. The name is the only join, and when it
misses, Approve says so rather than inventing a price or writing a zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.capture.schema import EQUIPMENT_PACKAGES

#: Equipment slug -> the product name a tenant must carry for it to be billable.
#: ⚠️ DERIVED FROM THE SCHEMA'S OWN LABELS, not retyped. `EQUIPMENT_PACKAGES` is the
#: single source for what the capture can answer, so a package added there appears
#: here automatically and its missing product is reported rather than ignored.
EQUIPMENT_PRODUCT_NAMES: dict[str, str] = {
    slug: label for slug, label in EQUIPMENT_PACKAGES
}

#: The answer meaning "no equipment on this order" — no line, and no blocker.
EQUIPMENT_NONE = "none"


@dataclass(frozen=True)
class OrderLine:
    """One prospective `sales_order_lines` row."""

    kind: str
    description: str
    product_id: str | None
    unit_price: Decimal | None
    quantity: Decimal = Decimal("1")

    @property
    def line_total(self) -> Decimal:
        if self.unit_price is None:
            return Decimal("0.00")
        return (self.unit_price * self.quantity).quantize(Decimal("0.01"))


@dataclass(frozen=True)
class Approval:
    """Whether the order can be created, what it would contain, and what blocks it."""

    ready: bool
    blockers: tuple[str, ...]
    lines: tuple[OrderLine, ...]
    total: Decimal
    customer_id: str | None


def _product_by_exact_name(db: Session, tenant_id: str, name: str):
    """The tenant's active product of exactly this name, or None.

    ⚠️ CASE-INSENSITIVE, WHITESPACE-TRIMMED, AND STILL "EXACT". The office types a
    product name into a catalog form; the capture resolves a display name from the
    platform catalog. Those two strings agree on the words and cannot be relied on
    to agree on capitalisation. What is NOT done here is any kind of fuzzy or
    prefix match — "Monticello" must not bill as "Monticello Burial Vault", because
    those are different products at different prices ($1,405 against $1,250 on the
    two tenants measured).
    """
    return db.execute(
        text(
            "SELECT id, name, price FROM products "
            "WHERE company_id = :t AND lower(btrim(name)) = lower(btrim(:n)) "
            "AND is_active = true "
            "ORDER BY created_at NULLS LAST LIMIT 1"
        ),
        {"t": tenant_id, "n": name},
    ).first()


#: The one equipment package priced per unit, and the field holding its count.
EQUIPMENT_EXTRA_CHAIRS = "extra_chairs"
EXTRA_CHAIRS_COUNT_FIELD = "extra_chairs_count"


def _equipment_quantity(equip: str, answers: dict) -> Decimal:
    """How many of this equipment package the line bills.

    ⚠️ ONE FOR EVERY PACKAGE EXCEPT CHAIRS, WHICH ARE $5.00 EACH. Every other
    package in the price list is a flat charge for the setup, so its quantity is 1
    and the line total is the price. "Extra Chairs (Over 8)" is the one per-unit row
    on the list, and a quantity of 1 there would bill one chair for an order that
    said twelve.

    ⚠️ IT FALLS BACK TO 1 RATHER THAN 0 WHEN THE COUNT IS MISSING OR UNREADABLE, and
    that fallback is unreachable on the Approve path — `extra_chairs_count` is
    REQUIRED whenever chairs are chosen, so a missing count is already a blocker and
    `assess` cannot reach a line. The fallback exists because this function is also
    called while the capture is still being typed, where a half-finished answer must
    render something rather than raise. 0 would make the summary read $0.00 and look
    like a priced answer; 1 reads as the understated guess it is, and the blocker
    beside it says the count is still needed.
    """
    if equip != EQUIPMENT_EXTRA_CHAIRS:
        return Decimal("1")
    raw = answers.get(EXTRA_CHAIRS_COUNT_FIELD)
    try:
        return Decimal(str(raw))
    except (TypeError, ValueError, ArithmeticError):
        return Decimal("1")


def _customer_by_exact_name(db: Session, tenant_id: str, name: str):
    return db.execute(
        text(
            "SELECT id, name FROM customers "
            "WHERE company_id = :t AND lower(btrim(name)) = lower(btrim(:n)) "
            "AND is_active = true LIMIT 1"
        ),
        {"t": tenant_id, "n": name},
    ).first()


def assess(
    db: Session,
    *,
    tenant_id: str,
    answers: dict,
    missing_labels: tuple[str, ...],
    open_picks: tuple[str, ...],
    conflicts: tuple[str, ...] = (),
) -> Approval:
    """Build the prospective lines and collect every reason Approve cannot run.

    `missing_labels` and `open_picks` are passed in rather than recomputed so that
    the caller's already-evaluated state is the one being judged — recomputing here
    would be a second evaluation that could disagree with the rows on screen.
    """
    blockers: list[str] = []
    lines: list[OrderLine] = []

    # ── the gaps the capture already knows about ───────────────────────────
    if missing_labels:
        blockers.append(
            "Still needed: " + ", ".join(sorted(missing_labels)).lower()
        )
    for field_id in open_picks:
        blockers.append(f"A question is still open: {field_id.replace('_', ' ')}")

    # ⚠️ A CONFLICT BLOCKS, BY RULING (2026-10-13). An answer the vault cannot take
    # is not a detail to be dropped on the way to an order — "Monticello Burial Vault
    # doesn't offer Nameplate Only" is resolved by removing the nameplate or changing
    # the vault, and both are the office's decision.
    #
    # ⚠️ THE MESSAGES ARE PASSED THROUGH WHOLE, NOT RE-WORDED. They already name the
    # vault and the answer; restating them here would be a second wording to keep in
    # step with the first.
    blockers.extend(conflicts)

    # ── the funeral home must be a customer we can bill ───────────────────
    customer_id = None
    fh = (answers.get("funeral_home") or "").strip()
    if not fh:
        # Already reported by `missing_labels`; naming it twice would read as two
        # problems.
        pass
    else:
        row = _customer_by_exact_name(db, tenant_id, fh)
        if row is None:
            # ⚠️ IT REFUSES RATHER THAN CREATING THE CUSTOMER — Q2 from the
            # investigation, answered. Creating a counterparty as a side effect of
            # approving an order is a second write nobody asked for, and a
            # misspelled funeral home would quietly mint a duplicate the office
            # then has to merge.
            blockers.append(
                f"No customer record for {fh} — add it before approving."
            )
        else:
            customer_id = row.id

    # ── the vault line ─────────────────────────────────────────────────────
    vault = (answers.get("vault") or "").strip()
    if vault:
        prod = _product_by_exact_name(db, tenant_id, vault)
        if prod is None or prod.price is None:
            why = "has no product on this tenant" if prod is None else "has no price"
            blockers.append(f"{vault} {why} — the order line would have no price.")
        else:
            lines.append(
                OrderLine(
                    kind="vault",
                    description=prod.name,
                    product_id=prod.id,
                    unit_price=Decimal(prod.price),
                )
            )

    # ── the equipment line ─────────────────────────────────────────────────
    equip = (answers.get("cemetery_equipment") or "").strip()
    if equip and equip != EQUIPMENT_NONE:
        name = EQUIPMENT_PRODUCT_NAMES.get(equip)
        if name is None:
            # An answer the schema does not list. Reported rather than dropped.
            blockers.append(f"Unknown equipment package {equip!r}.")
        else:
            prod = _product_by_exact_name(db, tenant_id, name)
            if prod is None or prod.price is None:
                why = (
                    "has no product on this tenant" if prod is None else "has no price"
                )
                blockers.append(
                    f"{name} {why} — the order line would have no price."
                )
            else:
                lines.append(
                    OrderLine(
                        kind="equipment",
                        description=prod.name,
                        product_id=prod.id,
                        unit_price=Decimal(prod.price),
                        quantity=_equipment_quantity(equip, answers),
                    )
                )

    # ⚠️ AN ORDER WITH NO LINES IS NOT AN ORDER. Reachable without this: a complete
    # capture whose vault product is missing produces a blocker AND no lines, and a
    # future caller that ignored blockers would write a $0.00 order.
    if not lines:
        blockers.append("Nothing to bill — the order would have no lines.")

    total = sum((l.line_total for l in lines), Decimal("0.00")).quantize(
        Decimal("0.01")
    )
    return Approval(
        ready=not blockers,
        blockers=tuple(blockers),
        lines=tuple(lines),
        total=total,
        customer_id=customer_id,
    )
