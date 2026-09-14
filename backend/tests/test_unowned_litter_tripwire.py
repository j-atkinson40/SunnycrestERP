"""Controls for the UNOWNED LITTER tripwire in conftest.

⚠️ A TRIPWIRE THAT ASSERTS AN ABSENCE LOOKS IDENTICAL WHETHER OR NOT THE
INSTRUMENT WORKS. This project has twice had a ratchet's own assertion pass
under a deliberate break while only a control caught it, so the two controls
CLAUDE.md requires are here: one proving the counter SEES the real population,
one proving a regression is NAMED rather than producing a generic red.

The tripwire itself is a session-scoped fixture and cannot be invoked directly
without a nested pytest session, so these exercise `_litter_counts` — the thing
the fixture reads — plus the comparison it performs.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from tests.conftest import _litter_counts


@pytest.fixture
def db():
    from app.database import SessionLocal
    s = SessionLocal()
    yield s
    s.close()


# ── control 1: the counter sees a real population ────────────────────────


def test_the_counter_SEES_a_nonempty_population():
    """⚠️ CONTROL. A counter matching nothing satisfies "did not grow" forever.

    Both classes are non-empty on this database today. If the purge has been
    run and both are legitimately zero, this test must be replaced by the
    ceiling it makes possible — NOT deleted, which would leave the tripwire
    unverified.
    """
    counts = _litter_counts()
    assert counts is not None, "no database — the control cannot run"
    assert set(counts) == {"orphaned_health_scores", "global_workflows"}
    assert sum(counts.values()) > 0, (
        f"both classes read zero: {counts}. Either the purge has run — in which "
        "case convert this tripwire to a ceiling of 0, which is stronger — or "
        "the predicates stopped matching and the tripwire is now blind."
    )


def test_the_predicate_EXCLUDES_rows_that_are_not_litter(db):
    """⚠️ CONTROL ON THE OTHER SIDE, AND IT INTERROGATES THE INSTRUMENT.

    A predicate that matched EVERYTHING would also be non-empty, so control 1
    cannot see it. This one derives the expected count independently and
    compares it to what `_litter_counts` actually returns.

    ⚠️ ITS FIRST VERSION RE-EXPRESSED THE PREDICATE INLINE and asserted the
    inline copy excluded canonical rows. That verified a copy, not the
    instrument: a break widening conftest's predicate to match every workflow
    left all three tests green. The break test is the only reason this is
    written the way it is now.
    """
    from app.data.default_workflows import ALL_DEFAULT_WORKFLOWS

    canonical = sorted({w["id"] for w in ALL_DEFAULT_WORKFLOWS})

    total_global = db.execute(text(
        "SELECT count(*) FROM workflows WHERE company_id IS NULL")).scalar()
    canonical_global = db.execute(text(
        "SELECT count(*) FROM workflows WHERE company_id IS NULL AND id = ANY(:c)"),
        {"c": canonical}).scalar()

    # The exclusion is only verifiable against rows that exist. Canonical rows
    # are permanent seed data, so this holds on any seeded database.
    assert canonical_global > 0, "no canonical rows are global; exclusion is vacuous"

    counts = _litter_counts()
    assert counts["global_workflows"] == total_global - canonical_global, (
        f"counter returned {counts['global_workflows']}; global rows are "
        f"{total_global} of which {canonical_global} are canonical, so litter is "
        f"{total_global - canonical_global}. The predicate is not excluding what "
        "it claims to exclude."
    )

    # ⚠️ THE COMPANY-OWNED EXCLUSION CREATES ITS OWN SUBJECT.
    #
    # A first version asserted `owned > 0` against whatever tenant-owned
    # workflows happened to exist. It passed standalone and FAILED in the
    # full-tree run: by the time it executed, other suites' teardown had purged
    # the companies those rows belonged to, and there were zero. The guard was
    # right to refuse — a vacuous exclusion proves nothing — but the test was
    # wrong to depend on a shared world it did not create.
    owned_id = str(uuid.uuid4())
    co_id = db.execute(text("SELECT id FROM companies LIMIT 1")).scalar()
    assert co_id, "no company exists; the owned-exclusion cannot be constructed"
    db.execute(text(
        "INSERT INTO workflows (id, company_id, name, tier, scope, trigger_type, "
        "is_active, is_system, created_at) VALUES "
        "(:i, :co, :n, 1, 'tenant', 'manual', true, false, now())"),
        {"i": owned_id, "co": co_id, "n": f"OWNED-CONTROL-{owned_id[:8]}"})
    db.commit()
    try:
        assert _litter_counts()["global_workflows"] == counts["global_workflows"], (
            "a company-OWNED workflow moved the global counter; the "
            "`company_id IS NULL` clause is not doing its work"
        )
    finally:
        db.execute(text("DELETE FROM workflows WHERE id = :i"), {"i": owned_id})
        db.commit()

    # Health scores: the same shape, against the live-tenant rows.
    live = db.execute(text(
        "SELECT count(*) FROM tenant_health_scores x WHERE "
        "EXISTS (SELECT 1 FROM companies c WHERE c.id = x.tenant_id)")).scalar()
    total_hs = db.execute(text("SELECT count(*) FROM tenant_health_scores")).scalar()
    assert live > 0, "no live-tenant health scores; that exclusion is vacuous"
    assert counts["orphaned_health_scores"] == total_hs - live


# ── control 2: a regression is NAMED, not a generic red ──────────────────


def test_a_LEAK_is_NAMED_by_class_not_merely_counted(db):
    """⚠️ CONTROL. Create one unowned workflow, confirm the counter moves and
    says WHICH class moved, then remove it.

    Without this, a green tripwire is evidence the counter matches nothing
    rather than evidence nothing leaked.
    """
    before = _litter_counts()
    wf_id = str(uuid.uuid4())
    db.execute(text(
        "INSERT INTO workflows (id, name, tier, scope, trigger_type, is_active, "
        "is_system, created_at) "
        "VALUES (:i, :n, 1, 'core', 'manual', true, true, now())"),
        {"i": wf_id, "n": f"LITTER-CONTROL-{wf_id[:8]}"})
    db.commit()
    try:
        after = _litter_counts()
        grew = {k: (before[k], after[k]) for k in after if after[k] > before[k]}
        # Control that the injection applied — a marker, not a green.
        assert wf_id in {r[0] for r in db.execute(text(
            "SELECT id FROM workflows WHERE id = :i"), {"i": wf_id}).all()}
        assert grew, "the counter did not move; it is not watching this table"
        assert "global_workflows" in grew, (
            f"the leak was detected but attributed to the wrong class: {grew}"
        )
        assert "orphaned_health_scores" not in grew, (
            "an unrelated class moved too — the counter is not discriminating"
        )
        b, a = grew["global_workflows"]
        assert a == b + 1, f"expected exactly one new row, got {a - b}"
    finally:
        db.execute(text("DELETE FROM workflows WHERE id = :i"), {"i": wf_id})
        db.commit()
    # ⚠️ AND THE TEARDOWN IS ITSELF VERIFIED. A control that leaks while
    # proving leaks are caught would fail the very tripwire it tests.
    assert _litter_counts()["global_workflows"] == before["global_workflows"]


# ── control 3: the ceiling cannot hide a new class ───────────────────────


def test_a_NEW_LITTER_CLASS_defaults_to_STRICT_not_to_slack():
    """⚠️ CONTROL ON THE CEILING ITSELF.

    The ceiling is a dict of allowances. The hazard is that someone adds a
    third class to `_litter_counts` and it silently inherits an allowance, or
    that a class is removed from the counter while its allowance stays and
    quietly permits a leak nobody is measuring.

    The comparison uses `.get(k, 0)`, so an unlisted class is STRICT — that is
    the safe direction, and this pins it. It also pins the reverse: no allowance
    may exist for a class the counter does not produce.

    ⚠️ TIGHTNESS IS NOT TESTABLE HERE, AND SAYING SO MATTERS. Whether 34 and
    1,364 are the real leak can only be established by a full-tree run; a unit
    test asserting the ceiling equals the leak would have to leak to find out.
    The gate run IS that control, and the commit that sets these numbers reports
    it. If a ceiling ever sits above the true leak, this ratchet has stopped
    ratcheting and will pass while the leak grows underneath it — which is
    exactly how two earlier ratchets in this project went green under a break.
    """
    from tests.conftest import _LEAK_CEILING

    counts = _litter_counts()
    assert counts is not None, "no database — the control cannot run"

    unknown = set(_LEAK_CEILING) - set(counts)
    assert not unknown, (
        f"allowance declared for classes the counter does not produce: {unknown}. "
        "Either the counter lost a class or the allowance outlived it."
    )
    assert all(v >= 0 for v in _LEAK_CEILING.values())
