"""capture_sessions.prefill — a value the pane filled in, which the text may override.

Revision ID: r216_capture_prefill
Revises: r215_opas_decisions_unresolved
Create Date: 2026-10-24

⚠️ EXPAND-ONLY, AND THAT MATTERS MORE THAN IT USED TO. Migrations now run in
`preDeployCommand` while the PREVIOUS deploy is still serving — 387-552 s measured — so
a migration must leave the running release working. One nullable column added and
nothing touched: the previous release does not select `prefill` and is unaffected.
No `DESTRUCTIVE_REVIEWED` marker is needed, and `tests/test_migration_safety.py` agrees.

⚠️ WHY A COLUMN AND NOT `resolutions`, WHICH ALREADY EXISTS AND ALREADY SURVIVES
RE-EXTRACTION. Because the two have OPPOSITE precedence against the text, and James's
ruling of 2026-10-24 needs the one that does not exist yet:

    resolutions   the director's decision ABOUT ambiguous text. OUTRANKS the text,
                  by design — the text stays ambiguous, so the pick must keep winning.
    prefill       the pane's choice BEFORE any text. Applies when the text says
                  nothing about the field; YIELDS when the text names something else.

Measured before choosing: seeding `resolutions` with the funeral home does make it
survive `set_text("")` — but it also makes `set_text("order Riverside Funeral Home …")`
keep returning Johnson, which is the half of the ruling that says "it's replaced only
if the person names a different funeral home in the text".

⚠️ THE ALTERNATIVE CONSIDERED AND REJECTED: have `set_text` drop a resolution whenever
the text names a different value for that field. It needs no column and it would fix
this — and it would change precedence for every CLICK-made pick platform-wide, which is
a far larger behavioural change than one nullable column. A magic key inside
`resolutions` was also rejected: two policies in one field is the shape this codebase
keeps recording as a defect.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "r216_capture_prefill"
down_revision = "r215_opas_decisions_unresolved"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "capture_sessions",
        # ⚠️ NULLABLE WITH NO SERVER DEFAULT, DELIBERATELY. CLAUDE.md §5: a column added
        # to a populated table is nullable unless every existing row has been SHOWN to
        # satisfy a value. NULL here means "no pane filled anything in", which is true
        # of every session captured before today and is not the same claim as `{}`.
        sa.Column("prefill", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("capture_sessions", "prefill")
