"""The price list landed on the catalog, and five distinctions hold.

⚠️ READ-ONLY. Creates no rows. Reads the platform tier, which has no `company_id`.

⚠️ SUBJECT: the database `DATABASE_URL` points at. Asserts r195 is applied there.
A migration verified on a scratch database and a suite run against another is how
105 failures were produced on 2026-10-02.

WHAT IT PINS:

1. **`urn` is not `urn_vault`.** An urn is not a vault. Twelve stocked urns live
   on their own form; folding them in would be a membership claim nobody made.

2. **Odd sizes are VARIANTS, not products.** `Continental 34"` is a variant of
   `Continental`, which is an INFERENCE — the price list groups it under
   `ODD SIZED`, away from its parent. The falsifier is a source showing the odd
   size is built differently. If that source arrives, these tests are what has to
   change, deliberately.

3. **`option_label` is ONE axis**, values heterogeneous in what they vary.
   Graveliner carries `Standard`, `Social Service`, `34 inch`, `38 inch` flat. It
   looks like grade × size only if the cross-product exists, and it does not —
   there is no Graveliner SS at 34" anywhere. Two axes would give six slots for
   four real things. **Set equality is the guard: a crossed configuration appearing
   fails this suite, which is exactly when the ruling should be revisited.**

4. **`UV-VET`'s SKU never changes.** The display name was corrected; the SKU is
   pinned so a later consistency-minded rename fails loudly rather than rippling
   into `r188`, two docstrings, two investigation docs and a seeder.

5. **`reinforcement` lives on the PRODUCT, and its NULLs are deliberate.** Seven
   products hold NULL: two because the price list withholds a tier, five because
   the concept does not apply to a tent.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.database import SessionLocal

URN_FAMILIES = {
    "country-bouquet", "jewel", "moon-stone", "sedona",
    "victorian", "arlington", "regal", "tribute-urn",
}
URN_SKUS = {
    "P445", "P440", "P440A", "P440B", "P363", "P600",
    "P300", "P300WS", "P300P", "P310", "P310WS", "P310P",
}
#: ⚠️ FLAT AND HETEROGENEOUS ON PURPOSE — grade values beside size values on one
#: axis, because the cross-product does not exist.
GRAVELINER_LABELS = {"Standard", "Social Service", "34 inch", "38 inch"}
CONTINENTAL_LABELS = {"Standard", "34 inch"}

REINFORCEMENT = {
    ("wilbert-bronze", "burial_vault"): "Triple",
    ("triune", "burial_vault"): "Double",
    ("tribute", "burial_vault"): "Single",
    ("venetian", "burial_vault"): "Single",
    ("continental", "burial_vault"): "Single",
    ("salute", "burial_vault"): "Single",
    ("monticello", "burial_vault"): "Single",
    ("monarch", "burial_vault"): "Non",
    ("graveliner", "grave_liner"): "Non",
    ("triune", "urn_vault"): "Double",
    ("venetian", "urn_vault"): "Single",
    ("monticello", "urn_vault"): "Single",
    ("salute", "urn_vault"): "Non",
    ("graveliner", "urn_vault"): "Non",
}
REINFORCEMENT_NULL = {
    ("universal", "urn_vault"),
    ("loved-and-cherished", "infant"),
    ("chairs", "equipment"),
    ("cremation-table", "equipment"),
    ("grass-mats", "equipment"),
    ("lowering-device", "equipment"),
    ("tent", "equipment"),
}


@pytest.fixture(scope="module")
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture(scope="module", autouse=True)
def _require_r195(db):
    """⚠️ PRECONDITION, LOUD. Without r195 several assertions below pass vacuously
    — an empty `urn` form satisfies every disjointness claim trivially."""
    n = db.execute(
        text("SELECT count(*) FROM product_templates WHERE form = 'urn'")
    ).scalar_one()
    assert n > 0, (
        "no products on the `urn` form — r195 is not applied to this database, "
        "and the tests below would pass over an empty set"
    )


class TestUrnIsNotUrnVault:
    def test_the_urn_products_are_exactly_the_eight(self, db):
        got = {
            r[0] for r in db.execute(
                text("SELECT family_slug FROM product_templates WHERE form='urn'")
            )
        }
        assert got == URN_FAMILIES

    def test_the_twelve_skus_are_exactly_the_price_lists(self, db):
        got = {
            r[0] for r in db.execute(
                text(
                    "SELECT v.sku FROM product_variant_templates v "
                    "JOIN product_templates t ON t.id = v.product_template_id "
                    "WHERE t.form = 'urn'"
                )
            )
        }
        assert got == URN_SKUS

    def test_no_p_numbered_sku_landed_on_a_vault_form(self, db):
        """⚠️ THE DISTINCTION, ASSERTED IN THE DIRECTION THAT COULD GO WRONG. The
        test above would still pass if the urns were ALSO duplicated onto
        `urn_vault`."""
        leaked = [
            r[0] for r in db.execute(
                text(
                    "SELECT v.sku FROM product_variant_templates v "
                    "JOIN product_templates t ON t.id = v.product_template_id "
                    "WHERE t.form <> 'urn' AND v.sku LIKE 'P%'"
                )
            )
        ]
        assert leaked == [], f"P-numbered skus on a non-urn form: {leaked}"

    def test_the_tribute_family_slugs_do_not_collide(self, db):
        """`tribute` is the burial vault; `tribute-urn` is the urn line. One
        family slug for both would merge a $2,570 vault with a $135 urn."""
        rows = {
            (r[0], r[1]) for r in db.execute(
                text(
                    "SELECT family_slug, form FROM product_templates "
                    "WHERE family_slug IN ('tribute', 'tribute-urn')"
                )
            )
        }
        assert rows == {("tribute", "burial_vault"), ("tribute-urn", "urn")}


class TestOddSizesAreVariantsNotProducts:
    def test_no_odd_size_became_a_product(self, db):
        names = {
            r[0] for r in db.execute(
                text("SELECT display_name FROM product_templates")
            )
        }
        for n in ('Continental 34"', 'Graveliner 34"', 'Graveliner 38"'):
            assert n not in names, f"{n} became a product; it is a size variant"

    def test_each_odd_size_hangs_off_its_parent(self, db):
        want = {
            "BV-CON34": ("continental", "burial_vault"),
            "GL-34": ("graveliner", "grave_liner"),
            "GL-38": ("graveliner", "grave_liner"),
        }
        got = {
            r[0]: (r[1], r[2]) for r in db.execute(
                text(
                    "SELECT v.sku, t.family_slug, t.form "
                    "FROM product_variant_templates v "
                    "JOIN product_templates t ON t.id = v.product_template_id "
                    "WHERE v.sku IN ('BV-CON34', 'GL-34', 'GL-38')"
                )
            )
        }
        assert got == want

    def test_the_inference_is_recorded_as_reinforcement_on_the_parent(self, db):
        """⚠️ The claim is "Continental 34\" IS A CONTINENTAL", not "Continental
        34\" is Single Reinforced" — the page does not say the second. The variant
        carries no tier of its own; it reads its parent's."""
        rows = list(db.execute(
            text(
                "SELECT v.sku, t.reinforcement FROM product_variant_templates v "
                "JOIN product_templates t ON t.id = v.product_template_id "
                "WHERE v.sku IN ('BV-CON34', 'GL-34', 'GL-38') ORDER BY v.sku"
            )
        ))
        assert [(r[0], r[1]) for r in rows] == [
            ("BV-CON34", "Single"), ("GL-34", "Non"), ("GL-38", "Non"),
        ]

    def test_the_variant_table_has_no_reinforcement_column(self, db):
        """Structural: the attribute cannot be set per variant even by accident."""
        cols = {
            r[0] for r in db.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'product_variant_templates'"
                )
            )
        }
        assert "reinforcement" not in cols


