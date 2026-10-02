"""Platform product catalog, phase 2a-0 — image_url on both template tiers

Revision ID: r187_product_template_images
Revises: r186_platform_product_catalog
Create Date: 2026-10-02

Adds three presentation columns: image_url on both tiers, plus display_name and
description on the VARIANT tier.

⚠️ RUNS AGAINST PRODUCTION ON DEPLOY (`railway-start.sh:45`). Additive and
nullable: two columns, no data, no consumer reads them yet.

WHY A FIELD AND NOT A CONVENTION. "Is this the same product?" turned out to be a
VISUAL question. Universal Urn Vault and "Basic Gray / Salute" are one shell in
two colours — same mould, same ribs, same base — which three separate text
sources failed to establish and one product image settled immediately. A catalog
that cannot hold the picture cannot answer the question it is most often asked.

Three consumers already named for it, none built yet:
  - the resolver's numbered-candidate disambiguation, where "Bronze Triune"
    legitimately matches two products and names alone do not separate a burial
    vault from an urn vault;
  - the Opas product pane, which is a record pane;
  - a licensee browsing their own catalog, who is choosing by eye.

Both tiers, because the axes differ: a product's image shows the shell, a
variant's shows the finish, and the Universal/Basic Gray case is precisely one
product with two variant images.

⚠️ THE VARIANT CARRIES ITS OWN NAME BECAUSE COMPOSITION BREAKS. "Bronze" +
"Triune Burial Vault" composes plausibly and that is the trap: `"19 inch"` +
`"Loved & Cherished"` is not `Loved & Cherished 19"`, and "Universal" +
"Universal Urn Vault" is nonsense. These are also the names that appear on
invoices and that the resolver must match, so they are preserved exactly rather
than reconstructed. `description` sits here too because the source carries it
per row, which makes it variant-level; the product's stays null rather than
being invented.

`display_name` is NOT NULL: every variant has one, and the table is provably
empty everywhere — it was created by r186, which is unpushed, so the table does
not exist in production and no existing row can violate the constraint.

No expand/contract needed. Both columns are nullable, so no existing row can
violate them and there is no NOT NULL window to open.
"""
from alembic import op
import sqlalchemy as sa

revision = "r187_product_template_images"
down_revision = "r186_platform_product_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "product_templates",
        sa.Column("image_url", sa.String(1000), nullable=True),
    )
    op.add_column(
        "product_variant_templates",
        sa.Column("image_url", sa.String(1000), nullable=True),
    )
    op.add_column(
        "product_variant_templates",
        sa.Column("display_name", sa.String(200), nullable=False),
    )
    op.add_column(
        "product_variant_templates",
        sa.Column("description", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("product_variant_templates", "description")
    op.drop_column("product_variant_templates", "display_name")
    op.drop_column("product_variant_templates", "image_url")
    op.drop_column("product_templates", "image_url")
