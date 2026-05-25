"""Task substrate v1 — shared test fixtures."""

from __future__ import annotations

import uuid

import pytest


def _make_ctx(
    *,
    role_slug: str = "admin",
    vertical: str = "manufacturing",
):
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"TS-{suffix}",
            slug=f"ts-{suffix}",
            is_active=True,
            vertical=vertical,
        )
        db.add(co)
        db.flush()
        role = Role(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name=role_slug.title(),
            slug=role_slug,
            is_system=True,
        )
        db.add(role)
        db.flush()
        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"u-{suffix}@ts.co",
            first_name="TS",
            last_name="User",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        return {
            "company_id": co.id,
            "user_id": user.id,
            "slug": co.slug,
            "role_id": role.id,
        }
    finally:
        db.close()


@pytest.fixture
def ts_ctx():
    """Task-substrate test context: tenant + admin user."""
    return _make_ctx(role_slug="admin", vertical="manufacturing")


@pytest.fixture
def ts_ctx_fh():
    return _make_ctx(role_slug="director", vertical="funeral_home")


@pytest.fixture
def db_session():
    from app.database import SessionLocal
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()
