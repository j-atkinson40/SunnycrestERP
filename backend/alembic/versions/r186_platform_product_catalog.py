"""Platform product catalog, phase 1 of 3 — PURELY ADDITIVE

Revision ID: r186_platform_product_catalog
Revises: r185_personalization_record_v2
Create Date: 2026-10-02

⚠️ THIS RUNS AGAINST PRODUCTION ON DEPLOY. `backend/railway-start.sh:45` runs
`alembic upgrade head` on every deploy, so merging this to `main` IS applying it.

WHAT IT DOES NOT TOUCH, which is the whole design of this phase:
  - `product_catalog_templates` — not altered, not dropped, not read.
  - `catalog_template_seeder` keeps writing to it, unchanged.
  - `onboarding_service` and `price_list_analysis_service` keep reading it.
Nothing in this migration can break an existing reader. Three new tables and one
new NULLABLE column.

⚠️ A PARALLEL TABLE RATHER THAN AN IN-PLACE RESHAPE, and the reason is measured:
NOTHING holds a foreign key into `product_catalog_templates` — not even
`products`, which copies from it by value. So building alongside it costs nothing
that reshaping would have saved, and every step stays independently reversible.
Measured 2026-10-02 via information_schema: 0 inbound FKs, 0 outbound FKs, PK
index only.

PHASE SEQUENCE
  Phase 1 (this)  new tables + one nullable column. Additive.
  Phase 2         backfill from the 37 production rows + the licensee spec sheet,
                  then repoint four consumers:
                    catalog_template_seeder.py:81-120      (writes 7 moved cols)
                    onboarding_service.py:1752-1759        (filters preset/category)
                    onboarding_service.py:1782-1786        (the copy path)
                    price_list_analysis_service.py:749-750 (filters preset)
  Phase 3         drop `product_catalog_templates`.

NO EXPAND/CONTRACT NEEDED HERE, stated rather than assumed. Expand/contract exists
to avoid a NOT NULL window during a rolling deploy. Three of these tables are new,
so no existing row can violate a constraint on them, and `products.variant_template_id`
is nullable. There is no window to open.

`product_families` FOLLOWS THE `verticals` SHAPE, per CLAUDE.md §5's rule that a
controlled reference is a slug-keyed lookup table. Read off the live table rather
than from a summary of it: slug varchar(32) PK, display_name varchar(100) NOT NULL,
description text, status varchar(32) NOT NULL default 'published' with a CHECK over
draft/published/archived, sort_order integer NOT NULL default 0, timestamps NOT NULL
default now(). Inbound FKs on `verticals` use ON DELETE RESTRICT, matched here.
`verticals.icon` is deliberately NOT copied — a family has no UI surface that needs
one, and an unused column is a field the table claims to model and does not.
"""
from alembic import op
import sqlalchemy as sa

revision = "r186_platform_product_catalog"
down_revision = "r185_personalization_record_v2"
branch_labels = None
depends_on = None

# The five forms a product takes. A controlled set rather than free text because
# `form` is what splits one family into rows — Triune Burial Vault and Triune Urn
# Vault are two products in one family — and a typo would silently create a sixth.
_FORMS = ("burial_vault", "urn_vault", "grave_liner", "infant", "equipment")

# ⚠️ EXACTLY TWO VALUES. Tenant ownership is expressed by a `products` row whose
# `variant_template_id` IS NULL — absence, not a third enum value. A third value
# here would let a row claim tenant ownership while still pointing at a platform
# variant, which is a state with no meaning.
_OWNERSHIP = ("wilbert", "licensee_common")


