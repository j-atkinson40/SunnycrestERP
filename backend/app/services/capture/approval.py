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
            # ⚠️ `included_chairs` IS IN THIS LIST AND FIVE TESTS FAILED BEFORE IT WAS.
            # The column was added by `r218_included_chairs` and read by
            # `billable_extra_chairs` through `getattr(prod, "included_chairs", None)` —
            # and an explicit SELECT that does not name it returns a row without the
            # attribute, so the getattr fell to its default and every derivation
            # correctly refused to compute. The code was right; the data was not
            # fetched. ⚠️ A `getattr` DEFAULT IS WHY THIS WAS QUIET: `row.included_chairs`
            # would have raised and named itself.
            "SELECT id, name, price, included_chairs FROM products "
            "WHERE company_id = :t AND lower(btrim(name)) = lower(btrim(:n)) "
            "AND is_active = true "
            "ORDER BY created_at NULLS LAST LIMIT 1"
        ),
        {"t": tenant_id, "n": name},
    ).first()


#: The one equipment package priced per unit, and the field holding its count.
#: ⚠️ THE PRODUCT NAME, HELD HERE BECAUSE IT IS NO LONGER AN EQUIPMENT OPTION.
#: `EQUIPMENT_PRODUCT_NAMES` is derived from `EQUIPMENT_PACKAGES`, and ruling A removed
#: chairs from that list — so the one string billing needs would have vanished with it.
#: The capital `Over` is load-bearing for the reason the schema's old comment gave: it
#: is the string the capture layer and the catalog share, and `r212` created the product
#: named as the price list names it.
EXTRA_CHAIRS_PRODUCT_NAME = "Extra Chairs (Over 8)"
CHAIRS_TOTAL_FIELD = "chairs_total"
CHAIRS_EXTRA_FIELD = "chairs_extra"


def _equipment_quantity(equip: str, answers: dict) -> Decimal:
    """How many of this equipment BUNDLE the line bills. Always one.

    ⚠️ IT USED TO BRANCH ON CHAIRS AND NO LONGER CAN, BY RULING A (2026-10-30). Chairs
    stopped being a `cemetery_equipment` option, so every value this function can see is
    a bundle, and every bundle in the price list is a flat charge for the setup. The
    chair quantity moved to `billable_extra_chairs` below, where it has the bundle's own
    included count to subtract.

    ⚠️ KEPT AS A FUNCTION RATHER THAN INLINED AS `1`. Its caller asks "how many of this
    line", which is a real question with a real answer; collapsing it would delete the
    place a future per-unit bundle would be handled, and the price list already has one
    per-unit row, so a second is not unimaginable.
    """
    return Decimal("1")


def billable_extra_chairs(
    included: int | None, total: object, extra: object
) -> Decimal | None:
    """Chairs to bill, or None when the question is still open.

    Ruling B' (James, 2026-10-30): *"Billable extras = max(0, chairs −
    bundle.included_chairs), billed on Extra Chairs (Over 8) at its price."* And the
    billing half of the same ruling: *"no Extra Chairs line when extras = 0 — never a
    $0 line."*

    THE THREE INPUTS AND WHY THERE ARE THREE:

        included    the BUNDLE's own `products.included_chairs`. `None` means the
                    product is not a bundle at all, which is not a zero.
        total       what the director said the crew sets out — "12 chairs".
        extra       what the director said was already extra — "extra chairs 4".

    ⚠️ `extra` WINS WHEN BOTH ARE PRESENT AND THEY AGREE, AND NEITHER WINS WHEN THEY DO
    NOT. James ruled the disagreement is a QUESTION, not an arithmetic: *"Both said and
    they disagree (e.g. '12 chairs, 6 extra' on Full Equipment) → don't pick."* So this
    returns None there and the caller asks. Returning either number would settle a
    thing the director said two ways.

    ⚠️ AND `None` IS NOT ZERO ANYWHERE IN HERE. Zero means "no chairs to bill, bill no
    line"; None means "I cannot say yet" — the bundle is unknown, the count is unsaid,
    or the two readings conflict. A caller that treats them alike bills a $0 line or
    silently drops a real one.
    """
    t = _as_int(total)
    e = _as_int(extra)

    # ⚠️ NO BUNDLE, NO DERIVATION. Without `included` an "extra" count is still usable
    # as given — it is already netted, by definition — but a TOTAL cannot be converted.
    if included is None:
        return Decimal(e) if e is not None else None

    if e is not None and t is not None:
        # the two readings, each expressed as extras
        if max(0, t - included) != e:
            return None                      # disagreement: the caller asks
        return Decimal(e)
    if e is not None:
        return Decimal(e)
    if t is not None:
        # ⚠️ CLAMPED AT ZERO. "6 chairs" on a bundle including 8 is fewer than the
        # bundle already brings; that bills no extras rather than a negative line.
        return Decimal(max(0, t - included))
    return None


