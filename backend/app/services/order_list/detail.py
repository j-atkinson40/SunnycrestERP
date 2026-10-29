"""The Sales Order Pane's read — one order, shortened, as the tables already record it.

⚠️ READ-ONLY. Nothing here writes. The pane's single action (Undo confirm) goes through
`PATCH /sales-orders/{id}`, which already owns that rule.

⚠️ MEASURED FROM `docs/prototypes/2026-10-04-sales-order-pane.html` (81544 bytes, md5
`1fe0b3083812cb92ed0975f8c17c5926`; authored remainder 41096 bytes, md5
`b49d38c664f9d4e253485be7c549a395` — see `PROVENANCE-2026-10-19-sales-order-pane.md`).
The lines this module follows, quoted from that file:

    line 334   return {key:'so',kind:'Sales order',main:true,render:()=>{
    line 330   const s=[['Proof',...],['Scheduled',...],['Delivered',''],['Invoiced','']];
               <div class="ttl dec">${esc(O.dec)}</div>
               <div class="meta">${O.id} · <button class="lnk" data-a="fh">${O.fh}</button></div>
               kv rows: Vault (data-a="prod") · Personalization (data-a="proof")
                        Cemetery (data-a="cem") `${O.cem}, ${O.town}` · `${O.plot}`
                        Service `Fri Oct 2 · ${O.time} AM graveside` · Delivery
                        Equipment · Total
               tabs:    S.push(['bill','Billing',…]) ; S.push(['hist','History',HIST.length,…])
               billing: "Not invoiced yet. It goes out at month end with the October
                         statement. Hopkins is Net 30"

⚠️ WHERE THIS DEPARTS FROM THE PROTOTYPE, AND WHY — THREE PLACES, ALL BY DISPATCH:

  * **The steps.** The prototype's four are `Proof -> Scheduled -> Delivered -> Invoiced`.
    The dispatch (James, 2026-10-19) specifies `Confirmed -> Delivered -> Invoiced`, and
    adds "Draft and cancelled show as such, not as steps". The prototype predates the
    confirm step — it was last updated 2026-10-04 and Approve began confirming orders on
    2026-10-16 — so it has `Confirmed` 0 times and `Undo confirm` 0 times. The dispatch
    wins on the state vocabulary; the prototype wins on look and layout.
  * **No Delivery row.** The prototype's kv list has one. The dispatch's list is Vault,
    Personalization, Cemetery, Service, Equipment, Total — Delivery is not on it, and
    `deliveries` has 0 rows for Sunnycrest anyway (measured 2026-10-19).
  * **No "Net 30".** The prototype's billing sentence ends "Hopkins is Net 30".
    `customers.payment_terms` is NULL on all 5 Sunnycrest customers and on all 22
    platform-wide (measured 2026-10-19), so that clause would be invented. Omitted.

⚠️ WHAT RENDERS FOR NOTHING TODAY, STATED SO IT IS NOT MISTAKEN FOR COVERAGE. Measured on
production 2026-10-19:

    Personalization row     0 rows in `order_personalization_tasks` for Sunnycrest, and
                            `products.has_personalization` is False on all 10. Coded;
                            renders for no order today.
    "Invoiced after delivery"  all 22 customers platform-wide are `statement_only`. The
                            other branch is coded and unreachable with today's data.
    Cemetery ETA            `sales_orders.eta` is NULL on all 3 orders. The clause only
                            appears for a non-graveside service that carries one.
    Vault link              `products.variant_template_id` is NULL on all 39 products,
                            every tenant — so the order LINE carries no catalog link and
                            the link is resolved from the line's NAME instead (below).
"""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.services.capture.schema import EQUIPMENT_PACKAGES
from app.services.order_list.stage import (
    STATUS_LABEL,
    OrderFacts,
    format_money,
    stage_of,
    stands_at,
)
from app.services.display_name import UNNAMED, deceased_for_display, title_case_for_display

