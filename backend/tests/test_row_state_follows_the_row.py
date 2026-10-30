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


def _composed_row(db, session, lines, row_id="cemetery"):
    """Render a COMPOSED row — one that answers several fields — after some lines.

    ⚠️ REPOINTED 2026-10-27 FROM THE `service` ROW, which is no longer composed. The
    reshape to one-row-per-question split it into Service day, Service and Time, so a
    row that could be PARTIAL — something captured, something required outstanding —
    is not among them any more.

    ⚠️ REPOINTED AGAIN 2026-10-30, FROM THE EQUIPMENT ROW TO THE CEMETERY ROW, AND
    THE REASON IS A RULING RATHER THAN A PREFERENCE. The 10-27 choice rested on
    "choosing chairs makes the count required" — `extra_chairs_count` was required
    when `cemetery_equipment == "extra_chairs"`. Rulings A/B' (2026-10-30) removed
    both halves: chairs are no longer a `cemetery_equipment` value, and neither
    `chairs_total` nor `chairs_extra` is ever required. MEASURED after that change:
    NO field on the Equipment row is required, so `unanswered_required` is always
    empty there and the row can never take the PARTIAL branch these tests are about.

    ⚠️ THE CEMETERY ROW IS CHOSEN BY MEASUREMENT TOO, AND IT IS THE ORIGINAL SUBJECT.
    `rows.py` records the measurement in its own words — "with 'eta 11:30' and no
    cemetery named, the Cemetery row rendered **Not configured for this licensee**
    above the time 11:30 AM … It should have read PARTIAL: something captured, the
    required cemetery still missing." One typed line, a rendered value, a required
    field of the same row outstanding: the exact shape of James's screenshot.
    """
    cid, uid, sid = session
    for line in lines:
        session_service.add_line(db, sid, company_id=cid, user_id=uid, line=line)
    state = session_service.read_state(db, sid, company_id=cid, user_id=uid)
    return next(r for r in state["surface"]["rows"] if r["row_id"] == row_id), state


# ── the five states exist and are distinct ──────────────────────────────

def test_partial_is_a_fifth_state_and_not_an_alias():
    assert RowState.PARTIAL.value == "partial"
    assert len({s.value for s in RowState}) == 5, [s.value for s in RowState]


# ── the defect ──────────────────────────────────────────────────────────

def test_a_row_that_captured_something_is_PARTIAL_not_not_mentioned(db, session):
    """⚠️ THE REPORTED DEFECT. One field of a composed row answered, another still
    required: the row holds a value, so it cannot claim nothing was mentioned."""
    row, _ = _composed_row(db, session, ["eta 11:30"])
    assert row["value"] == "11:30", row
    assert row["state"] == RowState.PARTIAL.value, row
    # ⚠️ AND THE OUTSTANDING FIELD IS NAMED, which is what makes PARTIAL different from
    # a row that merely looks half-filled: the cemetery is required and the arrival
    # time the director just gave belongs to the same row.
    assert row["missing_field_ids"] == ["cemetery"], row


def test_a_row_with_NOTHING_is_still_not_mentioned(db, session):
    """⚠️ THE CONTROL ON THE FIX. If PARTIAL leaked into rows holding nothing, every
    untouched row would stop reading as untouched and the pane would look full."""
    row, state = _composed_row(db, session, ["34 inch Continental"])
    assert row["value"] is None, row
    assert row["state"] == RowState.NOT_MENTIONED.value, row
    others = [r for r in state["surface"]["rows"] if r["value"] is None]
    assert others, "no empty rows to check — this control is measuring nothing"
    assert all(r["state"] != RowState.PARTIAL.value for r in others), [
        r for r in others if r["state"] == RowState.PARTIAL.value
    ]


