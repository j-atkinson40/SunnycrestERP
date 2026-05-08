"""R-5.1a — backend per-placement override granularity tests.

Extends R-5.0's edge_panel_overrides shape (Option B from R-5.1
investigation). Each page override now accepts:
  - hidden_placement_ids
  - additional_placements
  - placement_order

alongside the existing rows / canvas_config full-replace fields. Plus
top-level additional_pages for user's personal pages.

Resolver merge semantics covered here:
  - If "rows" set in override → use it (R-5.0 full-replace escape
    hatch); per-placement fields ignored.
  - Else: tenant placements minus hidden_placement_ids +
    additional_placements (each at row_index, clamp to last row),
    then reordered by placement_order.
  - Orphan IDs (hidden_ids referencing non-existent placements; order
    IDs not in effective set) silently dropped with logger.debug.

Top-level additional_pages append to tenant pages list before
hidden_page_ids filter and page_order_override apply (so personal
pages participate in both).

Plus the new ?ignore_user_overrides=true query param on
GET /api/v1/edge-panel/resolve for the upcoming /settings/edge-panel
diff display.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


def _make_tenant_with_admin(vertical: str = "manufacturing") -> dict:
    """Mirrors the R-5.0 fixture in test_edge_panel_r50.py."""
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
            name=f"R51 {suffix}",
            slug=f"r51-{suffix}",
            is_active=True,
            vertical=vertical,
        )
        db.add(co)
        db.flush()

        admin_role = Role(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name="Admin",
            slug="admin",
            is_system=True,
        )
        db.add(admin_role)
        db.flush()

        admin = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"r51-admin-{suffix}@bridgeable.test",
            hashed_password="x",
            first_name="R51",
            last_name="Admin",
            role_id=admin_role.id,
            is_active=True,
        )
        db.add(admin)
        db.commit()

        tenant_token = create_access_token(
            {"sub": admin.id, "company_id": co.id},
            realm="tenant",
        )
        return {
            "company_id": co.id,
            "vertical": vertical,
            "user_id": admin.id,
            "tenant_token": tenant_token,
            "company_slug": co.slug,
        }
    finally:
        db.close()


def _set_user_prefs(user_id: str, panel_key: str, override: dict) -> None:
    """Persist a per-panel override on a user's preferences."""
    from app.database import SessionLocal
    from app.models.user import User
    from sqlalchemy.orm.attributes import flag_modified

    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=user_id).first()
        prefs = dict(user.preferences or {})
        ep = dict(prefs.get("edge_panel_overrides") or {})
        ep[panel_key] = override
        prefs["edge_panel_overrides"] = ep
        user.preferences = prefs
        flag_modified(user, "preferences")
        db.add(user)
        db.commit()
    finally:
        db.close()


def _cleanup():
    from app.database import SessionLocal
    from app.models.focus_composition import FocusComposition
    from app.models.user import User
    from sqlalchemy.orm.attributes import flag_modified

    db = SessionLocal()
    try:
        db.query(FocusComposition).delete()
        # Clear edge_panel_overrides from any test users so they don't
        # leak across tests.
        users = db.query(User).filter(User.preferences.isnot(None)).all()
        for u in users:
            if isinstance(u.preferences, dict) and "edge_panel_overrides" in u.preferences:
                p = dict(u.preferences)
                p.pop("edge_panel_overrides", None)
                u.preferences = p
                flag_modified(u, "preferences")
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _per_test_cleanup():
    _cleanup()
    yield
    _cleanup()


def _placement(
    pid: str,
    *,
    component_kind: str = "button",
    component_name: str = "open-funeral-scheduling-focus",
    starting_column: int = 0,
    column_span: int = 12,
) -> dict:
    return {
        "placement_id": pid,
        "component_kind": component_kind,
        "component_name": component_name,
        "starting_column": starting_column,
        "column_span": column_span,
        "prop_overrides": {},
        "display_config": {},
        "nested_rows": None,
    }


def _row(*, placements: list | None = None, column_count: int = 12) -> dict:
    return {
        "row_id": str(uuid.uuid4()),
        "column_count": column_count,
        "row_height": "auto",
        "column_widths": None,
        "nested_rows": None,
        "placements": placements or [],
    }


