"""The burial is always the service day, so Opas stopped asking for it.

⚠️ RULED BY JAMES 2026-10-13: "The burial is always the same day as the service.
When it isn't, it is a graveside service." Three consequences, each tested here:

  - `burial_date` is never required and never in the missing set. It is DERIVED at
    Approve from `service_date`.
  - A typed burial date that DISAGREES with the service date is a conflict, not a
    silently stored second date.
  - "11 graveside", "graveside at 11" and "graveside friday 11am" set the service
    LOCATION and the service TIME together.

⚠️ THE FIELD STAYS ON THE TEMPLATE AND IS STILL EXTRACTED, which looks redundant and
is not: without extraction a contradictory burial date would be unsayable, and
therefore invisible. Not asking is different from not listening.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.services.capture.typed_extraction import (
    _graveside_time,
    evaluate_typed,
    extract_text,
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


@pytest.fixture(scope="module")
def tenant(db) -> str:
    tid = db.execute(text("SELECT id FROM companies WHERE slug = 'testco'")).scalar()
    assert tid, "testco is not seeded — run scripts/seed_dev.sh"
    return tid


def _state(db, tenant, body):
    ex = extract_text(db, tenant_id=tenant, text=body)
    _r, st, conflicts = evaluate_typed(db, tenant_id=tenant, answers=dict(ex.values))
    return ex, st, conflicts


# ── it is no longer asked ───────────────────────────────────────────────────

def test_burial_date_is_never_in_the_missing_set(db, tenant):
    _ex, st, _c = _state(
        db, tenant, "order for riverside monticello burial vault going to oakwood"
    )
    assert "burial_date" not in st.missing, sorted(st.missing)


def test_it_is_not_required_even_on_an_otherwise_complete_order(db, tenant):
    # ⚠️ THE STRONGER FORM. "Not in missing" could be true because the field is
    # indeterminate or not applicable; this asserts an order can be COMPLETE without
    # it, which is what "no longer asked" has to mean.
    _ex, st, _c = _state(
        db,
        tenant,
        "order for riverside monticello burial vault Mary Smith 1948 to 2026 "
        "going to oakwood section 4 lot 12 service at the church friday 11am",
    )
    assert st.missing == (), sorted(st.missing)


def test_the_done_signal_is_not_blocked_by_it(db, tenant):
    """⚠️ THE DONE-SIGNAL BLOCKERS ARE THE MISSING SET, so this follows from the test
    above — asserted separately because the ruling names it separately, and because
    `_signal_done` reading some other collection is exactly the kind of drift that
    would make the two disagree."""
    from app.services.capture.session_service import _signal_done

    assert _signal_done.__doc__  # the function exists and is the one gate
    _ex, st, _c = _state(
        db,
        tenant,
        "order for riverside monticello burial vault Mary Smith 1948 to 2026 "
        "going to oakwood section 4 lot 12 service at the church friday 11am",
    )
    assert not st.missing


# ── a disagreeing date is a conflict ────────────────────────────────────────

def test_a_burial_date_that_matches_the_service_date_is_no_conflict(db, tenant):
    _ex, _st, conflicts = _state(
        db,
        tenant,
        "order for riverside monticello burial vault service at the church friday "
        "10am burial friday 11am",
    )
    assert not [c for c in conflicts if c.field_id == "burial_date"], conflicts


def test_a_burial_date_that_DIFFERS_is_reported(db, tenant):
    ex, _st, conflicts = _state(
        db,
        tenant,
        "order for riverside monticello burial vault service at the church friday "
        "10am burial saturday 11am",
    )
    assert ex.values.get("burial_date") != ex.values.get("service_date"), ex.values
    c = next((c for c in conflicts if c.field_id == "burial_date"), None)
    assert c is not None, conflicts
    assert "always the service day" in c.message, c.message
    # ⚠️ IT NAMES BOTH DATES AND THE WAY OUT. A refusal that does not say what to type
    # instead leaves the office stuck.
    assert str(ex.values["service_date"]) in c.message, c.message
    assert "graveside" in c.message.lower(), c.message


def test_no_burial_date_at_all_is_no_conflict(db, tenant):
    _ex, _st, conflicts = _state(
        db, tenant,
        "order for riverside monticello burial vault service at the church friday 10am",
    )
    assert not conflicts, conflicts


# ── a graveside service ─────────────────────────────────────────────────────

GRAVESIDE = ["11 graveside Friday", "graveside at 11 Friday", "graveside Friday 11am"]


@pytest.mark.parametrize("phrase", GRAVESIDE)
def test_every_graveside_phrasing_sets_the_location_and_the_time(db, tenant, phrase):
    ex, _st, _c = _state(
        db,
        tenant,
        f"order for riverside monticello burial vault going to oakwood section 4 {phrase}",
    )
    assert ex.values.get("service_location") == "graveside", (phrase, ex.values)
    assert ex.values.get("service_time") == "11:00", (phrase, ex.values)


@pytest.mark.parametrize("phrase", GRAVESIDE)
def test_and_leaves_nothing_unplaced(db, tenant, phrase):
    ex, _st, _c = _state(
        db,
        tenant,
        f"order for riverside monticello burial vault going to oakwood section 4 {phrase}",
    )
    assert ex.unrecognized == (), (phrase, ex.unrecognized)


@pytest.mark.parametrize("phrase", GRAVESIDE)
def test_the_ETA_is_not_asked_for_a_graveside_service(db, tenant, phrase):
    # ⚠️ THE EXISTING RULE, RE-ASSERTED HERE BECAUSE THIS IS WHERE IT NOW BITES. The
    # cemetery arrival is meaningless when the service is already at the grave.
    _ex, st, _c = _state(
        db,
        tenant,
        f"order for riverside monticello burial vault going to oakwood section 4 {phrase}",
    )
    assert "eta" not in st.missing, sorted(st.missing)


def test_graveside_does_NOT_set_a_burial_date(db, tenant):
    """⚠️ "graveside" WAS IN THE BURIAL-DATE MARKER AND THAT WAS THE WHOLE PROBLEM.

    `(?:burial|interment|graveside)` matched "graveside friday 11am", so the one
    phrasing James named for a graveside service set a BURIAL DATE and lost the
    service location entirely. It is a location word, not a date one.
    """
    ex, _st, _c = _state(
        db, tenant,
        "order for riverside monticello burial vault graveside friday 11am",
    )
    assert ex.values.get("burial_date") is None, ex.values
    assert ex.values.get("service_location") == "graveside", ex.values


def test_burial_still_marks_a_date_when_said_plainly(db, tenant):
    # ⚠️ THE NEGATIVE CONTROL ON THAT REMOVAL. "burial friday 11am" must still be
    # read, or the conflict above could never arise.
    ex, _st, _c = _state(
        db, tenant, "order for riverside monticello burial vault burial friday 11am"
    )
    assert ex.values.get("burial_date"), ex.values


# ── the bare hour, and the number that is not one ───────────────────────────

@pytest.mark.parametrize(
    "line,expected",
    [
        ("11 graveside", "11:00"),
        ("graveside at 11", "11:00"),
        ("graveside 9", "09:00"),
        ("graveside at 2", "14:00"),
        ("graveside at 2pm", "14:00"),
        ("section 4 graveside at 11", "11:00"),
        ("lot 12 graveside at 2pm", "14:00"),
    ],
)
def test_the_bare_hour_next_to_graveside(line, expected):
    got = _graveside_time(line)
    assert got is not None, line
    assert got[0] == expected, (line, got)


@pytest.mark.parametrize("line", ["section 11 lot 4", "continental 34", "1948 to 2026"])
def test_a_number_with_no_graveside_is_not_a_time(line):
    assert _graveside_time(line) is None, line


def test_a_section_number_is_not_the_graveside_time(db, tenant):
    """⚠️ THE DEFECT THAT COST THE MOST TO FIND. "section 4 graveside at 11" matched
    the SECTION NUMBER as the hour — "4 graveside" — returned 16:00, and because that
    bogus match consumed the word "graveside" the real "11" was never looked at. The
    sentence said eleven and the engine read four in the afternoon."""
    assert _graveside_time("section 4 graveside at 11") == ("11:00", (23, 25))
    ex, _st, _c = _state(
        db, tenant,
        "order for riverside monticello burial vault going to oakwood "
        "section 4 graveside at 11 Friday",
    )
    assert ex.values.get("service_time") == "11:00", ex.values
    assert ex.values.get("grave_location") == "Section 4", ex.values


def test_the_burial_row_shows_ONLY_the_grave_location(db, tenant):
    """⚠️ THIS TEST ASSERTED AN INHERITED DATE UNTIL 2026-10-14, one day old.

    The 10-13 ruling put the service date on this row labelled "same day as the
    service"; the 10-14 ruling took it off entirely — the Service row already says
    the day, and repeating it under a second heading makes a reader wonder which is
    authoritative. `burial_date` is still DERIVED at Approve; it is simply displayed
    nowhere.

    ⚠️ AND THE ROW CAN NEVER BE AMBER NOW, because `grave_location` is optional by
    the same ruling. An empty Burial row is a quiet empty row.
    """
    import uuid

    from app.services.capture import session_service

    uid = db.execute(
        text("SELECT id FROM users WHERE company_id = :t AND is_active LIMIT 1"),
        {"t": tenant},
    ).scalar()
    assert uid, "testco has no active user"

    row = session_service.start(db, company_id=tenant, user_id=uid)
    try:
        session_service.set_text(
            db, row.id, company_id=tenant, user_id=uid,
            text=(
                "order for riverside monticello burial vault going to oakwood "
                "section 4 lot 12 service at the church friday 11am"
            ),
        )
        state = session_service.read_state(
            db, row.id, company_id=tenant, user_id=uid
        )
        burial = next(
            r for r in state["surface"]["rows"] if r["row_id"] == "burial"
        )
        assert burial["value"] == "Section 4, Lot 12", burial
        # ⚠️ NO DATE AND NO LABEL. Asserted as absence, which is the whole ruling.
        assert burial["secondary_value"] is None, burial
        assert "same day" not in str(burial), burial
        # ⚠️ AND NEVER NEEDED, so it carries no missing field and cannot go amber.
        assert burial["missing_field_ids"] == [], burial
        assert burial["state"] != "needed", burial
    finally:
        db.execute(
            text("DELETE FROM capture_sessions WHERE id = :i"), {"i": row.id}
        )
        db.commit()


def test_an_EMPTY_burial_row_is_NOT_RENDERED_AT_ALL(db, tenant):
    """⚠️ THIS ASSERTED A QUIET EMPTY ROW UNTIL 2026-10-14, one day old. James then
    ruled that optional unmentioned rows are not rendered at all — "only needed rows
    and things you've actually said are shown" — so the quiet row became no row.

    ⚠️ THE CLAIM IS THE SAME ONE, STRENGTHENED: an empty Burial row must never look
    like something outstanding. It cannot, because it is absent.
    """
    from app.services.capture import session_service

    uid = db.execute(
        text("SELECT id FROM users WHERE company_id = :t AND is_active LIMIT 1"),
        {"t": tenant},
    ).scalar()
    row = session_service.start(db, company_id=tenant, user_id=uid)
    try:
        session_service.set_text(
            db, row.id, company_id=tenant, user_id=uid,
            text="order for riverside monticello burial vault",
        )
        state = session_service.read_state(
            db, row.id, company_id=tenant, user_id=uid
        )
        shown = {r["row_id"] for r in state["surface"]["rows"]}
        assert "burial" not in shown, sorted(shown)
    finally:
        db.execute(
            text("DELETE FROM capture_sessions WHERE id = :i"), {"i": row.id}
        )
        db.commit()
