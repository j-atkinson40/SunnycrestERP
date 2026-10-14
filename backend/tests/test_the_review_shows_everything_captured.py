"""Every captured field appears on the Review, and unmentioned optional rows do not.

⚠️ WALK NOTE, James, production 2026-10-14 09:24, screenshot of the Review:
"Smith" was captured and absent from the Review.

TWO CAUSES, and only the first is obvious:

  1. The summary surface puts the decedent in a `SubjectSlot` — "Smith" over
     "1948 — 2026" above the grid, from the prototype — and `read_state` serialized
     only `rows`. The value was computed and thrown away at the API, so the pane
     could not render it however it tried.
  2. Three capturable fields had NOWHERE on that surface at all:
     `cemetery_city`, `grave_location`, `nameplate_date_format`. A director could say
     them, the engine captured them, and the Review had no slot to show them in.

⚠️ THE STRUCTURAL TEST IS THE ONE THAT WILL CATCH THE NEXT FIELD. A rendering check
over one sentence passes as long as that sentence happens to mention everything; the
coverage assertion fails the moment a field is added without a home.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.services.capture import session_service as ss
from app.services.capture.rows import RowState, _source_field_ids, row_field_ids
from app.services.capture.schema import PLATFORM_DEFAULT_FIELDS
from app.services.capture.surfaces import CAPTURE_SALES_ORDER, SUMMARY_SALES_ORDER

#: ⚠️ THE ONE DELIBERATE OMISSION, and it is a ruling rather than a gap. James ruled
#: 2026-10-14 that the burial is always the service day, so `burial_date` is derived
#: at Approve and displayed nowhere — the Service row already says the day.
DERIVED_AND_NOT_SHOWN = {"burial_date"}


def _covered(surface) -> set[str]:
    ids: set[str] = set()
    for r in surface.rows:
        ids |= set(row_field_ids(r))
    if surface.subject is not None:
        for src in surface.subject.primary + surface.subject.secondary:
            ids |= set(_source_field_ids(src))
    return ids


def test_every_capturable_field_has_a_place_on_the_REVIEW():
    """⚠️ THE SUBJECT SLOT COUNTS, which is the whole point of computing coverage over
    rows AND subject. `deceased_name` is only ever on the subject, so a check that
    walked rows alone would call it an orphan and a check that ignored the subject
    would have called the Review complete while it omitted the name."""
    template = {f.field_id for f in PLATFORM_DEFAULT_FIELDS}
    missing = sorted(template - _covered(SUMMARY_SALES_ORDER) - DERIVED_AND_NOT_SHOWN)
    assert missing == [], (
        f"these fields can be captured and have no place on the Review, so a "
        f"director who says them sees nothing back: {missing}"
    )


def test_and_on_the_CAPTURE_surface_too():
    # ⚠️ ASSERTED SEPARATELY BECAUSE THE TWO SURFACES DRIFTED ONCE. The capture
    # surface was complete while the summary was missing three fields — the gap was
    # invisible to any check that looked at only one of them.
    template = {f.field_id for f in PLATFORM_DEFAULT_FIELDS}
    missing = sorted(template - _covered(CAPTURE_SALES_ORDER) - DERIVED_AND_NOT_SHOWN)
    assert missing == [], missing


def test_the_subject_is_where_the_name_lives():
    """⚠️ PINNED, because the fix is easy to undo by "tidying" the decedent into a
    row. If it moves, this test should be updated deliberately rather than the name
    quietly vanishing from the Review again."""
    subj = SUMMARY_SALES_ORDER.subject
    assert subj is not None
    assert "deceased_name" in {
        i for src in subj.primary for i in _source_field_ids(src)
    }


# ── against the real engine ─────────────────────────────────────────────────


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
    tid = db.execute(
        text("SELECT id FROM companies WHERE slug = 'sunnycrest'")
    ).scalar()
    assert tid, "no sunnycrest tenant — this suite must not skip"
    return tid


@pytest.fixture(scope="module")
def world(db, tenant):
    """The records the sentence names, ensured — CI's tenant is bare."""
    made: list[tuple[str, str]] = []

    def ensure(table, where, params, insert):
        if db.execute(text(f"SELECT id FROM {table} WHERE {where}"), params).scalar():
            return
        rid = str(uuid.uuid4())
        db.execute(text(insert), {**params, "i": rid})
        made.append((table, rid))

    ensure("company_entities", "company_id = :t AND name = :n",
           {"t": tenant, "n": "Hopkins Funeral Home"},
           "INSERT INTO company_entities (id, company_id, name) VALUES (:i, :t, :n)")
    ensure("cemeteries", "company_id = :t AND name = :n",
           {"t": tenant, "n": "St. Mary's Cemetery"},
           "INSERT INTO cemeteries (id, company_id, name, city, state, is_active) "
           "VALUES (:i, :t, :n, 'Skaneateles', 'NY', true)")
    db.commit()
    yield True
    for table, rid in made:
        db.execute(text(f"DELETE FROM {table} WHERE id = :i"), {"i": rid})
    db.commit()