def _page(
    *,
    page_id: str | None = None,
    name: str = "Quick Actions",
    rows: list | None = None,
) -> dict:
    return {
        "page_id": page_id or str(uuid.uuid4()),
        "name": name,
        "rows": rows or [
            _row(
                placements=[
                    _placement("p1"),
                    _placement("p2"),
                ]
            )
        ],
        "canvas_config": {},
    }


def _make_three_placement_panel(db_session) -> str:
    """Seed a platform_default panel with one page, one row, three
    placements. Returns the page_id."""
    from app.services.focus_compositions import create_composition

    page = _page(
        page_id="pg1",
        name="Quick",
        rows=[
            _row(
                placements=[
                    _placement("p1"),
                    _placement("p2"),
                    _placement("p3"),
                ]
            )
        ],
    )
    create_composition(
        db_session,
        scope="platform_default",
        focus_type="default",
        kind="edge_panel",
        pages=[page],
    )
    return "pg1"


# ─── Per-placement hide ──────────────────────────────────────────


class TestPerPlacementHide:
    """hidden_placement_ids on a page override drops matching placements."""

    def test_hide_single_placement(self, db_session):
        from app.services.focus_compositions import resolve_edge_panel

        _make_three_placement_panel(db_session)
        result = resolve_edge_panel(
            db_session,
            panel_key="default",
            user_overrides={
                "page_overrides": {
                    "pg1": {"hidden_placement_ids": ["p2"]},
                }
            },
        )
        kept = [
            p["placement_id"]
            for p in result["pages"][0]["rows"][0]["placements"]
        ]
        assert kept == ["p1", "p3"]

    def test_hide_multiple_placements(self, db_session):
        from app.services.focus_compositions import resolve_edge_panel

        _make_three_placement_panel(db_session)
        result = resolve_edge_panel(
            db_session,
            panel_key="default",
            user_overrides={
                "page_overrides": {
                    "pg1": {"hidden_placement_ids": ["p1", "p3"]},
                }
            },
        )
        kept = [
            p["placement_id"]
            for p in result["pages"][0]["rows"][0]["placements"]
        ]
        assert kept == ["p2"]

    def test_orphan_hidden_id_silently_dropped(self, db_session):
        """Orphan placement IDs in hidden_placement_ids (referencing
        placements that no longer exist in the tenant default) are
        silently dropped — does NOT raise, does NOT affect kept set.
        """
        from app.services.focus_compositions import resolve_edge_panel

        _make_three_placement_panel(db_session)
        result = resolve_edge_panel(
            db_session,
            panel_key="default",
            user_overrides={
                "page_overrides": {
                    "pg1": {
                        "hidden_placement_ids": ["nonexistent", "p2"],
                    },
                }
            },
        )
        kept = [
            p["placement_id"]
            for p in result["pages"][0]["rows"][0]["placements"]
        ]
        assert kept == ["p1", "p3"]


# ─── Additional placements ───────────────────────────────────────


