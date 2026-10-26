"""Find the orders a question names, and add up what they come to.

Reads are tenant-scoped off the caller's company. The question is a structured
object from the rules (or a validated model proposal). This module is the only
place a total is computed.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.models.company import Company
from app.services.order_list import cemetery, customer
from app.services.order_list.question import (
    TRY_HINT,
    Interpretation,
    OrderQuestion,
    Pick,
    _going,
    _nice,
    default_question,
    interpret,
    money_for,
    normalize,
    pills_for,
    title_for,
    without_pill,
)
from app.services.order_list.stage import (
    DEFAULT_FOOTER,
    FILTER_FOOTER,
    GROUP_LABEL,
    DeliveryFact,
    OrderFacts,
    ProofFact,
    TaskFact,
    group_order_for,
    is_driver,
    lens_for,
    matches,
    row_dict,
    select_default,
    select_flat,
    stands_at,
    sum_totals,
    total_sentence,
    format_when,
)

SETTING_KEY = "opas_order_list_phrases"
MAX_TAUGHT = 40


def today_for(company: Company | None) -> date:
    """The tenant's local date. A UTC date near midnight is the wrong 'Friday'."""
    name = (company.timezone if company is not None and company.timezone else None) or "UTC"
    try:
        zone = ZoneInfo(name)
    except (KeyError, ValueError):
        zone = ZoneInfo("UTC")
    return datetime.now(zone).date()


def _like(token: str) -> str:
    escaped = token.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def load_taught(db: Session, company_id: str) -> dict:
    company = db.get(Company, company_id)
    if company is None:
        return {}
    raw = company.get_setting(SETTING_KEY)
    return raw if isinstance(raw, dict) else {}


def remember(db: Session, company_id: str, phrase: str, question: OrderQuestion) -> None:
    """Store a corrected phrasing on the company. No new table — `settings_json`."""
    key = normalize(phrase)
    if not key:
        return
    company = db.get(Company, company_id)
    if company is None:
        return
    taught = company.get_setting(SETTING_KEY)
    if not isinstance(taught, dict):
        taught = {}
    taught[key] = question.model_dump(mode="json")
    while len(taught) > MAX_TAUGHT:
        taught.pop(next(iter(taught)))
    company.set_setting(SETTING_KEY, taught)
    db.commit()


def _assignee_kwargs(role_slug: str | None, user_id: str | None) -> dict:
    """A driver is limited to their own deliveries. Everyone else is not."""
    if not is_driver(role_slug):
        return {}
    return {"scope_to_assignee": True, "assignee_id": user_id}


