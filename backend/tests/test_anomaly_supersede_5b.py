"""Phase 5b — supersede on write. This is the phase that closes the
2026-09-01 canon requirement; 1-5a were precondition.

⚠️ NEITHER THE r176 TENANT LISTENER NOR THIS SUPERSEDE PATH HAS RUN IN
PRODUCTION. No anomaly row has been written there since 2026-08-31. Six clean
`expense_categorization` runs after the r176 deploy are evidence that nothing
BROKE, not that either listener works — a quiet interval is not confirmation.
These tests are the only thing exercising either, so they carry the whole
weight, and every absence assertion below is paired with a control.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest

from app.models.agent import AgentJob
from app.models.agent_anomaly import AgentAnomaly
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture

canonical_tenant = make_canonical_tenant_fixture(
    child_tables=("agent_anomalies", "agent_jobs")
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


def _job(db, tenant=TESTCO_ID, job_type="month_end_close") -> AgentJob:
    j = AgentJob(
        id=str(uuid.uuid4()), tenant_id=tenant, job_type=job_type,
        status="running", trigger_type="manual", dry_run=True,
        period_start=date(2026, 8, 1), period_end=date(2026, 8, 31),
    )
    db.add(j)
    db.flush()
    return j


def _write(db, job, *, atype="t_5b", etype="fiscal_year", eid="2026", desc="d"):
    a = AgentAnomaly(
        id=str(uuid.uuid4()), agent_job_id=job.id, severity="info",
        anomaly_type=atype, entity_type=etype, entity_id=eid, description=desc,
    )
    db.add(a)
    db.flush()
    return a


def _rows(db, job_ids, atype="t_5b"):
    return (
        db.query(AgentAnomaly)
        .filter(AgentAnomaly.agent_job_id.in_(job_ids),
                AgentAnomaly.anomaly_type == atype)
        .order_by(AgentAnomaly.created_at)
        .all()
    )


# ── The core behaviour ───────────────────────────────────────────────


def test_a_second_write_supersedes_the_first_rather_than_duplicating(db_session):
    j1, j2 = _job(db_session), _job(db_session)
    a1 = _write(db_session, j1, desc="first run")
    a2 = _write(db_session, j2, desc="second run")
    db_session.expire_all()

    rows = _rows(db_session, [j1.id, j2.id])
    assert len(rows) == 2, "supersede must WRITE a new row, not update in place"

    old = db_session.get(AgentAnomaly, a1.id)
    new = db_session.get(AgentAnomaly, a2.id)
    assert old.superseded_at is not None, "the prior open row was not superseded"
    assert new.superseded_at is None, "the row just written must be open"
    assert old.description == "first run", "the superseded row keeps its content"


def test_the_writer_actually_writes_control(db_session):
    """⚠️ CONTROL FOR EVERY DEDUP ASSERTION IN THIS FILE.

    "No duplicate was written" is satisfied trivially by a writer that writes
    NOTHING. Every count-based claim here rests on rows existing first, so this
    proves the fixture can produce one at all."""
    j = _job(db_session)
    a = _write(db_session, j)
    db_session.expire_all()
    assert db_session.get(AgentAnomaly, a.id) is not None
    assert len(_rows(db_session, [j.id])) == 1


# ── The recurrence ruling ────────────────────────────────────────────


def test_recurrence_writes_a_new_row_and_does_not_reopen(db_session):
    """⚠️ THE RULING. Write, supersede, write again under the same subject.

    A later occurrence is a different decision on a different day. Reopening
    would say "a problem since August" when the truth is it was a problem, was
    fixed, and RECURRED — and recurrence is the more useful fact."""
    j1, j2, j3 = _job(db_session), _job(db_session), _job(db_session)
    a1 = _write(db_session, j1, desc="occurrence 1")
    a2 = _write(db_session, j2, desc="occurrence 2")
    db_session.expire_all()
    stamp_after_second = db_session.get(AgentAnomaly, a1.id).superseded_at
    assert stamp_after_second is not None

    a3 = _write(db_session, j3, desc="occurrence 3")
    db_session.expire_all()

    rows = _rows(db_session, [j1.id, j2.id, j3.id])
    assert len(rows) == 3, f"each recurrence is its own row; got {len(rows)}"

    r1 = db_session.get(AgentAnomaly, a1.id)
    r2 = db_session.get(AgentAnomaly, a2.id)
    r3 = db_session.get(AgentAnomaly, a3.id)

    open_rows = [r for r in (r1, r2, r3) if r.superseded_at is None and not r.resolved]
    assert len(open_rows) == 1 and open_rows[0].id == a3.id, (
        "exactly one row may be open, and it must be the latest write"
    )
    assert r1.superseded_at == stamp_after_second, (
        "⚠️ the FIRST row's supersede timestamp was rewritten by a later "
        "recurrence. It records when THAT occurrence was replaced and must not "
        "move — an already-superseded row is not re-superseded."
    )


def test_reopening_is_now_REFUSED_BY_THE_DATABASE(db_session):
    """⚠️ THIS TEST CHANGED SHAPE UNDER 5c, AND THE CHANGE IS THE POINT.

    It used to reproduce the rejected reopen design and assert that it yields
    two open rows for one key -- a control proving the invariant was real rather
    than asserted. Under r177's partial unique index that state is no longer
    reachable: clearing `superseded_at` on a row whose key already has an open
    row raises `UniqueViolation`.

    So the control retires and this replaces it. The old version proved the
    design was WRONG; this proves it is now IMPOSSIBLE, which is the stronger
    statement and the whole objective of the arc -- a validated field is a hole
    with a guard on it, and a field the database will not accept a wrong value
    for is not a hole.
    """
    from sqlalchemy.exc import IntegrityError

    j1, j2 = _job(db_session), _job(db_session)
    a1 = _write(db_session, j1)
    _write(db_session, j2)
    db_session.expire_all()
    assert db_session.get(AgentAnomaly, a1.id).superseded_at is not None

    db_session.get(AgentAnomaly, a1.id).superseded_at = None
    with pytest.raises(IntegrityError, match="uq_agent_anomalies_open_subject"):
        db_session.flush()
    db_session.rollback()


# ── What supersede must NOT touch ────────────────────────────────────


def test_a_resolved_row_is_left_alone(db_session):
    """⚠️ A human's decision is not erased by a machine recurrence. The resolved
    row keeps its resolution and the recurrence lands beside it."""
    j1, j2 = _job(db_session), _job(db_session)
    a1 = _write(db_session, j1)
    r1 = db_session.get(AgentAnomaly, a1.id)
    r1.resolved = True
    r1.resolved_at = datetime.now(timezone.utc)
    r1.resolution_note = "operator fixed it"
    db_session.flush()

    _write(db_session, j2)
    db_session.expire_all()

    r1 = db_session.get(AgentAnomaly, a1.id)
    assert r1.resolved is True and r1.superseded_at is None, (
        "a resolved row must not be superseded — its resolution is the record "
        "that a human acted, and superseding it would overwrite that"
    )
    assert r1.resolution_note == "operator fixed it"


def test_a_different_subject_is_not_superseded(db_session):
    """POSITIVE CONTROL FOR THE KEY. A supersede that fired on everything would
    satisfy every dedup assertion above while destroying unrelated findings."""
    j1, j2 = _job(db_session), _job(db_session)
    a1 = _write(db_session, j1, eid="2025")
    _write(db_session, j2, eid="2026")
    db_session.expire_all()
    assert db_session.get(AgentAnomaly, a1.id).superseded_at is None, (
        "fiscal_year 2025 was superseded by a write about 2026"
    )


def test_a_different_type_on_the_same_subject_is_not_superseded(db_session):
    """The type is part of the key — two questions about one subject are two
    decisions, which is why month_end_close's three period-scoped anomalies can
    share a subject."""
    j1, j2 = _job(db_session), _job(db_session)
    a1 = _write(db_session, j1, atype="t_5b")
    _write(db_session, j2, atype="t_5b_other")
    db_session.expire_all()
    assert db_session.get(AgentAnomaly, a1.id).superseded_at is None


def test_another_tenants_row_is_not_superseded(db_session):
    """⚠️ CROSS-TENANT. Subjects are deliberately NOT globally unique after the
    subject arc — `fiscal_year:2026` is byte-identical across tenants. Without
    tenant_id in the key this write would supersede another tenant's finding."""
    from app.models.company import Company

    other = db_session.query(Company).filter(Company.id != TESTCO_ID).first()
    if other is None:
        pytest.skip("only one company present; cross-tenant case needs two")

    j_other = _job(db_session, tenant=other.id)
    a_other = _write(db_session, j_other)
    j_mine = _job(db_session)
    _write(db_session, j_mine)
    db_session.expire_all()

    assert db_session.get(AgentAnomaly, a_other.id).superseded_at is None, (
        "a write for one tenant superseded another tenant's anomaly"
    )


