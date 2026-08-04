"""Ledger Posting arc L-1 — FK: financial_accounts.gl_account_id → tenant_gl_mappings.id.

The bank account's GL (cash/contra) account has always been stored on
`FinancialAccount.gl_account_id` as a `TenantGLMapping.id` by convention
(every consumer resolves it there — journal_entries.py, EPD). It was a bare
`String(36)` with no FK. The Ledger Posting arc makes that id load-bearing (it
is the credit/debit contra leg of every reconciliation JE), so the convention
becomes a constraint.

DANGLING-VALUE PRE-FLIGHT (run before the FK is added on any environment):

    SELECT fa.id, fa.tenant_id, fa.gl_account_id
    FROM financial_accounts fa
    LEFT JOIN tenant_gl_mappings gl ON gl.id = fa.gl_account_id
    WHERE fa.gl_account_id IS NOT NULL AND gl.id IS NULL;

A non-empty result FAILS `ADD CONSTRAINT` (Postgres validates existing rows).
We surface those rows and decide per-row — we do NOT blindly null or coerce
them in this migration. On sunnycrest the live account's gl_account_id is NULL
(safe); the pre-flight is the guard for other tenants / future rows.

IDEMPOTENCY: Postgres has no `ADD CONSTRAINT IF NOT EXISTS`, so we use the
codebase idiom (r149 / r152): DROP CONSTRAINT IF EXISTS, then ADD. A re-run
drops the identical constraint and re-adds it — a no-op in effect, safe on the
second deploy. NO ON DELETE clause: mappings are soft-deleted (is_active), so a
hard DELETE of a mapping a bank account books to SHOULD be refused (default
NO ACTION), not silently null the contra.
"""

from alembic import op

revision = "r153_financial_account_gl_fk"
down_revision = "r152_candidate_record_type_check"
branch_labels = None
depends_on = None

_CONSTRAINT = "fk_financial_accounts_gl_account"


def upgrade() -> None:
    op.execute(
        f"ALTER TABLE financial_accounts DROP CONSTRAINT IF EXISTS {_CONSTRAINT}"
    )
    op.execute(
        f"ALTER TABLE financial_accounts ADD CONSTRAINT {_CONSTRAINT} "
        "FOREIGN KEY (gl_account_id) REFERENCES tenant_gl_mappings (id)"
    )


def downgrade() -> None:
    op.execute(
        f"ALTER TABLE financial_accounts DROP CONSTRAINT IF EXISTS {_CONSTRAINT}"
    )
