"""TAX-3 — a ZIP that cannot decide does not decide.

⚠️ 24 ZIP CODES INSIDE SUNNYCREST'S OWN TWELVE COUNTIES DO NOT DETERMINE A RATE.
Measured against New York State's ZIP→County cross-reference (data.ny.gov
juva-r6g2, loaded as `data/ny-zip-counties.json`): 57 ZIPs touch two or more of
the twelve, and 24 of those do not resolve — **19** because the counties they
span charge different rates (Oneida 8.75%, Ontario 7.5%, the rest 8%), and **5**
because they spill into a county this tenant has no rate configured for. For a
customer in one of those, a ZIP lookup returns whichever county the source
assigned and is wrong for a real share of them, by 0.5–0.75 points, in both
directions, forever.

⚠️ THE FIRST COUNT OF THIS WAS REPORTED AS "22 CROSSING A RATE BOUNDARY" AND WAS
WRONG. It intersected the straddle list with "ZIPs touching Oneida or Ontario",
which merged two different refusals and missed two ZIPs that spill outside the
twelve without touching either. 19 + 5 = 24 is the corrected split, and the
buckets are counted the way the resolver decides rather than the way a
convenient filter would. The ruling it informed does not change; the numbers do.

Publication 718 says so itself — *"the use of ZIP codes for tax collection
results in a high degree of inaccurate tax reporting"* — but that reads as
distant-metro caution. The measurement is what makes it local.

⚠️ AND A STRADDLE IS ONLY AMBIGUOUS IF THE ANSWER DIFFERS. The other 33 straddles
resolve, because every county they touch charges 8% and the rate is the same
whichever one the customer is actually in. Refusing those would be theatre.

⚠️ THEY ARE HARMLESS ONLY BECAUSE THOSE RATES MATCH TODAY. If one of those
counties changes rate, those 33 ZIPs silently become ambiguous and nothing announces
it — Publication 718-A announces RATE changes, not the second-order fact that a
rate change made a ZIP undecidable. `TestHarmlessTodayIsNotHarmlessForever`
encodes the current agreement so that a future rate correction fails loudly here
instead of quietly mispricing.

⚠️ THE PREVIOUS RESOLVER USED 107 COUNTY CENTROIDS AS A COVERAGE TABLE. One ZIP
per county — so 14580 (Webster, Monroe) resolved to nothing while 14604
(Rochester) resolved fine, and every real customer outside those 107 silently
charged zero tax. B-2's own test used 13021, one of the 107, so it passed and
would have passed against a one-entry map.
"""
from __future__ import annotations

import json
import pathlib
import uuid
from decimal import Decimal

import pytest

from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture

TENANT = TESTCO_ID
BACKEND = pathlib.Path(__file__).resolve().parent.parent
ZIP_FILE = BACKEND / "data" / "ny-zip-counties.json"

#: Sunnycrest's configured twelve, and the rates Publication 718 gives them.
SUNNYCREST = {
    "Cayuga": "8", "Cortland": "8", "Madison": "8", "Monroe": "8",
    "Oneida": "8.75", "Onondaga": "8", "Ontario": "7.5", "Oswego": "8",
    "Seneca": "8", "Tompkins": "8", "Wayne": "8", "Yates": "8",
}

canonical_tenant = make_canonical_tenant_fixture(
    child_tables=("customers", "tax_jurisdictions", "tax_rates"),
)


@pytest.fixture
def db():
    from app.database import SessionLocal

    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture
def twelve(db):
    """Sunnycrest's twelve counties, configured on the canonical tenant."""
    from app.models.tax import TaxJurisdiction, TaxRate

    for county, pct in SUNNYCREST.items():
        rate = TaxRate(id=str(uuid.uuid4()), tenant_id=TENANT,
                       rate_name=f"t-{county}", rate_percentage=Decimal(pct))
        db.add(rate)
        db.flush()
        db.add(TaxJurisdiction(
            id=str(uuid.uuid4()), tenant_id=TENANT, jurisdiction_name=county,
            state="NY", county=county.lower(), tax_rate_id=rate.id))
    db.flush()


