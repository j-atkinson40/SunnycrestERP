"""The price-list analyser reads the platform catalog, and classifies by `form`.

⚠️ READ-ONLY. No rows created.

WHAT IT PINS:

1. **Variants, not products.** The old flat table's 37 rows were each one SELLABLE
   thing. They map 1:1 onto variants and collapse onto only 21 products, so reading
   products would offer "Triune Burial Vault" where a price list says "Bronze
   Triune" — a silent 43% shrink of the candidate set.

2. **Classification comes from the `form` COLUMN.** The old code string-matched
   `"urn vault" in name.lower()`, which worked only because every row in the old
   table happened to be named `<x> Burial Vault` or `<x> Urn Vault` — a convention
   nobody declared and nothing enforced.

3. ⚠️ **The rows that convention never covered.** `Wilbert Bronze`, `Graveliner`,
   `Loved & Cherished 19"` and all twelve stocked urns match NEITHER old branch.
   This suite asserts they classify correctly now — that is the regression the
   repoint had to fix, not a nicety.

4. **The urn↔burial pairing is exact.** A burial variant and its urn twin share a
   family and an option label (`triune`/`Bronze` is `BV-BTRI` and `UV-BTRI`), so
   the pairing is a key lookup rather than stripping `" urn vault"` off a name.
"""
from __future__ import annotations

import pytest

from app.database import SessionLocal
from app.services.price_list_analysis_service import (
    _catalog_rows,
    _fix_urn_vault_items,
)

#: Names the OLD classifier could not place in either branch. Every one is a real
#: row in the current catalog.
OLD_CLASSIFIER_BLIND_SPOTS = [
    "Wilbert Bronze Burial Vault",  # has "Burial Vault" — the one that DID work
    "Graveliner",
    "Graveliner (Social Service)",
    'Loved & Cherished 19"',
    "Country Bouquet",
    "Cream & Gold",
]


@pytest.fixture(scope="module")
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture(scope="module")
def rows(db):
    return _catalog_rows(db)


def _old_string_classifier(name: str) -> str:
    """The classifier as it was, reproduced verbatim for comparison.

    ⚠️ Kept so the test can SHOW the blind spot rather than assert one existed.
    """
    n = name.lower()
    if "urn vault" in n:
        return "urn_vault"
    if "burial vault" in n:
        return "burial_vault"
    return "UNCLASSIFIED"


class TestItReadsVariantsNotProducts:
    def test_the_row_count_is_the_variant_count(self, db, rows):
        from sqlalchemy import text

        variants = db.execute(
            text("SELECT count(*) FROM product_variant_templates")
        ).scalar_one()
        products = db.execute(
            text("SELECT count(*) FROM product_templates")
        ).scalar_one()
        assert len(rows) == variants
        assert len(rows) != products, (
            "reading products would shrink the candidate set — the old flat rows "
            "were sellable things, which are variants"
        )

    def test_every_row_carries_the_fields_downstream_consumers_use(self, rows):
        """`_promote_exact_matches` and the final `template_map` read `.id` and
        `.product_name`; the repoint keeps those names so it touches the source
        and the classifier, not every consumer."""
        assert rows
        for r in rows[:5]:
            assert r.id and r.product_name and r.sku_prefix and r.form


class TestClassificationComesFromTheColumn:
    def test_every_row_has_a_form(self, rows):
        assert all(r.form for r in rows)

    def test_all_six_forms_are_present(self, rows):
        assert {r.form for r in rows} == {
            "burial_vault", "urn_vault", "grave_liner",
            "infant", "equipment", "urn",
        }

    def test_the_old_classifier_was_blind_and_the_new_one_is_not(self, rows):
        """⚠️ THE REGRESSION THIS REPOINT HAD TO FIX, shown rather than asserted.

        Each name below is a real catalog row the old string match placed in
        NEITHER branch. The new classification is a column read, so it places all
        of them."""
        by_name = {r.product_name: r for r in rows}
        blind = []
        for name in OLD_CLASSIFIER_BLIND_SPOTS:
            row = by_name.get(name)
            assert row is not None, f"{name!r} is not in the catalog — test is stale"
            if _old_string_classifier(name) == "UNCLASSIFIED":
                blind.append(name)
            # the new path always has an answer
            assert row.form in {
                "burial_vault", "urn_vault", "grave_liner",
                "infant", "equipment", "urn",
            }
        assert len(blind) >= 4, (
            f"expected the old classifier to be blind to several of these; it was "
            f"blind to {blind}. If the catalog was renamed so the string match "
            f"works again, that is worth knowing deliberately."
        )

    def test_the_twelve_urns_are_urns_not_urn_vaults(self, rows):
        """An urn is not a vault. The old classifier had no third answer."""
        urns = [r for r in rows if r.form == "urn"]
        assert len(urns) == 12
        for r in urns:
            assert _old_string_classifier(r.product_name) == "UNCLASSIFIED"


