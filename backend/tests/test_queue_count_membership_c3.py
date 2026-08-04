"""Queue-count perf arc C-3 — email_unclassified, the window-function translation.

email_unclassified is the only non-trivial membership: "the LATEST classification
per message is tier IS NULL AND NOT suppressed", filtered in Python today
(classification.dispatch.list_unclassified via get_latest_classification_for_message).
`_mq_email_unclassified_triage` expresses it as a ROW_NUMBER() window.

The load-bearing test (per the dispatch): prove the SQL and the existing Python
produce IDENTICAL membership against seeded data — run both, diff the id sets,
assert empty — BEFORE trusting the SQL. The Python reference is called with a
large limit so its incidental LIMIT 50 doesn't mask the comparison.

Plus the cap-behavior characterization: the count is EXACT + uncapped (per the
arc's EXACT-COUNTS decision), while the builder keeps its display LIMIT. At >50
members, count == true N and the build stages 50 — they legitimately differ,
which is why the C-2 `count == len(build)` invariant does NOT apply here.

Cleans up its own `qce3-*` tenants via the shared FK-safe helper.
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
from app.services.classification.dispatch import list_unclassified
from app.services.triage.engine import (
    _dq_email_unclassified_triage,
    _mq_email_unclassified_triage,
    queue_count,
)
from tests._classification_fixtures import make_email_account, make_inbound_email
from tests._cleanup import purge_companies_by_slug

_SLUG = "qce3-"
_QUEUE = "email_unclassified_triage"
_BASE = datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc)


def _company(s):
    sfx = uuid.uuid4().hex[:8]
    co = Company(id=str(uuid.uuid4()), name=f"QCE3 {sfx}", slug=f"{_SLUG}{sfx}",
                 is_active=True, vertical="manufacturing")
    s.add(co)
    s.flush()
    role = Role(id=str(uuid.uuid4()), company_id=co.id, name="Admin", slug="admin")
    s.add(role)
    s.flush()
    user = User(id=str(uuid.uuid4()), company_id=co.id, role_id=role.id,
                email=f"qce3-{sfx}@test.local", hashed_password="x",
                first_name="Q", last_name="Three", is_active=True,
                is_super_admin=True)
    s.add(user)
    s.flush()
    return co, user


@pytest.fixture
def env():
    s = SessionLocal()
    co, user = _company(s)
    other_co, other_user = _company(s)
    s.commit()
    acct = make_email_account(s, co)
    other_acct = make_email_account(s, other_co)
    yield type("Env", (), {
        "s": s, "co": co, "user": user, "acct": acct,
        "other_co": other_co, "other_user": other_user, "other_acct": other_acct,
    })()
    s.rollback()
    try:
        purge_companies_by_slug(s, f"{_SLUG}%")
    finally:
        s.close()


def _msg(env, co, acct, subject="s"):
    return make_inbound_email(env.s, tenant=co, account=acct, subject=subject)


def _wec(env, co, msg, *, tier, suppressed=False, mins=0):
    row = WEC(id=str(uuid.uuid4()), tenant_id=co.id, email_message_id=msg.id,
              tier=tier, is_suppressed=suppressed,
              created_at=_BASE + timedelta(minutes=mins))
    env.s.add(row)
    env.s.flush()
    return row


def _sql_member_ids(env):
    return {w.id for w in _mq_email_unclassified_triage(env.s, env.user).query.all()}


def _python_member_ids(env):
    # Large limit so the Python reference's incidental LIMIT 50 doesn't cap the
    # comparison — pure membership logic (latest-per-message) vs the SQL window.
    return {r["id"] for r in list_unclassified(env.s, tenant_id=env.co.id, limit=100000)}


def test_sql_membership_matches_python_reference(env):
    """The identity proof: seed the substantive membership cases, run BOTH the
    SQL window and the Python reference, diff the id sets, assert empty."""
    co, acct = env.co, env.acct

    # A — single unclassified → MEMBER
    a = _wec(env, co, _msg(env, co, acct, "A"), tier=None, mins=0)
    # B — unclassified then later classified (replay) → latest classified → OUT
    mb = _msg(env, co, acct, "B")
    _wec(env, co, mb, tier=None, mins=1)
    _wec(env, co, mb, tier=2, mins=2)
    # C — classified then reopened unclassified → latest unclassified → MEMBER
    mc = _msg(env, co, acct, "C")
    _wec(env, co, mc, tier=2, mins=1)
    c2 = _wec(env, co, mc, tier=None, mins=3)
    # D — unclassified then suppressed → latest suppressed → OUT
    md = _msg(env, co, acct, "D")
    _wec(env, co, md, tier=None, mins=1)
    _wec(env, co, md, tier=None, suppressed=True, mins=2)
    # E — single classified → OUT
    _wec(env, co, _msg(env, co, acct, "E"), tier=1, mins=0)
    # F — single unclassified but suppressed → OUT
    _wec(env, co, _msg(env, co, acct, "F"), tier=None, suppressed=True, mins=0)
    # G — other tenant, unclassified → OUT of tenant A's membership
    _wec(env, env.other_co, _msg(env, env.other_co, env.other_acct, "G"),
         tier=None, mins=0)
    env.s.commit()

    sql = _sql_member_ids(env)
    py = _python_member_ids(env)
    assert sql - py == set(), f"SQL has extra members: {sql - py}"
    assert py - sql == set(), f"Python has extra members: {py - sql}"
    assert sql == py == {a.id, c2.id}
    # count agrees with the (uncapped) membership
    assert queue_count(env.s, user=env.user, queue_id=_QUEUE) == 2


def test_count_is_exact_and_uncapped_while_build_is_display_capped(env):
    """60 members: the count reports the TRUE number (uncapped, exact — the arc's
    EXACT-COUNTS decision), while the builder stages only its display LIMIT (50).
    This is why `count == len(build)` (the C-2 invariant) does NOT hold here."""
    co, acct = env.co, env.acct
    for i in range(60):
        _wec(env, co, _msg(env, co, acct, f"m{i}"), tier=None, mins=i)
    env.s.commit()

    assert queue_count(env.s, user=env.user, queue_id=_QUEUE) == 60      # exact
    assert len(_dq_email_unclassified_triage(env.s, env.user)) == 50     # display cap
    # And even at >50, the SQL membership still matches the Python reference
    # (run with a large limit so neither is capped).
    assert _sql_member_ids(env) == _python_member_ids(env)


def test_build_display_shape_and_ordering(env):
    """The builder preserves the display projection + oldest-first ordering."""
    co, acct = env.co, env.acct
    m_old = _msg(env, co, acct, "older")
    _wec(env, co, m_old, tier=None, mins=0)
    m_new = _msg(env, co, acct, "newer")
    _wec(env, co, m_new, tier=None, mins=5)
    env.s.commit()

    rows = _dq_email_unclassified_triage(env.s, env.user)
    assert [r["subject"] for r in rows] == ["older", "newer"]  # created_at asc
    assert set(rows[0]) >= {
        "id", "classification_id", "email_message_id", "subject",
        "sender_email", "body_excerpt", "received_at", "created_at",
        "tier_reasoning",
    }