def load_facts(
    db: Session,
    company_id: str,
    *,
    order_id: str | None = None,
    assignee_id: str | None = None,
    scope_to_assignee: bool = False,
    include_cancelled: bool = False,
) -> list[OrderFacts]:
    """Every non-cancelled order for this tenant, with the facts the list reads.

    Cancelled orders are excluded in SQL unless `include_cancelled` is set, which only
    the Sales Order Pane's detail read does — a director typing an old order number or
    clicking a stale link must see "Cancelled" rather than a 404 (James, 2026-10-19:
    "Draft and cancelled show as such, not as steps").

    ⚠️ THE SQL EXCLUSION IS DEFENSIVE, NOT LOAD-BEARING FOR THE LIST, and the difference
    is worth stating because the obvious reading is the other one. Measured by break
    test 2026-10-19: flipping this default to `True` left every list test green. The
    default view is kept clean by `stage.group_of` (`if facts.cancelled … return None`)
    and every filtered question by `stage.matches`, so each of the three guards alone is
    sufficient. What this one buys is independence from the other two — a future list
    path that reached `load_facts` without going through either would still not see a
    cancelled order. Keep it; do not cite it as the reason the list is clean.

    When `scope_to_assignee` is set, the
    same query keeps only orders with a non-cancelled delivery assigned to
    `assignee_id`. A driver with no user id sees nothing. Invoice, delivery,
    and proof rows are loaded for the ids this query returned, and only for
    this company.
    """
    if scope_to_assignee and not assignee_id:
        return []
    sql = """
        SELECT so.id, so.number, so.deceased_name, so.scheduled_date, so.service_time,
               so.status, so.total, so.delivered_at, so.completed_at,
               so.delivered_by_driver_name,
               c.name AS funeral_home,
               so.cemetery_id AS cemetery_id,
               so.customer_id AS customer_id,
               cem.name AS cemetery_name,
               cem.city AS cemetery_city,
               (
                 SELECT COALESCE(p.name, sol.description)
                   FROM sales_order_lines sol
                   LEFT JOIN products p
                     ON p.id = sol.product_id AND p.company_id = so.company_id
                  WHERE sol.sales_order_id = so.id
                  ORDER BY sol.line_total DESC NULLS LAST, sol.sort_order ASC
                  LIMIT 1
               ) AS vault_name
          FROM sales_orders so
          JOIN customers c
            ON c.id = so.customer_id AND c.company_id = so.company_id
          LEFT JOIN cemeteries cem
            ON cem.id = so.cemetery_id AND cem.company_id = so.company_id
         WHERE so.company_id = :company_id
    """
    params: dict = {"company_id": company_id}
    # ⚠️ THE CANCELLED FILTER IS APPENDED RATHER THAN INTERPOLATED INTO THE LITERAL, so
    # the two populations differ by one clause in one place. Written as a conditional
    # inside the f-string it would have been a second WHERE to keep in step.
    if not include_cancelled:
        sql += " AND lower(so.status) NOT IN ('cancelled', 'canceled')\n"
    if order_id is not None:
        sql += " AND so.id = :order_id"
        params["order_id"] = order_id
    if scope_to_assignee:
        sql += """
           AND EXISTS (
             SELECT 1 FROM deliveries d
              WHERE d.company_id = so.company_id
                AND d.order_id = so.id
                AND d.primary_assignee_id = :assignee_id
                AND lower(COALESCE(d.status, '')) NOT IN ('cancelled', 'canceled')
           )
        """
        params["assignee_id"] = assignee_id
    rows = db.execute(text(sql), params).mappings().all()
    if not rows:
        return []

    ids = [row["id"] for row in rows]
    proofs: dict[str, list[ProofFact]] = defaultdict(list)
    tasks: dict[str, list[TaskFact]] = defaultdict(list)
    deliveries: dict[str, list[DeliveryFact]] = defaultdict(list)
    invoices: dict[str, list[str]] = defaultdict(list)

    proof_rows = db.execute(
        text("""
            SELECT lp.order_id, lp.status, lp.family_approved, lp.approved_at,
                   MAX(v.created_at) AS latest_version_at
              FROM legacy_proofs lp
              LEFT JOIN legacy_proof_versions v ON v.legacy_proof_id = lp.id
             WHERE lp.company_id = :company_id AND lp.order_id IN :ids
             GROUP BY lp.id
        """).bindparams(bindparam("ids", expanding=True)),
        {"company_id": company_id, "ids": ids},
    ).mappings().all()
    for proof in proof_rows:
        if proof["order_id"] is None:
            continue
        proofs[proof["order_id"]].append(ProofFact(
            status=proof["status"],
            family_approved=bool(proof["family_approved"]),
            approved_at=proof["approved_at"],
            latest_version_at=proof["latest_version_at"],
        ))

    task_rows = db.execute(
        text("""
            SELECT order_id, task_type, status, approved_at
              FROM order_personalization_tasks
             WHERE company_id = :company_id AND order_id IN :ids
        """).bindparams(bindparam("ids", expanding=True)),
        {"company_id": company_id, "ids": ids},
    ).mappings().all()
    for task in task_rows:
        if task["order_id"] is None:
            continue
        tasks[task["order_id"]].append(TaskFact(
            task_type=task["task_type"],
            status=task["status"],
            approved_at=task["approved_at"],
        ))

    delivery_rows = db.execute(
        text("""
            SELECT order_id, status, primary_assignee_id, requested_date
              FROM deliveries
             WHERE company_id = :company_id AND order_id IN :ids
        """).bindparams(bindparam("ids", expanding=True)),
        {"company_id": company_id, "ids": ids},
    ).mappings().all()
    for delivery in delivery_rows:
        if delivery["order_id"] is None:
            continue
        deliveries[delivery["order_id"]].append(DeliveryFact(
            status=delivery["status"],
            primary_assignee_id=delivery["primary_assignee_id"],
            requested_date=delivery["requested_date"],
        ))

    invoice_rows = db.execute(
        text("""
            SELECT sales_order_id, status
              FROM invoices
             WHERE company_id = :company_id AND sales_order_id IN :ids
        """).bindparams(bindparam("ids", expanding=True)),
        {"company_id": company_id, "ids": ids},
    ).mappings().all()
    for invoice in invoice_rows:
        if invoice["sales_order_id"] is None:
            continue
        invoices[invoice["sales_order_id"]].append(invoice["status"] or "")

    facts: list[OrderFacts] = []
    for row in rows:
        total = row["total"] if isinstance(row["total"], Decimal) else Decimal(str(row["total"] or "0"))
        facts.append(OrderFacts(
            id=row["id"],
            number=row["number"],
            deceased_name=row["deceased_name"],
            funeral_home=row["funeral_home"] or "",
            cemetery_id=row["cemetery_id"],
            customer_id=row["customer_id"],
            cemetery=row["cemetery_name"],
            cemetery_city=row["cemetery_city"],
            vault=row["vault_name"],
            service_date=row["scheduled_date"],
            service_time=row["service_time"],
            total=total,
            status=row["status"] or "",
            delivered_at=row["delivered_at"],
            completed_at=row["completed_at"],
            delivered_by_driver_name=row["delivered_by_driver_name"],
            proofs=proofs.get(row["id"], []),
            tasks=tasks.get(row["id"], []),
            deliveries=deliveries.get(row["id"], []),
            invoice_statuses=invoices.get(row["id"], []),
        ))
    return facts


