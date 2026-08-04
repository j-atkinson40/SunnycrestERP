"""Queue-count perf arc C-5 — the new count preserves the OLD path's numbers.

The pre-C-1 materialize-and-count implementation is gone from the code, so the
"old path" is reconstructed inline here: exactly the pre-C-1 queue_count body —
run the builder via `_execute_queue_saved_view`, then subtract the user's active
snoozes. This is the permanent form of the C-5 prod validation (which diffed the
same reconstruction against production and found 0 unexpected mismatches).

  * standard queues: new count (counts_for_user) == reconstructed old count;
  * email_unclassified: the DOCUMENTED exception — its new count is exact +
    uncapped while its builder stays display-capped at 50, so at >50 members the
    new count exceeds the reconstructed (capped) old count by design.

Cleans up its own `qcm5-*` tenants via the shared FK-safe helper.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.database import SessionLocal
from app.models.company import Company
from app.models.email_classification import WorkflowEmailClassification as WEC
from app.models.role import Role
from app.models.user import User
from app.services.triage import counts_for_user, list_queues_for_user
from app.services.triage.engine import (
    _active_snooze_entity_ids,
    _execute_queue_saved_view,
)
from tests._classification_fixtures import make_email_account, make_inbound_email
from tests._cleanup import purge_companies_by_slug
from tests.test_queue_count_membership_c2 import _anomaly, _job

_SLUG = "qcm5-"


def _company(s):
    sfx = uuid.uuid4().hex[:8]
    co = Company(id=str(uuid.uuid4()), name=f"QCM5 {sfx}", slug=f"{_SLUG}{sfx}",
                 is_active=True, vertical="manufacturing")
    s.add(co)
    s.flush()
    role = Role(id=str(uuid.uuid4()), company_id=co.id, name="Admin", slug="admin")
    s.add(role)
    s.flush()
    user = User(id=str(uuid.uuid4()), company_id=co.id, role_id=role.id,
                email=f"qcm5-{sfx}@test.local", hashed_password="x",
                first_name="Q", last_name="Five", is_active=True,
                is_super_admin=True)
    s.add(user)
    s.flush()
    return co, user


def _reconstruct_old_count(s, user, cfg):
    """The pre-C-1 queue_count body: materialize the builder + drop snoozed."""
    snoozed = _active_snooze_entity_ids(s, user_id=user.id, queue_id=cfg.queue_id)
    rows = _execute_queue_saved_view(s, config=cfg, user=user)
    return sum(1 for r in rows if r.get("id") not in snoozed)


@pytest.fixture
def env():
    s = SessionLocal()
    co, user = _company(s)
    s.commit()
    acct = make_email_account(s, co)
    yield type("Env", (), {"s": s, "co": co, "user": user, "acct": acct})()
    s.rollback()
    try:
        purge_companies_by_slug(s, f"{_SLUG}%")
    finally:
        s.close()


def test_new_count_equals_reconstructed_old_path(env):
    """Standard queues: counts_for_user == the reconstructed pre-arc count."""
    jcr = _job(env.s, env.co.id, "cash_receipts_matching")
    for _ in range(3):
        _anomaly(env.s, jcr, "payment_unmatched_stale")
    jar = _job(env.s, env.co.id, "ar_collections")
    for _ in range(2):
        _anomaly(env.s, jar, "collections_critical", entity_type="customer")
    env.s.commit()

    new = counts_for_user(env.s, user=env.user)
    for cfg in list_queues_for_user(env.s, user=env.user):
        if cfg.queue_id == "email_unclassified_triage":
            continue  # documented exception — see the next test
        assert new[cfg.queue_id] == _reconstruct_old_count(env.s, env.user, cfg), (
            f"{cfg.queue_id}: new={new[cfg.queue_id]} "
            f"old={_reconstruct_old_count(env.s, env.user, cfg)}"
        )
    assert new["cash_receipts_matching_triage"] == 3
    assert new["ar_collections_triage"] == 2


def test_email_unclassified_is_the_documented_exception(env):
    """At >50 members the new count is exact (uncapped) while the reconstructed
    old count is display-capped at 50 — the intended, documented divergence."""
    co, acct = env.co, env.acct
    for i in range(60):
        msg = make_inbound_email(env.s, tenant=co, account=acct, subject=f"m{i}")
        env.s.add(WEC(id=str(uuid.uuid4()), tenant_id=co.id,
                      email_message_id=msg.id, tier=None, is_suppressed=False,
                      created_at=datetime.now(timezone.utc) + timedelta(minutes=i)))
    env.s.commit()

    cfg = next(c for c in list_queues_for_user(env.s, user=env.user)
               if c.queue_id == "email_unclassified_triage")
    old = _reconstruct_old_count(env.s, env.user, cfg)      # capped 50 build
    new = counts_for_user(env.s, user=env.user)["email_unclassified_triage"]
    assert old == 50            # the builder's display cap
    assert new == 60            # exact, uncapped
    assert new > old            # the documented, by-design divergence
