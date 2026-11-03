"""Roles may be limited to named areas.

James's ruling, 2026-11-03: rather than gate 886 endpoints one at a time, deny a
limited role everything by default and let it reach only the areas it names.

### One nullable column, and NULL is a value

    NULL   no area restriction was ever established for this role.
           Today's behaviour, byte for byte, for every existing role.
    []     limited to NOTHING — refuses everything but the common set.
    [...]  limited to these areas.

⚠️ **NOT BACKFILLED, AND THE NULL IS THE REASON.** Every existing role at every
tenant — admin, office, production, dispatcher, driver, accountant — keeps NULL
and keeps behaving exactly as it does today. Writing `[]` or a guessed area list
onto them would be a claim about each one that nobody measured, and both are
PLAUSIBLE values, which is the form of that mistake that does not announce
itself (CLAUDE.md §5, "a migration must leave 'not established' distinguishable
from a measured value").

So there is no `server_default` and no UPDATE. A role becomes limited only when
something deliberately writes its areas.

### On DELETE

No new foreign key. The column is a JSONB list of area KEYS — strings from
`app.core.areas.KNOWN_AREAS` — not ids. Areas are code, not rows: they are
declared by `area:` tags at the router registration layer, so there is no table
for a key to reference and nothing for a cascade to reach.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "r221_role_limited_to_areas"
down_revision = "r220_payroll_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "roles",
        sa.Column(
            "limited_to_areas",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment=(
                "Area keys this role is limited to. NULL = not limited (today's "
                "behaviour, never backfilled). [] = limited to nothing. A user on "
                "a limited role is refused every tenant endpoint not tagged "
                "area:<key> for one of these, plus the common set in "
                "app/core/areas.py. Keys are code, not rows — see KNOWN_AREAS."
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("roles", "limited_to_areas")