def subject_kinds(db: Session, company_id: str, token: str) -> list[str]:
    """Which kinds in THIS tenant the token names. Empty means it names nothing."""
    pat = _like(token.strip())
    params = {"c": company_id, "pat": pat}
    found: list[str] = []
    if db.execute(text(
        "SELECT 1 FROM customers WHERE company_id = :c AND name ILIKE :pat LIMIT 1"
    ), params).first():
        found.append("funeral_home")
    if db.execute(text(
        "SELECT 1 FROM cemeteries WHERE company_id = :c AND (name ILIKE :pat OR city ILIKE :pat) LIMIT 1"
    ), params).first():
        found.append("cemetery")
    if db.execute(text("""
        SELECT 1
          FROM sales_order_lines sol
          JOIN sales_orders so ON so.id = sol.sales_order_id
          LEFT JOIN products p ON p.id = sol.product_id AND p.company_id = so.company_id
         WHERE so.company_id = :c
           AND (COALESCE(p.name, '') ILIKE :pat OR sol.description ILIKE :pat)
         LIMIT 1
    """), params).first():
        found.append("vault")
    return found


def bind_subject(db: Session, company_id: str, question: OrderQuestion) -> Interpretation:
    """A name the rules would not classify. One kind is applied. Two kinds are a pick."""
    token = question.unresolved_subject
    if not token:
        return Interpretation(kind="question", question=question)
    kinds = subject_kinds(db, company_id, token)
    if not kinds:
        return Interpretation(
            kind="unrecognized",
            hint=f'Nothing matched “{_nice(token)}”. {TRY_HINT}',
        )
    if len(kinds) == 1:
        question.unresolved_subject = None
        question.subject_hint = None
        setattr(question, kinds[0], token)
        question.about_money = money_for(question)
        question.title = title_for(question)
        return Interpretation(kind="question", question=question)
    labels = {
        "funeral_home": f"{_nice(token)}, the funeral home",
        "cemetery": f"{_nice(token)}, the cemetery",
        "vault": f"{_nice(token)}, the vault",
    }
    picks: list[Pick] = []
    for kind in kinds:
        copy = question.model_copy(deep=True)
        copy.unresolved_subject = None
        copy.subject_hint = None
        setattr(copy, kind, token)
        copy.about_money = money_for(copy)
        copy.title = title_for(copy)
        picks.append(Pick(label=labels[kind], question=copy))
    return Interpretation(kind="picks", picks=picks, hint="Which one?")


