"""Task routing rules — three-tier resolver table.

v1 task substrate B3 §7.8 + state doc §5.4. Adds `task_routing_rules`
table: per-task-type assignment policy with three-tier inheritance
(platform_default → vertical_default → tenant). First-match-wins
resolver at `app.services.tasks.routing.resolve_routing`.

Schema:
  id                      UUID PK
  scope                   String(20) CHECK IN
                            ('platform_default','vertical_default','tenant')
  vertical                String(32) NULL  (required when scope='vertical_default')
  tenant_id               String(36) NULL FK→companies.id ON DELETE CASCADE
                            (required when scope='tenant')
  task_type_key           String(64) NOT NULL
  routing_mode            String(16) NOT NULL CHECK IN
                            ('direct_user','round_robin')
  target_user_id          String(36) NULL FK→users.id ON DELETE SET NULL
                            (required when routing_mode='direct_user')
  target_permission_key   String(64) NULL
                            (required when routing_mode='round_robin')
  priority                Integer NOT NULL DEFAULT 0
  is_active               Boolean NOT NULL DEFAULT TRUE
  routing_config          JSONB NOT NULL DEFAULT '{}'::jsonb
                            (forward-compat for v2 escalation_chain
                            / capacity_aware modes)
  created_at              DateTime(timezone=True) NOT NULL
  updated_at              DateTime(timezone=True) NOT NULL

Indexes:
  • ix_task_routing_rules_lookup on
    (task_type_key, scope, is_active, priority desc)
    powers the resolver's per-tier lookup.
  • ix_task_routing_rules_tenant on (tenant_id) partial WHERE
    tenant_id IS NOT NULL — accelerates per-tenant deletes via FK
    cascade and tenant-scoped resolver scans.

Idempotent: each DDL gated on inspector state. Reversible.

Migration head: r108_focus_session_task_extension → r109.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers
revision = "r109_task_routing_rules"
down_revision = "r108_focus_session_task_extension"
branch_labels = None
depends_on = None


_TABLE = "task_routing_rules"
_IDX_LOOKUP = "ix_task_routing_rules_lookup"
_IDX_TENANT = "ix_task_routing_rules_tenant"


def _table_exists(bind, table_name: str) -> bool:
    insp = sa.inspect(bind)
    return table_name in insp.get_table_names()


def _existing_indexes(bind, table_name: str) -> set[str]:
    insp = sa.inspect(bind)
    if table_name not in insp.get_table_names():
        return set()
    return {idx["name"] for idx in insp.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()

    if not _table_exists(bind, _TABLE):
        op.create_table(
            _TABLE,
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("scope", sa.String(length=20), nullable=False),
            sa.Column("vertical", sa.String(length=32), nullable=True),
            sa.Column(
                "tenant_id",
                sa.String(length=36),
                sa.ForeignKey("companies.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column("task_type_key", sa.String(length=64), nullable=False),
            sa.Column("routing_mode", sa.String(length=16), nullable=False),
            sa.Column(
                "target_user_id",
                sa.String(length=36),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "target_permission_key",
                sa.String(length=64),
                nullable=True,
            ),
            sa.Column(
                "priority",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column(
                "routing_config",
                sa.dialects.postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
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
            sa.CheckConstraint(
                "scope IN ('platform_default','vertical_default','tenant')",
                name="ck_task_routing_rules_scope",
            ),
            sa.CheckConstraint(
                "routing_mode IN ('direct_user','round_robin')",
                name="ck_task_routing_rules_routing_mode",
            ),
            sa.CheckConstraint(
                "(scope != 'vertical_default') OR (vertical IS NOT NULL)",
                name="ck_task_routing_rules_vertical_required",
            ),
            sa.CheckConstraint(
                "(scope != 'tenant') OR (tenant_id IS NOT NULL)",
                name="ck_task_routing_rules_tenant_id_required",
            ),
            sa.CheckConstraint(
                "(routing_mode != 'direct_user') OR (target_user_id IS NOT NULL)",
                name="ck_task_routing_rules_target_user_required",
            ),
            sa.CheckConstraint(
                "(routing_mode != 'round_robin') OR "
                "(target_permission_key IS NOT NULL)",
                name="ck_task_routing_rules_target_permission_required",
            ),
        )

    existing = _existing_indexes(bind, _TABLE)
    if _IDX_LOOKUP not in existing:
        op.create_index(
            _IDX_LOOKUP,
            _TABLE,
            ["task_type_key", "scope", "is_active", "priority"],
        )
    if _IDX_TENANT not in existing:
        op.create_index(
            _IDX_TENANT,
            _TABLE,
            ["tenant_id"],
            postgresql_where=sa.text("tenant_id IS NOT NULL"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    existing = _existing_indexes(bind, _TABLE)
    if _IDX_TENANT in existing:
        op.drop_index(_IDX_TENANT, table_name=_TABLE)
    if _IDX_LOOKUP in existing:
        op.drop_index(_IDX_LOOKUP, table_name=_TABLE)
    if _table_exists(bind, _TABLE):
        op.drop_table(_TABLE)
