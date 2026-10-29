"""The Cemetery Pane's read, and the rule that opens it from a bare name.

James's dispatch of 2026-10-26, "Cemetery Pane, slice 1". Read-only on real data; no
migration. Built from the prototype (artifact
`0f3ee586-8baf-4b5e-b058-a9848aabc3ce`, "Contact, Cemetery, Invoice Panes", updated
2026-10-03 — 93,927 bytes, md5 `44063e83a50a1260e42a30a4d7e975e2`, of which 52,899 chars
after `<!-- /frame-runtime -->` are the author's own source). The bytes and the digests
are in `docs/prototypes/`, with `PROVENANCE-2026-10-26-cemetery-pane.md` recording that
the dispatch's short URL does not resolve and the uuid, given truncated, had to be
completed from the artifact listing.

THE PROTOTYPE LINES THIS FOLLOWS, quoted:

    .ttl        `<div class="ttl">${c.n}</div>`
    .meta       `<div class="meta">${c.town}, NY · <button type="button" class="lnk"
                 data-a="cem:${c.other}">${c.not}</button></div>`
    action      `<button class="btn…" data-a="chip:Directions to the …">Directions</button>`
    essentials  `<div class="sech"><span>The essentials</span></div><div class="kv">`
                `<div><span>Address</span><span>${esc(c.addr)}</span></div>`
                `<div><span>Getting in</span><span>${esc(c.approach)}</span></div>`
                `<div><span>${c.people[0][1]}</span><span>${esc(c.people[0][0])} · …`
    coming up   `<div class="sech"><span>Coming up here</span><span>${c.up.length}</span></div>`
                `<button type="button" class="row" …><span class="a">${u[0]}</span>
                  <span class="b">${esc(u[1])} · ${esc(u[2])} · …</span>
                  <span class="c">›</span></button>`
    knows       `<div><span>Deliveries this year</span><span>${c.year}</span></div>`
                `<div><span>Next delivery</span><span>…</span></div>`
                `<div><span>Same name elsewhere</span><span><button … class="lnk">…`

⚠️ LEFT OUT BY RULING: the `Right now` closures (`c.alert`), `Sections` (`c.secs`),
`Driver notes` (`c.notes`), the `Call the <role>` action, the `Also called` alias list,
and the People tab unless contacts are recorded. "Almost none of that is recorded yet, so
this slice shows only what Bridgeable actually knows and leaves the rest out rather than
faking it" (James, 2026-10-26).

⚠️ MEASURED ON PRODUCTION BEFORE BUILDING, AND IT DECIDES MOST OF THIS FILE. There are
**four** cemetery rows platform-wide — three on testco, one on sunnycrest. Of the fields
the prototype shows:

    city, state           4/4 recorded      -> the meta line works
    address               0/4               -> the Directions action NEVER appears
    phone, contact_name   0/4               -> no contact row, no People tab
    access_notes          0/4               -> "Nothing recorded about getting in yet"
    equipment_note        0/4
    county, zip_code      0/4
    latitude, longitude   0/4

So on today's data the pane is a name, a town, the orders, and the counts. That is the
dispatch's own rule working, not a defect, and it is the argument for the pane rather
than against it — the rows fill as the office uses it.

⚠️ AND THE FOUR `cemetery_provides_*` BOOLEANS ARE `nullable=False, default=False`, WHICH
IS CLAUDE.md §5's TRAP EXACTLY. `False` cannot be told apart from "nobody said", so this
file reports only the TRUE ones and treats all-false as nothing recorded. Rendering
"Tents: not provided" off a default would be the platform asserting something no one
measured. One row — testco's St. Mary's — has three of them true, which is the only
affirmative equipment data that exists.

⚠️ THE SHARED-NAME RULE IS BUILT AND NO PRODUCTION ROW EXERCISES IT. The dispatch says
"several share names"; measured, there are **zero** name collisions within any tenant.
"St. Mary's Cemetery" does exist twice — once on sunnycrest and once on testco — but
those are different tenants, and a cross-tenant link would be a tenant-isolation
breach, not a feature. So `same_name` and the shared-name choice list are reachable only
from constructed fixtures today. Said out loud because machinery behind a condition no
data satisfies is CLAUDE.md §11's unprovisioned-entrance class, and the way that stays
honest is naming it rather than discovering it later.
"""

