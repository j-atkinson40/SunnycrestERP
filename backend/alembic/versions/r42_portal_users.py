"""Workflow Arc Phase 8e.2 — portal users + driver.portal_user_id + audit_logs.actor_type.

Ships the portal-as-space-with-modifiers identity layer. Separate
table (not a discriminator on users) per SPACES_ARCHITECTURE.md §10
— identity-level separation prevents cross-realm privilege bleed.

`drivers.portal_user_id` is the NEW optional parallel link for
portal-authed drivers. `drivers.employee_id` stays — Sunnycrest's
existing tenant-user drivers continue working unchanged (non-
destructive additive migration). Exactly one of the two columns
should be populated per Driver row in production, enforced at the
service layer (no DB CHECK constraint — allows migration windows).

`audit_logs.actor_type` discriminator carries forward audit
semantics across the two identity types. Default "tenant_user"
preserves backward compatibility — every pre-8e.2 row reads as a
tenant action.

Chain: r41_user_space_affinity → r42_portal_users.

Revision ID: r42_portal_users
Down Revision: r41_user_space_affinity
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "r42_portal_users"
down_revision = "r41_user_space_affinity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── portal_users ────────────────────────────────────────────────
    op.create_table(
        "portal_users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        # Nullable so admin-provisioned users can be invite-only until they
        # set their password through the recovery link.
        sa.Column("hashed_password", sa.String(255), nullable=True),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        # Matches SpaceConfig.space_id ("sp_<12 hex>"). Spaces live in
        # User.preferences.spaces JSONB — no FK target. Scope-enforced
        # at the session layer (portal JWT carries space_id claim).
        sa.Column("assigned_space_id", sa.String(36), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "last_login_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "failed_login_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "locked_until",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "invited_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("invite_token", sa.String(128), nullable=True),
        sa.Column(
            "invite_token_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        # Password recovery — distinct from invite_token so the two flows
        # don't collide.
        sa.Column("recovery_token", sa.String(128), nullable=True),
        sa.Column(
            "recovery_token_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint(
            "email", "company_id", name="uq_portal_users_email_company"
        ),
    )
    op.create_index(
        "ix_portal_users_company",
        "portal_users",
        ["company_id"],
    )
    # Partial unique on invite/recovery tokens (when present) to
    # prevent duplicate live tokens across users.
    op.create_index(
        "uq_portal_users_invite_token",
        "portal_users",
        ["invite_token"],
        unique=True,
        postgresql_where=sa.text("invite_token IS NOT NULL"),
    )
    op.create_index(
        "uq_portal_users_recovery_token",
        "portal_users",
        ["recovery_token"],
        unique=True,
        postgresql_where=sa.text("recovery_token IS NOT NULL"),
    )

    # ── drivers.portal_user_id ──────────────────────────────────────
    op.add_column(
        "drivers",
        sa.Column(
            "portal_user_id",
            sa.String(36),
            sa.ForeignKey("portal_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_drivers_portal_user",
        "drivers",
        ["portal_user_id"],
        postgresql_where=sa.text("portal_user_id IS NOT NULL"),
    )

    # ── audit_logs.actor_type ──────────────────────────────────────
    # Default "tenant_user" preserves backward compatibility — every
    # pre-8e.2 audit row reads as a tenant action. Portal actions
    # going forward stamp "portal_user".
    op.add_column(
        "audit_logs",
        sa.Column(
            "actor_type",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'tenant_user'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("audit_logs", "actor_type")
    op.drop_index(
        "ix_drivers_portal_user",
        table_name="drivers",
    )
    op.drop_column("drivers", "portal_user_id")
    op.drop_index(
        "uq_portal_users_recovery_token",
        table_name="portal_users",
    )
    op.drop_index(
        "uq_portal_users_invite_token",
        table_name="portal_users",
    )
    op.drop_index("ix_portal_users_company", table_name="portal_users")
    op.drop_table("portal_users")
