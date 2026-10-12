"""Row state follows what the row actually holds — and two defects in one row.

⚠️ DEFECT 3c, FROM JAMES'S PRODUCTION WALK. He typed "...service at the church" and
the Service row showed **"Church" in the not-mentioned style** — italic, no check.
`rows.py` read "something required in this row is still missing" and returned
NOT_MENTIONED without looking at whether anything had rendered. Ruled 2026-10-12: row
style must follow row state, so the STATE had to learn the case.

`PARTIAL` means: this row has captured something and is not finished. The server stays
the only thing deciding — a pane that inferred "has a value but the state says
not-mentioned, so style it differently" would be a second source of truth for
completeness.

⚠️ AND A SECOND DEFECT, NOT IN THE SCREENSHOT, FOUND WHILE VERIFYING THE FIRST. The
same row expressed its location fallback as TWO overlapping `ComposedSource`s, each
also carrying the date and the time — so the first started yielding the moment a DATE
existed and **the location silently vanished from the row**. Measured: "Church"
became "2027-03-02" when the date arrived. Fixed with `FirstOf`, which makes the
fallback expressible inside a composition instead of emerging from the interaction of
two alternatives.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.services.capture import session_service
from app.services.capture.rows import (
    ComposedSource,
    FieldSource,
    FirstOf,
    RowState,
    _render,
    _source_field_ids,
)


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


@pytest.fixture
def session(db):
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    sp = db.begin_nested()
    slug = f"rowstate-{uuid.uuid4().hex[:8]}"
    co = Company(id=str(uuid.uuid4()), name=slug, slug=slug, vertical="manufacturing")
    db.add(co)
    db.flush()
    role = Role(id=str(uuid.uuid4()), company_id=co.id, name="Admin", slug="admin")
    db.add(role)
    db.flush()
    u = User(id=str(uuid.uuid4()), company_id=co.id, email=f"{slug}@example.com",
             first_name="R", last_name="S", hashed_password="x", role_id=role.id)
    db.add(u)
    db.flush()
    row = session_service.start(db, company_id=co.id, user_id=u.id)
    yield co.id, u.id, row.id
    sp.rollback()


def _service_row(db, session, lines):
    cid, uid, sid = session
    for line in lines:
        session_service.add_line(db, sid, company_id=cid, user_id=uid, line=line)
    state = session_service.read_state(db, sid, company_id=cid, user_id=uid)
    return next(r for r in state["surface"]["rows"] if r["row_id"] == "service"), state


# ── the five states exist and are distinct ──────────────────────────────

def test_partial_is_a_fifth_state_and_not_an_alias():
    assert RowState.PARTIAL.value == "partial"
    assert len({s.value for s in RowState}) == 5, [s.value for s in RowState]


# ── the defect ──────────────────────────────────────────────────────────

def test_a_row_that_captured_something_is_PARTIAL_not_not_mentioned(db, session):
    """⚠️ THE REPORTED DEFECT. One field of a composed row answered, another still
    required: the row holds a value, so it cannot claim nothing was mentioned."""
    row, _ = _service_row(db, session, ["service at the church"])
    assert row["value"] == "Church", row
    assert row["state"] == RowState.PARTIAL.value, row


def test_a_row_with_NOTHING_is_still_not_mentioned(db, session):
    """⚠️ THE CONTROL ON THE FIX. If PARTIAL leaked into rows holding nothing, every
    untouched row would stop reading as untouched and the pane would look full."""
    row, state = _service_row(db, session, ["34 inch Continental"])
    assert row["value"] is None, row
    assert row["state"] == RowState.NOT_MENTIONED.value, row
    others = [r for r in state["surface"]["rows"] if r["value"] is None]
    assert others, "no empty rows to check — this control is measuring nothing"
    assert all(r["state"] != RowState.PARTIAL.value for r in others), [
        r for r in others if r["state"] == RowState.PARTIAL.value
    ]


def test_a_complete_row_is_done(db, session):
    row, _ = _service_row(db, session, [
        "service at the church", "service on March 2 2027", "service at 10am",
    ])
    assert row["state"] == RowState.DONE.value, row
    assert row["value"] == "Church · 2027-03-02 · 10:00", row


def test_PARTIAL_holds_after_the_done_signal_rather_than_becoming_NEEDED(db, session):
    """⚠️ A REAL CHOICE, ASSERTED SO IT IS NOT UNDONE BY TIDYING. Letting NEEDED win
    once the director says "that's everything" would make the row amber and emphatic —
    and would RE-INTRODUCE THE ORIGINAL DEFECT, because NEEDED's prototype value text
    is "Still needed" and the captured value would disappear from the row again. What
    is blocking is carried by the `missing` set and rendered in the header; what the
    ROW must not do is deny the director typed something."""
    cid, uid, sid = session
    session_service.add_line(db, sid, company_id=cid, user_id=uid,
                             line="service at the church")
    session_service.add_line(db, sid, company_id=cid, user_id=uid,
                             line="that's everything")
    state = session_service.read_state(db, sid, company_id=cid, user_id=uid)
    row = next(r for r in state["surface"]["rows"] if r["row_id"] == "service")
    assert state["missing"], "the done signal did not report anything missing"
    assert row["state"] == RowState.PARTIAL.value, row
    assert row["value"] == "Church", row


def test_an_EMPTY_row_does_become_NEEDED_after_the_done_signal(db, session):
    """The other half: NEEDED still exists and still fires, for rows holding nothing.
    Without this, removing the PARTIAL clause entirely would pass the test above."""
    cid, uid, sid = session
    session_service.add_line(db, sid, company_id=cid, user_id=uid,
                             line="that's everything")
    state = session_service.read_state(db, sid, company_id=cid, user_id=uid)
    needed = [r for r in state["surface"]["rows"]
              if r["state"] == RowState.NEEDED.value]
    assert needed, [
        (r["row_id"], r["state"], r["value"]) for r in state["surface"]["rows"]
    ]
    assert all(r["value"] is None for r in needed), needed


# ── the second defect: the location must survive the date ───────────────

def test_the_location_is_not_lost_when_the_date_arrives(db, session):
    """⚠️ THE DEFECT `FirstOf` EXISTS FOR, AND THE MIDDLE STEP IS THE WHOLE TEST.
    With two overlapping ComposedSources this row showed "Church", then "2027-03-02"
    — a field the director had given, gone, with nothing reported."""
    cid, uid, sid = session
    session_service.add_line(db, sid, company_id=cid, user_id=uid,
                             line="service at the church")
    session_service.add_line(db, sid, company_id=cid, user_id=uid,
                             line="service on March 2 2027")
    state = session_service.read_state(db, sid, company_id=cid, user_id=uid)
    row = next(r for r in state["surface"]["rows"] if r["row_id"] == "service")
    assert row["value"] == "Church · 2027-03-02", row


def test_firstof_renders_the_first_child_that_yields():
    src = FirstOf((FieldSource("a"), FieldSource("b")))
    assert _render(src, {"b": "second"}, {}) == "second"
    assert _render(src, {"a": "first", "b": "second"}, {}) == "first"
    assert _render(src, {}, {}) is None


def test_firstof_composes_without_swallowing_its_siblings():
    """⚠️ THE SHAPE THE REAL ROW USES. A fallback INSIDE a composition, so the other
    parts still join on."""
    src = ComposedSource(
        (FirstOf((FieldSource("other"), FieldSource("loc"))), FieldSource("date")),
        join=" · ",
    )
    assert _render(src, {"loc": "Church", "date": "2027-03-02"}, {}) == (
        "Church · 2027-03-02"
    )
    assert _render(src, {"date": "2027-03-02"}, {}) == "2027-03-02"


def test_source_field_ids_walks_into_firstof():
    """⚠️ LOAD-BEARING FOR THE STATE, NOT JUST FOR BOOKKEEPING. `row_field_ids` feeds
    the required-field computation; if it did not see inside `FirstOf`, the Service
    row's location fields would vanish from `unanswered_required` and the row would
    report DONE while the location was still missing."""
    src = ComposedSource(
        (FirstOf((FieldSource("other"), FieldSource("loc"))), FieldSource("date")),
    )
    assert set(_source_field_ids(src)) == {"other", "loc", "date"}