class TestTheUrnBurialPairingIsExact:
    def test_a_burial_variant_and_its_urn_twin_share_family_and_option(self, rows):
        burial = {(r.family_slug, r.option_label): r for r in rows if r.form == "burial_vault"}
        urn = {(r.family_slug, r.option_label): r for r in rows if r.form == "urn_vault"}
        shared = set(burial) & set(urn)
        assert shared, "no family/option pair appears in both forms — pairing is dead"
        # The canonical case: triune/Bronze is BV-BTRI and UV-BTRI
        assert ("triune", "Bronze") in shared
        assert burial[("triune", "Bronze")].sku_prefix == "BV-BTRI"
        assert urn[("triune", "Bronze")].sku_prefix == "UV-BTRI"

    def test_the_classifier_corrects_a_burial_match_to_its_urn_twin(self, rows):
        """End-to-end on the function itself: Claude matched an urn-vault line to
        the BURIAL variant; the pairing moves it to the urn one."""
        bv = next(r for r in rows if r.sku_prefix == "BV-BTRI")
        uv = next(r for r in rows if r.sku_prefix == "UV-BTRI")
        items = [{
            "extracted_name": "Bronze Triune Urn Vault",
            "raw_text": "Bronze Triune Urn Vault  $855",
            "match": {"template_id": bv.id, "template_name": bv.product_name},
        }]
        out = _fix_urn_vault_items(items, rows)
        assert out[0]["match"]["template_id"] == uv.id, (
            "the burial match was not corrected to its urn twin"
        )

    def test_the_pairing_works_where_the_NAME_FALLBACK_CANNOT(self, rows):
        """⚠️ THE DISCRIMINATING TEST, and the suite had none until a break test
        said so.

        `test_the_classifier_corrects_a_burial_match_to_its_urn_twin` passes
        through the NAME FALLBACK — "Bronze Triune Urn Vault" minus " urn vault"
        is "bronze triune", which the fallback resolves on its own. So emptying
        `urn_by_key` left it green, and the suite could not tell the exact path
        from the old string surgery.

        This builds a pair whose NAMES DO NOT CORRESPOND AT ALL. Only the shared
        family + option label connects them, so a pass here is a pass through the
        exact path and nothing else.
        """
        from app.services.price_list_analysis_service import _CatalogRow

        bv = _CatalogRow(
            id="bv-x", product_name="Shale Casket Enclosure", category="Burial Vaults",
            sku_prefix="BV-X", form="burial_vault",
            family_slug="unrelated-family", option_label="Oxblood",
        )
        uv = _CatalogRow(
            id="uv-x", product_name="Companion Ash Container", category="Urn Vaults",
            sku_prefix="UV-X", form="urn_vault",
            family_slug="unrelated-family", option_label="Oxblood",
        )
        # Neither name contains the other's stem; stripping " urn vault" from
        # "companion ash container" yields nothing the burial name resembles.
        # ⚠️ The extracted name shares NO stem with the urn row's name, so the
        # fallback's `base` ("oxblood shale") cannot match its key
        # ("companion ash container"). An earlier version of this test put the
        # urn row's own name in `extracted_name` and so resolved through the
        # fallback after all — it passed with `urn_by_key` emptied, which is how
        # a non-discriminating test looks from the outside.
        items = [{
            "extracted_name": "Oxblood Shale UV",
            "raw_text": "Oxblood Shale UV  $500",
            "match": {"template_id": bv.id, "template_name": bv.product_name},
        }]
        out = _fix_urn_vault_items(items, [bv, uv])
        assert out[0]["match"]["template_id"] == uv.id, (
            "the urn twin was not found by family+option — the exact pairing path "
            "is not doing the work, only the name fallback is"
        )

    def test_a_correct_urn_match_is_left_alone(self, rows):
        """⚠️ THE CONTROL. A 'corrector' that rewrote every item would pass the
        test above."""
        uv = next(r for r in rows if r.sku_prefix == "UV-BTRI")
        items = [{
            "extracted_name": "Bronze Triune Urn Vault",
            "raw_text": "Bronze Triune Urn Vault  $855",
            "match": {"template_id": uv.id, "template_name": uv.product_name},
        }]
        out = _fix_urn_vault_items(items, rows)
        assert out[0]["match"]["template_id"] == uv.id

    def test_a_burial_line_is_not_dragged_into_urn_vaults(self, rows):
        """⚠️ THE OTHER CONTROL. Nothing about a plain burial-vault line should
        trigger the urn correction."""
        bv = next(r for r in rows if r.sku_prefix == "BV-CON")
        items = [{
            "extracted_name": "Continental",
            "raw_text": "Continental  $1,607",
            "match": {"template_id": bv.id, "template_name": bv.product_name},
        }]
        out = _fix_urn_vault_items(items, rows)
        assert out[0]["match"]["template_id"] == bv.id
        assert "urn" not in out[0]["extracted_name"].lower()