from __future__ import annotations

from datetime import date
from urllib.parse import quote_plus

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.capture.prefix_resolve import GENERIC_WORDS, MIN_PREFIX, reaches
# ⚠️ ONE TOWN PATTERN, SHARED — not a copy. See `capture/towns.py`, whose single
# definition of the town pattern is held by the ratchet in
# `test_a_director_types_no_commas.py`. Same precedent as `prefix_resolve` above.
from app.services.capture.towns import town_before, town_leading
from app.services.party_resolver import normalize as _pn
from app.services.order_list.customer import DID_YOU_MEAN, TOO_MANY, needs_confirmation
from app.services.order_list.stage import (
    GROUP_LABEL,
    OrderFacts,
    format_when,
    is_overdue,
    sort_key,
    status_label,
)
from app.services.display_name import deceased_for_display, title_case_for_display

#: Said when the record holds nothing but a name and a town.
#:
#: ⚠️ THE DISPATCH'S OWN WORDS, and it is about GETTING IN rather than about the record
#: in general — "If nothing is recorded beyond the name and town, say 'Nothing recorded
#: about getting in yet'". It names the thing the driver wanted, not the row that is
#: empty, which is why it is a useful sentence instead of a shrug.
NOTHING_RECORDED = "Nothing recorded about getting in yet"

#: The equipment booleans, and the words for them when TRUE.
#:
#: ⚠️ ONLY THE TRUE DIRECTION HAS WORDS, deliberately. There is no "does not provide a
#: tent" string anywhere in this file, because the column cannot distinguish that from
#: silence (see the module docstring). A future NULLABLE column could say it; this one
#: cannot, and the absence of the phrase is what stops it being said by accident.
_PROVIDES: tuple[tuple[str, str], ...] = (
    ("cemetery_provides_lowering_device", "Lowering device"),
    ("cemetery_provides_grass", "Grass"),
    ("cemetery_provides_tent", "Tent"),
    ("cemetery_provides_chairs", "Chairs"),
)


def _cemetery_row(db: Session, company_id: str, cemetery_id: str) -> dict | None:
    """The cemetery, or None when the id is not this caller's.

    ⚠️ `company_id` IN THE WHERE CLAUSE, NOT CHECKED AFTERWARDS. A read that fetches by
    id and then compares has already loaded another tenant's row, and the version that
    forgets the comparison looks identical.
    """
    row = db.execute(
        text(
            """
            SELECT id, name, address, city, state, county, zip_code, phone,
                   contact_name, access_notes, equipment_note, latitude, longitude,
                   cemetery_provides_lowering_device, cemetery_provides_grass,
                   cemetery_provides_tent, cemetery_provides_chairs
              FROM cemeteries
             WHERE id = :c AND company_id = :t AND is_active
            """
        ),
        {"c": cemetery_id, "t": company_id},
    ).mappings().first()
    return dict(row) if row else None


def meta_line(row: dict) -> str | None:
    """"Skaneateles, NY" — the town, always shown.

    ⚠️ THE TOWN IS NOT OPTIONAL IN THE DISPATCH ("town always shown") AND IS OPTIONAL IN
    THE SCHEMA. `cemeteries.city` is nullable. It happens to be populated on all four
    rows that exist, which is exactly the sort of fact that stops being true the first
    time someone adds a cemetery by name alone — so this returns None rather than ", NY"
    when it is missing.
    """
    town = (row.get("city") or "").strip()
    state = (row.get("state") or "").strip()
    if not town:
        return None
    return f"{town}, {state}" if state else town


