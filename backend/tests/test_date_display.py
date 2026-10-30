"""Dates and times on rows are written the way the office writes them, never ISO.

⚠️ JAMES, 2026-10-12: the Service row showed `2027-03-02`. "It's the same problem as
the raw codes, just for dates." Same rule as labels-not-slugs: a STORED form leaked to
a screen. Stored values are unchanged — `'2027-03-02'`, `'10:00'`; only the rendering
moved.

⚠️ A BARE YEAR STAYS A BARE YEAR, AND THIS IS THE CASE THAT MATTERS. "1948 to 2026"
stores `'1948'` and `'2026'` — measured, not assumed — because the year-pair parser's
whole point is that a director who gave years gave YEARS. Formatting those as dates
would mean inventing a month and a day in order to print a weekday: a fabricated value
in a field whose honesty is its reason for existing. CLAUDE.md §5, *not established is
a value*.

⚠️ NO `strftime`, AND THE REASON IS PORTABILITY NOT TASTE. `%-d` for a day without a
leading zero is platform-specific, and `%a`/`%b` are locale-dependent; either would
make the rendered row depend on where the server runs. The month and weekday names are
listed in the source and the weekday is Zeller's congruence — checked below against
`datetime` over 3000 dates, which is an independent instrument rather than a second
run of the same one.
"""
from __future__ import annotations

import datetime
import random
import uuid

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.services.capture import session_service
from app.services.capture.rows import _weekday, write_for_a_human
from app.services.capture.schema import PLATFORM_DEFAULT_FIELDS

BY_ID = {d.field_id: d for d in PLATFORM_DEFAULT_FIELDS}

#: ⚠️ LISTED, SO ADDING A SEVENTH IS A VISIBLE EDIT HERE.
DATE_FIELDS = ("service_date", "burial_date", "date_of_birth", "date_of_death")
TIME_FIELDS = ("service_time", "eta")
#: ⚠️ A THIRD KIND SINCE 2026-10-14. `display="name"` title-cases an all-lowercase
#: name FOR DISPLAY ONLY — "smith" shows as "Smith" and is stored as typed. Ruled by
#: James, superseding "display as given" from the day before.
NAME_FIELDS = ("deceased_name",)
#: ⚠️ A FOURTH KIND SINCE 2026-10-14. `display="count"` names the unit — "4" renders
#: as "4 chairs", singular at one — because a bare number on an equipment row reads
#: as a quantity of PACKAGES. Chairs are the only per-unit thing on the order; every
#: other equipment package is a flat charge at quantity 1.
#:
#: ⚠️ TWO FIELDS SINCE 2026-10-30 (rulings A/B'), WHERE `extra_chairs_count` STOOD.
#: That one field held an ALREADY-SUBTRACTED extra count, so "6 chairs" was stored as
#: 0 and the pane could never show "6 chairs" again. `chairs_total` and `chairs_extra`
#: each hold one reading in the sense the director gave it, and BOTH need the unit
#: named for the same reason the single field did.
COUNT_FIELDS = ("chairs_total", "chairs_extra")


def _refuse_a_non_local_database() -> None:
    from urllib.parse import urlparse

    from app.config import settings

    host = (urlparse(settings.DATABASE_URL).hostname or "").lower()
    assert host in ("localhost", "127.0.0.1", "::1", "")


@pytest.fixture(scope="module")
def db():
    _refuse_a_non_local_database()
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


# ── the partition ───────────────────────────────────────────────────────

def test_exactly_these_fields_declare_a_display_format():
    declared = {d.field_id for d in PLATFORM_DEFAULT_FIELDS if d.display}
    expected = (
        set(DATE_FIELDS) | set(TIME_FIELDS) | set(NAME_FIELDS) | set(COUNT_FIELDS)
    )
    assert declared == expected, (
        f"the display partition moved. extra={sorted(declared - expected)} "
        f"missing={sorted(expected - declared)}"
    )
    for f in DATE_FIELDS:
        assert BY_ID[f].display == "date", f
    for f in TIME_FIELDS:
        assert BY_ID[f].display == "time", f
    for f in NAME_FIELDS:
        assert BY_ID[f].display == "name", f
    for f in COUNT_FIELDS:
        assert BY_ID[f].display == "count", f


def test_no_field_declares_both_options_and_a_display_format():
    """⚠️ THE TWO MECHANISMS MUST NOT STACK. `_render` checks `display` first, so a
    field carrying both would have its label map SILENTLY IGNORED. An enum's stored
    value is an id with a label; a date's is a value with a format."""
    both = [d.field_id for d in PLATFORM_DEFAULT_FIELDS if d.options and d.display]
    assert not both, both


