"""Phase 5a — the supersede foundation.

⚠️ 5a IS STRUCTURE ONLY. No supersede logic ships here and no unique index is
created. The index would fail to build today: 9 colliding groups in production,
192 rows against one `vendor_bill_line`. Building it first would force a cleanup
decision under the pressure of a failed migration. 5b drains the backlog on
write, 5c adds the index. Removal is the last step — CLAUDE.md §11.

What 5a must get right, and what these tests hold:
  1. `tenant_id` is DERIVED from the job and cannot disagree with it.
  2. `entity_id` accepts a subject longer than a UUID.
  3. `superseded_at` exists and is NOT `resolved`.
  4. No read site filters on `resolved` alone.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import inspect

from app.models.agent_anomaly import AgentAnomaly
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture

_APP = Path(__file__).resolve().parents[1] / "app"

#: Sweeps the two tables this file writes, so the COMPANY LITTER tripwire in
#: conftest stays satisfied without this suite opting out of it.
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


# ── 4. The scanner. This is the one that generalises. ────────────────


def test_no_read_site_filters_on_resolved_alone():
    """⚠️ ADDING `superseded_at` SILENTLY CHANGED WHAT EVERY EXISTING FILTER
    MEANS.

    A query written against `resolved == False` now includes rows the machine
    replaced. Nothing about such a query looks wrong — it reads exactly as it
    did when it was correct — and every count, badge and queue built on it would
    overstate open work by the size of the duplicate backlog. That was 240 rows
    in production when this landed, against 11 real decisions.

    So the bare filter is made DETECTABLE rather than discouraged. `open_filter()`
    is the single source; this scanner is what stops a new bare one appearing.

    The one permitted exception is an explicit `resolved.is_(True)` — asking for
    resolved rows is a different question, not the open-work question.
    """
    offenders: list[str] = []
    for f in sorted(_APP.rglob("*.py")):
        for i, line in enumerate(f.read_text().split("\n"), 1):
            if "AgentAnomaly.resolved" not in line:
                continue
            if "AgentAnomaly.resolved.is_(True)" in line:
                continue  # deliberate: the resolved-rows question
            offenders.append(f"{f.relative_to(_APP)}:{i}: {line.strip()}")

    assert not offenders, (
        "these sites filter AgentAnomaly on `resolved` alone, which now silently "
        "includes superseded rows:\n  " + "\n  ".join(offenders) +
        "\nUse AgentAnomaly.open_filter()."
    )


def test_the_scanner_can_actually_see():
    """POSITIVE CONTROL. A scanner that matches nothing satisfies the assertion
    above trivially — it would pass just as happily on an empty tree."""
    hits = sum(
        1
        for f in _APP.rglob("*.py")
        for line in f.read_text().split("\n")
        if "AgentAnomaly" in line
    )
    assert hits > 20, f"scanner found only {hits} AgentAnomaly references; it is not reading the tree"


def test_open_filter_names_both_conditions():
    """The predicate must test BOTH columns. One that checked only `resolved`
    would satisfy every caller and reintroduce the defect at the single source
    instead of at eleven sites — worse, not better."""
    sql = str(AgentAnomaly.open_filter())
    assert "resolved" in sql and "superseded_at" in sql, sql


# ── 1-3. Schema and the derived tenant ───────────────────────────────


def test_superseded_at_is_not_resolved():
    """⚠️ THE AUDIT-TRAIL POINT. They must be separate columns. Marking a
    duplicate `resolved=True` would claim a human acted on it — a false
    statement in the record, biased toward overstating engagement."""
    cols = {c.key for c in inspect(AgentAnomaly).columns}
    assert {"resolved", "superseded_at", "resolved_by", "resolved_at"} <= cols
    assert AgentAnomaly.__table__.c.superseded_at.nullable
    assert not AgentAnomaly.__table__.c.resolved.nullable


def test_entity_id_holds_a_subject_longer_than_a_uuid():
    """The column was varchar(36) — UUID-sized — and phases 2-3 produce
    `total_expenses:2026-08-01:2026-08-31`, which is exactly 36. Fitting by one
    character is not a margin, and a truncation would merge two distinct
    subjects into one key."""
    assert AgentAnomaly.__table__.c.entity_id.type.length >= 255
    longest_phase23 = "total_expenses:2026-08-01:2026-08-31"
    assert len(longest_phase23) == 36, "the phase 2-3 composite changed; re-check the width"


def test_tenant_id_is_nullable_on_purpose_until_5c():
    """⚠️ NOT AN OVERSIGHT, AND THE FIRST DRAFT HAD IT AS NOT NULL.

    Migrations run inside the deploy, before uvicorn, while Railway keeps the
    OLD container serving. So there is a window where the new schema is live and
    the old code -- which does not set tenant_id and has no listener -- is still
    taking traffic. NOT NULL there would fail every anomaly insert for the
    length of that window, against expense_categorization on a */15 cron.

    Expand/contract: widen now, tighten in 5c once the writer is many deploys
    live. Correctness in the meantime rests on the listener, not the constraint.
    """
    assert AgentAnomaly.__table__.c.tenant_id.nullable, (
        "tenant_id was made NOT NULL. If that is deliberate, it belongs in 5c, "
        "not in a migration that lands while the old writer is still serving."
    )


def test_tenant_is_derived_from_the_job_not_supplied(db_session):
    """⚠️ DERIVED, NOT ASKED FOR. Six production sites and thirteen test/seed
    sites construct AgentAnomaly; a tenant_id each supplies is one each can get
    wrong, and wrong here files a row under another tenant — which the supersede
    key would then read as another tenant's decision."""
    from app.models.agent import AgentJob

    job = AgentJob(
        tenant_id=TESTCO_ID, job_type="month_end_close",
        status="running", trigger_type="manual", dry_run=True,
    )
    db_session.add(job)
    db_session.flush()

    a = AgentAnomaly(
        agent_job_id=job.id, severity="info", anomaly_type="t",
        description="d", entity_type="fiscal_year", entity_id="2026",
    )
    db_session.add(a)
    db_session.flush()
    assert a.tenant_id == TESTCO_ID, "tenant_id was not derived from the job"


