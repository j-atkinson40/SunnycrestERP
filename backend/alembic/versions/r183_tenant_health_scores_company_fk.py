"""tenant_health_scores.tenant_id -> companies.id, ON DELETE CASCADE

Revision ID: r183_tenant_health_scores_company_fk
Revises: r182_retire_pulse_widget_kind
Create Date: 2026-09-14

⚠️ CORRECTED 2026-09-15 — THIS MIGRATION IS APPLIED BY THE DEPLOY, NOT BY HAND,
AND ITS DOCUMENTED REMEDY DOES NOT EXIST ON PRODUCTION.

`backend/railway-start.sh:45` runs `alembic upgrade head` on every deploy and
ABORTS THE DEPLOY if it fails. So merging this to `main` IS applying it to
production; there is no separate manual step, and the original text below
describing one was wrong about the environment it mattered in.

⚠️ AND `scripts/purge_test_litter.py` REFUSES when `ENVIRONMENT=production` — by
design, it is a development-database tool. So on production the remedy named
below is unavailable: had violations existed, this migration would have failed,
taken the deploy red, and left no documented recovery. Verified read-only before
the fact was noticed: production held 0 violations across all 20 columns and 0
orphaned health scores, so the risk did not materialise. It was still run.

If production ever does hold violating rows, the decision is what to do with
REAL orphaned data, and it is not this file's to make.

⚠️ ORIGINAL PREREQUISITE, WHICH STILL APPLIES TO DEVELOPMENT DATABASES:
`python -m scripts.purge_test_litter --apply` MUST HAVE RUN, AND RUN RECENTLY.
This is not a suggestion and it is not satisfied by "we ran it once".

`tenant_health_scores` accumulates rows whose owning company no longer exists at
a measured **+1,364 to +1,368 per full-tree test run** (four observations,
2026-09-14). `ADD CONSTRAINT` fails if even one such row is present. So a
development database that has run its suite since the last purge WILL fail this
migration, correctly and loudly.

Measured 2026-09-14 18:39 UTC, after one full-tree run since the last purge:
1,374 rows, of which **1,368 would block this migration**. Six would survive.

⚠️ THE FAILURE IS THE DESIGN. There is no pre-delete in this migration and no
exception handler. A migration that quietly deleted the violating rows would be
destroying data on the operator's behalf without showing them the count; a
migration that swallowed the error would leave the constraint absent while
reporting success. It raises, the operator runs the purge, and re-runs.

──────────────────────────────────────────────────────────────────────────
⚠️ WHY THIS CONSTRAINT IS THE FIX AND THE PURGE IS NOT

Enumerated 2026-09-14 across all 391 (table, column) pairs carrying a
`company_id`/`tenant_id`: exactly ONE held orphaned rows, and it is this table.
The other 390 were at zero because their constraints did the work. This is not a
cleanup someone forgot — it is a constraint that was never added, and the
cleanup would otherwise have to be re-run forever.

⚠️ CASCADE, NOT `NO ACTION`, AGAINST THE CATALOG MAJORITY.

Of 370 FKs to `companies.id` from a company/tenant column, **83% are NO ACTION**
and 17% CASCADE. The majority is the wrong guide here, deliberately:

  - `tenant_health_scores` is DERIVED DATA at a LEAF. Verified four ways, not
    inherited: nothing references it in the FK catalog; the three columns
    anywhere named like a health-score are numeric scalars or a String(20)
    status label defaulting to "unknown"; no ORM relationship targets the model;
    and its own relationship list is empty.
  - The scores are meaningless once the tenant is gone.
  - ⚠️ `NO ACTION` would mean the class cannot recur SILENTLY. `CASCADE` means
    it cannot recur. With NO ACTION every future tenant deletion either fails or
    leaves orphans — which is the mechanism that produced 60,469 of them.
  - The convention is not neutral: purging litter workflows was hard precisely
    BECAUSE three referrers of `workflows.id` are NO ACTION and raise rather
    than cascade.

⚠️ AND THE OTHER HALF OF THE CONSTRAINT, PER CLAUDE.md §5. This FK changes
DELETE behaviour as well as INSERT: after it, deleting a company DELETES its
health scores, where previously they were left behind. That is the intent. No
other FK covers this parent-child pair, so no existing cascade is being revoked
— the hazard §5 describes does not apply here, and it was checked rather than
assumed.

──────────────────────────────────────────────────────────────────────────
⚠️ WHAT THE DOWNGRADE COSTS

Dropping the constraint is cheap and instant. It does NOT restore anything the
constraint cascaded away: rows deleted alongside their company while the FK was
in force are gone, and this migration cannot know which they were. Downgrade
returns the schema, never the data.

⚠️ AND THIS TABLE IS NOT COVERED BY 21 OF 391 CONSTRAINTS — SEE STATE. The same
enumeration found **21 tenant-scoped columns with no FK to `companies.id`**, of
which this is one. The other 20 hold no orphans today (14 are empty tables), but
the mechanism is identical and latent. This migration fixes the instance that
has fired; the class is a separate ruling.
"""
from alembic import op
import sqlalchemy as sa


revision = "r183_tenant_health_scores_company_fk"
down_revision = "r182_retire_pulse_widget_kind"
branch_labels = None
depends_on = None


CONSTRAINT_NAME = "fk_tenant_health_scores_tenant_id_companies"


def upgrade() -> None:
    # ⚠️ NO PRE-DELETE AND NO try/except, DELIBERATELY. If violating rows exist
    # this raises, naming the constraint and the table, and the operator runs
    # scripts/purge_test_litter.py before re-running. Both alternatives are
    # worse: a silent delete destroys data without showing a count, and a
    # swallowed error reports success with the constraint absent.
    op.create_foreign_key(
        CONSTRAINT_NAME,
        source_table="tenant_health_scores",
        referent_table="companies",
        local_cols=["tenant_id"],
        remote_cols=["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # Returns the schema. Does NOT return rows the constraint cascaded away.
    op.drop_constraint(
        CONSTRAINT_NAME, "tenant_health_scores", type_="foreignkey"
    )
