"""RI-1 — three by-id lookups in report_intelligence_service that never asked
whose row it was. CHARACTERIZATION, written before the fix.

Every test tagged WRONGNESS passes against the CURRENT code and is flipped in
the same commit, with its prior body quoted in the flipped test's docstring.

WHAT IS WRONG. `get_commentary`, `get_preflight_result` and `override_preflight`
each filter on `id` alone. The routes take `current_user` and use it for
authentication but never for scoping, so any authenticated user of any tenant
can read another tenant's row by id:

  * `GET  /report-intelligence/commentary/{id}` — executive_summary,
    key_findings, trend_summary, forecast_note, attention_items. This is
    AI-written narrative about another company's financial position.
  * `GET  /report-intelligence/preflight/{id}` — audit pre-flight state,
    including who overrode a blocked audit and the reason they gave.
  * `POST /report-intelligence/preflight/{id}/override` — a cross-tenant WRITE.

WHY THIS IS BEING FIXED NOW RATHER THAN WITH A-2. The override is unreachable
today only by accident: `override_preflight` returns False unless the row is
`blocked`, and `run_preflight` cannot produce that status — `blocking` and
`warnings` are initialised empty and never appended to, so every run is
`passed`. A-2 makes pre-flight able to block. The moment it does, the write
becomes live. Fixing the scope AFTER A-2 would mean shipping the thing that
arms it first.

IDs are UUID4, so this is not trivially enumerable. That is obscurity, not a
control, and ids travel — in logs, in support tickets, in URLs.

Cleans up its own `ri1-` tenants (COMPANY-LITTER ratchet).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest

from app.database import SessionLocal
from app.models.company import Company
from app.models.report_intelligence import AuditPreflightResult, ReportCommentary
from app.services import report_intelligence_service as ri
from tests._cleanup import purge_companies_by_slug

_SLUG = "ri1-"


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
    sfx = uuid.uuid4().hex[:8]
    mine = Company(id=str(uuid.uuid4()), name=f"RI1 mine {sfx}",
                   slug=f"{_SLUG}mine-{sfx}", is_active=True, vertical="manufacturing")
    theirs = Company(id=str(uuid.uuid4()), name=f"RI1 theirs {sfx}",
                     slug=f"{_SLUG}theirs-{sfx}", is_active=True, vertical="manufacturing")
    s.add_all([mine, theirs]); s.flush()

    commentary = ReportCommentary(
        id=str(uuid.uuid4()), tenant_id=theirs.id, report_type="income_statement",
        period_start=date(2026, 1, 1), period_end=date(2026, 1, 31), status="complete",
        executive_summary="THEIR CONFIDENTIAL SUMMARY",
        key_findings=["their margin fell"], trend_summary="their trend",
        forecast_note="their forecast", attention_items=["their problem"],
        generated_at=datetime.now(timezone.utc),
    )
    preflight = AuditPreflightResult(
        id=str(uuid.uuid4()), tenant_id=theirs.id, status="blocked",
        blocking_issues=[{"code": "x", "message": "THEIR BLOCKING ISSUE"}],
        warning_issues=[], passed_checks=[],
    )
    s.add_all([commentary, preflight]); s.commit()

    yield {"s": s, "mine": mine.id, "theirs": theirs.id,
           "commentary": commentary.id, "preflight": preflight.id}
    s.rollback(); s.close()


# ── DELIBERATE PIN FLIPS ────────────────────────────────────────────────────


class TestForeignRowsAreInvisible:
    """The three characterizations this class replaces read, verbatim:

        def test_WRONGNESS_any_tenant_reads_any_commentary(self, env):
            got = ri.get_commentary(env["s"], env["commentary"])
            assert got["executive_summary"] == "THEIR CONFIDENTIAL SUMMARY"

        def test_WRONGNESS_any_tenant_reads_any_preflight(self, env):
            got = ri.get_preflight_result(env["s"], env["preflight"])
            assert got["blocking_issues"][0]["message"] == "THEIR BLOCKING ISSUE"

        def test_WRONGNESS_any_tenant_overrides_any_blocked_preflight(self, env):
            assert ri.override_preflight(env["s"], env["preflight"],
                                         "attacker-user-id", "because I said so") is True
            row = env["s"].get(AuditPreflightResult, env["preflight"])
            assert row.status == "passed"
            assert row.override_by == "attacker-user-id"

    All three passed. Each is now scoped by tenant at the service layer, which
    is where the fix belongs — a route-layer check would leave the next caller
    of the service unprotected.
    """

    def test_a_foreign_commentary_is_not_readable(self, env):
        assert ri.get_commentary(env["s"], env["commentary"], env["mine"]) is None

    def test_a_foreign_preflight_is_not_readable(self, env):
        assert ri.get_preflight_result(env["s"], env["preflight"], env["mine"]) is None

    def test_a_foreign_preflight_cannot_be_overridden(self, env):
        assert ri.override_preflight(env["s"], env["preflight"], "attacker-user-id",
                                     "because I said so", env["mine"]) is False
        row = env["s"].get(AuditPreflightResult, env["preflight"])
        assert row.status == "blocked", "the foreign row must be untouched"
        assert row.override_by is None
        assert row.override_reason is None

    def test_absent_and_foreign_are_indistinguishable(self, env):
        """No existence oracle. A caller outside the tenant must not be able to
        tell a real id from a made-up one — otherwise the 404 leaks which ids
        exist, which is most of what enumeration wants."""
        real_but_foreign = ri.get_preflight_result(env["s"], env["preflight"], env["mine"])
        never_existed = ri.get_preflight_result(env["s"], str(uuid.uuid4()), env["mine"])
        assert real_but_foreign is never_existed is None


class TestOwnRowsStillWork:
    """The scope must refuse the foreign row without breaking the real path —
    a fix that returns None for everybody would pass the class above."""

    def test_own_commentary_is_readable(self, env):
        got = ri.get_commentary(env["s"], env["commentary"], env["theirs"])
        assert got is not None
        assert got["executive_summary"] == "THEIR CONFIDENTIAL SUMMARY"

    def test_own_preflight_is_readable(self, env):
        got = ri.get_preflight_result(env["s"], env["preflight"], env["theirs"])
        assert got is not None
        assert got["blocking_issues"][0]["message"] == "THEIR BLOCKING ISSUE"

    def test_own_blocked_preflight_can_be_overridden(self, env):
        assert ri.override_preflight(env["s"], env["preflight"], "their-admin",
                                     "reviewed and accepted", env["theirs"]) is True
        row = env["s"].get(AuditPreflightResult, env["preflight"])
        assert row.status == "passed"
        assert row.override_by == "their-admin"
        assert row.override_reason == "reviewed and accepted"


class TestTheRoutesPassTheTenant:
    """The service is scoped, but the routes are what supply the tenant. If a
    route forgot the argument this would now be a TypeError rather than a silent
    leak — which is the point of making the parameter required — but a signature
    can be satisfied with the wrong value, so pin that it is company_id."""

    def test_every_call_site_passes_current_user_company_id(self):
        import inspect
        from app.api.routes import report_intelligence as routes
        src = inspect.getsource(routes)
        for call in ("get_commentary(db, commentary_id, current_user.company_id)",
                     "get_preflight_result(db, result_id, current_user.company_id)"):
            assert call in src, call
        assert "override_preflight(db, result_id, current_user.id, body.reason," in src
        assert "current_user.company_id)" in src
