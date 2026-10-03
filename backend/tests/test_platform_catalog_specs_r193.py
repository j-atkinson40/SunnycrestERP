"""The licensee spec sheet landed on the catalog, and three distinctions hold.

⚠️ READ-ONLY. Creates no rows, so there is nothing to purge and no company
litter. It reads the platform tier, which has no `company_id` at all.

⚠️ THIS SUITE'S SUBJECT IS THE DATABASE `DATABASE_URL` POINTS AT, not a fixture.
It asserts that r192 + r193 have been applied there. A scratch database that was
round-tripped is not the subject; the environment the suite runs against is.
Named because a migration verified on one database and a suite run against
another is how 105 failures were produced on 2026-10-02.

WHAT IT PINS, and each is a distinction that reads as data loss if it is lost:

1. SET EQUALITY ON PROVENANCE. The products carrying `spec_source` are exactly
   the 15 the sheet covers — compared as a SET of (family_slug, form), never as
   a count. 15 == 15 passes while membership is wrong.

2. ABSENCE STAYS ABSENT. The 6 products with no row in the sheet carry NULL in
   every spec column AND NULL personalization capability. Nothing is copied from
   a sibling.

3. `[]` IS NOT `NULL`. An empty capability list is a finding ("takes none"); NULL
   is an absence ("nobody established it"). r186 shipped the column NOT NULL so
   every row read `[]`, asserting the finding 21 times by default. Both
   populations are asserted non-empty FIRST, because if either were empty the
   distinction tests would pass trivially.

4. THE REFUSED FIGURE STAYED REFUSED. `Graveliner Urn Vault`'s outside triple is
   NULL because its first component (`151/2`) is unreadable. Its inside triple is
   loaded, which is what makes this a refusal of one reading rather than of the
   row.

5. READ-THROUGH IS THE MODEL WORKING. `UV-UCG` has no CSV row and no override,
   and resolves to its product's figures. Asserted explicitly so a later reader
   does not file it as missing data.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import text

from app.database import SessionLocal

#: The 15 products the sheet covers, as (family_slug, form). Derived from the
#: sheet's 31 rows minus the 6 non-manufactured vaults that have no product yet,
#: and written out rather than computed so the test does not re-derive its
#: expected value from the same mapping the migration used.
EXPECTED_SOURCED = {
    ("wilbert-bronze", "burial_vault"),
    ("triune", "burial_vault"),
    ("venetian", "burial_vault"),
    ("continental", "burial_vault"),
    ("salute", "burial_vault"),
    ("monticello", "burial_vault"),
    ("monarch", "burial_vault"),
    ("graveliner", "grave_liner"),
    ("triune", "urn_vault"),
    ("venetian", "urn_vault"),
    ("monticello", "urn_vault"),
    ("universal", "urn_vault"),
    ("salute", "urn_vault"),
    ("graveliner", "urn_vault"),
    ("loved-and-cherished", "infant"),
}

#: Products with no row in the spec sheet. Tribute plus the five equipment
#: products — and, since r195, the eight stocked-urn products.
#:
#: ⚠️ GREW FROM 6 TO 14 AT r195, AND THE GROWTH IS CORRECT. The spec sheet is a
#: VAULT spec sheet; it predates the urns and says nothing about them, so they
#: belong in the unsourced set exactly as Tribute does. This suite's claim is
#: global — "every product without a CSV row has NULL specs" — and a global claim
#: has to grow with the table rather than be scoped away from the new rows.
#:
#: The two tests that failed when r195 landed failed CORRECTLY: they pinned a
#: 21-product population and the catalog became 29. Reported as regressions rather
#: than silently widened, because a test whose expected set is edited to match
#: whatever the code now does has stopped testing anything.
EXPECTED_UNSOURCED = {
    ("tribute", "burial_vault"),
    ("chairs", "equipment"),
    ("cremation-table", "equipment"),
    ("grass-mats", "equipment"),
    ("lowering-device", "equipment"),
    ("tent", "equipment"),
    # r195 — the twelve stocked urns, eight products on the `urn` form
    ("country-bouquet", "urn"),
    ("jewel", "urn"),
    ("moon-stone", "urn"),
    ("sedona", "urn"),
    ("victorian", "urn"),
    ("arlington", "urn"),
    ("regal", "urn"),
    ("tribute-urn", "urn"),
}

SPEC_COLS = (
    "inside_length_in", "inside_width_in", "inside_height_in",
    "outside_length_in", "outside_width_in", "outside_height_in",
    "weight_lb",
)


@pytest.fixture(scope="module")
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture(scope="module", autouse=True)
def _require_r193(db):
    """⚠️ PRECONDITION, LOUD. Without r192+r193 every assertion below is about a
    database in a different state, and several would pass vacuously."""
    head = db.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    cols = {
        r[0]
        for r in db.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'product_variant_templates'"
            )
        )
    }
    missing = set(SPEC_COLS) - cols
    assert not missing, (
        f"r192 is not applied to this database (head={head!r}); "
        f"product_variant_templates is missing {sorted(missing)}"
    )
    nullable = db.execute(
        text(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_name='product_templates' "
            "AND column_name='personalization_capability'"
        )
    ).scalar_one()
    assert nullable == "YES", (
        "personalization_capability is still NOT NULL, so `[]` and `unknown` "
        "cannot be distinguished and tests 3a/3b below are meaningless"
    )


def _key_set(db, where: str) -> set[tuple[str, str]]:
    return {
        (r[0], r[1])
        for r in db.execute(
            text(f"SELECT family_slug, form FROM product_templates WHERE {where}")
        )
    }


class TestProvenanceIsASet:
    def test_the_sourced_products_are_exactly_the_sheets_products(self, db):
        """⚠️ SET EQUALITY, NOT A COUNT. `spec_source` is the membership marker
        and not `inside_length_in`, because Loved & Cherished has a row in the
        sheet and NULL product-level dimensions on purpose — model is a size axis
        there. A check written over dimensions reports the sheet's most precisely
        measured product as unmeasured."""
        assert _key_set(db, "spec_source IS NOT NULL") == EXPECTED_SOURCED

    def test_the_unsourced_products_are_exactly_the_six(self, db):
        assert _key_set(db, "spec_source IS NULL") == EXPECTED_UNSOURCED

    def test_the_two_sets_partition_the_catalog(self, db):
        """No product is in neither set, which a pair of equalities over a
        changing table would not otherwise catch."""
        total = db.execute(text("SELECT count(*) FROM product_templates")).scalar_one()
        assert EXPECTED_SOURCED.isdisjoint(EXPECTED_UNSOURCED)
        assert total == len(EXPECTED_SOURCED) + len(EXPECTED_UNSOURCED)

    def test_every_sourced_product_cites_the_committed_csv(self, db):
        sources = {
            r[0]
            for r in db.execute(
                text(
                    "SELECT DISTINCT spec_source FROM product_templates "
                    "WHERE spec_source IS NOT NULL"
                )
            )
        }
        assert sources == {"docs/catalog/2026-10-02-sunnycrest-product-specs.csv"}
        asof = {
            r[0]
            for r in db.execute(
                text(
                    "SELECT DISTINCT spec_asof FROM product_templates "
                    "WHERE spec_source IS NOT NULL"
                )
            )
        }
        assert len(asof) == 1, f"one sheet, one as-of date; got {asof}"


class TestAbsenceStaysAbsent:
    def test_no_unsourced_product_carries_any_spec_figure(self, db):
        """No inference, no copying from a sibling. Tribute shares a family with
        nothing and the equipment products share a form with each other, so a
        family- or form-level fill would show up here."""
        cols = " OR ".join(f"{c} IS NOT NULL" for c in SPEC_COLS)
        leaked = list(
            db.execute(
                text(
                    f"SELECT family_slug, form FROM product_templates "
                    f"WHERE spec_source IS NULL AND ({cols})"
                )
            )
        )
        assert leaked == [], f"unsourced products carrying figures: {leaked}"

    def test_no_unsourced_product_claims_a_personalization_capability(self, db):
        leaked = list(
            db.execute(
                text(
                    "SELECT family_slug, form FROM product_templates "
                    "WHERE spec_source IS NULL "
                    "AND personalization_capability IS NOT NULL"
                )
            )
        )
        assert leaked == [], (
            f"products with no CSV row asserting a capability: {leaked}. "
            f"`[]` here would claim 'takes no personalization', which the sheet "
            f"does not say about them — it says nothing about them."
        )


class TestEmptyIsNotUnknown:
    def test_both_populations_are_non_empty(self, db):
        """⚠️ THE POSITIVE CONTROL, READ FIRST. The two tests below assert a
        distinction between `[]` and NULL. If either population were empty, both
        would pass while nothing was being distinguished."""
        n_empty = db.execute(
            text(
                "SELECT count(*) FROM product_templates "
                "WHERE personalization_capability::text = '[]'"
            )
        ).scalar_one()
        n_null = db.execute(
            text(
                "SELECT count(*) FROM product_templates "
                "WHERE personalization_capability IS NULL"
            )
        ).scalar_one()
        assert n_empty > 0, "no product carries the empty set — nothing to distinguish"
        assert n_null > 0, "no product carries NULL — nothing to distinguish"

    def test_empty_set_means_the_product_takes_none(self, db):
        """Monticello, Monarch, Graveliner and the Monticello urn vault have a row
        in the sheet whose personalization cell is EMPTY. That is a finding."""
        for family, form in (
            ("monticello", "burial_vault"),
            ("monarch", "burial_vault"),
            ("graveliner", "grave_liner"),
            ("monticello", "urn_vault"),
        ):
            cap, src = db.execute(
                text(
                    "SELECT personalization_capability::text, spec_source "
                    "FROM product_templates WHERE family_slug=:f AND form=:m"
                ),
                {"f": family, "m": form},
            ).one()
            assert src is not None, f"{family}/{form} should have a sheet row"
            assert cap == "[]", f"{family}/{form} capability is {cap!r}, want []"

    def test_unknown_means_nobody_established_it(self, db):
        cap = db.execute(
            text(
                "SELECT personalization_capability FROM product_templates "
                "WHERE family_slug='tribute' AND form='burial_vault'"
            )
        ).scalar_one()
        assert cap is None, (
            "Tribute Burial Vault has NO row in the sheet, so its capability is "
            "unknown rather than empty"
        )

    def test_the_three_question_ids_are_the_canonical_ones(self, db):
        """Stored ids are checked against the declaration site, not against a
        list retyped here."""
        from app.services.personalization.questions import QUESTIONS

        canonical = {q.question_id for q in QUESTIONS}
        stored = set()
        for (cap,) in db.execute(
            text(
                "SELECT personalization_capability FROM product_templates "
                "WHERE personalization_capability IS NOT NULL"
            )
        ):
            stored.update(cap)
        assert stored, "no capability ids stored at all — positive control"
        assert stored <= canonical, f"unknown question ids stored: {stored - canonical}"


class TestLovedAndCherishedUsesTheVariantTier:
    def test_the_product_tier_holds_no_dimension(self, db):
        """Its three models differ in every dimension, so there is no
        product-level truth. NULL here is correct, not missing."""
        row = db.execute(
            text(
                f"SELECT {', '.join(SPEC_COLS)} FROM product_templates "
                f"WHERE family_slug='loved-and-cherished' AND form='infant'"
            )
        ).one()
        assert all(v is None for v in row), f"L&C product tier carries {row}"

    def test_all_three_variants_carry_overrides(self, db):
        rows = {
            r[0]: r[1:]
            for r in db.execute(
                text(
                    f"SELECT v.sku, {', '.join('v.' + c for c in SPEC_COLS)} "
                    f"FROM product_variant_templates v "
                    f"JOIN product_templates t ON t.id = v.product_template_id "
                    f"WHERE t.family_slug='loved-and-cherished'"
                )
            )
        }
        assert set(rows) == {"LC-19", "LC-24", "LC-31"}
        for sku, vals in rows.items():
            assert vals[0] is not None, f"{sku} has no inside length"

    def test_the_three_variants_disagree_in_every_dimension(self, db):
        """The reason the tier exists. If a future edit collapsed them onto one
        set of figures, the override columns would be pointless and this fails."""
        rows = list(
            db.execute(
                text(
                    "SELECT v.inside_length_in, v.inside_width_in, "
                    "v.inside_height_in FROM product_variant_templates v "
                    "JOIN product_templates t ON t.id = v.product_template_id "
                    "WHERE t.family_slug='loved-and-cherished'"
                )
            )
        )
        assert len(rows) == 3
        for axis in range(3):
            vals = [r[axis] for r in rows]
            assert len(set(vals)) == 3, f"axis {axis} does not differ across models: {vals}"

    def test_only_loved_and_cherished_overrides(self, db):
        """Every other product's variants are finishes, and a finish does not
        change size. An override appearing elsewhere means someone treated a
        finish as a size."""
        cols = " OR ".join(f"v.{c} IS NOT NULL" for c in SPEC_COLS)
        families = {
            r[0]
            for r in db.execute(
                text(
                    f"SELECT DISTINCT t.family_slug FROM product_variant_templates v "
                    f"JOIN product_templates t ON t.id = v.product_template_id "
                    f"WHERE {cols}"
                )
            )
        }
        assert families == {"loved-and-cherished"}, (
            f"variant spec overrides outside L&C: {families - {'loved-and-cherished'}}"
        )


class TestTheRefusedFigureStayedRefused:
    def test_graveliner_urn_vault_has_no_outside_reading(self, db):
        """`151/2` is unreadable and its two companions are discarded with it,
        because that row's outside width (+6.00" over inside) is twice the next
        largest growth of any urn vault in the sheet."""
        row = db.execute(
            text(
                "SELECT outside_length_in, outside_width_in, outside_height_in "
                "FROM product_templates "
                "WHERE family_slug='graveliner' AND form='urn_vault'"
            )
        ).one()
        assert all(v is None for v in row), (
            f"an outside reading was stored for Graveliner Urn Vault: {row}. "
            f"If the sheet was corrected, correct this test deliberately."
        )

    def test_its_inside_reading_IS_loaded(self, db):
        """⚠️ THE CONTROL ON THE TEST ABOVE. Without this, the whole row being
        absent for any reason would satisfy it."""
        row = db.execute(
            text(
                "SELECT inside_length_in, inside_width_in, inside_height_in "
                "FROM product_templates "
                "WHERE family_slug='graveliner' AND form='urn_vault'"
            )
        ).one()
        assert row == (Decimal("14.5000"), Decimal("12.0000"), Decimal("10.0000"))

    def test_weight_is_absent_for_every_urn_vault(self, db):
        """The sheet carries no weight for any urn vault. A lift rating depends on
        that number, so NULL is the honest value and a sibling's weight is not."""
        weights = [
            r[0]
            for r in db.execute(
                text(
                    "SELECT weight_lb FROM product_templates "
                    "WHERE form='urn_vault' AND spec_source IS NOT NULL"
                )
            )
        ]
        assert weights, "no sourced urn vaults — positive control"
        assert all(w is None for w in weights), f"inferred urn-vault weights: {weights}"