def test_a_complete_row_is_done(db, session):
    """⚠️ STILL THE EQUIPMENT ROW, DELIBERATELY, THOUGH ITS SIBLINGS MOVED TO THE
    CEMETERY ROW. DONE needs a row with a primary AND a secondary both rendered, and
    after rulings A/B' the Equipment row is the only one that has a secondary a
    director can type. The two tests either side need a REQUIRED field outstanding,
    which that row no longer has — so the split is not inconsistency, it is each test
    taking the row that can still produce its state."""
    row, _ = _composed_row(db, session, ["full equipment, 4 extra chairs"],
                           row_id="cemetery_equipment")
    assert row["state"] == RowState.DONE.value, row
    # ⚠️ THE VALUE AND ITS SECONDARY, which is what "complete" means on this row: the
    # bundle chosen and the extras beside it. The old assertion read
    # "Church · Tue Mar 2, 2027 · 10:00 AM" on the Service row — those three facts are
    # three rows now, and each is asserted in `test_date_display.py` where the
    # rendering rules live.
    #
    # ⚠️ "Full Equipment" RATHER THAN "Extra Chairs (Over 8)" SINCE RULING A. Chairs
    # stopped being a `cemetery_equipment` answer, so the bundle the director named is
    # what the primary holds and the count is purely the secondary. Before the ruling
    # this same sentence stored `cemetery_equipment = extra_chairs` and the bundle was
    # LOST — one of the four phrasings measured on 2026-10-30.
    assert row["value"] == "Full Equipment", row
    # ⚠️ "4 extra chairs", NOT "12 chairs (4 extra)", AND THE REASON IS THIS FIXTURE'S
    # TENANT RATHER THAN RULING E BEING WRONG. Ruling E derives the total from the
    # BUNDLE PRODUCT's `products.included_chairs`, and the `session` fixture above
    # builds a company with a user and no products at all — so there is no "Full
    # Equipment" row to read an included count from and `chairs_for_display` refuses
    # to convert between the senses. It says what the director said, in the sense they
    # said it. `test_the_equipment_row_shows_both_chair_numbers.py` seeds the bundles
    # and asserts the derived forms.
    #
    # ⚠️ AND THIS IS THE NEW-TENANT CASE, VISIBLE HERE BY ACCIDENT AND WORTH NAMING.
    # `included_chairs` is set on Sunnycrest's five production rows and by no seed, so
    # every bundle on a fresh tenant reads NULL and every chair display lands on this
    # branch until the onboarding checklist sets them. The row stays honest; it just
    # cannot do the arithmetic.
    assert row["secondary_value"] == "4 extra chairs", row
    assert row["missing_field_ids"] == [], row


def test_a_row_showing_ONLY_a_SECONDARY_is_PARTIAL_not_not_mentioned(db, session):
    """⚠️ DEFECT 3c IN A ROW THAT COULD NOT REACH IT BEFORE 2026-10-30, and it was
    open for the length of this slice.

    `resolve_surface` decided NOT_MENTIONED on `value is None` alone and never looked
    at the secondary — so "12 chairs" with no bundle named rendered "12 chairs" on the
    Equipment row in the not-mentioned style: italic, no check. The same thing James
    photographed on the Service row, one row over.

    ⚠️ IT IS NEW BECAUSE RULING D' MADE THE STATE REACHABLE. Before ruling A a chair
    count could only exist alongside `cemetery_equipment = extra_chairs`, so a
    rendered secondary implied a rendered primary. D' rules that a count with no
    bundle records the count and leaves the bundle open — so the row now has a real
    way to hold a secondary and nothing else.

    ⚠️ AND PARTIAL RATHER THAN DONE, THOUGH NOTHING IN THE ROW IS REQUIRED. What makes
    it unfinished is not the schema but ruling D': `approval.assess` BLOCKS an order
    whose chairs have no bundle rather than billing zero, so the director has to come
    back to this row. DONE would say otherwise.
    """
    row, _ = _composed_row(db, session, ["12 chairs"], row_id="cemetery_equipment")
    assert row["value"] is None, row
    assert row["secondary_value"] == "12 chairs", row
    assert row["state"] == RowState.PARTIAL.value, row
    # ⚠️ AND NO FIELD IS NAMED AS MISSING, which is the honest report: nothing in this
    # row is required. The block comes from `approval.assess`, not from the row.
    assert row["missing_field_ids"] == [], row


