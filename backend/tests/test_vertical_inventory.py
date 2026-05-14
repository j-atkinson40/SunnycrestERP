"""Studio 1a-ii — Vertical Inventory service + API tests (B-2 rewrite).

Covers:
  - Section counts correct for platform vs vertical scope
  - Sections without backend source (registry, plugin-registry under
    vertical scope) report count=None
  - Tables without a `vertical` column (component_class_configurations)
    return zero under vertical scope, full count under platform scope
  - Recent-edits ordering, limit, 7-day window
  - editor_email resolution: User-id-to-email join; None when
    updated_by is NULL or unresolvable; None on document_templates
    (which has no updated_by column)
  - Deep-link path construction (vertical drop on platform-only
    editors; entity-id query param shape)
  - API: 200 platform, 200 vertical, 401 anon/tenant, 404 unknown slug

B-2 update: Focus + edge-panel inventory now anchors on the new
`focus_templates` + `edge_panel_templates` Tier 2 tables (post-r96/r97),
NOT the legacy `focus_compositions` shape. Seed fixtures create rows
against the new substrate.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


def _make_platform_admin() -> dict:
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.platform_user import PlatformUser

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        platform_admin = PlatformUser(
            id=str(uuid.uuid4()),
            email=f"studio-inv-{suffix}@bridgeable.test",
            hashed_password="x",
            first_name="Studio",
            last_name="Inv",
            role="super_admin",
            is_active=True,
        )
        db.add(platform_admin)
        db.commit()
        token = create_access_token(
            {"sub": platform_admin.id}, realm="platform"
        )
        return {
            "platform_id": platform_admin.id,
            "platform_token": token,
        }
    finally:
        db.close()


def _make_tenant_admin() -> dict:
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
            name=f"InvTen {suffix}",
            slug=f"inv-ten-{suffix}",
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
        u = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"ten-inv-{suffix}@inv.test",
            hashed_password="x",
            first_name="T",
            last_name="A",
            role_id=role.id,
            is_active=True,
        )
        db.add(u)
        db.commit()
        token = create_access_token({"sub": u.id}, realm="tenant")
        return {
            "company_id": co.id,
            "user_id": u.id,
            "tenant_token": token,
            "slug": co.slug,
        }
    finally:
        db.close()


# Per-test marker isolating the rows this test inserts so assertions
# can scope to its own data without depending on global DB state.
_TEST_MARKER_PREFIX = "studio-1aii-test"


def _marker() -> str:
    return f"{_TEST_MARKER_PREFIX}-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def seeded_inventory(db_session):
    """Insert a small fixed set of rows across editor tables so the
    service has known data to count + surface.

    Returns dict { 'marker', 'user_id', 'user_email', 'ids' }.
    Cleanup runs on teardown so the test DB stays clean.
    """
    from app.models.component_class_configuration import (
        ComponentClassConfiguration,
    )
    from app.models.component_configuration import ComponentConfiguration
    from app.models.company import Company
    from app.models.document_template import DocumentTemplate
    from app.models.edge_panel_template import EdgePanelTemplate
    from app.models.focus_core import FocusCore
    from app.models.focus_template import FocusTemplate
    from app.models.platform_theme import PlatformTheme
    from app.models.role import Role
    from app.models.user import User
    from app.models.workflow_template import WorkflowTemplate

    marker = _marker()

    user_id = str(uuid.uuid4())
    user_email = f"editor-{marker}@inv.test"
    co = Company(
        id=str(uuid.uuid4()),
        name=f"InvSeed {marker}",
        slug=f"inv-seed-{marker[:12]}",
        is_active=True,
        vertical="manufacturing",
    )
    db_session.add(co)
    db_session.flush()
    role = Role(
        id=str(uuid.uuid4()),
        company_id=co.id,
        name="Admin",
        slug="admin",
        is_system=True,
    )
    db_session.add(role)
    db_session.flush()
    user = User(
        id=user_id,
        company_id=co.id,
        email=user_email,
        hashed_password="x",
        first_name="E",
        last_name="D",
        role_id=role.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    now = datetime.now(timezone.utc)

    # 2 themes — 1 manufacturing-vertical (with editor), 1 funeral_home
    # (without editor — exercises updated_by=NULL email resolution).
    t1 = PlatformTheme(
        id=str(uuid.uuid4()),
        scope="vertical_default",
        vertical="manufacturing",
        mode="light",
        token_overrides={"_marker": marker, "accent": "#aaa"},
        is_active=True,
        updated_at=now - timedelta(minutes=10),
        updated_by=user_id,
    )
    t2 = PlatformTheme(
        id=str(uuid.uuid4()),
        scope="vertical_default",
        vertical="funeral_home",
        mode="light",
        token_overrides={"_marker": marker},
        is_active=True,
        updated_at=now - timedelta(minutes=20),
        updated_by=None,
    )
    db_session.add_all([t1, t2])

    # Tier 1 Focus Core (single shared core for both templates).
    core = FocusCore(
        id=str(uuid.uuid4()),
        core_slug=f"core-{marker[:8]}",
        display_name=f"Core {marker[:8]}",
        registered_component_kind="focus-core",
        registered_component_name=f"Core{marker[:8]}",
        default_starting_column=0,
        default_column_span=12,
        default_row_index=0,
        min_column_span=6,
        max_column_span=12,
        canvas_config={},
        is_active=True,
    )
    db_session.add(core)
    db_session.flush()

    # 1 Focus template — manufacturing vertical
    ft_mfg = FocusTemplate(
        id=str(uuid.uuid4()),
        scope="vertical_default",
        vertical="manufacturing",
        template_slug=f"scheduling-{marker[:8]}",
        display_name=f"Scheduling {marker[:8]}",
        inherits_from_core_id=core.id,
        inherits_from_core_version=core.version,
        rows=[],
        canvas_config={"_marker": marker},
        is_active=True,
        updated_at=now - timedelta(minutes=5),
        updated_by=user_id,
    )
    db_session.add(ft_mfg)

    # 1 Edge-panel template — manufacturing vertical
    ep_mfg = EdgePanelTemplate(
        id=str(uuid.uuid4()),
        scope="vertical_default",
        vertical="manufacturing",
        panel_key=f"panel-{marker[:8]}",
        display_name=f"Panel {marker[:8]}",
        pages=[],
        canvas_config={"_marker": marker},
        is_active=True,
        updated_at=now - timedelta(minutes=3),
        updated_by=user_id,
    )
    db_session.add(ep_mfg)

    # 1 widget config (component_configurations, kind=widget) mfg
    cc1 = ComponentConfiguration(
        id=str(uuid.uuid4()),
        scope="vertical_default",
        vertical="manufacturing",
        component_kind="widget",
        component_name=f"today_{marker[:8]}",
        prop_overrides={"_marker": marker},
        is_active=True,
        updated_at=now - timedelta(minutes=2),
        updated_by=user_id,
    )
    # Non-widget kind to confirm we don't count it for widgets section
    cc2 = ComponentConfiguration(
        id=str(uuid.uuid4()),
        scope="vertical_default",
        vertical="manufacturing",
        component_kind="entity-card",
        component_name=f"case_card_{marker[:8]}",
        prop_overrides={"_marker": marker},
        is_active=True,
        updated_at=now - timedelta(minutes=1),
        updated_by=user_id,
    )
    db_session.add_all([cc1, cc2])

    ccc = ComponentClassConfiguration(
        id=str(uuid.uuid4()),
        component_class="surface-card",
        prop_overrides={"_marker": marker},
        is_active=True,
        updated_at=now - timedelta(minutes=4),
        updated_by=user_id,
    )
    db_session.add(ccc)

    wt = WorkflowTemplate(
        id=str(uuid.uuid4()),
        scope="vertical_default",
        vertical="manufacturing",
        workflow_type=f"wf_{marker[:8]}",
        display_name=f"WF {marker[:8]}",
        canvas_state={"_marker": marker, "nodes": [], "edges": []},
        is_active=True,
        updated_at=now - timedelta(minutes=8),
        updated_by=user_id,
    )
    db_session.add(wt)

    dt = DocumentTemplate(
        id=str(uuid.uuid4()),
        template_key=f"tpl_{marker[:8]}",
        document_type="invoice",
        vertical="manufacturing",
        output_format="html",
        is_active=True,
        updated_at=now - timedelta(minutes=6),
    )
    db_session.add(dt)

    # An OLD theme outside the 7-day window — must NOT appear in
    # recent_edits, but must be counted (still active).
    t_old = PlatformTheme(
        id=str(uuid.uuid4()),
        scope="vertical_default",
        vertical="manufacturing",
        mode="dark",
        token_overrides={"_marker": marker, "stale": True},
        is_active=True,
        updated_at=now - timedelta(days=30),
        updated_by=user_id,
    )
    db_session.add(t_old)

    db_session.commit()

    yield {
        "marker": marker,
        "user_id": user_id,
        "user_email": user_email,
        "ids": {
            "themes_recent": [t1.id, t2.id],
            "themes_old": [t_old.id],
            "focuses": [ft_mfg.id],
            "edge_panels": [ep_mfg.id],
            "widgets": [cc1.id],
            "classes": [ccc.id],
            "workflows": [wt.id],
            "documents": [dt.id],
        },
    }

    # ─── Cleanup ─────────────────────────────────────────
    db_session.rollback()
    for model_name, id_list in [
        (PlatformTheme, [t1.id, t2.id, t_old.id]),
        (FocusTemplate, [ft_mfg.id]),
        (EdgePanelTemplate, [ep_mfg.id]),
        (FocusCore, [core.id]),
        (ComponentConfiguration, [cc1.id, cc2.id]),
        (ComponentClassConfiguration, [ccc.id]),
        (WorkflowTemplate, [wt.id]),
        (DocumentTemplate, [dt.id]),
    ]:
        for row_id in id_list:
            row = db_session.get(model_name, row_id)
            if row is not None:
                db_session.delete(row)
    db_session.delete(user)
    db_session.delete(role)
    db_session.delete(co)
    db_session.commit()


# ─── Service-layer tests ──────────────────────────────────────


class TestSections:
    def test_response_shape(self, db_session, seeded_inventory):
        from app.services.vertical_inventory import get_inventory

        resp = get_inventory(db_session, vertical_slug=None)
        assert resp.scope == "platform"
        assert resp.vertical_slug is None
        assert isinstance(resp.sections, list)
        keys = [s.key for s in resp.sections]
        assert keys == [
            "themes",
            "focuses",
            "widgets",
            "documents",
            "classes",
            "workflows",
            "edge-panels",
            "registry",
            "plugin-registry",
        ]

    def test_vertical_scope_filters(self, db_session, seeded_inventory):
        from app.services.vertical_inventory import get_inventory

        mfg = get_inventory(db_session, vertical_slug="manufacturing")
        fh = get_inventory(db_session, vertical_slug="funeral_home")
        counts_mfg = {s.key: s.count for s in mfg.sections}
        counts_fh = {s.key: s.count for s in fh.sections}

        assert counts_mfg["themes"] >= 2
        assert counts_mfg["focuses"] >= 1
        assert counts_mfg["edge-panels"] >= 1
        assert counts_mfg["widgets"] >= 1
        assert counts_mfg["workflows"] >= 1
        assert counts_mfg["documents"] >= 1

        assert counts_fh["themes"] >= 1
        assert counts_mfg["themes"] > counts_fh["themes"]

    def test_classes_zero_under_vertical_scope(
        self, db_session, seeded_inventory
    ):
        from app.services.vertical_inventory import get_inventory

        platform_resp = get_inventory(db_session, vertical_slug=None)
        vertical_resp = get_inventory(
            db_session, vertical_slug="manufacturing"
        )
        platform_counts = {s.key: s.count for s in platform_resp.sections}
        vertical_counts = {s.key: s.count for s in vertical_resp.sections}

        assert platform_counts["classes"] is not None
        assert platform_counts["classes"] >= 1
        assert vertical_counts["classes"] == 0

    def test_registry_count_always_none(self, db_session):
        from app.services.vertical_inventory import get_inventory

        platform_resp = get_inventory(db_session, vertical_slug=None)
        vertical_resp = get_inventory(
            db_session, vertical_slug="manufacturing"
        )
        platform_count = next(
            s.count for s in platform_resp.sections if s.key == "registry"
        )
        vertical_count = next(
            s.count for s in vertical_resp.sections if s.key == "registry"
        )
        assert platform_count is None
        assert vertical_count is None

    def test_plugin_registry_count_platform_vs_vertical(
        self, db_session
    ):
        from app.services.vertical_inventory import get_inventory
        from app.services.plugin_registry import list_category_keys

        platform_resp = get_inventory(db_session, vertical_slug=None)
        vertical_resp = get_inventory(
            db_session, vertical_slug="manufacturing"
        )
        platform_count = next(
            s.count
            for s in platform_resp.sections
            if s.key == "plugin-registry"
        )
        vertical_count = next(
            s.count
            for s in vertical_resp.sections
            if s.key == "plugin-registry"
        )
        assert platform_count == len(list_category_keys())
        assert vertical_count is None

    def test_widgets_section_filters_by_component_kind(
        self, db_session, seeded_inventory
    ):
        from app.services.vertical_inventory import get_inventory

        resp = get_inventory(db_session, vertical_slug="manufacturing")
        widgets = next(s for s in resp.sections if s.key == "widgets")
        assert widgets.count is not None
        assert widgets.count >= 1


class TestRecentEdits:
    def test_window_excludes_old(self, db_session, seeded_inventory):
        from app.services.vertical_inventory import get_inventory

        resp = get_inventory(db_session, vertical_slug="manufacturing")
        edited_entity_ids = {e.entity_id for e in resp.recent_edits}
        old_id = seeded_inventory["ids"]["themes_old"][0]
        assert old_id not in edited_entity_ids

    def test_ordering_desc_by_edited_at(
        self, db_session, seeded_inventory
    ):
        from app.services.vertical_inventory import get_inventory

        resp = get_inventory(db_session, vertical_slug="manufacturing")
        timestamps = [e.edited_at for e in resp.recent_edits]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_limit_at_most_10(self, db_session, seeded_inventory):
        from app.services.vertical_inventory import get_inventory

        resp = get_inventory(db_session, vertical_slug="manufacturing")
        assert len(resp.recent_edits) <= 10

    def test_editor_email_resolved_when_user_present(
        self, db_session, seeded_inventory
    ):
        from app.services.vertical_inventory import get_inventory

        resp = get_inventory(db_session, vertical_slug="manufacturing")
        widget_id = seeded_inventory["ids"]["widgets"][0]
        widget_edit = next(
            (e for e in resp.recent_edits if e.entity_id == widget_id),
            None,
        )
        assert widget_edit is not None
        assert widget_edit.editor_email == seeded_inventory["user_email"]

    def test_editor_email_none_when_updated_by_null(
        self, db_session, seeded_inventory
    ):
        from app.services.vertical_inventory import get_inventory

        resp = get_inventory(db_session, vertical_slug="funeral_home")
        fh_theme_id = seeded_inventory["ids"]["themes_recent"][1]
        match = next(
            (e for e in resp.recent_edits if e.entity_id == fh_theme_id),
            None,
        )
        assert match is not None
        assert match.editor_email is None

    def test_editor_email_none_on_documents(
        self, db_session, seeded_inventory
    ):
        from app.services.vertical_inventory import get_inventory

        resp = get_inventory(db_session, vertical_slug="manufacturing")
        docs = [e for e in resp.recent_edits if e.section == "documents"]
        for e in docs:
            assert e.editor_email is None

    def test_edge_panel_section_distinct_from_focuses(
        self, db_session, seeded_inventory
    ):
        """Edge-panel templates surface as section='edge-panels'; focus
        templates as section='focuses'."""
        from app.services.vertical_inventory import get_inventory

        resp = get_inventory(db_session, vertical_slug="manufacturing")
        edge_id = seeded_inventory["ids"]["edge_panels"][0]
        focus_id = seeded_inventory["ids"]["focuses"][0]

        edge_entry = next(
            (e for e in resp.recent_edits if e.entity_id == edge_id),
            None,
        )
        focus_entry = next(
            (e for e in resp.recent_edits if e.entity_id == focus_id),
            None,
        )
        assert edge_entry is not None
        assert edge_entry.section == "edge-panels"
        assert focus_entry is not None
        assert focus_entry.section == "focuses"


class TestDeepLink:
    def test_platform_scope_no_vertical(
        self, db_session, seeded_inventory
    ):
        from app.services.vertical_inventory import get_inventory

        resp = get_inventory(db_session, vertical_slug=None)
        themes = [e for e in resp.recent_edits if e.section == "themes"]
        assert len(themes) > 0
        for e in themes:
            assert e.deep_link_path.startswith("/studio/themes?theme_id=")

    def test_vertical_scope_includes_vertical(
        self, db_session, seeded_inventory
    ):
        from app.services.vertical_inventory import get_inventory

        resp = get_inventory(db_session, vertical_slug="manufacturing")
        themes = [e for e in resp.recent_edits if e.section == "themes"]
        for e in themes:
            assert e.deep_link_path.startswith(
                "/studio/manufacturing/themes?theme_id="
            )

    def test_focus_deep_link_uses_template_id(
        self, db_session, seeded_inventory
    ):
        """B-2 contract: focuses + edge-panels deep-link uses
        `template_id` (not `composition_id`) since the inventory now
        anchors on Tier 2 rows."""
        from app.services.vertical_inventory import get_inventory

        resp = get_inventory(db_session, vertical_slug="manufacturing")
        focus_entries = [
            e for e in resp.recent_edits if e.section == "focuses"
        ]
        edge_entries = [
            e for e in resp.recent_edits if e.section == "edge-panels"
        ]
        for e in focus_entries:
            assert "template_id=" in e.deep_link_path
        for e in edge_entries:
            assert "template_id=" in e.deep_link_path

    def test_platform_only_editor_drops_vertical(
        self, db_session, seeded_inventory
    ):
        from app.services.vertical_inventory.service import _build_deep_link

        link = _build_deep_link("classes", "manufacturing", "abc-123")
        assert link == "/studio/classes?config_id=abc-123"
        link2 = _build_deep_link("registry", "manufacturing", "x")
        assert link2 == "/studio/registry"


# ─── API tests ─────────────────────────────────────────────────


class TestAPI:
    def test_anonymous_rejected(self, client):
        r = client.get("/api/platform/admin/studio/inventory")
        assert r.status_code in (401, 403)

    def test_tenant_token_rejected(self, client):
        ctx = _make_tenant_admin()
        r = client.get(
            "/api/platform/admin/studio/inventory",
            headers={
                "Authorization": f"Bearer {ctx['tenant_token']}",
                "X-Company-Slug": ctx["slug"],
            },
        )
        assert r.status_code == 401

    def test_platform_wide_200(self, client):
        ctx = _make_platform_admin()
        r = client.get(
            "/api/platform/admin/studio/inventory",
            headers={"Authorization": f"Bearer {ctx['platform_token']}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["scope"] == "platform"
        assert body["vertical_slug"] is None
        assert isinstance(body["sections"], list)
        assert len(body["sections"]) == 9

    def test_vertical_scope_200(self, client):
        ctx = _make_platform_admin()
        r = client.get(
            "/api/platform/admin/studio/inventory",
            params={"vertical": "manufacturing"},
            headers={"Authorization": f"Bearer {ctx['platform_token']}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["scope"] == "vertical"
        assert body["vertical_slug"] == "manufacturing"

    def test_unknown_vertical_404(self, client):
        ctx = _make_platform_admin()
        r = client.get(
            "/api/platform/admin/studio/inventory",
            params={"vertical": "does-not-exist"},
            headers={"Authorization": f"Bearer {ctx['platform_token']}"},
        )
        assert r.status_code == 404

    def test_section_count_shape_optional(self, client):
        from app.services.plugin_registry import list_category_keys

        ctx = _make_platform_admin()
        r = client.get(
            "/api/platform/admin/studio/inventory",
            headers={"Authorization": f"Bearer {ctx['platform_token']}"},
        )
        body = r.json()
        registry = next(
            s for s in body["sections"] if s["key"] == "registry"
        )
        assert registry["count"] is None
        plugin_reg = next(
            s for s in body["sections"] if s["key"] == "plugin-registry"
        )
        assert plugin_reg["count"] == len(list_category_keys())
