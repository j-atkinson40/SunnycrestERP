"""Included chairs live on the equipment bundle.

Ruling B' (James, 2026-10-30): *"Included chairs live on the equipment bundle: new
column products.included_chairs (integer, nullable; null = not an equipment bundle).
Migration approved."*

⚠️ WHAT IT REPLACES IS A GLOBAL CONSTANT THAT WAS WRONG FOR TWO BUNDLES.
`typed_extraction.CHAIRS_INCLUDED = 8` was subtracted from every chair count regardless
of which bundle the director named — measured 2026-10-30 on production: `"device only,
10 chairs"` billed 2 extras, subtracting eight chairs from a bundle that includes none.
The number is a property of the bundle, so it lives on the bundle.

⚠️ NULLABLE, AND `NULL` IS A MEANING RATHER THAN A GAP. Per the ruling, `null = not an
equipment bundle`, which is true of every product that is not one of the five. That is
why there is no server default and no backfill of zero: a default of 0 would assert
"this bundle includes no chairs" about every vault in the catalog, which is the
plausible-value trap CLAUDE.md §5 names — "not manufactured" and "takes no
personalization" are the two instances already recorded there.

⚠️ AND THAT IS ALSO WHY THIS MIGRATION WRITES NO DATA. The five Sunnycrest rows are a
separate, separately-authorised production write. A migration that filled them would be
asserting business facts from a schema change, and four of the five values are James's
numbers rather than anything derivable from the catalog — the price list says only that
"the first 8 are included in a package", with no per-bundle breakdown recorded anywhere
(`docs/investigations/2026-10-03-price-list-reconciliation.md:415`).

Downgrade drops the column. Nothing reads it before the backfill, and the code that will
read it treats NULL as "cannot derive" rather than guessing — so the intermediate state
is loud, not silently wrong.
"""

from alembic import op
import sqlalchemy as sa

revision = "r218_included_chairs"
down_revision = "r217_opas_why_and_rulebook"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "included_chairs",
            sa.Integer(),
            nullable=True,
            comment=(
                "Chairs included in this equipment bundle. NULL means the product is "
                "not an equipment bundle. Billable extras are "
                "max(0, chairs_total - included_chairs). Ruling B', James 2026-10-30."
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("products", "included_chairs")
