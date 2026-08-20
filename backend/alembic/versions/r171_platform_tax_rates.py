"""TAX-3 — county rates as PLATFORM data, effective-dated, with reporting codes.

Cayuga is Cayuga's rate whoever is selling. Today every tenant keeps a private
copy: `data/us-county-tax-rates.json` is read at onboarding, the operator ticks
counties, and `POST /tax/jurisdictions/bulk-onboarding` writes the numbers into
that tenant's `tax_rates`. From then on the copy is frozen and the file is never
consulted again — two producers of one fact, diverging in one direction, with
nothing able to notice.

That is not hypothetical. Checked against Publication 718 on 2026-08-20 the file
was wrong for NINE New York counties (b09c7c4f), and Suffolk showed the whole
cycle: the state enacted a change 17 Dec 2024 effective 1 Mar 2025, and the file
— compiled 2025-01-01, between those dates — still carried the old rate
nineteen months later.

⚠️ A SEPARATE TABLE, NOT A NULLABLE `tenant_id` ON `tax_rates`, AND THE REASON
IS DESTRUCTIVE. `scripts/wipe_tenant.py:106` deletes `tax_rates` and
`tax_jurisdictions` filtered by tenant. Under a nullable-`tenant_id` design a
sentinel or mis-scoped platform row is reachable by a routine tenant teardown —
the platform's rate table deleted by a tenant wipe, reported as success. This
table has NO tenant column at all, so a query filtering `tenant_id` cannot name
it. Unreachable beats untouched.

⚠️ EFFECTIVE-DATED BECAUSE THE SOURCE IS. Publication 718-A is literally a table
of (jurisdiction, rate, enacted, effective) — so this carries the same columns.
A rate change is an INSERT that closes the prior row, never an UPDATE, which is
what makes an old invoice recomputable by construction rather than by someone
remembering to look. Measured from 718-A across 258 statewide changes: 91% take
effect on 1 Mar / 1 Jun / 1 Sep / 1 Dec, median 81 days after enactment. That
gap is why `enacted_on` is stored separately from `effective_from` — a rate can
be KNOWN for three months before it is IN FORCE, and a table with only
`effective_from` cannot tell an operator what is coming.

⚠️ KEYED ON THE JURISDICTION, NOT THE COUNTY, BECAUSE NEW YORK IS.
Pub 718's unit is a jurisdiction with a four-digit REPORTING CODE, which is what
an ST-100 return is filed on — the platform has never stored one. Most counties
are a single jurisdiction, but twelve are split (Cayuga vs Auburn city, and so
on) and Westchester's Yonkers (8.875%) genuinely differs from the county
(8.375%). `county` is carried alongside so today's county-keyed resolver can
still find a row; the code is carried so filing has the key it actually needs.

NOTHING READS THIS FOR BILLING YET. `TaxJurisdiction.tax_rate_id` still points
at tenant `tax_rates`, and changing that — plus giving the resolver an `on_date`
so effective dating means anything at the point of sale — is deliberately a
separate step with its own ruling. This migration is additive and reversible.

Revision ID: r171_platform_tax_rates
Revises: r170_invoice_journal_entry
"""

import sqlalchemy as sa
from alembic import op

revision = "r171_platform_tax_rates"
down_revision = "r170_invoice_journal_entry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_tax_rates",
        sa.Column("id", sa.String(36), primary_key=True),
        # NO tenant_id. See the module docstring — its absence is the safety
        # property, not an omission.
        sa.Column("state", sa.String(2), nullable=False),
        sa.Column("jurisdiction_code", sa.String(8), nullable=False),
        sa.Column("jurisdiction_name", sa.String(120), nullable=False),
        # NULL for a statewide row (NY's "New York State only") — the rate
        # exists but belongs to no county.
        sa.Column("county", sa.String(100), nullable=True),
        sa.Column("rate_percentage", sa.Numeric(6, 4), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        # NULL = in force. Closing a row is how a change is recorded.
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("enacted_on", sa.Date(), nullable=True),
        sa.Column("source_publication", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        # The date a human read the authority. Goes stale visibly, which is the
        # entire point — an unverified rate table looks exactly like a verified
        # one until someone checks.
        sa.Column("verified_on", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="ck_platform_tax_rate_dates_ordered",
        ),
        sa.CheckConstraint(
            "rate_percentage >= 0 AND rate_percentage < 100",
            name="ck_platform_tax_rate_percentage_sane",
        ),
    )

    # At most one IN-FORCE row per (state, jurisdiction, county). COALESCE
    # rather than the bare column because Postgres treats NULLs as distinct in a
    # unique index, which would let duplicate statewide rows through.
    #
    # County is part of the key because New York City is ONE jurisdiction code
    # (8081) spanning FIVE borough counties — genuinely one rate, five rows, and
    # a unique on (state, code) alone would reject four of them.
    op.execute(
        "CREATE UNIQUE INDEX ux_platform_tax_rate_in_force"
        " ON platform_tax_rates (state, jurisdiction_code, COALESCE(county, ''))"
        " WHERE effective_to IS NULL"
    )
    op.create_index(
        "ix_platform_tax_rate_lookup",
        "platform_tax_rates",
        ["state", "county"],
    )


def downgrade() -> None:
    op.drop_index("ix_platform_tax_rate_lookup", table_name="platform_tax_rates")
    op.execute("DROP INDEX IF EXISTS ux_platform_tax_rate_in_force")
    op.drop_table("platform_tax_rates")