class TestOptionLabelIsOneAxis:
    def test_graveliner_carries_a_flat_heterogeneous_axis(self, db):
        """⚠️ SET EQUALITY IS THE FALSIFIER GUARD. Grade values beside size values
        on one axis, because no crossed configuration exists. If `Graveliner SS
        34"` ever appears, this fails — and that is the day the ruling to keep one
        axis should be revisited, not worked around."""
        got = {
            r[0] for r in db.execute(
                text(
                    "SELECT v.option_label FROM product_variant_templates v "
                    "JOIN product_templates t ON t.id = v.product_template_id "
                    "WHERE t.family_slug='graveliner' AND t.form='grave_liner'"
                )
            )
        }
        assert got == GRAVELINER_LABELS

    def test_continental_base_label_is_standard_not_the_product_name(self, db):
        """`Continental` restated the product rather than naming an axis value —
        invisible at one variant, wrong once `34 inch` joined it."""
        got = {
            r[0] for r in db.execute(
                text(
                    "SELECT v.option_label FROM product_variant_templates v "
                    "JOIN product_templates t ON t.id = v.product_template_id "
                    "WHERE t.family_slug='continental' AND t.form='burial_vault'"
                )
            )
        }
        assert got == CONTINENTAL_LABELS
        assert "Continental" not in got