def _pack(
    question: OrderQuestion,
    facts: list[OrderFacts],
    today: date,
    role_slug: str | None,
    *,
    hint: str | None = None,
) -> dict:
    if question.is_default:
        grouped = select_default(facts, today)
        order = group_order_for(role_slug)
        groups = []
        flat: list[OrderFacts] = []
        for group_id in order:
            members = grouped[group_id]
            if not members:
                continue
            groups.append({
                "id": group_id,
                "label": GROUP_LABEL[group_id],
                "count": len(members),
                "orders": [row_dict(item, today) for item in members],
            })
            flat.extend(members)
        first_id = next((group_id for group_id in order if grouped[group_id]), None)
        first_rows = grouped[first_id] if first_id is not None else []
        lens = lens_for(
            title=question.title,
            rows=first_rows,
            today=today,
            group_label=GROUP_LABEL[first_id] if first_id is not None else question.title,
            flagged=first_id == "needs_something",
        )
        body: dict = {
            "kind": "question",
            "layout": "grouped",
            "title": question.title,
            "question": question.model_dump(mode="json", exclude_none=True),
            "pills": [],
            "groups": groups,
            "orders": [row_dict(item, today) for item in flat],
            "footer": DEFAULT_FOOTER,
            "lens": lens,
            "surface": question.surface,
        }
        if not flat:
            body["empty"] = "No open orders in these groups."
        if hint:
            body["hint"] = hint
        return body

    chosen = select_flat(facts, question, today)
    totals = sum_totals(chosen, question)
    body = {
        "kind": "question",
        "layout": "flat",
        "title": question.title,
        "question": question.model_dump(mode="json", exclude_none=True),
        "pills": [pill.model_dump() for pill in pills_for(question)],
        "groups": [],
        "orders": [row_dict(item, today) for item in chosen],
        "totals": totals,
        "footer": FILTER_FOOTER,
        "lens": lens_for(title=question.title, rows=chosen, today=today),
        "surface": question.surface,
    }
    if not chosen:
        body["empty"] = "No orders match this question."
    if hint:
        body["hint"] = hint
    return body


def _picks_body(picks: list[Pick], hint: str | None) -> dict:
    out_picks = []
    for index, pick in enumerate(picks, start=1):
        item: dict = {"n": index, "label": pick.label}
        if pick.question is not None:
            item["question"] = pick.question.model_dump(mode="json", exclude_none=True)
        if pick.order_id is not None:
            item["order_id"] = pick.order_id
        out_picks.append(item)
    return {
        "kind": "picks",
        "title": "Which one?",
        "hint": hint or "Which one?",
        "picks": out_picks,
        "layout": "picks",
        "orders": [],
        "groups": [],
        "pills": [],
    }


#: What a bare name is tried against, in order, when opening ONE order.
#:
#: ⚠️ THE ORDER IS THE RULING, AND IT IS NOT ALPHABETICAL. James's opening paths name
#: "the deceased's surname ('smith order')" first and "'<funeral home> order' when
#: there's exactly one match" second. A name that is both — a funeral home called
#: Smith — resolves as the decedent, which is what "smith order" means to the person
#: who typed it while looking at a service sheet.
#:
#: ⚠️ CEMETERY AND VAULT ARE HERE BECAUSE `bind_subject` ALREADY TREATS A BARE NAME AS
#: ONE OF THESE FOUR. Leaving them out would mean "monticello order" opened nothing
#: while "monticello orders" listed them — one trailing letter, two behaviours.
OPEN_ONE_FIELDS: tuple[str, ...] = ("decedent", "funeral_home", "cemetery", "vault")


def _pick_or_open(found: list[OrderFacts], today: date) -> dict:
    """One match opens; several ask. Never a guess.

    ⚠️ THE SAME SHAPE AS THE CATALOG'S NUMBERED PICK, by dispatch: "Several matches ->
    a numbered pick, same as capture's picks (digit selects)". `_picks_body` numbers
    them and the overlay's existing digit handling settles them, so this adds no second
    picking mechanism.
    """
    if len(found) == 1:
        return {"kind": "open_order", "open_order_id": found[0].id}
    picks = []
    for item in sorted(found, key=lambda row: row.service_date or date.max):
        when = format_when(item.service_date, item.service_time, today)
        label = item.deceased_name or "Unnamed"
        # ⚠️ THE NUMBER IS ON THE LABEL, not only the name. Two Hopkins orders for the
        # same week with no decedent recorded would otherwise be two identical choices.
        label = f"{label} · {item.number}"
        if when.get("date_primary"):
            label = f"{label} · {when['date_primary']}"
        picks.append(Pick(label=label, order_id=item.id))
    return _picks_body(picks, "Which one?")


def _open_by_number(facts: list[OrderFacts], suffix: str, today: date) -> dict:
    """Open the order whose number ends in these digits.

    ⚠️ A SUFFIX MATCH, NOT EQUALITY, because "0002" and "SO-2026-0002" are the same
    request (James's first opening path). The tenant's prefix is not reconstructed —
    see `question.order_number_query`.

    ⚠️ AND IT IS STILL A PICK WHEN TWO YEARS COLLIDE. `SO-2025-0002` and `SO-2026-0002`
    both end in "0002"; the digits alone do not say which, so the office is asked rather
    than shown the newer one. Sunnycrest has one year of orders today, so this cannot
    fire there yet — which is exactly why it is written now rather than discovered in
    January.
    """
    wanted = suffix.lstrip("0") or "0"
    hits = [
        item for item in facts
        if (item.number or "").endswith(suffix)
        or (item.number or "").split("-")[-1].lstrip("0") == wanted
    ]
    if not hits:
        return {"kind": "unrecognized", "hint": f"No order numbered {suffix}. {TRY_HINT}"}
    return _pick_or_open(hits, today)