def _same_name(db: Session, company_id: str, row: dict) -> dict | None:
    """Another cemetery in THIS tenant with the same name, if there is one.

    ⚠️ WITHIN THE TENANT, AND THAT IS NOT A DETAIL. "St. Mary's Cemetery" exists on both
    sunnycrest and testco; linking those together would hand one tenant a route into
    another's record. The dispatch says "another cemetery in the tenant", and the
    `company_id` here is what makes that true rather than nearly true.

    ⚠️ AND NOTHING IN PRODUCTION MATCHES — zero shared-name groups in any tenant. The
    unique constraint is `(company_id, name)`, so an EXACT duplicate is impossible by
    construction; what can collide is the same name with different punctuation or
    spacing ("St. Mary's" vs "St Marys"), which is why this compares on a squeezed,
    case-folded key rather than on equality.
    """
    key = _name_key(row["name"])
    others = db.execute(
        text(
            """
            SELECT id, name, city, state FROM cemeteries
             WHERE company_id = :t AND is_active AND id <> :c
            """
        ),
        {"t": company_id, "c": row["id"]},
    ).mappings().all()
    for other in others:
        if _name_key(other["name"]) == key:
            town = (other["city"] or "").strip()
            return {
                "cemetery_id": other["id"],
                "name": other["name"],
                **({"town": town} if town else {}),
                # ⚠️ THE SERVER COMPOSES THE SENTENCE, same rule as the Customer Pane's
                # `meta` and `account.line`. The prototype's own words are "not the
                # St. Mary's in Auburn".
                "line": f"not the {other['name']} in {town}" if town
                        else f"not the other {other['name']}",
            }
    return None


def _name_key(name: str) -> str:
    """"St. Mary's Cemetery" and "St Marys Cemetery" are the same name here."""
    return "".join(ch for ch in (name or "").casefold() if ch.isalnum())


def _directions(row: dict) -> dict | None:
    """The one action, and only when there is an address to send.

    ⚠️ "ONLY IF AN ADDRESS IS RECORDED" (dispatch), AND THAT MEANS IT IS ABSENT ON EVERY
    CEMETERY TODAY — `address` is NULL on all four rows. A Directions button built from
    a name and a town would open a maps search for "St. Mary's Cemetery, Skaneateles",
    which is a guess dressed as a record, and the one time it guesses wrong it sends a
    driver with a vault on the truck to the wrong gate.

    ⚠️ LAT/LONG WOULD BE BETTER AND IS ALSO EMPTY (0/4), so there is no second source to
    fall back to. Recorded here because the remedy is data, not code.
    """
    address = (row.get("address") or "").strip()
    if not address:
        return None
    parts = [address]
    for key in ("city", "state", "zip_code"):
        value = (row.get(key) or "").strip()
        if value:
            parts.append(value)
    query = ", ".join(parts)
    return {
        "kind": "directions",
        "label": "Directions",
        "url": f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}",
    }


def essentials(row: dict) -> list[dict]:
    """The recorded facts about getting in, in the prototype's order. Never a blank.

    ⚠️ EVERY ROW HERE IS CONDITIONAL. "Missing fields are left out, never 'N/A'"
    (dispatch), which on today's data means this returns an EMPTY LIST for all four
    cemeteries — and the caller says `NOTHING_RECORDED` rather than rendering a heading
    over nothing.
    """
    out: list[dict] = []

    address = (row.get("address") or "").strip()
    if address:
        tail = ", ".join(
            v for v in ((row.get("city") or "").strip(), (row.get("state") or "").strip())
            if v
        )
        out.append({"label": "Address", "value": f"{address}, {tail}" if tail else address})

    # ⚠️ "GETTING IN", WHICH IS THE PROTOTYPE'S LABEL FOR `c.approach`. The schema's
    # column is `access_notes` and it is the only free-text field about reaching the
    # grave, so it carries both of the prototype's `gate` and `approach` lines. Two
    # labels over one column would be the platform inventing a distinction its record
    # does not make.
    access = (row.get("access_notes") or "").strip()
    if access:
        out.append({"label": "Getting in", "value": access})

    contact = (row.get("contact_name") or "").strip()
    phone = (row.get("phone") or "").strip()
    if contact or phone:
        out.append({
            "label": "Contact",
            "value": " · ".join(p for p in (contact, phone) if p),
        })

    # ⚠️ TRUE ONLY. See `_PROVIDES` — a False here is indistinguishable from unset.
    provided = [label for column, label in _PROVIDES if row.get(column)]
    if provided:
        out.append({"label": "Cemetery provides", "value": ", ".join(provided)})

    note = (row.get("equipment_note") or "").strip()
    if note:
        out.append({"label": "Equipment", "value": note})

    return out


