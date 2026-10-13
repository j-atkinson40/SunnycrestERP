"""capture_sessions.switches — values chosen for the director, with their alternative

⚠️ NULLABLE, NO SERVER DEFAULT AND NO MODEL-SIDE `default=` (both layers checked,
CLAUDE.md §5 on a default living in two places). A non-null value here would be an
assertion about every session row that already exists and nothing has measured one.
NULL means "this session was captured before switches existed", which is a different
fact from "this session offered none".

Revision ID: r209_capture_session_switches
Revises: r208_capture_session_text
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# ⚠️ IMPORTED EXPLICITLY, NOT REACHED THROUGH `sa.dialects.postgresql`. That
# attribute does not exist until something imports the submodule — measured:
# `import sqlalchemy as sa; sa.dialects.postgresql` raises AttributeError on a bare
# interpreter. This migration ran on dev only because alembic's env.py had already
# imported the dialect for its own connection. Relying on that is relying on an
# import ORDER inside someone else's module, on the one code path that writes
# production (`railway-start.sh` runs `alembic upgrade head` on every deploy).

revision = "r209_capture_session_switches"
down_revision = "r208_capture_session_text"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "capture_sessions",
        sa.Column("switches", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("capture_sessions", "switches")