class TestAdditionalPlacements:
    """additional_placements on a page override appends placements at
    the specified row_index."""

    def test_append_at_default_row_index(self, db_session):
        """row_index defaults to 0 (first row)."""
        from app.services.focus_compositions import resolve_edge_panel

        _make_three_placement_panel(db_session)
        new_p = _placement("user_p1")
        result = resolve_edge_panel(
            db_session,
            panel_key="default",
            user_overrides={
                "page_overrides": {
                    "pg1": {
                        "additional_placements": [new_p],
                    },
                }
            },
        )
        ids = [
            p["placement_id"]
            for p in result["pages"][0]["rows"][0]["placements"]
        ]
        # User addition appended at end of row 0
        assert ids == ["p1", "p2", "p3", "user_p1"]
        # row_index is NOT persisted as a placement attribute
        last = result["pages"][0]["rows"][0]["placements"][-1]
        assert "row_index" not in last

    def test_row_index_clamped_to_last_row(self, db_session):
        """row_index higher than the row count clamps to last row."""
        from app.services.focus_compositions import (
            create_composition,
            resolve_edge_panel,
        )

        # Two rows.
        page = _page(
            page_id="pg1",
            rows=[
                _row(placements=[_placement("p1")]),
                _row(placements=[_placement("p2")]),
            ],
        )
        create_composition(
            db_session,
            scope="platform_default",
            focus_type="default",
            kind="edge_panel",
            pages=[page],
        )
        new_p = dict(_placement("user_x"))
        new_p["row_index"] = 99
        result = resolve_edge_panel(
            db_session,
            panel_key="default",
            user_overrides={
                "page_overrides": {
                    "pg1": {"additional_placements": [new_p]},
                }
            },
        )
        # Row 0 unchanged; user_x lands in last row (idx 1) only.
        rows = result["pages"][0]["rows"]
        assert [p["placement_id"] for p in rows[0]["placements"]] == ["p1"]
        assert [p["placement_id"] for p in rows[1]["placements"]] == [
            "p2",
            "user_x",
        ]

    def test_empty_rows_synthesizes_new_row(self, db_session):
        """Empty rows + additional_placement → new synthetic row holding
        the single placement."""
        from app.services.focus_compositions import (
            create_composition,
            resolve_edge_panel,
        )

        # Page with NO rows. _page uses falsy-default for rows; build
        # the page dict directly so we can pass rows=[] verbatim.
        page = {
            "page_id": "pg1",
            "name": "Empty",
            "rows": [],
            "canvas_config": {},
        }
        create_composition(
            db_session,
            scope="platform_default",
            focus_type="default",
            kind="edge_panel",
            pages=[page],
        )
        new_p = _placement("user_y")
        result = resolve_edge_panel(
            db_session,
            panel_key="default",
            user_overrides={
                "page_overrides": {
                    "pg1": {"additional_placements": [new_p]},
                }
            },
        )
        rows = result["pages"][0]["rows"]
        assert len(rows) == 1
        assert [p["placement_id"] for p in rows[0]["placements"]] == ["user_y"]


# ─── Placement order ─────────────────────────────────────────────


class TestPlacementOrder:
    """placement_order reorders placements within each row."""

    def test_full_order_reorders(self, db_session):
        from app.services.focus_compositions import resolve_edge_panel

        _make_three_placement_panel(db_session)
        result = resolve_edge_panel(
            db_session,
            panel_key="default",
            user_overrides={
                "page_overrides": {
                    "pg1": {"placement_order": ["p3", "p1", "p2"]},
                }
            },
        )
        ids = [
            p["placement_id"]
            for p in result["pages"][0]["rows"][0]["placements"]
        ]
        assert ids == ["p3", "p1", "p2"]

    def test_partial_order_preserves_unmentioned(self, db_session):
        """Placements not mentioned in placement_order keep their
        relative position appended at end."""
        from app.services.focus_compositions import resolve_edge_panel

        _make_three_placement_panel(db_session)
        result = resolve_edge_panel(
            db_session,
            panel_key="default",
            user_overrides={
                "page_overrides": {
                    "pg1": {"placement_order": ["p3"]},
                }
            },
        )
        ids = [
            p["placement_id"]
            for p in result["pages"][0]["rows"][0]["placements"]
        ]
        # p3 first; p1 + p2 in original relative order behind it.
        assert ids == ["p3", "p1", "p2"]

    def test_orphan_order_id_silently_dropped(self, db_session):
        """Orphan IDs in placement_order are silently dropped."""
        from app.services.focus_compositions import resolve_edge_panel

        _make_three_placement_panel(db_session)
        result = resolve_edge_panel(
            db_session,
            panel_key="default",
            user_overrides={
                "page_overrides": {
                    "pg1": {
                        "placement_order": [
                            "ghost",
                            "p2",
                            "another-ghost",
                            "p1",
                        ],
                    },
                }
            },
        )
        ids = [
            p["placement_id"]
            for p in result["pages"][0]["rows"][0]["placements"]
        ]
        # Ghost ids dropped; p2 + p1 reordered; p3 unmentioned → end.
        assert ids == ["p2", "p1", "p3"]


# ─── Additional pages (top-level) ────────────────────────────────


