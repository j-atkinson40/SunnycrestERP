"""Queue-count perf arc C-2 — count == build membership, every converted builder.

The property the design rests on, pinned per builder: `queue_count` (COUNT(*) over
the shared membership query + snooze anti-join) returns EXACTLY the number of rows
the builder (`_dq_*`) produces, over the same id universe, against seeded data.

Covered here (10): task, cash_receipts, month_end_close, ar_collections,
expense_categorization, aftercare, catalog_fetch, safety_program, workflow_review,
reconciliation_review. (ss_cert is pinned in C-1; email_unclassified is C-3.)

aftercare gets extra care: the builder drops falsy entity_id (`if not case_id`);
the membership lifts that to SQL (`isnot(None) AND != ''`). A null- and an
empty-entity_id anomaly must be excluded by BOTH count and build.

Cleans up its own `qcm2-*` tenants via the shared FK-safe helper.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.database import SessionLocal
from app.models.company import Company
from app.models.role import Role
from app.models.user import User
from app.services.triage import registry
from app.services.triage.engine import _DIRECT_QUERIES, queue_count
from tests._cleanup import purge_companies_by_slug

_SLUG = "qcm2-"


def _company(s, vertical="manufacturing"):
    sfx = uuid.uuid4().hex[:8]
    co = Company(id=str(uuid.uuid4()), name=f"QCM2 {sfx}", slug=f"{_SLUG}{sfx}",
                 is_active=True, vertical=vertical)
    s.add(co)
    s.flush()
    role = Role(id=str(uuid.uuid4()), company_id=co.id, name="Admin", slug="admin")
    s.add(role)
    s.flush()
    user = User(id=str(uuid.uuid4()), company_id=co.id, role_id=role.id,
                email=f"qcm2-{sfx}@test.local", hashed_password="x",
                first_name="Q", last_name="Two", is_active=True,
                is_super_admin=True)  # bypass queue permission gate
    s.add(user)
    s.flush()
    return co, user


@pytest.fixture
def env():
    from app.models.safety_training_topic import SafetyTrainingTopic

    s = SessionLocal()
    co, user = _company(s)
    other_co, _other = _company(s)  # second tenant for isolation checks
    # SafetyTrainingTopic is GLOBAL (no tenant column); safety_program rows
    # need a real topic_id (NOT NULL FK). Create one + delete it by id in
    # teardown (purge_companies_by_slug can't scope a non-tenant table).
    topic = SafetyTrainingTopic(
        id=str(uuid.uuid4()), month_number=1,
        topic_key=f"{_SLUG}{uuid.uuid4().hex[:8]}", title="QCM2 Topic")
    s.add(topic)
    s.commit()
    yield type("Env", (), {
        "s": s, "co": co.id, "user": user, "other": other_co.id,
        "topic_id": topic.id,
    })()
    s.rollback()
    try:
        purge_companies_by_slug(s, f"{_SLUG}%")  # deletes safety_program_generations first
        s.execute(
            SafetyTrainingTopic.__table__.delete().where(
                SafetyTrainingTopic.id == topic.id))
        s.commit()
    finally:
        s.close()


def _assert_count_eq_build(env, queue_id, expected):
    """The core property: count == len(build) == expected, same id universe."""
    cfg = registry.get_config(env.s, company_id=env.user.company_id, queue_id=queue_id)
    build = _DIRECT_QUERIES[cfg.source_direct_query_key](env.s, env.user)
    cnt = queue_count(env.s, user=env.user, queue_id=queue_id)
    assert cnt == len(build) == expected, (
        f"{queue_id}: count={cnt} build={len(build)} expected={expected}"
    )
    return {r["id"] for r in build}


# ── Agent-anomaly-backed builders (shared seeding) ──────────────────────

def _job(s, tenant, job_type, status="awaiting_approval"):
    from app.models.agent import AgentJob
    j = AgentJob(id=str(uuid.uuid4()), tenant_id=tenant, job_type=job_type,
                 status=status)
    s.add(j)
    s.flush()
    return j


def _anomaly(s, job, atype, *, resolved=False, entity_type="payment",
             entity_id=None, severity="WARNING", amount=Decimal("100")):
    from app.models.agent_anomaly import AgentAnomaly
    a = AgentAnomaly(
        id=str(uuid.uuid4()), agent_job_id=job.id, anomaly_type=atype,
        resolved=resolved, entity_type=entity_type,
        entity_id=entity_id if entity_id is not None else str(uuid.uuid4()),
        severity=severity, amount=amount,
        description="x", created_at=datetime.now(timezone.utc),
    )
    s.add(a)
    s.flush()
    return a


def test_cash_receipts(env):
    job = _job(env.s, env.co, "cash_receipts_matching")
    m1 = _anomaly(env.s, job, "payment_unmatched_stale")
    m2 = _anomaly(env.s, job, "payment_possible_match")
    _anomaly(env.s, job, "payment_unmatched_stale", resolved=True)   # resolved → out
    _anomaly(env.s, job, "some_other_type")                          # wrong type → out
    other_job = _job(env.s, env.other, "cash_receipts_matching")
    _anomaly(env.s, other_job, "payment_unmatched_stale")            # other tenant → out
    env.s.commit()
    ids = _assert_count_eq_build(env, "cash_receipts_matching_triage", 2)
    assert ids == {m1.id, m2.id}


def test_ar_collections(env):
    job = _job(env.s, env.co, "ar_collections")
    _anomaly(env.s, job, "collections_critical")
    _anomaly(env.s, job, "collections_follow_up")
    _anomaly(env.s, job, "collections_critical", resolved=True)      # out
    env.s.commit()
    _assert_count_eq_build(env, "ar_collections_triage", 2)


def test_expense_categorization(env):
    job = _job(env.s, env.co, "expense_categorization")
    _anomaly(env.s, job, "expense_low_confidence", entity_type="vendor_bill_line")
    _anomaly(env.s, job, "expense_no_gl_mapping", entity_type="vendor_bill_line")
    _anomaly(env.s, job, "expense_low_confidence", resolved=True,
             entity_type="vendor_bill_line")                          # out
    env.s.commit()
    _assert_count_eq_build(env, "expense_categorization_triage", 2)


def test_aftercare_excludes_null_and_empty_entity_id(env):
    """The one non-verbatim membership: the lifted `entity_id IS NOT NULL AND
    != ''` must exclude exactly what the builder's `if not case_id` dropped."""
    from app.services.workflows.aftercare_adapter import (
        AFTERCARE_JOB_TYPE,
        ANOMALY_TYPE,
    )
    job = _job(env.s, env.co, AFTERCARE_JOB_TYPE)
    _anomaly(env.s, job, ANOMALY_TYPE, entity_type="funeral_case")   # member
    _anomaly(env.s, job, ANOMALY_TYPE, entity_type="funeral_case")   # member
    _anomaly(env.s, job, ANOMALY_TYPE, entity_type="funeral_case",
             entity_id="")                                            # empty → out
    # null entity_id (bypass the helper's uuid default)
    from app.models.agent_anomaly import AgentAnomaly
    env.s.add(AgentAnomaly(
        id=str(uuid.uuid4()), agent_job_id=job.id, anomaly_type=ANOMALY_TYPE,
        resolved=False, entity_type="funeral_case", entity_id=None,
        severity="WARNING", amount=Decimal("0"), description="x",
        created_at=datetime.now(timezone.utc),
    ))
    env.s.commit()
    # Both count and build see 2 — the empty + null are excluded by both.
    _assert_count_eq_build(env, "aftercare_triage", 2)


