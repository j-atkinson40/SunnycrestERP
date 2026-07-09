"""Demo Walk G-1 — the case.opened beat, end to end.

The Act II theater, pinned as assembly: create a case through the REAL
chokepoint (the same `create_case` both demo doors share — the T-2.2a
emitter has fired here since that arc) → the outbox row exists in the same
transaction → the matcher (the 1-minute sweep's body) fires the seeded
First Call Intake trigger DRY-RUN → the run carries full event provenance
(the fires log's row). Plus the seed's contracts: idempotent, is_live
preserved across re-runs (an operator promotion survives deploys).

State-immunity: fixture company; assertions scoped to the fixture's rows;
teardown deletes the fixture's case/events/runs — never the seeded trigger
(the G-6 reset interface this seed documents).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.company import Company
from app.services.maps_of_content.event_matcher import check_moc_domain_events
from scripts.seed_moc_case_opened_trigger import EVENT_KEY, seed as seed_trigger


@pytest.fixture
def env():
    s = SessionLocal()
    suffix = uuid.uuid4().hex[:8]
    co = Company(
        id=str(uuid.uuid4()), name=f"Beat FH {suffix}",
        slug=f"beat-fh-{suffix}", is_active=True, vertical="funeral_home",
    )
    s.add(co)
    s.commit()
    yield {"db": s, "company": co}
    s.rollback()
    s.execute(sql_text(
        "DELETE FROM workflow_run_steps WHERE run_id IN "
        "(SELECT id FROM workflow_runs WHERE company_id = :c)"), {"c": co.id})
    s.execute(sql_text("DELETE FROM workflow_runs WHERE company_id = :c"),
              {"c": co.id})
    # Case + satellites + events cascade with the company (FK ON DELETE) —
    # except the case tables that RESTRICT; delete the case tree explicitly.
    s.execute(sql_text(
        "DELETE FROM funeral_case_notes WHERE company_id = :c"), {"c": co.id})
    for t in ("case_deceased", "case_service", "case_disposition",
              "case_cemetery", "case_cremation", "case_veteran",
              "case_merchandise", "case_financials", "case_preneed",
              "case_aftercare", "case_informants", "case_vaults",
              "case_field_config"):
        s.execute(sql_text(f"DELETE FROM {t} WHERE company_id = :c"),
                  {"c": co.id})
    s.execute(sql_text("DELETE FROM funeral_cases WHERE company_id = :c"),
              {"c": co.id})
    s.execute(sql_text("DELETE FROM moc_domain_event WHERE company_id = :c"),
              {"c": co.id})
    s.delete(co)
    s.commit()
    s.close()


def test_seed_idempotent_and_preserves_promotion(env):
    db = env["db"]
    r1 = seed_trigger(db)
    if r1.get("skipped"):
        pytest.skip("First Call Intake task absent on this DB")
    r2 = seed_trigger(db)
    assert r2["trigger_id"] == r1["trigger_id"]           # one trigger, ever
    assert r2["created"] is False
    # An operator promotion survives a re-seed (the witness-seed discipline).
    from app.models.moc_task_trigger import MoCTaskTrigger

    trig = db.get(MoCTaskTrigger, r1["trigger_id"])
    original = trig.is_live
    trig.is_live = True
    db.commit()
    try:
        r3 = seed_trigger(db)
        assert r3["is_live"] is True                      # PRESERVED
    finally:
        trig = db.get(MoCTaskTrigger, r1["trigger_id"])
        trig.is_live = original
        db.commit()


def test_the_beat_create_case_to_dry_run_fire(env):
    """The minute-long theater, compressed: create → outbox → match → the
    fires-log row with provenance."""
    from app.services.fh import case_service

    db, co = env["db"], env["company"]
    seeded = seed_trigger(db)
    if seeded.get("skipped"):
        pytest.skip("First Call Intake task absent on this DB")

    case = case_service.create_case(db, company_id=co.id)

    # The outbox row exists (same transaction as the case — T-2.2a).
    ev = db.execute(sql_text(
        "SELECT id FROM moc_domain_event WHERE company_id = :c "
        "AND event_key = :k AND processed_at IS NULL"),
        {"c": co.id, "k": EVENT_KEY}).fetchall()
    assert len(ev) == 1

    # The matcher's sweep body (what the 1-minute cadence runs).
    check_moc_domain_events()

    # The fire: a DRY-RUN run for THIS tenant, on the seeded trigger, with
    # full event provenance — the fires log's exact row.
    runs = db.execute(sql_text(
        "SELECT trigger_context, output_data FROM workflow_runs "
        "WHERE company_id = :c AND trigger_source = 'moc_task_event'"),
        {"c": co.id}).fetchall()
    assert len(runs) == 1
    ctx = runs[0].trigger_context
    assert ctx["moc_task_trigger_id"] == seeded["trigger_id"]
    assert ctx["event_key"] == EVENT_KEY
    assert ctx["event_id"] == ev[0].id                     # attributable
    assert (runs[0].output_data or {}).get("__dry_run__") is True  # THE SHOW

    # And the case itself is untouched by any of it (regression).
    assert case.case_number
    assert case.status == "active"