class TestAdditionalPages:
    """Top-level additional_pages append user's personal pages."""

    def test_personal_page_appended(self, db_session):
        from app.services.focus_compositions import resolve_edge_panel

        _make_three_placement_panel(db_session)
        personal = _page(page_id="my-page", name="Mine")
        result = resolve_edge_panel(
            db_session,
            panel_key="default",
            user_overrides={"additional_pages": [personal]},
        )
        ids = [p["page_id"] for p in result["pages"]]
        assert ids == ["pg1", "my-page"]

    def test_personal_page_collision_drops_personal(self, db_session):
        """If a personal page's page_id matches a tenant page_id, the
        tenant page wins and the personal page is silently dropped."""
        from app.services.focus_compositions import resolve_edge_panel

        _make_three_placement_panel(db_session)
        # Personal page with SAME id as tenant page.
        collide = _page(page_id="pg1", name="Personal Quick")
        result = resolve_edge_panel(
            db_session,
            panel_key="default",
            user_overrides={"additional_pages": [collide]},
        )
        # Only one page with id pg1, and it's the tenant version.
        assert len(result["pages"]) == 1
        assert result["pages"][0]["name"] == "Quick"

    def test_personal_page_participates_in_hide_and_order(self, db_session):
        from app.services.focus_compositions import resolve_edge_panel

        _make_three_placement_panel(db_session)
        a = _page(page_id="my-a", name="A")
        b = _page(page_id="my-b", name="B")
        result = resolve_edge_panel(
            db_session,
            panel_key="default",
            user_overrides={
                "additional_pages": [a, b],
                "hidden_page_ids": ["my-a"],
                "page_order_override": ["my-b", "pg1"],
            },
        )
        ids = [p["page_id"] for p in result["pages"]]
        # my-a hidden; my-b reordered before pg1.
        assert ids == ["my-b", "pg1"]


# ─── rows-replace takes precedence ───────────────────────────────


class TestRowsFullReplaceTakesPrecedence:
    """When override carries `rows`, per-placement fields are ignored."""

    def test_rows_set_ignores_per_placement_fields(self, db_session):
        from app.services.focus_compositions import resolve_edge_panel

        _make_three_placement_panel(db_session)
        custom = _row(placements=[_placement("X")])
        result = resolve_edge_panel(
            db_session,
            panel_key="default",
            user_overrides={
                "page_overrides": {
                    "pg1": {
                        "rows": [custom],
                        # All these should be IGNORED because rows set
                        "hidden_placement_ids": ["X"],
                        "additional_placements": [_placement("Y")],
                        "placement_order": ["Y", "X"],
                    },
                }
            },
        )
        # The full-replace rows must be applied verbatim — X stays,
        # Y not added, hidden_ids ignored.
        page = result["pages"][0]
        assert len(page["rows"]) == 1
        ids = [p["placement_id"] for p in page["rows"][0]["placements"]]
        assert ids == ["X"]


# ─── Panel-level overrides (preserve R-5.0 behavior) ─────────────


class TestPanelLevelOverrides:
    """R-5.0 panel-level fields (hidden_page_ids, page_order_override,
    canvas_config) still work alongside R-5.1 per-placement fields."""

    def test_canvas_config_replaces_when_set(self, db_session):
        from app.services.focus_compositions import resolve_edge_panel

        _make_three_placement_panel(db_session)
        result = resolve_edge_panel(
            db_session,
            panel_key="default",
            user_overrides={
                "page_overrides": {
                    "pg1": {
                        "canvas_config": {"gap_size": 24},
                    },
                }
            },
        )
        assert result["pages"][0]["canvas_config"] == {"gap_size": 24}

    def test_canvas_config_alone_does_not_alter_rows(self, db_session):
        """canvas_config-only override must NOT touch row placements."""
        from app.services.focus_compositions import resolve_edge_panel

        _make_three_placement_panel(db_session)
        result = resolve_edge_panel(
            db_session,
            panel_key="default",
            user_overrides={
                "page_overrides": {
                    "pg1": {"canvas_config": {"gap_size": 8}},
                }
            },
        )
        ids = [
            p["placement_id"]
            for p in result["pages"][0]["rows"][0]["placements"]
        ]
        assert ids == ["p1", "p2", "p3"]

    def test_hidden_pages_still_drop_pages(self, db_session):
        from app.services.focus_compositions import (
            create_composition,
            resolve_edge_panel,
        )

        page1 = _page(page_id="a", name="A")
        page2 = _page(page_id="b", name="B")
        create_composition(
            db_session,
            scope="platform_default",
            focus_type="default",
            kind="edge_panel",
            pages=[page1, page2],
        )
        result = resolve_edge_panel(
            db_session,
            panel_key="default",
            user_overrides={"hidden_page_ids": ["a"]},
        )
        assert len(result["pages"]) == 1
        assert result["pages"][0]["page_id"] == "b"

    def test_page_order_override_still_reorders(self, db_session):
        from app.services.focus_compositions import (
            create_composition,
            resolve_edge_panel,
        )

        a = _page(page_id="a", name="A")
        b = _page(page_id="b", name="B")
        c = _page(page_id="c", name="C")
        create_composition(
            db_session,
            scope="platform_default",
            focus_type="default",
            kind="edge_panel",
            pages=[a, b, c],
        )
        result = resolve_edge_panel(
            db_session,
            panel_key="default",
            user_overrides={"page_order_override": ["c", "a", "b"]},
        )
        ids = [p["page_id"] for p in result["pages"]]
        assert ids == ["c", "a", "b"]