# ── the weekday arithmetic, against an independent instrument ───────────

def test_the_weekday_matches_the_standard_library():
    """⚠️ 3000 RANDOM DATES ACROSS 1900-2105, compared with `datetime` — a different
    implementation, not a second call to the same one. Hand-rolled calendar maths is
    exactly the kind of thing that is right for the dates you tried."""
    rng = random.Random(20261012)
    for _ in range(3000):
        d = datetime.date(1900, 1, 1) + datetime.timedelta(
            days=rng.randrange(0, 75000)
        )
        assert _weekday(d.year, d.month, d.day) == d.weekday(), d


# ── the formatter ───────────────────────────────────────────────────────

@pytest.mark.parametrize("stored,shown", [
    ("2027-03-02", "Tue Mar 2, 2027"),
    ("2026-10-13", "Tue Oct 13, 2026"),
    ("2027-01-01", "Fri Jan 1, 2027"),
    ("2024-02-29", "Thu Feb 29, 2024"),   # a leap day
    ("2026-12-31", "Thu Dec 31, 2026"),
])
def test_a_stored_date_is_written_for_a_human(stored, shown):
    assert write_for_a_human(stored, "date") == shown


@pytest.mark.parametrize("stored", ["1948", "2026", "1900"])
def test_a_bare_year_is_left_exactly_as_it_is(stored):
    """⚠️ NO MONTH AND NO DAY INVENTED. See the module docstring."""
    assert write_for_a_human(stored, "date") == stored


@pytest.mark.parametrize("stored,shown", [
    ("10:00", "10:00 AM"),
    ("14:30", "2:30 PM"),
    ("00:15", "12:15 AM"),     # midnight is 12 AM, not 0 AM
    ("12:00", "12:00 PM"),     # noon is 12 PM, not 0 PM
    ("23:59", "11:59 PM"),
    ("09:05", "9:05 AM"),
])
def test_a_stored_time_is_written_for_a_human(stored, shown):
    assert write_for_a_human(stored, "time") == shown


@pytest.mark.parametrize("stored,kind", [
    ("not-a-date", "date"),
    ("2027-13-02", "date"),    # month 13
    ("2027-03-45", "date"),    # day 45
    ("9:5", "time"),           # not HH:MM
    ("25:00", "time"),         # hour 25
    ("10:99", "time"),         # minute 99
    ("anything", None),        # no format declared
])
def test_an_unrecognised_value_passes_through_unchanged(stored, kind):
    """A stored row may predate a parser change. A visible oddity an operator can
    report beats raising and taking the pane down over one row — the same choice
    `label_for` makes."""
    assert write_for_a_human(stored, kind) == stored


# ── through the API response ────────────────────────────────────────────

@pytest.fixture
def session(db):
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    sp = db.begin_nested()
    slug = f"datedisp-{uuid.uuid4().hex[:8]}"
    co = Company(id=str(uuid.uuid4()), name=slug, slug=slug, vertical="manufacturing")
    db.add(co)
    db.flush()
    role = Role(id=str(uuid.uuid4()), company_id=co.id, name="Admin", slug="admin")
    db.add(role)
    db.flush()
    u = User(id=str(uuid.uuid4()), company_id=co.id, email=f"{slug}@example.com",
             first_name="D", last_name="D", hashed_password="x", role_id=role.id)
    db.add(u)
    db.flush()
    row = session_service.start(db, company_id=co.id, user_id=u.id)
    yield co.id, u.id, row.id
    sp.rollback()


