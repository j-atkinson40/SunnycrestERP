"""CR-2 A-2 — a place to say nothing happened.

⚠️ WHY THIS CANNOT LIVE IN THE EVIDENCE TABLES. Measured, not preferred:

    production_log_entries.product_id    NOT NULL
    production_log_entries.product_name  NOT NULL
    toolbox_talks.topic_title            NOT NULL
    toolbox_talks.topic_category         NOT NULL

"No production today" has no product. A sentinel row would assert "we made 0 of
product X" — a different and FALSE claim — and would corrupt production
reporting in order to satisfy a review. So the nil claim gets its own home.

⚠️ THE CLAIMANT IS EVIDENCE, NOT METADATA. Everywhere else in this design,
evidence satisfies and assertion does not. This is the one carve-out, and it
exists because "nothing happened" is UNVERIFIABLE by evidence — there is no
artifact a quiet day produces. What makes the claim worth anything is that a
named person with the obligation stood behind it. So the accountability IS the
evidence, and it is stored as such.

⚠️ THE ROLE AND NAME ARE SNAPSHOTTED, NOT JOINED. Roles change and users are
deactivated. A join answers "what role does this person hold NOW", which is a
different question from "did they hold the obligation when they claimed it" —
and the second is the one that makes the claim strong or weak. That fact is only
capturable at write time; a later join cannot reconstruct it. Storing is
irreversible if missed, so it is stored. CLASSIFYING claim strength (current
holder vs former holder vs departed) is deferred — that is a rendering decision
and can be made any time.

Revision ID: r168_completeness_nil_claims
Revises: r167_drr_placeholder_unmark_legacy_proof
"""
from alembic import op
import sqlalchemy as sa

revision = "r168_completeness_nil_claims"
down_revision = "r167_drr_placeholder_unmark_legacy_proof"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "completeness_nil_claims",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        # The obligation this answers. A string key, not an FK: expectations are
        # DECLARED IN CODE, so there is no row to point at. A claim against a
        # key that no longer exists stays readable rather than dangling.
        sa.Column("expectation_key", sa.String(64), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        # Nullable FK: a departed user must not take their claim with them.
        sa.Column("claimed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        # Snapshotted at write time — see the module docstring.
        sa.Column("claimed_by_name", sa.String(255), nullable=False),
        sa.Column("claimed_by_role_slug", sa.String(64), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    # One claim per obligation per period per tenant. Without this, "nothing
    # happened" could be asserted repeatedly and a count of claims would read as
    # a count of quiet days.
    op.create_index(
        "ux_completeness_nil_claim",
        "completeness_nil_claims",
        ["tenant_id", "expectation_key", "period_start", "period_end"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ux_completeness_nil_claim", table_name="completeness_nil_claims")
    op.drop_table("completeness_nil_claims")
