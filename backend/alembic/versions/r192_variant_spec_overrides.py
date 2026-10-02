"""Variant-level spec overrides, and personalization capability becomes UNKNOWABLE

Revision ID: r192_variant_spec_overrides
Revises: r191_platform_alias_seed
Create Date: 2026-10-02

⚠️ RUNS AGAINST PRODUCTION ON DEPLOY (`railway-start.sh:45`). Schema only — seven
nullable columns added, one NOT NULL dropped, and 21 rows reset to NULL. No spec
figure is loaded here; r193 does that.

TWO CHANGES, AND THE SECOND IS A RETRACTION.

1. SEVEN NULLABLE SPEC COLUMNS ON `product_variant_templates`, mirroring the
   product's. NULL means READ THROUGH TO THE PRODUCT. A variant that agrees with
   its product stores nothing, so there is exactly one place a shared figure
   lives and no way for the two tiers to disagree by omission.

   ⚠️ THIS EXISTS FOR ONE PRODUCT AND THAT IS THE POINT. Every other product's
   variants are FINISHES — Bronze, Copper, Cameo Rose — and a finish does not
   change the object's size. `Loved & Cherished`'s three variants are SIZES: 19",
   24" and 31", differing in all six dimensions. Model is a size axis there, so
   the product tier has nothing true to say and the variant tier has to.

   It is the same platform-default-over-tenant shape the catalog already uses,
   one tier further down: the narrower scope stores only its deltas and the
   resolution happens at READ time. See `docs/investigations/2026-10-02-platform-catalog-scoping.md`
   §1 for the five existing instances of that pattern.

2. ⚠️ `product_templates.personalization_capability` BECOMES NULLABLE, AND ALL 21
   EXISTING VALUES ARE RESET TO NULL.

   r186 declared it `JSON NOT NULL DEFAULT list`, so every one of the 21 rows
   currently reads `[]`. Under the semantics this column is for, `[]` is a
   CLAIM — "this product can take no personalization at all" — and it was never
   measured for any of them. It is a column default wearing a measurement's
   clothes, asserted 21 times.

   The distinction the column exists to carry is exactly:

       []     the product physically takes NO personalization   (a finding)
       NULL   nobody has established what it takes              (an absence)

   A NOT NULL column cannot express the second, so the first was being asserted
   by default. Dropping NOT NULL and resetting to NULL puts every row back to
   "unestablished", and r193 then sets the 15 the spec sheet actually covers.
   The 6 it does not cover stay NULL — Tribute Burial Vault and the five
   equipment products have no row in the sheet, so there is nothing to load and
   nothing to infer from a sibling.

   ⚠️ THIS IS THE `is_manufactured` DEFECT, FOUND BEFORE IT SHIPPED RATHER THAN
   AFTER. `docs/investigations/2026-10-02-platform-catalog-discrepancies.md` §4
   records a rule that would have read `is_manufactured=False` — a NOT NULL
   column default — as a deliberate tenant override and pinned every Wilbert
   vault as not-manufactured permanently. Same mechanism, same column shape, and
   the only reason this one is caught is that someone asked what `[]` was
   asserting before writing a consumer that trusts it.

EXPAND/CONTRACT. Both halves widen what the schema accepts, so a rolling deploy
is safe in either order: a reader compiled against NOT NULL still reads the new
nullable column, and the added columns are nullable so an old writer that omits
them is still valid. Nothing here would break a pod running the previous image.

SAFE TO REVERSE. Downgrade drops the seven columns and restores NOT NULL by
first refilling NULL with `[]`. ⚠️ That refill is LOSSY — it cannot distinguish a
measured empty set from an unestablished one, which is the whole distinction
being added. Stated here so a downgrade is not mistaken for a round trip.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "r192_variant_spec_overrides"
down_revision = "r191_platform_alias_seed"
branch_labels = None
depends_on = None


#: Mirrors `product_templates` exactly — same names, same precisions. A variant
#: override is the same KIND of figure as the product's, so it is the same type;
#: Numeric(8,4) because every figure in the source is sixteenths-exact and 1/16
#: is 0.0625.
_SPEC_COLUMNS: tuple[tuple[str, sa.types.TypeEngine], ...] = (
    ("inside_length_in", sa.Numeric(8, 4)),
    ("inside_width_in", sa.Numeric(8, 4)),
    ("inside_height_in", sa.Numeric(8, 4)),
    ("outside_length_in", sa.Numeric(8, 4)),
    ("outside_width_in", sa.Numeric(8, 4)),
    ("outside_height_in", sa.Numeric(8, 4)),
    ("weight_lb", sa.Numeric(10, 2)),
)


def upgrade() -> None:
    for name, type_ in _SPEC_COLUMNS:
        op.add_column(
            "product_variant_templates",
            sa.Column(name, type_, nullable=True),
        )

    # Drop NOT NULL and the default together. Leaving the default in place would
    # re-assert `[]` on the next insert that omits the column, which is the thing
    # being retracted.
    op.alter_column(
        "product_templates",
        "personalization_capability",
        existing_type=sa.JSON(),
        nullable=True,
        server_default=None,
    )
    op.execute("UPDATE product_templates SET personalization_capability = NULL")


def downgrade() -> None:
    # ⚠️ LOSSY. Collapses "unestablished" back into "takes none".
    op.execute(
        "UPDATE product_templates SET personalization_capability = '[]'::json "
        "WHERE personalization_capability IS NULL"
    )
    op.alter_column(
        "product_templates",
        "personalization_capability",
        existing_type=sa.JSON(),
        nullable=False,
    )
    for name, _ in reversed(_SPEC_COLUMNS):
        op.drop_column("product_variant_templates", name)
