"""Platform product catalog, phase 2a — the catalog's one definition

Revision ID: r188_platform_catalog_backfill
Revises: r187_product_template_images
Create Date: 2026-10-02

⚠️ RUNS AGAINST PRODUCTION ON DEPLOY (`railway-start.sh:45`). It INSERTS into
three tables that r186 created and nothing has written to, so it adds rows and
changes none.

⚠️ SELF-CONTAINED ON PURPOSE. IT READS `product_catalog_templates` FOR NOTHING.
That table holds 37 rows on production, 25 on dev, and 25 on any fresh
`alembic upgrade head` — because the 37 come from `seed_wilbert_templates`, which
runs at RUNTIME inside `seed_platform_admin()` behind `PLATFORM_ADMIN_EMAIL` and
`PLATFORM_ADMIN_PASSWORD`. A backfill reading that table would therefore produce a
different catalog per environment, which is the divergence that made a dev-based
reading of the platform convention wrong earlier today. Defining the catalog here,
in code, is what makes every environment converge.

This is not a transcription of that table. It is the platform catalog's one
definition, written where it will live.

SOURCE OF THE NAMES AND DESCRIPTIONS: the committed dump at
`docs/investigations/2026-10-02-production-catalog-dump.md` (landed in
`ed6b649b`), read mechanically rather than retyped. It is in git, so it reads
identically in every environment, and it carries all 37 rows' exact strings.
Verified by set equality before generation: the dump's SKUs minus the mapping's
are exactly {UV-SAL}.

⚠️ ALL 37 SKUs CARRY ACROSS, AND AN EARLIER DRAFT OF THIS MIGRATION DROPPED ONE
ON A WRONG READING. That draft excluded `UV-SAL`, holding that Wilbert sells one
Universal product in two finishes and that "Basic Gray / Salute" was the gray
variant's name. The dump refutes it in its own strings:

    UV-UWS  Universal Urn Vault (White & Silver)  "universal urn vault white and silver finish"
    UV-UCG  Universal Urn Vault (Cream & Gold)    "universal urn vault cream and gold finish"
    UV-SAL  Salute Urn Vault                      "salute urn vault"

Both Universal rows say Universal and name their own finish; the SKU suffixes
decode the same way — UWS is White & Silver, UCG is Cream & Gold. So the Universal
product has a Finish axis with two values, exactly like Venetian, and
`Salute Urn Vault` is its own product in the existing `salute` family, giving that
family both a burial and an urn form the way `triune` has.

The wrong reading came from resolving `UV-UCG` by ELIMINATION against a spec sheet
while the row's own display name stated what it was. Elimination where a label
exists is the weakest instrument available. 21 products and 37 variants.

ALIAS DIRECTION ALSO INVERTED BY THIS. It is not "Salute Urn Vault -> UV-UCG". If
anything it is "Basic Gray" -> `UV-SAL`, since Wilbert bundles the listing as
"Basic Gray/Salute" and the dump carries only the Salute half. Either way there is
no home for it yet: `product_aliases.company_id` is NOT NULL, so it cannot hold a
platform-level alias. Recorded rather than invented.

⚠️ `sort_order` IS ASSIGNED FRESH, NOT CARRIED. Production has `BV-MON` and
`BV-WBR` both at 10, so their order is whatever Postgres picks — the
duplicate-ordering pathology CLAUDE.md records for `workflow_steps`. Because this
backfill reads nothing, that collision stops existing here rather than being
reproduced. Sequential within each parent, no ties.

⚠️ NO SPEC DATA. Dimensions, weights and personalization capability stay NULL.
They arrive in 2b from the licensee spec sheet, and two figures plus every urn
vault weight are still unresolved at the source. Seeding a guess is worse than an
empty column.

NAMING DISCREPANCY RECORDED, NOT NORMALISED. The burial form is "Grave Liner" on
the licensee spec sheet and "Graveliner" in production, while the urn form is
"Graveliner Urn Vault" in both. Slug `graveliner`, family display name
"Graveliner", and each variant keeps the dump's exact string. This is alias
territory, and the alias list already stands at five before the resolver is
scoped.

IDs are deterministic (`uuid5` over a fixed namespace and the natural key) so
re-running on a database that already has these rows is a no-op rather than a
duplicate, and so the same row carries the same id in every environment.
"""
import uuid

