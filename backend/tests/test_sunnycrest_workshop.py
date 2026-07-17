"""The Sunnycrest Workshop pins.

  * THE SEED IS PRESERVE-AWARE — the operator's authored state survives
    every re-run byte-intact (name, password, module flags); only missing
    rows are backfilled. Hermetic via monkeypatched identifiers.
  * TENANT ADD's COHERENCE GUARD — a tenant add NEVER lands vertical/core:
    the scope is forced server-side; smuggled body fields are dropped.
  * THE LOOP, both directions — a task added tenant-side is fully visible
    admin-side (the destination page's read); an admin edit reflects back
    on the tenant map read.
  * ISOLATION — the loop is per-tenant, never a broadcast.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.company import Company
from app.models.moc_task_catalog import MoCTaskCatalog
from app.models.user import User
from app.services.maps_of_content import task_catalog as task_svc
from app.services.maps_of_content.task_catalog import resolve_task_catalog

VERT = "manufacturing"


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _auth(ctx):
    return {"Authorization": f"Bearer {ctx['token']}", "X-Company-Slug": ctx["slug"]}


def _make_ctx(*, role_slug: str = "admin", vertical: str = VERT):
    from app.core.security import create_access_token
    from app.models.role import Role

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()), name=f"WKSP-{suffix}", slug=f"wksp-{suffix}",
            is_active=True, vertical=vertical,
        )
        db.add(co)
        db.flush()
        role = Role(
            id=str(uuid.uuid4()), company_id=co.id, name=role_slug.title(),
            slug=role_slug, is_system=True,
        )
        db.add(role)
        db.flush()
        user = User(
            id=str(uuid.uuid4()), company_id=co.id,
            email=f"u-{suffix}@wksp.co", first_name="Wksp",
            last_name=role_slug.title(), hashed_password="x",
            is_active=True, role_id=role.id,
        )
        db.add(user)
        db.commit()
        token = create_access_token({"sub": user.id, "company_id": co.id})
        return {"user_id": user.id, "company_id": co.id, "token": token,
                "slug": co.slug}
    finally:
        db.close()


@pytest.fixture(scope="module")
def world():
    a = _make_ctx(role_slug="admin")
    a_office = _make_ctx(role_slug="office")
    b = _make_ctx(role_slug="admin")
    yield {"a": a, "a_office": a_office, "b": b}
    db = SessionLocal()
    for ctx in (a, a_office, b):
        db.execute(sql_text(
            "DELETE FROM moc_task_trigger WHERE task_catalog_id IN "
            "(SELECT id FROM moc_task_catalog WHERE tenant_id = :c)"
        ), {"c": ctx["company_id"]})
        db.execute(sql_text(
            "DELETE FROM moc_task_catalog WHERE tenant_id = :c"
        ), {"c": ctx["company_id"]})
        db.execute(sql_text("DELETE FROM users WHERE company_id = :c"), {"c": ctx["company_id"]})
        db.execute(sql_text("DELETE FROM roles WHERE company_id = :c"), {"c": ctx["company_id"]})
        db.execute(sql_text("DELETE FROM companies WHERE id = :c"), {"c": ctx["company_id"]})
    db.commit()
    db.close()


# ── 1. The seed — preserve-aware, ensure-only ───────────────────────────


class TestSeedPreserveAware:
    def test_authored_state_survives_rerun_and_gaps_backfill(self, monkeypatch):
        import scripts.seed_sunnycrest as seed

        suffix = uuid.uuid4().hex[:6]
        monkeypatch.setattr(seed, "SLUG", f"wksp-seed-{suffix}")
        monkeypatch.setattr(seed, "NAME", "Wksp Seed Co")
        monkeypatch.setattr(seed, "ADMIN_EMAIL", f"wksp-{suffix}@seed.co")

        assert seed.main() == 0  # fresh create
        db = SessionLocal()
        try:
            co = db.query(Company).filter(Company.slug == seed.SLUG).one()
            admin = (
                db.query(User)
                .filter(User.company_id == co.id, User.email == seed.ADMIN_EMAIL)
                .one()
            )
            # THE OPERATOR AUTHORS: rename the company, rotate the password,
            # deliberately disable a module, and lose one module row.
            co.name = "The Operator Renamed It"
            admin.hashed_password = "operator-rotated-hash"
            db.execute(sql_text(
                "UPDATE company_modules SET enabled = false "
                "WHERE company_id = :c AND module = 'sales'"
            ), {"c": co.id})
            db.execute(sql_text(
                "DELETE FROM company_modules WHERE company_id = :c AND module = 'pos'"
            ), {"c": co.id})
            db.commit()

            assert seed.main() == 0  # the boot re-run

            db.expire_all()
            co2 = db.query(Company).filter(Company.slug == seed.SLUG).one()
            assert co2.name == "The Operator Renamed It"          # preserved
            admin2 = db.query(User).filter(User.id == admin.id).one()
            assert admin2.hashed_password == "operator-rotated-hash"  # preserved
            sales = db.execute(sql_text(
                "SELECT enabled FROM company_modules WHERE company_id = :c "
                "AND module = 'sales'"
            ), {"c": co.id}).scalar()
            assert sales is False                                  # HIS flag
            pos = db.execute(sql_text(
                "SELECT enabled FROM company_modules WHERE company_id = :c "
                "AND module = 'pos'"
            ), {"c": co.id}).scalar()
            assert pos is True                                     # gap backfilled
        finally:
            db.execute(sql_text(
                "DELETE FROM company_modules WHERE company_id IN "
                "(SELECT id FROM companies WHERE slug = :s)"
            ), {"s": seed.SLUG})
            db.execute(sql_text(
                "DELETE FROM users WHERE company_id IN "
                "(SELECT id FROM companies WHERE slug = :s)"
            ), {"s": seed.SLUG})
            db.execute(sql_text(
                "DELETE FROM roles WHERE company_id IN "
                "(SELECT id FROM companies WHERE slug = :s)"
            ), {"s": seed.SLUG})
            db.execute(sql_text("DELETE FROM companies WHERE slug = :s"), {"s": seed.SLUG})
            db.commit()
            db.close()


# ── 2. Tenant ADD — the coherence guard ─────────────────────────────────


class TestTenantAdd:
    def test_add_lands_tenant_override_always(self, client, world):
        # Smuggled scope/vertical/tenant_id fields are DROPPED — the server
        # decides. A tenant add can never land vertical/core.
        r = client.post("/api/v1/moc/tasks", headers=_auth(world["a"]), json={
            "name": "Wksp Guard Probe",
            "description": "coherence",
            "scope": "vertical_default",              # smuggled — dropped
            "vertical": "funeral_home",               # smuggled — dropped
            "tenant_id": world["b"]["company_id"],    # smuggled — dropped
        })
        assert r.status_code == 201, r.text
        row = r.json()
        assert row["scope"] == "tenant_override"
        assert row["tenant_id"] == world["a"]["company_id"]

        db = SessionLocal()
        try:
            t = db.get(MoCTaskCatalog, row["id"])
            assert t.scope == "tenant_override"
            assert t.tenant_id == world["a"]["company_id"]
            assert t.vertical == VERT
        finally:
            db.close()

    def test_non_admin_cannot_add(self, client, world):
        r = client.post("/api/v1/moc/tasks", headers=_auth(world["a_office"]),
                        json={"name": "Office Probe"})
        assert r.status_code == 403

    def test_duplicate_name_rejected_honestly(self, client, world):
        client.post("/api/v1/moc/tasks", headers=_auth(world["a"]),
                    json={"name": "Wksp Dup"})
        r = client.post("/api/v1/moc/tasks", headers=_auth(world["a"]),
                        json={"name": "Wksp Dup"})
        assert r.status_code == 400
        assert "already exists" in r.json()["detail"]

    def test_vocabulary_read(self, client, world):
        r = client.get("/api/v1/moc/vocabulary", headers=_auth(world["a_office"]),
                       params={"kind": "type"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ── 3. The loop — tenant-side add, admin-side full function, and back ───


class TestTheLoop:
    def test_tenant_add_visible_and_editable_admin_side_and_back(self, client, world):
        r = client.post("/api/v1/moc/tasks", headers=_auth(world["a"]), json={
            "name": "Wksp Loop Task", "description": "born tenant-side",
        })
        assert r.status_code == 201
        task_id = r.json()["id"]

        # ADMIN SIDE (the destination page's read is resolve_task_catalog
        # with tenant_id): the tenant-created task is there, pilled.
        db = SessionLocal()
        try:
            admin_view = resolve_task_catalog(
                db, vertical=VERT, tenant_id=world["a"]["company_id"]
            )
            mine = next(t for t in admin_view if t["id"] == task_id)
            assert mine["scope"] == "tenant_override"

            # The admin edits on the destination page (the same service the
            # admin router calls)…
            task_svc.patch_task(
                db, task_id=task_id, description="edited admin-side"
            )
            db.commit()
        finally:
            db.close()

        # …and the edit REFLECTS on the tenant map read.
        r2 = client.get("/api/v1/moc/tasks", headers=_auth(world["a"]))
        mine2 = next(t for t in r2.json()["tasks"] if t["id"] == task_id)
        assert mine2["description"] == "edited admin-side"

        # Admin-side triggers + captions work on it (recon-proven; pinned
        # here at the service layer the routes call).
        db = SessionLocal()
        try:
            from app.services.maps_of_content import triggers as triggers_svc

            trig = triggers_svc.add_trigger(
                db, task_catalog_id=task_id, kind="schedule",
                config={"spec_kind": "time_of_day", "time": "07:00"},
            )
            db.commit()
            assert trig.id
        finally:
            db.close()

    def test_isolation_the_loop_is_per_tenant(self, client, world):
        r = client.get("/api/v1/moc/tasks", headers=_auth(world["b"]))
        names = {t["name"] for t in r.json()["tasks"]}
        assert "Wksp Loop Task" not in names
        assert "Wksp Guard Probe" not in names
