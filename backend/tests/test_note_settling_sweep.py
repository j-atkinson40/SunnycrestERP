"""The settling sweep — one cron, per-tenant local timing.

⚠️ THE SWEEP FIRES ~96 TIMES A DAY PER TENANT and settling must happen once per
user per day. These tests hold the two halves of that separately: the window
check fires once per hour, and settling is idempotent even when it doesn't.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone

import pytest
from zoneinfo import ZoneInfo

from app.models.daily_note import DailyNote
from app.models.note_fragment_render import NoteFragmentRender
from app.models.note_settled_record import NoteSettledRecord
from app.services.note.settling_sweep import (
    DEFAULT_SETTLING_HOUR, SETTLING_HOUR_SETTING, hour_fell_in_window,
    sweep_notes_to_settle,
)
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture

canonical_tenant = make_canonical_tenant_fixture(
    child_tables=("note_settled_records", "note_fragment_renders", "daily_notes")
)

TZ = ZoneInfo("America/New_York")


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
    def purge():
        for m in (NoteSettledRecord, NoteFragmentRender):
            db_session.query(m).filter(m.user_id == user.id).delete(
                synchronize_session=False
            )
        db_session.query(DailyNote).filter(DailyNote.user_id == user.id).delete(
            synchronize_session=False
        )
        db_session.commit()
    purge()
    yield
    db_session.rollback()
    purge()


# ── The window ───────────────────────────────────────────────────────


def test_the_window_fires_ONCE_per_hour_not_once_per_sweep():
    """⚠️ `local_now.hour == hour` would fire at :00, :15, :30 and :45."""
    fires = [
        m for m in range(0, 60)
        if hour_fell_in_window(datetime(2026, 9, 11, 0, m, tzinfo=TZ), hour=0)
    ]
    assert fires == list(range(0, 15)), (
        f"the window admitted minutes {fires} — expected only the first 15"
    )


def test_the_window_is_closed_outside_the_settling_hour():
    """The control for every 'it settled' assertion below."""
    for h in (1, 6, 12, 23):
        assert not hour_fell_in_window(
            datetime(2026, 9, 11, h, 3, tzinfo=TZ), hour=0
        ), f"hour {h} fell inside a midnight window"


def test_a_missed_firing_does_not_lose_the_hour_forever():
    """A trailing window still admits a later firing inside the same window."""
    assert hour_fell_in_window(datetime(2026, 9, 11, 0, 14, tzinfo=TZ), hour=0)


def test_the_settling_hour_is_a_tenant_setting_defaulting_to_midnight(db_session):
    from app.models.company import Company
    from app.services.note.settling_sweep import _settling_hour_for

    co = db_session.query(Company).filter(Company.id == TESTCO_ID).one()
    assert _settling_hour_for(co) == DEFAULT_SETTLING_HOUR

    co.set_setting(SETTLING_HOUR_SETTING, 18)
    db_session.flush()
    assert _settling_hour_for(co) == 18

    # ⚠️ A nonsense value falls back rather than settling at hour 99.
    co.set_setting(SETTLING_HOUR_SETTING, "not-an-hour")
    db_session.flush()
    assert _settling_hour_for(co) == DEFAULT_SETTLING_HOUR
    co.set_setting(SETTLING_HOUR_SETTING, 47)
    db_session.flush()
    assert _settling_hour_for(co) == DEFAULT_SETTLING_HOUR


# ── The sweep ────────────────────────────────────────────────────────


def _settled_note(db, user, day: date) -> DailyNote:
    """A note already settled, so the CATCH-UP pass picks it up."""
    n = DailyNote(
        id=str(uuid.uuid4()), company_id=user.company_id, user_id=user.id,
        note_date=day, created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        settled_at=datetime.now(timezone.utc),
    )
    db.add(n); db.flush()
    db.add(NoteFragmentRender(
        daily_note_id=n.id, company_id=user.company_id, user_id=user.id,
        note_date=datetime.combine(day, time.min, tzinfo=timezone.utc),
        fragment_id="tasks_due_today", kind="prompt",
        instance_key=f"tasks_due_today:user_day:{user.id}:{day.isoformat()}",
        change_digest="d" * 64,
    ))
    db.commit()
    return n


def test_the_catch_up_pass_reaches_a_recently_settled_note(db_session, user):
    """⚠️ THE APPEND-ONLY HALF. An action after settling still belongs to its day.

    Asserted by the note being VISITED — the sweep reports it — rather than by a
    record appearing, because whether one appears depends on events this test
    does not create. A test that asserted records would pass for the wrong
    reason on a day when something unrelated resolved.
    """
    today = date.today()
    _settled_note(db_session, user, today)

    stats = sweep_notes_to_settle(db_session)
    assert stats["catch_up_notes"] >= 1, (
        f"the settled note was not revisited: {stats}"
    )


def test_repeated_firing_does_not_double_anything(db_session, user):
    """⚠️ ~96 firings a day. Idempotence is in settle_note, not the window."""
    today = date.today()
    _settled_note(db_session, user, today)

    first = sweep_notes_to_settle(db_session)
    second = sweep_notes_to_settle(db_session)
    third = sweep_notes_to_settle(db_session)

    assert second["records_written"] == 0
    assert third["records_written"] == 0
    assert db_session.query(NoteSettledRecord).filter(
        NoteSettledRecord.user_id == user.id
    ).count() == first["records_written"]


def test_a_sweep_never_raises_out_of_one_tenant(db_session, user):
    """One tenant's failure must not stop the others — per-tenant try/rollback.

    ⚠️ This test originally asserted `tenants_scanned >= 1` with no note in the
    database. That passed only because the sweep scanned EVERY active company;
    once the scan was scoped to tenants that actually have notes, the assertion
    became false by design. It was measuring the breadth of the scan while
    claiming to measure error isolation — so it now creates the note it needs.
    """
    _settled_note(db_session, user, date.today())

    stats = sweep_notes_to_settle(db_session)
    assert stats["errors"] == 0
    assert stats["tenants_scanned"] >= 1


def test_a_tenant_with_no_notes_is_not_scanned(db_session, user):
    """Nothing to settle is not a question worth asking 96 times a day."""
    stats = sweep_notes_to_settle(db_session)
    assert stats["tenants_scanned"] == 0, (
        f"scanned {stats['tenants_scanned']} tenants with no notes at all"
    )


# ── Registration ─────────────────────────────────────────────────────


def test_the_job_is_registered_and_manually_triggerable():
    """⚠️ Registered in its own commit so the deploy is identifiable."""
    from app.scheduler import JOB_REGISTRY

    assert "note_settling_sweep" in JOB_REGISTRY, (
        "the sweep is not in JOB_REGISTRY — it cannot be triggered or audited"
    )
    assert callable(JOB_REGISTRY["note_settling_sweep"])