def _row_for_pane(facts: OrderFacts, today: date) -> dict:
    """One order row: day/time · deceased · funeral home · status.

    ⚠️ THE FUNERAL HOME IS IN IT AND THE CEMETERY IS NOT — the mirror image of the
    Customer Pane's row, and for the same reason. We are inside the cemetery's pane, so
    repeating its name on every row is the blank-label problem in a different key; the
    funeral home is the thing the office would not otherwise know from here.

    ⚠️ AND THE STATUS COMES FROM `stage.status_label`, NOT A SECOND COPY, which is the
    rule since 2026-10-23 when a rung called "scheduled" was printing on drafts.
    """
    row: dict = {
        "id": facts.id,
        "number": facts.number,
        # the prototype's `.mono` is the last four of the number
        "short": facts.number[-4:],
        "deceased_name": deceased_for_display(facts.deceased_name),
        "status": status_label(facts),
    }
    home = (facts.funeral_home or "").strip()
    if home:
        row["funeral_home"] = home
        # ⚠️ ONLY WHEN THE ORDER HAS A CUSTOMER ROW, so the client renders plain text
        # rather than a button that cannot resolve. Same rule as the cemetery link.
        if facts.customer_id:
            row["customer_id"] = facts.customer_id
    row.update(format_when(facts.service_date, facts.service_time, today))
    return row


def _order_ids(db: Session, company_id: str, cemetery_id: str) -> set[str]:
    """Which orders name this cemetery."""
    rows = db.execute(
        text("SELECT id FROM sales_orders WHERE company_id = :t AND cemetery_id = :c"),
        {"t": company_id, "c": cemetery_id},
    ).all()
    return {r[0] for r in rows}


def what_opas_knows(mine: list[OrderFacts], today: date, same: dict | None) -> dict:
    """Counted from records, with no model.

    ⚠️ ONLY WHAT CAN BE COUNTED, which is the dispatch's instruction and rules out three
    of the prototype's four rows here. `Also called` needs an alias list the schema does
    not have; the "when someone says just St. Mary's" line is a claim about Opas rather
    than about the cemetery.

    ⚠️ "DELIVERIES THIS YEAR" IS CALENDAR-YEAR TO DATE AND COUNTS `delivered`, WHICH
    INCLUDES `completed`. `OrderFacts.delivered` is true for status `delivered` OR
    `completed`, or a completed delivery row — so an order closed out counts, which is
    what the office means by a delivery having happened. Measured: sunnycrest's
    St. Mary's has 1, testco's has 4.
    """
    delivered_this_year = [
        f for f in mine
        if f.delivered and f.service_date is not None and f.service_date.year == today.year
    ]
    upcoming = sorted(
        [f for f in mine
         if not f.cancelled and f.service_date is not None and f.service_date >= today],
        key=sort_key,
    )
    out: dict = {
        "deliveries_this_year": len(delivered_this_year),
        "year": today.year,
    }
    if upcoming:
        nxt = upcoming[0]
        when = format_when(nxt.service_date, nxt.service_time, today)
        label = " · ".join(
            p for p in (when.get("date_primary") or when.get("date_head"),
                        title_case_for_display(nxt.deceased_name)) if p
        )
        out["next_delivery"] = {"order_id": nxt.id, "line": label}
    if same is not None:
        out["same_name"] = same
    return out


