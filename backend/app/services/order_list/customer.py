"""The Customer Pane's read, and the rule that opens it from a bare name.

James's dispatch of 2026-10-24, "Customer Pane, slice 1". Read-only on real data; no
migration. Built from the prototype (artifact `3ca35d0b-c93a-4924-8cb2-32772fa49876`,
"Customer Pane", updated 2026-10-04 — fetched 77,121 bytes, md5
`dd76be20c2c1f19e8fd6c036b56e6c15` of the page INCLUDING the artifact-runtime wrapper,
of which 36,104 chars are the author's own source).

⚠️ THE SHORT URL IN THE DISPATCH DOES NOT RESOLVE AND THE ID DOES. The dispatch cited
`claude.ai/artifact/8VJ9XsfWhLayikmLDx3vcM`; the artifact listing has it at
`claude.ai/code/artifact/3ca35d0b-…`, which is the id the dispatch also gave. CLAUDE.md
asks dispatches to cite only sources the executor can reach, and this one was reachable
only through the id — which is the argument for always including it.

THE PROTOTYPE LINES THIS FOLLOWS, quoted:

    .ttl    `<div class="ttl">${FH.name}</div>`
    .meta   `<div class="meta">Funeral home · ${FH.addr}, ${FH.city} · ${FH.director}, director</div>`
    action  `<button class="btn primary" data-a="neworder">New order</button>`
    rows    `<div class="sech"><span>Open orders</span><span>${ORDERS.length}</span></div>`
            `<span class="a"><span class="mono">${o.id.slice(-4)}</span>${o.who}</span>`
            `<span class="b">${o.what} · ${o.when}</span>`
            `<span class="c${o.st==='No driver'?' neg':''}">${o.st}</span>`
    account `<div class="line">$5,810 balance · <span class="neg">$1,590 past due</span> · Net 30 · …`
    tabs    `S.push(['people','People',PEOPLE.length, …])`
            `S.push(['recent','Recent',RECENT.length, …])`
            `S.push(['knows','What Opas knows','', …])`
    knows   `<span>Usual vault</span><span>Monticello 51% · Venetian 23% · Continental 13%</span>`
            `<span>Usual cemeteries</span><span>St. Mary's · Lake View</span>`

⚠️ LEFT OUT BY RULING, NOT BY OVERSIGHT (James, 2026-10-24): the "Right now" offers, the
contact flow, presenting mode, and the Office/Driver/Accounting views. Also dropped from
"What Opas knows": its `Setup photo`, `Best reached by` and alias rows — none is
derivable from orders, and the ruling is "only worked out from real orders".

⚠️ AND THE DISPATCH OVERRIDES THE PROTOTYPE ON ONE LINE, which is recorded here because
CLAUDE.md §12 says spec beats canon and the prototype is neither. The prototype shows
`Monticello 51%`; the dispatch says "each with its count ('Monticello · 2 of 3
orders')" and "with fewer than 3 orders, say 'Not enough orders yet' instead of a
percentage". The counts are what ship. A percentage over two orders reads as a finding
and is an arithmetic accident.

⚠️ MEASURED BEFORE BUILDING, AND IT CHANGES WHAT THIS PANE CAN SHOW. On production every
one of `customer_type`, `address_line1`, `city`, `state`, `contact_name`, `payment_terms`
and `phone` is NULL for all five of Sunnycrest's customers; the `company_entities` rows
exist with no address and every flag False; and `contacts` holds ZERO rows for the
tenant. So the meta line renders as nothing and the People tab is absent — which is the
dispatch's own rule ("missing fields are left out, never shown as blank labels") doing
its job, not a defect. Reported rather than worked around: the remedy is data.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.capture.prefix_resolve import GENERIC_WORDS, MIN_PREFIX, reaches
from app.services.order_list.stage import (
    GROUP_LABEL,
    OrderFacts,
    format_money,
    format_when,
    is_overdue,
    sort_key,
    status_label,
)

#: Fewer than this many orders and the rulebook says so instead of counting.
#:
#: ⚠️ JAMES'S NUMBER, AND IT MEANS THE FEATURE SAYS NOTHING ON TODAY'S DATA. Measured on
#: production: Hopkins has 2 non-cancelled orders and Riverside 1, so every customer
#: reads "Not enough orders yet". That is the honest output of a tenant with four orders,
#: and it is also the argument for the pane — the counts fill as Opas gets used.
MIN_ORDERS_FOR_HABITS = 3

#: How many habits a line shows.
#:
#: ⚠️ THE PROTOTYPE'S OWN NUMBER, WHICH IS WHY IT IS NOT MY INVENTION. Its line reads
#: `Monticello 51% · Venetian 23% · Continental 13%` — three. Measured on testco, where
#: Johnson Funeral Home has 10 orders across 5 different vaults, the uncapped line read
#: "Bronze Triune · 1 of 10 orders · Cameo Rose · 1 of 10 orders · Continental · 1 of 10
#: orders · Monticello · 1 of 10 orders · Venetian · 1 of 10 orders" — five entries, not
#: one of them a habit. A "usual vault" that lists everything once is a census.
#:
#: ⚠️ AND IT DOES NOT ANSWER THE REAL QUESTION, WHICH IS JAMES'S: whether a 1-of-10
#: belongs on a line headed "Usual vault" at all. Capping stops the line running away;
#: it does not decide what counts as usual. Reported rather than ruled on here.
MAX_HABITS = 3

NOT_ENOUGH = "Not enough orders yet"
NO_INVOICES = "No invoices yet"

#: ⚠️ CANCELLED ORDERS DO NOT TEACH A HABIT, and this is a judgement the dispatch did not
#: make for me. Every list in this module excludes them, "2 of 3 orders" reads as a count
#: of real orders, and an order the home cancelled is weak evidence of what they usually
#: want. Stated because it moves Hopkins from 3 orders to 2 and therefore under the
#: threshold above — the single most visible consequence in the whole pane.
_CANCELLED = frozenset({"cancelled", "canceled"})


def _nice_kind(raw: str | None) -> str | None:
    """`funeral_home` -> `Funeral home`. None stays None."""
    if not raw:
        return None
    return raw.replace("_", " ").strip().capitalize() or None


def _nice_terms(raw: str | None) -> str | None:
    """`net_30` -> `Net 30`. None stays None.

    ⚠️ FOUND BY WALKING THE ROUTE OVER HTTP ON DATA-RICH testco, WHICH PRODUCTION COULD
    NOT SHOW ME. Sunnycrest stores no terms at all, so the line read "$0 balance" there
    and looked finished. testco stores `net_30`, and the account line rendered
    "$0 balance · net_30" — a database token on the office's screen. The prototype says
    `Net 30`.

    ⚠️ SENTENCE CASE, NOT TITLE CASE, AND MY FIRST VERSION GOT IT WRONG. Capitalising
    every word turned `due_on_receipt` into "Due On Receipt" — a mid-phrase "On" that
    reads like a brand. These are phrases, not headings.

    ⚠️ A LONE SHORT ACRONYM SURVIVES; A SHOUTED PHRASE DOES NOT. My second attempt kept
    any all-caps token under five characters, which turned `DUE_ON_RECEIPT` into "DUE ON
    receipt" — "DUE" and "ON" preserved, "RECEIPT" lowered. Per-token rules cannot tell
    an acronym from a shouted word, so the decision is made about the WHOLE value: one
    short word stays as stored ("COD", "EOM"), anything longer is a phrase and gets
    sentence case. A lowercase "cod" becomes "Cod" — what the database says, sentence
    cased; reading it as an acronym would be inventing a fact about the tenant's data.
    """
    if not raw:
        return None
    words = raw.replace("_", " ").split()
    if not words:
        return None
    if len(words) == 1 and words[0].isupper() and len(words[0]) <= 4:
        return words[0]
    head = words[0]
    head = head[0].upper() + head[1:].lower() if head[:1].isalpha() else head
    return " ".join([head, *(w.lower() for w in words[1:])]) or None


def meta_line(row: dict) -> str | None:
    """"Funeral home · 12 Genesee St, Skaneateles, NY · Ruth Hopkins, director".

    ⚠️ EVERY PART IS OPTIONAL AND THE SEPARATORS COLLAPSE WITH THEM. The prototype's
    line is built from a fixture where all four fields exist; on production none of them
    do, so a naive f-string would render "Funeral home ·  ,  · , director". The dispatch
    is explicit: "Missing fields are left out, never shown as blank labels."
    """
    place = ", ".join(part for part in (row.get("address_line1"), row.get("city")) if part)
    if place and row.get("state"):
        place = f"{place}, {row['state']}"
    director = f"{row['contact_name']}, director" if row.get("contact_name") else None
    parts = [part for part in (_nice_kind(row.get("kind")), place or None, director) if part]
    return " · ".join(parts) or None


def _customer_row(db: Session, company_id: str, customer_id: str) -> dict | None:
    """The customer, plus the kind from the CRM entity when the customer row lacks one.

    ⚠️ TWO SOURCES FOR ONE FIELD, AND THE ORDER IS DELIBERATE. `customers.customer_type`
    is the account's own classification; `company_entities.is_funeral_home` is the CRM's.
    The account wins because it is what the order was written against. Both are empty on
    production today, so the kind is absent and the meta line drops it.
    """
    row = db.execute(
        text("""
            SELECT cu.id, cu.name, cu.account_number, cu.email, cu.phone,
                   cu.address_line1, cu.city, cu.state,
                   cu.contact_name, cu.payment_terms,
                   COALESCE(NULLIF(cu.customer_type, ''), ce.customer_type,
                            CASE WHEN ce.is_funeral_home THEN 'funeral_home'
                                 WHEN ce.is_cemetery THEN 'cemetery' END) AS kind,
                   ce.id AS entity_id
              FROM customers cu
              LEFT JOIN company_entities ce
                     ON ce.company_id = cu.company_id AND ce.name = cu.name
             WHERE cu.id = :c AND cu.company_id = :t
        """),
        {"c": customer_id, "t": company_id},
    ).mappings().first()
    return dict(row) if row is not None else None


def _order_ids(db: Session, company_id: str, customer_id: str) -> set[str]:
    """This customer's order ids.

    ⚠️ A QUERY RATHER THAN A FIELD ON `OrderFacts`, and rather than matching on the NAME.
    Widening the shared dataclass would put a column on every list row for one pane's
    sake — the argument `_order_extras` already makes in `detail.py`. And matching on the
    name is what the bar does for a typed phrase, which is right there and wrong here: a
    pane opened for one account must show that account's orders, not every order whose
    funeral home happens to contain the same word.
    """
    rows = db.execute(
        text("SELECT id FROM sales_orders WHERE company_id = :t AND customer_id = :c"),
        {"t": company_id, "c": customer_id},
    ).scalars().all()
    return set(rows)


def _row_for_pane(facts: OrderFacts, today: date) -> dict:
    """One order row: deceased · vault · cemetery · day/time · status.

    ⚠️ THE FUNERAL HOME IS NOT IN IT, which is the one place this row differs from
    `stage.row_dict`'s `meta`. We are inside that customer's pane; repeating the name on
    every row is the blank-label problem in a different key.

    ⚠️ AND THE STATUS COMES FROM `stage.status_label`, NOT A SECOND COPY. That function
    is the single source since 2026-10-23, when a ladder rung called "scheduled" was
    printing on drafts. A pane with its own status vocabulary would reintroduce exactly
    that drift one surface over.
    """
    place = [part for part in (facts.vault, facts.cemetery) if part]
    row: dict = {
        "id": facts.id,
        "number": facts.number,
        # the prototype's `.mono` is the last four of the number
        "short": facts.number[-4:],
        "deceased_name": facts.deceased_name or "Unnamed",
        "what": " · ".join(place) or None,
        "status": status_label(facts),
    }
    if row["what"] is None:
        del row["what"]
    row.update(format_when(facts.service_date, facts.service_time, today))
    return row


def _account(db: Session, company_id: str, customer_id: str, terms: str | None,
             today: date) -> dict:
    """One line from real invoices, or that there are none.

    ⚠️ DRAFTS, VOIDS AND WRITE-OFFS ARE NOT A BALANCE. `OrderFacts.invoiced` already
    excludes exactly those three statuses; the same set is used here so "invoiced" and
    "owes money" cannot disagree between the row and the account line.

    ⚠️ AND TERMS COME FROM THE CUSTOMER, NOT FROM AN INVOICE. `invoices.payment_terms`
    IS populated on production ('Net 30' on 8 of 9) and `customers.payment_terms` is not
    — so reading the invoice would fill the line in. It would also be answering a
    different question: "the terms we last billed on" is not "this account's terms", and
    the dispatch says "terms if stored". Absent means absent.
    """
    row = db.execute(
        text("""
            SELECT count(*) AS n,
                   COALESCE(sum(COALESCE(i.total, 0) - COALESCE(i.amount_paid, 0)), 0)
                       AS outstanding,
                   COALESCE(sum(CASE WHEN i.due_date IS NOT NULL AND i.due_date < :today
                                      THEN COALESCE(i.total, 0) - COALESCE(i.amount_paid, 0)
                                      ELSE 0 END), 0) AS past_due
              FROM invoices i
             WHERE i.company_id = :t AND i.customer_id = :c
               AND i.status NOT IN ('draft', 'void', 'write_off')
        """),
        {"t": company_id, "c": customer_id, "today": today},
    ).mappings().first()
    if row is None or not row["n"]:
        return {"none": NO_INVOICES}
    bits = [f"{format_money(f'{Decimal(row['outstanding']):.2f}')} balance"]
    past_due = Decimal(row["past_due"])
    if past_due > 0:
        bits.append(f"{format_money(f'{past_due:.2f}')} past due")
    nice = _nice_terms(terms)
    if nice:
        bits.append(nice)
    return {
        "line": " · ".join(bits),
        "past_due": past_due > 0,
        "invoices": int(row["n"]),
    }


def _recent(db: Session, company_id: str, customer_id: str) -> list[dict]:
    """The last orders and invoices, dated. Newest first."""
    rows = db.execute(
        text("""
            SELECT 'order' AS kind, so.number AS label, so.created_at AS when_,
                   so.deceased_name AS detail
              FROM sales_orders so
             WHERE so.company_id = :t AND so.customer_id = :c
            UNION ALL
            SELECT 'invoice' AS kind, i.number AS label, i.invoice_date AS when_,
                   i.status AS detail
              FROM invoices i
             WHERE i.company_id = :t AND i.customer_id = :c
             ORDER BY when_ DESC NULLS LAST
             LIMIT 8
        """),
        {"t": company_id, "c": customer_id},
    ).mappings().all()
    out = []
    for r in rows:
        entry: dict = {"kind": r["kind"], "label": r["label"]}
        if r["when_"] is not None:
            entry["when"] = r["when_"].isoformat()
        if r["detail"]:
            entry["detail"] = r["detail"]
        out.append(entry)
    return out


def _people(db: Session, company_id: str, entity_id: str | None) -> list[dict]:
    """Contacts on the record. Empty means the tab is left out by the caller."""
    if entity_id is None:
        return []
    rows = db.execute(
        text("""
            SELECT name, title, role, phone, email
              FROM contacts
             WHERE company_id = :t AND master_company_id = :e AND is_active
             ORDER BY is_primary DESC NULLS LAST, name
             LIMIT 12
        """),
        {"t": company_id, "e": entity_id},
    ).mappings().all()
    out = []
    for r in rows:
        entry = {"name": r["name"]}
        sub = " · ".join(part for part in (r["title"] or r["role"], r["phone"]) if part)
        if sub:
            entry["detail"] = sub
        out.append(entry)
    return out


def what_opas_knows(orders: list[OrderFacts]) -> dict:
    """Usual vault and usual cemeteries, counted from this customer's own orders.

    ⚠️ NO MODEL, AND THAT IS THE POINT OF SHOWING IT. "That's the start of the rulebook,
    shown on screen" (James, 2026-10-24). Everything here is a count over records, so the
    office can check it against what they know rather than take it on trust.
    """
    live = [o for o in orders if (o.status or "").lower() not in _CANCELLED]
    total = len(live)
    if total < MIN_ORDERS_FOR_HABITS:
        return {"not_enough": NOT_ENOUGH, "orders": total}

    def tally(field: str) -> list[dict]:
        counts: dict[str, int] = {}
        for order in live:
            value = getattr(order, field, None)
            if value:
                counts[value] = counts.get(value, 0) + 1
        # ⚠️ TIES BREAK BY NAME, so the same data always renders in the same order. An
        # unstable order would read as the rulebook changing its mind.
        ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        return [
            {"name": name, "count": n, "of": total,
             "line": f"{name} · {n} of {total} orders"}
            for name, n in ranked[:MAX_HABITS]
        ]

    return {"usual_vault": tally("vault"), "usual_cemeteries": tally("cemetery"),
            "orders": total}


def customer_detail(
    db: Session,
    company_id: str,
    customer_id: str,
    today: date,
    *,
    facts: list[OrderFacts] | None = None,
) -> dict | None:
    """The whole pane. None when the id is not this caller's customer.

    `facts` is the already-loaded fact set when the caller has one — the route passes
    `load_facts`'s result rather than making this function re-read every order.
    """
    row = _customer_row(db, company_id, customer_id)
    if row is None:
        return None

    from app.services.order_list.service import load_facts

    all_facts = facts if facts is not None else load_facts(db, company_id, include_cancelled=True)
    ids = _order_ids(db, company_id, customer_id)
    mine = [f for f in all_facts if f.id in ids]

    live = [f for f in mine if (f.status or "").lower() not in _CANCELLED]
    # ⚠️ "service date today or later", the same boundary `going_out` now uses.
    coming = sorted(
        [f for f in live if f.service_date is not None and f.service_date >= today],
        key=sort_key,
    )
    # ⚠️ THE ORDER LIST'S OWN FOURTH GROUP, CALLED THROUGH ITS OWN FUNCTION. "Overdue
    # drafts in their own small group, like the order list's fourth group" — so this
    # asks `group_of` rather than re-deriving "passed and not delivered". One rule; if
    # the group's definition moves, this moves with it.
    # ⚠️ `is_overdue`, NOT `group_of(...) == "overdue"`, AND A PRODUCTION RENDER FORCED
    # THAT. `group_of` lets a FLAG win, so SO-2026-0003 — dated yesterday, undelivered,
    # no driver — came back as "needs_something" and therefore appeared in NEITHER of
    # this pane's two lists. It was shown nowhere on its own customer's pane. The
    # definition is shared; the default view's precedence is not this pane's.
    overdue = sorted([f for f in live if is_overdue(f, today)], key=sort_key)

    people = _people(db, company_id, row.get("entity_id"))
    detail: dict = {
        "id": row["id"],
        "name": row["name"],
        "action": {
            "kind": "new_order",
            "label": "New order",
            # ⚠️ TRAILING SPACE, DELIBERATELY. "as if the bar said 'order <name> '" — the
            # space is what leaves the capture ready for the next word rather than
            # mid-token, and it is in the dispatch's own quoting.
            "opening_line": f"order {row['name']} ",
            # ⚠️ THE SERVER NAMES THE FIELD, NOT THE CLIENT. The capture route
            # whitelists what a pane may seed (`PREFILLABLE_FIELDS`), and having the
            # client decide which field "New order" fills would put that decision in two
            # places — one of them the side that cannot be trusted with it.
            #
            # ⚠️ AND IT IS WHAT MAKES THE FILL SURVIVE. Measured 2026-10-24: the opening
            # line alone gave a funeral home that the next debounced re-read erased,
            # because `start` leaves `full_text` NULL and the bar's text arrives empty.
            # `prefill` is stored on the session and re-applied beneath the text on every
            # re-read; it yields only when the text names a different home.
            "prefill": {"funeral_home": row["name"]},
        },
        "open_orders": [_row_for_pane(f, today) for f in coming],
        "overdue": [_row_for_pane(f, today) for f in overdue],
        "overdue_label": GROUP_LABEL["overdue"],
        "account": _account(db, company_id, customer_id, row.get("payment_terms"), today),
        "knows": what_opas_knows(mine),
        "recent": _recent(db, company_id, customer_id),
    }
    meta = meta_line(row)
    if meta:
        detail["meta"] = meta
    # ⚠️ ABSENT, NOT EMPTY. "contacts on the record, if any; otherwise leave the tab out".
    if people:
        detail["people"] = people
    return detail


def resolve(db: Session, company_id: str, typed: str) -> list[dict]:
    """Customers a typed name or prefix could mean. Exact-ish first, then prefixes.

    ⚠️ IT REUSES `prefix_resolve.reaches`, WHICH IS THE RULING. "A prefix may match at
    the start of any word inside a known name… generic words never count as a match
    point" (James, 2026-10-21), with `funeral`, `home`, `memorial`, `chapel` and
    `cemetery` among the generics. That is why "riverside" finds Riverside Memorial
    Chapel and "memorial" finds nothing. A second copy of that walk here is the defect
    this codebase keeps recording; one source of truth, not a copy.

    ⚠️ IT RESOLVES ANY CUSTOMER ACCOUNT, NOT ONLY FUNERAL HOMES, AND THE DATA FORCES
    THAT. The dispatch says "a funeral home name or prefix"; on production every
    `customers.customer_type` is NULL and every `company_entities.is_funeral_home` is
    False, so filtering on kind would resolve NOTHING AT ALL. St. Mary's Cemetery is a
    real customer account with real invoices, and this opens its Customer Pane.

    ⚠️ WHEN THE CEMETERY PANE LANDS (the next slice) a cemetery-kind account should route
    there instead, and this is the line that has to change. Recorded as a note rather
    than built as a guess: routing on a kind that is universally NULL would be a rule
    with no data behind it.
    """
    text_in = " ".join((typed or "").split()).strip()
    if len(text_in) < MIN_PREFIX:
        return []
    rows = db.execute(
        text("SELECT id, name FROM customers WHERE company_id = :t AND is_active"),
        {"t": company_id},
    ).mappings().all()
    needle = text_in.casefold()

    exact = [dict(r) for r in rows if r["name"].casefold() == needle]
    if exact:
        return exact
    # ⚠️ A SINGLE GENERIC WORD IS NOT A NAME, AND MY SUBSTRING PASS DEFEATED THE RULING
    # UNTIL A PRODUCTION RENDER SHOWED IT. "memorial" opened Riverside Memorial Chapel,
    # because `needle in name` does not care that `memorial` is in `GENERIC_WORDS`. The
    # ruling (James, 2026-10-21) is that generic words never count as a match point, and
    # a second matching pass that skips the rule is the same defect as a second copy of
    # it. "memorial chapel" is still fine — it is two words, one of them distinctive.
    if len(text_in.split()) == 1 and needle in GENERIC_WORDS:
        return []
    contains = [dict(r) for r in rows if needle in r["name"].casefold()]
    if contains:
        return sorted(contains, key=lambda r: (len(r["name"]), r["name"]))
    # ⚠️ INTERIOR MATCH POINTS ON PURPOSE. `interior=True` is what lets "riverside"
    # reach a name whose first word is something else; the generic-word list is what
    # stops "home" reaching every funeral home at once.
    prefixed = [dict(r) for r in rows if reaches(r["name"], text_in, interior=True)]
    return sorted(prefixed, key=lambda r: (len(r["name"]), r["name"]))


#: Words that make a phrase an ORDER request rather than a customer one.
#:
#: ⚠️ "with an order word it stays an order request as today" (James, 2026-10-24). The
#: table is exact rather than a stem match: "orders" and "order" are the words a director
#: uses, and a `\border` prefix rule would also claim "ordered" and "reorder".
_ORDER_WORDS = frozenset({"order", "orders", "order's"})

#: Stripped from the front of a phrase before resolving, so "open hopkins" works.
_OPENERS = ("open ", "show ", "pull up ", "bring up ")

TOO_MANY = "Which one?"


def open_from_phrase(db: Session, company_id: str, phrase: str) -> dict | None:
    """A bare customer name or prefix, as an `ask` reply. None means not one.

    ⚠️ None IS "NOT A CUSTOMER PHRASE", NOT "NO SUCH CUSTOMER", and the caller depends on
    the difference: `ask` falls through to the model door on None. A phrase that looks
    like a name and matches nothing must NOT be claimed here, or the door never sees it.
    """
    text_in = " ".join((phrase or "").split()).strip()
    if not text_in:
        return None
    lowered = text_in.casefold()
    for opener in _OPENERS:
        if lowered.startswith(opener):
            text_in = text_in[len(opener):].strip()
            lowered = text_in.casefold()
            break
    if not text_in:
        return None
    # ⚠️ ANY order word anywhere, not just a trailing one. "order hopkins" starts a
    # capture and "hopkins order" opens an order; neither is this.
    if _ORDER_WORDS & set(lowered.replace(",", " ").split()):
        return None

    hits = resolve(db, company_id, text_in)
    if not hits:
        return None
    if len(hits) == 1:
        return {
            "kind": "open_customer",
            "customer_id": hits[0]["id"],
            "customer_name": hits[0]["name"],
        }
    # ⚠️ A CHOICE LIST, NOT THE FIRST MATCH, and `picks` is the shape the bar already
    # renders and numbers. Two customers whose names share a word is the ordinary case
    # for "riverside" in a county with two Riversides.
    # ⚠️ UNDER ITS OWN KEY, NOT `picks`. An order pick carries a `question` that narrows
    # the list; a customer pick carries an id that OPENS A PANE. Sharing the key would
    # make every existing consumer of `picks` test which kind it held, and the one that
    # forgot would feed a customer id into `ask` as a question.
    return {
        "kind": "customer_picks",
        "hint": TOO_MANY,
        "customer_picks": [
            {"label": hit["name"], "customer_id": hit["id"]} for hit in hits[:6]
        ],
    }