_MON = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_DOW = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MONTH_FULL = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)

#: Equipment package labels, lower-cased, from the capture schema's own list.
#:
#: ⚠️ DERIVED, NOT RETYPED. `EQUIPMENT_PACKAGES` is the single source for what the capture
#: can answer and what `approval.assess` names an equipment line, so a package added there
#: is classified here without a second edit. `none` is excluded — it means "no equipment"
#: and never becomes a line.
EQUIPMENT_LABELS: frozenset[str] = frozenset(
    label.strip().casefold() for slug, label in EQUIPMENT_PACKAGES if slug != "none"
)


def is_equipment_line(description: str | None) -> bool:
    """True when this line is one of the capture's equipment packages."""
    return (description or "").strip().casefold() in EQUIPMENT_LABELS


def split_lines(lines: list[dict]) -> tuple[dict | None, list[dict], list[dict]]:
    """`(vault_line, equipment_lines, other_lines)`.

    The vault is the most expensive NON-equipment line.

    ⚠️ `load_facts` ANSWERS THE SAME QUESTION DIFFERENTLY, AND THE DIVERGENCE IS RECORDED
    RATHER THAN HIDDEN. Its SQL subquery takes the highest `line_total` across ALL lines,
    equipment included (`service.py`, `vault_name`), so an order whose equipment cost more
    than its vault would show the equipment as the list row's vault and the vault here.
    No such order exists on production (measured 2026-10-19: every order's vault line is
    $1,250–$1,405 against $300 of equipment). Narrowing the SQL would change what the
    LIST shows, which this dispatch does not touch.
    """
    equipment = [l for l in lines if is_equipment_line(l.get("description"))]
    others = [l for l in lines if not is_equipment_line(l.get("description"))]
    vault = max(others, key=lambda l: l.get("line_total") or Decimal("0"), default=None)
    rest = [l for l in others if l is not vault]
    return vault, equipment, rest


def format_day(value: date | None) -> str | None:
    """`date(2026,10,23)` -> `'Fri Oct 23'`."""
    if value is None:
        return None
    return f"{_DOW[value.weekday()]} {_MON[value.month - 1]} {value.day}"


def format_clock(value: time | None) -> str | None:
    """`time(11,0)` -> `'11:00 AM'`.

    ⚠️ WITH THE MERIDIEM, UNLIKE THE LIST ROW. `stage.format_when` returns a bare
    `'11:00'` because a list row is read beside a weekday and the hour is unambiguous in
    context. On the pane it is the only time on screen, and "11:00" for a 23:00 service
    would be wrong rather than terse.
    """
    if value is None:
        return None
    hour = value.hour % 12 or 12
    meridiem = "AM" if value.hour < 12 else "PM"
    return f"{hour}:{value.minute:02d} {meridiem}"


#: `service_location` -> how the pane says it. Measured in use platform-wide 2026-10-19:
#: NULL ×37, `church` ×2, `graveside` ×1.
SERVICE_LOCATION_LABEL: dict[str, str] = {
    "graveside": "graveside",
    "church": "church",
    "chapel": "chapel",
    "funeral_home": "at the funeral home",
    "other": "",
}

GRAVESIDE = "graveside"


def service_sentence(facts: OrderFacts, *, location: str | None,
                     location_other: str | None, eta: time | None) -> str | None:
    """"Fri Oct 23 · 11:00 AM church · at the cemetery 12:30 PM".

    Per the dispatch: "Service (day, time, graveside or where, with the cemetery ETA if
    not graveside)". A graveside service IS at the cemetery, so an ETA there would be the
    same clock twice.
    """
    bits: list[str] = []
    day = format_day(facts.service_date)
    if day:
        bits.append(day)
    clock = format_clock(facts.service_time)
    where = (location or "").strip().casefold()
    label = SERVICE_LOCATION_LABEL.get(where, where)
    if where == "other" and (location_other or "").strip():
        label = (location_other or "").strip()
    second = " ".join(part for part in (clock, label) if part)
    if second:
        bits.append(second)
    if where and where != GRAVESIDE and eta is not None:
        bits.append(f"at the cemetery {format_clock(eta)}")
    return " · ".join(bits) or None