# ── The subjectless pair, which is why the key uses IS NOT DISTINCT FROM ──


def test_a_subjectless_anomaly_still_supersedes(db_session):
    """⚠️ THE 'THEY CANNOT GROW' REQUIREMENT, delivered.

    The two deliberately-subjectless anomaly types are per-tenant singletons.
    Without supersede they would accumulate one row per run forever, which is
    the condition they were flagged for when they were held open.

    ⚠️ WHAT THIS TEST DOES NOT PROVE, corrected after break-testing. Its
    docstring first claimed it demonstrated that `IS NOT DISTINCT FROM` was
    load-bearing versus `==`. Rewriting the listener to `==` left this test
    GREEN, because SQLAlchemy compiles `col == None` to `col IS NULL`. The two
    forms are behaviourally identical here and nothing here can separate them.
    This test proves subjectless rows supersede AT ALL — removing the listener
    does turn it red — and that is the property that matters."""
    j1, j2 = _job(db_session), _job(db_session)
    a1 = _write(db_session, j1, atype="t_5b_nosub", etype=None, eid=None)
    a2 = _write(db_session, j2, atype="t_5b_nosub", etype=None, eid=None)
    db_session.expire_all()

    assert db_session.get(AgentAnomaly, a1.id).superseded_at is not None, (
        "a subjectless anomaly did not supersede — it would grow unbounded"
    )
    assert db_session.get(AgentAnomaly, a2.id).superseded_at is None


# ── Item 3: the two listeners, exercised together ────────────────────


def test_the_tenant_listener_and_supersede_run_on_the_same_insert(db_session):
    """⚠️ ITEM 3'S POSITIVE CONTROL. Both listeners live on `before_insert` and
    NEITHER HAS RUN IN PRODUCTION — no anomaly has been written there since
    2026-08-31, and the six clean agent runs after the r176 deploy show only
    that nothing broke.

    Order is load-bearing and is asserted here rather than assumed: supersede
    matches on `tenant_id`, so it is wrong unless tenant derivation has already
    happened on the same insert."""
    j1, j2 = _job(db_session), _job(db_session)
    a1 = _write(db_session, j1)
    db_session.expire_all()
    r1 = db_session.get(AgentAnomaly, a1.id)
    assert r1.tenant_id == TESTCO_ID, "tenant listener did not run"

    a2 = _write(db_session, j2)
    db_session.expire_all()
    assert db_session.get(AgentAnomaly, a1.id).superseded_at is not None, (
        "supersede did not run, or ran before tenant_id was derived and "
        "therefore matched nothing"
    )
    assert db_session.get(AgentAnomaly, a2.id).tenant_id == TESTCO_ID
