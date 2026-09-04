"""Note surface session 1 — per-user-per-day note identity + standing-set overrides.

Two tables, one migration, because the note shell and the standing-set register
want their storage decided together.

⚠️ THE THREE TIERS ARE NOT ALL STORED, AND THAT IS THE DESIGN. The cascade is

    code role template  →  tenant override  →  user override

and only the last two are rows. The role tier is code-declared, keyed on
(vertical, role_slug), following `spaces/registry.py::SEED_TEMPLATES` rather than
the Focus layout-state pattern the session-1 dispatch originally named — Focus's
three tiers are `active user session → recent closed user session → tenant
default`, which is two user-scoped tiers plus a tenant baseline and has no role
tier at all. Composing the spaces precedent (role) with the Focus precedent
(tenant + user) beats inventing a tier.

The consequence for this migration: there is no `role` table here. A role's
standing set is a design artifact that ships with the vertical, not tenant data,
and it belongs on the code side of the code-declared/config-enabled split the
fragment registry already follows.

⚠️ `standing_set_configs` HOLDS OVERRIDES, NOT COMPLETE SETS. A row states what
this tenant or this user changed about the tier beneath it. An absent row means
"inherit", which is distinct from an empty `entries` array meaning "inherit
nothing — show no standing set". Both are legal and they are not the same, so
`entries` is NOT NULL and the absence of a row is the only way to say inherit.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "r175_note_surface_foundation"
down_revision = "r174_gl_category_correction"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── The note's identity ──────────────────────────────────────────
    # One note per user per day. NOT one per Space: Space selection is a
    # filter on which fragments appear, never a separate surface, so the
    # Space is deliberately absent from this key.
    #
    # `note_date` is a DATE in the TENANT's local day, resolved by the
    # caller before it reaches here. Storing a date rather than a timestamp
    # is what makes "the note for 2026-09-04" answerable without knowing
    # which timezone the reader is in — the settling hour (session 4) moves
    # the boundary, not the identity.
    op.create_table(
        "daily_notes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("note_date", sa.Date(), nullable=False),
        # Session 4 flips this at the tenant-configured settling hour. It
        # exists now because the day identity that will settle must exist
        # now, and adding it later would mean a second migration over rows
        # that already carry the meaning.
        sa.Column(
            "settled_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    # The identity itself. One note per user per day is enforced here rather
    # than in application code, because "get or create today's note" runs on
    # every page load and a race would otherwise mint two.
    op.create_unique_constraint(
        "uq_daily_notes_user_date", "daily_notes", ["user_id", "note_date"]
    )

    # ── Standing-set overrides (tiers 2 and 3) ───────────────────────
    op.create_table(
        "standing_set_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # NULL user_id => the TENANT override (tier 2).
        # non-NULL      => that user's override (tier 3).
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        # The ordered entry list. NOT NULL: an absent ROW means inherit; an
        # empty ARRAY means "inherit nothing". Distinct states, both legal.
        sa.Column(
            "entries",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    # At most one tenant override per company, and at most one per user.
    # Two partial uniques rather than one composite, because NULL never
    # equals NULL in a composite unique and the tenant row would not be
    # constrained at all — a real trap, and the reason this is written out.
    op.create_index(
        "uq_standing_set_tenant",
        "standing_set_configs",
        ["company_id"],
        unique=True,
        postgresql_where=sa.text("user_id IS NULL"),
    )
    op.create_index(
        "uq_standing_set_user",
        "standing_set_configs",
        ["company_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_standing_set_user", table_name="standing_set_configs")
    op.drop_index("uq_standing_set_tenant", table_name="standing_set_configs")
    op.drop_table("standing_set_configs")
    op.drop_constraint(
        "uq_daily_notes_user_date", "daily_notes", type_="unique"
    )
    op.drop_table("daily_notes")
