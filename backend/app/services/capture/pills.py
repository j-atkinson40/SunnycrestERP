"""The three or four answers Opas offers for the question it is asking.

James's dispatch of 2026-10-27, clause 3:

> PILLS: up to 3-4 answers per question, answer only: no prices or descriptions
> (towns on funeral homes and cemeteries, dates on days, "cremation" on urn
> vaults). Order: this customer's usual first (counted from their orders, the same
> rule as the Customer Pane's "What Opas knows"), then the tenant's most ordered.

⚠️ "THE SAME RULE" IS A SHARED FUNCTION, NOT A SECOND IMPLEMENTATION. `rank_habits`
in `order_list.customer` is the rule — at least 2 orders AND at least 25%, max 3,
count-descending, ties by name — and this module calls it. Two implementations of
"the same rule" agree until one of them is tuned, and the Customer Pane shows its
habits on screen, so a divergence would be visible as the pane and the pills
disagreeing about what this home usually orders.

⚠️ AND IT COUNTS FROM THE SAME ROWS. `load_facts` is what the order list and the
Customer Pane read; the habits here are computed over its `OrderFacts`, not over a
query written for pills. One source, one answer.

⚠️ ANSWER ONLY — AND THE `sub` FIELD IS THE EXCEPTION THE DISPATCH NAMES, not a
loophole. Three things may appear beside an answer, because each of them is what
tells two answers apart rather than a description of one: a TOWN (two St. Mary's),
a DATE (which Thursday), and the word "cremation" (this vault makes it one). No
price, ever — the dispatch says so and the prototype obeys it too, showing prices
only in the pane's total and never on a pill.

⚠️ PILLS COME FROM WHAT THE TENANT CARRIES, which is why there is no "offer it and
let approve complain" path. Measured 2026-10-27: the platform catalogue holds exactly
one cremation-specific equipment item, `Cremation Table` (`CE-CT`), and NO TENANT
STOCKS IT. Offering it would put an answer in front of the office that
`approval.assess` must then refuse for want of a product. So equipment pills are
filtered to packages the tenant can bill, and the Cremation Table will appear on its
own the day Sunnycrest adds the product. See
`docs/investigations/2026-10-27-is-this-vault-a-cremation.md`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.capture.schema import (
    EQUIPMENT_PACKAGES,
    VAULT_FIELD_ID,
    ResolvedField,
)
from app.services.capture.vault_form import VAULT_FORMS, FormResolver
from app.services.order_list.customer import rank_habits
from app.services.personalization.questions import ANSWER_NONE

#: ⚠️ FOUR, WHICH IS THE TOP OF THE DISPATCH'S RANGE ("up to 3-4"). The prototype
#: shows three for most questions and four for burial equipment, and four is also the
#: number of distinct ⌥ keys a reader will scan without counting. Not a cap on what
#: EXISTS — a director types anything; this caps what is OFFERED.
MAX_PILLS = 4

#: Only the next three service days are offered, Sundays skipped.
#:
#: ⚠️ THE PROTOTYPE'S OWN RULE, quoted: `function nextDays(n){…if(d.getDay()!==0)…}`.
#: Sunday is excluded because a burial is not scheduled on one, and `nextDays` starts
#: at `i=1` — TOMORROW, not today. An order taken this morning for this afternoon is
#: typed, not picked.
DAYS_OFFERED = 3

#: ⚠️ THE BURIAL-ONLY EQUIPMENT PACKAGES, and each one is burial-only for a physical
#: reason rather than by convention: a lowering device lowers a casket into a grave and
#: a vault placer sets a burial vault. Neither happens at a committal.
#:
#: ⚠️ DERIVED FROM NOTHING — IT IS A JUDGEMENT, and it is declared here rather than
#: inferred from a name so that a package added to `EQUIPMENT_PACKAGES` is offered for
#: BOTH kinds until somebody decides otherwise. The failure mode of the other default
#: is silently hiding a new package from half the orders.
#: The fields whose answers are ranked from the tenant's order history.
#:
#: ⚠️ IT IS NOT "FIELDS WITH PILLS" — enum fields have pills too and get them from the
#: resolved schema's own options, which needs no history. This names the fields that
#: must READ, so every other field can skip `load_facts` entirely.
#:
#: ⚠️ AND IT IS CHECKED ALONGSIDE `options == ()`, NOT INSTEAD OF IT, so a field that
#: is neither — a new free-text field — reads nothing by default. The failure mode of
#: the other arrangement is a new field silently reading every order on every
#: keystroke.
RANKED_FROM_HISTORY = frozenset({
    VAULT_FIELD_ID,
    "funeral_home",
    "cemetery",
    "service_time",
})

#: `customers.customer_type` for a funeral home. The column's own model comment
#: declares the vocabulary: 'funeral_home', 'contractor', 'cemetery', 'individual',
#: 'unknown'. There is no CHECK constraint, so the string is the contract.
FUNERAL_HOME_TYPE = "funeral_home"

BURIAL_ONLY_EQUIPMENT = frozenset({
    "full_equipment",
    "lowering_device_and_grass",
    "lowering_device_only",
    "vault_placer",
})


@dataclass(frozen=True)
class Pill:
    """One offered answer.

    `value` is what gets stored — an id for an enum field, the display text for a
    resolved-entity or free-text field. That split is the schema's, not this module's:
    `FieldDefinition.options` means "stores an id".
    """

    value: str
    label: str
    #: The one thing that tells this answer from another. None for most pills.
    sub: str | None = None

    def as_dict(self) -> dict:
        out: dict = {"value": self.value, "label": self.label}
        if self.sub:
            out["sub"] = self.sub
        return out


def _dedupe(pills: list[Pill]) -> list[Pill]:
    """First occurrence wins, which is what makes "usual first" mean anything.

    ⚠️ WITHOUT THIS THE USUAL ONE APPEARS TWICE. Habits and tenant-frequency are two
    rankings over the same population — a home's usual vault is usually also the
    tenant's most ordered — so concatenating them repeats it, and the repeat would take
    one of the four slots.
    """
    seen: set[str] = set()
    out: list[Pill] = []
    for pill in pills:
        if pill.value in seen:
            continue
        seen.add(pill.value)
        out.append(pill)
    return out


def _habit_then_tenant(
    *,
    mine: list[str | None],
    mine_total: int,
    everyone: list[str | None],
) -> list[str]:
    """This customer's usual first, then the tenant's most ordered.

    ⚠️ THE TENANT TAIL IS NOT HABIT-FILTERED, deliberately. `rank_habits` answers "is
    this a habit of this customer", which is a claim about a person. The tail answers
    "what does this licensee sell", which only has to be popular — applying the 25%
    bar to a tenant with twenty products would empty the tail and leave a question with
    one pill on it.
    """
    usual = [name for name, _ in rank_habits(mine, total=mine_total)] if mine_total else []
    counts: dict[str, int] = {}
    for value in everyone:
        if value:
            counts[value] = counts.get(value, 0) + 1
    tail = [name for name, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
    ordered: list[str] = []
    for name in [*usual, *tail]:
        if name not in ordered:
            ordered.append(name)
    return ordered


def _service_days(today: date) -> list[Pill]:
    """Tomorrow and the next two service days, Sundays skipped.

    ⚠️ THE LABEL IS THE WEEKDAY AND THE SUB IS THE DATE, which is the prototype's
    split: `opt('day', d.iso, tomorrow?'Tomorrow':d.weekday, d.short, d)`. "Thursday"
    is the answer; "Oct 29" is what tells this Thursday from the next one.
    """
    out: list[Pill] = []
    step = 1
    while len(out) < DAYS_OFFERED and step < 14:
        day = today + timedelta(days=step)
        step += 1
        if day.weekday() == 6:  # Sunday
            continue
        out.append(Pill(
            value=day.isoformat(),
            label="Tomorrow" if day == today + timedelta(days=1) else day.strftime("%A"),
            sub=f"{day.strftime('%b')} {day.day}",
        ))
    return out


def _enum_pills(
    field: ResolvedField,
    *,
    mine: list[str | None],
    mine_total: int,
    everyone: list[str | None],
    allowed: set[str] | None,
) -> list[Pill]:
    """An enum field's own options, ordered by habit then tenant frequency.

    ⚠️ `permitted_answers` IS WHAT MAKES "ONLY THE OPTIONS THAT VAULT OFFERS" TRUE, and
    it is the engine's own answer rather than a rule invented here. `resolve_schema`
    stamps it from `platform_personalization_availability` — the catalogue's record of
    what each vault physically takes — so a Venetian that offers only a nameplate
    offers only a nameplate here.

    ⚠️ EMPTY MEANS "NO NARROWING", NOT "NOTHING PERMITTED". The field's own docstring
    says so: *"Empty for plain fields and for NOT_CONFIGURED questions, where any
    answer the question defines is acceptable."* Reading empty as a filter would empty
    every pill row on every non-personalization question, and would hide
    personalization entirely on a licensee whose availability is not configured —
    which is most of them.

    ⚠️ "NONE" IS KEPT LAST RATHER THAN RANKED. It is the most-chosen answer on plenty
    of tenants, and ranking it by frequency would put "No personalization" first on a
    question about personalization — technically the usual answer, and a worse question.
    """
    options = [(value, label) for value, label in (field.definition.options or ())]
    if field.permitted_answers:
        permitted = set(field.permitted_answers) | {ANSWER_NONE}
        options = [(v, l) for v, l in options if v in permitted]
    if allowed is not None:
        options = [(v, l) for v, l in options if v in allowed]
    labels = dict(options)
    ranked = _habit_then_tenant(mine=mine, mine_total=mine_total, everyone=everyone)
    ordered: list[str] = []
    for value in ranked:
        if value in labels and value != ANSWER_NONE:
            ordered.append(value)
    for value, _ in options:
        if value not in ordered and value != ANSWER_NONE:
            ordered.append(value)
    if ANSWER_NONE in labels:
        ordered.append(ANSWER_NONE)
    return [Pill(value=value, label=labels[value]) for value in ordered]


def _tenant_equipment(db: Session, tenant_id: str) -> set[str]:
    """Which equipment packages this tenant can actually bill.

    ⚠️ A PACKAGE WITHOUT A PRODUCT IS NOT AN ANSWER. `approval.EQUIPMENT_PRODUCT_NAMES`
    maps each package to the product name a tenant must carry, and `assess` reports a
    blocker when it is absent. Offering it anyway would mean a pill that cannot be
    approved — the exact shape of the door offering an edit it could not perform
    (2026-10-26).
    """
    from app.services.capture.approval import EQUIPMENT_PRODUCT_NAMES

    carried = {
        str(name).strip().lower()
        for (name,) in db.execute(
            text("SELECT name FROM products WHERE company_id = :t AND is_active"),
            {"t": tenant_id},
        ).all()
        if name
    }
    allowed = {ANSWER_NONE}
    for slug, product_name in EQUIPMENT_PRODUCT_NAMES.items():
        if slug == ANSWER_NONE or product_name.strip().lower() in carried:
            allowed.add(slug)
    return allowed


def pills_for(
    db: Session,
    *,
    tenant_id: str,
    field_id: str,
    values: dict,
    resolved_fields: tuple[ResolvedField, ...],
    today: date,
    facts: list | None = None,
) -> tuple[Pill, ...]:
    """The answers to offer for `field_id`, already ordered and capped.

    ⚠️ AN EMPTY TUPLE IS A REAL ANSWER AND MEANS "TYPE IT". `deceased_name`, the dates
    and `grave_location` have no offerable answers — a name is not pickable from a list
    — and the dispatch's own prototype marks those questions `free:true` rather than
    inventing options. The caller renders the hint instead of a row of pills.

    ⚠️ `facts` IS INJECTABLE SO THE CALLER CAN READ ONCE. A response that asks about
    one field reads the tenant's orders once; without this, every field asked during a
    session re-runs `load_facts`.
    """
    from app.services.order_list.service import load_facts

    by_id = {f.definition.field_id: f for f in resolved_fields}
    field = by_id.get(field_id)
    if field is None:
        return ()

    if field_id == "service_date":
        return tuple(_service_days(today))

    # ⚠️ A FREE-TEXT FIELD READS NOTHING. `deceased_name`, the dates and
    # `grave_location` have no offerable answers, so returning early here is not a
    # micro-optimisation — it is the difference between reading every order the tenant
    # has and reading none, on a question that can never have a pill.
    #
    # ⚠️ AND THIS RUNS ON EVERY KEYSTROKE. `_guided` is called from `read_state`, which
    # the client hits on a ~350ms debounce while the director types; `load_facts` is a
    # full pass over the tenant's sales orders with a correlated subquery per row. The
    # question being asked is `deceased_name` for a good part of a real order.
    if field.definition.options == () and field_id not in RANKED_FROM_HISTORY:
        return ()

    if facts is None:
        facts = load_facts(db, tenant_id)

    # ⚠️ ONE RESOLVER FOR THE WHOLE CALL. `form_of` is five table reads, and the vault
    # branch asks it once per product to exclude non-vaults — so the module-level
    # function in that loop meant 5N queries on a path that runs on every capture
    # read, behind a blocking latency gate. Measured: a clean gate run went from 0
    # errors to 10 at the same 12% mark when the per-product call landed.
    forms = FormResolver(db, tenant_id)

    # ⚠️ "THIS CUSTOMER" IS THE FUNERAL HOME ON THE ORDER BEING CAPTURED, matched by
    # NAME, because that is what the capture holds. `values["funeral_home"]` is a
    # display name resolved by the extractor; the order rows carry the same name from
    # `customers.name`, which is where the extractor resolved it from.
    home = str(values.get("funeral_home") or "").strip().lower()
    mine = [f for f in facts if (f.funeral_home or "").strip().lower() == home] if home else []
    mine_total = len(mine)

    def column(rows: list, attr: str) -> list[str | None]:
        return [getattr(row, attr, None) for row in rows]

    if field_id == VAULT_FIELD_ID:
        ordered = _habit_then_tenant(
            mine=column(mine, "vault"), mine_total=mine_total,
            everyone=column(facts, "vault"),
        )
        # ⚠️ THE TENANT'S OWN CATALOGUE IS THE TAIL OF LAST RESORT. A tenant with no
        # order history would otherwise offer nothing for its most important question.
        if len(ordered) < MAX_PILLS:
            # ⚠️ THE CATALOGUE FALLBACK ASKS THE FORM, NOT THE NAME, AND A PRODUCTION
            # PROBE IS WHY. This matched `lower(name) LIKE '%vault%'`, which is true of
            # "Vault Placer" — graveside equipment — and offered it at ⌥4 under "Which
            # vault?". `form_of` is the one thing that knows what a product IS.
            #
            # ⚠️ IT STILL READS EVERY ACTIVE PRODUCT RATHER THAN FILTERING IN SQL,
            # because the form is not a column on `products`: it is resolved through a
            # five-step ladder whose first step is a join that reaches nothing today.
            # A SQL filter would have to encode one step of that ladder and would
            # disagree with the other four.
            for (name,) in db.execute(
                text("""SELECT name FROM products
                         WHERE company_id = :t AND is_active
                         ORDER BY name"""),
                {"t": tenant_id},
            ).all():
                if not name or name in ordered:
                    continue
                if forms.form_of(name).form in VAULT_FORMS:
                    ordered.append(name)
        out: list[Pill] = []
        for name in ordered[:MAX_PILLS]:
            form = forms.form_of(name)
            out.append(Pill(value=name, label=name,
                            sub="cremation" if form.is_cremation else None))
        return tuple(_dedupe(out))

    if field_id == "cemetery":
        towns = {
            (f.cemetery or ""): (f.cemetery_city or None)
            for f in facts if f.cemetery
        }
        ordered = _habit_then_tenant(
            mine=column(mine, "cemetery"), mine_total=mine_total,
            everyone=column(facts, "cemetery"),
        )
        if len(ordered) < MAX_PILLS:
            for name, city in db.execute(
                text("""SELECT name, city FROM cemeteries
                         WHERE company_id = :t ORDER BY name"""),
                {"t": tenant_id},
            ).all():
                if name and name not in ordered:
                    ordered.append(name)
                    towns.setdefault(name, city)
        return tuple(_dedupe([
            Pill(value=name, label=name, sub=towns.get(name))
            for name in ordered[:MAX_PILLS]
        ]))

    if field_id == "funeral_home":
        # ⚠️ ONLY CUSTOMERS WHO HAVE ORDERED, AND THAT IS THE FIX FOR WHAT JAMES SAW.
        # The screenshot had "St. Mary's Cemetery" and "Fairview Burial Services" under
        # "Which funeral home?". Both are customers; neither has ever placed an order.
        # They were there because this branch USED to pad the list from every active
        # customer, which is a pad I added and the dispatch never asked for: clause 3
        # says "this customer's usual first… then the tenant's most ordered", and a
        # customer with zero orders is not among the tenant's most ordered at all.
        #
        # ⚠️ IT IS NOT THE `customer_type` FIX AND DOES NOT REPLACE IT. No ruling on
        # `customer_type` has reached me; measured on production, the column is NULL on
        # all five of Sunnycrest's customers, so nothing can tell a funeral home from a
        # cemetery today. Order history is a different discriminator that happens to
        # give the right answer here — Hopkins (3 live orders) and Riverside (1) are the
        # two real funeral homes, and the three with none are a cemetery and two seeds.
        #
        # ⚠️ AND IT HAS A KNOWN COST, STATED RATHER THAN DISCOVERED LATER: a genuinely
        # NEW funeral home has no orders either, so it is not offered until its first
        # one is typed. That is survivable — a name typed in full always works, pills
        # are an accelerator and never the only route — and it is exactly the case the
        # `customer_type` ruling is needed for.
        ordered = _habit_then_tenant(
            mine=[], mine_total=0, everyone=column(facts, "funeral_home"),
        )
        towns: dict[str, str | None] = {}
        funeral_homes: set[str] = set()
        typed_any = False
        for name, city, ctype in db.execute(
            text("SELECT name, city, customer_type FROM customers "
                 "WHERE company_id = :t AND is_active"),
            {"t": tenant_id},
        ).all():
            if not name:
                continue
            towns[name] = city
            if ctype:
                typed_any = True
            if (ctype or "").strip().lower() == FUNERAL_HOME_TYPE:
                funeral_homes.add(name)

        # ⚠️ THE FILTER APPLIES ONLY WHERE THE TENANT HAS SAID SOMETHING. A filter that
        # ignored that would offer ZERO funeral homes on a tenant nobody has classified
        # — turning "nobody has typed these yet" into "none of these is a funeral home".
        #
        # ⚠️ AND MY FIRST VERSION OF THIS COMMENT CLAIMED SUNNYCREST WAS THE ONLY TYPED
        # TENANT. THAT WAS FALSE AND A TEST CONTROL CAUGHT IT. `seed_staging.py` has
        # been setting `customer_type = 'funeral_home'` on the FH-001..FH-005 customers
        # all along, so measured on dev testco is 261 customers, 5 typed funeral_home
        # and 256 NULL — the NULLs being `Fixture …` / `Cert Fixture …` test litter.
        # The real shape is therefore PARTIAL typing, not all-or-nothing, and that is
        # the case the condition has to be right about.
        #
        # ⚠️ IT IS THE SAME NOT_CONFIGURED / NOT_OFFERED DISTINCTION THE AVAILABILITY
        # RESOLVER ALREADY MAKES: an absent key means "nothing constrains this", an
        # explicit value means "this is the constraint". `typed_any` is the
        # key-presence test, read across the tenant rather than per row.
        #
        # ⚠️ STATED COST OF READING IT STRICTLY, which is what James's "funeral homes
        # ONLY" asks for: on a PARTIALLY typed tenant, a real funeral home that has
        # orders but has not been typed drops out of the pills until someone types it.
        # Measured, nobody is in that position today — testco's five typed homes are
        # exactly the five its orders name, and Sunnycrest's Hopkins and Riverside are
        # both typed — but it is the first thing to look at if a licensee reports a
        # missing pill. The name typed in full always works.
        if typed_any:
            ordered = [name for name in ordered if name in funeral_homes]

        # ⚠️ NO PAD, AND THE OMISSION IS THE RULING'S WORDING. "Which funeral home?
        # pills offer funeral homes ONLY" is a restriction, not an instruction to add
        # zero-order funeral homes to the list — and the last time this branch padded
        # from the customer table it was a pad the dispatch never asked for, which is
        # what put St. Mary's under "Which funeral home?" in James's screenshot.
        #
        # ⚠️ STATED COST, UNCHANGED BY THIS RULING: a genuinely new funeral home still
        # has no orders, so it is still not offered until its first one is typed. The
        # type column now makes padding a one-line change if James wants it; this is
        # not that change.
        return tuple(_dedupe([
            Pill(value=name, label=name, sub=towns.get(name))
            for name in ordered[:MAX_PILLS]
        ]))

    if field_id == "service_time":
        ordered = _habit_then_tenant(
            mine=[_hhmm(f.service_time) for f in mine], mine_total=mine_total,
            everyone=[_hhmm(f.service_time) for f in facts],
        )
        return tuple(_dedupe([
            Pill(value=value, label=_spoken_time(value))
            for value in ordered[:MAX_PILLS]
        ]))

    if field.definition.options:
        allowed = None
        if field_id == "cemetery_equipment":
            allowed = _tenant_equipment(db, tenant_id)
            cremation = forms.form_of(values.get(VAULT_FIELD_ID)).is_cremation
            if cremation:
                allowed = {v for v in allowed if v not in BURIAL_ONLY_EQUIPMENT}
        return tuple(_enum_pills(
            field,
            mine=column(mine, field_id), mine_total=mine_total,
            everyone=column(facts, field_id), allowed=allowed,
        )[:MAX_PILLS])

    return ()


def _hhmm(value: object) -> str | None:
    """A stored `time` as `"13:00"`, which is what the field holds."""
    if value is None:
        return None
    text_form = str(value)
    return text_form[:5] if len(text_form) >= 5 else None


def _spoken_time(hhmm: str) -> str:
    """`"13:00"` -> `"1:00 PM"`.

    ⚠️ THE SAME SPLIT AS EVERY OTHER DISPLAY RULE: the server writes it the way the
    office writes it. `rows.write_for_a_human` does this for rows; a pill is not a row,
    so this is the pill's own one line rather than a reach into that module's
    row-shaped API.
    """
    try:
        hour, minute = (int(part) for part in hhmm.split(":")[:2])
    except ValueError:
        return hhmm
    suffix = "AM" if hour < 12 else "PM"
    shown = hour % 12 or 12
    return f"{shown}:{minute:02d} {suffix}"
