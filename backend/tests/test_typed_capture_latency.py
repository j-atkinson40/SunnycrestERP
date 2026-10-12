"""The typed pane's extraction budget: 150 ms per re-extraction, by ruling.

⚠️ THIS IS A BLOCKING GATE AND IT MEASURES THE SERVICE SEAM, NOT THE FUNCTION.
`set_text` is what the route calls, and it is the whole cost the director waits
through: load the row, re-read every segment, resolve parties against the
database, write back. Timing `extract_text` alone would exclude the two database
round trips that bracket it.

⚠️ GROWING PREFIXES OF ONE SENTENCE, because that is what the pane actually sends.
Cost is per-segment, so a single fixed string measures one length and tells you
nothing about the shape of the curve. 42 prefixes of a 177-character order.

⚠️ THE FIRST CALL IN A FRESH PROCESS IS EXCLUDED, AND HERE IS THE NUMBER SO THE
EXCLUSION IS AUDITABLE RATHER THAN CONVENIENT. Measured 2026-10-12 on local dev:
the first call cost **225.6 ms** at 10 characters — the shortest text in the run —
while the longest text (174 characters) cost 24.2 ms. So the 225 ms is process
warm-up (SQLAlchemy statement compilation, vocabulary construction) and not a
function of text length; attributing it to extraction would be attributing it to
the wrong thing.

⚠️ IT IS STILL A REAL 226 ms THAT A DIRECTOR WAITS THROUGH ONCE PER PROCESS, and
that is recorded in the report rather than buried here. What this gate measures is
the per-keystroke cost, which is the one the 150 ms budget is about.
"""
from __future__ import annotations

import statistics
import time
import uuid

import pytest

from app.database import SessionLocal

#: The ruled budget, per re-extraction.
BUDGET_MS = 150.0

#: One order as a director types it, used as growing prefixes.
SENTENCE = (
    "start an order for Hopkins, Mary Smith, Continental 34, tent only, "
    "nameplate and vinyl, cross, years only, to St Mary's in Auburn, "
    "service at the church Thursday 10am, eta 11:30"
)


def _refuse_a_non_local_database() -> None:
    from urllib.parse import urlparse

    from app.config import settings

    host = (urlparse(settings.DATABASE_URL).hostname or "").lower()
    assert host in ("localhost", "127.0.0.1", "::1", ""), (
        f"this test writes; refusing to run against host {host!r}"
    )


@pytest.fixture(scope="module")
def timings():
    """Every prefix timed once, as (chars, ms), in typing order."""
    _refuse_a_non_local_database()
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User
    from app.services.capture import session_service

    db = SessionLocal()
    sp = db.begin_nested()
    try:
        cid = str(uuid.uuid4())
        db.add(Company(id=cid, name="Latency Co", slug=f"lat-{cid[:8]}"))
        db.flush()
        rid = str(uuid.uuid4())
        db.add(Role(id=rid, company_id=cid, name="Admin", slug="admin"))
        db.flush()
        uid = str(uuid.uuid4())
        db.add(User(
            id=uid, company_id=cid, email=f"{uid[:8]}@lat.example.com",
            hashed_password="x", first_name="L", last_name="C",
            role_id=rid, is_active=True,
        ))
        db.flush()
        row = session_service.start(db, company_id=cid, user_id=uid)

        out = []
        for n in range(10, len(SENTENCE) + 1, 4):
            t0 = time.perf_counter()
            session_service.set_text(
                db, row.id, company_id=cid, user_id=uid, text=SENTENCE[:n]
            )
            out.append((n, (time.perf_counter() - t0) * 1000.0))
        yield out
    finally:
        sp.rollback()
        db.rollback()
        db.close()


def test_the_sample_is_big_enough_to_mean_anything(timings):
    """⚠️ A POSITIVE CONTROL ON THE INSTRUMENT. A fixture that produced two samples
    would satisfy every percentile assertion below trivially, and a fixture that
    produced none would satisfy them vacuously. Read this before the results."""
    assert len(timings) >= 30, f"only {len(timings)} samples"
    assert all(ms > 0 for _, ms in timings), "a sample took no measurable time"


def test_every_warm_re_extraction_is_inside_the_budget(timings):
    """⚠️ EVERY ONE, NOT THE MEDIAN. The budget is per-keystroke, so a p50 inside it
    and a worst case outside it is a pane that stutters while someone types."""
    warm = timings[1:]
    over = [(n, round(ms, 1)) for n, ms in warm if ms > BUDGET_MS]
    assert not over, (
        f"{len(over)} of {len(warm)} re-extractions exceeded {BUDGET_MS} ms "
        f"(chars, ms): {over}"
    )


def test_the_cost_does_not_run_away_with_LENGTH(timings):
    """⚠️ THE CURVE, NOT THE POINT. Re-reading the whole text on every pause is
    quadratic in principle — n keystrokes each re-reading n characters — so the
    thing worth pinning is that the LONGEST text is still cheap. A gate on the
    median would pass while the end of a long order crawled."""
    warm = timings[1:]
    longest_n, longest_ms = max(warm, key=lambda x: x[0])
    assert longest_ms <= BUDGET_MS, (
        f"the longest text ({longest_n} chars) took {longest_ms:.1f} ms"
    )
    # ⚠️ 6x THE MEDIAN IS THE CEILING, AND IT IS DELIBERATELY LOOSE. The point is to
    # catch a change that makes cost superlinear in text length, not to pin today's
    # ratio — measured at ~1.6x (15.2 ms median, 24.2 ms longest) on local dev.
    median_ms = statistics.median([ms for _, ms in warm])
    assert longest_ms <= median_ms * 6, (
        f"the longest text cost {longest_ms / median_ms:.1f}x the median "
        f"({longest_ms:.1f} ms vs {median_ms:.1f} ms) — cost is running away "
        f"with length"
    )
