"""Load the price list into the catalog: urns as a form, odd sizes as variants

Revision ID: r195_price_list_catalog_load
Revises: r194_product_template_natural_key
Create Date: 2026-10-03

⚠️ RUNS AGAINST PRODUCTION ON DEPLOY (`railway-start.sh:45`). Extends one CHECK
constraint, adds 8 families / 8 products / 15 variants, and updates 16 existing
rows. No row is deleted.

SOURCE: `docs/catalog/2026-02-01-sunnycrest-funeral-price-list.pdf`, md5
`ab3fb519423c09fd766b0a265f288cee`, pinned by `tests/test_price_list_provenance.py`
and read page-by-page against a 200dpi rasterisation rather than trusted from text
extraction. The map is `docs/catalog/2026-10-03-price-list-to-catalog-map.md`.

AUTHORITY: *"Do what our price list says."* The price list is authoritative for
catalog MEMBERSHIP and ORGANIZATION; the spec sheet is authoritative for
DIMENSIONS only.

WHAT THIS DOES, and the basis for each:

1. **`urn` joins the form vocabulary.** ⚠️ An urn is NOT a vault, so these do not
   fold into `urn_vault`. Extends `ck_product_templates_form`.

2. **Twelve stocked urns** — 8 products, 12 variants, ownership `wilbert`.
   ⚠️ OWNERSHIP IS INFERRED, NOT MEASURED. The pattern: `P445`, `P440`, `P363`,
   `P600`, `P300`, `P310` share the P-number scheme with `P400WS` and `P410` on the
   spec sheet, and those were already ruled Wilbert products. A tenant does not
   mint P-numbers. **FALSIFIER: Sunnycrest buying these from a non-Wilbert supplier
   who also uses P-numbers.** Stocking and price remain Sunnycrest's; this table
   holds neither.

3. **Three odd sizes become VARIANTS, not products.** `Loved & Cherished` is the
   precedent — one product, three sizes, three prices — so price being
   variant-level is already established.
   ⚠️ THE INFERENCE IS "Continental 34\" IS A CONTINENTAL", not "Continental 34\"
   is Single Reinforced". The page does not say the second. As a variant it carries
   no reinforcement at all; the attribute lives on the parent, which the page DOES
   state. **FALSIFIER: a source showing the odd size is built differently from its
   parent** — different wall thickness, reinforcement, or mold line. The price
   list's `ODD SIZED` grouping is weak contrary evidence; nothing resolves it, and
   nothing needs to until something reads a dimension.

4. **`option_label` stays ONE axis**, values heterogeneous in what they vary.
   Graveliner carries `Standard`, `Social Service`, `34 inch`, `38 inch` as a flat
   list. ⚠️ This looks like a grade axis crossed with a size axis ONLY IF THE
   CROSS-PRODUCT EXISTS, AND IT DOES NOT — there is no Graveliner SS at 34" on the
   price list, in the tenant seeder, or anywhere else. Two axes would create six
   slots to hold four real things, and the two empties would then need a reason to
   be empty that nobody has. Basis: **decided**.
   **FALSIFIER: any source offering a crossed configuration** (Graveliner SS in 34"
   or 38"). That is the day it becomes two axes. It is not today, and building for
   it now is the same move as mapping shells to products before anything needs
   dimensions.

5. **`BV-CON`'s `option_label` becomes `Standard`.** Basis: **decided** — the price
   list says "Continental", not "Continental Standard". `Continental` restates the
   product rather than naming a value on any axis, which is invisible at one
   variant and wrong the moment `34 inch` joins it. Parallel to `GL-STD` by our
   choice, not by the source.

6. **`UV-VET`'s display name** becomes `Veteran Triune Urn Vault`. **Measured** —
   the price list (p2, Double Reinforced) and `sunnycrest_product_seeder.py:173`
   agree; the spec sheet and this catalog were the outliers.
   ⚠️ **THE SKU STAYS `UV-VET` PERMANENTLY.** The cosmetic inconsistency with
   `UV-BTRI`/`UV-CTRI`/`UV-SSTRI`/`UV-CRTRI` is DELIBERATE. A SKU is an identifier:
   unambiguous, and referenced in `r188:262`, two migration docstrings, two
   investigation documents and `catalog_template_seeder.py:49`. Renaming it for
   consistency is churn with real blast radius and no user-visible benefit. If you
   are reading this because it looks wrong: it is known, and it stays.

7. **`reinforcement` on 14 products, measured from the price list's group
   headings.** Seven products keep NULL — 2 because the source withholds a tier
   (`universal` has its own group with no reinforcement word; `loved-and-cherished`
   has its own block) and 5 because the concept does not apply to a tent or a
   lowering device. ⚠️ KEY ON THE COLUMN, NEVER ON LABEL TEXT: `option_label`
   already holds `Single` and `Double` as **Tent** variant values.

WHAT THIS DELIBERATELY DOES NOT DO:

- **No price is written, for anything.** `product_templates` has no price column —
  price lives on the tenant `products` row. So James's two rulings are recorded in
  the map and have nothing to write here: `Vault Placer` at **$0.00** (measured,
  correct, no additional cost) and `CE-CT` Cremation Table at **NULL** (exists, not
  on this price list, price NOT established and NOT zero). ⚠️ Those two resolve
  OPPOSITELY from identical-looking absences, which is why neither was defaulted.
- **`CE-CT` is NOT deleted.** It exists; it is simply not on the February 2026
  list. Absence from a price list is not absence from the world.
- **Graveside packages and fee lines are not products.** Services composed of
  equipment products, and billing rules. They get their own design.
- **Spec-sheet-only names do not become products** — already ruled.

SAFE TO REVERSE. Downgrade deletes exactly the rows this adds, restores the two
labels, nulls the 14 tiers, and narrows the CHECK back. ⚠️ The CHECK narrowing
fails if any `urn` row survives, which is the correct behaviour rather than a flaw.
"""
from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision = "r195_price_list_catalog_load"
down_revision = "r194_product_template_natural_key"
branch_labels = None
depends_on = None

