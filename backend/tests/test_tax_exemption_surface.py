"""TAX-3 — the second tax engine is gone, and the checks can report failure.

⚠️ TWO ENGINES ANSWERED "IS THIS TAXABLE" AND THEY DISAGREED IN BOTH DIRECTIONS.
`tax_service.resolve_line_tax` fails CLOSED — an exemption flag without a
backing certificate resolves TAXABLE with the gap listed. The deleted
`tax.py::_resolve_line_tax` would have failed OPEN, exempting on
`customers.tax_status == "exempt"` alone and rendering the reason
`"Customer exempt — no certificate"` onto an invoice. On an address it could not
resolve, it also fell back to the tenant's DEFAULT rate — Cayuga's 8% on a
delivery anywhere — where the surviving engine returns 0.00 marked unresolved.

⚠️ IT NEVER RAN, AND THE REASON IT NEVER RAN IS THE REAL DEFECT.
`s3a4b5c6d7e8_add_tax_system.py` added `tax_status`, `exemption_certificate`,
`exemption_expiry` and `exemption_verified` to the `customers` TABLE. The
`Customer` MODEL was never updated. So every consumer of those columns raised
`AttributeError` — five of them — and three swallowed it:

  - `financial_report_service` missing_cert (amber)     → "finding silently absent"
  - `financial_report_service` expired_exemptions (RED) → "finding silently absent"
  - `tax-settings.tsx` Exemptions tab                   → `.catch(() => {})`

Two tax-compliance alarms, one of them red, that had never been able to fire —
rendering exactly as they would if they had run and found nothing. Measured when
found: no customer on any tenant was exempt, so both would legitimately have
reported zero. **That is luck, not correctness.**

⚠️ AND THE CHEAP FIX WOULD HAVE BEEN THE WRONG ONE. Mapping the columns to stop
the 500s would have turned unreachable code into REACHABLE WRONG CODE — the
fail-open engine, live. Deletion is why that is now impossible rather than
merely unlikely.

Pure where possible; the DB tests use the canonical tenant fixture.
"""
from __future__ import annotations

import pathlib
import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import text

from tests._source import code_only
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture

TENANT = TESTCO_ID
BACKEND = pathlib.Path(__file__).resolve().parent.parent

