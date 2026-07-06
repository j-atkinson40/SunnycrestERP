"""MoC Tenant View — the task-catalog tenant-merge read (Phase 1).

The claims:
  1. NO tenant_id → byte-identical to the pre-tenant-view behavior
     (vertical_default only — the non-regression pin).
  2. tenant_id → the MERGED set: vertical defaults + THAT tenant's
     tenant_override rows (defaults ordered first).
  3. Another tenant's overrides are NEVER included (tenant isolation).
  4. A tenant with no overrides → exactly the defaults (graceful).
  5. The read shape carries `scope` + `tenant_id` (the labeling fields).
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.company import Company
from app.models.moc_task_catalog import MoCTaskCatalog
from app.services.maps_of_content.task_catalog import resolve_task_catalog

VERT = "manufacturing"


@pytest.fixture
def env():
    s = SessionLocal()
    suffix = uuid.uuid4().hex[:8]
    t1 = Company(id=str(uuid.uuid4()), name="Tenant One", slug=f"tv1-{suffix}",
                 vertical=VERT, is_active=True)
    t2 = Company(id=str(uuid.uuid4()), name="Tenant Two", slug=f"tv2-{suffix}",
                 vertical=VERT, is_active=True)
    s.add_all([t1, t2])
    s.flush()

    def mk(name: str, scope: str, tenant_id: str | None, order: int = 0):
        task = MoCTaskCatalog(
            id=str(uuid.uuid4()), scope=scope, vertical=VERT, tenant_id=tenant_id,
            name=f"{name} {suffix}", display_order=order, is_active=True,
        )
        s.add(task)
        s.flush()
        return task

    default_a = mk("Default A", "vertical_default", None, 0)
    default_b = mk("Default B", "vertical_default", None, 1)
    t1_task = mk("T1 Override", "tenant_override", t1.id, 0)
    t2_task = mk("T2 Override", "tenant_override", t2.id, 0)
    ctx = {"db": s, "t1": t1, "t2": t2, "suffix": suffix,
           "ids": {"da": default_a.id, "db": default_b.id, "t1": t1_task.id, "t2": t2_task.id}}
    s.commit()
    yield ctx
    s.rollback()
    s.execute(sql_text("DELETE FROM moc_task_catalog WHERE id = ANY(:ids)"),
              {"ids": list(ctx["ids"].values())})
    s.execute(sql_text("DELETE FROM companies WHERE id IN (:a, :b)"),
              {"a": t1.id, "b": t2.id})
    s.commit()
    s.close()


def _mine(rows: list[dict], env) -> list[dict]:
    """Scope assertions to this test's fixture rows (the shared dev DB has other
    vertical_default tasks; the suffix keys ours)."""
    return [r for r in rows if env["suffix"] in r["name"]]


def test_no_tenant_returns_defaults_only(env):
    rows = _mine(resolve_task_catalog(env["db"], vertical=VERT), env)
    ids = {r["id"] for r in rows}
    assert ids == {env["ids"]["da"], env["ids"]["db"]}   # defaults only
    assert all(r["scope"] == "vertical_default" for r in rows)


def test_tenant_view_merges_defaults_plus_own_overrides(env):
    rows = _mine(resolve_task_catalog(env["db"], vertical=VERT, tenant_id=env["t1"].id), env)
    ids = [r["id"] for r in rows]
    assert set(ids) == {env["ids"]["da"], env["ids"]["db"], env["ids"]["t1"]}
    assert env["ids"]["t2"] not in ids                    # isolation
    # defaults order FIRST, the tenant's overrides after
    assert ids[:2] == [env["ids"]["da"], env["ids"]["db"]]
    assert ids[2] == env["ids"]["t1"]


def test_other_tenants_overrides_never_leak(env):
    rows = _mine(resolve_task_catalog(env["db"], vertical=VERT, tenant_id=env["t2"].id), env)
    ids = {r["id"] for r in rows}
    assert env["ids"]["t2"] in ids
    assert env["ids"]["t1"] not in ids


def test_tenant_with_no_overrides_gets_exactly_the_defaults(env):
    ghost = Company(id=str(uuid.uuid4()), name="Ghost", slug=f"tv3-{env['suffix']}",
                    vertical=VERT, is_active=True)
    env["db"].add(ghost)
    env["db"].commit()
    try:
        with_tenant = _mine(resolve_task_catalog(env["db"], vertical=VERT, tenant_id=ghost.id), env)
        without = _mine(resolve_task_catalog(env["db"], vertical=VERT), env)
        assert [r["id"] for r in with_tenant] == [r["id"] for r in without]
    finally:
        env["db"].execute(sql_text("DELETE FROM companies WHERE id = :c"), {"c": ghost.id})
        env["db"].commit()


def test_read_shape_carries_scope_and_tenant_id(env):
    rows = _mine(resolve_task_catalog(env["db"], vertical=VERT, tenant_id=env["t1"].id), env)
    by_id = {r["id"]: r for r in rows}
    assert by_id[env["ids"]["da"]]["scope"] == "vertical_default"
    assert by_id[env["ids"]["da"]]["tenant_id"] is None
    assert by_id[env["ids"]["t1"]]["scope"] == "tenant_override"
    assert by_id[env["ids"]["t1"]]["tenant_id"] == env["t1"].id


# ── H-1: the fires log's company filter (the tenant page's fires card) ──


def test_fires_log_company_filter(env):
    import uuid as _uuid

    from app.models.workflow import Workflow, WorkflowRun
    from app.services.maps_of_content.schedule_sweep import list_schedule_runs

    s = env["db"]
    wf = Workflow(id=str(_uuid.uuid4()), company_id=env["t1"].id, name="h1 probe",
                  trigger_type="manual", scope="tenant", tier=4, is_active=True)
    s.add(wf)
    s.flush()
    run_ids = []
    for co in (env["t1"], env["t2"]):
        r = WorkflowRun(id=str(_uuid.uuid4()), workflow_id=wf.id, company_id=co.id,
                        trigger_source="moc_task_schedule",
                        trigger_context={"moc_task_trigger_id": f"trig-{co.slug}",
                                         "task_name": "probe"},
                        status="completed", output_data={"__dry_run__": True})
        s.add(r)
        s.flush()
        run_ids.append(r.id)
    s.commit()
    try:
        # scoped to t1 → t1's run only (t2's excluded)
        mine = [r for r in list_schedule_runs(s, limit=200, company_id=env["t1"].id)
                if r["run_id"] in run_ids]
        assert [r["run_id"] for r in mine] == [run_ids[0]]
        # unscoped still sees both
        both = [r for r in list_schedule_runs(s, limit=200) if r["run_id"] in run_ids]
        assert {r["run_id"] for r in both} == set(run_ids)
    finally:
        s.execute(sql_text("DELETE FROM workflow_runs WHERE id = ANY(:r)"), {"r": run_ids})
        s.execute(sql_text("DELETE FROM workflows WHERE id = :w"), {"w": wf.id})
        s.commit()
