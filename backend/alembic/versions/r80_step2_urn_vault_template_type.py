"""Step 2 substrate-consumption-follower extension — extend
``ck_gen_focus_template_type`` CHECK constraint with
``urn_vault_personalization_studio``.

Per r76 directive ("Step 2 extends with ``urn_vault_personalization_studio``;
future migrations extend with new template types via ALTER TABLE ...
DROP/ADD CONSTRAINT") + Phase 2A scope canonical-extension at substrate
boundary.

Pattern parallels r77 r70-CHECK-extension precedent:
  1. DROP existing CHECK constraint (idempotent IF EXISTS guard).
  2. ADD CHECK constraint with extended 2-value enum.

Down-migration restores r76's 1-value enum (preserves canonical history
continuity discipline). Pre-r79 rows have ``template_type=
'burial_vault_personalization_studio'`` only; canonical down preserves
existing data without DELETE.

Revision ID: r80_step2_urn_vault_template_type
Revises: r79_platform_themes
"""

from __future__ import annotations

from alembic import op


revision = "r80_step2_urn_vault_template_type"
down_revision = "r79_platform_themes"
branch_labels = None
depends_on = None


# Step 2 extended canonical enum — keep in sync with
# ``app.models.generation_focus_instance.CANONICAL_TEMPLATE_TYPES``.
_STEP2_TEMPLATE_TYPES = (
    "burial_vault_personalization_studio",
    "urn_vault_personalization_studio",
)


_R76_TEMPLATE_TYPES = ("burial_vault_personalization_studio",)


def _quoted_csv(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    """Drop r76 CHECK + recreate with extended 2-value enum."""

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_gen_focus_template_type'
            ) THEN
                ALTER TABLE generation_focus_instances
                DROP CONSTRAINT ck_gen_focus_template_type;
            END IF;
        END
        $$;
        """
    )

    op.execute(
        f"""
        ALTER TABLE generation_focus_instances
        ADD CONSTRAINT ck_gen_focus_template_type
        CHECK (template_type IN ({_quoted_csv(_STEP2_TEMPLATE_TYPES)}));
        """
    )


def downgrade() -> None:
    """Restore r76 CHECK constraint (1-value enum).

    Pre-r79 rows have ``template_type='burial_vault_personalization_studio'``
    only; canonical down preserves existing data without DELETE.
    """

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_gen_focus_template_type'
            ) THEN
                ALTER TABLE generation_focus_instances
                DROP CONSTRAINT ck_gen_focus_template_type;
            END IF;
        END
        $$;
        """
    )

    op.execute(
        f"""
        ALTER TABLE generation_focus_instances
        ADD CONSTRAINT ck_gen_focus_template_type
        CHECK (template_type IN ({_quoted_csv(_R76_TEMPLATE_TYPES)}));
        """
    )
