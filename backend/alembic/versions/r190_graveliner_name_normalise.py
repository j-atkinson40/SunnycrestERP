"""Correct the grave_liner product's display_name: "Grave Liner" -> "Graveliner"

Revision ID: r190_graveliner_name_normalise
Revises: r189_platform_product_aliases
Create Date: 2026-10-02

⚠️ A DATA CORRECTION TO r188, AND THEREFORE ITS OWN MIGRATION. r188 is applied;
editing an applied migration would leave databases that already ran it unchanged
while new ones got the fix, which is the dev/production divergence this whole arc
exists to remove.

THE DEFECT WAS OURS. r188 set the `grave_liner` product's display_name from the
mapping as "Grave Liner" (two words), while its own two variants read
"Graveliner" and "Graveliner (Social Service)" from the production dump, and the
sibling urn product reads "Graveliner Urn Vault". So one product disagreed with
its own children and with its sibling.

⚠️ AND IT WAS ABOUT TO BE PRESERVED BY AN ALIAS. The licensee spec sheet spells
it "Grave Liner", so the obvious move was an alias from the sheet's spelling to
our data. But our data already contained that spelling — at the product tier —
which makes the alias a RESTATEMENT of a name we hold rather than a bridge to a
name we do not. Aliasing around an inconsistency we introduced would have frozen
it. The product is corrected, and the sheet's two-word spelling then appears
nowhere in our data and becomes a genuine alias.

Variant names are NOT touched: they carry the dump's exact strings, which are the
ones that land on invoices and that the resolver must match.

Idempotent and narrow: it matches on the current value, so re-running is a no-op
and a hand-edited name is left alone rather than overwritten.
"""
from alembic import op
import sqlalchemy as sa

revision = "r190_graveliner_name_normalise"
down_revision = "r189_platform_product_aliases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE product_templates SET display_name = 'Graveliner' "
            "WHERE family_slug = 'graveliner' AND form = 'grave_liner' "
            "AND display_name = 'Grave Liner'"
        )
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE product_templates SET display_name = 'Grave Liner' "
            "WHERE family_slug = 'graveliner' AND form = 'grave_liner' "
            "AND display_name = 'Graveliner'"
        )
    )