def chairs_readings(included: int | None, total: object, extra: object):
    """`(total, extra)` pairs the two readings could mean, for the disagreement pick.

    ⚠️ IT EXISTS SO THE QUESTION CAN SHOW BOTH NUMBERS, which is what James asked for:
    *"Opas asks '12 chairs (4 extra) or 14 chairs (6 extra)?' with two pills."* A pick
    offering "4 or 6" would ask the director to do the arithmetic that confused the
    engine.
    """
    t = _as_int(total)
    e = _as_int(extra)
    if included is None or t is None or e is None:
        return ()
    return (
        (t, max(0, t - included)),       # take the total as said
        (e + included, e),               # take the extra as said
    )


def chairs_for_display(included: int | None, total: object, extra: object) -> str | None:
    """The equipment row's chair line — RULING E (James, 2026-10-30).

    *"`Full equipment · 12 chairs (4 extra)` when extras are non-zero,
    `Full equipment · 2 chairs` at or under the included count, and never a bare 0 —
    and it shows BOTH numbers whichever sense the director used, so `extra chairs 4`
    on Full Equipment still reads `12 chairs (4 extra)`."*

    Returns the chair half only; the bundle label is the row's primary value and the
    pane puts the two together.

    ⚠️ IT LIVES HERE RATHER THAN IN `rows.py` OR `surfaces.py` BECAUSE IT NEEDS THE
    BUNDLE. `included` is `products.included_chairs` on the bundle PRODUCT
    (`r218_included_chairs`), and neither of those layers has a database. The caller
    is `session_service`, which does — the same layer and the same reason the urn-vault
    row label flips there rather than on the static `Row`.

    ⚠️ AND IT IS HERE RATHER THAN IN `session_service` BECAUSE THE ARITHMETIC ALREADY
    IS. `billable_extra_chairs` and `chairs_readings` convert between the two senses
    four lines up; a second body doing the same subtraction in a serializer is the
    defect this repo has already paid for twice — two `title_case_name`s that
    disagreed on `"MCLEOD"`, and a `CHAIRS_INCLUDED` constant that disagreed with the
    product rows for two of five bundles.

    ⚠️ THE DISAGREEMENT CASE SHOWS BOTH READINGS rather than picking one. `"12 chairs,
    6 extra"` on a bundle including 8 is two different orders — 12 chairs or 14 — and
    ruling B blocks it at approval with exactly these numbers. A row that displayed
    one of them would quietly answer the question the blocker is asking.

    ⚠️ ZERO IS DELEGATED, NOT RE-DECIDED. `write_for_a_human(..., "count")` already
    renders `"0"` as `"none extra"` under the 2026-10-15 ruling, and "never a bare 0"
    is the same prohibition said again. Routing through it keeps one answer.
    """
    from app.services.capture.rows import write_for_a_human

    t = _as_int(total)
    e = _as_int(extra)
    if t is None and e is None:
        return None

    # ⚠️ NO BUNDLE, NO CONVERSION — the same refusal `billable_extra_chairs` makes, and
    # for the same reason: without the included count neither sense can be expressed as
    # the other. Ruling D' leaves the bundle open here and `assess` blocks, so the row
    # shows what the director actually said, labelled with the sense they said it in.
    if included is None:
        if t is not None:
            return write_for_a_human(str(t), "count")
        if e == 0:
            return "none extra"
        return f"{e} extra chair" if e == 1 else f"{e} extra chairs"

    if t is not None and e is not None and max(0, t - included) != e:
        a, b = chairs_readings(included, total, extra)
        return (
            f"{a[0]} chairs ({a[1]} extra) or {b[0]} chairs ({b[1]} extra)"
        )

    total_n = t if t is not None else e + included
    extra_n = max(0, total_n - included)
    shown = write_for_a_human(str(total_n), "count")
    return f"{shown} ({extra_n} extra)" if extra_n > 0 else shown