def cemetery_detail(
    db: Session,
    company_id: str,
    cemetery_id: str,
    today: date,
    *,
    facts: list[OrderFacts] | None = None,
) -> dict | None:
    """The whole pane. None when the id is not this caller's cemetery.

    `facts` is the already-loaded fact set when the caller has one — the route passes
    `load_facts`'s result rather than re-reading every order.
    """
    row = _cemetery_row(db, company_id, cemetery_id)
    if row is None:
        return None

    from app.services.order_list.service import load_facts

    all_facts = facts if facts is not None else load_facts(
        db, company_id, include_cancelled=True
    )
    ids = _order_ids(db, company_id, cemetery_id)
    mine = [f for f in all_facts if f.id in ids]
    live = [f for f in mine if not f.cancelled]

    # ⚠️ "SERVICE DATE TODAY OR LATER", the same boundary `going_out` uses since
    # 2026-10-23 — not "not yet delivered". A past service date is never coming up.
    coming = sorted(
        [f for f in live if f.service_date is not None and f.service_date >= today],
        key=sort_key,
    )
    # ⚠️ `is_overdue`, NOT `group_of(...) == "overdue"`, for the reason the Customer Pane
    # records: `group_of` lets a FLAG win, so a past-dated undelivered order with no
    # driver came back as "needs_something" and appeared in NEITHER list. The definition
    # is shared; the default view's precedence is not this pane's.
    overdue = sorted([f for f in live if is_overdue(f, today)], key=sort_key)

    same = _same_name(db, company_id, row)
    rows = essentials(row)

    detail: dict = {
        "id": row["id"],
        "name": row["name"],
        "coming": [_row_for_pane(f, today) for f in coming],
        "overdue": [_row_for_pane(f, today) for f in overdue],
        "overdue_label": GROUP_LABEL["overdue"],
        "knows": what_opas_knows(mine, today, same),
    }
    meta = meta_line(row)
    if meta:
        detail["meta"] = meta
    if same is not None:
        detail["same_name"] = same
    action = _directions(row)
    if action is not None:
        detail["action"] = action
    if rows:
        detail["essentials"] = rows
    else:
        detail["essentials_empty"] = NOTHING_RECORDED
    return detail


