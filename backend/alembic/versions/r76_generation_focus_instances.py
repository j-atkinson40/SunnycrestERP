"""Generation Focus instances substrate — Phase 1A canonical-pattern-establisher
of Personalization Studio implementation arc Step 1.

Per §3.26.11.12.20 single-entity-with-discriminator meta-pattern (5th canonical
application post-Session-7) + §3.26.11.12 Generation Focus canon: every
Generation Focus instance is canonically a row in ``generation_focus_instances``
keyed by ``template_type`` discriminator. Phase 1A canonical-pattern-establisher
ships ``burial_vault_personalization_studio``; Step 2 extends the same table
with ``urn_vault_personalization_studio``; future Generation Focus templates
(Wall Designer, Drawing Takeoff, Audit Prep, Mix Design, Legacy Studio,
monument customizer, engraved urn customizer, Surgical Planning, Treatment
Plan, Discharge Planning, Invoice Factoring Decision Focus per §3.26.11.12
strategic vision) extend the same table.

**Canonical schema canonical (Phase 1A canonical-pattern-establisher discipline)**:

- ``id`` (primary key UUID)
- ``company_id`` (canonical tenant scoping FK → companies.id)
- ``template_type`` (canonical discriminator; Phase 1A canonical value
  ``burial_vault_personalization_studio``; Step 2 extends with
  ``urn_vault_personalization_studio``; CHECK constraint enumerates
  canonical values to prevent silent drift)
- ``authoring_context`` (canonical 3-value enumeration per Q3
  baked at §3.26.11.12.19.3: ``funeral_home_with_family`` |
  ``manufacturer_without_family`` | ``manufacturer_from_fh_share``;
  CHECK constraint enforces canonical values)
- ``lifecycle_state`` (canonical 4-state enumeration:
  ``active`` | ``draft`` | ``committed`` | ``abandoned``;
  CHECK constraint enforces canonical values)
- Polymorphic linked entity:
  - ``linked_entity_type`` (canonical discriminator for linked entity
    polymorphism: ``fh_case`` (FH-vertical with family co-authoring)
    | ``sales_order`` (Mfg-vertical without family co-authoring)
    | ``document_share`` (Mfg-vertical reading FH-shared canvas))
  - ``linked_entity_id`` (UUID; ungated FK — polymorphic; service-layer
    enforces FK integrity per linked_entity_type + canonical authoring
    context coherence)
  - CHECK constraint enforces canonical authoring_context ↔
    linked_entity_type pairing per Q3 canonical resolution
- Canvas state polymorphism via canonical Document substrate consumption:
  - ``document_id`` (FK → documents.id; canonical Document substrate
    consumption per D-9 polymorphic substrate; canvas state persisted
    to DocumentVersion at each commit per §3.26.11.12.5)
- Canonical Generation Focus instance lifecycle metadata:
  - ``opened_at`` (when Focus opened — canonical lifecycle entry)
  - ``opened_by_user_id`` (who opened — canonical actor attribution)
  - ``last_active_at`` (canonical activity tracking; updated on canvas
    commits + state transitions)
  - ``committed_at`` (when state transitioned to ``committed``;
    canonical lifecycle exit point per §3.26.11.12.5 commit semantics)
  - ``committed_by_user_id`` (who committed)
  - ``abandoned_at`` + ``abandoned_by_user_id`` (canonical lifecycle
    abandon path symmetric with committed path)
- Family approval canonical fields per FH-vertical authoring context
  (per Q7b family portal Space template seed integration at Phase 1E):
  - ``family_approval_status`` (canonical 4-state: ``not_requested`` |
    ``requested`` | ``approved`` | ``rejected``; nullable for non-FH
    authoring contexts)
  - ``family_approval_requested_at`` + ``family_approval_decided_at``
- Standard timestamps (``created_at`` + ``updated_at``)

**Canonical indexes** (Phase 1A canonical-pattern-establisher discipline
preserves canonical query patterns Step 2 + future Generation Focus
templates inherit):

- (``company_id``, ``template_type``, ``lifecycle_state``) composite
  index for "list active instances of template type X for tenant Y"
  canonical query pattern
- (``linked_entity_type``, ``linked_entity_id``) composite index for
  "list instances linked to entity Z" canonical query pattern
- (``document_id``) for "list instance for Document substrate D"
  canonical query pattern
- (``company_id``, ``opened_by_user_id``, ``last_active_at`` DESC)
  partial index WHERE lifecycle_state = 'active' for "what am I
  currently working on?" canonical operator query

**Canonical CHECK constraints** preserve canonical-quality discipline at
substrate boundary; service-layer + future migrations extend canonical
enumerations as new template types + authoring contexts emerge.

**Q3 canonical authoring_context ↔ linked_entity_type pairing** per
§3.26.11.12.19.3 baked canonical:

- ``funeral_home_with_family`` ↔ ``fh_case`` (canonical FH-vertical;
  family co-authoring at family portal Space)
- ``manufacturer_without_family`` ↔ ``sales_order`` (canonical
  Mfg-vertical; no family co-authoring)
- ``manufacturer_from_fh_share`` ↔ ``document_share`` (canonical
  Mfg-vertical reading FH-shared canvas via D-6 DocumentShare bilateral
  consent canonical per §2.5 + r75 Q4 + Phase 1F canvas chrome canonical)

Revision ID: r76_generation_focus_instances
Revises: r75_personalization_studio_consent
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "r76_generation_focus_instances"
down_revision = "r75_personalization_studio_consent"
branch_labels = None
depends_on = None


# Canonical enumerations baked at substrate boundary per Phase 1A
# canonical-pattern-establisher discipline. Keep in sync with model layer
# (``app.models.generation_focus_instance``) + service layer.
CANONICAL_TEMPLATE_TYPES = ("burial_vault_personalization_studio",)
# Step 2 extends with ``urn_vault_personalization_studio``; future migrations
# extend with new template types via ALTER TABLE ... DROP/ADD CONSTRAINT.
# Phase 1A ships canonical-pattern-establisher set.

CANONICAL_AUTHORING_CONTEXTS = (
    "funeral_home_with_family",
    "manufacturer_without_family",
    "manufacturer_from_fh_share",
)

CANONICAL_LIFECYCLE_STATES = (
    "active",
    "draft",
    "committed",
    "abandoned",
)

CANONICAL_LINKED_ENTITY_TYPES = (
    "fh_case",
    "sales_order",
    "document_share",
)

CANONICAL_FAMILY_APPROVAL_STATUSES = (
    "not_requested",
    "requested",
    "approved",
    "rejected",
)


def _quoted_csv(values: tuple[str, ...]) -> str:
    """Render a SQL-quoted comma-separated list for IN-clause CHECK constraints."""
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "generation_focus_instances" not in inspector.get_table_names():
        op.create_table(
            "generation_focus_instances",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "company_id",
                sa.String(36),
                sa.ForeignKey("companies.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            # Canonical discriminators
            sa.Column("template_type", sa.String(64), nullable=False),
            sa.Column("authoring_context", sa.String(64), nullable=False),
            sa.Column(
                "lifecycle_state",
                sa.String(32),
                nullable=False,
                server_default="active",
            ),
            # Polymorphic linked entity per Q3 canonical pairing
            sa.Column("linked_entity_type", sa.String(64), nullable=False),
            sa.Column("linked_entity_id", sa.String(36), nullable=False),
            # Canonical Document substrate consumption per D-9
            sa.Column(
                "document_id",
                sa.String(36),
                sa.ForeignKey("documents.id", ondelete="SET NULL"),
                nullable=True,
            ),
            # Canonical Generation Focus instance lifecycle metadata
            sa.Column(
                "opened_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "opened_by_user_id",
                sa.String(36),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "last_active_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "committed_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.Column(
                "committed_by_user_id",
                sa.String(36),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "abandoned_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.Column(
                "abandoned_by_user_id",
                sa.String(36),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            # Family approval canonical (FH-vertical authoring context)
            sa.Column(
                "family_approval_status",
                sa.String(32),
                nullable=True,
            ),
            sa.Column(
                "family_approval_requested_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.Column(
                "family_approval_decided_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            # Standard timestamps
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
            # Canonical CHECK constraints — canonical-quality discipline
            # at substrate boundary per Phase 1A canonical-pattern-
            # establisher.
            sa.CheckConstraint(
                f"template_type IN ({_quoted_csv(CANONICAL_TEMPLATE_TYPES)})",
                name="ck_gen_focus_template_type",
            ),
            sa.CheckConstraint(
                f"authoring_context IN ({_quoted_csv(CANONICAL_AUTHORING_CONTEXTS)})",
                name="ck_gen_focus_authoring_context",
            ),
            sa.CheckConstraint(
                f"lifecycle_state IN ({_quoted_csv(CANONICAL_LIFECYCLE_STATES)})",
                name="ck_gen_focus_lifecycle_state",
            ),
            sa.CheckConstraint(
                f"linked_entity_type IN ({_quoted_csv(CANONICAL_LINKED_ENTITY_TYPES)})",
                name="ck_gen_focus_linked_entity_type",
            ),
            # Q3 canonical pairing: authoring_context ↔ linked_entity_type
            # baked at substrate boundary per §3.26.11.12.19.3.
            sa.CheckConstraint(
                "("
                "(authoring_context = 'funeral_home_with_family' AND linked_entity_type = 'fh_case') "
                "OR (authoring_context = 'manufacturer_without_family' AND linked_entity_type = 'sales_order') "
                "OR (authoring_context = 'manufacturer_from_fh_share' AND linked_entity_type = 'document_share')"
                ")",
                name="ck_gen_focus_authoring_linked_entity_pair",
            ),
            sa.CheckConstraint(
                f"family_approval_status IS NULL OR "
                f"family_approval_status IN ({_quoted_csv(CANONICAL_FAMILY_APPROVAL_STATUSES)})",
                name="ck_gen_focus_family_approval_status",
            ),
        )

        # Canonical query-pattern indexes per Phase 1A canonical-pattern-
        # establisher discipline.
        op.create_index(
            "ix_gen_focus_company_template_lifecycle",
            "generation_focus_instances",
            ["company_id", "template_type", "lifecycle_state"],
        )
        op.create_index(
            "ix_gen_focus_linked_entity",
            "generation_focus_instances",
            ["linked_entity_type", "linked_entity_id"],
        )
        op.create_index(
            "ix_gen_focus_document_id",
            "generation_focus_instances",
            ["document_id"],
        )
        # Partial index for "what am I currently working on?" canonical
        # operator query pattern. Postgres-only; SQLite-on-CI strips the
        # WHERE clause via the env.py op_create_index monkey-patch
        # canonical pattern.
        op.create_index(
            "ix_gen_focus_user_active",
            "generation_focus_instances",
            ["company_id", "opened_by_user_id", "last_active_at"],
            postgresql_where=sa.text("lifecycle_state = 'active'"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "generation_focus_instances" in inspector.get_table_names():
        op.drop_index(
            "ix_gen_focus_user_active",
            table_name="generation_focus_instances",
        )
        op.drop_index(
            "ix_gen_focus_document_id",
            table_name="generation_focus_instances",
        )
        op.drop_index(
            "ix_gen_focus_linked_entity",
            table_name="generation_focus_instances",
        )
        op.drop_index(
            "ix_gen_focus_company_template_lifecycle",
            table_name="generation_focus_instances",
        )
        op.drop_table("generation_focus_instances")
