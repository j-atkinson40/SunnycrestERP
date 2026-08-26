"""HC-1 A-2 — a check that cannot run must not produce a green.

WHY THIS EXISTS, established by EXECUTION before the fix rather than by reading:

  1. Forcing the reconciliation check to raise produced output BYTE-IDENTICAL to
     a healthy tenant — three greens, including "All accounts reconciled within
     35 days". The absence of a finding became a positive claim about a
     condition nobody had checked.
  2. The tax checks ALREADY emitted a `*_check_failed` finding on failure, and
     the green fired anyway, in the same payload, contradicting it. The green
     tested `f["code"] == "missing_cert"`; a failed check emits
     `missing_cert_check_failed`. Different string, so "no bad finding exists"
     held.

THE GENERAL SHAPE: a green gated on the ABSENCE OF A SPECIFIC FAILURE CODE is
satisfied by the check dying. The structural fix is to gate on the check having
RUN. These tests exist so the next green cannot be gated on a string instead.

One break test per check, five checks. Each asserts three things: the failure is
announced, that check's green is gone, and the OTHER greens survive — because a
fix that suppressed every green on any failure would pass the first two.

Cleans up its own `hc1-` tenants (COMPANY-LITTER ratchet).
"""
from __future__ import annotations

import uuid

import pytest

from app.database import SessionLocal
from app.models.company import Company
from app.services import financial_report_service as frs
from tests._cleanup import purge_companies_by_slug

_SLUG = "hc1-"


class _Exploding:
    """Raises on any attribute access. NOT a MagicMock — a MagicMock answers
    every attribute, so a check that started reading a different attribute would
    keep passing against a mock that invented it."""

    def __getattr__(self, name):
        raise AttributeError(f"simulated schema drift: no attribute {name!r}")


@pytest.fixture(autouse=True)
def _purge():
    yield
    s = SessionLocal()
    try:
        purge_companies_by_slug(s, f"{_SLUG}%")
    finally:
        s.close()


@pytest.fixture
def env():
    s = SessionLocal()
    co = Company(id=str(uuid.uuid4()), name="HC1", slug=f"{_SLUG}{uuid.uuid4().hex[:8]}",
                 is_active=True, vertical="manufacturing")
    s.add(co); s.commit()
    yield {"s": s, "co": co.id}
    s.rollback(); s.close()


def _codes(result) -> set[str]:
    return {f["code"] for f in result["findings"]}


def _greens(result) -> set[str]:
    return {f["code"] for f in result["findings"] if f["severity"] == "green"}


# (check name, monkeypatch target, the green it may no longer claim)
_CHECKS = [
    ("reconciliation",      "app.models.financial_account.FinancialAccount", "recon_current"),
    ("stale_drafts",        "app.models.journal_entry.JournalEntry",         "drafts_current"),
    ("missing_cert",        "app.models.tax_filing.TaxCertificate",          "exemptions_valid"),
    ("expired_exemptions",  "app.models.tax_filing.TaxCertificate",          "exemptions_valid"),
    ("overdue_90",          "app.services.financial_report_service.Invoice", "ar_current"),
]


class TestABaselineTenantIsAllGreen:
    """Establishes what "healthy" looks like, so the break tests are measured
    against something rather than against nothing."""

    def test_every_check_runs_and_every_green_appears(self, env):
        r = frs.run_health_check(env["s"], env["co"])
        assert _greens(r) == {"recon_current", "drafts_current", "exemptions_valid", "ar_current"}
        assert not [f for f in r["findings"] if f["code"].endswith("_check_failed")]
        assert r["overall_score"] == "green"


class TestADeadCheckCannotClaimGreen:

    @pytest.mark.parametrize("name,target,green", _CHECKS, ids=[c[0] for c in _CHECKS])
    def test_the_failure_is_announced(self, env, monkeypatch, name, target, green):
        monkeypatch.setattr(target, _Exploding())
        r = frs.run_health_check(env["s"], env["co"])
        assert f"{name}_check_failed" in _codes(r), \
            f"{name} died and said nothing — that is the defect this file exists for"

    @pytest.mark.parametrize("name,target,green", _CHECKS, ids=[c[0] for c in _CHECKS])
    def test_its_green_is_gone(self, env, monkeypatch, name, target, green):
        monkeypatch.setattr(target, _Exploding())
        r = frs.run_health_check(env["s"], env["co"])
        assert green not in _greens(r), (
            f"{name} could not run, yet the report still claims {green!r}. "
            "A green must mean CHECKED AND CLEAN, never merely 'no bad finding'."
        )

    @pytest.mark.parametrize("name,target,green", _CHECKS, ids=[c[0] for c in _CHECKS])
    def test_the_other_greens_survive(self, env, monkeypatch, name, target, green):
        """Targeted, not blanket. A fix that dropped every green whenever
        anything failed would satisfy the two tests above and would make the
        report useless."""
        monkeypatch.setattr(target, _Exploding())
        r = frs.run_health_check(env["s"], env["co"])
        others = {"recon_current", "drafts_current", "exemptions_valid", "ar_current"} - {green}
        # the tax pair share one green, so breaking either removes only that one
        assert others <= _greens(r), f"breaking {name} collaterally removed {others - _greens(r)}"

    def test_a_dead_check_is_DISTINGUISHABLE_from_a_healthy_one(self, env, monkeypatch):
        """The original defect in its purest form: before the fix, these two
        produced identical output."""
        healthy = frs.run_health_check(env["s"], env["co"])
        monkeypatch.setattr("app.models.financial_account.FinancialAccount", _Exploding())
        broken = frs.run_health_check(env["s"], env["co"])
        assert _codes(healthy) != _codes(broken)
        assert healthy["overall_score"] != broken["overall_score"]


class TestTheHalfFixRegression:
    """The tax checks emitted `*_check_failed` BEFORE this arc and the green
    fired anyway. Pinned separately because it is the specific bug, not the
    general shape — a fix could close the general case and reintroduce this one
    by renaming a code."""

    def test_a_failed_tax_check_does_not_also_certify_the_certificates(self, env, monkeypatch):
        monkeypatch.setattr("app.models.tax_filing.TaxCertificate", _Exploding())
        r = frs.run_health_check(env["s"], env["co"])
        assert "missing_cert_check_failed" in _codes(r)
        assert "expired_exemptions_check_failed" in _codes(r)
        assert "exemptions_valid" not in _codes(r), (
            "the report said the condition is unknown AND that all certificates "
            "are valid, in the same payload"
        )

    def test_the_green_does_not_depend_on_a_failure_code_STRING(self, env):
        """The half-fix failed because the green tested for `missing_cert` while
        failure produced `missing_cert_check_failed`. Renaming the failure code
        must not resurrect the green, so the gate is on `ran`, not on strings."""
        import inspect
        src = inspect.getsource(frs.run_health_check)
        assert '"missing_cert" in ran' in src or '{"missing_cert", "expired_exemptions"} <= ran' in src, \
            "the tax green must gate on the checks having RUN"


class TestOneFailureDoesNotTakeTheReportDown:
    """`overdue_90` was the only unguarded check: an exception took the whole
    function with it, hiding four working checks behind one broken query."""

    def test_the_report_still_returns(self, env, monkeypatch):
        monkeypatch.setattr("app.services.financial_report_service.Invoice", _Exploding())
        r = frs.run_health_check(env["s"], env["co"])
        assert r["findings"], "the report must survive one check failing"
        assert "overdue_90_check_failed" in _codes(r)