def test_no_rendered_row_shows_an_ISO_DATE(db, session):
    """⚠️ THE PROPERTY, NOT THE EXAMPLE. Asserting the Service row reads
    "Tue Mar 2, 2027" passes if someone hardcodes that string. Asserting that NO row
    anywhere matches `\\d{4}-\\d{2}-\\d{2}` fails for a field nobody listed here."""
    import re

    cid, uid, sid = session
    for line in ["Bronze Triune Burial Vault", "service at the church",
                 "service on March 2 2027", "service at 10am",
                 "burial on March 3 2027", "1948 to 2026", "nameplate only"]:
        session_service.add_line(db, sid, company_id=cid, user_id=uid, line=line)
    state = session_service.read_state(db, sid, company_id=cid, user_id=uid)

    # ⚠️ CONTROL. If nothing rendered, "no ISO on screen" and "nothing on screen"
    # are the same green.
    rendered = [r for r in state["surface"]["rows"] if r["value"]]
    assert len(rendered) >= 4, [(r["row_id"], r["value"]) for r in rendered]

    # And the STORED side is untouched, which is half the ruling.
    assert state["values"]["service_date"] == "2027-03-02"
    assert state["values"]["service_time"] == "10:00"
    assert state["values"]["date_of_birth"] == "1948"

    iso = re.compile(r"\d{4}-\d{2}-\d{2}")
    offenders = [
        (r["row_id"], r["value"]) for r in state["surface"]["rows"]
        if r["value"] and iso.search(r["value"])
    ] + [
        (r["row_id"], r["secondary_value"]) for r in state["surface"]["rows"]
        if r["secondary_value"] and iso.search(r["secondary_value"])
    ]
    assert not offenders, f"these rows still show an ISO date: {offenders}"

    shown = {r["row_id"]: r["value"] for r in state["surface"]["rows"]}
    # ⚠️ THREE ROWS SINCE 2026-10-27, NOT ONE, AND THIS IS A BETTER TEST FOR IT. The
    # Service row carried location, day and time until the reshape to
    # one-row-per-question; each is now its own row, so each date and time is asserted
    # where it renders rather than inside a joined string.
    assert shown["service"] == "Church", shown
    assert shown["service_date"] == "Tue Mar 2, 2027", shown
    assert shown["service_time"] == "10:00 AM", shown
    assert shown["dates"] == "1948 — 2026", shown


def test_the_rows_and_the_sets_agree_about_configuration(db, session):
    """⚠️ A DEFECT FOUND BY READING THE OUTPUT OF THE DATE WORK, NOT BY LOOKING FOR IT.

    `read_state` used to re-derive the resolved schema with
    `personalization_config=None` while `evaluate_typed` passed the real availability,
    so ONE RESPONSE CONTRADICTED ITSELF: the `personalization` ROW read
    `not_configured` — "Not configured for this licensee" on a screen — while the SET
    said `answered`. Now the rows read the resolution `evaluate` already performed, so
    passing different arguments is not expressible.
    """
    cid, uid, sid = session
    for line in ["Bronze Triune Burial Vault", "nameplate only"]:
        session_service.add_line(db, sid, company_id=cid, user_id=uid, line=line)
    state = session_service.read_state(db, sid, company_id=cid, user_id=uid)

    assert "personalization" in state["answered"], state["answered"]
    row = next(r for r in state["surface"]["rows"]
               if r["row_id"] == "personalization")
    # ⚠️ THE CLAIM IS ABOUT CONFIGURATION AND IS NOW ASSERTED DIRECTLY. This read
    # `row["state"] == "done"`, which was a PROXY for "the row does not report a
    # configuration problem" and stopped being one on 2026-10-12, when
    # `nameplate_date_format` joined this row by ruling. Choosing a nameplate makes
    # the date format required, this test never answers it, so the row is correctly
    # PARTIAL — started and unfinished. A proxy assertion fails on a change that
    # does not touch the thing it was standing in for.
    assert row["state"] != "not_configured", (
        f"the row reports the licensee's setup as missing while the set says "
        f"personalization is answered: {row}"
    )
    # ⚠️ `done` SINCE 2026-10-27, AND THE REASON IS A ROW SPLIT RATHER THAN A STATE
    # CHANGE. This asserted `partial` because `nameplate_date_format` shared the
    # Personalization row and was required-and-unanswered. One-row-per-question moved
    # the format onto the DATES row ("1948 — 2026 · Years" — it is a property OF the
    # dates), so the Personalization row now holds only the choice and its symbol, and
    # the choice IS answered.
    assert row["state"] == "done", row
    assert row["value"] == "Nameplate Only", row

    # ⚠️ AND THE PARTIAL IS STILL PINNED, ON THE ROW THAT NOW HAS THAT SHAPE. Dropping
    # the assertion because the row changed would retire a guard rather than move it:
    # the claim is that a row with something captured and something required
    # outstanding reads PARTIAL, and the Dates row is where that now happens —
    # `nameplate_date_format` is required once personalization is chosen and this test
    # never answers it.
    dates = next(r for r in state["surface"]["rows"] if r["row_id"] == "dates")
    assert dates["state"] in ("not_mentioned", "needed", "partial"), dates
    assert "nameplate_date_format" in dates["missing_field_ids"], dates

    # ⚠️ THE GENERAL FORM: no row may claim NOT_CONFIGURED for a field the engine
    # placed in `answered`. That is the contradiction, stated over every row.
    answered = set(state["answered"])
    liars = [
        r for r in state["surface"]["rows"]
        if r["state"] == "not_configured" and r["row_id"] in answered
    ]
    assert not liars, liars
