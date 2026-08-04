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
    # Email classification substrate. Classifications reference email_messages
    # AND workflow_runs/workflows (workflow_run_id / selected_workflow_id) — so
    # delete them before those. Then messages → threads → accounts (each
    # tenant-scoped, child-before-parent).
    "DELETE FROM workflow_email_classifications WHERE tenant_id = ANY(:ids)",
    "DELETE FROM email_messages WHERE tenant_id = ANY(:ids)",
    "DELETE FROM email_threads WHERE tenant_id = ANY(:ids)",
    "DELETE FROM email_accounts WHERE tenant_id = ANY(:ids)",
    "DELETE FROM agent_activity_log WHERE job_id IN (SELECT id FROM agent_jobs WHERE tenant_id = ANY(:ids))",
    "UPDATE agent_schedules SET last_job_id = NULL WHERE last_job_id IN (SELECT id FROM agent_jobs WHERE tenant_id = ANY(:ids))",
    "DELETE FROM period_locks WHERE tenant_id = ANY(:ids)",
    "DELETE FROM agent_jobs WHERE tenant_id = ANY(:ids)",
    "DELETE FROM agent_schedules WHERE tenant_id = ANY(:ids)",
    "DELETE FROM agent_alerts WHERE tenant_id = ANY(:ids)",
    "DELETE FROM tenant_alerts WHERE tenant_id = ANY(:ids)",
    # workflow_review_items reference workflow_runs (run_id CASCADE) — delete
    # before the runs.
    "DELETE FROM workflow_review_items WHERE company_id = ANY(:ids)",
    "DELETE FROM workflow_runs WHERE company_id = ANY(:ids)",
    "DELETE FROM workflow_steps WHERE workflow_id IN (SELECT id FROM workflows WHERE company_id = ANY(:ids))",
    "DELETE FROM workflows WHERE company_id = ANY(:ids)",
    # r148/r149 (Books Review Phase 2 A-1b/A-3): these cascade via
    # reconciliation_transactions' ondelete=CASCADE, but delete them explicitly
    # first so the helper stays honest if that cascade is ever removed
    # (children-first discipline).
    "DELETE FROM reconciliation_payment_claims WHERE tenant_id = ANY(:ids)",
    "DELETE FROM reconciliation_match_candidates WHERE tenant_id = ANY(:ids)",
    # r151 (B-4): flags first — the flag_id FK is ondelete SET NULL, so deleting
    # flags clears the exceptions' back-reference before the exceptions go.
    "DELETE FROM reconciliation_flags WHERE tenant_id = ANY(:ids)",
    "DELETE FROM reconciliation_exceptions WHERE tenant_id = ANY(:ids)",
    "DELETE FROM reconciliation_transactions WHERE tenant_id = ANY(:ids)",
    "DELETE FROM reconciliation_adjustments WHERE tenant_id = ANY(:ids)",
    "DELETE FROM reconciliation_runs WHERE tenant_id = ANY(:ids)",
    # Plaid substrate (children-first). bank_accounts.financial_account_id references
    # financial_accounts, so these precede it; reconciliation_transactions.bank_transaction_id
    # is ondelete=SET NULL and already deleted above.
    "DELETE FROM bank_transactions WHERE tenant_id = ANY(:ids)",
    "DELETE FROM bank_accounts WHERE tenant_id = ANY(:ids)",
    "DELETE FROM plaid_category_mappings WHERE tenant_id = ANY(:ids)",
    "DELETE FROM plaid_items WHERE tenant_id = ANY(:ids)",
    "DELETE FROM financial_accounts WHERE tenant_id = ANY(:ids)",
    "DELETE FROM customer_payment_applications WHERE payment_id IN (SELECT id FROM customer_payments WHERE company_id = ANY(:ids))",
    "DELETE FROM customer_payments WHERE company_id = ANY(:ids)",
    "DELETE FROM vendor_payments WHERE company_id = ANY(:ids)",
    "DELETE FROM vendor_bill_lines WHERE bill_id IN (SELECT id FROM vendor_bills WHERE company_id = ANY(:ids))",
    "DELETE FROM vendor_bills WHERE company_id = ANY(:ids)",
    # Invoices: after customer_payment_applications (which references invoice_id,
    # deleted above) and before customers (which invoices reference).
    "DELETE FROM invoice_lines WHERE invoice_id IN (SELECT id FROM invoices WHERE company_id = ANY(:ids))",
    "DELETE FROM invoices WHERE company_id = ANY(:ids)",
    # Social-service certs reference sales_orders (order_id, unique NOT NULL);
    # sales_orders reference customers. Delete certs → order lines → orders
    # before customers below.
    "DELETE FROM social_service_certificates WHERE company_id = ANY(:ids)",
    "DELETE FROM sales_order_lines WHERE sales_order_id IN (SELECT id FROM sales_orders WHERE company_id = ANY(:ids))",
    "DELETE FROM sales_orders WHERE company_id = ANY(:ids)",
    "DELETE FROM customers WHERE company_id = ANY(:ids)",
    "DELETE FROM vendors WHERE company_id = ANY(:ids)",
    # Task substrate + audit (B-4: the "Ask someone" flag creates a Task, which
    # fires the audit subscriber). audit_logs.user_id and vault_items.company_id
    # would otherwise block the users/companies deletes. task_details cascades
    # from vault_items; reconciliation_flags.task_id (→ vault_items) is deleted
    # in the reconciliation block above.
    "DELETE FROM audit_logs WHERE company_id = ANY(:ids)",
    "DELETE FROM notifications WHERE company_id = ANY(:ids)",
    "DELETE FROM triage_snoozes WHERE company_id = ANY(:ids)",
    # tasks.assignee_user_id / created_by_user_id → users; delete before users.
    "DELETE FROM tasks WHERE company_id = ANY(:ids)",
    # tenant-scoped triage-backed entities with no child rows in these tests.
    "DELETE FROM safety_program_generations WHERE tenant_id = ANY(:ids)",
    "DELETE FROM urn_catalog_sync_logs WHERE tenant_id = ANY(:ids)",
    "DELETE FROM task_details WHERE vault_item_id IN (SELECT id FROM vault_items WHERE company_id = ANY(:ids))",
    "DELETE FROM vault_items WHERE company_id = ANY(:ids)",
    "DELETE FROM vaults WHERE company_id = ANY(:ids)",
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