class TestTheVeteranRename:
    def test_the_display_name_matches_the_price_list(self, db):
        got = db.execute(text(
            "SELECT display_name FROM product_variant_templates WHERE sku='UV-VET'"
        )).scalar_one()
        assert got == "Veteran Triune Urn Vault"

    def test_the_sku_is_pinned_and_must_not_be_tidied(self, db):
        """⚠️ DELIBERATE INCONSISTENCY. `UV-VET` sits beside `UV-BTRI`, `UV-CTRI`,
        `UV-SSTRI`, `UV-CRTRI` and looks wrong. It is known and it stays — a SKU is
        an identifier, referenced in r188, two migration docstrings, two
        investigation documents and catalog_template_seeder.py. This test exists so
        a consistency-minded rename fails here rather than rippling."""
        n = db.execute(text(
            "SELECT count(*) FROM product_variant_templates WHERE sku='UV-VET'"
        )).scalar_one()
        assert n == 1, "UV-VET was renamed; the SKU is deliberately permanent"

    def test_its_option_label_still_matches_its_siblings(self, db):
        got = db.execute(text(
            "SELECT option_label FROM product_variant_templates WHERE sku='UV-VET'"
        )).scalar_one()
        assert got == "Veteran"


class TestReinforcementLivesOnTheProduct:
    def test_the_tiers_are_exactly_the_price_lists(self, db):
        got = {
            (r[0], r[1]): r[2] for r in db.execute(
                text(
                    "SELECT family_slug, form, reinforcement FROM product_templates "
                    "WHERE reinforcement IS NOT NULL"
                )
            )
        }
        assert got == REINFORCEMENT

    def test_the_nulls_are_exactly_the_seven(self, db):
        got = {
            (r[0], r[1]) for r in db.execute(
                text(
                    "SELECT family_slug, form FROM product_templates "
                    "WHERE reinforcement IS NULL AND form <> 'urn'"
                )
            )
        }
        assert got == REINFORCEMENT_NULL

    def test_both_populations_are_non_empty(self, db):
        """⚠️ POSITIVE CONTROL. The two set equalities above would both hold over a
        table that lost every row."""
        assert REINFORCEMENT and REINFORCEMENT_NULL
        n = db.execute(text("SELECT count(*) FROM product_templates")).scalar_one()
        assert n == len(REINFORCEMENT) + len(REINFORCEMENT_NULL) + 8, (
            "14 tiered + 7 null + 8 urn should account for every product"
        )


class TestAbsenceFromAPriceListIsNotAbsenceFromTheWorld:
    def test_cremation_table_survived(self, db):
        """⚠️ `CE-CT` is on NEITHER the price list nor the tenant seeder, and James
        confirmed it exists. It must not be deleted as a membership gap."""
        n = db.execute(text(
            "SELECT count(*) FROM product_variant_templates WHERE sku='CE-CT'"
        )).scalar_one()
        assert n == 1

    def test_no_price_column_exists_to_have_defaulted(self, db):
        """The reason Vault Placer's $0.00 and CE-CT's NULL price could not be
        confused here: this tier holds no price at all. Both rulings live in the
        map, and the migration had nothing to write."""
        cols = {
            r[0] for r in db.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'product_templates'"
                )
            )
        }
        assert "price" not in cols
