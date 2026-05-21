"""Widget definitions — composition substrate extension (WB-1).

First widget-builder sub-arc per investigation
`docs/investigations/2026-05-21-widget-builder.md`. Establishes the
persistence + serialization substrate that WB-2 through WB-8 all
consume. Foundational; invisible to operators (no UI changes).

Per Area 7 lock (Q-29 + Q-30 + Q-31):

  • composition_blob (JSONB nullable) — the composed widget shape.
    NULL on every existing row (legacy hand-coded widgets remain
    code-rendered; their composition lives in React component code,
    not in the DB).
  • composition_version (Integer nullable) — schema_version tracker
    on the blob. Phase 1 stamp = 1.
  • tier_scope ({'platform', 'vertical'}, NOT NULL, default 'platform')
    — Tier-1 + Tier-2 discrimination per Q-38. Existing rows
    backfilled to 'platform' (Tier-1 platform-shipped).
  • last_edit_session_id (UUID nullable) + last_edit_session_at
    (TIMESTAMPTZ nullable) + last_edit_session_actor_id (UUID nullable)
    — mirrors r102/r103 session-aware versioning pattern per Q-31.

CHECK constraint enforces blob+version mutual presence:
  (composition_blob IS NULL AND composition_version IS NULL) OR
  (composition_blob IS NOT NULL AND composition_version IS NOT NULL)

Idempotent (matches r103 + migration-arc 9e47a3e precedent): each
DDL step is gated on inspector-reported state.

Reversible: downgrade drops the CHECK + all 6 added columns.

Migration head: r104_migrate_focus_templates_to_freeform → r105.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "r105_widget_definitions_composition_extension"
down_revision = "r104_migrate_focus_templates_to_freeform"
branch_labels = None
depends_on = None


_TABLE = "widget_definitions"
_CHECK_NAME = "ck_widget_definitions_composition_blob_version_paired"
_TIER_SCOPE_ENUM_VALUES = ("platform", "vertical")


def _existing_columns(bind, table_name: str) -> set[str]:
    insp = sa.inspect(bind)
    if table_name not in insp.get_table_names():
        return set()
    return {col["name"] for col in insp.get_columns(table_name)}


def _existing_check_constraints(bind, table_name: str) -> set[str]:
    insp = sa.inspect(bind)
    if table_name not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_check_constraints(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    cols = _existing_columns(bind, _TABLE)

    if "composition_blob" not in cols:
        op.add_column(
            _TABLE,
            sa.Column(
                "composition_blob",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
        )

    if "composition_version" not in cols:
        op.add_column(
            _TABLE,
            sa.Column("composition_version", sa.Integer(), nullable=True),
        )

    if "tier_scope" not in cols:
        # Add nullable first so backfill can populate; tighten to NOT
        # NULL after backfill. Matches r103/precedent two-step shape.
        op.add_column(
            _TABLE,
            sa.Column("tier_scope", sa.String(length=20), nullable=True),
        )

    # Backfill existing rows to tier_scope='platform' per investigation
    # Area 10 (all existing widget_definitions are platform-shipped
    # hand-coded widgets seeded via `seed_widget_definitions`).
    op.execute(
        sa.text(
            "UPDATE widget_definitions SET tier_scope = 'platform' "
            "WHERE tier_scope IS NULL"
        )
    )

    # Re-inspect; if any rows landed without backfill (concurrent
    # insert during migration window — vanishingly rare on a single-
    # writer migration runner), the ALTER COLUMN NOT NULL will fail
    # loud, which is the correct behavior.
    op.alter_column(
        _TABLE,
        "tier_scope",
        existing_type=sa.String(length=20),
        nullable=False,
        server_default=sa.text("'platform'"),
    )

    # Enum value check (CHECK constraint — keeps the column shape
    # storage-agnostic; future-proofs adding values without a PG enum
    # ALTER ceremony).
    existing_checks = _existing_check_constraints(bind, _TABLE)
    enum_check_name = "ck_widget_definitions_tier_scope_enum"
    if enum_check_name not in existing_checks:
        op.create_check_constraint(
            enum_check_name,
            _TABLE,
            "tier_scope IN ('platform', 'vertical')",
        )

    if "last_edit_session_id" not in cols:
        op.add_column(
            _TABLE,
            sa.Column(
                "last_edit_session_id",
                postgresql.UUID(as_uuid=False),
                nullable=True,
            ),
        )
    if "last_edit_session_at" not in cols:
        op.add_column(
            _TABLE,
            sa.Column(
                "last_edit_session_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        )
    if "last_edit_session_actor_id" not in cols:
        op.add_column(
            _TABLE,
            sa.Column(
                "last_edit_session_actor_id",
                postgresql.UUID(as_uuid=False),
                nullable=True,
            ),
        )

    # CHECK: composition_blob + composition_version are jointly present
    # or jointly absent. Prevents drift where a blob lands without a
    # schema version anchor (or vice versa).
    existing_checks = _existing_check_constraints(bind, _TABLE)
    if _CHECK_NAME not in existing_checks:
        op.create_check_constraint(
            _CHECK_NAME,
            _TABLE,
            "(composition_blob IS NULL AND composition_version IS NULL) "
            "OR (composition_blob IS NOT NULL "
            "AND composition_version IS NOT NULL)",
        )


def downgrade() -> None:
    bind = op.get_bind()
    cols = _existing_columns(bind, _TABLE)
    checks = _existing_check_constraints(bind, _TABLE)

    if _CHECK_NAME in checks:
        op.drop_constraint(_CHECK_NAME, _TABLE, type_="check")

    enum_check_name = "ck_widget_definitions_tier_scope_enum"
    if enum_check_name in checks:
        op.drop_constraint(enum_check_name, _TABLE, type_="check")

    if "last_edit_session_actor_id" in cols:
        op.drop_column(_TABLE, "last_edit_session_actor_id")
    if "last_edit_session_at" in cols:
        op.drop_column(_TABLE, "last_edit_session_at")
    if "last_edit_session_id" in cols:
        op.drop_column(_TABLE, "last_edit_session_id")
    if "tier_scope" in cols:
        op.drop_column(_TABLE, "tier_scope")
    if "composition_version" in cols:
        op.drop_column(_TABLE, "composition_version")
    if "composition_blob" in cols:
        op.drop_column(_TABLE, "composition_blob")
