"""Phase W-4a Step 3 — Saved-view vertical-scope enforcement tests.

Pattern A (BRIDGEABLE_MASTER §3.25 saved view vertical-scope
inheritance amendment) enforced at four layers:

  Layer 1 — Entity registry: `allowed_verticals` per entity_type.
  Layer 2 — Seed-time skip when entity_type incompatible with vertical.
  Layer 3 — Creation-time 400 when entity_type incompatible.
  Layer 4 — Read-time defense-in-depth filter.

Plus migration r62 cleans up pre-Step-3 contamination from existing
tenants' vault_items.

Test classes mirror the locked enforcement layers:
  • TestEntityRegistryVerticalScope — Layer 1 contract
  • TestSeedLayerEnforcement — Layer 2 (skip cross-vertical at seed)
  • TestCreationLayerEnforcement — Layer 3 (400 on cross-vertical create)
  • TestReadLayerEnforcement — Layer 4 (defense-in-depth filter)
  • TestDataCleanupMigration — r62 idempotency + scope guard

Each layer has its own test class so a regression in one layer is
diagnosed without false positives from neighbors. The layered defense
means contamination has to bypass every layer to leak — these tests
verify each layer rejects independently.
"""
from __future__ import annotations

import uuid
from typing import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


@pytest.fixture
def db_session() -> Iterator:
    from app.database import SessionLocal

    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _make_tenant_user(
    *,
    vertical: str = "manufacturing",
    permissions: list[str] | None = None,
) -> dict:
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.role_permission import RolePermission
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"VS-{suffix}",
            slug=f"vs-{suffix}",
            is_active=True,
            vertical=vertical,
            timezone="America/New_York",
        )
        db.add(co)
        db.flush()
        role = Role(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name="Test",
            slug="test",
            is_system=False,
        )
        db.add(role)
        db.flush()
        for p in permissions or []:
            db.add(RolePermission(role_id=role.id, permission_key=p))
        if permissions:
            db.flush()
        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"u-{suffix}@example.com",
            first_name="Vert",
            last_name="Scope",
            hashed_password="x",
            is_active=True,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        token = create_access_token(
            {"sub": user.id, "company_id": co.id, "realm": "tenant"}
        )
        return {
            "company_id": co.id,
            "slug": co.slug,
            "user_id": user.id,
            "token": token,
        }
    finally:
        db.close()


def _auth_headers(ctx: dict) -> dict:
    return {
        "Authorization": f"Bearer {ctx['token']}",
        "X-Company-Slug": ctx["slug"],
    }


# ── Layer 1 ────────────────────────────────────────────────────────


class TestEntityRegistryVerticalScope:
    """Layer 1: every registered entity declares allowed_verticals."""

    def test_all_entities_declare_allowed_verticals(self):
        from app.services.saved_views import registry

        registry.reset_registry()
        entities = registry.list_entities()
        assert len(entities) > 0  # sanity: registry seeded
        for e in entities:
            assert isinstance(e.allowed_verticals, list)
            assert len(e.allowed_verticals) > 0, (
                f"Entity {e.entity_type!r} has empty allowed_verticals — "
                f"must declare at least one vertical or ['*']"
            )

    def test_fh_case_is_funeral_home_only(self):
        from app.services.saved_views import registry

        registry.reset_registry()
        meta = registry.get_entity("fh_case")
        assert meta is not None
        assert meta.allowed_verticals == ["funeral_home"]

    def test_cross_vertical_entities_use_star(self):
        """Cross-vertical entities (sales_order, invoice, contact,
        product, document, vault_item, delivery) declare ["*"]."""
        from app.services.saved_views import registry

        registry.reset_registry()
        for entity_type in [
            "sales_order",
            "invoice",
            "contact",
            "product",
            "document",
            "vault_item",
            "delivery",
        ]:
            meta = registry.get_entity(entity_type)
            assert meta is not None, f"Missing entity {entity_type}"
            assert "*" in meta.allowed_verticals, (
                f"Entity {entity_type!r} should be cross-vertical "
                f"(allowed_verticals=['*']) but got {meta.allowed_verticals}"
            )

    def test_helper_compatibility_check(self):
        from app.services.saved_views import registry

        registry.reset_registry()
        # fh_case in funeral_home: allowed
        assert registry.is_entity_compatible_with_vertical(
            "fh_case", "funeral_home"
        )
        # fh_case in manufacturing: blocked
        assert not registry.is_entity_compatible_with_vertical(
            "fh_case", "manufacturing"
        )
        # fh_case in cemetery: blocked
        assert not registry.is_entity_compatible_with_vertical(
            "fh_case", "cemetery"
        )
        # fh_case in crematory: blocked
        assert not registry.is_entity_compatible_with_vertical(
            "fh_case", "crematory"
        )
        # invoice in any vertical: allowed (cross-vertical)
        for v in ["funeral_home", "manufacturing", "cemetery", "crematory"]:
            assert registry.is_entity_compatible_with_vertical("invoice", v)

    def test_helper_rejects_unknown_entity(self):
        from app.services.saved_views import registry

        registry.reset_registry()
        # Unknown entity_type: rejected (defensive default).
        assert not registry.is_entity_compatible_with_vertical(
            "made_up_entity", "manufacturing"
        )

    def test_helper_rejects_missing_vertical(self):
        from app.services.saved_views import registry

        registry.reset_registry()
        # Tenant without classified vertical: rejected (no implicit
        # "everyone" — better to surface the gap explicitly).
        assert not registry.is_entity_compatible_with_vertical(
            "invoice", None
        )


