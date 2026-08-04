"""Queue-count perf arc C-4 — batched counts_for_user.

The fan-out entry point: one call returns pending counts for every queue the user
can see, hoisting the per-render floor (queue configs + permission set) out of the
per-queue path so a 12-queue render is ~12 counts + a small constant, not
12 × (config + permission + count).

Pinned:
  * EQUIVALENCE (the anti-divergence guard): counts_for_user == the per-queue
    queue_count for the same queues — batched and single-queue cannot disagree;
  * the queue_ids subset filter + the configs= reuse path;
  * the QUERY-COUNT WIN: the batched call issues materially fewer SQL statements
    than the per-queue loop it replaces (measured with a statement counter).

Reuses the C-2 seeding helpers. Cleans up its own `qcm2-*` tenants (shared helper).
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import event

from app.database import SessionLocal, engine
from app.services.triage import (
    counts_for_user,
    list_queues_for_user,
    queue_count,
)
from tests._cleanup import purge_companies_by_slug
from tests.test_queue_count_membership_c2 import _anomaly, _company, _job

_SLUG = "qcm2-"


class _StmtCounter:
    """Counts SQL statements executed on the shared engine within a block."""

    def __init__(self):
        self.n = 0

    def __enter__(self):
        self.n = 0
        event.listen(engine, "after_cursor_execute", self._bump)
        return self

    def __exit__(self, *exc):
        event.remove(engine, "after_cursor_execute", self._bump)

    def _bump(self, *a):
        self.n += 1


@pytest.fixture
def env():
    s = SessionLocal()
    co, user = _company(s)
    # Seed members across three queues so counts are non-trivial + distinct.
    jcr = _job(s, co.id, "cash_receipts_matching")
    for _ in range(3):
        _anomaly(s, jcr, "payment_unmatched_stale")
    jar = _job(s, co.id, "ar_collections")
    for _ in range(2):
        _anomaly(s, jar, "collections_critical", entity_type="customer")
    for _ in range(4):
        _job(s, co.id, "month_end_close")  # 4 awaiting-approval jobs
    s.commit()
    yield type("Env", (), {"s": s, "co": co.id, "user": user})()
    s.rollback()
    try:
        purge_companies_by_slug(s, f"{_SLUG}%")
    finally:
        s.close()


def _per_queue(env):
    return {
        c.queue_id: queue_count(env.s, user=env.user, queue_id=c.queue_id)
        for c in list_queues_for_user(env.s, user=env.user)
    }


def test_batched_equals_per_queue(env):
    """The anti-divergence guard: batched counts == single-queue counts."""
    batched = counts_for_user(env.s, user=env.user)
    per_queue = _per_queue(env)
    assert batched == per_queue
    # and the seeded numbers are what we expect
    assert batched["cash_receipts_matching_triage"] == 3
    assert batched["ar_collections_triage"] == 2
    assert batched["month_end_close_triage"] == 4


def test_queue_ids_subset(env):
    only = counts_for_user(
        env.s, user=env.user,
        queue_ids=["cash_receipts_matching_triage", "month_end_close_triage"],
    )
    assert set(only) == {"cash_receipts_matching_triage", "month_end_close_triage"}
    assert only["cash_receipts_matching_triage"] == 3
    assert only["month_end_close_triage"] == 4


def test_configs_reuse_matches(env):
    """Passing a pre-fetched list_queues_for_user result yields the same counts
    (and lets the caller avoid a second gate pass)."""
    configs = list_queues_for_user(env.s, user=env.user)
    assert counts_for_user(env.s, user=env.user, configs=configs) == counts_for_user(
        env.s, user=env.user
    )


def test_batched_issues_fewer_statements_than_loop(env):
    """The whole point: the batched call pays the config + permission floor once,
    the per-queue loop pays it N times. Measured as SQL-statement count."""
    n_queues = len(list_queues_for_user(env.s, user=env.user))
    assert n_queues >= 10  # sanity: the full platform fan-out

    with _StmtCounter() as loop:
        _per_queue(env)
    with _StmtCounter() as batched:
        counts_for_user(env.s, user=env.user)

    # Batched must be materially cheaper — and on the order of "one per queue
    # plus a small constant", well under the per-queue loop.
    assert batched.n < loop.n
    assert batched.n <= n_queues + 6, (
        f"batched={batched.n} exceeds ~{n_queues}+const; loop={loop.n}"
    )
