"""The completeness scenario anchor, shared by the tests that need it.

⚠️ EXTRACTED BECAUSE TWO FILES NEEDED IT, AND TWO COPIES OF ONE FACT DRIFT.
`tests/test_completeness_review.py` anchors a whole scenario here;
`tests/test_completeness_declining.py` needs exactly one date, for
`my_obligations(as_of=...)`. Both are answering "when is this tenant old enough
to owe anything", and that question has one answer.
"""
from __future__ import annotations

from datetime import date, timedelta

from app.services.completeness import expectations as ex
from tests._tenant import TESTCO_ID

TENANT = TESTCO_ID

#: ⚠️ THESE DATES USED TO BE LITERALS, AND THE LITERALS WERE THE DEFECT.
#: `review()` owes nothing for a period before `_tenant_start`
#: (`app/services/completeness/review.py:216`) — the real business rule. The
#: scenario below was written when `testco` was months old, so every date sat
#: safely after the tenant began. A reseed makes the tenant hours old, every
#: expectation comes back `not_yet_due`, and eight tests fail for a reason that
#: has nothing to do with what they assert.
#:
#: So the anchor is DERIVED from the tenant's own `created_at`, and every date
#: below is an offset from it. The scenario keeps its shape and stops encoding
#: when the database happened to be seeded. Ruled 2026-09-23: fix the tests, do
#: not backdate the seed — backdating makes the fixture lie about when the
#: tenant started, to suit a test.
_ANCHOR: date | None = None


def _anchor() -> date:
    """The scenario's "today", far enough after the tenant began that every
    declared window is genuinely due.

    Self-sizing rather than a magic constant: it walks forward until the OLDEST
    period of EVERY declared cadence sits at or after the tenant's start. A
    hard-coded offset would silently rot the first time a cadence's window got
    longer.
    """
    global _ANCHOR
    if _ANCHOR is not None:
        return _ANCHOR
    from sqlalchemy import text as _t

    from app.database import SessionLocal

    s = SessionLocal()
    try:
        got = s.execute(
            _t("SELECT created_at FROM companies WHERE id = :t"), {"t": TENANT}
        ).scalar()
    finally:
        s.close()
    assert got is not None, (
        f"tenant {TENANT} does not exist — seed_staging has not run. "
        "These tests cannot anchor themselves without it."
    )
    began = got.date()
    cadences = {e.cadence for e in ex.VERTICAL["manufacturing"]}
    probe = began
    for _ in range(1000):
        probe += timedelta(days=1)
        if all(ex.periods_in_window(c, probe)[0][0] >= began for c in cadences):
            _ANCHOR = probe
            return _ANCHOR
    raise AssertionError(
        f"no anchor within 1000 days of {began} puts every cadence "
        f"{sorted(cadences)} past the tenant start"
    )


def D(offset: int = 0) -> date:
    """A scenario date, `offset` days from the anchor."""
    return _anchor() + timedelta(days=offset)