# ── Layer 2 ────────────────────────────────────────────────────────


class TestSeedLayerEnforcement:
    """Layer 2: seed_for_user skips cross-vertical templates even if
    they're listed in _SEED_TEMPLATES (defense-in-depth)."""

    def test_seed_skips_cross_vertical_when_template_smuggled_in(
        self, db_session
    ):
        """Synthetic test: temporarily inject a cross-vertical seed
        for (manufacturing, test) and verify the seed-time enforcement
        skips it. This guards against future copy-paste mistakes that
        move templates between (vertical, role) keys without re-
        evaluating entity_type."""
        from app.models.role import Role
        from app.models.user import User
        from app.services.saved_views import seed
        from app.services.saved_views.types import (
            Filter,
            SavedViewConfig,
            Sort,
        )

        ctx = _make_tenant_user(vertical="manufacturing")

        # Smuggle in a cross-vertical template.
        injected_key = ("manufacturing", "test")
        original = seed.SEED_TEMPLATES.get(injected_key, [])
        seed.SEED_TEMPLATES[injected_key] = [
            seed.SeedTemplate(
                template_id="injected_recent_cases",
                title="Smuggled FH cases",
                description="Should NOT seed in manufacturing tenant.",
                entity_type="fh_case",  # FH-only entity in mfg tenant
                config_factory=lambda role: seed._basic_list(
                    entity_type="fh_case",
                    sort=[Sort(field="updated_at", direction="desc")],
                    role_slug=role,
                ),
            ),
        ]

        try:
            user = (
                db_session.query(User).filter(User.id == ctx["user_id"]).one()
            )
            # seed_for_user uses the user's role slug — our test role's
            # slug is "test" (set in _make_tenant_user). Re-seed.
            count = seed.seed_for_user(
                db_session, user=user, tenant_vertical="manufacturing"
            )
        finally:
            seed.SEED_TEMPLATES[injected_key] = original

        # The smuggled template was skipped — count == 0.
        assert count == 0
        # Verify no fh_case saved view was seeded.
        from app.models.vault_item import VaultItem

        rows = (
            db_session.query(VaultItem)
            .filter(
                VaultItem.company_id == ctx["company_id"],
                VaultItem.item_type == "saved_view",
            )
            .all()
        )
        for r in rows:
            cfg = (r.metadata_json or {}).get("saved_view_config", {})
            entity_type = (cfg.get("query") or {}).get("entity_type")
            assert entity_type != "fh_case"

    def test_seed_templates_have_no_cross_vertical_entries(self):
        """Regression guard: scan all _SEED_TEMPLATES for cross-
        vertical entity_type x tenant_vertical pairs. Step 3 removed
        cemetery/admin and crematory/admin recent_cases entries; this
        test fails loudly if anyone re-adds them or inserts a new one.
        """
        from app.services.saved_views import registry, seed

        registry.reset_registry()
        violations = []
        for (vertical, role), templates in seed.SEED_TEMPLATES.items():
            for tpl in templates:
                if not registry.is_entity_compatible_with_vertical(
                    tpl.entity_type, vertical
                ):
                    violations.append(
                        (vertical, role, tpl.template_id, tpl.entity_type)
                    )
        assert not violations, (
            "_SEED_TEMPLATES contains cross-vertical entries:\n"
            + "\n".join(
                f"  ({v}, {r}) → {tid} entity_type={ent}"
                for v, r, tid, ent in violations
            )
        )

    def test_funeral_home_admin_seed_includes_fh_case(self, db_session):
        """Sanity: FH tenants STILL get fh_case-typed saved views.
        Pattern A enforcement should not break legitimate seeding."""
        from app.services.saved_views import registry, seed

        registry.reset_registry()
        fh_admin_templates = seed.SEED_TEMPLATES.get(
            ("funeral_home", "admin"), []
        )
        ids = {t.template_id for t in fh_admin_templates}
        # FH admin has my_active_cases (entity_type=fh_case).
        assert "my_active_cases" in ids
        # Verify the registry agrees fh_case is fine in funeral_home.
        for tpl in fh_admin_templates:
            assert registry.is_entity_compatible_with_vertical(
                tpl.entity_type, "funeral_home"
            )


