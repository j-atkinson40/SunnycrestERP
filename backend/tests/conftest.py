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


# ── litter the company tripwire cannot see ───────────────────────────────
#
# ⚠️ THE COMPANY TRIPWIRE WATCHES ONE TABLE, AND TWO CLASSES ESCAPE IT.
# Measured 2026-09-14 on the development database:
#
#   55,013 tenant_health_scores rows whose owning company NO LONGER EXISTS.
#          The table has NO FOREIGN KEY on tenant_id, so nothing cascaded and
#          nothing complained. It is the ONLY table of 391 carrying a
#          company/tenant column that holds orphans — the FK cascades and
#          purge_companies_by_slug handle the other 390.
#
#    1,960 workflows with company_id IS NULL and an id not declared in
#          app/data/default_workflows.py. Global rows belong to no tenant, so
#          deleting a company never reaches them.
#
# ⚠️ A DELTA, NOT A CEILING, AND THE REASON IS NOT STYLE. A ceiling needs the
# right number. The right number here is zero, but only AFTER
# scripts/purge_test_litter.py has been run — and that is a write against a
# shared database that James runs, not this suite. A delta detects accumulation
# at any absolute level, so it works today at 55,013 and tomorrow at 0. Once the
# purge has run, a ceiling of 0 becomes available and is strictly stronger; this
# should be revisited then.


#: ⚠️ A DELTA CEILING THAT MAY ONLY SHRINK — NOT A LICENCE.
#:
#: A STRICT delta (ceiling 0) is the destination and is RED TODAY: one full-tree
#: run leaks +34 global workflows and +1,364 orphaned health scores. Landing that
#: red would install a permanently-failing check, and CLAUDE.md is explicit that
#: an already-red check cannot report a new failure — it conceals the next
#: regression in its own noise. So the direction is enforced instead: the leak
#: per run may fall and may not rise.
#:
#: ⚠️ ONE ENTRY, AND THE OTHER WAS DELETED RATHER THAN TUNED.
#:
#: `orphaned_health_scores` used to sit here at 1,364, then 1,400 after a
#: two-row overshoot showed the first value was a sample minimum mistaken for a
#: bound. It is GONE as of r183, which added the foreign key
#: `tenant_health_scores.tenant_id -> companies.id ON DELETE CASCADE`.
#:
#: ⚠️ THE ABSENCE OF A KEY HERE IS STRICTER THAN A ZERO, NOT WEAKER. The
#: comparison below reads `_LEAK_CEILING.get(k, 0)`, so a class with no entry
#: tolerates NO growth at all. The counter still counts it; what changed is that
#: any growth now fails the session.
#:
#: And it is structurally unreachable rather than merely unobserved: deleting a
#: company now deletes its health scores, so the mechanism that produced 60,469
#: orphans — create tenant, compute scores, purge tenant, leave scores — cannot
#: complete. That is the difference between a class that cannot recur and one
#: that cannot recur silently.
#:
#: `global_workflows` remains, unaffected by r183 and previously measured at
#: exactly +34 on four separate full-tree runs. Those rows have
#: `company_id IS NULL`, so no company-scoped constraint can ever reach them;
#: closing that one needs fixture teardown, not a foreign key. Lower it as
#: fixtures gain teardown; at 0, delete this dict and let the strict delta stand
#: alone.
#:
#: ⚠️ RATCHETED 34 -> 11 ON 2026-09-15, AND THE 23 THAT LEFT HAVE A NAME.
#:
#: The +34 was never one leak. Attributed per test on a full-tree run — by the
#: row class this dict defines, not by a name pattern — it was:
#:
#:     23  test_workflow_scope_latency_phase8a::test_workflow_fork_latency
#:      4  test_workflow_scope_phase8a  (TestForkEndpoint x3, TestCountTenants x1)
#:      5  tasks/test_b3_consumer_integration::TestWorkflowNodeTypes
#:      1  test_moc_ponder      1  test_classification_tier_3_registry
#:      1  test_moc_tenant_map, and -1 from a later test in the same file
#:     --
#:     34
#:
#: The fork gate now tears down by recorded id and contributes 0, measured over
#: three runs of the file and one full tree. 11 remains, re-measured on the
#: full-tree run that set this number.
#:
#: ⚠️ THE REMAINING 11 IS NOT THE SAME SHAPE and should not be swept up as more
#: of the same. The fork gate CLAIMED in its docstring to delete what it left;
#: none of these five does. One (`test_workflow_scope_phase8a`) has no
#: row-deleting teardown at all; the other three have substantial teardown that
#: does not reach these particular rows. That is a different item.
_LEAK_CEILING = {
    "global_workflows": 11,
}


def _litter_counts() -> dict | None:
    """Rows of the two classes the company tripwire is blind to."""
    try:
        from app.data.default_workflows import ALL_DEFAULT_WORKFLOWS
        from app.database import SessionLocal

        canonical = sorted({w["id"] for w in ALL_DEFAULT_WORKFLOWS})
        db = SessionLocal()
        try:
            return {
                "orphaned_health_scores": db.execute(text(
                    "SELECT count(*) FROM tenant_health_scores x WHERE x.tenant_id IS NOT NULL "
                    "AND NOT EXISTS (SELECT 1 FROM companies c WHERE c.id = x.tenant_id)"
                )).scalar(),
                "global_workflows": db.execute(text(
                    "SELECT count(*) FROM workflows WHERE company_id IS NULL "
                    "AND NOT (id = ANY(:c))"
                ), {"c": canonical}).scalar(),
            }
        finally:
            db.close()
    except Exception:
        return None  # no DB in this run — the tripwire stands down


@pytest.fixture(scope="session", autouse=True)
def _unowned_litter_tripwire():
    before = _litter_counts()
    yield
    if before is None or os.environ.get("BRIDGEABLE_ALLOW_COMPANY_LITTER"):
        return
    after = _litter_counts()
    if after is None:
        return
    over = {
        k: (before[k], after[k], _LEAK_CEILING[k])
        for k in after
        if after[k] - before[k] > _LEAK_CEILING.get(k, 0)
    }
    if over:
        detail = "; ".join(
            f"{k}: +{a - b} (ceiling {c})" for k, (b, a, c) in sorted(over.items())
        )
        pytest.fail(
            "UNOWNED LITTER GREW BEYOND ITS CEILING: rows the COMPANY LITTER "
            f"tripwire cannot see — {detail}. These belong to no company, so "
            "deleting a test tenant never reaches them. Either give the "
            "offending fixture a teardown that deletes the rows it creates by "
            "id, or — if the growth is legitimate — state why here. ⚠️ THE "
            "CEILING MAY ONLY BE LOWERED. Raising it retires the guard.",
            pytrace=False,
        )


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