def billing_sentence(
    db: Session,
    company_id: str,
    *,
    customer_name: str,
    preference: str | None,
    invoiced: bool,
    service_date: date | None,
    today: date,
) -> str:
    """The real invoicing line, from the customer's own setting.

    Two shapes, per the dispatch: "Invoiced at month end with the <Month> statement" or
    "Invoiced after delivery", "honest about sending being off".

    ⚠️ THE MONTH IS THE SERVICE MONTH, NOT THIS MONTH. An order for next Friday bills on
    next Friday's statement; saying "the October statement" for a November service would
    be wrong for every order written in the last week of a month.

    ⚠️ THE SEND SWITCH IS CONSULTED HERE TOO, through the same
    `invoice_email_allowed` the Review's promise uses. A customer set to
    `invoice_immediately` must not read as "emailed" while the tenant switch is off —
    `approval._describe_billing` already makes that distinction and this is the second
    place the office sees the claim, so it has to agree.
    """
    pref = (preference or "statement_only").strip()
    short = (customer_name or "").split()[0] if customer_name else "this customer"

    if pref in ("invoice_immediately", "both"):
        from app.services.invoice_email_switch import invoice_email_allowed

        allowed, _why = invoice_email_allowed(db, company_id)
        after = "Invoiced after delivery"
        if allowed:
            return (
                f"{after}, and emailed to {short}." if not invoiced
                else f"Invoiced. {short} is billed after delivery and emailed."
            )
        return (
            f"{after}. Nothing is emailed — sending is off for this tenant."
            if not invoiced
            else f"Invoiced. Nothing was emailed — sending is off for this tenant."
        )

    month = _MONTH_FULL[(service_date or today).month - 1]
    if invoiced:
        return f"Invoiced. It goes out with the {month} statement."
    return f"Not invoiced yet. It goes out at month end with the {month} statement."


def steps_for(facts: OrderFacts) -> dict:
    """`Confirmed -> Delivered -> Invoiced`, or the state instead of steps.

    ⚠️ THE PROTOTYPE'S FOUR ARE `Proof -> Scheduled -> Delivered -> Invoiced` (line 330).
    The dispatch specifies three and the two different first steps, so this is the one
    place the prototype is deliberately not followed. See the module docstring.

    ⚠️ CANCELLED AND DRAFT ARE NOT STEP ZERO. "Draft and cancelled show as such, not as
    steps" — a draft rendered as an unfilled `Confirmed` would read as an order on its way
    somewhere, and a cancelled one as an order that merely has not got there yet.
    """
    if facts.cancelled:
        return {"kind": "cancelled", "label": STATUS_LABEL["cancelled"]}
    if facts.draft:
        # ⚠️ READ OFF `OrderFacts.draft` SINCE 2026-10-23 rather than spelt here. This
        # function was the only place in the codebase that knew what a draft was, and
        # the list row's label did not — so the pane said "Draft" and the row beside it
        # said "Scheduled" about the same order. One property, one answer.
        return {"kind": "draft", "label": STATUS_LABEL["draft"]}
    return {
        "kind": "steps",
        "steps": [
            # Past draft is confirmed, by the transition graph: nothing reaches any later
            # status without passing through `confirmed`.
            {"id": "confirmed", "label": "Confirmed", "done": True},
            {"id": "delivered", "label": "Delivered", "done": facts.delivered},
            {"id": "invoiced", "label": "Invoiced", "done": facts.invoiced},
        ],
        "stage": stage_of(facts),
    }