def test_month_end_close(env):
    _job(env.s, env.co, "month_end_close", status="awaiting_approval")
    _job(env.s, env.co, "month_end_close", status="awaiting_approval")
    _job(env.s, env.co, "month_end_close", status="complete")        # wrong status → out
    _job(env.s, env.co, "cash_receipts_matching", status="awaiting_approval")  # wrong type
    env.s.commit()
    _assert_count_eq_build(env, "month_end_close_triage", 2)


def test_task_triage(env):
    from app.services.task_service import create_task
    create_task(env.s, company_id=env.co, title="A", created_by_user_id=env.user.id,
                assignee_user_id=env.user.id, priority="high")
    create_task(env.s, company_id=env.co, title="B", created_by_user_id=env.user.id,
                assignee_user_id=env.user.id)
    # assigned to nobody-relevant (different assignee) → not a member of THIS user's queue
    other_user = User(id=str(uuid.uuid4()), company_id=env.co, role_id=env.user.role_id,
                      email=f"o-{uuid.uuid4().hex[:6]}@test.local", hashed_password="x",
                      first_name="O", last_name="X", is_active=True)
    env.s.add(other_user)
    env.s.flush()
    create_task(env.s, company_id=env.co, title="C", created_by_user_id=env.user.id,
                assignee_user_id=other_user.id)                       # out (other assignee)
    env.s.commit()
    _assert_count_eq_build(env, "task_triage", 2)