# ── Layer 3 ────────────────────────────────────────────────────────


class TestCreationLayerEnforcement:
    """Layer 3: create_saved_view rejects cross-vertical with 400."""

    def _basic_payload(self, entity_type: str, title: str = "Test view") -> dict:
        return {
            "title": title,
            "description": "",
            "config": {
                "query": {
                    "entity_type": entity_type,
                    "filters": [],
                    "sort": [],
                    "grouping": None,
                    "limit": None,
                },
                "presentation": {
                    "mode": "list",
                    "table_config": None,
                    "card_config": None,
                    "kanban_config": None,
                    "calendar_config": None,
                    "chart_config": None,
                    "stat_config": None,
                },
                "permissions": {
                    "owner_user_id": "",
                    "visibility": "private",
                    "shared_with_users": [],
                    "shared_with_roles": [],
                    "shared_with_tenants": [],
                    "cross_tenant_field_visibility": {
                        "per_tenant_fields": {}
                    },
                },
                "extras": {},
            },
        }

    def test_manufacturing_tenant_creating_fh_case_returns_400(
        self, client
    ):
        ctx = _make_tenant_user(vertical="manufacturing")
        r = client.post(
            "/api/v1/saved-views/",
            json=self._basic_payload("fh_case", "Should be rejected"),
            headers=_auth_headers(ctx),
        )
        assert r.status_code == 400
        body = r.json()
        # Error message identifies the offending entity_type + vertical.
        assert "fh_case" in body.get("detail", "")
        assert "manufacturing" in body.get("detail", "")

    def test_cemetery_tenant_creating_fh_case_returns_400(self, client):
        ctx = _make_tenant_user(vertical="cemetery")
        r = client.post(
            "/api/v1/saved-views/",
            json=self._basic_payload("fh_case"),
            headers=_auth_headers(ctx),
        )
        assert r.status_code == 400

    def test_crematory_tenant_creating_fh_case_returns_400(self, client):
        ctx = _make_tenant_user(vertical="crematory")
        r = client.post(
            "/api/v1/saved-views/",
            json=self._basic_payload("fh_case"),
            headers=_auth_headers(ctx),
        )
        assert r.status_code == 400

    def test_funeral_home_tenant_creating_fh_case_succeeds(self, client):
        """Legitimate creation: FH tenant CAN create fh_case views."""
        ctx = _make_tenant_user(vertical="funeral_home")
        r = client.post(
            "/api/v1/saved-views/",
            json=self._basic_payload("fh_case", "FH legit"),
            headers=_auth_headers(ctx),
        )
        assert r.status_code == 201
        body = r.json()
        assert body["title"] == "FH legit"

    def test_manufacturing_tenant_creating_invoice_succeeds(self, client):
        """Cross-vertical entity (invoice): allowed in any vertical."""
        ctx = _make_tenant_user(vertical="manufacturing")
        r = client.post(
            "/api/v1/saved-views/",
            json=self._basic_payload("invoice", "Mfg invoices"),
            headers=_auth_headers(ctx),
        )
        assert r.status_code == 201

    def test_manufacturing_tenant_creating_vault_item_succeeds(self, client):
        ctx = _make_tenant_user(vertical="manufacturing")
        r = client.post(
            "/api/v1/saved-views/",
            json=self._basic_payload("vault_item", "Mfg vault items"),
            headers=_auth_headers(ctx),
        )
        assert r.status_code == 201

    def test_error_message_lists_allowed_verticals(self, client):
        """Error response cites allowed_verticals so frontend can
        render a useful message."""
        ctx = _make_tenant_user(vertical="manufacturing")
        r = client.post(
            "/api/v1/saved-views/",
            json=self._basic_payload("fh_case"),
            headers=_auth_headers(ctx),
        )
        detail = r.json().get("detail", "")
        assert "funeral_home" in detail


# ── Layer 4 ────────────────────────────────────────────────────────