def _lines_for(db: Session, company_id: str, order_id: str) -> list[dict]:
    rows = db.execute(
        text("""
            SELECT sol.description, sol.quantity, sol.unit_price, sol.line_total,
                   sol.sort_order
              FROM sales_order_lines sol
              JOIN sales_orders so ON so.id = sol.sales_order_id
             WHERE sol.sales_order_id = :o AND so.company_id = :c
             ORDER BY sol.sort_order ASC, sol.description ASC
        """),
        {"o": order_id, "c": company_id},
    ).mappings().all()
    return [dict(r) for r in rows]


def _personalization_for(db: Session, company_id: str, order_id: str) -> list[dict]:
    rows = db.execute(
        text("""
            SELECT task_type, status, print_name, symbol, inscription_name,
                   inscription_dates, is_custom_legacy
              FROM order_personalization_tasks
             WHERE company_id = :c AND order_id = :o
             ORDER BY created_at ASC NULLS LAST
        """),
        {"c": company_id, "o": order_id},
    ).mappings().all()
    return [dict(r) for r in rows]


#: Audit actions the History tab renders, with the word it shows.
#:
#: ⚠️ ONLY `created` CARRIES DETAIL. Measured on production 2026-10-19: Sunnycrest has 3
#: `created` rows (all with a `changes` JSON naming the number, the total, and
#: `source: opas_capture`) and 2 `updated` rows with `changes` NULL —
#: `sales_service.update_sales_order` calls `log_action` without a `changes` argument. So
#: an "Updated" entry can say who and when and nothing about WHAT, and the tab says that
#: rather than implying more.
AUDIT_WORD: dict[str, str] = {
    "created": "Created",
    "updated": "Updated",
    "deleted": "Deleted",
}

#: What the pane prints beside an `updated` row, because the row itself records no fields.
NO_DETAIL_NOTE = "no fields recorded"


def _history_for(db: Session, company_id: str, order_id: str) -> list[dict]:
    """The audit trail for this order, newest last. `[]` means the tab is left out."""
    rows = db.execute(
        text("""
            SELECT a.action, a.changes, a.actor_type, a.created_at, u.email, u.first_name,
                   u.last_name
              FROM audit_logs a
              LEFT JOIN users u ON u.id = a.user_id
             WHERE a.company_id = :c
               AND a.entity_type = 'sales_order'
               AND a.entity_id = :o
             ORDER BY a.created_at ASC
        """),
        {"c": company_id, "o": order_id},
    ).mappings().all()

    out: list[dict] = []
    for row in rows:
        entry: dict = {"action": AUDIT_WORD.get(row["action"], row["action"] or "Changed")}
        who = " ".join(
            part for part in (row["first_name"], row["last_name"]) if part
        ).strip() or (row["email"] or "")
        if who:
            entry["who"] = who
        if row["created_at"] is not None:
            entry["when"] = row["created_at"].isoformat()
        detail = _history_detail(row["changes"])
        if detail:
            entry["detail"] = detail
        else:
            entry["detail_absent"] = NO_DETAIL_NOTE
        out.append(entry)
    return out


#: `changes` keys the History line reads, and how it words them.
_CHANGE_SOURCE = {"opas_capture": "from Opas capture"}


