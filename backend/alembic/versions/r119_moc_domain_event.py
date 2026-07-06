"""MoC domain-event outbox (Canvas↔Runtime Bridge T-2.2a).

The transactional outbox for domain-event emission — the first net-new layer of
the T-2.2 event-firing arc (emit → durable-record → match → fire). One row per
emitted domain event, written IN THE SAME TRANSACTION as the mutation it
records (the transactional-outbox reliability model: the event commits iff the
mutation commits — no lost events, no phantom events).

`payload` is the filterable-field VALUES snapshotted at emit time (the catalog's
`filterable_fields` is the contract) — trigger conditions evaluate against the
state when the event happened, and the matcher never re-reads domain entities.

`processed_at` NULL marks the matcher's work queue (partial index). T-2.2a
ships this INERT — nothing consumes the rows yet; the matcher sweep is T-2.2b.

At-least-once + idempotent firing: the fire-side dedup key is
(moc_task_trigger_id, event_id) via WorkflowRun.trigger_context — the T-2.1a
idempotency pattern re-keyed. No ordering guarantee (documented non-goal).

Revision ID: r119_moc_domain_event
Revises: r118_moc_witness_marker
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "r119_moc_domain_event"
down_revision = "r118_moc_witness_marker"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "moc_domain_event",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            # ON DELETE CASCADE: a deleted tenant's events are meaningless —
            # and (load-bearing) emitted rows must NOT block a company delete;
            # without cascade, every existing test teardown that deletes its
            # fixture company after a case-creating flow breaks on this FK.
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("event_key", sa.String(120), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=True),
        sa.Column("entity_id", sa.String(36), nullable=True),
        sa.Column("payload", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "emitted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    # The matcher's work queue — unprocessed rows only.
    op.create_index(
        "ix_moc_domain_event_unprocessed",
        "moc_domain_event",
        ["emitted_at"],
        postgresql_where=sa.text("processed_at IS NULL"),
    )
    op.create_index(
        "ix_moc_domain_event_company_key",
        "moc_domain_event",
        ["company_id", "event_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_moc_domain_event_company_key", table_name="moc_domain_event")
    op.drop_index("ix_moc_domain_event_unprocessed", table_name="moc_domain_event")
    op.drop_table("moc_domain_event")