#: Same fixed namespace as r188, so ids are reproducible across environments and
#: consistent with the rows already in the table.
_NS = uuid.UUID("6f1b4a52-0000-5000-8000-000000000000")


def _id(*parts: str) -> str:
    return str(uuid.uuid5(_NS, "|".join(parts)))


FORMS_BEFORE = ("burial_vault", "urn_vault", "grave_liner", "infant", "equipment")
FORMS_AFTER = FORMS_BEFORE + ("urn",)
FORM_CHECK = "ck_product_templates_form"

#: (family_slug, family_display, product_display, [(sku, option_label, variant_display)])
#: Every name measured from price list p2. ⚠️ The variant display_name is the price
#: list's item text with the P-number prefix dropped, because the P-number is the
#: sku and storing it twice is the only alternative — `decided`, not measured.
URNS: list[tuple[str, str, str, list[tuple[str, str, str]]]] = [
    ("country-bouquet", "Country Bouquet", "Country Bouquet",
     [("P445", "Country Bouquet", "Country Bouquet")]),
    ("jewel", "Jewel", "Jewel",
     [("P440", "Jewel", "Jewel")]),
    ("moon-stone", "Moon Stone", "Moon Stone",
     [("P440A", "Moon Stone", "Moon Stone")]),
    ("sedona", "Sedona", "Sedona",
     [("P440B", "Sedona", "Sedona")]),
    ("victorian", "Victorian", "Victorian",
     [("P363", "Victorian", "Victorian")]),
    ("arlington", "Arlington", "Arlington",
     [("P600", "Arlington", "Arlington")]),
    ("regal", "Regal", "Regal Line", [
        ("P300", "Cream & Gold", "Cream & Gold"),
        ("P300WS", "White & Silver", "White & Silver"),
        ("P300P", "Pebble Dust", "Pebble Dust"),
    ]),
    # ⚠️ `tribute-urn`, not `tribute` — that slug is the Tribute BURIAL VAULT's.
    # The price list calls this group "Tribute Line"; the slug is ours (`decided`).
    ("tribute-urn", "Tribute (Urn)", "Tribute Line", [
        ("P310", "Cream & Gold", "Cream & Gold"),
        ("P310WS", "White & Silver", "White & Silver"),
        ("P310P", "Pebble Dust", "Pebble Dust"),
    ]),
]

#: (family_slug, form, sku, option_label, display_name, sort_order)
#: ⚠️ SKU prefixes follow each PRODUCT's existing convention, not one global scheme:
#: `BV-CON` -> `BV-CON34`; `GL-STD`/`GL-SS` -> `GL-34`/`GL-38`. `decided`.
ODD_SIZES: list[tuple[str, str, str, str, str, int]] = [
    ("continental", "burial_vault", "BV-CON34", "34 inch", 'Continental 34"', 2),
    ("graveliner", "grave_liner", "GL-34", "34 inch", 'Graveliner 34"', 3),
    ("graveliner", "grave_liner", "GL-38", "38 inch", 'Graveliner 38"', 4),
]