# ─── Composition (multi-feature interaction) ─────────────────────


class TestComposition:
    """Multiple R-5.1 features stacking together correctly."""

    def test_per_placement_plus_personal_page(self, db_session):
        from app.services.focus_compositions import resolve_edge_panel

        _make_three_placement_panel(db_session)
        personal = _page(
            page_id="my-page",
            name="Mine",
            rows=[_row(placements=[_placement("mine_p1")])],
        )
        result = resolve_edge_panel(
            db_session,
            panel_key="default",
            user_overrides={
                "page_overrides": {
                    "pg1": {
                        "hidden_placement_ids": ["p2"],
                        "placement_order": ["p3", "p1"],
                    },
                },
                "additional_pages": [personal],
            },
        )
        # Tenant page reordered + p2 hidden.
        ids_tenant = [
            p["placement_id"]
            for p in result["pages"][0]["rows"][0]["placements"]
        ]
        assert ids_tenant == ["p3", "p1"]
        # Personal page appended.
        ids_pages = [p["page_id"] for p in result["pages"]]
        assert ids_pages == ["pg1", "my-page"]

    def test_hide_and_add_combined(self, db_session):
        from app.services.focus_compositions import resolve_edge_panel

        _make_three_placement_panel(db_session)
        new_p = _placement("user_new")
        result = resolve_edge_panel(
            db_session,
            panel_key="default",
            user_overrides={
                "page_overrides": {
                    "pg1": {
                        "hidden_placement_ids": ["p1"],
                        "additional_placements": [new_p],
                    },
                }
            },
        )
        ids = [
            p["placement_id"]
            for p in result["pages"][0]["rows"][0]["placements"]
        ]
        # p1 hidden; user_new appended.
        assert ids == ["p2", "p3", "user_new"]

    def test_no_overrides_returns_tenant_unchanged(self, db_session):
        from app.services.focus_compositions import resolve_edge_panel

        _make_three_placement_panel(db_session)
        result = resolve_edge_panel(
            db_session,
            panel_key="default",
            user_overrides={},
        )
        ids = [
            p["placement_id"]
            for p in result["pages"][0]["rows"][0]["placements"]
        ]
        assert ids == ["p1", "p2", "p3"]


# ─── API surface ─────────────────────────────────────────────────


