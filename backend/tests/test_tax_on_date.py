"""TAX-5 — the resolver asks a date, and the date it asks about is the document's.

⚠️ THIS WAS NOT A HAZARD TO DESIGN AGAINST. IT WAS ALREADY PRODUCING WRONG
ANSWERS. `resolve_line_tax` has taken `on_date` since the sales-tax arc, and it
defaulted to `today()`. **No caller has ever passed it** — `grep -rn "on_date="`
over `app/` and `scripts/` returned the parameter declaration and nothing else.

`on` decides CERTIFICATE VALIDITY (`_find_valid_certificate`,
`TaxCertificate.is_valid_on`). So with all five callers silently taking today, a
resale certificate that expired last month still exempted a document backdated
to before its expiry — and a certificate not yet in force exempted nothing on a
document dated after it began. Plausibly, and with no test that would notice.

Required rather than defaulted, because the failure mode is FORGETTING and a
required argument makes forgetting impossible rather than detectable. Same
reasoning as `.get(key, 0)` returning a number for a key that is absent.

⚠️ AND `datetime` IS A SUBCLASS OF `date`, WHICH MAKES THE TYPE TRAP INVISIBLE
TWICE. The annotation says `date`; a `datetime` satisfies it, and
`isinstance(a_datetime, date)` is True — so neither the hint nor a defensive
isinstance check would catch a caller passing a timestamp. What catches it is
Python refusing the comparison at the point of use:

    datetime.now() < date.today()
    TypeError: '<' not supported between instances of 'datetime.datetime'
               and 'datetime.date'

Both quote callers hold a `datetime` (`quotes.quote_date`,
`QuoteCreate.quote_date`), so every real caller would have raised. Coerced once
at the boundary rather than at four call sites.

⚠️ IT DOES NOT GOVERN THE RATE, DELIBERATELY. `get_jurisdiction_for_order` still
takes no date. `platform_tax_rates` carries ONE edition — every row
`effective_from = 2025-03-01` — so threading the date into the rate lookup would
change no answer for any document that exists while implying the table knew
better. The certificate date and the rate date are different problems that
happened to share a parameter; this fixes the one that is live and wrong.
"""
from __future__ import annotations

import ast
import inspect
import pathlib
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from tests._source import code_only
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture

TENANT = TESTCO_ID
BACKEND = pathlib.Path(__file__).resolve().parent.parent

canonical_tenant = make_canonical_tenant_fixture(
    child_tables=("tax_certificates", "customers", "tax_jurisdictions", "tax_rates"),
)

LINES = [{"product_id": None, "amount": Decimal("100.00"), "description": "x"}]


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
def customer(db):
    from app.models.customer import Customer

    c = Customer(id=str(uuid.uuid4()), company_id=TENANT, name="Cert Co",
                 zip_code="13021")
    db.add(c)
    db.flush()
    return c


def _cert(db, customer_id, *, valid_from=None, valid_through=None):
    from app.models.tax_filing import TaxCertificate

    c = TaxCertificate(
        id=str(uuid.uuid4()), company_id=TENANT, customer_id=customer_id,
        cert_type="resale", cert_number="R-1",
        valid_from=valid_from, valid_through=valid_through, is_active=True,
    )
    db.add(c)
    db.flush()
    return c


class TestTheDateDecidesCertificateValidity:
    """⚠️ THE DEFECT, DEMONSTRATED. These two cases differ ONLY in the date
    passed. Under the old default both took today and both got the same answer —
    which is how an expired certificate went on exempting backdated work."""

    def test_an_expired_certificate_does_not_exempt_a_later_document(self, db, customer):
        from app.services.tax_service import resolve_line_tax

        _cert(db, customer.id, valid_from=date(2020, 1, 1),
              valid_through=date(2020, 12, 31))
        res = resolve_line_tax(db, TENANT, lines=LINES, customer_id=customer.id,
                               on_date=date(2026, 6, 1))
        assert res.source != "customer_certificate", (
            "a certificate that expired in 2020 exempted a 2026 document"
        )

    def test_the_same_certificate_DOES_exempt_a_document_inside_its_validity(self, db, customer):
        """The other arm. Without it, the test above would be satisfied by a
        certificate lookup that never matches anything."""
        from app.services.tax_service import resolve_line_tax

        _cert(db, customer.id, valid_from=date(2020, 1, 1),
              valid_through=date(2020, 12, 31))
        res = resolve_line_tax(db, TENANT, lines=LINES, customer_id=customer.id,
                               on_date=date(2020, 6, 1))
        assert res.source == "customer_certificate"
        assert res.tax_amount == Decimal("0.00")

    def test_a_certificate_not_yet_in_force_does_not_exempt(self, db, customer):
        from app.services.tax_service import resolve_line_tax

        future = date.today() + timedelta(days=365)
        _cert(db, customer.id, valid_from=future, valid_through=None)
        res = resolve_line_tax(db, TENANT, lines=LINES, customer_id=customer.id,
                               on_date=date.today())
        assert res.source != "customer_certificate"

    def test_an_open_dated_certificate_exempts_whenever(self, db, customer):
        """`valid_through` NULL never lapses — a real answer, not a missing one."""
        from app.services.tax_service import resolve_line_tax

        _cert(db, customer.id, valid_from=date(2020, 1, 1), valid_through=None)
        for when in (date(2021, 1, 1), date(2026, 6, 1)):
            res = resolve_line_tax(db, TENANT, lines=LINES,
                                   customer_id=customer.id, on_date=when)
            assert res.source == "customer_certificate", when


