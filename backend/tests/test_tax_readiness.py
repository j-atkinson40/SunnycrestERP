"""TAX-4 — the readiness step: an obligation the tenant meets by knowing.

⚠️ COMPLETING IT MEANS THE TENANT LOOKED, NOT THAT EVERY CUSTOMER RESOLVES.
A tenant with 400 imported customers and 30 bad addresses must be able to finish
onboarding — the 30 surface at the till once the order path refuses, and
blocking platform use over them would be the wrong trade. So the completion hook
fires when the report is VIEWED, and the copy never implies zero is required.

⚠️ AND IT NAMES THE ROWS. A count sends someone hunting; three different
failures want three different actions:

    no_address    → the customer needs a ZIP
    ambiguous     → the ZIP spans counties charging different rates; set
                    `tax_county`
    unconfigured  → resolves to a county with no jurisdiction; add it

Collapsing them into "unresolved" would be the same defect as the single
"cannot resolve" sentence r172 replaced, and as a health report that cannot
distinguish "did not run" from "found nothing".

⚠️ NOTHING IS CACHED, DELIBERATELY. The answer changes every time a customer is
edited. A stored readiness count is a second producer of a fact derived from
`customers` and goes stale the moment someone fixes an address — the
`setup_complete` shape, where a flag outlives what it described.
"""
from __future__ import annotations

import pathlib
import uuid
from decimal import Decimal

import pytest

from tests._source import code_only
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture

TENANT = TESTCO_ID
BACKEND = pathlib.Path(__file__).resolve().parent.parent
REPO = BACKEND.parent

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
def jurisdictions(db):
    """Cayuga 8%, Ontario 7.5%, Seneca 8%, Yates 8% — enough for 14456 to be
    genuinely rate-ambiguous and 13021 to resolve."""
    from app.models.tax import TaxJurisdiction, TaxRate

    for county, pct in (("cayuga", "8"), ("ontario", "7.5"),
                        ("seneca", "8"), ("yates", "8")):
        rate = TaxRate(id=str(uuid.uuid4()), tenant_id=TENANT,
                       rate_name=f"r-{county}", rate_percentage=Decimal(pct))
        db.add(rate)
        db.flush()
        db.add(TaxJurisdiction(id=str(uuid.uuid4()), tenant_id=TENANT,
                               jurisdiction_name=county, state="NY",
                               county=county, tax_rate_id=rate.id))
    db.flush()


def _customer(db, name, *, zip_code=None, tax_county=None):
    from app.models.customer import Customer

    c = Customer(id=str(uuid.uuid4()), company_id=TENANT, name=name,
                 zip_code=zip_code, tax_county=tax_county)
    db.add(c)
    db.flush()
    return c


def _bucket_of(report, customer_id) -> str:
    for state, rows in report["customers"].items():
        if any(r["customer_id"] == customer_id for r in rows):
            return state
    raise AssertionError(f"{customer_id} appears in no bucket")


class TestTheThreeFailuresStaySeparate:
    def test_a_customer_with_no_address(self, db, jurisdictions):
        from app.services.tax_service import tax_readiness

        c = _customer(db, "No Address Co")
        report = tax_readiness(db, TENANT)
        assert _bucket_of(report, c.id) == "no_address"
        row = next(r for r in report["customers"]["no_address"] if r["customer_id"] == c.id)
        assert "no ZIP code" in row["reason"]
        assert "not the same as being exempt" in row["reason"]

    def test_a_rate_ambiguous_zip(self, db, jurisdictions):
        """14456 spans Ontario (7.5%), Seneca (8%), Yates (8%)."""
        from app.services.tax_service import tax_readiness

        c = _customer(db, "Ambiguous Co", zip_code="14456")
        report = tax_readiness(db, TENANT)
        assert _bucket_of(report, c.id) == "ambiguous"
        row = next(r for r in report["customers"]["ambiguous"] if r["customer_id"] == c.id)
        # ⚠️ THE COUNTIES AND THEIR RATES, NOT "CANNOT RESOLVE".
        for county in ("Ontario", "Seneca", "Yates"):
            assert county in row["reason"]
        assert "7.5%" in row["reason"]

    def test_a_resolving_customer(self, db, jurisdictions):
        from app.services.tax_service import tax_readiness

        c = _customer(db, "Resolves Co", zip_code="13021")
        report = tax_readiness(db, TENANT)
        assert _bucket_of(report, c.id) == "resolves"
        row = next(r for r in report["customers"]["resolves"] if r["customer_id"] == c.id)
        assert row["county"] == "cayuga"
        assert row["rate_percentage"] == 8.0

    def test_the_override_moves_a_customer_into_resolves(self, db, jurisdictions):
        from app.services.tax_service import tax_readiness

        c = _customer(db, "Overridden Co", zip_code="14456", tax_county="Seneca")
        assert _bucket_of(tax_readiness(db, TENANT), c.id) == "resolves"

    def test_the_buckets_are_distinguishable(self, db, jurisdictions):
        """Held explicitly: the defect being avoided is one bucket called
        'unresolved' that three different fixes all point at."""
        from app.services.tax_service import tax_readiness

        _customer(db, "A")
        _customer(db, "B", zip_code="14456")
        report = tax_readiness(db, TENANT)
        reasons = {
            r["reason"]
            for state in ("no_address", "ambiguous", "unconfigured")
            for r in report["customers"][state]
        }
        assert len(reasons) >= 2