def _open_one(facts: list[OrderFacts], query: str, today: date) -> dict:
    """Open the one order a bare name picks out, over the four fields it could name.

    ⚠️ IT WAS DECEDENT-ONLY UNTIL 2026-10-19, AND THAT IS WHY "riverside order" DID
    NOTHING. The function was `_open_decedent`; it matched `OrderQuestion(decedent=...)`
    and nothing else, so a funeral home's name — which is how the office refers to most
    orders — returned "No order for Riverside". James's own walk for this slice is
    'type "riverside order"', so the narrowness was the first thing it would have hit.

    ⚠️ FIRST FIELD THAT MATCHES ANYTHING WINS, and it does not merge across fields. A
    name matching one decedent and three funeral-home orders opens the decedent's
    rather than asking about four, because the earlier field is the stronger reading.

    ⚠️ LIVE ORDERS FIRST, CANCELLED ONLY IF NOTHING LIVE MATCHES. `matches()` refuses a
    cancelled order by default, which is right for a list and wrong for "open the one
    called X" — Sunnycrest's SO-2026-0002 is cancelled, so "walker order" would have
    reported no such order while the pane is specifically required to be able to show
    one as cancelled. Two passes rather than one so a live order is never buried under a
    cancelled namesake.
    """
    for include_cancelled in (False, True):
        for field in OPEN_ONE_FIELDS:
            question = OrderQuestion(title="Open orders", **{field: query})
            found = [
                item for item in facts
                if matches(item, question, today, include_cancelled=include_cancelled)
            ]
            if found:
                return _pick_or_open(found, today)
    return {"kind": "unrecognized", "hint": f'No order for {_nice(query)}. {TRY_HINT}'}


def sales_order_summary(
    db: Session,
    company_id: str,
    order_id: str,
    today: date,
    *,
    role_slug: str | None = None,
    user_id: str | None = None,
) -> dict | None:
    """The Sales Order Pane's read. Kept at this name; the body moved to `detail.py`.

    ⚠️ IT USED TO BE A FOUR-FACT CARD AND IS NOW THE WHOLE PANE. The old body built
    `id/number/deceased_name/funeral_home/stands_at` plus a `vault`, `service` and
    `cemetery` string. Those keys are all still here, produced by `detail.order_detail`,
    so the tenant-isolation and driver-scoping tests that address this function keep
    testing the thing the route calls.

    ⚠️ ONE IMPLEMENTATION, NOT TWO. Leaving the short body here and adding a second
    detail function would have given the pane and the card two formatters for the same
    cemetery-and-town string, free to drift. `order_detail` is the only one.
    """
    from app.services.order_list.detail import order_detail

    return order_detail(
        db, company_id, order_id, today, role_slug=role_slug, user_id=user_id
    )


