"""Health Triage P2 (commit 1): the 3 unwrapped dead-import endpoints.

widget_data inventory + safety widgets and statements/runs/current each held an
in-function import of a non-existent module (app.models.inventory / .safety /
.statement_run) → ImportError → HTTP 500 on every hit. Repointed to the real
models (inventory_item / safety_incident+safety_inspection / statement).

Witness bar per the dispatch: exercise the ACTUAL route — assert it RETURNS
(200) rather than 500. A resolving import is not the witness; the route running
its query against the real schema is.
"""

from __future__ import annotations

import uuid

import pytest


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture
def auth():
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"P2C-{suffix}",
            slug=f"p2c-{suffix}",
            is_active=True,
            vertical="manufacturing",
        )
        db.add(co)
        db.flush()
        role = Role(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name="Admin",
            slug="admin",
            is_system=True,
        )
        db.add(role)
        db.flush()
        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"u-{suffix}@p2c.co",
            first_name="P2",
            last_name="Crasher",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,  # bypass permission gates
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        token = create_access_token({"sub": user.id, "company_id": co.id})
        return {
            "headers": {
                "Authorization": f"Bearer {token}",
                "X-Company-Slug": co.slug,  # tenant resolution (company_resolver)
            }
        }
    finally:
        db.close()


@pytest.mark.parametrize(
    "route",
    [
        "/api/v1/widget-data/inventory/key-items",  # was: app.models.inventory
        "/api/v1/widget-data/safety/dashboard-summary",  # was: app.models.safety
        "/api/v1/statements/runs/current",  # was: app.models.statement_run
    ],
)
def test_repointed_endpoint_returns_not_500(client, auth, route):
    resp = client.get(route, headers=auth["headers"])
    # The witness: the route runs its query against the real schema and returns,
    # where the dead import previously raised ImportError → 500.
    assert resp.status_code == 200, f"{route} → {resp.status_code}: {resp.text[:300]}"
