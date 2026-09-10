"""The live-to-settled transition.

⚠️ THE CLAIM UNDER TEST IS THAT THE RECORD SAYS WHAT HAPPENED. A cancelled task
reads as cancelled, not as completed and not as silence. Everything else here
exists to make that claim falsifiable.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, time, timedelta, timezone

import pytest
from zoneinfo import ZoneInfo

from app.models.daily_note import DailyNote
from app.models.note_fragment_render import NoteFragmentRender
from app.models.note_settled_record import NoteSettledRecord
from app.services.note.settling import (
    settle_note, split_instance_key, tenant_day_window,
)
from app.services.tasks.service import create_task_with_provenance, transition_task
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture

canonical_tenant = make_canonical_tenant_fixture(
    child_tables=(
        "note_settled_records", "note_fragment_deferrals",
        "note_fragment_renders", "daily_notes",
    )
)


@pytest.fixture
def db_session():
    from app.database import SessionLocal
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture
def user(db_session):
    from app.models.user import User
    u = db_session.query(User).filter(User.company_id == TESTCO_ID).first()
    if u is None:
        pytest.skip("no user on the canonical tenant")
    return u


@pytest.fixture(autouse=True)
def _isolate(db_session, user):
    """⚠️ `_task_reaching` COMMITS, and settling COUNTS TASKS.

    Without purging them, a task completed by an earlier test is counted by the
    next one — and the test that suffers most is the CONTROL, which asserts a
    quiet day settles to nothing. A leaked task makes the control fail while
    every positive test passes, which reads as the control being wrong.
    """
    from sqlalchemy import text as _sql

    def purge():
        for model in (NoteSettledRecord, NoteFragmentRender):
            db_session.query(model).filter(model.user_id == user.id).delete(
                synchronize_session=False
            )
        db_session.query(DailyNote).filter(DailyNote.user_id == user.id).delete(
            synchronize_session=False
        )
        # This file's tasks, by the title it stamps on them.
        db_session.execute(_sql("""
            DELETE FROM vault_items WHERE id IN (
              SELECT td.vault_item_id FROM task_details td
              JOIN vault_items vi ON vi.id = td.vault_item_id
              WHERE vi.company_id = :cid AND vi.title = 'settling fixture')
        """), {"cid": user.company_id})
        db_session.execute(_sql("""
            DELETE FROM agent_anomalies WHERE resolved_by = :uid
        """), {"uid": user.id})
        db_session.commit()
    purge()
    yield
    db_session.rollback()
    purge()


def _note(db, user, d: date) -> DailyNote:
    n = DailyNote(
        id=str(uuid.uuid4()), company_id=user.company_id, user_id=user.id,
        note_date=d, created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(n); db.flush()
    return n


def _rendered_prompt(db, user, note, fragment_id, instance_key):
    db.add(NoteFragmentRender(
        daily_note_id=note.id, company_id=user.company_id, user_id=user.id,
        note_date=datetime.combine(note.note_date, time.min, tzinfo=timezone.utc),
        fragment_id=fragment_id, instance_key=instance_key, kind="prompt",
        change_digest="d" * 64,
    ))
    db.flush()


def _task_reaching(db, user, *, due: date, terminal: str):
    """A task due on `due` that this user drives to `terminal`. Real path."""
    td = create_task_with_provenance(
        db, company_id=user.company_id, provenance_kind="manual_creation",
        provenance_ref_type=None, provenance_ref_id=str(uuid.uuid4()),
        event_kind="manual", task_type_key="generic_task",
        title="settling fixture", created_by_user_id=user.id, due_date=due,
    )
    db.commit()
    path = {
        "done": ["assigned", "in_progress", "done"],
        "cancelled": ["assigned", "cancelled"],
    }[terminal]
    for s in path:
        transition_task(db, task_details_id=td.id, to_state=s,
                        actor_user_id=user.id)
    db.commit()
    return td


# ── The rule ─────────────────────────────────────────────────────────


def test_completed_and_cancelled_settle_as_TWO_DIFFERENT_SENTENCES(db_session, user):
    """⚠️ THE RULE. One prompt, two endings on the same day, two records."""
    today = date.today()
    note = _note(db_session, user, today)
    key = f"tasks_due_today:user_day:{user.id}:{today.isoformat()}"
    _rendered_prompt(db_session, user, note, "tasks_due_today", key)

    _task_reaching(db_session, user, due=today, terminal="done")
    _task_reaching(db_session, user, due=today, terminal="cancelled")

    res = settle_note(db_session, user=user, note=note)
    db_session.flush()

    recs = db_session.query(NoteSettledRecord).filter(
        NoteSettledRecord.daily_note_id == note.id
    ).all()
    by_outcome = {r.outcome_key: r for r in recs}

    assert set(by_outcome) == {"done", "cancelled"}, (
        f"expected both endings, got {sorted(by_outcome)}; unsettleable="
        f"{res.unsettleable} unresolvable={res.unresolvable}"
    )
    assert "completed" in by_outcome["done"].text
    assert "cancelled" in by_outcome["cancelled"].text
    assert "completed" not in by_outcome["cancelled"].text, (
        "the cancelled task reads as completed — the flattening this replaced"
    )


def test_CONTROL_a_day_with_no_terminal_transitions_settles_to_nothing(
    db_session, user
):
    """The pair that makes the test above mean something.

    Without it, "two records appeared" is satisfied by a settler that writes
    records regardless of what happened.
    """
    today = date.today()
    note = _note(db_session, user, today)
    key = f"tasks_due_today:user_day:{user.id}:{today.isoformat()}"
    _rendered_prompt(db_session, user, note, "tasks_due_today", key)

    res = settle_note(db_session, user=user, note=note)
    db_session.flush()

    assert res.written == 0
    assert db_session.query(NoteSettledRecord).filter(
        NoteSettledRecord.daily_note_id == note.id
    ).count() == 0


# ── Idempotence and stability ────────────────────────────────────────


def test_settling_twice_writes_once(db_session, user):
    """⚠️ A */15 sweep evaluates the same day many times."""
    today = date.today()
    note = _note(db_session, user, today)
    key = f"tasks_due_today:user_day:{user.id}:{today.isoformat()}"
    _rendered_prompt(db_session, user, note, "tasks_due_today", key)
    _task_reaching(db_session, user, due=today, terminal="done")

    first = settle_note(db_session, user=user, note=note)
    db_session.flush()
    second = settle_note(db_session, user=user, note=note)
    db_session.flush()

    assert first.written == 1
    assert second.written == 0, "settling twice doubled the summary"
    assert second.already_present == 1
    assert db_session.query(NoteSettledRecord).filter(
        NoteSettledRecord.daily_note_id == note.id
    ).count() == 1


def test_a_settled_record_is_NOT_REWORDED_when_more_happens(db_session, user):
    """The count that was true when written stays written.

    A settled note that re-words itself is worse than one that says nothing —
    it is what "what did I decide Tuesday" reads.
    """
    today = date.today()
    note = _note(db_session, user, today)
    key = f"tasks_due_today:user_day:{user.id}:{today.isoformat()}"
    _rendered_prompt(db_session, user, note, "tasks_due_today", key)

    _task_reaching(db_session, user, due=today, terminal="done")
    settle_note(db_session, user=user, note=note)
    db_session.flush()
    first = db_session.query(NoteSettledRecord).filter(
        NoteSettledRecord.outcome_key == "done",
        NoteSettledRecord.daily_note_id == note.id,
    ).one()
    original_text, original_count = first.text, first.count

    _task_reaching(db_session, user, due=today, terminal="done")
    settle_note(db_session, user=user, note=note)
    db_session.flush()
    db_session.refresh(first)

    assert first.text == original_text, "the settled sentence was rewritten"
    assert first.count == original_count


# ── Outcomes come from structured fields, never prose ────────────────


def test_a_resolution_with_NO_declared_outcome_is_reported_not_parsed(
    db_session, user
):
    """⚠️ `resolution_note` says which act it was, in a sentence. Not used."""
    from app.models.agent import AgentJob
    from app.models.agent_anomaly import AgentAnomaly

    today = date.today()
    note = _note(db_session, user, today)
    cust_id = str(uuid.uuid4())
    key = f"collections_outstanding:customer:{cust_id}"
    _rendered_prompt(db_session, user, note, "collections_outstanding", key)

    job = AgentJob(id=str(uuid.uuid4()), tenant_id=user.company_id,
                   job_type="ar_collections", status="complete")
    db_session.add(job); db_session.flush()
    db_session.add(AgentAnomaly(
        id=str(uuid.uuid4()), agent_job_id=job.id, tenant_id=user.company_id,
        anomaly_type="collections_critical", entity_type="customer",
        entity_id=cust_id, severity="critical", description="x",
        resolved=True, resolved_by=user.id,
        resolved_at=datetime.now(timezone.utc),
        resolution_note="Skipped via triage — customer disputed",
        resolution_outcome=None,
    ))
    db_session.flush()

    res = settle_note(db_session, user=user, note=note)
    db_session.flush()

    assert res.written == 0, "an undeclared outcome was settled anyway"
    assert any("recorded no outcome" in u.reason for u in res.unsettleable), (
        f"not reported as unsettleable: {res.unsettleable}"
    )
    texts = [r.text for r in db_session.query(NoteSettledRecord).filter(
        NoteSettledRecord.daily_note_id == note.id).all()]
    assert not any("skip" in t.lower() for t in texts), (
        "the outcome was recovered from resolution_note — prose parsing"
    )


# ── Tenant-local day ─────────────────────────────────────────────────


def test_the_day_window_is_tenant_local_not_utc(db_session):
    """An 11pm action belongs to the day the person was living."""
    start, end = tenant_day_window(
        db_session, company_id=TESTCO_ID, day=date(2026, 9, 10)
    )
    assert end - start == timedelta(days=1)
    from app.models.company import Company
    tz = ZoneInfo(
        db_session.query(Company.timezone).filter(Company.id == TESTCO_ID).scalar()
        or "America/New_York"
    )
    assert start.astimezone(tz).time() == time.min, (
        "the window does not start at tenant-local midnight"
    )


def test_split_instance_key_keeps_a_subject_that_contains_colons():
    """⚠️ `user_day` is "{user_id}:{date}" — a naive split truncates it."""
    uid = "11111111-2222-3333-4444-555555555555"
    frag, kind, subject = split_instance_key(
        f"tasks_due_today:user_day:{uid}:2026-09-10"
    )
    assert frag == "tasks_due_today"
    assert kind == "user_day"
    assert subject == f"{uid}:2026-09-10", "the subject was truncated"


# ── Spans ────────────────────────────────────────────────────────────


def test_the_settled_record_serialises_spans_through_the_ONE_serialiser(
    db_session, user
):
    """Asserted against the serialiser's own output, not against a shape."""
    from app.services.fragments.synthesis import measured, plain
    from app.services.fragments.types import ReferencedItem
    from app.services.note.spans import serialise_spans

    today = date.today()
    note = _note(db_session, user, today)
    key = f"tasks_due_today:user_day:{user.id}:{today.isoformat()}"
    _rendered_prompt(db_session, user, note, "tasks_due_today", key)
    _task_reaching(db_session, user, due=today, terminal="done")

    settle_note(db_session, user=user, note=note)
    db_session.flush()
    rec = db_session.query(NoteSettledRecord).filter(
        NoteSettledRecord.daily_note_id == note.id
    ).one()

    stored = json.loads(rec.spans)
    assert stored, "the settled record carries no spans"
    # Rebuild what the serialiser would emit for an equivalent span set and
    # compare the SHAPE OF THE OUTPUT, not a hand-written literal.
    reference = serialise_spans([
        plain("x"),
        measured("1", ReferencedItem(kind="k", entity_id="e", label="l", href=None)),
    ])
    assert set(stored[0]) == set(reference[0]), (
        "the settled record's span keys differ from the serialiser's — a "
        "second implementation has appeared"
    )
    assert any(sp["state"] == "measured" for sp in stored), (
        "the count is not marked measured — it was counted from events"
    )