def test_a_tenant_that_disagrees_with_the_job_raises(db_session):
    """POSITIVE CONTROL FOR THE DERIVATION, and the half that makes it a guard
    rather than a convenience. Silently overwriting a supplied value would hide
    a real cross-tenant bug; the disagreement is the signal."""
    from app.models.agent import AgentJob

    job = AgentJob(
        tenant_id=TESTCO_ID, job_type="month_end_close",
        status="running", trigger_type="manual", dry_run=True,
    )
    db_session.add(job)
    db_session.flush()

    a = AgentAnomaly(
        agent_job_id=job.id, tenant_id="some-other-tenant",
        severity="info", anomaly_type="t", description="d",
    )
    db_session.add(a)
    with pytest.raises(ValueError, match="disagrees with its job's tenant"):
        db_session.flush()
    db_session.rollback()


# ── The classifier's answer is a subject ─────────────────────────────


def test_classifier_output_is_validated_before_becoming_a_subject():
    """`expense_no_gl_mapping` writes the category into `entity_id`, so an
    unvalidated string is an unvalidated SUBJECT. A hallucinated spelling would
    create a subject naming nothing, and a second spelling would create a
    second — `complete`/`completed` arriving through a field nobody treated as
    a key."""
    from app.services.agents.expense_categorization_agent import (
        EXPENSE_CATEGORIES,
        ExpenseCategorizationAgent as E,
    )

    assert E._validated_category("utilities") == "utilities"
    assert E._validated_category("Utilities & Water For The Main Plant") == "other_expense"
    assert E._validated_category(None) == "other_expense"
    assert E._validated_category("x" * 300) == "other_expense"
    for c in EXPENSE_CATEGORIES:
        assert E._validated_category(c) == c, f"{c} is in the vocabulary but was rejected"


def test_the_5c_index_is_deliberately_absent():
    """⚠️ Pins the sequencing decision so a later reader does not 'finish the
    job' by adding the unique index. It cannot be built until 5b drains the 240
    duplicate rows; adding it now fails the migration and forces a production
    delete under time pressure."""
    idx = {i.name for i in AgentAnomaly.__table__.indexes}
    assert not any("uq" in n or "unique" in n for n in idx), (
        f"a unique index appeared on agent_anomalies: {idx}. That is phase 5c "
        "and it must wait for 5b's drain."
    )