def included_chairs_for(db: Session, tenant_id: str, answers: dict) -> int | None:
    """The chosen bundle's `products.included_chairs`, or None when it cannot be read.

    ⚠️ FOUR WAYS TO GET None AND THEY ARE ALL THE SAME ANSWER TO THE CALLER: no bundle
    chosen, the explicit `none` answer, an equipment value the schema does not list, or
    a product row whose `included_chairs` is NULL. Each means "the included count is
    unknown", which is exactly what `chairs_for_display` and `billable_extra_chairs`
    refuse to derive from.

    ⚠️ A NULL COLUMN IS THE LIVE ONE. `included_chairs` is set on Sunnycrest's five
    production rows and nowhere else — no seed writes it — so on a new tenant every
    bundle returns None here until the onboarding checklist sets them.
    """
    equip = (answers.get("cemetery_equipment") or "").strip()
    if not equip or equip == EQUIPMENT_NONE:
        return None
    name = EQUIPMENT_PRODUCT_NAMES.get(equip)
    if name is None:
        return None
    prod = _product_by_exact_name(db, tenant_id, name)
    if prod is None:
        return None
    # ⚠️ PLAIN ATTRIBUTE ACCESS, NOT `getattr(..., None)`, AND THAT IS SWEEP ITEM 5
    # APPLIED AT THE SITE THAT PROMPTED IT. The same read through a getattr default
    # cost five failing tests and looked like a code bug: the SELECT did not name the
    # column, the default stood in for the value, and every derivation correctly
    # refused to compute. If the column stops being selected this raises and says so.
    return prod.included_chairs


