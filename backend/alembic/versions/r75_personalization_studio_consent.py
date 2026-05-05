"""Personalization Studio cross-tenant sharing consent — Step 0 migration of Personalization Studio implementation arc Step 1.

Per Q4 canonical resolution (column-per-capability discipline) +
§3.26.11.10 cross-tenant Focus consent canonical + §2.5 portal-extension
foundation:

**Canonical 4-state machine stored directly at column substrate** per
Q4 canonical direction:

- ``default`` — canonical privacy-preserving baseline (initial state of
  every PTR row; no consent expressed in either direction)
- ``pending_outbound`` — caller (this PTR row's tenant) has requested
  upgrade; partner has not yet accepted
- ``pending_inbound`` — partner has requested upgrade; caller has not
  yet accepted
- ``active`` — bilateral consent in force; canonical cross-tenant
  DocumentShare grant of personalization Generation Focus Document
  substrate authorized

**Canonical-substrate-shape distinction from Calendar Step 4.1**: Calendar
Step 4.1 stores per-side intent (``free_busy_only`` | ``full_details``)
and resolves the bilateral 4-state machine at service-layer state
resolver from the (forward, reverse) tuple. Q4 canonical direction for
personalization_studio capability stores the canonical 4-state machine
DIRECTLY at column substrate per-tenant-perspective: each PTR row's
column reflects the bilateral state from THAT tenant's canonical
perspective. State transitions update BOTH PTR rows (forward + reverse)
synchronously per dual-row canonical pattern. Service layer reads state
directly from caller's row (no resolver needed).

**Canonical state machine transitions** (dual-row update pattern):

- ``request_*``: forward (caller side) ``default → pending_outbound``;
  reverse (partner side) ``default → pending_inbound``
- ``accept_*``: forward (acceptor side) ``pending_inbound → active``;
  reverse (requester side) ``pending_outbound → active``
- ``revoke_*``: forward (revoker side) ``* → default``;
  reverse (partner side) ``* → default``

**Q3 canonical metadata columns** parallel to Calendar Step 4.1
precedent — settings-page rendering ergonomics ("Last updated 3 days
ago by Jane"). NULL when consent has never been changed (canonical
default-state rows). Stamped on first state flip on caller's side
(reverse-row metadata stamped synchronously with caller-row metadata
per dual-row canonical pattern).

**Column-per-capability discipline (Q4 canonical)**: Calendar's
``calendar_freebusy_consent`` column is the canonical-pattern-establisher
precedent at PTR substrate level (column-per-capability discipline);
this column is the second canonical instance of the same column-per-capability
pattern. Per-capability state-machine storage shape may differ
canonically per capability (Calendar stores per-side intent + resolver;
Personalization Studio stores 4-state directly + dual-row updates) —
the canonical column-per-capability discipline holds at substrate
boundary while per-capability state-machine semantics are canonical
service-layer concerns.

**Default-state rows are NOT backfilled** — column ships with
server_default ``default`` so existing PTR rows render at canonical
default state. Settings-page rendering treats NULL ``updated_at`` as
"never changed" canonical state.

Revision ID: r75_personalization_studio_consent
Revises: r74_personalization_vocabulary_canonicalization
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "r75_personalization_studio_consent"
down_revision = "r74_personalization_vocabulary_canonicalization"
branch_labels = None
depends_on = None


# Canonical 4-state machine values per Q4. Keep in sync with model layer
# (``app.models.platform_tenant_relationship``) + service layer
# (``app.services.calendar.ptr_consent_service``).
CANONICAL_PERSONALIZATION_STUDIO_STATES = (
    "default",
    "pending_outbound",
    "pending_inbound",
    "active",
)


def _quoted_csv(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = {
        col["name"]
        for col in inspector.get_columns("platform_tenant_relationships")
    }

    # Canonical consent column — column-per-capability discipline (Q4)
    # storing canonical 4-state machine directly per Q4 canonical
    # direction.
    if "personalization_studio_cross_tenant_sharing_consent" not in columns:
        op.add_column(
            "platform_tenant_relationships",
            sa.Column(
                "personalization_studio_cross_tenant_sharing_consent",
                sa.String(32),
                nullable=False,
                server_default="default",
            ),
        )

    # CHECK constraint enumerating canonical 4 state values per
    # canonical-quality discipline at substrate boundary. Idempotent
    # via existence check on pg_constraint.
    constraint_exists = bind.execute(
        sa.text(
            """
            SELECT 1 FROM pg_constraint
            WHERE conname = 'ck_ptr_personalization_studio_consent'
            AND conrelid = 'platform_tenant_relationships'::regclass
            """
        )
    ).first()
    if constraint_exists is None:
        op.create_check_constraint(
            "ck_ptr_personalization_studio_consent",
            "platform_tenant_relationships",
            f"personalization_studio_cross_tenant_sharing_consent IN "
            f"({_quoted_csv(CANONICAL_PERSONALIZATION_STUDIO_STATES)})",
        )

    # Q3 canonical metadata columns — parallel to Calendar Step 4.1
    # precedent.
    if (
        "personalization_studio_cross_tenant_sharing_consent_updated_at"
        not in columns
    ):
        op.add_column(
            "platform_tenant_relationships",
            sa.Column(
                "personalization_studio_cross_tenant_sharing_consent_updated_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        )

    if (
        "personalization_studio_cross_tenant_sharing_consent_updated_by"
        not in columns
    ):
        op.add_column(
            "platform_tenant_relationships",
            sa.Column(
                "personalization_studio_cross_tenant_sharing_consent_updated_by",
                sa.String(36),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {
        col["name"]
        for col in inspector.get_columns("platform_tenant_relationships")
    }

    if (
        "personalization_studio_cross_tenant_sharing_consent_updated_by"
        in columns
    ):
        op.drop_column(
            "platform_tenant_relationships",
            "personalization_studio_cross_tenant_sharing_consent_updated_by",
        )

    if (
        "personalization_studio_cross_tenant_sharing_consent_updated_at"
        in columns
    ):
        op.drop_column(
            "platform_tenant_relationships",
            "personalization_studio_cross_tenant_sharing_consent_updated_at",
        )

    # Drop CHECK constraint before dropping the column it references.
    constraint_exists = bind.execute(
        sa.text(
            """
            SELECT 1 FROM pg_constraint
            WHERE conname = 'ck_ptr_personalization_studio_consent'
            AND conrelid = 'platform_tenant_relationships'::regclass
            """
        )
    ).first()
    if constraint_exists is not None:
        op.drop_constraint(
            "ck_ptr_personalization_studio_consent",
            "platform_tenant_relationships",
            type_="check",
        )

    if "personalization_studio_cross_tenant_sharing_consent" in columns:
        op.drop_column(
            "platform_tenant_relationships",
            "personalization_studio_cross_tenant_sharing_consent",
        )
