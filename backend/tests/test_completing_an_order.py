"""Finishing an order: one action, three entrances, and nothing lost on the way.

⚠️ WALK NOTE, James, production 2026-10-14 07:27. He typed
"…11 am church last name smith approve" and got a "2 needed" pill, no row
highlighted, and **approve** under Not Understood.

THREE SEPARATE DEFECTS IN ONE SCREENSHOT, and this file covers the first two:

  1. "approve" was only stripped from the text when the session was ALREADY in
     review, and reaching review needed a separate "that's everything". So the word
     stayed in the order text, the extractor could place it nowhere, and it was
     reported as unreadable — a word the engine acts on also being a word it cannot
     read.
  2. The pill counted missing FIELDS while the amber belongs to ROWS. His two were
     `service_date` (Service row) and `grave_location` (Burial row), and neither was
     highlighted at all.

⚠️ `grave_location` WAS ONE OF THE TWO, which is worth stating because James's own
note says grave location is never needed. It WAS required — by the constructor's
default, never by a ruling — and it is optional as of this ruling.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.models.capture_session import (
    STATUS_APPROVED,
    STATUS_CAPTURING,
    STATUS_REVIEW,
)
from app.services.capture import session_service as ss


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
    """The records James's sentence names. Ensured, not assumed — CI's tenant is bare."""
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
        email=f"compl-{uuid.uuid4().hex[:8]}@example.com",
        username=f"compl{uuid.uuid4().hex[:8]}",
        hashed_password="x", first_name="Complete", last_name="Test",
        is_active=True, role_id=role.id if role else None,
    )
    db.add(u)
    db.commit()
    try:
        yield u.id
    finally:
        db.rollback()
        for sql in (
            "DELETE FROM audit_logs WHERE user_id = :u",
            "DELETE FROM capture_sessions WHERE user_id = :u",
            "DELETE FROM users WHERE id = :u",
        ):
            try:
                db.execute(text(sql), {"u": u.id})
                db.commit()
            except Exception:
                db.rollback()


#: James's exact sentence, 07:27.
HIS = (
    "order for hopkins monticello St. marys full equipment 11 am church "
    "last name smith approve"
)


def _session(db, tenant, user_id, body):
    row = ss.start(db, company_id=tenant, user_id=user_id)
    return ss.set_text(db, row.id, company_id=tenant, user_id=user_id, text=body)


# ── the two "needed" in his sentence ────────────────────────────────────────

def test_the_only_thing_missing_is_the_SERVICE_DATE(db, tenant, world, user_id):
    """⚠️ IT WAS TWO AND IS NOW ONE. Measured 2026-10-14 before this ruling:
    `['grave_location', 'service_date']`. Grave location was required by the
    constructor's default — no ruling ever argued for it — and James ruled it
    optional, so only the service date is outstanding."""
    row = _session(db, tenant, user_id, HIS)
    st = ss.read_state(db, row.id, company_id=tenant, user_id=user_id)
    assert st["missing"] == ["service_date"], st["missing"]
    assert st["missing_labels"] == ["Service date"], st["missing_labels"]


def test_grave_location_is_never_needed(db, tenant, world, user_id):
    row = _session(db, tenant, user_id, HIS)
    st = ss.read_state(db, row.id, company_id=tenant, user_id=user_id)
    assert "grave_location" not in st["missing"], st["missing"]
    burial = next(r for r in st["surface"]["rows"] if r["row_id"] == "burial")
    assert burial["missing_field_ids"] == [], burial
    assert burial["state"] != "needed", burial


# ── "approve" is understood, never unreadable ───────────────────────────────

@pytest.mark.parametrize(
    "phrase",
    ["approve", "done", "that's it", "that's everything", "complete", "ready"],
)
def test_no_completion_WORD_is_ever_unreadable(db, tenant, world, user_id, phrase):
    """⚠️ THE DEFECT, GENERALISED. Only `approve` was reported, but every one of these
    would have been if a director had reached review a different way — the phrase was
    stripped from the text in one status and left in it in the other."""
    row = _session(db, tenant, user_id, f"order for hopkins monticello {phrase}")
    st = ss.read_state(db, row.id, company_id=tenant, user_id=user_id)
    assert phrase not in st["unrecognized"], st["unrecognized"]
    assert st["unrecognized"] == [], st["unrecognized"]


def test_his_sentence_leaves_nothing_unreadable(db, tenant, world, user_id):
    row = _session(db, tenant, user_id, HIS)
    st = ss.read_state(db, row.id, company_id=tenant, user_id=user_id)
    assert st["unrecognized"] == [], st["unrecognized"]


def test_the_word_is_still_order_text_in_the_MIDDLE_of_a_sentence(db, tenant, world, user_id):
    # ⚠️ TRAILING ONLY, AND THIS IS THE GUARD ON THAT. "go" and "yes" are ordinary
    # words; a completion phrase is one a director puts at the END. Stripping them
    # anywhere would quietly delete words from the middle of an order.
    row = _session(
        db, tenant, user_id, "order for hopkins go to St. marys monticello"
    )
    st = ss.read_state(db, row.id, company_id=tenant, user_id=user_id)
    assert st["status"] == STATUS_CAPTURING, st["status"]
    assert st["values"].get("cemetery") == "St. Mary's Cemetery", st["values"]


# ── completing ──────────────────────────────────────────────────────────────

def test_completing_an_incomplete_order_STAYS_PUT_and_names_the_gap(
    db, tenant, world, user_id
):
    """⚠️ IT DOES NOT ADVANCE AND DOES NOT RAISE. A summary whose only content is a
    refusal would be a worse screen than the one the director is already on; the rows
    go amber where the gap is."""
    row = _session(db, tenant, user_id, HIS)
    row = ss.complete(db, row.id, company_id=tenant, user_id=user_id)
    assert row.status == STATUS_CAPTURING, row.status
    st = ss.read_state(db, row.id, company_id=tenant, user_id=user_id)
    assert st["missing_labels"] == ["Service date"]
    amber = [r["row_id"] for r in st["surface"]["rows"] if r["missing_field_ids"]]
    assert amber == ["service"], amber


def test_the_pill_count_equals_the_number_of_amber_ROWS(db, tenant, world, user_id):
    """⚠️ THE RULING'S OWN TEST, and the case that distinguishes the two rules is two
    missing fields on ONE row. A sentence with no day and no time leaves
    `service_date` AND `service_time` outstanding, both on the Service row — two
    fields, one amber row."""
    row = _session(
        db, tenant, user_id,
        "order for hopkins monticello St. marys full equipment church last name smith",
    )
    st = ss.read_state(db, row.id, company_id=tenant, user_id=user_id)
    assert set(st["missing"]) == {"service_date", "service_time"}, st["missing"]
    amber = [r["row_id"] for r in st["surface"]["rows"] if r["missing_field_ids"]]
    assert amber == ["service"], amber
    assert len(amber) == 1 and len(st["missing"]) == 2


def test_adding_the_day_reaches_the_summary(db, tenant, world, user_id):
    row = _session(db, tenant, user_id, HIS.replace(" approve", " friday approve"))
    assert row.status == STATUS_REVIEW, row.status
    st = ss.read_state(db, row.id, company_id=tenant, user_id=user_id)
    assert st["missing"] == []
    assert st["can_approve"] is True, st["blockers"]


def test_a_typed_completion_phrase_reports_the_attempt(db, tenant, world, user_id):
    # ⚠️ THE CLIENT CANNOT SEE A SERVER-SIDE DETECTION. The rows turn amber on an
    # attempt, and a typed phrase is only visible to the server — so the response has
    # to say an attempt happened.
    row = _session(db, tenant, user_id, HIS)
    assert getattr(row, "_completion_attempt", False) is True

    quiet = _session(db, tenant, user_id, "order for hopkins monticello")
    assert getattr(quiet, "_completion_attempt", False) is False


def test_complete_from_review_APPROVES(db, tenant, world, user_id):
    """⚠️ THE SAME PHRASE, THE SECOND TIME. From capture it shows the summary; from
    the summary it approves. The office looks at the lines and the total before an
    order exists, and one typed word must not skip that."""
    from app.services.capture.approval import assess

    row = _session(db, tenant, user_id, HIS.replace(" approve", " friday approve"))
    assert row.status == STATUS_REVIEW
    a = ss.assess_approval(db, row)
    if not a.ready:
        pytest.skip(f"sunnycrest cannot bill this order here: {a.blockers}")
    row = ss.complete(db, row.id, company_id=tenant, user_id=user_id)
    oid = row.sales_order_id
    try:
        assert row.status == STATUS_APPROVED, row.status
        assert oid
        assert assess  # imported to pin the module the readiness came from
    finally:
        if oid:
            db.execute(text("UPDATE capture_sessions SET sales_order_id = NULL "
                            "WHERE id = :i"), {"i": row.id})
            db.execute(text("DELETE FROM order_personalization_tasks WHERE order_id = :i"),
                       {"i": oid})
            db.execute(text("DELETE FROM sales_order_lines WHERE sales_order_id = :i"),
                       {"i": oid})
            db.execute(text("DELETE FROM sales_orders WHERE id = :i"), {"i": oid})
            db.commit()


# ── the name, title-cased for display only ──────────────────────────────────

def test_a_lowercase_surname_DISPLAYS_capitalised(db, tenant, world, user_id):
    row = _session(db, tenant, user_id, HIS)
    st = ss.read_state(db, row.id, company_id=tenant, user_id=user_id)
    name_row = next(
        r for r in st["surface"]["rows"] if r["row_id"] == "deceased_name"
    )
    assert name_row["value"] == "Smith", name_row


def test_but_is_STORED_as_typed(db, tenant, world, user_id):
    """⚠️ DISPLAY ONLY, BY RULING. The stored value is what the director typed, so
    nothing downstream inherits a guess about capitalisation."""
    row = _session(db, tenant, user_id, HIS)
    assert dict(row.values or {})["deceased_name"] == "smith", row.values
    st = ss.read_state(db, row.id, company_id=tenant, user_id=user_id)
    assert st["values"]["deceased_name"] == "smith", st["values"]


def test_a_name_the_director_capitalised_is_LEFT_ALONE(db, tenant, world, user_id):
    # ⚠️ `.title()` WOULD HAVE BROKEN THESE. "deSoto" and "MacLeod" carry
    # capitalisation that is information; only an all-lowercase word is touched.
    from app.services.capture.rows import write_for_a_human

    assert write_for_a_human("deSoto", "name") == "deSoto"
    assert write_for_a_human("MacLeod", "name") == "MacLeod"
    assert write_for_a_human("O'Brien", "name") == "O'Brien"
    assert write_for_a_human("mary smith", "name") == "Mary Smith"
    assert write_for_a_human("smith", "name") == "Smith"
