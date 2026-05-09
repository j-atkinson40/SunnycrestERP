"""Phase R-6.1a — workflow email classification cascade tables.

R-6.1 introduces three-tier classification of inbound email messages
into workflow triggers. Tier 1 = deterministic tenant rules (sub-ms);
Tier 2 = AI classification into per-tenant taxonomy (Haiku); Tier 3
= AI selection from tenant-enrolled workflow registry (Haiku).

R-6.1a is the backend half: substrate + cascade + ingestion hook +
admin endpoints + seed. R-6.1b ships the two authoring surfaces +
triage display + Playwright spec.

Schema:

  ``tenant_workflow_email_rules`` — Tier 1 deterministic rule list
  per tenant. ``priority`` orders evaluation (lowest first; first
  match wins). ``match_conditions`` JSONB carries operator dict.
  ``fire_action.workflow_id`` may be null to deliberately suppress
  classification (Tier 1 escape hatch — admin authors a rule that
  drops messages from a noisy sender pattern without firing
  workflows or routing to triage).

  ``tenant_workflow_email_categories`` — Tier 2 taxonomy nodes per
  tenant. Self-FK ``parent_id`` for tree shape (depth bounded at 3
  by convention; v1 ships flat). ``mapped_workflow_id`` is the
  workflow that fires when the classifier picks this category.

  ``workflow_email_classifications`` — append-only audit log; one
  row per inbound EmailMessage that passed through the cascade
  regardless of outcome. Replays + manual reroutes write NEW rows
  (no UPDATE/DELETE service path) — preserves the canonical audit
  chain. ``UNIQUE(email_message_id, created_at)`` would be overkill;
  the read path uses ``ORDER BY created_at DESC LIMIT 1`` to fetch
  the latest classification per message. Cross-tenant scoped via
  ``tenant_id`` FK.

  ``Workflow.tier3_enrolled`` BOOLEAN — opt-in flag for Tier 3 AI
  workflow selection. Default false. Per-workflow column rather
  than nested in trigger_config so it's queryable + filterable
  without a JSONB scan. Tier 3 registry assembly filters on this.

Indexes (canonical patterns mirror r92 + r91):

  ``ix_tenant_workflow_email_rules_tenant_priority`` partial on
  (tenant_id, priority) WHERE is_active=true — hot-path for the
  first-match-wins scan during classification.

  ``ix_tenant_workflow_email_categories_tenant_active`` partial
  on (tenant_id) WHERE is_active=true — taxonomy lookup.

  ``ix_workflow_email_classifications_tenant_recent`` on
  (tenant_id, created_at DESC) — admin audit log query.

  ``ix_workflow_email_classifications_unclassified`` partial on
  (tenant_id, created_at DESC) WHERE tier IS NULL AND is_suppressed
  = false — feeds the unclassified triage queue's direct-query
  builder.

  ``ix_workflow_email_classifications_message`` on
  (email_message_id, created_at DESC) — replay history per message.

  ``ix_workflows_tier3_enrolled`` partial on (company_id, vertical)
  WHERE tier3_enrolled = true AND is_active = true — Tier 3
  registry assembly during classification.

Down: drops indexes + tables + the Workflow.tier3_enrolled column
cleanly. Reversible.

Revision ID: r93_workflow_email_classification
Revises: r92_workflow_review_items
Create Date: 2026-05-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "r93_workflow_email_classification"
down_revision: Union[str, Sequence[str], None] = "r92_workflow_review_items"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_RULES = "tenant_workflow_email_rules"
_CATEGORIES = "tenant_workflow_email_categories"
_CLASSIFICATIONS = "workflow_email_classifications"

_IX_RULES_TENANT_PRIORITY = "ix_tenant_workflow_email_rules_tenant_priority"
_IX_CATEGORIES_TENANT_ACTIVE = "ix_tenant_workflow_email_categories_tenant_active"
_IX_CLASSIFICATIONS_TENANT_RECENT = "ix_workflow_email_classifications_tenant_recent"
_IX_CLASSIFICATIONS_UNCLASSIFIED = "ix_workflow_email_classifications_unclassified"
_IX_CLASSIFICATIONS_MESSAGE = "ix_workflow_email_classifications_message"
_IX_WORKFLOWS_TIER3_ENROLLED = "ix_workflows_tier3_enrolled"


def _conn():
    return op.get_bind()


def _table_exists(name: str) -> bool:
    insp = sa.inspect(_conn())
    return name in insp.get_table_names()


def _index_exists(table: str, index_name: str) -> bool:
    insp = sa.inspect(_conn())
    if not _table_exists(table):
        return False
    indexes = insp.get_indexes(table)
    return any(idx["name"] == index_name for idx in indexes)


def _column_exists(table: str, column: str) -> bool:
    insp = sa.inspect(_conn())
    if not _table_exists(table):
        return False
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    # ── Workflow.tier3_enrolled ───────────────────────────────────
    if not _column_exists("workflows", "tier3_enrolled"):
        op.add_column(
            "workflows",
            sa.Column(
                "tier3_enrolled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )

    # ── tenant_workflow_email_rules ───────────────────────────────
    if not _table_exists(_RULES):
        op.create_table(
            _RULES,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "tenant_id",
                sa.String(36),
                sa.ForeignKey("companies.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("priority", sa.Integer, nullable=False),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column(
                "match_conditions",
                JSONB,
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "fire_action",
                JSONB,
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "is_active",
                sa.Boolean,
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column(
                "created_by_user_id",
                sa.String(36),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "updated_by_user_id",
                sa.String(36),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )

    op.create_index(
        _IX_RULES_TENANT_PRIORITY,
        _RULES,
        ["tenant_id", "priority"],
        postgresql_where=sa.text("is_active = true"),
    )

    # ── tenant_workflow_email_categories ──────────────────────────
    if not _table_exists(_CATEGORIES):
        op.create_table(
            _CATEGORIES,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "tenant_id",
                sa.String(36),
                sa.ForeignKey("companies.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "parent_id",
                sa.String(36),
                sa.ForeignKey(
                    "tenant_workflow_email_categories.id",
                    ondelete="CASCADE",
                ),
                nullable=True,
            ),
            sa.Column("label", sa.String(120), nullable=False),
            sa.Column("description", sa.Text, nullable=True),
            sa.Column(
                "mapped_workflow_id",
                sa.String(36),
                sa.ForeignKey("workflows.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "position",
                sa.Integer,
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "is_active",
                sa.Boolean,
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column(
                "created_by_user_id",
                sa.String(36),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "updated_by_user_id",
                sa.String(36),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )

    op.create_index(
        _IX_CATEGORIES_TENANT_ACTIVE,
        _CATEGORIES,
        ["tenant_id"],
        postgresql_where=sa.text("is_active = true"),
    )

    # ── workflow_email_classifications ────────────────────────────
    if not _table_exists(_CLASSIFICATIONS):
        op.create_table(
            _CLASSIFICATIONS,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "tenant_id",
                sa.String(36),
                sa.ForeignKey("companies.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "email_message_id",
                sa.String(36),
                sa.ForeignKey("email_messages.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("tier", sa.SmallInteger, nullable=True),
            sa.Column(
                "tier1_rule_id",
                sa.String(36),
                sa.ForeignKey(
                    "tenant_workflow_email_rules.id",
                    ondelete="SET NULL",
                ),
                nullable=True,
            ),
            sa.Column(
                "tier2_category_id",
                sa.String(36),
                sa.ForeignKey(
                    "tenant_workflow_email_categories.id",
                    ondelete="SET NULL",
                ),
                nullable=True,
            ),
            sa.Column("tier2_confidence", sa.Float, nullable=True),
            sa.Column("tier3_confidence", sa.Float, nullable=True),
            sa.Column(
                "selected_workflow_id",
                sa.String(36),
                sa.ForeignKey("workflows.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "is_suppressed",
                sa.Boolean,
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "workflow_run_id",
                sa.String(36),
                sa.ForeignKey("workflow_runs.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "is_replay",
                sa.Boolean,
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "replay_of_classification_id",
                sa.String(36),
                sa.ForeignKey(
                    "workflow_email_classifications.id",
                    ondelete="SET NULL",
                ),
                nullable=True,
            ),
            sa.Column("error_message", sa.Text, nullable=True),
            sa.Column("latency_ms", sa.Integer, nullable=True),
            sa.Column(
                "tier_reasoning",
                JSONB,
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.CheckConstraint(
                "tier IS NULL OR tier IN (1, 2, 3)",
                name="ck_workflow_email_classifications_tier",
            ),
        )

    op.create_index(
        _IX_CLASSIFICATIONS_TENANT_RECENT,
        _CLASSIFICATIONS,
        ["tenant_id", "created_at"],
    )

    op.create_index(
        _IX_CLASSIFICATIONS_UNCLASSIFIED,
        _CLASSIFICATIONS,
        ["tenant_id", "created_at"],
        postgresql_where=sa.text(
            "tier IS NULL AND is_suppressed = false"
        ),
    )

    op.create_index(
        _IX_CLASSIFICATIONS_MESSAGE,
        _CLASSIFICATIONS,
        ["email_message_id", "created_at"],
    )

    # ── tier3 enrolled index ──────────────────────────────────────
    op.create_index(
        _IX_WORKFLOWS_TIER3_ENROLLED,
        "workflows",
        ["company_id", "vertical"],
        postgresql_where=sa.text(
            "tier3_enrolled = true AND is_active = true"
        ),
    )


def downgrade() -> None:
    if _index_exists("workflows", _IX_WORKFLOWS_TIER3_ENROLLED):
        op.drop_index(_IX_WORKFLOWS_TIER3_ENROLLED, table_name="workflows")

    if _index_exists(_CLASSIFICATIONS, _IX_CLASSIFICATIONS_MESSAGE):
        op.drop_index(_IX_CLASSIFICATIONS_MESSAGE, table_name=_CLASSIFICATIONS)
    if _index_exists(_CLASSIFICATIONS, _IX_CLASSIFICATIONS_UNCLASSIFIED):
        op.drop_index(_IX_CLASSIFICATIONS_UNCLASSIFIED, table_name=_CLASSIFICATIONS)
    if _index_exists(_CLASSIFICATIONS, _IX_CLASSIFICATIONS_TENANT_RECENT):
        op.drop_index(_IX_CLASSIFICATIONS_TENANT_RECENT, table_name=_CLASSIFICATIONS)
    if _table_exists(_CLASSIFICATIONS):
        op.drop_table(_CLASSIFICATIONS)

    if _index_exists(_CATEGORIES, _IX_CATEGORIES_TENANT_ACTIVE):
        op.drop_index(_IX_CATEGORIES_TENANT_ACTIVE, table_name=_CATEGORIES)
    if _table_exists(_CATEGORIES):
        op.drop_table(_CATEGORIES)

    if _index_exists(_RULES, _IX_RULES_TENANT_PRIORITY):
        op.drop_index(_IX_RULES_TENANT_PRIORITY, table_name=_RULES)
    if _table_exists(_RULES):
        op.drop_table(_RULES)

    if _column_exists("workflows", "tier3_enrolled"):
        op.drop_column("workflows", "tier3_enrolled")
