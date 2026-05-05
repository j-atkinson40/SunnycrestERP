"""Shared fixtures for Calendar Step 5 test suite.

Centralizes tenant + user + account + event factory helpers so each
test module focuses on its specific assertion shape.

Pattern parallels ``_calendar_step4_fixtures.py`` verbatim with
extensions for Step 5 cross-surface scenarios (CRM activity feed
linkages, customer Pulse composition source, attendee resolution).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet


os.environ.setdefault(
    "CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode()
)


# ─────────────────────────────────────────────────────────────────────
# Session helpers
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def make_tenant(db_session, *, name_prefix="S5", vertical="manufacturing"):
    from app.models import Company

    co = Company(
        id=str(uuid.uuid4()),
        name=f"{name_prefix} {uuid.uuid4().hex[:8]}",
        slug=f"s5{uuid.uuid4().hex[:8]}",
        vertical=vertical,
        is_active=True,
    )
    db_session.add(co)
    db_session.flush()
    return co


def make_user(db_session, tenant, *, email_prefix="u", is_super_admin=False):
    from app.models import Role, User

    # Reuse existing admin role for this tenant if one exists (UNIQUE
    # constraint on (slug, company_id) prevents duplicate creation).
    role = (
        db_session.query(Role)
        .filter(Role.company_id == tenant.id, Role.slug == "admin")
        .first()
    )
    if role is None:
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
        email=f"{email_prefix}-{uuid.uuid4().hex[:8]}@s5.test",
        hashed_password="x",
        first_name="S",
        last_name="5",
        company_id=tenant.id,
        role_id=role.id,
        is_active=True,
        is_super_admin=is_super_admin,
    )
    db_session.add(user)
    db_session.flush()
    return user


def make_account(db_session, tenant, *, user=None, outbound_enabled=True):
    from app.models.calendar_primitive import CalendarAccount

    if user is None:
        user = make_user(db_session, tenant)
    acc = CalendarAccount(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        account_type="shared",
        display_name="S5 Test",
        primary_email_address=f"acc-{uuid.uuid4().hex[:8]}@s5.test",
        provider_type="local",
        outbound_enabled=outbound_enabled,
        created_by_user_id=user.id,
    )
    db_session.add(acc)
    db_session.flush()
    return acc


def grant_access(db_session, account, user, *, level="admin"):
    from app.models.calendar_primitive import CalendarAccountAccess

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


def make_event(
    db_session,
    account,
    *,
    status="confirmed",
    transparency="opaque",
    start_at=None,
    end_at=None,
    subject="S5 test event",
    location=None,
    is_cross_tenant=False,
    **kwargs,
):
    from app.models.calendar_primitive import CalendarEvent

    if start_at is None:
        start_at = datetime.now(timezone.utc) + timedelta(hours=1)
    if end_at is None:
        end_at = start_at + timedelta(hours=1)

    defaults = dict(
        id=str(uuid.uuid4()),
        tenant_id=account.tenant_id,
        account_id=account.id,
        subject=subject,
        location=location,
        start_at=start_at,
        end_at=end_at,
        event_timezone="UTC",
        status=status,
        transparency=transparency,
        is_cross_tenant=is_cross_tenant,
        action_payload={},
        is_active=True,
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
    display_name=None,
    role="required_attendee",
    response_status="needs_action",
    is_internal=True,
    resolved_user_id=None,
    resolved_company_entity_id=None,
):
    from app.models.calendar_primitive import CalendarEventAttendee

    att = CalendarEventAttendee(
        id=str(uuid.uuid4()),
        event_id=event.id,
        tenant_id=event.tenant_id,
        email_address=email_address
        or f"a-{uuid.uuid4().hex[:8]}@e.test",
        display_name=display_name,
        role=role,
        response_status=response_status,
        is_internal=is_internal,
        resolved_user_id=resolved_user_id,
        resolved_company_entity_id=resolved_company_entity_id,
    )
    db_session.add(att)
    db_session.flush()
    return att


def make_company_entity(db_session, tenant, *, name=None):
    from app.models import CompanyEntity

    entity = CompanyEntity(
        id=str(uuid.uuid4()),
        company_id=tenant.id,
        name=name or f"Customer {uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    db_session.add(entity)
    db_session.flush()
    return entity


def auth_headers(user, tenant):
    """Return Authorization + X-Company-Slug headers for TestClient calls."""
    from app.core.security import create_access_token

    token = create_access_token({"sub": user.id, "company_id": tenant.id})
    return {
        "Authorization": f"Bearer {token}",
        "X-Company-Slug": tenant.slug,
    }