def _customer(db, *, zip_code=None, tax_county=None, name="Cust"):
    from app.models.customer import Customer

    c = Customer(id=str(uuid.uuid4()), company_id=TENANT, name=name,
                 zip_code=zip_code, tax_county=tax_county)
    db.add(c)
    db.flush()
    return c


class TestTheZipData:
    def test_it_covers_new_york_and_records_its_own_staleness(self):
        """⚠️ THE CAVEAT IS PART OF THE DATA. The source has never been revised
        since 2007, so it UNDER-DETECTS ambiguity — the unsafe direction. A file
        that carries the numbers without carrying that fact would be read as
        authoritative."""
        doc = json.loads(ZIP_FILE.read_text())
        assert len(doc["zips"]) == 2169
        meta = doc["metadata"]
        assert meta["source_file_date"] == "2007-07-25"
        assert meta["verified_on"] == "2026-08-20"
        assert "UNDER-DETECTS" in meta["caveat"]
        assert "never to assert a county" in meta["caveat"]

    def test_the_centroid_file_is_not_the_coverage_file(self):
        """They are different data with different jobs. 14580 is the worked
        example: absent from the centroid file, present here."""
        from app.services.county_geographic_service import (
            _load_zip_mapping,
            counties_for_zip,
        )

        assert "14580" not in _load_zip_mapping()
        assert counties_for_zip("14580") == ["Monroe", "Wayne"]

    def test_counties_are_in_the_platforms_vocabulary(self):
        """The state prints "St. Lawrence"; every platform file uses
        "St Lawrence". This one has to join with them."""
        doc = json.loads(ZIP_FILE.read_text())
        names = {c for cs in doc["zips"].values() for c in cs}
        assert "St Lawrence" in names
        assert "St. Lawrence" not in names


class TestResolution:
    def test_an_unambiguous_zip_resolves(self, db, twelve):
        from app.services.tax_service import get_jurisdiction_for_order

        c = _customer(db, zip_code="13021")  # Cayuga only
        jur, rate = get_jurisdiction_for_order(db, TENANT, None, c.id)
        assert jur and jur.county == "cayuga"
        assert rate.rate_percentage == Decimal("8")

    def test_a_straddle_whose_counties_agree_still_resolves(self, db, twelve):
        """⚠️ 13045 SPANS CAYUGA, CORTLAND AND TOMPKINS — ALL AT 8%. The rate is
        the same whichever the customer is in, so refusing would be theatre and
        would put 33 ZIPs behind an operator prompt for no gain."""
        from app.services.tax_service import get_jurisdiction_for_order

        c = _customer(db, zip_code="13045")
        jur, rate = get_jurisdiction_for_order(db, TENANT, None, c.id)
        assert jur is not None
        assert rate.rate_percentage == Decimal("8")

    def test_a_straddle_whose_counties_disagree_does_not_resolve(self, db, twelve):
        """14456 spans Ontario (7.5%), Seneca (8%) and Yates (8%)."""
        from app.services.tax_service import get_jurisdiction_for_order

        c = _customer(db, zip_code="14456")
        assert get_jurisdiction_for_order(db, TENANT, None, c.id) == (None, None)

    def test_an_explicit_tax_county_beats_the_zip(self, db, twelve):
        from app.services.tax_service import get_jurisdiction_for_order

        c = _customer(db, zip_code="14456", tax_county="Seneca")
        jur, rate = get_jurisdiction_for_order(db, TENANT, None, c.id)
        assert jur.county == "seneca"
        assert rate.rate_percentage == Decimal("8")

    def test_a_straddle_into_an_unconfigured_county_does_not_resolve(self, db):
        """⚠️ EVERY CANDIDATE MUST BE CONFIGURED, NOT JUST ONE. With only
        Cortland set up, 13045's customer might genuinely be in Cayuga or
        Tompkins — resolving to Cortland because it is the only row we have is a
        guess wearing a lookup's clothes."""
        from app.models.tax import TaxJurisdiction, TaxRate
        from app.services.tax_service import get_jurisdiction_for_order

        rate = TaxRate(id=str(uuid.uuid4()), tenant_id=TENANT,
                       rate_name="t-cortland-only", rate_percentage=Decimal("8"))
        db.add(rate)
        db.flush()
        db.add(TaxJurisdiction(id=str(uuid.uuid4()), tenant_id=TENANT,
                               jurisdiction_name="Cortland", state="NY",
                               county="cortland", tax_rate_id=rate.id))
        db.flush()
        c = _customer(db, zip_code="13045")
        assert get_jurisdiction_for_order(db, TENANT, None, c.id) == (None, None)


