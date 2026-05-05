"""Phase 1E Path B substrate consumption — add ``action_payload`` JSONB column
to ``generation_focus_instances``.

Per §3.26.11.12 Generation Focus canon + §3.26.11.12.19 Personalization
Studio canonical category + Phase 1E build prompt: family-approval flow
consumes Path B platform_action_tokens substrate. The action shape per
§3.26.15.17 + §3.26.16.18 + §3.26.17.18 + §3.26.18.20 lives in a JSONB
column on the parent entity (mirrors ``email_messages.message_payload``
+ ``calendar_events.action_payload`` precedents). Phase 1E adds
``generation_focus_instances.action_payload`` for the
``personalization_studio_family_approval`` action_type.

The Phase 1E action shape:

.. code-block:: json

   {
     "actions": [
       {
         "action_type": "personalization_studio_family_approval",
         "action_target_type": "generation_focus_instance",
         "action_target_id": "<instance UUID>",
         "action_metadata": {
           "decedent_name": "...",
           "vault_product_name": "...",
           "fh_director_name": "...",
           "family_email": "...",
           "preview_url": "..."
         },
         "action_status": "pending",
         "action_completed_at": null,
         "action_completed_by": null,
         "action_completion_metadata": null
       }
     ]
   }

Status flow: ``pending`` → ``approved`` | ``request_changes`` | ``declined``.
``request_changes`` is non-terminal at the Quote-precedent sense — the
operator (FH director) follows up with a revised canvas; new send creates
a new action at the next index. ``approved`` and ``declined`` are terminal.

GIN index `ix_generation_focus_instances_action_payload` supports
cross-primitive action queries.

Revision ID: r78_generation_focus_action_payload
Revises: r77_path_b_generation_focus_extension
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "r78_generation_focus_action_payload"
down_revision = "r77_path_b_generation_focus_extension"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = {
        col["name"]
        for col in inspector.get_columns("generation_focus_instances")
    }
    if "action_payload" not in columns:
        op.add_column(
            "generation_focus_instances",
            sa.Column(
                "action_payload",
                sa.JSON().with_variant(
                    sa.dialects.postgresql.JSONB(), "postgresql"
                ),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )

    op.execute(
        "CREATE INDEX IF NOT EXISTS "
        "ix_generation_focus_instances_action_payload "
        "ON generation_focus_instances USING gin "
        "(action_payload jsonb_path_ops)"
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS ix_generation_focus_instances_action_payload"
    )

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {
        col["name"]
        for col in inspector.get_columns("generation_focus_instances")
    }
    if "action_payload" in columns:
        op.drop_column("generation_focus_instances", "action_payload")