class TestApi:
    """The new ?ignore_user_overrides=true query param + persistence
    of the new override schema through the existing PATCH endpoint."""

    def test_ignore_user_overrides_query_param(self, client, db_session):
        """ignore_user_overrides=true bypasses user override layer."""
        ctx = _make_tenant_with_admin()
        _make_three_placement_panel(db_session)
        # User hides p2.
        _set_user_prefs(
            ctx["user_id"],
            "default",
            {"page_overrides": {"pg1": {"hidden_placement_ids": ["p2"]}}},
        )
        # Default (no flag) → user override applied.
        resp_with = client.get(
            "/api/v1/edge-panel/resolve?panel_key=default",
            headers={
                "Authorization": f"Bearer {ctx['tenant_token']}",
                "X-Company-Slug": ctx["company_slug"],
            },
        )
        assert resp_with.status_code == 200
        ids_with = [
            p["placement_id"]
            for p in resp_with.json()["pages"][0]["rows"][0]["placements"]
        ]
        assert ids_with == ["p1", "p3"]

        # ignore_user_overrides=true → unmodified tenant default.
        resp_without = client.get(
            "/api/v1/edge-panel/resolve?panel_key=default&ignore_user_overrides=true",
            headers={
                "Authorization": f"Bearer {ctx['tenant_token']}",
                "X-Company-Slug": ctx["company_slug"],
            },
        )
        assert resp_without.status_code == 200
        ids_without = [
            p["placement_id"]
            for p in resp_without.json()["pages"][0]["rows"][0]["placements"]
        ]
        assert ids_without == ["p1", "p2", "p3"]

    def test_ignore_user_overrides_default_false(self, client, db_session):
        """Default behavior unchanged from R-5.0 — overrides applied."""
        ctx = _make_tenant_with_admin()
        _make_three_placement_panel(db_session)
        _set_user_prefs(
            ctx["user_id"],
            "default",
            {"page_overrides": {"pg1": {"placement_order": ["p3", "p1", "p2"]}}},
        )
        resp = client.get(
            "/api/v1/edge-panel/resolve?panel_key=default",
            headers={
                "Authorization": f"Bearer {ctx['tenant_token']}",
                "X-Company-Slug": ctx["company_slug"],
            },
        )
        assert resp.status_code == 200
        ids = [
            p["placement_id"]
            for p in resp.json()["pages"][0]["rows"][0]["placements"]
        ]
        assert ids == ["p3", "p1", "p2"]

    def test_patch_persists_per_placement_fields(self, client, db_session):
        """The new R-5.1 fields round-trip through the existing PATCH
        endpoint (no contract change at the boundary — JSONB blob)."""
        ctx = _make_tenant_with_admin()
        new_blob = {
            "default": {
                "page_overrides": {
                    "pg1": {
                        "hidden_placement_ids": ["p2"],
                        "additional_placements": [
                            {
                                **_placement("user_x"),
                                "row_index": 0,
                            }
                        ],
                        "placement_order": ["p3", "p1", "user_x"],
                    },
                },
                "additional_pages": [
                    _page(page_id="my-page", name="Mine"),
                ],
            }
        }
        resp = client.patch(
            "/api/v1/edge-panel/preferences",
            headers={
                "Authorization": f"Bearer {ctx['tenant_token']}",
                "X-Company-Slug": ctx["company_slug"],
            },
            json={"edge_panel_overrides": new_blob},
        )
        assert resp.status_code == 200
        # GET reflects the patch — full round-trip preserved.
        resp = client.get(
            "/api/v1/edge-panel/preferences",
            headers={
                "Authorization": f"Bearer {ctx['tenant_token']}",
                "X-Company-Slug": ctx["company_slug"],
            },
        )
        body = resp.json()
        page_override = body["edge_panel_overrides"]["default"]["page_overrides"]["pg1"]
        assert page_override["hidden_placement_ids"] == ["p2"]
        assert page_override["additional_placements"][0]["placement_id"] == "user_x"
        assert page_override["additional_placements"][0]["row_index"] == 0
        assert page_override["placement_order"] == ["p3", "p1", "user_x"]
        assert (
            body["edge_panel_overrides"]["default"]["additional_pages"][0]["page_id"]
            == "my-page"
        )

    def test_resolve_applies_persisted_per_placement_overrides(
        self, client, db_session
    ):
        """End-to-end: PATCH persists per-placement override → GET
        /resolve applies the full layer."""
        ctx = _make_tenant_with_admin()
        _make_three_placement_panel(db_session)
        _set_user_prefs(
            ctx["user_id"],
            "default",
            {
                "page_overrides": {
                    "pg1": {
                        "hidden_placement_ids": ["p1"],
                        "additional_placements": [_placement("user_n")],
                        "placement_order": ["p2", "user_n", "p3"],
                    },
                },
            },
        )
        resp = client.get(
            "/api/v1/edge-panel/resolve?panel_key=default",
            headers={
                "Authorization": f"Bearer {ctx['tenant_token']}",
                "X-Company-Slug": ctx["company_slug"],
            },
        )
        assert resp.status_code == 200
        ids = [
            p["placement_id"]
            for p in resp.json()["pages"][0]["rows"][0]["placements"]
        ]
        # p1 hidden; user_n added; reordered.
        assert ids == ["p2", "user_n", "p3"]

    def test_no_auth_rejected(self, client):
        resp = client.get(
            "/api/v1/edge-panel/resolve?panel_key=default&ignore_user_overrides=true"
        )
        assert resp.status_code in (401, 403)