#: (family_slug, form, reinforcement). All measured from the price list's group
#: headings — p1 for burial vaults and the grave liner, p2 for urn vaults.
REINFORCEMENT: list[tuple[str, str, str]] = [
    ("wilbert-bronze", "burial_vault", "Triple"),
    ("triune", "burial_vault", "Double"),
    ("tribute", "burial_vault", "Single"),
    ("venetian", "burial_vault", "Single"),
    ("continental", "burial_vault", "Single"),
    ("salute", "burial_vault", "Single"),
    ("monticello", "burial_vault", "Single"),
    ("monarch", "burial_vault", "Non"),
    ("graveliner", "grave_liner", "Non"),
    ("triune", "urn_vault", "Double"),
    ("venetian", "urn_vault", "Single"),
    ("monticello", "urn_vault", "Single"),
    ("salute", "urn_vault", "Non"),
    ("graveliner", "urn_vault", "Non"),
]

#: Must still read NULL afterwards. 2 because the source withholds a tier, 5
#: because the concept does not apply.
REINFORCEMENT_NULL: list[tuple[str, str]] = [
    ("universal", "urn_vault"),
    ("loved-and-cherished", "infant"),
    ("chairs", "equipment"),
    ("cremation-table", "equipment"),
    ("grass-mats", "equipment"),
    ("lowering-device", "equipment"),
    ("tent", "equipment"),
]


def _replace_form_check(forms: tuple[str, ...]) -> None:
    op.drop_constraint(FORM_CHECK, "product_templates", type_="check")
    op.create_check_constraint(
        FORM_CHECK,
        "product_templates",
        "form IN ('" + "', '".join(forms) + "')",
    )


def upgrade() -> None:
    bind = op.get_bind()

    # ---- 1. `urn` joins the form vocabulary --------------------------------
    _replace_form_check(FORMS_AFTER)

    # ---- 2. families, products, variants for the twelve stocked urns -------
    next_sort = bind.execute(
        sa.text("SELECT coalesce(max(sort_order), 0) FROM product_families")
    ).scalar_one()

    fam_t = sa.table(
        "product_families",
        sa.column("slug", sa.String), sa.column("display_name", sa.String),
        sa.column("status", sa.String), sa.column("sort_order", sa.Integer),
    )
    prod_t = sa.table(
        "product_templates",
        sa.column("id", sa.String), sa.column("family_slug", sa.String),
        sa.column("form", sa.String), sa.column("ownership", sa.String),
        sa.column("display_name", sa.String),
    )
    var_t = sa.table(
        "product_variant_templates",
        sa.column("id", sa.String),
        sa.column("product_template_id", sa.String),
        sa.column("sku", sa.String), sa.column("option_label", sa.String),
        sa.column("display_name", sa.String), sa.column("sort_order", sa.Integer),
    )

    fams, prods, vars_ = [], [], []
    for famslug, famname, prodname, variants in URNS:
        next_sort += 1
        fams.append({
            "slug": famslug, "display_name": famname,
            "status": "published", "sort_order": next_sort,
        })
        pid = _id("product", famslug, "urn")
        prods.append({
            "id": pid, "family_slug": famslug, "form": "urn",
            "ownership": "wilbert", "display_name": prodname,
        })
        for i, (sku, label, vname) in enumerate(variants, start=1):
            vars_.append({
                "id": _id("variant", sku), "product_template_id": pid,
                "sku": sku, "option_label": label,
                "display_name": vname, "sort_order": i,
            })

    op.bulk_insert(fam_t, fams)
    op.bulk_insert(prod_t, prods)
    op.bulk_insert(var_t, vars_)

    # ---- 3. odd sizes as variants of their existing parents ----------------
    odd_rows = []
    for famslug, form, sku, label, vname, order in ODD_SIZES:
        pid = bind.execute(
            sa.text(
                "SELECT id FROM product_templates "
                "WHERE family_slug = :f AND form = :m"
            ),
            {"f": famslug, "m": form},
        ).scalar_one()  # ⚠️ scalar_one RAISES on 0 or 2+ — r194 makes 2+ impossible
        odd_rows.append({
            "id": _id("variant", sku), "product_template_id": pid,
            "sku": sku, "option_label": label,
            "display_name": vname, "sort_order": order,
        })
    op.bulk_insert(var_t, odd_rows)

    # ---- 4/5. the two label corrections ------------------------------------
    bind.execute(sa.text(
        "UPDATE product_variant_templates "
        "SET display_name = 'Veteran Triune Urn Vault' WHERE sku = 'UV-VET'"
    ))
    bind.execute(sa.text(
        "UPDATE product_variant_templates "
        "SET option_label = 'Standard' WHERE sku = 'BV-CON'"
    ))

    # ---- 6. reinforcement ---------------------------------------------------
    for famslug, form, tier in REINFORCEMENT:
        r = bind.execute(
            sa.text(
                "UPDATE product_templates SET reinforcement = :t "
                "WHERE family_slug = :f AND form = :m"
            ),
            {"t": tier, "f": famslug, "m": form},
        )
        assert r.rowcount == 1, (
            f"reinforcement {famslug}/{form}: expected 1 row, updated {r.rowcount}"
        )

    # ---- postconditions, read back ------------------------------------------
    urn_products = {
        r[0] for r in bind.execute(
            sa.text("SELECT family_slug FROM product_templates WHERE form = 'urn'")
        )
    }
    assert urn_products == {f for f, _, _, _ in URNS}, (
        f"urn products wrong: {urn_products ^ {f for f, _, _, _ in URNS}}"
    )

    urn_skus = {
        r[0] for r in bind.execute(
            sa.text(
                "SELECT v.sku FROM product_variant_templates v "
                "JOIN product_templates t ON t.id = v.product_template_id "
                "WHERE t.form = 'urn'"
            )
        )
    }
    want_skus = {s for _, _, _, vs in URNS for s, _, _ in vs}
    assert urn_skus == want_skus, f"urn skus wrong: {urn_skus ^ want_skus}"

    odd_skus = {
        r[0] for r in bind.execute(
            sa.text(
                "SELECT sku FROM product_variant_templates "
                "WHERE sku IN ('BV-CON34', 'GL-34', 'GL-38')"
            )
        )
    }
    assert odd_skus == {"BV-CON34", "GL-34", "GL-38"}, f"odd sizes: {odd_skus}"

    tiers = {
        (r[0], r[1]): r[2]
        for r in bind.execute(
            sa.text(
                "SELECT family_slug, form, reinforcement FROM product_templates "
                "WHERE reinforcement IS NOT NULL"
            )
        )
    }
    want_tiers = {(f, m): t for f, m, t in REINFORCEMENT}
    assert tiers == want_tiers, (
        f"reinforcement set wrong: "
        f"{set(tiers.items()) ^ set(want_tiers.items())}"
    )

    nulls = {
        (r[0], r[1])
        for r in bind.execute(
            sa.text(
                "SELECT family_slug, form FROM product_templates "
                "WHERE reinforcement IS NULL AND form <> 'urn'"
            )
        )
    }
    assert nulls == set(REINFORCEMENT_NULL), (
        f"NULL reinforcement set wrong: {nulls ^ set(REINFORCEMENT_NULL)}"
    )

    vet = bind.execute(sa.text(
        "SELECT display_name, sku FROM product_variant_templates WHERE sku = 'UV-VET'"
    )).one()
    assert vet.display_name == "Veteran Triune Urn Vault", vet.display_name
    assert vet.sku == "UV-VET", "the SKU must not change — see the docstring"

    con = bind.execute(sa.text(
        "SELECT option_label FROM product_variant_templates WHERE sku = 'BV-CON'"
    )).scalar_one()
    assert con == "Standard", con

    # ⚠️ CE-CT must survive. Absence from a price list is not absence from the world.
    cect = bind.execute(sa.text(
        "SELECT count(*) FROM product_variant_templates WHERE sku = 'CE-CT'"
    )).scalar_one()
    assert cect == 1, "CE-CT was removed; it exists and is simply not on this list"