class TestTheParameterIsRequired:
    def test_omitting_it_raises(self, db, customer):
        """⚠️ REQUIRED, NOT DEFAULTED. The failure mode is forgetting, and five
        callers forgot for the life of the parameter. A required argument makes
        that impossible rather than detectable."""
        from app.services.tax_service import resolve_line_tax

        with pytest.raises(TypeError, match="on_date"):
            resolve_line_tax(db, TENANT, lines=LINES, customer_id=customer.id)

    def test_it_has_no_default_in_the_signature(self):
        from app.services.tax_service import resolve_line_tax

        param = inspect.signature(resolve_line_tax).parameters["on_date"]
        assert param.default is inspect.Parameter.empty, (
            "on_date acquired a default — the condition this change removed"
        )
        assert param.kind is inspect.Parameter.KEYWORD_ONLY

    def test_every_call_site_passes_it(self):
        """⚠️ DERIVED FROM THE CALL SITES, NOT A HARDCODED LIST. A ratchet that
        names the files it knows about goes stale the moment someone adds a
        caller — the too-narrow-matcher failure this arc hit twice. Parsed with
        `ast` so a call inside a comment or string cannot satisfy it."""
        offenders = []
        for path in sorted((BACKEND / "app").rglob("*.py")):
            try:
                tree = ast.parse(path.read_text())
            except SyntaxError:
                # ⚠️ `app/services/onboarding/unified_import_service.py` does not
                # parse AT HEAD and has not since 948acb4f — pre-existing, not
                # this change's doing, and reported separately. Skipped rather
                # than allowed to hide a genuine offender behind a crash.
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                if name == "resolve_line_tax" and "on_date" not in {
                    k.arg for k in node.keywords
                }:
                    offenders.append(f"{path.relative_to(BACKEND)}:{node.lineno}")
        assert not offenders, (
            "these call resolve_line_tax without a date, so certificate "
            f"validity is judged against today: {offenders}"
        )


class TestTheDatetimeTrap:
    """⚠️ `datetime` IS A `date` SUBCLASS. The annotation accepts it, isinstance
    accepts it, and the comparison inside `is_valid_on` refuses it. Both quote
    callers hold a datetime, so this is the shape every real caller has."""

    @pytest.mark.parametrize("supplied", [
        date(2020, 6, 1),
        datetime(2020, 6, 1, 10, 30),
        datetime(2020, 6, 1, 10, 30, tzinfo=timezone.utc),
    ])
    def test_a_datetime_is_accepted_and_compared_correctly(self, db, customer, supplied):
        from app.services.tax_service import resolve_line_tax

        _cert(db, customer.id, valid_from=date(2020, 1, 1),
              valid_through=date(2020, 12, 31))
        res = resolve_line_tax(db, TENANT, lines=LINES,
                               customer_id=customer.id, on_date=supplied)
        assert res.source == "customer_certificate", (
            f"{type(supplied).__name__} did not resolve the same as its date"
        )

    def test_the_coercion_is_at_the_boundary_not_the_call_sites(self):
        """One rule in one place. Four call sites each remembering to call
        `.date()` is four chances to forget."""
        src = code_only((BACKEND / "app" / "services" / "tax_service.py").read_text())
        body = src.split("def resolve_line_tax")[1].split("\ndef ")[0]
        assert "isinstance(on_date, datetime)" in body


class TestTheUncalledWrapperIsGone:
    """⚠️ `resolve_quote_tax` WRAPPED `resolve_line_tax` AND HAD NO CALLERS. The
    only reference anywhere was a comment asserting that "both faces resolve
    through" it, which had not been true for some time — the comment is what
    kept it looking alive. Threading a required date through a function nothing
    invokes is what this arc deleted a second tax engine over."""

    def test_it_is_deleted(self):
        src = code_only((BACKEND / "app" / "services" / "tax_service.py").read_text())
        assert "def resolve_quote_tax" not in src

    def test_nothing_references_it(self):
        hits = []
        for path in sorted((BACKEND / "app").rglob("*.py")):
            if "resolve_quote_tax" in code_only(path.read_text()):
                hits.append(str(path.relative_to(BACKEND)))
        assert not hits, f"resolve_quote_tax is referenced by: {hits}"


class TestTheRateIsStillNotDateAware:
    """⚠️ PINNED DELIBERATELY, SO THE SPLIT STAYS VISIBLE. The rate lookup takes
    no date because `platform_tax_rates` holds ONE edition — every row
    `effective_from = 2025-03-01`. Threading a date through it would change no
    answer for any document that exists while implying the table knew better.

    When real rate history is seeded, this test should fail and be replaced —
    that failure IS the signal that the second half of TAX-5 has become
    worth doing."""

    def test_get_jurisdiction_for_order_takes_no_date(self):
        from app.services.tax_service import get_jurisdiction_for_order

        params = set(inspect.signature(get_jurisdiction_for_order).parameters)
        assert "on_date" not in params and "as_of" not in params

    def test_the_rate_table_still_has_one_edition(self, db):
        """The fact that makes the above correct rather than lazy."""
        from sqlalchemy import text

        rows = db.execute(text(
            "SELECT count(DISTINCT effective_from) FROM platform_tax_rates"
        )).scalar()
        assert rows <= 1, (
            "platform_tax_rates now carries more than one edition — date-aware "
            "rate resolution has become meaningful and this pin should be "
            "replaced rather than relaxed"
        )
