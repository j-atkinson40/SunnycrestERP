"""Intelligence Phase 3b — test execution flag, audit log, super_admin.

Schema additions:
  intelligence_executions.is_test_execution     Boolean, default False
                                                (partial index where True)
  users.is_super_admin                          Boolean, default False
                                                (for platform-global prompt edits)

New table: intelligence_prompt_audit_log — records every activate / rollback /
  draft create / draft update / draft delete event. Append-only audit trail.

Revision ID: r19_intelligence_test_execution_flag
Revises: r18_intelligence_vision_support
"""

from alembic import op
import sqlalchemy as sa


revision = "r19_intelligence_test_execution_flag"
down_revision = "r18_intelligence_vision_support"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. intelligence_executions.is_test_execution ────────────────────
    op.add_column(
        "intelligence_executions",
        sa.Column(
            "is_test_execution",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    # Partial index — test executions are a minority; indexing only the
    # TRUE rows keeps the index small while still accelerating the
    # "show me test executions" query.
    op.create_index(
        "ix_intelligence_executions_is_test_execution_true",
        "intelligence_executions",
        ["is_test_execution"],
        unique=False,
        postgresql_where=sa.text("is_test_execution = true"),
    )

    # ── 2. users.is_super_admin ────────────────────────────────────────
    # Phase 3b DEFAULT 3: super_admin role didn't exist. Added as a bool
    # on users (gate-manually, no UI exposure yet). `require_super_admin`
    # in api/deps.py checks current_user.is_super_admin.
    op.add_column(
        "users",
        sa.Column(
            "is_super_admin",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # ── 3. intelligence_prompt_audit_log ───────────────────────────────
    op.create_table(
        "intelligence_prompt_audit_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "prompt_id",
            sa.String(36),
            sa.ForeignKey("intelligence_prompts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "version_id",
            sa.String(36),
            sa.ForeignKey(
                "intelligence_prompt_versions.id", ondelete="SET NULL"
            ),
            nullable=True,
            index=True,
        ),
        # activate | rollback | create_draft | update_draft | delete_draft
        sa.Column("action", sa.String(24), nullable=False, index=True),
        sa.Column(
            "actor_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("actor_email", sa.String(255), nullable=True),
        sa.Column("changelog_summary", sa.Text, nullable=True),
        sa.Column(
            "meta_json",
            sa.dialects.postgresql.JSON,
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            index=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("intelligence_prompt_audit_log")
    op.drop_column("users", "is_super_admin")
    op.drop_index(
        "ix_intelligence_executions_is_test_execution_true",
        table_name="intelligence_executions",
    )
    op.drop_column("intelligence_executions", "is_test_execution")
