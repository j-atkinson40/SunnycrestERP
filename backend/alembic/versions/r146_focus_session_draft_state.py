"""S-3b — focus_sessions.draft_state: per-user Focus editing draft.

The editable quote core (S-3b) persists its in-progress line items here so
an edit session survives reload — WITHOUT materializing a quote. Kept
separate from layout_state (which is widget geometry auto-seeded by the
tenant-default cascade). Nullable; most Focus types never set it.

THE HARD INVARIANT this column upholds: a draft is Focus session state,
not a quote. No quotes-domain read path surfaces it; a Quote row
materializes only at explicit save (quote_service.create_quote).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "r146_focus_session_draft_state"
down_revision = "r145_hopkins_pilot_config_repair"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "focus_sessions",
        sa.Column("draft_state", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("focus_sessions", "draft_state")
