"""The Opas catalog pane reads only what exists.

⚠️ THE SPARSENESS IS THE CONTRACT, which is why these tests assert ABSENCE as hard as
presence. The ruling for this slice is "a row or pill renders only if its data exists; no
empty states inside the pane", and the only way a client can honour that is if the server
omits keys rather than sending nulls. A `response_model` would have re-introduced them,
so there is none — and that makes these tests the only thing holding the shape.

⚠️ MEASURED STATE AT 2026-10-06, so a reader knows what these numbers mean:
    52 variants · 29 with at least one spec · 5 with a confirmed alias
    0 with personalization availability — of 3 wilbert_program_enrollments rows, all 3
      carry a personalization_config and NONE has an `availability` key
The personalization assertions below therefore pin an ABSENCE that is real, not a stub.

⚠️ ALMOST READ-ONLY — ONE TEST INSERTS AND ROLLS BACK. This said "READ-ONLY. Creates no
rows" and that stopped being true when the alias gate got a constructed subject: there are
5 confirmed aliases and ZERO unconfirmed ones, so nothing in the data can tell a gated
query from an ungated one. The insert happens inside a SAVEPOINT that the test rolls back,
so no row outlives it and there is still no litter — but the claim needed correcting rather
than leaving in place.
"""
from __future__ import annotations

import pytest

from app.database import SessionLocal
from app.services.catalog_pane_service import list_variants, variant_detail


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
    return list_variants(db)


class TestTheListIsTheWholeCatalog:
    def test_it_returns_every_active_variant(self, db, rows):
        """⚠️ COMPARED AGAINST THE TABLE, not a literal. A hardcoded 52 would go stale the
        day a variant is added and would fail for the wrong reason."""
        from sqlalchemy import text

        expected = db.execute(text(
            "SELECT count(*) FROM product_variant_templates WHERE is_active IS TRUE"
        )).scalar_one()
        assert len(rows) == expected
        assert expected > 0, "the catalog is empty — every assertion below is vacuous"

    def test_every_row_carries_the_three_fields_a_row_renders(self, rows):
        for r in rows:
            assert r["variant_template_id"]
            assert r["name"]
            assert r["kind"], f"{r['name']} has no kind, so it cannot be grouped"

    def test_it_is_ordered_by_kind_so_grouping_needs_no_client_sort(self, rows):
        """⚠️ Grouping in the pane assumes contiguity. If the server's order broke, the
        pane would render the same kind twice under two headings."""
        kinds = [r["kind"] for r in rows]
        first_seen = {}
        for i, k in enumerate(kinds):
            first_seen.setdefault(k, i)
        assert kinds == sorted(kinds, key=lambda k: first_seen[k]), (
            f"a kind appears in two runs: {kinds}"
        )

    def test_more_than_one_kind_exists(self, rows):
        """⚠️ THE POSITIVE CONTROL ON THE ORDERING TEST. With one kind, contiguity holds
        trivially and the assertion above proves nothing."""
        assert len({r["kind"] for r in rows}) >= 3


class TestNullIsOmittedNeverSentAsNull:
    def test_no_list_row_carries_a_null_value(self, rows):
        for r in rows:
            nulls = [k for k, v in r.items() if v is None]
            assert nulls == [], f"{r.get('name')} sent null for {nulls}"

    def test_no_detail_payload_carries_a_null_value(self, db, rows):
        for r in rows:
            d = variant_detail(db, r["variant_template_id"])
            nulls = [k for k, v in (d or {}).items() if v is None]
            assert nulls == [], f"{r['name']} sent null for {nulls}"

    def test_a_variant_without_specs_has_no_specs_key_at_all(self, db, rows):
        """Not `specs: {}`, not `specs: null` — absent. An empty dict is falsy in JS and
        would work by accident, which is worse than working on purpose."""
        bare = [
            r for r in rows
            if not (variant_detail(db, r["variant_template_id"]) or {}).get("specs")
        ]
        assert bare, "every variant has specs — this test cannot discriminate"
        for r in bare:
            assert "specs" not in (variant_detail(db, r["variant_template_id"]) or {})


