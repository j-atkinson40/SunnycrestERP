"""Domain-event emission (Canvas↔Runtime Bridge T-2.2a) — the transactional
outbox, proven at the transactionality boundary.

The claims:
  1. TRANSACTIONALITY (the reliability model): emit + commit → the event row is
     durable, payload verbatim; emit + ROLLBACK → NO row (the event commits iff
     the mutation commits — no phantom events).
  2. LOUD: an emission failure RAISES (never a swallowed emit — the
     silent-swallow-at-emission-scale guard). A bad company_id trips the FK at
     flush, inside emit_event, before any commit.
  3. CHOKEPOINT ASSEMBLY (two real sites end-to-end): fh case_service.create_case
     emits case.opened atomically with the case; the SSC approve() emits
     certificate.approved atomically with the approval. Payload = the catalog's
     filterable_fields snapshot; company scoping correct.
  4. INERT: emitted rows carry processed_at NULL (the T-2.2b matcher's queue);
     nothing consumes them this phase.

State-immunity: every assertion is scoped to this test's fixture ids (the
sweep-test lesson, pre-applied).
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.company import Company
from app.models.moc_domain_event import MoCDomainEvent
from app.services.maps_of_content.domain_events import emit_event

VERT = "manufacturing"


@pytest.fixture
def env():
    s = SessionLocal()
    suffix = uuid.uuid4().hex[:8]
    company = Company(id=str(uuid.uuid4()), name="Emit Co", slug=f"emit-{suffix}",
                      vertical=VERT, timezone="America/New_York", is_active=True)
    s.add(company)
    s.commit()
    ctx = {"db": s, "company": company}
    yield ctx
    s.rollback()
    cid = company.id
    # events + any chokepoint artifacts created against the fixture company
    s.execute(sql_text("DELETE FROM moc_domain_event WHERE company_id = :c"), {"c": cid})
    for tbl in (
        "funeral_case_notes", "case_vaults", "case_field_config",
        "case_deceased", "case_service", "case_disposition", "case_cemetery",
        "case_cremation", "case_veteran", "case_merchandise", "case_financials",
        "case_preneed", "case_aftercare",
    ):
        # table-name drift tolerance via SAVEPOINT — a bad name must not roll
        # back the earlier deletes (a plain rollback() here undid the events
        # delete and tripped the companies FK — the first run's teardown bug).
        try:
            with s.begin_nested():
                s.execute(sql_text(f"DELETE FROM {tbl} WHERE company_id = :c"), {"c": cid})
        except Exception:
            pass
    s.execute(sql_text("DELETE FROM funeral_cases WHERE company_id = :c"), {"c": cid})
    s.execute(sql_text("DELETE FROM social_service_certificates WHERE company_id = :c"), {"c": cid})
    s.execute(sql_text("DELETE FROM sales_orders WHERE company_id = :c"), {"c": cid})
    s.execute(sql_text("DELETE FROM customers WHERE company_id = :c"), {"c": cid})
    s.execute(sql_text("DELETE FROM users WHERE company_id = :c"), {"c": cid})
    s.execute(sql_text("DELETE FROM roles WHERE company_id = :c"), {"c": cid})
    s.execute(sql_text("DELETE FROM companies WHERE id = :c"), {"c": cid})
    s.commit()
    s.close()


def _events(db, company_id: str, event_key: str | None = None) -> list[MoCDomainEvent]:
    db.expire_all()
    q = db.query(MoCDomainEvent).filter(MoCDomainEvent.company_id == company_id)
    if event_key:
        q = q.filter(MoCDomainEvent.event_key == event_key)
    return q.all()


# ── 1. transactionality ────────────────────────────────────────────────


def test_emit_commits_with_the_transaction(env):
    s, co = env["db"], env["company"]
    emit_event(s, company_id=co.id, event_key="test.committed",
               entity_type="probe", entity_id="e-1",
               payload={"status": "active", "n": 3})
    s.commit()

    rows = _events(s, co.id, "test.committed")
    assert len(rows) == 1
    ev = rows[0]
    assert ev.payload == {"status": "active", "n": 3}   # snapshot verbatim
    assert ev.entity_type == "probe" and ev.entity_id == "e-1"
    assert ev.processed_at is None                       # inert — awaiting T-2.2b


def test_emit_rolls_back_with_the_transaction(env):
    """THE transactional-outbox claim: a rolled-back mutation leaves NO event
    (no phantom events for the matcher to fire on)."""
    s, co = env["db"], env["company"]
    emit_event(s, company_id=co.id, event_key="test.rolled_back",
               payload={"status": "x"})
    s.rollback()   # the mutation's transaction fails

    assert _events(s, co.id, "test.rolled_back") == []


def test_emit_failure_is_loud(env):
    """An emit that can't persist RAISES inside emit_event (flush trips the
    companies FK) — never a swallowed no-op."""
    s = env["db"]
    with pytest.raises(Exception):
        emit_event(s, company_id="nonexistent-company", event_key="test.loud")
    s.rollback()


# ── 2. chokepoint assembly — the real mutation sites ──────────────────


def test_create_case_emits_case_opened(env):
    from app.services.fh import case_service

    s, co = env["db"], env["company"]
    case = case_service.create_case(s, company_id=co.id)

    rows = _events(s, co.id, "case.opened")
    assert len(rows) == 1
    ev = rows[0]
    assert ev.entity_type == "fh_case"
    assert ev.entity_id == case.id                        # attributable
    assert ev.payload == {"status": "active"}             # the filterable snapshot
    assert ev.processed_at is None


def test_certificate_approve_emits_certificate_approved(env):
    from datetime import date

    from app.models.customer import Customer
    from app.models.role import Role
    from app.models.sales_order import SalesOrder
    from app.models.social_service_certificate import SocialServiceCertificate
    from app.models.user import User
    from app.services.social_service_certificate_service import (
        SocialServiceCertificateService,
    )

    s, co = env["db"], env["company"]
    role = Role(id=str(uuid.uuid4()), company_id=co.id, name="Admin", slug="admin")
    s.add(role)
    s.flush()
    approver = User(id=str(uuid.uuid4()), company_id=co.id, role_id=role.id,
                    email=f"appr-{uuid.uuid4().hex[:6]}@emit.test", hashed_password="x",
                    first_name="App", last_name="Rover")
    customer = Customer(id=str(uuid.uuid4()), company_id=co.id,
                        name=f"SSC Customer {uuid.uuid4().hex[:6]}")
    s.add_all([approver, customer])
    s.flush()
    order = SalesOrder(id=str(uuid.uuid4()), company_id=co.id,
                       customer_id=customer.id, order_date=date(2026, 7, 1),
                       number=f"SSC-{uuid.uuid4().hex[:6]}", status="pending")
    s.add(order)
    s.flush()
    cert = SocialServiceCertificate(
        id=str(uuid.uuid4()), company_id=co.id,
        certificate_number=f"CERT-{uuid.uuid4().hex[:6]}",
        order_id=order.id, status="pending_approval",
    )
    s.add(cert)
    s.commit()

    SocialServiceCertificateService.approve(cert.id, approved_by_user_id=approver.id, db=s)

    rows = _events(s, co.id, "certificate.approved")
    assert len(rows) == 1
    ev = rows[0]
    assert ev.entity_type == "social_service_certificate"
    assert ev.entity_id == cert.id
    assert ev.payload == {"status": "approved"}


def test_events_are_tenant_scoped(env):
    """An emit carries ITS company — another company's events never mix in."""
    s, co = env["db"], env["company"]
    other = Company(id=str(uuid.uuid4()), name="Other Co",
                    slug=f"emit-other-{uuid.uuid4().hex[:8]}", vertical=VERT, is_active=True)
    s.add(other)
    s.flush()
    try:
        emit_event(s, company_id=co.id, event_key="test.scoped", payload={})
        emit_event(s, company_id=other.id, event_key="test.scoped", payload={})
        s.commit()
        assert len(_events(s, co.id, "test.scoped")) == 1
        assert len(_events(s, other.id, "test.scoped")) == 1
    finally:
        s.execute(sql_text("DELETE FROM moc_domain_event WHERE company_id = :c"), {"c": other.id})
        s.execute(sql_text("DELETE FROM companies WHERE id = :c"), {"c": other.id})
        s.commit()
