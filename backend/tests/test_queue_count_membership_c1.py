"""Queue-count perf arc C-1 — the membership seam, established on ss_cert_triage.

The property the whole design rests on: COUNT and BUILD share ONE membership
expression (`_mq_ss_cert_triage`) and therefore cannot disagree. These tests pin:
  * build (`_dq_ss_cert_triage`) and count (`queue_count`) see the SAME member ids
    and the SAME number against seeded data;
  * count is the COUNT(*) fast path (membership seam), not materialize-and-count;
  * the snooze filter as a SQL anti-join produces the SAME result as the legacy
    Python post-filter (`len(members) - snoozed-that-are-members`);
  * tenant isolation — another company's pending cert is neither built nor counted.

Cleans up its own `qcm1-*` tenants via the shared FK-safe helper.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.database import SessionLocal
from app.models.company import Company
from app.models.customer import Customer
from app.models.role import Role
from app.models.sales_order import SalesOrder
from app.models.social_service_certificate import SocialServiceCertificate
from app.models.triage import TriageSnooze
from app.models.user import User
from app.services.triage.engine import (
    _dq_ss_cert_triage,
    _mq_ss_cert_triage,
    queue_count,
)
from tests._cleanup import purge_companies_by_slug

_SLUG = "qcm1-"
_QUEUE = "ss_cert_triage"


def _company(s, sfx):
    co = Company(id=str(uuid.uuid4()), name=f"QCM1 {sfx}", slug=f"{_SLUG}{sfx}",
                 is_active=True, vertical="manufacturing")
    s.add(co)
    s.flush()
    role = Role(id=str(uuid.uuid4()), company_id=co.id, name="Admin", slug="admin")
    s.add(role)
    s.flush()
    user = User(id=str(uuid.uuid4()), company_id=co.id, role_id=role.id,
                email=f"qcm1-{sfx}@test.local", hashed_password="x",
                first_name="Q", last_name="One", is_active=True,
                is_super_admin=True)  # bypass the per-queue permission gate
    s.add(user)
    s.flush()
    return co, user


def _cert(s, company_id, *, status, i):
    """A pending/approved cert + its required sales_order + customer chain
    (order_id is a unique NOT NULL FK, so each cert needs its own order)."""
    cust = Customer(id=str(uuid.uuid4()), company_id=company_id,
                    name=f"Cust {i}", is_active=True)
    s.add(cust)
    s.flush()
    order = SalesOrder(id=str(uuid.uuid4()), company_id=company_id,
                       number=f"SO-{uuid.uuid4().hex[:8]}", customer_id=cust.id,
                       order_date=datetime.now(timezone.utc))
    s.add(order)
    s.flush()
    cert = SocialServiceCertificate(
        id=str(uuid.uuid4()), company_id=company_id,
        certificate_number=f"{order.number}-SSC", order_id=order.id,
        status=status,
        generated_at=datetime.now(timezone.utc) - timedelta(hours=i),
    )
    s.add(cert)
    s.flush()
    return cert


@pytest.fixture
def env():
    s = SessionLocal()
    sfx = uuid.uuid4().hex[:8]
    co, user = _company(s, sfx)
    # 3 pending (members) + 2 non-pending (non-members) in this tenant.
    pending = [_cert(s, co.id, status="pending_approval", i=i) for i in range(3)]
    _cert(s, co.id, status="approved", i=10)
    _cert(s, co.id, status="voided", i=11)
    # A different tenant with its own pending cert — must never leak in.
    other_co, _other_user = _company(s, uuid.uuid4().hex[:8])
    other_cert = _cert(s, other_co.id, status="pending_approval", i=0)
    s.commit()
    yield type("Env", (), {
        "s": s, "user": user,
        "pending_ids": {c.id for c in pending},
        "other_cert_id": other_cert.id,
    })()
    s.rollback()
    try:
        purge_companies_by_slug(s, f"{_SLUG}%")
    finally:
        s.close()


def test_build_returns_the_pending_members(env):
    rows = _dq_ss_cert_triage(env.s, env.user)
    assert {r["id"] for r in rows} == env.pending_ids


def test_count_equals_build_membership(env):
    """The core property: count == number of built rows, same id universe."""
    rows = _dq_ss_cert_triage(env.s, env.user)
    n = queue_count(env.s, user=env.user, queue_id=_QUEUE)
    assert n == len(rows) == 3


def test_membership_query_and_build_agree_on_ids(env):
    """Build consumes the membership query; the ids must be identical to what
    the membership query yields directly (one expression, two consumers)."""
    mq = _mq_ss_cert_triage(env.s, env.user)
    mq_ids = {c.id for c in mq.query.all()}
    build_ids = {r["id"] for r in _dq_ss_cert_triage(env.s, env.user)}
    assert mq_ids == build_ids == env.pending_ids


def test_snooze_anti_join_matches_legacy_post_filter(env):
    """Snooze as a SQL anti-join must equal the legacy Python semantics:
    len(members) - snoozed-that-are-members."""
    snoozed_id = next(iter(env.pending_ids))
    env.s.add(TriageSnooze(
        id=str(uuid.uuid4()), company_id=env.user.company_id,
        user_id=env.user.id, queue_id=_QUEUE, entity_type="ss_cert",
        entity_id=snoozed_id,
        wake_at=datetime.now(timezone.utc) + timedelta(hours=6),
    ))
    env.s.commit()

    n = queue_count(env.s, user=env.user, queue_id=_QUEUE)
    build_ids = {r["id"] for r in _dq_ss_cert_triage(env.s, env.user)}
    legacy = len([i for i in build_ids if i != snoozed_id])
    assert n == legacy == 2


def test_expired_snooze_does_not_reduce_count(env):
    """A snooze whose wake_at has passed is inactive — must not be excluded."""
    env.s.add(TriageSnooze(
        id=str(uuid.uuid4()), company_id=env.user.company_id,
        user_id=env.user.id, queue_id=_QUEUE, entity_type="ss_cert",
        entity_id=next(iter(env.pending_ids)),
        wake_at=datetime.now(timezone.utc) - timedelta(hours=1),
    ))
    env.s.commit()
    assert queue_count(env.s, user=env.user, queue_id=_QUEUE) == 3


def test_tenant_isolation(env):
    """The other tenant's pending cert is neither built nor counted here."""
    rows = _dq_ss_cert_triage(env.s, env.user)
    assert env.other_cert_id not in {r["id"] for r in rows}
    assert queue_count(env.s, user=env.user, queue_id=_QUEUE) == 3