class TestSpecsComeFromTheProductTierNotTheVariant:
    def test_some_variants_have_specs(self, db, rows):
        """⚠️ THE ASSERTION MY PART 4 REPORT GOT WRONG. I measured
        `product_variant_templates` (inside 3/52, weight 0/52) and reported that Specs
        renders nothing. r193 writes to `product_templates`: spec_source 15/29,
        inside_length_in 14/29. Specs is real for over half the catalog, and the verdict
        was wrong because it was taken at the wrong tier."""
        n = sum(1 for r in rows
                if (variant_detail(db, r["variant_template_id"]) or {}).get("specs"))
        assert n >= 20, f"only {n} of {len(rows)} variants carry specs"

    def test_spec_source_travels_with_the_specs(self, db, rows):
        """⚠️ r193: "SO `spec_source` IS THE MEMBERSHIP MARKER, NOT `inside_length_in`" —
        one family's sheet records no inside dimensions, so keying off a dimension would
        report it as unmeasured. Where a spec block exists it should say where it came
        from."""
        sourced = 0
        for r in rows:
            specs = (variant_detail(db, r["variant_template_id"]) or {}).get("specs") or {}
            if specs.get("spec_source"):
                sourced += 1
        assert sourced >= 20, f"only {sourced} spec blocks name their source"

    def test_no_spec_value_is_the_string_None(self, db, rows):
        """⚠️ The service stringifies Decimals. A None reaching `str()` becomes the
        four-character string "None", which renders as a plausible value and is the exact
        shape a null-omission bug takes once a formatter is involved."""
        for r in rows:
            specs = (variant_detail(db, r["variant_template_id"]) or {}).get("specs") or {}
            assert "None" not in specs.values(), f"{r['name']}: {specs}"


class TestAliases:
    def test_confirmed_aliases_reach_the_pane(self, db, rows):
        n = sum(1 for r in rows
                if (variant_detail(db, r["variant_template_id"]) or {}).get("aliases"))
        assert n >= 1, "no variant has a confirmed alias — the pill can never render"

    # ⚠️ `test_unconfirmed_aliases_do_not` REMOVED 2026-10-06. It looked for an
    # unconfirmed alias in the live data and skipped when it found none — which it always
    # did, because there are zero. A test that can only skip is not coverage, and its skip
    # was concealing that the gate was untested. Replaced by
    # `TestTheAliasGateIsConfirmedOnly`, which CONSTRUCTS the subject and rolls it back.


class TestPersonalizationIsAbsentAndThatIsMeasured:
    def test_no_variant_offers_personalization_today(self, db, rows):
        """⚠️ THIS PINS AN ABSENCE THAT IS REAL AND WILL CHANGE. Of 3
        `wilbert_program_enrollments` rows, all 3 carry a `personalization_config` and NONE
        has an `availability` key, so `read_availability` returns NOT_CONFIGURED for every
        question on every variant — and NOT_CONFIGURED is not data.

        When a licensee records availability this test FAILS, and that failure is the
        feature arriving. Replace it then with the positive assertion; do not relax it
        now."""
        from app.models.company import Company

        company_id = db.query(Company.id).limit(1).scalar()
        offered = [
            r["name"] for r in rows
            if (variant_detail(db, r["variant_template_id"], company_id=company_id) or {})
            .get("personalization")
        ]
        assert offered == [], (
            f"personalization availability now exists for {offered} — this is the "
            f"feature arriving, not a regression. Swap this for the positive assertion."
        )

    def test_not_configured_is_not_reported_as_offered(self, db, rows):
        """The discriminating half: the lookup IS being called, and its NOT_CONFIGURED
        answer is being dropped rather than never consulted."""
        from app.services.personalization.availability import (
            AvailabilityState,
            read_availability,
        )

        state = read_availability({}, rows[0]["variant_template_id"], "legacy_print").state
        assert state is AvailabilityState.NOT_CONFIGURED
        d = variant_detail(db, rows[0]["variant_template_id"], company_id=None) or {}
        assert "personalization" not in d


class TestUnknownIdIsLoud:
    def test_it_returns_none_rather_than_an_empty_pane(self, db):
        assert variant_detail(db, "not-a-real-variant-id") is None


# ---------------------------------------------------------------------------
# Unit-level: the omission contract, with constructed subjects
# ---------------------------------------------------------------------------