from alembic import op
import sqlalchemy as sa

revision = "r188_platform_catalog_backfill"
down_revision = "r187_product_template_images"
branch_labels = None
depends_on = None

#: Fixed namespace so ids are reproducible across environments and re-runs.
_NS = uuid.UUID("6f1b4a52-0000-5000-8000-000000000000")


def _id(*parts: str) -> str:
    return str(uuid.uuid5(_NS, "|".join(parts)))


FAMILIES: list[tuple[str, str]] = [
    ('wilbert-bronze', 'Wilbert Bronze'),
    ('triune', 'Triune'),
    ('tribute', 'Tribute'),
    ('venetian', 'Venetian'),
    ('continental', 'Continental'),
    ('monticello', 'Monticello'),
    ('salute', 'Salute'),
    ('monarch', 'Monarch'),
    ('graveliner', 'Graveliner'),
    ('loved-and-cherished', 'Loved & Cherished'),
    ('universal', 'Universal'),
    ('lowering-device', 'Lowering Device'),
    ('cremation-table', 'Cremation Table'),
    ('tent', 'Tent'),
    ('grass-mats', 'Grass Mats'),
    ('chairs', 'Chairs'),
]

#: (family_slug, form, ownership, product_display_name, sort_order,
#:  [(sku, option_label, variant_display_name, variant_description, sort_order)])
#:
#: Four family slugs appear twice — triune, venetian, monticello, graveliner —
#: once per form. That is why there are 16 families and 20 products, and it is the
#: reason a family is a lookup table rather than a level of the hierarchy.
PRODUCTS: list[tuple] = [
    (
        'wilbert-bronze', 'burial_vault', 'wilbert',
        'Wilbert Bronze', 1,
        [
            ('BV-WBR', 'Wilbert Bronze',
             'Wilbert Bronze Burial Vault',
             'Premium bronze-finished Wilbert vault', 1),
        ],
    ),
    (
        'triune', 'burial_vault', 'wilbert',
        'Triune Burial Vault', 2,
        [
            ('BV-BTRI', 'Bronze',
             'Bronze Triune Burial Vault',
             'Bronze Triune three-piece protective vault', 1),
            ('BV-CTRI', 'Copper',
             'Copper Triune Burial Vault',
             'Copper Triune three-piece protective vault', 2),
            ('BV-SSTRI', 'Stainless Steel',
             'Stainless Steel Triune Burial Vault',
             'Stainless steel Triune three-piece protective', 3),
            ('BV-CRTRI', 'Cameo Rose',
             'Cameo Rose Triune Burial Vault',
             'Cameo Rose Triune three-piece protective vault', 4),
            ('BV-VTRI', 'Veteran',
             'Veteran Triune Burial Vault',
             'Military tribute Triune vault', 5),
        ],
    ),
    (
        'tribute', 'burial_vault', 'wilbert',
        'Tribute Burial Vault', 3,
        [
            ('BV-WTRIB', 'White',
             'White Tribute Burial Vault',
             'White Tribute entry-level vault', 1),
            ('BV-GTRIB', 'Gray',
             'Gray Tribute Burial Vault',
             'Gray Tribute entry-level vault', 2),
        ],
    ),
    (
        'venetian', 'burial_vault', 'wilbert',
        'Venetian Burial Vault', 4,
        [
            ('BV-WVEN', 'White',
             'White Venetian Burial Vault',
             'White finish Venetian air-sealed vault', 1),
            ('BV-GVEN', 'Gold',
             'Gold Venetian Burial Vault',
             'Gold finish Venetian air-sealed vault', 2),
        ],
    ),
    (
        'continental', 'burial_vault', 'wilbert',
        'Continental Burial Vault', 5,
        [
            ('BV-CON', 'Continental',
             'Continental Burial Vault',
             'Continental reinforced concrete vault', 1),
        ],
    ),
    (
        'monticello', 'burial_vault', 'wilbert',
        'Monticello Burial Vault', 6,
        [
            ('BV-MON', 'Monticello',
             'Monticello Burial Vault',
             'Monticello reinforced concrete burial vault', 1),
        ],
    ),
    (
        'salute', 'burial_vault', 'wilbert',
        'Salute Burial Vault', 7,
        [
            ('BV-SAL', 'Salute',
             'Salute Burial Vault',
             'Salute reinforced concrete vault', 1),
        ],
    ),
    (
        'monarch', 'burial_vault', 'licensee_common',
        'Monarch Burial Vault', 8,
        [
            ('BV-MRC', 'Monarch',
             'Monarch Burial Vault',
             'Monarch reinforced concrete vault', 1),
        ],
    ),
    (
        'graveliner', 'grave_liner', 'licensee_common',
        'Grave Liner', 9,
        [
            ('GL-STD', 'Standard',
             'Graveliner',
             'Standard concrete grave liner', 1),
            ('GL-SS', 'Social Service',
             'Graveliner (Social Service)',
             'Social service concrete grave liner', 2),
        ],
    ),
    (
        'loved-and-cherished', 'infant', 'wilbert',
        'Loved & Cherished', 10,
        [
            ('LC-19', '19 inch',
             'Loved & Cherished 19"',
             'Infant/child vault 19 inch', 1),
            ('LC-24', '24 inch',
             'Loved & Cherished 24"',
             'Infant/child vault 24 inch', 2),
            ('LC-31', '31 inch',
             'Loved & Cherished 31"',
             'Infant/child vault 31 inch', 3),
        ],
    ),
    (
        'triune', 'urn_vault', 'wilbert',
        'Triune Urn Vault', 11,
        [
            ('UV-BTRI', 'Bronze',
             'Bronze Triune Urn Vault',
             'Bronze Triune urn vault', 1),
            ('UV-CTRI', 'Copper',
             'Copper Triune Urn Vault',
             'Copper Triune urn vault', 2),
            ('UV-SSTRI', 'Stainless Steel',
             'Stainless Steel Triune Urn Vault',
             'Stainless Steel Triune urn vault', 3),
            ('UV-CRTRI', 'Cameo Rose',
             'Cameo Rose Triune Urn Vault',
             'Cameo Rose Triune urn vault', 4),
            ('UV-VET', 'Veteran',
             'Veteran Urn Vault',
             'Veteran military tribute urn vault', 5),
        ],
    ),
    (
        'venetian', 'urn_vault', 'wilbert',
        'Venetian Urn Vault', 12,
        [
            ('UV-WVEN', 'White',
             'White Venetian Urn Vault',
             'White Venetian urn vault', 1),
            ('UV-GVEN', 'Gold',
             'Gold Venetian Urn Vault',
             'Gold Venetian urn vault', 2),
        ],
    ),
    (
        'monticello', 'urn_vault', 'wilbert',
        'Monticello Urn Vault', 13,
        [
            ('UV-MON', 'Monticello',
             'Monticello Urn Vault',
             'Monticello urn vault', 1),
        ],
    ),
    (
        'universal', 'urn_vault', 'wilbert',
        'Universal Urn Vault', 14,
        [
            ('UV-UWS', 'White & Silver',
             'Universal Urn Vault (White & Silver)',
             'Universal urn vault white and silver finish', 1),
            ('UV-UCG', 'Cream & Gold',
             'Universal Urn Vault (Cream & Gold)',
             'Universal urn vault cream and gold finish', 2),
        ],
    ),
    (
        'salute', 'urn_vault', 'wilbert',
        'Salute Urn Vault', 15,
        [
            ('UV-SAL', 'Salute',
             'Salute Urn Vault',
             'Salute urn vault', 1),
        ],
    ),
    (
        'graveliner', 'urn_vault', 'licensee_common',
        'Graveliner Urn Vault', 16,
        [
            ('UV-GL', 'Graveliner',
             'Graveliner Urn Vault',
             'Graveliner urn vault', 1),
        ],
    ),
    (
        'lowering-device', 'equipment', 'licensee_common',
        'Lowering Device', 17,
        [
            ('CE-LD', 'Lowering Device',
             'Lowering Device',
             'Lowering device rental per service', 1),
        ],
    ),
    (
        'cremation-table', 'equipment', 'licensee_common',
        'Cremation Table', 18,
        [
            ('CE-CT', 'Cremation Table',
             'Cremation Table',
             'Cremation table rental per service', 1),
        ],
    ),
    (
        'tent', 'equipment', 'licensee_common',
        'Tent', 19,
        [
            ('CE-TS', 'Single',
             'Cemetery Tent - Single',
             'Single tent (seats ~50) rental per service', 1),
            ('CE-TD', 'Double',
             'Cemetery Tent - Double',
             'Double tent (seats ~100) rental per service', 2),
        ],
    ),
    (
        'grass-mats', 'equipment', 'licensee_common',
        'Grass Mats', 20,
        [
            ('CE-GM', 'Grass Mats',
             'Grass Mats',
             'Artificial turf/grass mats rental per service', 1),
        ],
    ),
    (
        'chairs', 'equipment', 'licensee_common',
        'Chairs', 21,
        [
            ('CE-CH', 'Chairs',
             'Graveside Chairs',
             'Graveside chairs rental per set', 1),
        ],
    ),
]