class TestReadThroughIsTheModelWorking:
    def test_uv_ucg_has_no_override_and_resolves_to_its_product(self, db):
        """⚠️ NOT A GAP. `UV-UCG` (Cream & Gold) has no row in the sheet because
        the sheet names the MODEL (`P400WS`) where our catalog names the FINISH.
        The row is the product's; both variants read through to it."""
        rows = {
            r[0]: (r[1], r[2])
            for r in db.execute(
                text(
                    "SELECT v.sku, v.inside_length_in, t.inside_length_in "
                    "FROM product_variant_templates v "
                    "JOIN product_templates t ON t.id = v.product_template_id "
                    "WHERE v.sku IN ('UV-UCG', 'UV-UWS')"
                )
            )
        }
        assert set(rows) == {"UV-UCG", "UV-UWS"}
        for sku, (override, product) in rows.items():
            assert override is None, f"{sku} carries an override it should not"
            assert product == Decimal("13.0000"), f"{sku} product figure is {product}"


class TestEveryStoredFigureIsSixteenthsExact:
    def test_products(self, db):
        self._check(db, "product_templates", SPEC_COLS)

    def test_variants(self, db):
        self._check(db, "product_variant_templates", SPEC_COLS)

    @staticmethod
    def _check(db, table: str, cols: tuple[str, ...]) -> None:
        """Every figure in the sheet is sixteenths-exact. A value that is not
        came from arithmetic rather than from the sheet."""
        checked = 0
        for col in cols:
            for (v,) in db.execute(
                text(f"SELECT {col} FROM {table} WHERE {col} IS NOT NULL")
            ):
                checked += 1
                assert (Decimal(v) * 16) % 1 == 0, f"{table}.{col} = {v} not /16"
        assert checked > 0, f"no figures read from {table} — positive control"