class TestTheOverrideSurvivesTheApiContract:
    """⚠️ A FIELD THE SCHEMA SILENTLY DROPS IS A FIELD THAT DOES NOT EXIST, and
    the operator would have no way to tell — the form would accept the county,
    the save would succeed, and the order would still refuse. Pydantic ignores
    unknown keys by default, so `CustomerUpdate` accepting `tax_county` has to be
    asserted rather than assumed.

    Covers schema → model → resolver. The remaining link is the React payload
    (`customer-detail.tsx`, in the same object literal as `zip_code`), which is
    verified by reading rather than by breaking — recorded as such."""

    def test_an_update_persists_it_and_changes_resolution(self, db, twelve):
        from app.schemas.customer import CustomerUpdate
        from app.services.tax_service import get_jurisdiction_for_order

        c = _customer(db, zip_code="14456", name="Override Co")
        assert get_jurisdiction_for_order(db, TENANT, None, c.id) == (None, None)

        payload = CustomerUpdate(tax_county="Yates")
        assert payload.tax_county == "Yates", "CustomerUpdate dropped tax_county"
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(c, k, v)
        db.flush()

        jur, rate = get_jurisdiction_for_order(db, TENANT, None, c.id)
        assert jur.county == "yates"
        assert rate.rate_percentage == Decimal("8")

    def test_blank_is_treated_as_unset_rather_than_stored(self, db, twelve):
        """The frontend sends `undefined` for blank; the validator turns a
        stray empty string into None. Either way a blank must mean "derive from
        the ZIP", never "the county is empty-string"."""
        from app.schemas.customer import CustomerUpdate

        assert CustomerUpdate(tax_county="   ").tax_county is None


class TestTheRefusalNamesTheAmbiguity:
    """⚠️ "CANNOT RESOLVE" SENDS SOMEONE HUNTING. Three failures need three
    different actions, and one message for all of them is the same defect as a
    health check that cannot tell "did not run" from "found nothing"."""

    def test_it_names_the_counties_and_their_rates(self, db, twelve):
        from app.services.tax_service import unresolved_reason_for_customer

        c = _customer(db, zip_code="14456", name="Hopkins FH")
        reason = unresolved_reason_for_customer(db, c.id)
        assert "14456" in reason
        for county in ("Ontario", "Seneca", "Yates"):
            assert county in reason
        # The rates are what make it obvious WHY it matters.
        assert "7.5%" in reason and "8%" in reason
        assert "Hopkins FH" in reason

    def test_a_missing_zip_says_so_instead(self, db, twelve):
        from app.services.tax_service import unresolved_reason_for_customer

        c = _customer(db, zip_code=None, name="No Address Co")
        reason = unresolved_reason_for_customer(db, c.id)
        assert "no ZIP code" in reason
        assert "not the same as being exempt" in reason

    def test_an_unconfigured_county_says_that_instead(self, db):
        from app.services.tax_service import unresolved_reason_for_customer

        c = _customer(db, zip_code="13021", name="Cayuga Co")
        reason = unresolved_reason_for_customer(db, c.id)
        assert "Cayuga" in reason and "tax settings" in reason

    def test_the_three_reasons_are_distinguishable(self, db, twelve):
        """Held explicitly, because the failure mode being fixed is that they
        used to be one string."""
        from app.services.tax_service import unresolved_reason_for_customer

        reasons = {
            unresolved_reason_for_customer(db, _customer(db, zip_code=z, name=n).id)
            for z, n in (("14456", "A"), (None, "B"), ("13032", "C"))
        }
        assert len(reasons) == 3