def resolve(db: Session, company_id: str, typed: str) -> list[dict]:
    """Cemeteries a typed name or prefix could mean. Exact-ish first, then prefixes.

    ⚠️ THE SAME WALK AS `customer.resolve`, AND IT REUSES `reaches` RATHER THAN COPYING
    IT. "A prefix may match at the start of any word inside a known name… generic words
    never count as a match point" (James, 2026-10-21). A second copy of that walk is the
    defect this codebase keeps recording.

    ⚠️ AND A LONE GENERIC WORD IS RESOLVED HERE AND CONFIRMED IN `open_from_phrase`,
    which is ruling 1 of 2026-10-24 reaching this surface. It matters more here than for
    customers: `cemetery` IS a generic word, and so is `st`. So "cemetery" comes back
    with every cemetery as a choice, and "st marys" — two words — resolves normally.
    """
    text_in = " ".join((typed or "").split()).strip()
    if len(text_in) < MIN_PREFIX:
        return []
    rows = db.execute(
        text("SELECT id, name, city, state FROM cemeteries "
             "WHERE company_id = :t AND is_active"),
        {"t": company_id},
    ).mappings().all()
    needle = text_in.casefold()

    # ⚠️ PUNCTUATION-INSENSITIVE EXACT MATCH, because "st marys" is what a person types
    # and "St. Mary's Cemetery" is what the record holds. A strict equality pass would
    # find nothing and fall through to prefixes, which happens to work — but only by
    # accident, and it would stop working for a name whose words are all generic.
    key = _name_key(text_in)
    exact = [dict(r) for r in rows if _name_key(r["name"]) == key]
    if exact:
        return exact

    # ⚠️ NAME PLUS TOWN, AND THE DISPATCH'S OWN EXAMPLE DID NOT WORK WITHOUT IT.
    # Measured on production before building: `"st mary's skaneateles"` — one of the two
    # phrases the dispatch names — resolved to NOTHING, on either the cemetery or the
    # customer resolver, because the town is not part of the name and no pass joined
    # them. "st marys" worked; the disambiguating form did not, which is the one that
    # matters precisely when a name IS shared.
    #
    # ⚠️ AND IT IS THE DISAMBIGUATOR, so it is tried before `contains` rather than after.
    # "st mary's skaneateles" must reach ONE cemetery even though "st mary's" alone
    # reaches both — that is the whole point of typing the town.
    with_town = [
        dict(r) for r in rows
        if (r["city"] or "").strip()
        and key in (
            _name_key(f"{r['name']} {r['city']}"),
            _name_key(f"{r['city']} {r['name']}"),
        )
    ]
    if with_town:
        return with_town

    # A NAME PREFIX plus the exact town, IN EITHER ORDER — "st marys skaneateles" and
    # "skaneateles st marys" where the record reads "St. Mary's Cemetery". The town has
    # to match in full; a prefix of a town would start matching things nobody typed.
    #
    # ⚠️ BOTH ORDERINGS, BY RULING (James, 2026-10-29): *"Extend the leading/bare town
    # rule to the cemetery pane's search … One town pattern shared by both surfaces, not
    # a copy."* The leading form resolved to NOTHING before this — `with_town` above
    # cannot see it either, because the record's name carries "Cemetery" and the typed
    # text does not, so neither joined key matches.
    #
    # ⚠️ AND IT ROUTES THROUGH `capture.towns`, WHICH IS A BEHAVIOUR CHANGE AS WELL AS A
    # DE-DUPLICATION. The pass this replaces tested `key.endswith(_name_key(city))` —
    # a squeezed-string suffix, which matches INSIDE a word: a town "Auburn" against a
    # typed "newauburn" satisfied it. `town_before` / `town_leading` compare whole
    # whitespace runs, so the town must be a word, and the longest run wins so a
    # two-word town is never read as its second word.
    town_edge: list[dict] = []
    if rows:
        known_towns = frozenset(
            _pn(r["city"]) for r in rows if (r["city"] or "").strip()
        )
        trailing = town_before(text_in, known_towns)
        leading = town_leading(text_in, known_towns)
        for r in rows:
            city = (r["city"] or "").strip()
            if not city:
                continue
            for found, rest in (
                (trailing, text_in[: trailing[1]] if trailing else ""),
                (leading, text_in[leading[1] :] if leading else ""),
            ):
                if not found or _pn(found[0]) != _pn(city):
                    continue
                # ⚠️ `rest.strip() and` IS DEFENSIVE, NOT LOAD-BEARING, AND A BREAK TEST
                # PROVED IT: removing it leaves every test green, because `reaches`
                # returns None for an empty needle and the argument is stripped here too.
                # It is kept because `reaches(name, " ")` DOES return a position — so one
                # missing `.strip()` and this clause becomes the only thing stopping a
                # bare town ("skaneateles") from opening a cemetery pane.
                if rest.strip() and reaches(r["name"], rest.strip(), interior=True):
                    town_edge.append(dict(r))
                    break
    if town_edge:
        return sorted(town_edge, key=lambda r: (len(r["name"]), r["name"]))

    # ⚠️ A PUNCTUATION-BLIND PREFIX, AND A TEST OF THE SHARED-NAME CASE IS WHAT FOUND
    # THE NEED. "st marys" against two cemeteries — "St. Mary's Cemetery" and
    # "St Marys Cemetery" — reached only the second, because `contains` is defeated by
    # the apostrophe and `reaches` matches on the name's real words. So the pane asked
    # nothing and opened one of the two arbitrarily, which is the exact failure the
    # choice list exists to prevent, in the exact case it was built for.
    #
    # ⚠️ IT IS A PREFIX, NOT A CONTAINS, so "marys" does NOT come through here — that
    # one still needs `reaches`'s interior match below, and the two passes cover
    # different things rather than one shadowing the other.
    #
    # ⚠️ AND IT RUNS BEFORE `contains`, WHICH IS THE HALF I GOT WRONG FIRST. Placed
    # after it, `contains` matched the UNPUNCTUATED name and returned early with one
    # of the two — so the test still saw `open_cemetery` where it wanted a question.
    # A more general pass behind a narrower one never runs on the cases that need it.
    squeezed = [
        dict(r) for r in rows if key and _name_key(r["name"]).startswith(key)
    ]
    if squeezed:
        return sorted(squeezed, key=lambda r: (len(r["name"]), r["name"]))

    contains = [dict(r) for r in rows if needle in r["name"].casefold()]
    if contains:
        return sorted(contains, key=lambda r: (len(r["name"]), r["name"]))

    prefixed = [dict(r) for r in rows if reaches(r["name"], text_in, interior=True)]
    return sorted(prefixed, key=lambda r: (len(r["name"]), r["name"]))