# ⚠️ `audit_health_checks` IS HERE BECAUSE `run_health_check` COMMITS. The
# report writes a row per run and that row OUTLIVES this file's rollback, so the
# `db` fixture is not sufficient teardown for the tests that exercise it. Caught
# by the session litter tripwire on the bare axis, presenting as an FK violation
# blocking the company DELETE — the same shape as `generate_insight` in
# `test_zip_alarm.py`. A service under test that commits needs its table swept.
canonical_tenant = make_canonical_tenant_fixture(
    child_tables=("audit_health_checks", "tax_certificates", "customers"),
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


def _customer(db) -> str:
    cid = str(uuid.uuid4())
    db.execute(
        text("INSERT INTO customers (id, company_id, name, is_active, created_at, updated_at)"
             " VALUES (:i, :c, :n, true, now(), now())"),
        {"i": cid, "c": TENANT, "n": f"Cert Fixture {cid[:8]}"},
    )
    db.flush()
    return cid


def _cert(db, customer_id, *, valid_through=None, cert_number="R-1", is_active=True):
    cid = str(uuid.uuid4())
    db.execute(
        text("INSERT INTO tax_certificates"
             " (id, company_id, customer_id, cert_type, cert_number, valid_through,"
             "  is_active, created_at)"
             " VALUES (:i, :co, :cu, 'resale', :n, :v, :a, now())"),
        {"i": cid, "co": TENANT, "cu": customer_id, "n": cert_number,
         "v": valid_through, "a": is_active},
    )
    db.flush()
    return cid


class TestTheSecondEngineIsGone:
    """⚠️ A RATCHET, NOT A ONE-TIME ASSERTION. The failure mode is that someone
    reintroduces the fail-open branch — or 'fixes' the AttributeError by mapping
    the columns, which would activate it. Both are caught here."""

    def test_the_fail_open_engine_and_its_endpoints_are_deleted(self):
        src = code_only((BACKEND / "app" / "api" / "routes" / "tax.py").read_text())
        for gone in ("_resolve_line_tax", "_resolve_jurisdiction",
                     "resolve-line", "resolve-invoice",
                     "ResolveLineRequest", "ResolveInvoiceRequest"):
            assert gone not in src, f"{gone!r} is back in tax.py"

    def test_the_fail_open_reason_string_exists_nowhere(self):
        """The specific words that would have gone onto an invoice asserting an
        exemption with nothing behind it."""
        hits = []
        for p in (BACKEND / "app").rglob("*.py"):
            if "no certificate" in code_only(p.read_text()):
                hits.append(str(p.relative_to(BACKEND)))
        assert not hits, f"the fail-open exemption wording is live in: {hits}"

    def test_the_endpoints_are_not_mounted(self):
        from app.main import app

        paths = [getattr(r, "path", "") for r in app.routes]
        assert not [p for p in paths if "resolve-line" in p or "resolve-invoice" in p]


class TestNoCodeReadsAnUnmappedColumn:
    """⚠️ THE GENERAL FORM OF THE BUG, AND THE ONLY TEST THAT WOULD HAVE CAUGHT
    IT BEFORE IT SHIPPED. The specific defect was four `customers` columns in
    the database and absent from the ORM. The CLASS of defect is any column that
    exists in one and not the other, read as `Customer.<name>` — which raises
    AttributeError at query-build time, i.e. before any SQL runs, i.e. silently
    if the caller catches broadly.

    Derived from the live schema rather than a hardcoded list, so a future
    migration that adds a column without mapping it is caught by this test on
    the day some code first reads it.

    ⚠️ THE FIRST VERSION OF THIS TEST MATCHED ONLY `Customer.<col>` AND
    `customer.<col>` AND WAS TOO NARROW TO CATCH ITS OWN BUG. Reintroducing the
    defect through a local named `cust` — which is what `tax_service.py`
    actually calls it — left the test green. It now matches the attribute on ANY
    receiver, because the receiver's variable name is not the thing that makes
    the access wrong.
    """

    def test_no_module_references_an_unmapped_customer_column(self, db):
        from app.models.customer import Customer

        mapped = set(Customer.__mapper__.columns.keys())
        in_db = {
            r[0] for r in db.execute(text(
                "SELECT column_name FROM information_schema.columns"
                " WHERE table_name = 'customers'"
            )).fetchall()
        }
        unmapped = sorted(in_db - mapped)
        assert unmapped, (
            "expected some unmapped columns to exist — if this is now empty the "
            "test is no longer proving anything and should be revisited"
        )

        import re

        # Attribute access on ANY receiver. These names are specific enough to
        # the customers table that a match elsewhere is worth looking at anyway;
        # if a genuine collision ever appears, narrow it by receiver TYPE, never
        # by variable name.
        patterns = {col: re.compile(rf"\.{re.escape(col)}\b") for col in unmapped}
        offenders = []
        for p in (BACKEND / "app").rglob("*.py"):
            src = code_only(p.read_text())
            for col, pat in patterns.items():
                for line_no, line in enumerate(src.splitlines(), 1):
                    if pat.search(line):
                        offenders.append(
                            f"{p.relative_to(BACKEND)}:{line_no} reads .{col} — "
                            f"{line.strip()[:70]}"
                        )
        assert not offenders, (
            "these read `customers` columns that exist in the DATABASE but are "
            "NOT mapped on the ORM model — every one raises AttributeError "
            "before any SQL runs:\n  " + "\n  ".join(offenders)
        )


class TestTheExemptionsEndpointReadsCertificates:
    def test_it_returns_expiry_status_from_tax_certificates(self, db):
        from app.api.routes.tax import list_exemptions

        cust = _customer(db)
        _cert(db, cust, valid_through=date.today() - timedelta(days=1), cert_number="EXPIRED-1")
        _cert(db, cust, valid_through=date.today() + timedelta(days=10), cert_number="SOON-1")
        _cert(db, cust, valid_through=None, cert_number=None)

        user = type("U", (), {"company_id": TENANT})()
        rows = list_exemptions(status=None, current_user=user, db=db)
        by_num = {r["cert_number"]: r for r in rows}

        assert by_num["EXPIRED-1"]["is_expired"] is True
        assert by_num["SOON-1"]["is_expiring"] is True
        assert by_num["SOON-1"]["is_expired"] is False
        # ⚠️ An open-dated certificate NEVER expires. Reporting it as expiring
        # would send an operator chasing a renewal that does not exist.
        open_dated = by_num[None]
        assert open_dated["is_expired"] is False and open_dated["is_expiring"] is False
        assert open_dated["missing_cert"] is True
        assert open_dated["valid_through"] is None

    def test_an_inactive_certificate_is_not_reported(self, db):
        from app.api.routes.tax import list_exemptions

        cust = _customer(db)
        _cert(db, cust, valid_through=date.today() - timedelta(days=5),
              cert_number="REVOKED-1", is_active=False)
        user = type("U", (), {"company_id": TENANT})()
        rows = list_exemptions(status=None, current_user=user, db=db)
        assert "REVOKED-1" not in {r["cert_number"] for r in rows}


class TestDidNotRunIsNotFoundNothing:
    """⚠️ THE WIRING TEST, AND THE WHOLE POINT OF THE CHANGE. The old code
    caught a raising compliance check into a bare `except Exception` and
    appended no finding — so a check that COULD NOT RUN produced a report
    identical to a check that ran and found nothing. The distinction is the
    fiduciary one: 'no expired certificates' and 'we could not tell' are
    different answers to a question the state eventually asks."""

    def test_a_failing_check_reports_that_it_failed(self, db, monkeypatch):
        from app.services import financial_report_service as frs

        real_query = db.query

        def exploding_query(*args, **kwargs):
            # Break ONLY the certificate counts, the way an unmapped column
            # did — leaving every other health check working, so the assertion
            # is about this check and not about a broken session.
            rendered = " ".join(str(a) for a in args)
            if "tax_certificates" in rendered or "TaxCertificate" in rendered:
                raise AttributeError("simulated: type object 'TaxCertificate' has no attribute 'x'")
            return real_query(*args, **kwargs)

        monkeypatch.setattr(db, "query", exploding_query)
        result = frs.run_health_check(db, TENANT)

        codes = {f["code"] for f in result["findings"]}
        assert "missing_cert_check_failed" in codes, (
            "a compliance check raised and the report did not say so — which is "
            "the exact behaviour this change removed"
        )
        assert "expired_exemptions_check_failed" in codes
        failed = next(f for f in result["findings"] if f["code"] == "expired_exemptions_check_failed")
        assert "NOT a clean result" in failed["message"]

    def test_a_working_check_that_finds_nothing_reports_nothing(self, db):
        """The other half of the distinction — silence is still correct when the
        check actually ran. Without this, the test above could be satisfied by a
        finding that fires unconditionally."""
        from app.services import financial_report_service as frs

        result = frs.run_health_check(db, TENANT)
        codes = {f["code"] for f in result["findings"]}
        assert "missing_cert_check_failed" not in codes
        assert "expired_exemptions_check_failed" not in codes

    def test_an_expired_certificate_actually_raises_the_red_finding(self, db):
        """And the repointed check reads real data — otherwise 'it did not fail'
        would be satisfied by a check that returns zero forever."""
        from app.services import financial_report_service as frs

        cust = _customer(db)
        _cert(db, cust, valid_through=date.today() - timedelta(days=1), cert_number="OLD-1")
        db.flush()

        result = frs.run_health_check(db, TENANT)
        expired = [f for f in result["findings"] if f["code"] == "expired_exemptions"]
        assert expired, "an expired certificate exists and the red finding did not fire"
        assert expired[0]["severity"] == "red"
