"""Shared test teardown — FK-safe purge of test-created companies.

ONE place for the company FK-cascade order so per-file teardown fixtures
don't each re-derive the graph and drift (S-5 CI-clean). The
accounting/workflow suites create companies plus a web of children —
agent_jobs (with non-cascading referrers agent_activity_log /
agent_schedules / period_locks), reconciliation runs/transactions,
payments, vendor bills, workflows/runs. Deleting the company alone
FK-fails; this deletes children first, in order. Extra DELETEs over empty
sets are harmless no-ops, so a single ordered list covers the union of
tables the suites touch.

Usage in a module-scoped teardown fixture:

    from tests._cleanup import purge_companies_by_slug

    @pytest.fixture(scope="module", autouse=True)
    def _cleanup():
        yield
        s = SessionLocal()
        try:
            purge_companies_by_slug(s, "myprefix-%")
        finally:
            s.close()
"""
from __future__ import annotations

from sqlalchemy import text

# FK-safe order: children before parents. agent_run_steps + agent_anomalies
# cascade from agent_jobs; the non-cascading referrers are cleared first.
_PURGE_STATEMENTS = [
    "DELETE FROM agent_activity_log WHERE job_id IN (SELECT id FROM agent_jobs WHERE tenant_id = ANY(:ids))",
    "UPDATE agent_schedules SET last_job_id = NULL WHERE last_job_id IN (SELECT id FROM agent_jobs WHERE tenant_id = ANY(:ids))",
    "DELETE FROM period_locks WHERE tenant_id = ANY(:ids)",
    "DELETE FROM agent_jobs WHERE tenant_id = ANY(:ids)",
    "DELETE FROM agent_schedules WHERE tenant_id = ANY(:ids)",
    "DELETE FROM agent_alerts WHERE tenant_id = ANY(:ids)",
    "DELETE FROM tenant_alerts WHERE tenant_id = ANY(:ids)",
    "DELETE FROM workflow_runs WHERE company_id = ANY(:ids)",
    "DELETE FROM workflow_steps WHERE workflow_id IN (SELECT id FROM workflows WHERE company_id = ANY(:ids))",
    "DELETE FROM workflows WHERE company_id = ANY(:ids)",
    # r148 (Books Review Phase 2 A-1b): these cascade via reconciliation_transactions'
    # ondelete=CASCADE, but delete them explicitly first so the helper stays honest
    # if that cascade is ever removed (children-first discipline).
    "DELETE FROM reconciliation_match_candidates WHERE tenant_id = ANY(:ids)",
    "DELETE FROM reconciliation_exceptions WHERE tenant_id = ANY(:ids)",
    "DELETE FROM reconciliation_transactions WHERE tenant_id = ANY(:ids)",
    "DELETE FROM reconciliation_adjustments WHERE tenant_id = ANY(:ids)",
    "DELETE FROM reconciliation_runs WHERE tenant_id = ANY(:ids)",
    "DELETE FROM financial_accounts WHERE tenant_id = ANY(:ids)",
    "DELETE FROM customer_payment_applications WHERE payment_id IN (SELECT id FROM customer_payments WHERE company_id = ANY(:ids))",
    "DELETE FROM customer_payments WHERE company_id = ANY(:ids)",
    "DELETE FROM vendor_payments WHERE company_id = ANY(:ids)",
    "DELETE FROM vendor_bill_lines WHERE bill_id IN (SELECT id FROM vendor_bills WHERE company_id = ANY(:ids))",
    "DELETE FROM vendor_bills WHERE company_id = ANY(:ids)",
    "DELETE FROM customers WHERE company_id = ANY(:ids)",
    "DELETE FROM vendors WHERE company_id = ANY(:ids)",
    "DELETE FROM users WHERE company_id = ANY(:ids)",
    "DELETE FROM roles WHERE company_id = ANY(:ids)",
    "DELETE FROM companies WHERE id = ANY(:ids)",
]


def purge_test_companies(session, company_ids) -> None:
    ids = list(company_ids)
    if not ids:
        return
    for stmt in _PURGE_STATEMENTS:
        session.execute(text(stmt), {"ids": ids})
    session.commit()


def purge_companies_by_slug(session, slug_prefix: str) -> None:
    """Purge every company whose slug LIKE the given prefix (+ children)."""
    ids = [
        r[0]
        for r in session.execute(
            text("SELECT id FROM companies WHERE slug LIKE :p"),
            {"p": slug_prefix},
        ).all()
    ]
    purge_test_companies(session, ids)
