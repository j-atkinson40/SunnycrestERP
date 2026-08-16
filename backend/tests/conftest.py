"""Shared test plumbing.

THE COMPANY-LITTER TRIPWIRE (map-performance arc, 2026-07-20 — the
class killer). Test suites without teardown left 515 synthetic
companies on dev; their nightly fan-out and months of churn bloated the
database to 7.3 GB and slowed every map page. The generalized purge
removed them once — this tripwire keeps the class dead:

The whole pytest session FAILS if it ends with more `companies` rows
than it started with. A suite that creates a company must tear it down
(module-fixture teardown runs even when its tests fail — see the S&O
pin suites for the pattern). Set BRIDGEABLE_ALLOW_COMPANY_LITTER=1 to
bypass deliberately (e.g. a seed-authoring session that MEANS to keep
rows).

RATCHET CONVENTION (Accounting Substrate Arc, 2026-07-29). This is a
ratchet, not a courtesy: the net company count per session can only
stay flat or SHRINK. Every NEW test file that creates a company MUST
tear its own companies down in a module-scoped teardown fixture (the
`_cleanup_test_workflows`-style pattern in
test_workflow_scheduler_pair_isolation.py). "The other files already
leak" is never a licence to add another leaker — the debt has a
direction (down), and the offender set is meant to be enumerated and
drained (routed to S-6 test-hygiene), not grown. Its signal is only as
good as the baseline; pre-existing leakers keep it red, which is
exactly why new files must not add to the pile.

⚠️ CORRECTED 2026-08-16 — this said "CI's backend job runs imports +
migration-heads + `alembic upgrade` only — it does NOT run pytest, so
this tripwire is a LOCAL guardrail." That is FALSE and was believed
while acting on it. `.github/workflows/ci.yml` runs
`python -m pytest $(… ci_gate.txt …)` against a fresh Postgres, which
is how three seed-dependent tests in test_completeness_review.py were
finally caught. The gate is not local-only, and a bare-database axis
runs on every push.

⚠️ AND THE BARE AXIS IS NOT OPTIONAL COVERAGE — see tests/_tenant.py.
Passing on a bare database is not evidence a test is independent of
seeded state; it is evidence that THAT PATH did not need it. A file can
be nine-tenths green on a fresh database while resting entirely on a row
nobody creates, because read paths tolerate a missing tenant and write
paths do not.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import text


def _company_count() -> int | None:
    try:
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            return db.execute(text("SELECT count(*) FROM companies")).scalar()
        finally:
            db.close()
    except Exception:
        return None  # no DB in this run — the tripwire stands down


@pytest.fixture(scope="session", autouse=True)
def _company_litter_tripwire():
    before = _company_count()
    yield
    if before is None or os.environ.get("BRIDGEABLE_ALLOW_COMPANY_LITTER"):
        return
    after = _company_count()
    if after is not None and after > before:
        pytest.fail(
            f"COMPANY LITTER: the test session started with {before} "
            f"companies and ended with {after} — {after - before} row(s) "
            "were created without teardown. This is the class that bloated "
            "dev to 7.3 GB. Add teardown to the offending fixture (see "
            "tests/test_so_class_killers.py's world fixture for the "
            "pattern), or set BRIDGEABLE_ALLOW_COMPANY_LITTER=1 if the "
            "rows are deliberate.",
            pytrace=False,
        )