class TestPresentOnlyOmitsWhatIsNotEstablished:
    """⚠️ THESE EXIST BECAUSE A BREAK TEST CAME BACK GREEN, AND THE DIAGNOSIS WAS WRONG
    TWICE OVER. The omission was inline in two separate loops; the break was aimed at the
    list loop only, so the detail loop was never broken — and four of the five fields have
    no NULL in the data, so even a correctly-aimed break could only be caught by
    `description`. I reported it as a blind test when it was a mis-aimed break. A helper
    with constructed input is testable either way.
    """

    def test_a_null_value_is_omitted_not_sent(self):
        from app.services.catalog_pane_service import present_only

        assert present_only({"a": None, "b": "x"}, ("a", "b")) == {"b": "x"}

    def test_an_empty_string_is_omitted(self):
        from app.services.catalog_pane_service import present_only

        assert present_only({"a": "", "b": "x"}, ("a", "b")) == {"b": "x"}

    def test_whitespace_is_omitted(self):
        """⚠️ A name of " " renders as a blank row, which reads as a bug in the pane rather
        than a gap in the data."""
        from app.services.catalog_pane_service import present_only

        assert present_only({"a": "   ", "b": "x"}, ("a", "b")) == {"b": "x"}

    def test_a_missing_key_is_not_an_error(self):
        from app.services.catalog_pane_service import present_only

        assert present_only({"b": "x"}, ("a", "b")) == {"b": "x"}

    def test_zero_and_false_are_KEPT(self):
        """⚠️ THE DISCRIMINATING CASE, and the one a truthiness test gets wrong. A weight of
        0 and a flag of False are ESTABLISHED values. Omitting them would turn a measured
        zero into "not recorded", which is the r196 confusion in the other direction."""
        from app.services.catalog_pane_service import present_only

        assert present_only({"a": 0, "b": False}, ("a", "b")) == {"a": 0, "b": False}

    def test_the_detail_omit_list_contains_the_one_field_that_is_null_in_the_data(self):
        """⚠️ PINS WHY THE ORIGINAL BREAK MISSED. `description` is NULL for 15 of 52 and is
        in the DETAIL list only; the other four are never NULL. A break aimed at the list
        loop therefore cannot produce a single null, whatever it does."""
        from app.services.catalog_pane_service import _DETAIL_OPTIONAL, _LIST_OPTIONAL

        assert "description" in _DETAIL_OPTIONAL
        assert "description" not in _LIST_OPTIONAL

    def test_a_real_variant_with_a_null_description_omits_the_key(self, db, rows):
        """The same contract end-to-end, on the field that actually discriminates."""
        from sqlalchemy import text

        vid = db.execute(text(
            "SELECT id FROM product_variant_templates "
            "WHERE description IS NULL AND is_active IS TRUE LIMIT 1"
        )).scalar()
        assert vid is not None, "no variant has a null description — this cannot discriminate"
        assert "description" not in (variant_detail(db, vid) or {})


class TestTheAliasGateIsConfirmedOnly:
    def test_an_unconfirmed_alias_is_excluded(self, db, rows):
        """⚠️ CONSTRUCTED SUBJECT, ROLLED BACK. Zero unconfirmed aliases exist, so this
        gate was untested and a break removing `is_confirmed IS TRUE` came back green. The
        alias is inserted in a savepoint and discarded.

        `is_confirmed` is the same gate `product_name_resolver` uses. An unconfirmed alias
        is a guess nobody has accepted; rendering it under "what Opas knows" would present
        a guess as knowledge.
        """
        import uuid

        from sqlalchemy import text

        vid = rows[0]["variant_template_id"]
        before = (variant_detail(db, vid) or {}).get("aliases") or []
        probe = f"zz-unconfirmed-{uuid.uuid4().hex[:8]}"
        sp = db.begin_nested()
        try:
            db.execute(text(
                "INSERT INTO platform_product_aliases "
                "(id, variant_template_id, alias_text, alias_text_normalized, "
                " is_confirmed, source, created_at) "
                # ⚠️ `source` CARRIES A CHECK CONSTRAINT: production_catalog | spec_sheet |
                # wilbert_store | manual. 'test' is rejected, which is the constraint doing
                # its job — read the definition rather than guessing a value.
                "VALUES (:i, :v, :a, :a, FALSE, 'manual', now())"
            ), {"i": str(uuid.uuid4()), "v": vid, "a": probe})
            db.flush()
            # ⚠️ POSITIVE CONTROL ON THE SUBJECT: prove the row is visible to this session
            # before concluding anything from its absence downstream.
            n = db.execute(text(
                "SELECT count(*) FROM platform_product_aliases WHERE alias_text = :a"
            ), {"a": probe}).scalar_one()
            assert n == 1, "the probe alias was not inserted; the test would be vacuous"

            after = (variant_detail(db, vid) or {}).get("aliases") or []
            assert probe not in after, "an UNCONFIRMED alias reached the pane"
            assert after == before, "the gate changed the confirmed set"
        finally:
            sp.rollback()