def _history_detail(raw: object) -> str | None:
    """"$1,705.00 · from Opas capture" from the `changes` JSON, or None.

    ⚠️ `changes` IS A TEXT COLUMN HOLDING JSON, so it is parsed rather than subscripted,
    and a value that is not JSON produces None rather than an exception on a read path.
    """
    if not raw:
        return None
    import json

    try:
        parsed = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
    except (ValueError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None
    bits: list[str] = []
    total = parsed.get("total")
    if total is not None:
        money = format_money(str(total))
        if money:
            bits.append(money)
    source = parsed.get("source")
    if isinstance(source, str) and source:
        bits.append(_CHANGE_SOURCE.get(source, source.replace("_", " ")))
    return " · ".join(bits) or None


def _vault_link(db: Session, description: str | None) -> str | None:
    """The platform variant this vault line names, when the name reaches exactly one.

    ⚠️ THIS IS THE ONLY ROUTE TO THE PRODUCT PANE, AND IT GOES THROUGH THE NAME BECAUSE
    THERE IS NO LINK IN THE DATA. `products.variant_template_id` is NULL on all 39
    products across all tenants (measured 2026-10-19; `approval.py` records the same for
    2026-10-13), so a sales order line has nothing pointing at the platform catalog. The
    line's NAME does — through `product_name_resolver`, which is the same resolver the
    command line itself uses, so there is one set of matching rules rather than two.

    ⚠️ EXACTLY ONE CANDIDATE, OR NO LINK. Measured 2026-10-19 over Sunnycrest's catalogue:
    `Monticello Burial Vault` resolves to 1 (`8a3c6253-…`), `Continental Burial Vault` to
    2 differing by size, and the 8 equipment and urn names to 0. An ambiguous name gets no
    link rather than an arbitrary one — the same rule the bar follows, where several
    matches become a numbered pick and never a guess.
    """
    if not (description or "").strip():
        return None
    try:
        from app.services.product_name_resolver import build_index, resolve

        resolution = resolve(build_index(db), description or "")
    except Exception:  # pragma: no cover - a read path must not fail on the resolver
        return None
    if len(resolution.candidates) != 1:
        return None
    return resolution.candidates[0].variant_template_id


def _row(label: str, value: str | None, **extra) -> dict | None:
    """One kv row, or None when the fact is absent.

    ⚠️ ABSENT ROWS ARE ABSENT — "Optional empty rows hidden, the same rule as capture"
    (dispatch), which is also `ProductPane`'s rule. A dash or an "—" would read as a
    measured emptiness rather than as nothing having been recorded.
    """
    if not value:
        return None
    return {"label": label, "value": value, **extra}


def _order_extras(db: Session, company_id: str, order_id: str) -> dict | None:
    """The detail-only columns, and the customer's billing setting.

    ⚠️ A SECOND QUERY RATHER THAN WIDER `OrderFacts`. `load_facts` feeds the LIST, where
    every row pays for every column it selects; `service_location`, `eta`,
    `grave_location` and the customer's invoice preference are read by this pane and
    nothing else. Widening the shared dataclass would put four unused fields on every
    list row and give the list a second reason to change when the pane does.
    """
    row = db.execute(
        text("""
            SELECT so.status, so.service_location, so.service_location_other, so.eta,
                   so.grave_location, so.customer_id,
                   c.name AS customer_name, c.invoice_delivery_preference
              FROM sales_orders so
              LEFT JOIN customers c
                ON c.id = so.customer_id AND c.company_id = so.company_id
             WHERE so.id = :o AND so.company_id = :c
        """),
        {"o": order_id, "c": company_id},
    ).mappings().first()
    return dict(row) if row is not None else None


def order_detail(
    db: Session,
    company_id: str,
    order_id: str,
    today: date,
    *,
    role_slug: str | None = None,
    user_id: str | None = None,
) -> dict | None:
    """The whole pane, or None when this is not the caller's order.

    ⚠️ CANCELLED ORDERS ARE READABLE HERE AND NOT IN THE LIST. The dispatch says
    "Draft and cancelled show as such", so the pane has to be able to open one — and
    SO-2026-0002 is Sunnycrest's cancelled order, which is exactly what a director
    clicking a stale link or typing an old number will reach. `load_facts` excludes
    cancelled rows in SQL for the list, by design, so the pane passes
    `include_cancelled=True` rather than the list dropping its filter.
    """
    from app.services.order_list.service import _assignee_kwargs, load_facts

    found = load_facts(
        db,
        company_id,
        order_id=order_id,
        include_cancelled=True,
        **_assignee_kwargs(role_slug, user_id),
    )
    if not found:
        return None
    facts = found[0]
    extras = _order_extras(db, company_id, order_id)
    if extras is None:  # pragma: no cover - load_facts already proved the row exists
        return None

    lines = _lines_for(db, company_id, order_id)
    vault_line, equipment_lines, _other = split_lines(lines)
    personalization = _personalization_for(db, company_id, order_id)

    cemetery = facts.cemetery or ""
    if facts.cemetery_city:
        cemetery = f"{cemetery}, {facts.cemetery_city}" if cemetery else facts.cemetery_city

    # ── "The order" ────────────────────────────────────────────────────────
    # ⚠️ IN THE DISPATCH'S ORDER: Vault, Personalization, Cemetery, Service, Equipment,
    # Total. Absent rows drop out below rather than rendering empty.
    vault_value = (vault_line or {}).get("description")
    variant_id = _vault_link(db, vault_value) if vault_value else None
    rows = [
        _row(
            "Vault", vault_value,
            **({"link": {"kind": "product", "variant_template_id": variant_id}}
               if variant_id else {}),
        ),
        _row("Personalization", _personalization_value(personalization)),
        _row(
            "Cemetery", cemetery or None,
            # ⚠️ LIVE AS OF 2026-10-26, AND IT NEEDED AN ID RATHER THAN A DECISION. This
            # shipped as `{"kind": "cemetery", "inert": True, "why": "The cemetery pane
            # isn't built yet."}` — honest, and unbuildable while `OrderFacts` carried
            # the cemetery's NAME and TOWN but no way back to the row. `facts.cemetery_id`
            # is what retired the tooltip.
            #
            # ⚠️ AND IT IS STILL CONDITIONAL ON THE ID, not on the name. `_order_extras`
            # LEFT JOINs, so an order can name a cemetery the join did not resolve; the
            # pane then renders plain text rather than a button that 404s.
            **({"link": {
                "kind": "cemetery",
                "cemetery_id": facts.cemetery_id,
            }} if cemetery and facts.cemetery_id else {}),
        ),
        _row(
            "Service",
            service_sentence(
                facts,
                location=extras["service_location"],
                location_other=extras["service_location_other"],
                eta=extras["eta"],
            ),
        ),
        _row("Grave", extras["grave_location"]),
        _row("Equipment", " · ".join(
            str(l["description"]) for l in equipment_lines if l.get("description")
        ) or None),
        _row("Total", format_money(f"{facts.total:.2f}")),
    ]

    detail: dict = {
        # ── the existing summary keys, unchanged. `OrderListPane` reads `stands_at` and
        #    the three short facts beside the list; the pane's extra keys are additive so
        #    that read keeps working.
        "id": facts.id,
        "number": facts.number,
        # ⚠️ RAW ON PURPOSE, AND IT IS NOT A MISS. The Sales Order Pane displays
        # `title` (SalesOrderPane.tsx:229 renders `row.title`); this key carries the
        # name AS STORED and `test_sales_order_pane.py` pins it with its own message,
        # "the raw name stopped being carried". Title-casing it was tried on
        # 2026-10-29 while fixing the display bug and reverted — the 2026-10-15
        # ruling is about what is DISPLAYED, and nothing displays this.
        "deceased_name": facts.deceased_name or UNNAMED,
        "funeral_home": facts.funeral_home,
        # ⚠️ THE ID, SO THE NAME CAN BE A LINK (James, 2026-10-24: "Right now the funeral
        # home link on an order goes nowhere"). `funeral_home` above is the NAME and is
        # kept — the pane renders it, and the reply line says it. Opening the Customer
        # Pane needs the account's id, and resolving a name back to an account in the
        # client would be the name-matching this pane already has the key for.
        #
        # ⚠️ ABSENT WHEN THE ORDER HAS NO CUSTOMER ROW, which `_order_extras` already
        # tolerates with a LEFT JOIN. The frontend renders plain text in that case
        # rather than a link that cannot resolve.
        **({"customer_id": extras["customer_id"]} if extras.get("customer_id") else {}),
        "stands_at": stands_at(facts, today),
        # ── the pane ──────────────────────────────────────────────────────
        "title": deceased_for_display(facts.deceased_name),
        "state": steps_for(facts),
        "order": [r for r in rows if r is not None],
        "billing": {
            "lines": [
                {
                    "description": l["description"],
                    "quantity": _plain(l["quantity"]),
                    "unit_price": format_money(f"{Decimal(str(l['unit_price'] or 0)):.2f}"),
                    "line_total": format_money(f"{Decimal(str(l['line_total'] or 0)):.2f}"),
                }
                for l in lines
            ],
            "total": format_money(f"{facts.total:.2f}"),
            "sentence": billing_sentence(
                db, company_id,
                customer_name=extras["customer_name"] or facts.funeral_home,
                preference=extras["invoice_delivery_preference"],
                invoiced=facts.invoiced,
                service_date=facts.service_date,
                today=today,
            ),
        },
        # ⚠️ TRUE ONLY FOR A CONFIRMED ORDER, AND IT DOES NOT PRE-JUDGE THE REST. The rule
        # has two halves — the graph (`confirmed -> draft` is permitted in shape) and the
        # per-order blocker (not delivered, no live invoice) — and the SERVER owns the
        # second half. `sales-orders.tsx` takes the same line: show the control, let the
        # PATCH refuse with the sentence that names the remedy. A read that pre-computed
        # the blocker would be a second copy of the rule, free to disagree with the one
        # that actually decides.
        "can_undo_confirm": (facts.status or "").strip().casefold() == "confirmed",
    }
    if facts.vault:
        detail["vault"] = facts.vault
    service = service_sentence(
        facts, location=extras["service_location"],
        location_other=extras["service_location_other"], eta=extras["eta"],
    )
    if service:
        detail["service"] = service
    if cemetery:
        detail["cemetery"] = cemetery
    if extras["customer_id"]:
        detail["customer_id"] = extras["customer_id"]

    history = _history_for(db, company_id, order_id)
    # ⚠️ THE KEY IS OMITTED WHEN THE TRAIL IS EMPTY, AND THE PANE LEAVES THE TAB OUT —
    # "if none, say so and leave the tab out rather than faking it" (dispatch). An empty
    # History tab would be a tab that promises a record and shows none.
    if history:
        detail["history"] = history
    return detail


def _personalization_value(tasks: list[dict]) -> str | None:
    """What the Personalization row says, or None so the row is absent.

    ⚠️ RENDERS FOR NO ORDER ON PRODUCTION TODAY. `order_personalization_tasks` holds 0
    rows for Sunnycrest and `products.has_personalization` is False on all 10 of its
    products (measured 2026-10-19). Coded because the capture writes this table on every
    approve that chose a substrate — see `session_service._write_personalization_tasks` —
    so the first personalised order will fill it.
    """
    if not tasks:
        return None
    bits: list[str] = []
    for task in tasks:
        label = str(task.get("task_type") or "").replace("_", " ").strip()
        if not label:
            continue
        pieces = [label[:1].upper() + label[1:]]
        if task.get("print_name"):
            pieces.append(f"“{task['print_name']}”")
        elif task.get("inscription_name"):
            pieces.append(f"“{title_case_for_display(str(task['inscription_name']))}”")
        if task.get("symbol"):
            pieces.append(str(task["symbol"]).replace("_", " "))
        bits.append(" ".join(pieces))
    return " · ".join(bits) or None


def _plain(value: object) -> str:
    """`Decimal('1.0000')` -> `'1'`; `Decimal('12.5000')` -> `'12.5'`.

    Quantities are `Numeric(12,4)`, so every one of them renders as `1.0000` unless the
    trailing zeros are dropped. The prototype shows bare counts.
    """
    try:
        d = Decimal(str(value))
    except (ValueError, TypeError, ArithmeticError):
        return str(value)
    normalized = d.normalize()
    if normalized == normalized.to_integral():
        return str(normalized.to_integral())
    return format(normalized, "f")
