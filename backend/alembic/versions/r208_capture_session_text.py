"""capture_sessions: the full typed text, and the resolutions that outrank it

Typed capture moves from appending lines to RE-READING THE WHOLE TEXT on every
pause. Two columns carry what that model needs and the line model did not.

⚠️ `full_text` IS THE SOURCE, `typed_lines` BECOMES HISTORY. Both are kept. The
lines are the only record of what was typed as separate events — the call
pipeline still produces them, and a session started before this migration has
nothing else. Dropping them would delete the evidence of what an earlier
extractor was given.

⚠️ `resolutions` EXISTS BECAUSE RE-EXTRACTION WOULD OTHERWISE UNDO EVERY PICK.
A pick the director settled by clicking is a decision about text that is still
on screen and still ambiguous; re-reading that text raises the same question on
the next keystroke, so the pane would be unusable. The resolution is applied
LAST, after extraction, and outranks it.

⚠️ BOTH NULLABLE, NO SERVER DEFAULT, BY CLAUDE.md §5. A non-null value here
would be an assertion about every session row that already exists, and nothing
has measured one. NULL means "this session was captured line-by-line and has no
whole-text record" — which is true of every pre-existing row and is a different
fact from "this session's text is empty".

Revision ID: r208_capture_session_text
Revises: r207_form_counterpart_aliases
"""
import sqlalchemy as sa
from alembic import op

revision = "r208_capture_session_text"
down_revision = "r207_form_counterpart_aliases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "capture_sessions",
        sa.Column("full_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "capture_sessions",
        sa.Column(
            "resolutions",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("capture_sessions", "resolutions")
    op.drop_column("capture_sessions", "full_text")
