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


def load_facts(
    db: Session, company_id: str, *, order_id: str | None = None,
) -> list[OrderFacts]:
    """Every non-cancelled order for this tenant, with the facts the list reads.

    Cancelled orders are excluded in SQL. Invoice, delivery, and proof rows are
    loaded for the ids this query returned, and only for this company.
    """
    sql = """
        SELECT so.id, so.number, so.deceased_name, so.scheduled_date, so.service_time,
               so.status, so.total, so.delivered_at, so.completed_at,
               so.delivered_by_driver_name,
               c.name AS funeral_home,
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
           AND lower(so.status) NOT IN ('cancelled', 'canceled')
    """
    params: dict = {"company_id": company_id}
    if order_id is not None:
        sql += " AND so.id = :order_id"
        params["order_id"] = order_id
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

    chosen = select_flat(facts, question)
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


def _open_decedent(facts: list[OrderFacts], query: str, today: date) -> dict:
    found = [item for item in facts if matches(
        item, OrderQuestion(decedent=query, title="Open orders"),
    )]
    if not found:
        return {"kind": "unrecognized", "hint": f'No order for {_nice(query)}. {TRY_HINT}'}
    if len(found) == 1:
        return {"kind": "open_order", "open_order_id": found[0].id}
    picks = []
    for item in sorted(found, key=lambda row: row.service_date or date.max):
        when = format_when(item.service_date, item.service_time, today)
        label = item.deceased_name or "Unnamed"
        if when.get("date_primary"):
            label = f"{label} · {when['date_primary']}"
        picks.append(Pick(label=label, order_id=item.id))
    return _picks_body(picks, "Which one?")


def sales_order_summary(
    db: Session, company_id: str, order_id: str, today: date,
) -> dict | None:
    found = load_facts(db, company_id, order_id=order_id)
    if not found:
        return None
    facts = found[0]
    when = format_when(facts.service_date, facts.service_time, today)
    service_bits: list[str] = []
    if facts.service_date is not None:
        service_bits.append(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")[facts.service_date.weekday()])
    if when.get("time_label"):
        service_bits.append(str(when["time_label"]))
    cemetery = facts.cemetery or ""
    if facts.cemetery_city:
        cemetery = f"{cemetery}, {facts.cemetery_city}" if cemetery else facts.cemetery_city
    summary: dict = {
        "id": facts.id,
        "number": facts.number,
        "deceased_name": facts.deceased_name or "Unnamed",
        "funeral_home": facts.funeral_home,
        "stands_at": stands_at(facts, today),
    }
    if facts.vault:
        summary["vault"] = facts.vault
    if service_bits:
        summary["service"] = " · ".join(service_bits)
    if cemetery:
        summary["cemetery"] = cemetery
    return summary


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
        facts = load_facts(db, company_id)
        return _open_decedent(facts, interpreted.decedent_query or "", today)

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

    driver_day = False
    if current.is_default and is_driver(role_slug):
        # Drivers do not get the office groups. The default is their own day,
        # including stops already delivered — "going out" would hide those.
        current = _going(today, "today", surface=current.surface)
        current.going_out = False
        current.delivered = None
        current.title = "Going out today"
        driver_day = True
        hint = "Your deliveries."

    facts = load_facts(db, company_id)
    if driver_day:
        facts = [item for item in facts if user_id and user_id in item.assignee_ids]

    if interpreted.kind == "total":
        # "How much is that?" sums what the open view is showing. The default
        # view is three groups, not every order the tenant has ever written.
        if current.is_default:
            grouped = select_default(facts, today)
            chosen = [item for rows in grouped.values() for item in rows]
        else:
            chosen = select_flat(facts, current)
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