def ask(
    db: Session,
    *,
    company_id: str,
    user_id: str | None,
    role_slug: str | None,
    phrase: str | None,
    question: OrderQuestion | None,
    remove_pill_id: str | None,
    teach_phrase: str | None,
    today: date,
    propose=None,
) -> dict:
    """Answer one request. `propose` is the optional model door; None skips it."""
    taught = load_taught(db, company_id)
    hint: str | None = None

    if remove_pill_id and question is not None:
        question = without_pill(question, remove_pill_id)
        interpreted = Interpretation(kind="question", question=question)
    elif phrase:
        interpreted = interpret(phrase, today=today, current=question, taught=taught)
        # ⚠️ A BARE CUSTOMER NAME IS A DETERMINISTIC RULE AND RUNS BEFORE THE MODEL DOOR.
        # "a funeral home name or prefix on its own ('hopkins', 'riverside memorial')
        # opens the pane" (James, 2026-10-24). Rules first is the standing contract, and
        # it matters here beyond tidiness: the model would answer "hopkins" with an
        # order-LIST question for that home, which is a plausible, wrong, and ~900 ms
        # answer to a question the tenant's own customer table settles for free.
        #
        # ⚠️ IT IS ONLY TRIED WHEN THE RULES DECLINED, so nothing that already works
        # changes meaning. "hopkins order" is still `open_order`; "hopkins orders this
        # month" is still a list.
        if interpreted.kind == "unrecognized":
            # ⚠️ THE CEMETERY RULE RUNS FIRST, AND THAT CHANGES A SHIPPED BEHAVIOUR. On
            # sunnycrest "st marys" matches a CEMETERY named "St. Mary's Cemetery" AND a
            # CUSTOMER account of exactly the same name — measured, both resolvers return
            # one hit each. Until today that phrase opened the Customer Pane. It now
            # opens the Cemetery Pane.
            #
            # WHY THAT WAY ROUND. The 2026-10-26 dispatch makes the bar a cemetery
            # entrance and its walk opens with "st marys. The pane opens"; the account
            # stays reachable from an order's funeral-home link, from "the customer", and
            # from any name that is customer-only. The reverse order would make the
            # dispatch's first step fail.
            #
            # ⚠️ THE REVERSAL IS THIS ONE BLOCK MOVING BELOW THE CUSTOMER BLOCK. Written
            # down because the choice is a judgement, not a derivation, and the next
            # person should be able to undo it in one edit rather than re-deriving it.
            #
            # ⚠️ AND THE PLATFORM CANNOT YET TELL THESE ARE ONE SUBJECT. `cemeteries`
            # has a `customer_id` for exactly this — the billing account behind the
            # operational record — and it is NULL on all four cemetery rows. Linked, this
            # would stop being a collision and become one subject with two faces. Worth
            # James's attention; it is data, not code.
            opened = cemetery.open_from_phrase(db, company_id, phrase)
            if opened is not None:
                return opened
            opened = customer.open_from_phrase(db, company_id, phrase)
            if opened is not None:
                return opened
        if interpreted.kind == "unrecognized" and propose is not None:
            proposed = propose(phrase, today, db, company_id)
            if proposed is not None:
                interpreted = proposed
    else:
        interpreted = Interpretation(
            kind="question",
            question=question if question is not None else default_question(),
        )

    if interpreted.kind == "unrecognized":
        return {"kind": "unrecognized", "hint": interpreted.hint or TRY_HINT}

    if interpreted.kind == "open_order":
        # ⚠️ `include_cancelled=True` HERE TOO, so typing a cancelled order's number
        # opens its pane saying "Cancelled" instead of claiming no such order exists.
        # SO-2026-0002 is Sunnycrest's cancelled order and is exactly what a stale note
        # on a desk points at.
        facts = load_facts(
            db, company_id, include_cancelled=True,
            **_assignee_kwargs(role_slug, user_id),
        )
        if interpreted.number_query:
            return _open_by_number(facts, interpreted.number_query, today)
        return _open_one(facts, interpreted.decedent_query or "", today)

    if interpreted.kind == "picks":
        return _picks_body(interpreted.picks, interpreted.hint)

    assert interpreted.question is not None
    current = interpreted.question
    if current.unresolved_subject:
        bound = bind_subject(db, company_id, current)
        if bound.kind != "question":
            return _picks_body(bound.picks, bound.hint) if bound.kind == "picks" else {
                "kind": "unrecognized", "hint": bound.hint or TRY_HINT,
            }
        current = bound.question or current

    if current.is_default and is_driver(role_slug):
        # Drivers do not get the office groups. The default is their own day,
        # including stops already delivered — "going out" would hide those.
        # Every other question is still limited to their deliveries, in SQL.
        current = _going(today, "today", surface=current.surface)
        current.going_out = False
        current.delivered = None
        current.title = "Going out today"
        hint = "Your deliveries."

    facts = load_facts(db, company_id, **_assignee_kwargs(role_slug, user_id))

    if interpreted.kind == "total":
        # "How much is that?" sums what the open view is showing. The default
        # view is three groups, not every order the tenant has ever written.
        if current.is_default:
            grouped = select_default(facts, today)
            chosen = [item for rows in grouped.values() for item in rows]
        else:
            chosen = select_flat(facts, current, today)
        return {
            "kind": "total",
            "hint": total_sentence(chosen),
            "totals": sum_totals(
                chosen,
                current.model_copy(update={"about_money": True, "is_default": False}),
            ),
        }

    if teach_phrase:
        remember(db, company_id, teach_phrase, current)

    return _pack(current, facts, today, role_slug, hint=hint)