@pytest.fixture
def user_id(db, tenant):
    from app.models.role import Role
    from app.models.user import User

    role = db.query(Role).filter(Role.company_id == tenant).first()
    u = User(
        id=str(uuid.uuid4()), company_id=tenant,
        email=f"rev-{uuid.uuid4().hex[:8]}@example.com",
        username=f"rev{uuid.uuid4().hex[:8]}",
        hashed_password="x", first_name="Review", last_name="Test",
        is_active=True, role_id=role.id if role else None,
    )
    db.add(u)
    db.commit()
    try:
        yield u.id
    finally:
        db.rollback()
        for sql in ("DELETE FROM audit_logs WHERE user_id = :u",
                    "DELETE FROM capture_sessions WHERE user_id = :u",
                    "DELETE FROM users WHERE id = :u"):
            try:
                db.execute(text(sql), {"u": u.id})
                db.commit()
            except Exception:
                db.rollback()


#: James's 09:24 sentence with the day he had to add.
HIS = (
    "order for hopkins monticello St. marys full equipment 11 am church "
    "last name smith friday"
)


def _review(db, tenant, user_id, body=HIS):
    row = ss.start(db, company_id=tenant, user_id=user_id)
    ss.set_text(db, row.id, company_id=tenant, user_id=user_id, text=body)
    ss.complete(db, row.id, company_id=tenant, user_id=user_id)
    return row, ss.read_state(db, row.id, company_id=tenant, user_id=user_id)


def test_the_review_shows_the_deceased_name(db, tenant, world, user_id):
    row, st = _review(db, tenant, user_id)
    try:
        assert st["status"] == "review", st["status"]
        assert st["surface"]["subject_primary"] == "Smith", st["surface"]
    finally:
        db.execute(text("DELETE FROM capture_sessions WHERE id = :i"), {"i": row.id})
        db.commit()


def test_EVERY_CAPTURED_VALUE_APPEARS_SOMEWHERE_ON_THE_REVIEW(db, tenant, world, user_id):
    """The invariant item 4 asks for, over a real sentence.

    ⚠️ IT COMPARES THE CAPTURED KEYS AGAINST WHAT THE SURFACE SOURCES, not against
    the rendered strings. An enum renders as its label and a date as "Fri Oct 16,
    2026", so searching the text for the stored value would fail on exactly the
    fields that are rendered correctly.
    """
    row, st = _review(db, tenant, user_id)
    try:
        captured = set(st["values"])
        shown = _covered(SUMMARY_SALES_ORDER)
        unshown = sorted(captured - shown - DERIVED_AND_NOT_SHOWN)
        assert unshown == [], (
            f"captured and absent from the Review: {unshown}"
        )
    finally:
        db.execute(text("DELETE FROM capture_sessions WHERE id = :i"), {"i": row.id})
        db.commit()


def test_the_grave_location_reaches_the_review(db, tenant, world, user_id):
    # ⚠️ ONE OF THE THREE THAT HAD NO HOME. Asserted through the render, because the
    # coverage test above would pass if it were sourced by a row that never shows.
    row, st = _review(
        db, tenant, user_id, HIS + " section 4 lot 12"
    )
    try:
        assert st["values"].get("grave_location") == "Section 4, Lot 12", st["values"]
        text_of = " | ".join(
            f"{r['value']} {r['secondary_value']}" for r in st["surface"]["rows"]
        )
        assert "Section 4, Lot 12" in text_of, text_of
    finally:
        db.execute(text("DELETE FROM capture_sessions WHERE id = :i"), {"i": row.id})
        db.commit()