#: Words that make a phrase an ORDER request rather than a cemetery one.
_ORDER_WORDS = frozenset({"order", "orders", "order's"})

#: Stripped from the front of a phrase before resolving.
_OPENERS = ("open ", "show ", "pull up ", "bring up ")


def _pick(hit: dict) -> dict:
    """One entry in a choice list, with the town, because the town is the discriminator.

    ⚠️ "ASK WHICH WITH THE CHOICE LIST, TOWN SHOWN" (dispatch). Two cemeteries with the
    same name and no town on the options would be a question nobody can answer.
    """
    town = (hit.get("city") or "").strip()
    return {
        "label": hit["name"],
        "cemetery_id": hit["id"],
        **({"detail": town} if town else {}),
    }


def open_from_phrase(db: Session, company_id: str, phrase: str) -> dict | None:
    """A bare cemetery name or prefix, as an `ask` reply. None means not one.

    ⚠️ None IS "NOT A CEMETERY PHRASE", NOT "NO SUCH CEMETERY", and the caller depends on
    the difference — `ask` must go on to try the customer rule and then the model door.
    A phrase that looks like a name and matches nothing must NOT be claimed here.
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
    if _ORDER_WORDS & set(lowered.replace(",", " ").split()):
        return None

    hits = resolve(db, company_id, text_in)
    if not hits:
        return None
    # ⚠️ RULING 1 (James, 2026-10-24) REACHES THIS SURFACE TOO. A lone generic word never
    # opens anything directly — and `cemetery`, `st`, `memorial` and `chapel` are all in
    # `GENERIC_WORDS`, so this fires far more often here than on the customer side.
    if needs_confirmation(text_in):
        return {
            "kind": "cemetery_picks",
            "hint": DID_YOU_MEAN,
            "cemetery_picks": [_pick(h) for h in hits[:6]],
        }
    if len(hits) == 1:
        return {
            "kind": "open_cemetery",
            "cemetery_id": hits[0]["id"],
            "cemetery_name": hits[0]["name"],
        }
    return {
        "kind": "cemetery_picks",
        "hint": TOO_MANY,
        "cemetery_picks": [_pick(h) for h in hits[:6]],
    }


__all__ = [
    "GENERIC_WORDS",
    "NOTHING_RECORDED",
    "cemetery_detail",
    "essentials",
    "meta_line",
    "open_from_phrase",
    "resolve",
    "what_opas_knows",
]