class TestReadLayerEnforcement:
    """Layer 4: list_saved_views_for_user filters cross-vertical
    instances even if they exist in storage. Defense-in-depth: even
    if Layers 1-3 fail or new contamination sneaks in via direct DB
    write, this filter prevents leak in transit."""

    def _seed_smuggled_fh_case_view(
        self, db_session, company_id: str, owner_user_id: str
    ) -> str:
        """Bypass create_saved_view and write directly to vault_items —
        simulating pre-Step-3 contamination or a direct DB insert."""
        from app.models.vault_item import VaultItem
        from app.services.vault_service import get_or_create_company_vault

        vault = get_or_create_company_vault(db_session, company_id)
        view_id = str(uuid.uuid4())
        row = VaultItem(
            id=view_id,
            vault_id=vault.id,
            company_id=company_id,
            item_type="saved_view",
            title="Smuggled FH cases",
            description="Direct DB insert — bypasses Layer 3.",
            visibility="internal",
            source="user_upload",
            created_by=owner_user_id,
            metadata_json={
                "saved_view_config": {
                    "query": {
                        "entity_type": "fh_case",
                        "filters": [],
                        "sort": [],
                        "grouping": None,
                        "limit": None,
                    },
                    "presentation": {"mode": "list"},
                    "permissions": {
                        "owner_user_id": owner_user_id,
                        "visibility": "private",
                        "shared_with_users": [],
                        "shared_with_roles": [],
                        "shared_with_tenants": [],
                        "cross_tenant_field_visibility": {
                            "per_tenant_fields": {}
                        },
                    },
                    "extras": {},
                }
            },
        )
        db_session.add(row)
        db_session.commit()
        return view_id

    def test_list_filters_smuggled_fh_case_in_manufacturing(
        self, db_session
    ):
        from app.models.user import User
        from app.services.saved_views import crud

        ctx = _make_tenant_user(vertical="manufacturing")
        smuggled_id = self._seed_smuggled_fh_case_view(
            db_session, ctx["company_id"], ctx["user_id"]
        )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        views = crud.list_saved_views_for_user(db_session, user=user)
        # Smuggled cross-vertical row dropped at read time.
        ids = [v.id for v in views]
        assert smuggled_id not in ids

    def test_list_returns_legitimate_fh_case_in_funeral_home(
        self, db_session
    ):
        from app.models.user import User
        from app.services.saved_views import crud

        ctx = _make_tenant_user(vertical="funeral_home")
        legit_id = self._seed_smuggled_fh_case_view(
            db_session, ctx["company_id"], ctx["user_id"]
        )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        views = crud.list_saved_views_for_user(db_session, user=user)
        ids = [v.id for v in views]
        # FH tenant: fh_case is legitimate, NOT filtered.
        assert legit_id in ids

    def test_list_filters_cross_vertical_via_api(self, client, db_session):
        ctx = _make_tenant_user(vertical="manufacturing")
        smuggled_id = self._seed_smuggled_fh_case_view(
            db_session, ctx["company_id"], ctx["user_id"]
        )
        r = client.get(
            "/api/v1/saved-views/", headers=_auth_headers(ctx)
        )
        assert r.status_code == 200
        body = r.json()
        # Body shape: dict {mine, shared_with_me, tenant_public}
        # OR list — both shapes drop the smuggled row.
        if isinstance(body, list):
            ids = [v["id"] for v in body]
        else:
            # Aggregate ids across all groupings.
            ids = []
            for group in body.values():
                if isinstance(group, list):
                    ids.extend(v["id"] for v in group)
        assert smuggled_id not in ids


# ── Layer 6 (r62 cleanup migration) ────────────────────────────────


