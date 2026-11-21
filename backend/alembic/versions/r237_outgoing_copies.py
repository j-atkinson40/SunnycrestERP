"""outgoing_copies — a copy of what left Bridgeable, and how it left

⚠️ **THE TABLE IS GENERAL FROM THE START, ON PURPOSE.** The R-115's "Mark as
sent" and its print view are the first two producers; building them as R-115
columns would mean redoing them for every later document. `document_kind` and
`subject` keep it general without a polymorphic FK nobody can constrain.

⚠️ **NO DATA IS WRITTEN AND NO COLUMN IS BACKFILLED.** There is nothing to
backfill: no copy of any document has ever been recorded, so an empty table is
the honest starting state rather than a gap. Per CLAUDE.md §5, a value written
uniformly across rows is an assertion about every row it touches — there are
no rows, and none are invented.

Revision ID: r237_outgoing_copies
Revises: r236_payroll_focus_writes
Create Date: 2026-11-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "r237_outgoing_copies"
down_revision = "r236_payroll_focus_writes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outgoing_copies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id", sa.String(36),
            # ⚠️ CASCADE, matching every other tenant-scoped table added since
            # r183. A copy belongs to the tenant whose document it is; leaving
            # the default NO ACTION would make a company purge raise on a
            # table whose rows nobody would think to list.
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("document_kind", sa.String(32), nullable=False),
        sa.Column("subject", sa.String(64), nullable=False),
        sa.Column("content", postgresql.JSONB, nullable=False),
        sa.Column("renderer", sa.String(64), nullable=False),
        sa.Column("renderer_version", sa.String(16), nullable=False),
        # ⚠️ SET NULL, not CASCADE. Deleting a user must not delete the record
        # that a document left the building; "who made it" becoming unknown is
        # a loss, and losing the copy is a bigger one.
        sa.Column(
            "made_by_user_id", sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("made_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("left_as", sa.String(16), nullable=False),
        sa.Column("sent_how", sa.String(200), nullable=True),
        sa.Column("email_to", sa.String(255), nullable=True),
        sa.Column("email_status", sa.String(32), nullable=True),
        sa.CheckConstraint(
            "left_as IN ('printed', 'downloaded', 'emailed', 'marked_sent')",
            name="ck_outgoing_copy_left_as",
        ),
        sa.CheckConstraint(
            "(left_as = 'emailed') = (email_to IS NOT NULL)",
            name="ck_outgoing_copy_email_to_only_when_emailed",
        ),
        sa.CheckConstraint(
            "left_as = 'marked_sent' OR sent_how IS NULL",
            name="ck_outgoing_copy_sent_how_only_when_marked_sent",
        ),
    )
    op.create_index("ix_outgoing_copies_tenant_id", "outgoing_copies",
                    ["tenant_id"])
    op.create_index("ix_outgoing_copy_tenant_kind_subject", "outgoing_copies",
                    ["tenant_id", "document_kind", "subject"])
    op.create_index("ix_outgoing_copy_tenant_made_at", "outgoing_copies",
                    ["tenant_id", "made_at"])


def downgrade() -> None:
    # ⚠️ THIS DROPS THE RECORD OF WHAT LEFT THE BUILDING. The table is new and
    # holds nothing on the day this ships, so the downgrade is safe NOW and
    # will not be once anybody has printed a form. Stated rather than assumed.
    op.drop_index("ix_outgoing_copy_tenant_made_at", table_name="outgoing_copies")
    op.drop_index("ix_outgoing_copy_tenant_kind_subject", table_name="outgoing_copies")
    op.drop_index("ix_outgoing_copies_tenant_id", table_name="outgoing_copies")
    op.drop_table("outgoing_copies")