# ── The seam. Everything above can be green while nothing is served. ──


def test_the_ENDPOINT_serves_settled_records(db_session, user):
    """⚠️ THE SEAM. Session 2 shipped a complete substrate that the endpoint
    never called; every test passed and the surface showed nothing.

    A settling job that writes records nobody reads is indistinguishable from a
    job that does not run.
    """
    from app.api.routes.note import get_today_note

    today = date.today()
    note = _note(db_session, user, today)
    key = f"tasks_due_today:user_day:{user.id}:{today.isoformat()}"
    _rendered_prompt(db_session, user, note, "tasks_due_today", key)
    _task_reaching(db_session, user, due=today, terminal="done")
    _task_reaching(db_session, user, due=today, terminal="cancelled")
    settle_note(db_session, user=user, note=note)
    db_session.commit()

    payload = get_today_note(current_user=user, db=db_session)

    assert "settled" in payload, "the endpoint does not serve settled records"
    outcomes = {r["outcome_key"]: r for r in payload["settled"]}
    assert set(outcomes) == {"done", "cancelled"}, (
        f"served {sorted(outcomes)} — both endings must reach the surface"
    )
    assert "completed" in outcomes["done"]["text"]
    assert "cancelled" in outcomes["cancelled"]["text"]
    assert outcomes["done"]["spans"], "the settled record reached the surface without spans"
    assert outcomes["done"]["occurred_through"], "no visible timestamp"


def test_the_endpoint_serves_an_EMPTY_settled_list_on_an_unsettled_day(
    db_session, user
):
    """The control: `settled` is always a list, and empty is a real state."""
    from app.api.routes.note import get_today_note

    _note(db_session, user, date.today())
    db_session.commit()
    payload = get_today_note(current_user=user, db=db_session)
    assert payload["settled"] == []