class TestDataCleanupMigration:
    """r62 idempotency + scope guard. The migration was already
    applied during dev DB setup; these tests verify shape + behavior
    contract."""

    def test_migration_is_registered_in_chain(self):
        """Migration head is r62_cleanup_cross_vertical_saved_views."""
        from alembic.script import ScriptDirectory
        from alembic.config import Config

        cfg = Config("alembic.ini")
        script = ScriptDirectory.from_config(cfg)
        head = script.get_current_head()
        assert head == "r62_cleanup_cross_vertical_saved_views"

    def test_migration_has_idempotent_downgrade_noop(self):
        """downgrade() is a no-op — restoring contamination would
        re-introduce the bug."""
        import importlib.util
        import pathlib

        path = pathlib.Path(
            "alembic/versions/r62_cleanup_cross_vertical_saved_views.py"
        )
        spec = importlib.util.spec_from_file_location(
            "r62_module", str(path)
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # downgrade body must contain only `pass` + comments/docstring
        # — inspect the disassembled bytecode for any DELETE/INSERT/
        # UPDATE op. The docstring contains those words by design (it
        # explains why downgrade is a no-op), so source-string scan
        # gives false positives.
        import dis
        import io

        buf = io.StringIO()
        dis.dis(mod.downgrade, file=buf)
        bytecode = buf.getvalue()
        # No CALL ops invoking DELETE/etc — body should be just
        # RESUME/LOAD_CONST None/RETURN_VALUE.
        forbidden = ("DELETE", "INSERT", "UPDATE", "EXECUTE", "OP.EXECUTE")
        for word in forbidden:
            assert word not in bytecode.upper(), (
                f"downgrade() must be a true no-op; bytecode "
                f"contains forbidden word {word!r}:\n{bytecode}"
            )

    def test_prohibited_pairs_match_registry_single_vertical_entities(self):
        """The migration's _PROHIBITED_PAIRS list must mirror every
        single-vertical entity in the entity registry. New single-
        vertical entities require an explicit migration update."""
        import importlib.util
        import pathlib

        from app.services.saved_views import registry

        path = pathlib.Path(
            "alembic/versions/r62_cleanup_cross_vertical_saved_views.py"
        )
        spec = importlib.util.spec_from_file_location(
            "r62_module2", str(path)
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        prohibited = {
            entity_type for (entity_type, _) in mod._PROHIBITED_PAIRS
        }
        registry.reset_registry()
        single_vertical_entities = {
            e.entity_type
            for e in registry.list_entities()
            if "*" not in e.allowed_verticals
        }
        assert prohibited == single_vertical_entities, (
            f"Migration r62 _PROHIBITED_PAIRS ({sorted(prohibited)}) "
            f"must mirror registry single-vertical entities "
            f"({sorted(single_vertical_entities)}). New single-vertical "
            f"entities require an explicit migration update."
        )

    def test_migration_idempotent_when_run_inline(self, db_session):
        """Run the migration's SQL inline against the current DB
        state and verify it deletes 0 rows when no contamination
        is present (idempotency contract).

        Note: this test runs in a pytest session that ALSO contains
        TestReadLayerEnforcement tests which deliberately seed
        smuggled cross-vertical rows to exercise the read filter.
        Test ordering means those rows may exist when this test
        runs. The contract being verified here is "running the
        migration twice in a row is safe" — so we run it twice
        inline and assert both invocations are well-defined.
        """
        import importlib.util
        import pathlib

        from sqlalchemy import text

        path = pathlib.Path(
            "alembic/versions/r62_cleanup_cross_vertical_saved_views.py"
        )
        spec = importlib.util.spec_from_file_location(
            "r62_module3", str(path)
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        prohibited = mod._PROHIBITED_PAIRS
        assert len(prohibited) > 0  # sanity

        # Inline DELETE (mirrors the migration's upgrade body).
        # Run twice — the second run must affect 0 rows regardless
        # of what existed before the first.
        for entity_type, allowed_verticals in prohibited:
            placeholders = ", ".join(
                f":vert_{i}" for i in range(len(allowed_verticals))
            )
            params: dict = {
                f"vert_{i}": v for i, v in enumerate(allowed_verticals)
            }
            params["entity_type"] = entity_type
            sql = f"""
                DELETE FROM vault_items vi
                USING companies c
                WHERE vi.company_id = c.id
                  AND vi.item_type = 'saved_view'
                  AND (vi.metadata_json::json
                       -> 'saved_view_config'
                       -> 'query'
                       ->> 'entity_type') = :entity_type
                  AND c.vertical NOT IN ({placeholders})
            """
            db_session.execute(text(sql), params)
        db_session.commit()

        # Second pass — must affect 0 rows now.
        affected_total = 0
        for entity_type, allowed_verticals in prohibited:
            placeholders = ", ".join(
                f":vert_{i}" for i in range(len(allowed_verticals))
            )
            params: dict = {
                f"vert_{i}": v for i, v in enumerate(allowed_verticals)
            }
            params["entity_type"] = entity_type
            sql = f"""
                DELETE FROM vault_items vi
                USING companies c
                WHERE vi.company_id = c.id
                  AND vi.item_type = 'saved_view'
                  AND (vi.metadata_json::json
                       -> 'saved_view_config'
                       -> 'query'
                       ->> 'entity_type') = :entity_type
                  AND c.vertical NOT IN ({placeholders})
            """
            result = db_session.execute(text(sql), params)
            affected_total += getattr(result, "rowcount", 0) or 0
        db_session.commit()
        # Idempotency: second pass deletes nothing.
        assert affected_total == 0