def test_PARTIAL_holds_after_the_done_signal_rather_than_becoming_NEEDED(db, session):
    """⚠️ A REAL CHOICE, ASSERTED SO IT IS NOT UNDONE BY TIDYING. Letting NEEDED win
    once the director says "that's everything" would make the row amber and emphatic —
    and would RE-INTRODUCE THE ORIGINAL DEFECT, because NEEDED's prototype value text
    is "Still needed" and the captured value would disappear from the row again. What
    is blocking is carried by the `missing` set and rendered in the header; what the
    ROW must not do is deny the director typed something."""
    cid, uid, sid = session
    # ⚠️ THE CEMETERY ROW, for the reason `_composed_row` records: the Service row is
    # no longer composed, and after rulings A/B' no field on the Equipment row is
    # required — so NEEDED could not have won there and this test would have passed
    # without exercising the choice it names.
    session_service.add_line(db, sid, company_id=cid, user_id=uid, line="eta 11:30")
    session_service.add_line(db, sid, company_id=cid, user_id=uid,
                             line="that's everything")
    state = session_service.read_state(db, sid, company_id=cid, user_id=uid)
    row = next(r for r in state["surface"]["rows"]
               if r["row_id"] == "cemetery")
    assert state["missing"], "the done signal did not report anything missing"
    # ⚠️ THE PRECONDITION THAT MAKES THIS A CHOICE AND NOT A TAUTOLOGY: the row has a
    # required field outstanding, so NEEDED is what it would become if PARTIAL
    # deferred. Asserted, because the subject moved and a row with nothing required
    # would satisfy the two lines below for the wrong reason.
    assert row["missing_field_ids"] == ["cemetery"], row
    assert row["state"] == RowState.PARTIAL.value, row
    assert row["value"] == "11:30", row


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
    # ⚠️ THE CEMETERY ROW AND THE ROW LAYER DIRECTLY, SINCE 2026-10-27. The defect was
    # on the Service row's two overlapping ComposedSources, and that row now carries
    # one question. The cemetery row still composes three fields, and the claim —
    # a field the director gave must not vanish when another arrives — is unchanged.
    #
    # ⚠️ RENDERED RATHER THAN TYPED, because that is where the defect was. One line
    # ("st marys cemetery") sets the name AND the town together, so typing cannot
    # produce the middle step this test exists for; building the answers by hand can.
    from app.services.capture import template_for, SALES_ORDER
    from app.services.capture.rows import resolve_surface
    from app.services.capture.schema import resolve_schema
    from app.services.capture.surfaces import CAPTURE_SALES_ORDER

    def cemetery_row(answers):
        fields = resolve_schema(
            vault_product_id=None, personalization_config=None,
            platform_fields=template_for(SALES_ORDER), answers=answers,
        )
        out = resolve_surface(CAPTURE_SALES_ORDER, fields, answers)
        return next(r for r in out.rows if r.row_id == "cemetery")

    # the name alone
    assert cemetery_row({"cemetery": "St. Mary's Cemetery"}).value == "St. Mary's Cemetery"
    # ⚠️ THE MIDDLE STEP, WHICH IS THE WHOLE TEST: the town arrives and the NAME is
    # still there. The original defect showed "Church", then "2027-03-02" — a field the
    # director had given, gone, with nothing reported.
    both = cemetery_row({"cemetery": "St. Mary's Cemetery", "cemetery_city": "Skaneateles"})
    assert both.value == "St. Mary's Cemetery · Skaneateles", both


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
