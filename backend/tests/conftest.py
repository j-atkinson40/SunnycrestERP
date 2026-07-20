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