# ── optional rows are not rendered until mentioned ──────────────────────────


def test_an_unmentioned_OPTIONAL_row_is_not_rendered(db, tenant, world, user_id):
    """⚠️ RULED 2026-10-14: "only needed rows and things you've actually said are
    shown". Nine empty rows on a fresh order read as work outstanding, and three of
    them — dates, grave location, contact — can never be outstanding."""
    row = ss.start(db, company_id=tenant, user_id=user_id)
    try:
        ss.set_text(db, row.id, company_id=tenant, user_id=user_id, text=HIS)
        st = ss.read_state(db, row.id, company_id=tenant, user_id=user_id)
        shown = {r["row_id"] for r in st["surface"]["rows"]}
        for hidden in ("contact", "dates", "burial"):
            assert hidden not in shown, (hidden, sorted(shown))
    finally:
        db.execute(text("DELETE FROM capture_sessions WHERE id = :i"), {"i": row.id})
        db.commit()


def test_and_APPEARS_the_moment_something_is_captured_for_it(db, tenant, world, user_id):
    # ⚠️ THE POSITIVE CONTROL, AND WITHOUT IT A BUILD THAT DROPPED THESE ROWS
    # PERMANENTLY WOULD PASS. The ruling says they appear as soon as there is
    # something to show.
    row = ss.start(db, company_id=tenant, user_id=user_id)
    try:
        ss.set_text(db, row.id, company_id=tenant, user_id=user_id,
                    text=HIS + " section 4 lot 12")
        st = ss.read_state(db, row.id, company_id=tenant, user_id=user_id)
        burial = next(
            (r for r in st["surface"]["rows"] if r["row_id"] == "burial"), None
        )
        assert burial is not None, [r["row_id"] for r in st["surface"]["rows"]]
        assert burial["value"] == "Section 4, Lot 12", burial
    finally:
        db.execute(text("DELETE FROM capture_sessions WHERE id = :i"), {"i": row.id})
        db.commit()


def test_a_REQUIRED_unanswered_row_is_still_rendered(db, tenant, world, user_id):
    """⚠️ THE CONDITION THAT MATTERS MOST. A required-and-unanswered row is
    `not_mentioned` too until a completion is attempted — so a naive "hide empty
    rows" would have hidden exactly the rows James needs to see."""
    row = ss.start(db, company_id=tenant, user_id=user_id)
    try:
        ss.set_text(db, row.id, company_id=tenant, user_id=user_id,
                    text="order for hopkins monticello")
        st = ss.read_state(db, row.id, company_id=tenant, user_id=user_id)
        shown = {r["row_id"]: r for r in st["surface"]["rows"]}
        assert "service" in shown, sorted(shown)
        assert shown["service"]["missing_field_ids"], shown["service"]
        assert shown["service"]["value"] is None, shown["service"]
    finally:
        db.execute(text("DELETE FROM capture_sessions WHERE id = :i"), {"i": row.id})
        db.commit()


def test_a_CONFLICTED_row_is_never_hidden(db, tenant, world, user_id):
    """⚠️ THE ROW THE DIRECTOR MOST NEEDS. "Monticello Burial Vault doesn't offer
    Nameplate Only" exists precisely because they DID mention it — and
    `personalization` is `not_applicable` on that vault, so without the conflict
    carve-out the hide rule would have taken the row away with the message on it."""
    row = ss.start(db, company_id=tenant, user_id=user_id)
    try:
        ss.set_text(db, row.id, company_id=tenant, user_id=user_id,
                    text="order for hopkins monticello nameplate only")
        st = ss.read_state(db, row.id, company_id=tenant, user_id=user_id)
        assert [c for c in st["conflicts"] if c["field_id"] == "personalization"], st["conflicts"]
        shown = {r["row_id"] for r in st["surface"]["rows"]}
        assert "personalization" in shown, sorted(shown)
    finally:
        db.execute(text("DELETE FROM capture_sessions WHERE id = :i"), {"i": row.id})
        db.commit()


def test_a_not_configured_row_is_not_hidden_either():
    # ⚠️ IT IS NOT AN EMPTY ROW, IT IS A REPORT. `not_configured` tells the licensee
    # their own setup is incomplete; hiding it would hide the only notice they get.
    assert RowState.NOT_CONFIGURED is not RowState.NOT_MENTIONED