def test_safety_program(env):
    from app.models.safety_program_generation import SafetyProgramGeneration
    for i in range(2):
        env.s.add(SafetyProgramGeneration(
            id=str(uuid.uuid4()), tenant_id=env.co, topic_id=env.topic_id,
            status="pending_review", year=2026, month_number=i + 1))
    env.s.add(SafetyProgramGeneration(
        id=str(uuid.uuid4()), tenant_id=env.co, topic_id=env.topic_id,
        status="approved", year=2026, month_number=6))               # out
    env.s.commit()
    _assert_count_eq_build(env, "safety_program_triage", 2)


def test_catalog_fetch(env):
    from app.models.urn_catalog_sync_log import UrnCatalogSyncLog
    for _ in range(2):
        env.s.add(UrnCatalogSyncLog(
            id=str(uuid.uuid4()), tenant_id=env.co,
            publication_state="pending_review", sync_type="scheduled",
            started_at=datetime.now(timezone.utc)))
    env.s.add(UrnCatalogSyncLog(
        id=str(uuid.uuid4()), tenant_id=env.co, publication_state="published",
        sync_type="scheduled", started_at=datetime.now(timezone.utc)))  # out
    env.s.commit()
    _assert_count_eq_build(env, "catalog_fetch_triage", 2)


def test_workflow_review(env):
    from app.models.workflow import Workflow, WorkflowRun
    from app.models.workflow_review_item import WorkflowReviewItem
    wf = Workflow(id=str(uuid.uuid4()), company_id=env.co, name="WF",
                  trigger_type="manual")
    env.s.add(wf)
    env.s.flush()
    run = WorkflowRun(id=str(uuid.uuid4()), company_id=env.co, workflow_id=wf.id,
                      trigger_source="manual")
    env.s.add(run)
    env.s.flush()
    for _ in range(2):
        env.s.add(WorkflowReviewItem(id=str(uuid.uuid4()), company_id=env.co,
                                     run_id=run.id, review_focus_id="rf",
                                     decision=None))
    env.s.add(WorkflowReviewItem(id=str(uuid.uuid4()), company_id=env.co,
                                 run_id=run.id, review_focus_id="rf",
                                 decision="approve"))                 # decided → out
    env.s.commit()
    _assert_count_eq_build(env, "workflow_review_triage", 2)


def test_reconciliation_review(env):
    from app.models.financial_account import (
        FinancialAccount,
        ReconciliationException,
        ReconciliationFlag,
        ReconciliationRun,
        ReconciliationTransaction,
    )
    acct = FinancialAccount(id=str(uuid.uuid4()), tenant_id=env.co,
                            account_type="checking", account_name="Op")
    env.s.add(acct)
    env.s.flush()
    run = ReconciliationRun(id=str(uuid.uuid4()), tenant_id=env.co,
                            financial_account_id=acct.id,
                            statement_date=date.today(),
                            statement_closing_balance=Decimal("0"))
    env.s.add(run)
    env.s.flush()

    def _txn(match_status, parked=False, so=0):
        t = ReconciliationTransaction(
            id=str(uuid.uuid4()), tenant_id=env.co,
            reconciliation_run_id=run.id, description="t",
            transaction_date=date.today(),
            amount=Decimal("10"), match_status=match_status, sort_order=so)
        env.s.add(t)
        env.s.flush()
        e = ReconciliationException(
            id=str(uuid.uuid4()), tenant_id=env.co,
            reconciliation_run_id=run.id,
            reconciliation_transaction_id=t.id, flag_id=None)
        env.s.add(e)
        env.s.flush()
        if parked:  # a real flag (flag_id FK) → exception excluded from the queue
            flag = ReconciliationFlag(
                id=str(uuid.uuid4()), tenant_id=env.co,
                reconciliation_exception_id=e.id,
                destination="hold_for_documentation",
                return_trigger_kind="document_attached")
            env.s.add(flag)
            env.s.flush()
            e.flag_id = flag.id
            env.s.flush()
        return t

    _txn("unmatched", so=1)
    _txn("unmatched", so=2)
    _txn("manually_matched", so=3)          # resolved off unmatched → out
    _txn("unmatched", parked=True, so=4)    # actively parked → out
    env.s.commit()
    _assert_count_eq_build(env, "reconciliation_review_triage", 2)