def _as_int(raw: object) -> int | None:
    """⚠️ A SEPARATE HELPER SO "UNREADABLE" AND "UNSAID" COLLAPSE TO THE SAME None.
    Both mean the engine has no number, and a half-typed "1" must not bill one chair."""
    if raw is None or raw == "":
        return None
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return None


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

    # ── the equipment bundle line, and the extra-chairs line beneath it ────
    #
    # ⚠️ TWO LINES NOW, NOT ONE, BY RULING A (James, 2026-10-30). This block used to
    # bill the bundle OR the chairs, because chairs were one of the
    # `cemetery_equipment` options and the field holds one value. They are two rows on
    # the price list — a flat setup charge and a per-unit overage — and billing them as
    # alternatives is why "full setup, 12 chairs" produced an order with the chairs and
    # no package.
    #
    # ⚠️ AND `price_list_analysis_service` ALREADY SAID SO: "Items like 'Extra Chairs
    # (Over 8)' ... are per-unit overage charges, NOT bundles." Two layers disagreed
    # about the same string's kind; the equipment list was the one that was wrong.
    equip = (answers.get("cemetery_equipment") or "").strip()
    bundle_prod = None
    if equip and equip != EQUIPMENT_NONE:
        name = EQUIPMENT_PRODUCT_NAMES.get(equip)
        if name is None:
            # An answer the schema does not list. Reported rather than dropped.
            blockers.append(f"Unknown equipment package {equip!r}.")
        else:
            bundle_prod = _product_by_exact_name(db, tenant_id, name)
            if bundle_prod is None or bundle_prod.price is None:
                why = (
                    "has no product on this tenant" if bundle_prod is None
                    else "has no price"
                )
                blockers.append(f"{name} {why} — the order line would have no price.")
                bundle_prod = None
            else:
                # ⚠️ ALWAYS QUANTITY ONE. Every bundle is a flat charge for the setup;
                # `Vault Placer` at $0.00 still bills a REAL line, because its PRICE is
                # zero and its QUANTITY is one. That distinction was the whole of the
                # old zero-quantity rule and it survives — what has gone is chairs
                # being able to make a BUNDLE's quantity anything but one.
                lines.append(
                    OrderLine(
                        kind="equipment",
                        description=bundle_prod.name,
                        product_id=bundle_prod.id,
                        unit_price=Decimal(bundle_prod.price),
                        quantity=_equipment_quantity(equip, answers),
                    )
                )

    # ── extra chairs, derived from the bundle rather than from a constant ──
    #
    # ⚠️ THE INCLUDED COUNT COMES OFF THE BUNDLE PRODUCT (`r218_included_chairs`), not
    # from a global 8. Measured on production 2026-10-30, the constant was wrong for two
    # of the five bundles: "device only, 10 chairs" billed 2 extras, subtracting eight
    # chairs from a bundle that includes none.
    chairs_total = answers.get(CHAIRS_TOTAL_FIELD)
    chairs_extra = answers.get(CHAIRS_EXTRA_FIELD)
    if chairs_total is not None or chairs_extra is not None:
        included = getattr(bundle_prod, "included_chairs", None) if bundle_prod else None
        qty = billable_extra_chairs(included, chairs_total, chairs_extra)
        if qty is None:
            # ⚠️ OPEN, NOT ZERO, AND IT BLOCKS RATHER THAN BILLING NOTHING. Three ways
            # to get here: no bundle chosen yet, a mention with no number, or the two
            # readings disagreeing. All three are questions the director has to answer,
            # and an order that quietly billed $0 for them is the failure the
            # unsaid/zero distinction exists to prevent.
            if bundle_prod is None:
                blockers.append(
                    "Chairs were named but no equipment bundle is chosen — the "
                    "billable extras depend on what the bundle includes."
                )
            elif _as_int(chairs_total) is not None and _as_int(chairs_extra) is not None:
                a, b = chairs_readings(included, chairs_total, chairs_extra)
                blockers.append(
                    f"Chairs were given two ways: {a[0]} chairs ({a[1]} extra) or "
                    f"{b[0]} chairs ({b[1]} extra). Which?"
                )
            else:
                blockers.append("Chairs were named but the count is still needed.")
        elif qty > 0:
            # ⚠️ NO LINE WHEN EXTRAS ARE ZERO, BY RULING — "never a $0 line". A bundle
            # that already includes the chairs the family needs bills the setup and
            # nothing more; a zero-quantity line would read as a priced answer.
            chair_prod = _product_by_exact_name(db, tenant_id, EXTRA_CHAIRS_PRODUCT_NAME)
            if chair_prod is None or chair_prod.price is None:
                why = (
                    "has no product on this tenant" if chair_prod is None
                    else "has no price"
                )
                blockers.append(
                    f"{EXTRA_CHAIRS_PRODUCT_NAME} {why} — the order line would have "
                    f"no price."
                )
            else:
                lines.append(
                    OrderLine(
                        kind="equipment",
                        description=chair_prod.name,
                        product_id=chair_prod.id,
                        unit_price=Decimal(chair_prod.price),
                        quantity=qty,
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


# ---------------------------------------------------------------------------
# What Approve will do, said before it is pressed
# ---------------------------------------------------------------------------


def describe_approve_effect(
    db: Session, tenant_id: str, answers: dict, approval: Approval
) -> str | None:
    """One line stating what pressing Approve will set in motion, from the real data.

    James's step 3, item 3. Example shape:

        Confirms the order · Delivered Tue Oct 20 · Invoiced at month end (Hopkins)

    ⚠️ IT IS BUILT FROM THE SAME `Approval` THE BUTTON IS GATED ON, not from a second
    read of the answers. A preview derived independently could promise something the
    press would not do — which is the whole failure this line exists to prevent, since
    Approve is now the step that puts an order in front of the batch.

    ⚠️ RETURNS None WHEN THE ORDER IS NOT APPROVABLE. A promise about a press that will
    be refused is worse than no promise; the blockers already say what is wrong.

    ⚠️ AND IT DOES NOT SAY "EMAILED" UNLESS MAIL CAN ACTUALLY LEAVE. A customer set to
    `invoice_immediately` would otherwise read as "Invoiced immediately" while the
    per-tenant `invoice_email_enabled` switch is off and nothing is sent — a sentence on
    screen that the system contradicts silently. The switch is consulted so the line
    describes what happens rather than what the customer record prefers.
    """
    if not approval.ready:
        return None

    parts = ["Confirms the order"]

    service = answers.get("service_date")
    when = _format_service_day(service)
    # ⚠️ NO DATE MEANS NO SENTENCE RATHER THAN A VAGUER ONE. `service_date` is
    # unconditionally required, so `approval.ready` already implies it is present; if
    # that ever changes, omitting the clause is better than promising "Delivered" with
    # no day attached.
    if when:
        parts.append(f"Delivered {when}")

    billing = _describe_billing(db, tenant_id, approval.customer_id)
    if billing:
        parts.append(billing)

    return " · ".join(parts)


def _format_service_day(value: object) -> str | None:
    """`'2026-10-20'` -> `'Tue Oct 20'`, or None if it is not a full date.

    The capture stores partial dates for other fields (a birth YEAR, commonly), so this
    refuses anything that is not a real day rather than rendering "Delivered 1948".
    """
    from datetime import date as _date

    if isinstance(value, _date):
        d = value
    elif isinstance(value, str):
        try:
            d = _date.fromisoformat(value.strip())
        except ValueError:
            return None
    else:
        return None
    # ⚠️ `%-d` RATHER THAN `%d`: "Oct 20" not "Oct 20" with a leading zero on single
    # digits. Platform-specific, so it is done by hand.
    return f"{d:%a %b} {d.day}"


def _describe_billing(db: Session, tenant_id: str, customer_id: str | None) -> str | None:
    """"Invoiced at month end (Hopkins)" — what billing will do, and for whom."""
    if not customer_id:
        return None
    row = db.execute(
        text(
            "SELECT name, invoice_delivery_preference FROM customers "
            "WHERE id = :c AND company_id = :t"
        ),
        {"c": customer_id, "t": tenant_id},
    ).first()
    if row is None:
        return None
    name, preference = row[0], (row[1] or "statement_only")

    # ⚠️ THE FIRST WORD OF THE NAME, because this line is read at a glance next to two
    # other clauses and "Hopkins" is how the office says it. The full name is on the
    # Review's own customer row.
    short = (name or "").split()[0] if name else "customer"

    if preference in ("invoice_immediately", "both"):
        from app.services.invoice_email_switch import invoice_email_allowed

        allowed, _why = invoice_email_allowed(db, tenant_id)
        if allowed:
            return f"Invoiced and emailed ({short})"
        # ⚠️ SAYS SO RATHER THAN IMPLYING A SEND. The invoice is still created; only the
        # mail is withheld, and the office should not be told otherwise.
        return f"Invoiced, not emailed ({short})"
    return f"Invoiced at month end ({short})"
