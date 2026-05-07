"""Phase R-3.1.2 — merge r48_fh_demo_email_tld_fix into r88 chain.

Two alembic heads existed prior to this migration:
  - r48_fh_demo_email_tld_fix (R-1.6.10, March 2026 — FH demo seed email
    TLD .test → .example.com migration)
  - r88_focus_compositions_rows (R-3.0, May 2026 — composition rows
    column + per-row column_count)

Both branched off the same parent (r47_users_template_defaults_retrofit /
r47_activity_log era) and were never merged. `alembic upgrade head`
refused with "Multiple head revisions are present for given argument
'head'". railway-start.sh (pre-R-3.1.3) swallowed the failure with
WARNING and continued, so staging served traffic with stale schema —
specifically, the r88-introduced `focus_compositions.rows` JSONB column
was missing on staging postgres.

R-3.1's Playwright specs 17-20 surfaced this: valid-payload POSTs to
/api/platform/admin/visual-editor/compositions/ reached the DB insert
and 500'd because `rows` didn't exist; invalid-payload tests (e.g.
spec 19's column-overflow check) passed because validation rejected
before touching the DB.

This migration is a no-op data-wise (alembic merge convention) — its
only job is to unify the two heads into a single linear history so
`alembic upgrade head` can apply both branches' changes cleanly on the
next deploy.

R-3.1.3 ships in the same commit, tightening railway-start.sh so future
migration failures abort the deploy instead of silently continuing —
matching R-1.6.3's seed-failure discipline.

R-3.1.4 candidate (separate small arc): CI gate that asserts
`alembic heads | wc -l == 1` on every PR — would have caught this at
PR time instead of at staging-deploy time.

See investigation /tmp/r3_1_specs_endpoint_bug.md for the full
diagnostic chain.

Revision ID: r89_merge_r48_fh_email_tld_into_r88
Revises: r48_fh_demo_email_tld_fix, r88_focus_compositions_rows
Create Date: 2026-05-07
"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "r89_merge_r48_fh_email_tld_into_r88"
down_revision: Union[str, Sequence[str], None] = (
    "r48_fh_demo_email_tld_fix",
    "r88_focus_compositions_rows",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No-op merge per alembic merge convention. Both branches' upgrades
    # apply on the next `alembic upgrade head`.
    pass


def downgrade() -> None:
    # No-op merge per alembic merge convention.
    pass
