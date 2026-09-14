"""Health Triage P1: run_uncleared_check_monitor dead-import repoint.

The agent imported `app.models.reconciliation` (never existed) → ImportError
every fire. The model is `app.models.financial_account.ReconciliationAdjustment`
(clean rename; fields tenant_id + adjustment_type + created_at verified). This
witnesses the agent IMPORTS AND RUNS — it executes its query against the real
schema and returns, rather than just asserting the import resolves.
"""

from __future__ import annotations

import uuid

import pytest

from app.database import SessionLocal
from app.models.company import Company
from app.services.proactive_agents import run_uncleared_check_monitor


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


@pytest.fixture(autouse=True)
def _no_litter(db):
    """⚠️ PRE-EXISTING COMPANY LITTER, fixed here because (c) 2c is the commit
    that touched this file. The test COMMITS a Company and the `db` fixture only
    rolls back -- a rollback after a commit reverts nothing. The session-scoped
    tripwire caught it: 453 companies in, 454 out.

    Per CLAUDE.md the litter count can only shrink, and the FK-safe order lives
    in tests/_cleanup.py rather than in a local delete list.
    """
    yield
    from tests._cleanup import purge_companies_by_slug
    purge_companies_by_slug(db, "p1r-%")


def test_uncleared_check_monitor_runs_against_real_schema(db):
    co = Company(
        id=str(uuid.uuid4()),
        name=f"P1R-{uuid.uuid4().hex[:6]}",
        slug=f"p1r-{uuid.uuid4().hex[:6]}",
        is_active=True,
        vertical="manufacturing",
    )
    db.add(co)
    db.commit()

    # The witness: the agent's query EXECUTES (ReconciliationAdjustment resolves
    # + the filter on tenant_id/adjustment_type/created_at runs) — pre-fix this
    # raised ImportError before any query.
    result = run_uncleared_check_monitor(db, co.id)
    # SUPERSEDED by (c) 2c step 2. Was: `assert isinstance(result, dict)` +
    # `result.get("flagged") == 0`. The witness is unchanged -- the query still
    # has to EXECUTE for any of this to be reached.
    from app.services.job_outcome import JobOutcome
    assert isinstance(result, JobOutcome)
    assert result.detail["flagged"] == 0  # fresh tenant, no outstanding checks
    assert result.state == "no_work"