def downgrade() -> None:
    bind = op.get_bind()

    bind.execute(sa.text(
        "UPDATE product_variant_templates "
        "SET option_label = 'Continental' WHERE sku = 'BV-CON'"
    ))
    bind.execute(sa.text(
        "UPDATE product_variant_templates "
        "SET display_name = 'Veteran Urn Vault' WHERE sku = 'UV-VET'"
    ))
    for famslug, form, _ in REINFORCEMENT:
        bind.execute(
            sa.text(
                "UPDATE product_templates SET reinforcement = NULL "
                "WHERE family_slug = :f AND form = :m"
            ),
            {"f": famslug, "m": form},
        )

    odd = tuple(s for _, _, s, _, _, _ in ODD_SIZES)
    bind.execute(
        sa.text("DELETE FROM product_variant_templates WHERE sku IN :skus").bindparams(
            sa.bindparam("skus", value=odd, expanding=True)
        )
    )
    bind.execute(sa.text(
        "DELETE FROM product_variant_templates WHERE product_template_id IN "
        "(SELECT id FROM product_templates WHERE form = 'urn')"
    ))
    bind.execute(sa.text("DELETE FROM product_templates WHERE form = 'urn'"))
    fam_slugs = tuple(f for f, _, _, _ in URNS)
    bind.execute(
        sa.text("DELETE FROM product_families WHERE slug IN :slugs").bindparams(
            sa.bindparam("slugs", value=fam_slugs, expanding=True)
        )
    )

    # ⚠️ Fails if any `urn` row survived the deletes above. Correct behaviour.
    _replace_form_check(FORMS_BEFORE)
