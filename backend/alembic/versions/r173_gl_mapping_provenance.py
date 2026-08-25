"""LEDGER-1 A-1 — record how each GL mapping was classified.

⚠️ THE IMPORTER COMPUTED CONFIDENCE AND THREW IT AWAY. `parse_sage_coa` has
always returned a confidence per account — 1.0 for an exact hit on
`SAGE_CATEGORY_MAP`, 0.7 for a fuzzy substring hit, 0.0 for the fallback — and
`import_gl_accounts` never persisted it. A 0.7 guess was stored
indistinguishably from a 1.0 exact match.

That is why four misclassifications sat in production undetected: 13 revenue
accounts categorised as cost of goods sold, 8 long-term liabilities categorised
as current, and 73 accounts in the `other` bucket that nobody had judged
miscellaneous — the importer simply could not map them. Every one of those rows
looked exactly like a deliberate, confident classification.

The raw Sage label went the same way. `parse_sage_coa` returns `sage_category`
verbatim; the importer dropped it, so the misclassification could not be
recomputed from the stored data at all. Diagnosing it required going back to the
source CSV, which by then was a request to the customer's accountant.

Two columns, both nullable:

    sage_category  — the label the source system used, verbatim
    confidence     — 1.00 exact / 0.70 fuzzy / 0.00 unmapped

NULLABLE AND NO BACKFILL, deliberately. Every row imported before this migration
has no recorded provenance, and NULL is the true statement about those rows.
Backfilling a confidence we did not measure would recreate the exact defect this
migration exists to close — a number that looks measured and is not.

Additive only. No data is modified here; the re-import and the vocabulary
constraint are r174.
"""
from alembic import op
import sqlalchemy as sa

revision = "r173_gl_mapping_provenance"
down_revision = "r172_customer_tax_county"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Additive and idempotent via env.py's op.add_column wrapper.
    op.add_column(
        "tenant_gl_mappings",
        sa.Column("sage_category", sa.String(100), nullable=True),
    )
    op.add_column(
        "tenant_gl_mappings",
        sa.Column("confidence", sa.Numeric(3, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenant_gl_mappings", "confidence")
    op.drop_column("tenant_gl_mappings", "sage_category")