def upgrade() -> None:
    op.create_table(
        "product_families",
        sa.Column("slug", sa.String(32), primary_key=True),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # Wilbert discontinues lines, so a family needs a lifecycle rather than a
        # delete — same reason `verticals` carries one.
        sa.Column(
            "status", sa.String(32), nullable=False, server_default="published"
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_product_families_status",
        ),
    )

    op.create_table(
        "product_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("family_slug", sa.String(32), nullable=False),
        sa.Column("form", sa.String(32), nullable=False),
        sa.Column("ownership", sa.String(32), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # Constant within a product — which is the point of storing it here. All
        # five Triune finishes share one reinforcement, one weight and one set of
        # dimensions, so a correction lands once instead of five times.
        sa.Column("reinforcement", sa.String(100), nullable=True),
        # ⚠️ NUMERIC INCHES, NOT STRINGS. Every figure on the licensee spec sheet
        # is sixteenths-exact — 14-5/16 is exactly 14.3125 — so numeric(8,4) holds
        # them losslessly and the casket-clearance check can do arithmetic.
        # Fractions are a render concern, not a storage one.
        sa.Column("inside_length_in", sa.Numeric(8, 4), nullable=True),
        sa.Column("inside_width_in", sa.Numeric(8, 4), nullable=True),
        sa.Column("inside_height_in", sa.Numeric(8, 4), nullable=True),
        sa.Column("outside_length_in", sa.Numeric(8, 4), nullable=True),
        sa.Column("outside_width_in", sa.Numeric(8, 4), nullable=True),
        sa.Column("outside_height_in", sa.Numeric(8, 4), nullable=True),
        sa.Column("weight_lb", sa.Numeric(10, 2), nullable=True),
        # ⚠️ PHYSICAL CAPABILITY, NOT AVAILABILITY, AND THE TWO ARE DIFFERENT
        # LAYERS. This is the set of r185 question ids the product can physically
        # take. Whether a given licensee OFFERS one lives in
        # `wilbert_program_enrollments.personalization_config.availability` and is
        # ruled on separately (DECISIONS 2026-09-22, "Conditional requirements are
        # determined by the vault, not stored on it"). Capability bounds
        # availability; it does not replace it.
        sa.Column(
            "personalization_capability",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
        # Where the figures came from and when. A spec Bridgeable asserts wrongly
        # is discovered by a driver at a graveside, so the record carries its own
        # provenance rather than relying on whoever typed it remembering.
        sa.Column("spec_source", sa.String(200), nullable=True),
        sa.Column("spec_asof", sa.Date(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["family_slug"], ["product_families.slug"],
            name="fk_product_templates_family",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "form IN ('" + "', '".join(_FORMS) + "')",
            name="ck_product_templates_form",
        ),
        sa.CheckConstraint(
            "ownership IN ('" + "', '".join(_OWNERSHIP) + "')",
            name="ck_product_templates_ownership",
        ),
    )
    op.create_index(
        "ix_product_templates_family", "product_templates", ["family_slug"]
    )

    op.create_table(
        "product_variant_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("product_template_id", sa.String(36), nullable=False),
        # Unique platform-wide. Phase 2 carries the existing 37 SKUs across
        # verbatim — they are cited in investigation documents and in this week's
        # analysis, so a regenerated SKU would silently break those references.
        sa.Column("sku", sa.String(64), nullable=False),
        # The variant's value on its product's axis: a finish, a model, a height.
        sa.Column("option_label", sa.String(100), nullable=False),
        # The only attribute that varies WITHIN a product rather than across one.
        sa.Column("tier", sa.String(50), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["product_template_id"], ["product_templates.id"],
            name="fk_product_variant_templates_product",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("sku", name="uq_product_variant_templates_sku"),
    )
    op.create_index(
        "ix_product_variant_templates_product",
        "product_variant_templates",
        ["product_template_id"],
    )

    # ⚠️ NULLABLE, AND THE NULL CARRIES MEANING. Non-null = a platform product
    # this tenant enabled. NULL = the tenant's own product. That is the third
    # ownership value, expressed by absence, which is why `product_templates
    # .ownership` has exactly two.
    #
    # ON DELETE RESTRICT rather than the default NO ACTION, matching the inbound
    # FKs on `verticals` and `product_templates` above. Per CLAUDE.md §5's
    # constraint rule, a foreign key specifies DELETE behaviour as well as INSERT
    # acceptance, so it is stated rather than defaulted.
    op.add_column(
        "products",
        sa.Column("variant_template_id", sa.String(36), nullable=True),
    )
    op.create_foreign_key(
        "fk_products_variant_template",
        "products",
        "product_variant_templates",
        ["variant_template_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_products_variant_template",
        "products",
        ["variant_template_id"],
        postgresql_where=sa.text("variant_template_id IS NOT NULL"),
    )


def downgrade() -> None:
    # Reverse order. Lossless: Phase 1 adds no data, and the column it adds to
    # `products` is nullable and unpopulated until Phase 2.
    op.drop_index("ix_products_variant_template", table_name="products")
    op.drop_constraint("fk_products_variant_template", "products", type_="foreignkey")
    op.drop_column("products", "variant_template_id")
    op.drop_index(
        "ix_product_variant_templates_product", table_name="product_variant_templates"
    )
    op.drop_table("product_variant_templates")
    op.drop_index("ix_product_templates_family", table_name="product_templates")
    op.drop_table("product_templates")
    op.drop_table("product_families")
