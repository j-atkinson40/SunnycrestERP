"""The natural key the catalog resolves through becomes a key the database holds

Revision ID: r194_product_template_natural_key
Revises: r193_load_licensee_specs
Create Date: 2026-10-03

⚠️ RUNS AGAINST PRODUCTION ON DEPLOY (`railway-start.sh:45`). One unique
constraint. No column added, no row written, no row read. Deliberately alone.

WHAT THIS FIXES, AND WHY IT IS A CONSTRAINT RATHER THAN A CODE REVIEW.

`(family_slug, form)` is the natural key the entire platform catalog resolves
through, and until now the schema did not enforce it. `product_templates` carried
only `id` as PRIMARY KEY and a **non-unique** index on `family_slug`.

⚠️ THE FAILURE MODE IS SILENT, WHICH IS WHY IT NEEDED A SCHEMA FIX RATHER THAN
CARE AT THE CALL SITE. `r193:607` resolves products into a Python dict:

    products = {
        (r.family_slug, r.form): r.id
        for r in bind.execute(sa.text("SELECT id, family_slug, form FROM ..."))
    }

A duplicate key does not raise. The dict COLLAPSES it — last row wins — and one
product becomes permanently unreachable with nothing reported. Demonstrated rather
than argued: two rows in, dict size 1.

That is a check that cannot fail, and the remedy for a check that cannot fail is
not to remember not to create duplicates. It is a key the database refuses to
duplicate. See CLAUDE.md §11, *Removal before recognition*: a validated field is a
hole with a guard on it; an absent field is not a hole. After this migration a
duplicate is UNEXPRESSIBLE rather than merely discouraged.

⚠️ THE ASYMMETRY IS THE TELL, AND IT WAS INSIDE ONE MIGRATION. `r186` created four
tables. Three got their natural key enforced and one did not:

    product_variant_templates   uq_..._sku UNIQUE (sku)                 enforced
    product_families            PRIMARY KEY (slug)                      enforced
    platform_product_aliases    UNIQUE (variant_template_id, alias_...) enforced
    product_templates           — nothing —                             ⚠️ NOT

So `r193`'s two lookup dicts have different safety: `variants = {sku: id}` is
backed by a unique constraint and cannot collapse; `products` was not and could.
Same file, same pattern, one of them unguarded.

MEASURED BEFORE WRITING, in both environments that matter:

    bridgeable_dev   21 rows, 21 distinct (family_slug, form)   no duplicates
    production       21 rows, 21 distinct (family_slug, form)   no duplicates
                     (read-only, connection-level guard, 2026-10-03)

⚠️ IF THIS MIGRATION FAILS, THAT IS THE AUDIT AND NOT AN OBSTACLE. A failure means
duplicates exist somewhere not measured above, and the duplicates are the finding.
Report them; do not work around the constraint. The ruling is explicit on this
point.

WHAT IS DELIBERATELY NOT HERE. The non-unique `ix_product_templates_family`
becomes largely redundant — the unique constraint's own index serves
`family_slug`-prefix lookups. Dropping it is a second change and this migration is
alone on purpose, so it stays. Note it for a later cleanup rather than tidying it
in passing.

BLOCKS NOTHING IT SHOULD NOT. No catalog row collides today, so this applies to a
clean table. It must land BEFORE any migration that adds a row which could collide
on the key — which is exactly the odd-sized burial vaults, now ruled to be size
VARIANTS rather than products and therefore no longer a collision risk at all.

EXPAND/CONTRACT. ⚠️ This NARROWS what the schema accepts, so it is not a pure
expansion. It is safe here only because the existing rows already satisfy it in
both environments, measured above — a writer on the previous image that tried to
insert a duplicate would now fail, and nothing does. A rolling deploy is safe
because no code path creates a second row for an existing (family_slug, form).
"""
from __future__ import annotations

from alembic import op

revision = "r194_product_template_natural_key"
down_revision = "r193_load_licensee_specs"
branch_labels = None
depends_on = None

#: Named to match its enforced siblings on the tables r186 created —
#: `uq_product_variant_templates_sku`, `uq_platform_product_aliases_variant_text`.
CONSTRAINT = "uq_product_templates_family_form"


def upgrade() -> None:
    op.create_unique_constraint(
        CONSTRAINT, "product_templates", ["family_slug", "form"]
    )


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT, "product_templates", type_="unique")
