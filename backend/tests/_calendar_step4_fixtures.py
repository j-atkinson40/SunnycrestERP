"""Shared fixtures for Calendar Step 4 test suite.

Centralizes tenant + user + account + event factory helpers so each
test module focuses on its specific assertion shape (action_types vs
cross_tenant_pairing vs magic_link vs outbound integration).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.database import SessionLocal
from app.models import Company, Role, User
from app.models.calendar_primitive import (
    CalendarAccount,
    CalendarAccountAccess,
    CalendarEvent,
    CalendarEventAttendee,
)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def make_tenant(db_session, *, name_prefix="Step4", vertical="manufacturing"):
    co = Company(
        id=str(uuid.uuid4()),
        name=f"{name_prefix} {uuid.uuid4().hex[:8]}",
        slug=f"s4{uuid.uuid4().hex[:8]}",
        vertical=vertical,
    )
    db_session.add(co)
    db_session.flush()
    return co


def make_user(db_session, tenant, *, email_prefix="u"):
    role = Role(
        id=str(uuid.uuid4()),
        company_id=tenant.id,
        name="Admin",
        slug="admin",
        is_system=True,
    )
    db_session.add(role)
    db_session.flush()
    user = User(
        id=str(uuid.uuid4()),
        email=f"{email_prefix}-{uuid.uuid4().hex[:8]}@s4.test",
        hashed_password="x",
        first_name="S",
        last_name="4",
        company_id=tenant.id,
        role_id=role.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def make_account(db_session, tenant, *, user=None, outbound_enabled=True):
    if user is None:
        user = make_user(db_session, tenant)
    acc = CalendarAccount(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        account_type="shared",
        display_name="Step 4 Test",
        primary_email_address=f"acc-{uuid.uuid4().hex[:8]}@s4.test",
        provider_type="local",
        outbound_enabled=outbound_enabled,
        created_by_user_id=user.id,
    )
    db_session.add(acc)
    db_session.flush()
    return acc


def grant_access(db_session, account, user, *, level="admin"):
    grant = CalendarAccountAccess(
        id=str(uuid.uuid4()),
        account_id=account.id,
        user_id=user.id,
        tenant_id=account.tenant_id,
        access_level=level,
    )
    db_session.add(grant)
    db_session.flush()
    return grant


def make_event(db_session, account, *, status="tentative", **kwargs):
    defaults = dict(
        id=str(uuid.uuid4()),
        tenant_id=account.tenant_id,
        account_id=account.id,
        subject="Step 4 test event",
        start_at=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
        event_timezone="UTC",
        status=status,
        transparency="opaque",
        is_cross_tenant=False,
        action_payload={},
    )
    defaults.update(kwargs)
    event = CalendarEvent(**defaults)
    db_session.add(event)
    db_session.flush()
    return event


def make_attendee(
    db_session,
    event,
    *,
    email_address=None,
    is_internal=True,
    response_status="needs_action",
):
    att = CalendarEventAttendee(
        id=str(uuid.uuid4()),
        event_id=event.id,
        tenant_id=event.tenant_id,
        email_address=email_address
        or f"a-{uuid.uuid4().hex[:8]}@e.test",
        role="required_attendee",
        response_status=response_status,
        is_internal=is_internal,
    )
    db_session.add(att)
    db_session.flush()
    return att