class TestTheVerdict:
    def test_no_customers_is_not_the_same_as_all_resolving(self, db, jurisdictions):
        """⚠️ AN EMPTY RESULT AND A CLEAN ONE MUST NOT RENDER ALIKE — the shape
        that let a 500-ing Exemptions tab report "no tax-exempt customers"."""
        from app.services.tax_service import tax_readiness

        report = tax_readiness(db, TENANT)
        if report["total_customers"] == 0:
            assert report["verdict"] == "reported_none"
        else:  # a seeded machine has customers; assert the other arm instead
            assert report["verdict"] in ("partial", "complete")

    def test_partial_when_some_resolve_and_some_do_not(self, db, jurisdictions):
        from app.services.tax_service import tax_readiness

        _customer(db, "Good", zip_code="13021")
        _customer(db, "Bad")
        report = tax_readiness(db, TENANT)
        assert report["verdict"] == "partial"
        assert report["resolves"] >= 1 and report["unresolved"] >= 1

    def test_counts_and_rows_agree(self, db, jurisdictions):
        """A count that disagrees with its own list is how a summary starts
        lying about the thing underneath it."""
        from app.services.tax_service import tax_readiness

        _customer(db, "X", zip_code="14456")
        _customer(db, "Y")
        report = tax_readiness(db, TENANT)
        for state, n in report["counts"].items():
            assert n == len(report["customers"][state]), state
        assert report["total_customers"] == sum(report["counts"].values())
        assert report["unresolved"] == report["total_customers"] - report["resolves"]


class TestTheStepIsReachable:
    """⚠️ THE FAILURE THIS ARC KEEPS FINDING IS A SURFACE THAT DOES NOT EXIST
    BEHIND A CORRECT-LOOKING POINTER — the incomplete-customer alarm linking at
    `?filter=incomplete`, which `customers.tsx` never read. A checklist item
    whose `action_target` 404s is the same defect with a nicer frame."""

    def test_the_item_is_declared(self):
        from app.services.onboarding_service import MANUFACTURING_CHECKLIST_ITEMS

        item = next(i for i in MANUFACTURING_CHECKLIST_ITEMS
                    if i["item_key"] == "verify_tax_readiness")
        assert item["tier"] == "must_complete"
        # Readiness cannot be judged before there are jurisdictions to resolve
        # against — every customer would read as unconfigured.
        assert item["depends_on"] == "setup_tax_jurisdictions"
        assert item["action_target"] == "/onboarding/tax-readiness"

    def test_its_target_route_exists(self):
        app = (REPO / "frontend" / "src" / "App.tsx").read_text()
        assert 'path="onboarding/tax-readiness"' in app, (
            "the step points at a route that is not mounted"
        )

    def test_the_endpoint_backing_the_page_exists(self):
        from app.main import app

        paths = {getattr(r, "path", "") for r in app.routes}
        assert "/api/v1/tax/readiness" in paths

    def test_viewing_the_report_is_what_completes_it(self):
        """Not reaching zero. A tenant with unfixable addresses must still be
        able to finish onboarding."""
        src = code_only((BACKEND / "app" / "api" / "routes" / "tax.py").read_text())
        body = src.split("def tax_readiness_report")[1].split("\n@router")[0]
        assert 'check_completion' in body and "verify_tax_readiness" in body


class TestTheRateProvenanceSurvivesToTheUi:
    """⚠️ TWO FACTS SHARED THE WORD `source` AND THE VALUABLE ONE WAS DISCARDED.
    The suggestion's `source` meant HOW THE COUNTY WAS SUGGESTED; the resolver's
    meant WHERE THE RATE CAME FROM. Building the payload with an explicit key
    list dropped the second, so a New York rate verified against Publication 718
    and an Ohio rate from an unverified 2025 compilation arrived identical."""

    def test_a_verified_rate_carries_its_provenance(self, db):
        from app.services.county_geographic_service import build_suggestions

        rows = build_suggestions(tenant_zip="13021", tenant_state="NY",
                                 radius_miles=30, db=db)
        cayuga = next(r for r in rows if r["county"] == "Cayuga")
        assert cayuga["rate_source"] == "platform_tax_rates"
        assert cayuga["rate_verified_on"] == "2026-08-20"
        assert cayuga["jurisdiction_code"] == "0511"

    def test_an_unverified_rate_says_nothing_rather_than_claiming_verification(self, db):
        """Ohio's rates may well be right. What would be dishonest is presenting
        unchecked numbers with the same confidence as checked ones."""
        from app.services.county_geographic_service import build_suggestions

        rows = build_suggestions(tenant_zip="44114", tenant_state="OH",
                                 radius_miles=30, db=db)
        assert rows, "44114 should be in the centroid file"
        assert all(r["rate_verified_on"] is None for r in rows)
        assert all(r["rate_source"] is None for r in rows)

    def test_the_suggestion_source_no_longer_collides(self, db):
        from app.services.county_geographic_service import build_suggestions

        rows = build_suggestions(tenant_zip="13021", tenant_state="NY",
                                 radius_miles=30, db=db)
        r = rows[0]
        assert r["suggested_by"] == "radius_lookup"
        assert r["rate_source"] != r["suggested_by"]

    def test_the_ui_marks_unverified_rates(self):
        page = (REPO / "frontend" / "src" / "pages" / "onboarding"
                / "tax-jurisdictions.tsx").read_text()
        assert "rate_verified_on" in page
        assert "Not verified against" in page

    def test_the_copy_promises_suggestion_not_supply(self):
        """⚠️ RULED: the tenant's own `tax_rates` are still what bills — six
        readers including the billing path, against one for suggestions. Copy
        saying "you supply nothing" would describe a system that does not exist
        yet."""
        page = (REPO / "frontend" / "src" / "pages" / "onboarding"
                / "tax-jurisdictions.tsx").read_text()
        assert "The rate you save here is what bills" in page
