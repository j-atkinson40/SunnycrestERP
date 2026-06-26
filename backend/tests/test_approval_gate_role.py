"""Health Triage P2: approval-email `admin.role` AttributeError.

approval_gate.py:80 accessed `admin.role` to gate accounting-admin recipients.
User has `role_id` + the `role_obj` relationship, NOT `.role` → AttributeError
every approval-email send (~every 15 min in the log). Fix: `.role` → `.role_obj`.
This pins both directions: `role_obj.slug` resolves, and `.role` genuinely
does not exist on User (so the old code could only have raised).
"""

from __future__ import annotations

import uuid

import pytest

from app.database import SessionLocal
from app.models.company import Company
from app.models.role import Role
from app.models.user import User


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


def _user_with_role(db, slug: str):
    suffix = uuid.uuid4().hex[:6]
    co = Company(
        id=str(uuid.uuid4()),
        name=f"P2-{suffix}",
        slug=f"p2-{suffix}",
        is_active=True,
        vertical="manufacturing",
    )
    db.add(co)
    db.commit()
    role = Role(
        id=str(uuid.uuid4()),
        company_id=co.id,
        name=slug.title(),
        slug=slug,
    )
    db.add(role)
    db.commit()
    user = User(
        id=str(uuid.uuid4()),
        company_id=co.id,
        email=f"{suffix}@example.com",
        hashed_password="x",
        first_name="Acc",
        last_name="Admin",
        role_id=role.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


def test_role_obj_resolves_and_role_attr_absent(db):
    user = _user_with_role(db, "accounting")
    # The fix: role_obj resolves to the Role (the gate checks .slug).
    assert user.role_obj is not None
    assert user.role_obj.slug == "accounting"
    # The bug, pinned: User has no `.role` — the old access could only raise.
    assert not hasattr(user, "role")