def upgrade() -> None:
    conn = op.get_bind()

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
        sa.column("personalization_capability", sa.JSON),
    )
    var_t = sa.table(
        "product_variant_templates",
        sa.column("id", sa.String), sa.column("product_template_id", sa.String),
        sa.column("sku", sa.String), sa.column("option_label", sa.String),
        sa.column("display_name", sa.String), sa.column("description", sa.Text),
        sa.column("sort_order", sa.Integer), sa.column("is_active", sa.Boolean),
    )

    existing = {r[0] for r in conn.execute(sa.text("SELECT slug FROM product_families"))}
    fams = [
        {"slug": s, "display_name": n, "status": "published", "sort_order": i}
        for i, (s, n) in enumerate(FAMILIES, start=1)
        if s not in existing
    ]
    if fams:
        op.bulk_insert(fam_t, fams)

    have_sku = {r[0] for r in conn.execute(sa.text("SELECT sku FROM product_variant_templates"))}
    have_prod = {r[0] for r in conn.execute(sa.text("SELECT id FROM product_templates"))}
    prods, vars_ = [], []
    for famslug, form, own, pname, order, variants in PRODUCTS:
        pid = _id("product", famslug, form)
        if pid not in have_prod:
            prods.append({
                "id": pid, "family_slug": famslug, "form": form, "ownership": own,
                "display_name": pname, "personalization_capability": [],
            })
        for sku, label, vname, vdesc, vorder in variants:
            if sku in have_sku:
                continue
            vars_.append({
                "id": _id("variant", sku), "product_template_id": pid, "sku": sku,
                "option_label": label, "display_name": vname, "description": vdesc,
                "sort_order": vorder, "is_active": True,
            })
    if prods:
        op.bulk_insert(prod_t, prods)
    if vars_:
        op.bulk_insert(var_t, vars_)


def downgrade() -> None:
    # Only the rows this migration defines, by their deterministic ids and SKUs.
    # A blanket DELETE would take rows a later pass added.
    conn = op.get_bind()
    skus = [s for _, _, _, _, _, vs in PRODUCTS for s, _, _, _, _ in vs]
    pids = [_id("product", f, form) for f, form, _, _, _, _ in PRODUCTS]
    conn.execute(
        sa.text("DELETE FROM product_variant_templates WHERE sku = ANY(:s)"), {"s": skus}
    )
    conn.execute(
        sa.text("DELETE FROM product_templates WHERE id = ANY(:p)"), {"p": pids}
    )
    conn.execute(
        sa.text("DELETE FROM product_families WHERE slug = ANY(:f)"),
        {"f": [s for s, _ in FAMILIES]},
    )
