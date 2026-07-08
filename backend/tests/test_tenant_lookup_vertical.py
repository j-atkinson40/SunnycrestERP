"""P-1 (FH map stamp, commit 1) — tenant_lookup's server-side vertical filter.

The MoC Tenants card filtered by vertical CLIENT-SIDE over a 100-row
cross-vertical page: on a vertical with sparse alphabetical presence the
default list rendered near-empty while thousands of its tenants existed
(FH: 9.8k tenants, Hopkins reachable only by search). Pin BOTH directions:
an FH-filtered lookup returns only FH tenants; a manufacturing-filtered
lookup only manufacturing.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.database import SessionLocal
from app.models.company import Company
from app.models.platform_user import PlatformUser


@pytest.fixture
def ctx():
    s = SessionLocal()
    suffix = uuid.uuid4().hex[:6]
    admin = PlatformUser(
        id=str(uuid.uuid4()), email=f"p1-{suffix}@bridgeable.test",
        hashed_password="x", first_name="P", last_name="1",
        role="super_admin", is_active=True,
    )
    fh = Company(id=str(uuid.uuid4()), name=f"AAA P1 FH {suffix}",
                 slug=f"p1-fh-{suffix}", is_active=True, vertical="funeral_home")
    mfg = Company(id=str(uuid.uuid4()), name=f"AAA P1 MFG {suffix}",
                  slug=f"p1-mfg-{suffix}", is_active=True, vertical="manufacturing")
    s.add_all([admin, fh, mfg])
    s.commit()
    token = create_access_token({"sub": admin.id}, realm="platform")
    yield {"headers": {"Authorization": f"Bearer {token}"}, "suffix": suffix,
           "fh": fh, "mfg": mfg}
    for row in (fh, mfg, admin):
        s.delete(row)
    s.commit()
    s.close()


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


def test_lookup_filters_fh_server_side(client, ctx):
    r = client.get(
        "/api/platform/admin/tenants/lookup",
        params={"q": ctx["suffix"], "vertical": "funeral_home", "limit": 100},
        headers=ctx["headers"],
    )
    assert r.status_code == 200
    rows = [t for t in r.json() if ctx["suffix"] in t["slug"]]
    assert [t["slug"] for t in rows] == [ctx["fh"].slug]     # FH only
    assert all(t["vertical"] == "funeral_home" for t in r.json())


def test_lookup_filters_manufacturing_server_side(client, ctx):
    r = client.get(
        "/api/platform/admin/tenants/lookup",
        params={"q": ctx["suffix"], "vertical": "manufacturing", "limit": 100},
        headers=ctx["headers"],
    )
    assert r.status_code == 200
    rows = [t for t in r.json() if ctx["suffix"] in t["slug"]]
    assert [t["slug"] for t in rows] == [ctx["mfg"].slug]    # MFG only
    assert all(t["vertical"] == "manufacturing" for t in r.json())


def test_lookup_without_vertical_unchanged(client, ctx):
    """The pre-P-1 callers (Visual Editor pickers) see no behavior change."""
    r = client.get(
        "/api/platform/admin/tenants/lookup",
        params={"q": ctx["suffix"], "limit": 100},
        headers=ctx["headers"],
    )
    assert r.status_code == 200
    slugs = {t["slug"] for t in r.json() if ctx["suffix"] in t["slug"]}
    assert slugs == {ctx["fh"].slug, ctx["mfg"].slug}        # both verticals