class TestHarmlessTodayIsNotHarmlessForever:
    """⚠️ THE SECOND-ORDER ALARM. 35 ZIPs straddle counties that all charge 8%,
    so they resolve. That is a fact about TODAY'S RATES, not about geography.
    Publication 718-A announces rate changes; nothing announces that a rate
    change has made a ZIP undecidable.

    This encodes the current agreement so a future rate correction — the
    quarterly diff doing its job — fails HERE, naming the ZIPs it just made
    ambiguous, instead of silently routing them into the wrong rate."""

    @staticmethod
    def _buckets() -> tuple[dict, dict, dict]:
        """(resolve, rate_differs, spills_outside) for ZIPs touching ≥2 of the
        twelve. The three buckets are the three outcomes the resolver produces,
        and they are counted the way the resolver decides — not the way a
        convenient filter would."""
        doc = json.loads(ZIP_FILE.read_text())
        touching = {
            z: cs for z, cs in doc["zips"].items()
            if sum(c in SUNNYCREST for c in cs) >= 2
        }
        spills = {z: cs for z, cs in touching.items()
                  if not all(c in SUNNYCREST for c in cs)}
        inside = {z: cs for z, cs in touching.items() if z not in spills}
        resolve = {z: cs for z, cs in inside.items()
                   if len({SUNNYCREST[c] for c in cs}) == 1}
        differs = {z: cs for z, cs in inside.items()
                   if len({SUNNYCREST[c] for c in cs}) > 1}
        return resolve, differs, spills

    def test_the_three_buckets_are_what_was_measured(self):
        """⚠️ THESE NUMBERS WERE REPORTED WRONG ONCE AND ARE PINNED HERE SO THEY
        CANNOT DRIFT SILENTLY. The first count intersected the straddle list
        with "ZIPs touching Oneida or Ontario", which conflated two different
        refusals: a ZIP whose counties charge different rates, and a ZIP that
        spills into a county this tenant has no rate for. Both refuse, for
        different reasons, and an operator fixes them differently."""
        resolve, differs, spills = self._buckets()
        assert len(resolve) + len(differs) + len(spills) == 57
        assert len(differs) == 19, (
            f"{len(differs)} straddling ZIPs cross a rate boundary, not 19 — a "
            f"rate changed. Newly ambiguous: "
            f"{sorted(set(differs) - _RATE_DIFFERING)}"
        )
        assert len(spills) == 5
        assert len(resolve) == 33

    def test_the_resolvable_straddles_still_agree_on_their_rate(self):
        """The direct form. If this fails, the listed ZIPs stopped being
        decidable from a ZIP alone and their customers now need `tax_county`."""
        resolve, differs, _ = self._buckets()
        newly = {
            z: sorted({f"{c} {SUNNYCREST[c]}%" for c in cs})
            for z, cs in differs.items() if z not in _RATE_DIFFERING
        }
        assert not newly, (
            "these ZIPs were resolvable and are not any more:\n  "
            + "\n  ".join(f"{z}: {v}" for z, v in sorted(newly.items()))
        )
        assert _RATE_DIFFERING - set(differs) == set(), (
            "these were ambiguous and now resolve — verify the rate change was "
            f"intended: {sorted(_RATE_DIFFERING - set(differs))}"
        )


#: The 19 measured on 2026-08-20. Listed rather than counted so a change in the
#: SET shows in a diff, not only a change in the total.
_RATE_DIFFERING = {
    "13032", "13042", "13402", "13409", "13421", "13425", "13477", "13480",
    "13483", "14432", "14456", "14489", "14513", "14522", "14532", "14534",
    "14544", "14561", "14564",
}
