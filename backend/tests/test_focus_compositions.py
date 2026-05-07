"""Focus composition layer tests.

R-3.0: composition data model is now a sequence of rows. Each row
declares its own column_count and carries its own placements with
0-indexed `starting_column` + `column_span`. Pre-R-3.0 flat-placements
payloads are rejected at the API boundary.

Covers:
  - CRUD lifecycle (create, version, update, list, get) — rows shape
  - Inheritance walk (platform_default → vertical_default →
    tenant_override; first match wins)
  - Validation: scope-key shape, malformed rows, per-row column_count,
    duplicate row_ids, duplicate placement_ids across rows,
    starting_column + column_span fits within row.column_count
  - Variant B (column_widths) + bounded-nesting (nested_rows)
    extension points accept null OR validated lists; non-null logs
    warning in R-3.0
  - Legacy payload rejection at the API boundary
  - Admin gating
"""

from __future__ import annotations

import uuid

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


def _make_platform_admin_token():
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.platform_user import PlatformUser

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        admin = PlatformUser(
            id=str(uuid.uuid4()),
            email=f"platform-comp-{suffix}@bridgeable.test",
            hashed_password="x",
            first_name="Platform",
            last_name="Admin",
            role="super_admin",
            is_active=True,
        )
        db.add(admin)
        db.commit()
        token = create_access_token({"sub": admin.id}, realm="platform")
        return {"id": admin.id, "token": token}
    finally:
        db.close()


def _admin_headers(ctx):
    return {"Authorization": f"Bearer {ctx['token']}"}


def _make_tenant():
    """Create a minimal tenant + return its company_id for
    tenant_override scope tests."""
    from app.database import SessionLocal
    from app.models.company import Company

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"Comp Test {suffix}",
            slug=f"comp-test-{suffix}",
            is_active=True,
            vertical="manufacturing",
        )
        db.add(co)
        db.commit()
        return co.id
    finally:
        db.close()


def _cleanup():
    from app.database import SessionLocal
    from app.models.focus_composition import FocusComposition

    db = SessionLocal()
    try:
        db.query(FocusComposition).delete()
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _per_test_cleanup():
    _cleanup()
    yield
    _cleanup()


# ─── Sample row + placement helpers ──────────────────────────────


def _placement(
    placement_id: str,
    *,
    starting_column: int = 0,
    column_span: int = 12,
    component_kind: str = "widget",
    component_name: str = "today",
    prop_overrides: dict | None = None,
) -> dict:
    return {
        "placement_id": placement_id,
        "component_kind": component_kind,
        "component_name": component_name,
        "starting_column": starting_column,
        "column_span": column_span,
        "prop_overrides": prop_overrides or {},
        "display_config": {},
        "nested_rows": None,
    }


def _row(
    *,
    row_id: str | None = None,
    column_count: int = 12,
    row_height="auto",
    placements: list | None = None,
    column_widths=None,
    nested_rows=None,
) -> dict:
    return {
        "row_id": row_id or str(uuid.uuid4()),
        "column_count": column_count,
        "row_height": row_height,
        "column_widths": column_widths,
        "nested_rows": nested_rows,
        "placements": placements or [],
    }


# ─── Service layer ──────────────────────────────────────────────


class TestServiceValidation:
    def test_scope_key_mismatch_rejected(self, db_session):
        from app.services.focus_compositions import (
            CompositionScopeMismatch,
            create_composition,
        )

        with pytest.raises(CompositionScopeMismatch):
            create_composition(
                db_session,
                scope="vertical_default",
                focus_type="scheduling",
                vertical=None,  # missing; should be required
                tenant_id=None,
                rows=[],
            )

    def test_duplicate_placement_id_across_rows_rejected(self, db_session):
        from app.services.focus_compositions import (
            InvalidCompositionShape,
            create_composition,
        )

        with pytest.raises(InvalidCompositionShape):
            create_composition(
                db_session,
                scope="platform_default",
                focus_type="scheduling",
                rows=[
                    _row(placements=[_placement("a")]),
                    _row(placements=[_placement("a")]),  # duplicate id
                ],
            )

    def test_duplicate_row_id_rejected(self, db_session):
        from app.services.focus_compositions import (
            InvalidCompositionShape,
            create_composition,
        )

        with pytest.raises(InvalidCompositionShape):
            create_composition(
                db_session,
                scope="platform_default",
                focus_type="scheduling",
                rows=[
                    _row(row_id="dup", placements=[_placement("a")]),
                    _row(row_id="dup", placements=[_placement("b")]),
                ],
            )

    def test_out_of_bounds_placement_within_row_rejected(self, db_session):
        from app.services.focus_compositions import (
            InvalidCompositionShape,
            create_composition,
        )

        with pytest.raises(InvalidCompositionShape):
            create_composition(
                db_session,
                scope="platform_default",
                focus_type="scheduling",
                rows=[
                    _row(
                        column_count=4,
                        placements=[
                            _placement("a", starting_column=2, column_span=4)
                        ],  # 2 + 4 > 4
                    )
                ],
            )

    def test_column_count_above_max_rejected(self, db_session):
        from app.services.focus_compositions import (
            InvalidCompositionShape,
            create_composition,
        )

        with pytest.raises(InvalidCompositionShape):
            create_composition(
                db_session,
                scope="platform_default",
                focus_type="scheduling",
                rows=[_row(column_count=13)],
            )

    def test_column_count_below_min_rejected(self, db_session):
        from app.services.focus_compositions import (
            InvalidCompositionShape,
            create_composition,
        )

        with pytest.raises(InvalidCompositionShape):
            create_composition(
                db_session,
                scope="platform_default",
                focus_type="scheduling",
                rows=[_row(column_count=0)],
            )

    def test_negative_starting_column_rejected(self, db_session):
        from app.services.focus_compositions import (
            InvalidCompositionShape,
            create_composition,
        )

        with pytest.raises(InvalidCompositionShape):
            create_composition(
                db_session,
                scope="platform_default",
                focus_type="scheduling",
                rows=[
                    _row(
                        placements=[
                            _placement("a", starting_column=-1, column_span=2)
                        ]
                    )
                ],
            )

    def test_per_row_different_column_counts_accepted(self, db_session):
        """Different rows can declare different column_counts —
        the entire reason this model exists."""
        from app.services.focus_compositions import create_composition

        row = create_composition(
            db_session,
            scope="platform_default",
            focus_type="scheduling",
            rows=[
                _row(
                    column_count=4,
                    placements=[
                        _placement("kanban", starting_column=0, column_span=3),
                        _placement("widget", starting_column=3, column_span=1),
                    ],
                ),
                _row(
                    column_count=12,
                    placements=[
                        _placement("a", starting_column=0, column_span=3),
                        _placement("b", starting_column=3, column_span=3),
                        _placement("c", starting_column=6, column_span=3),
                        _placement("d", starting_column=9, column_span=3),
                    ],
                ),
            ],
        )
        assert row.id
        assert len(row.rows) == 2
        assert row.rows[0]["column_count"] == 4
        assert row.rows[1]["column_count"] == 12

    def test_extension_points_accept_null(self, db_session):
        from app.services.focus_compositions import create_composition

        row = create_composition(
            db_session,
            scope="platform_default",
            focus_type="scheduling",
            rows=[
                _row(
                    column_widths=None,
                    nested_rows=None,
                    placements=[_placement("a")],
                )
            ],
        )
        assert row.rows[0]["column_widths"] is None
        assert row.rows[0]["nested_rows"] is None

    def test_extension_points_warn_when_non_null(self, db_session, caplog):
        from app.services.focus_compositions import create_composition

        with caplog.at_level("WARNING"):
            row = create_composition(
                db_session,
                scope="platform_default",
                focus_type="scheduling",
                rows=[
                    _row(
                        column_widths=[25.0, 25.0, 25.0, 25.0],
                        column_count=4,
                        placements=[_placement("a", column_span=4)],
                    )
                ],
            )
        assert row.id
        # At least one warning mentioning column_widths in R-3.0 ignored.
        joined = " ".join(rec.getMessage() for rec in caplog.records)
        assert "column_widths" in joined or "Variant B" in joined


class TestServiceCRUD:
    def test_create_versions_existing_active_row(self, db_session):
        from app.services.focus_compositions import (
            create_composition,
            list_compositions,
        )

        v1 = create_composition(
            db_session,
            scope="platform_default",
            focus_type="scheduling",
            rows=[_row(placements=[_placement("a")])],
        )
        v2 = create_composition(
            db_session,
            scope="platform_default",
            focus_type="scheduling",
            rows=[
                _row(
                    placements=[
                        _placement("a", starting_column=0, column_span=6),
                        _placement("b", starting_column=6, column_span=6),
                    ]
                )
            ],
        )
        assert v2.version == v1.version + 1
        assert v2.is_active is True

        rows = list_compositions(
            db_session,
            scope="platform_default",
            focus_type="scheduling",
            include_inactive=True,
        )
        assert sum(1 for r in rows if r.is_active) == 1

    def test_update_versions_and_replaces(self, db_session):
        from app.services.focus_compositions import (
            create_composition,
            update_composition,
        )

        v1 = create_composition(
            db_session,
            scope="platform_default",
            focus_type="scheduling",
            rows=[_row(placements=[_placement("a")])],
        )
        v2 = update_composition(
            db_session,
            composition_id=v1.id,
            rows=[
                _row(
                    placements=[
                        _placement("a", starting_column=0, column_span=6),
                        _placement("b", starting_column=6, column_span=6),
                    ]
                )
            ],
            canvas_config={"gap_size": 16},
        )
        assert v2.version > v1.version
        assert v2.is_active is True
        assert len(v2.rows) == 1
        assert len(v2.rows[0]["placements"]) == 2
        assert v2.canvas_config.get("gap_size") == 16

    def test_normalize_assigns_row_id_when_missing(self, db_session):
        from app.services.focus_compositions import create_composition

        # Caller omits row_id; service normalization assigns one.
        row = create_composition(
            db_session,
            scope="platform_default",
            focus_type="scheduling",
            rows=[
                {
                    "column_count": 12,
                    "row_height": "auto",
                    "column_widths": None,
                    "nested_rows": None,
                    "placements": [_placement("a")],
                }
            ],
        )
        assert row.rows[0]["row_id"]
        # UUID-shaped (not literally validating UUID format; just check it's
        # a non-empty string the service generated)
        assert isinstance(row.rows[0]["row_id"], str)
        assert len(row.rows[0]["row_id"]) >= 8


class TestResolution:
    def test_empty_when_no_composition_exists(self, db_session):
        from app.services.focus_compositions import resolve_composition

        result = resolve_composition(
            db_session, focus_type="scheduling", vertical="funeral_home"
        )
        assert result["source"] is None
        assert result["rows"] == []

    def test_platform_default_returned_when_no_vertical_or_tenant(
        self, db_session
    ):
        from app.services.focus_compositions import (
            create_composition,
            resolve_composition,
        )

        create_composition(
            db_session,
            scope="platform_default",
            focus_type="scheduling",
            rows=[_row(placements=[_placement("p")])],
        )
        result = resolve_composition(db_session, focus_type="scheduling")
        assert result["source"] == "platform_default"
        assert len(result["rows"]) == 1

    def test_vertical_default_overrides_platform(self, db_session):
        from app.services.focus_compositions import (
            create_composition,
            resolve_composition,
        )

        create_composition(
            db_session,
            scope="platform_default",
            focus_type="scheduling",
            rows=[_row(placements=[_placement("p")])],
        )
        create_composition(
            db_session,
            scope="vertical_default",
            focus_type="scheduling",
            vertical="funeral_home",
            rows=[
                _row(
                    placements=[
                        _placement("v1", starting_column=0, column_span=6),
                        _placement("v2", starting_column=6, column_span=6),
                    ]
                )
            ],
        )
        result = resolve_composition(
            db_session, focus_type="scheduling", vertical="funeral_home"
        )
        assert result["source"] == "vertical_default"
        assert len(result["rows"][0]["placements"]) == 2
        result_mfg = resolve_composition(
            db_session, focus_type="scheduling", vertical="manufacturing"
        )
        assert result_mfg["source"] == "platform_default"

    def test_tenant_override_wins_over_vertical_and_platform(self, db_session):
        from app.services.focus_compositions import (
            create_composition,
            resolve_composition,
        )

        tenant_id = _make_tenant()
        create_composition(
            db_session,
            scope="platform_default",
            focus_type="scheduling",
            rows=[_row(placements=[_placement("p")])],
        )
        create_composition(
            db_session,
            scope="vertical_default",
            focus_type="scheduling",
            vertical="manufacturing",
            rows=[_row(placements=[_placement("v")])],
        )
        create_composition(
            db_session,
            scope="tenant_override",
            focus_type="scheduling",
            tenant_id=tenant_id,
            rows=[
                _row(
                    placements=[
                        _placement("t1", starting_column=0, column_span=6),
                        _placement("t2", starting_column=6, column_span=6),
                    ]
                ),
                _row(placements=[_placement("t3")]),
            ],
        )
        result = resolve_composition(
            db_session,
            focus_type="scheduling",
            vertical="manufacturing",
            tenant_id=tenant_id,
        )
        assert result["source"] == "tenant_override"
        assert len(result["rows"]) == 2


class TestLegacyPayloadRejection:
    def test_legacy_placements_payload_rejected(self):
        from app.services.focus_compositions import (
            LegacyPayloadRejected,
            reject_legacy_placements_payload,
        )

        with pytest.raises(LegacyPayloadRejected):
            reject_legacy_placements_payload(
                {
                    "scope": "platform_default",
                    "focus_type": "scheduling",
                    "placements": [{"placement_id": "a"}],
                }
            )

    def test_rows_payload_passes_through(self):
        from app.services.focus_compositions import (
            reject_legacy_placements_payload,
        )

        # Should NOT raise.
        reject_legacy_placements_payload(
            {
                "scope": "platform_default",
                "focus_type": "scheduling",
                "rows": [],
            }
        )

    def test_dual_payload_passes_through(self):
        """If caller sends BOTH `rows` and `placements`, the legacy
        guard does NOT fire — the rows-shaped payload is taken as
        canonical and Pydantic discards extra keys (or accepts them
        depending on model config). The guard's job is to catch the
        ambiguous case where ONLY `placements` is present."""
        from app.services.focus_compositions import (
            reject_legacy_placements_payload,
        )

        # Should NOT raise.
        reject_legacy_placements_payload(
            {
                "scope": "platform_default",
                "focus_type": "scheduling",
                "rows": [],
                "placements": [],  # legacy noise; guard ignores when rows present
            }
        )


# ─── API layer ──────────────────────────────────────────────────


class TestApiAdmin:
    def test_create_then_list_then_resolve(self, client):
        ctx = _make_platform_admin_token()
        create_resp = client.post(
            "/api/platform/admin/visual-editor/compositions/",
            headers=_admin_headers(ctx),
            json={
                "scope": "platform_default",
                "focus_type": "scheduling",
                "rows": [_row(placements=[_placement("a")])],
                "canvas_config": {"gap_size": 12},
            },
        )
        assert create_resp.status_code == 201
        payload = create_resp.json()
        assert payload["focus_type"] == "scheduling"
        assert len(payload["rows"]) == 1
        assert len(payload["rows"][0]["placements"]) == 1

        list_resp = client.get(
            "/api/platform/admin/visual-editor/compositions/?focus_type=scheduling",
            headers=_admin_headers(ctx),
        )
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1

        resolve_resp = client.get(
            "/api/platform/admin/visual-editor/compositions/resolve?focus_type=scheduling",
            headers=_admin_headers(ctx),
        )
        assert resolve_resp.status_code == 200
        body = resolve_resp.json()
        assert body["source"] == "platform_default"
        assert body["focus_type"] == "scheduling"
        assert "rows" in body

    def test_invalid_grid_returns_400(self, client):
        ctx = _make_platform_admin_token()
        resp = client.post(
            "/api/platform/admin/visual-editor/compositions/",
            headers=_admin_headers(ctx),
            json={
                "scope": "platform_default",
                "focus_type": "scheduling",
                "rows": [
                    _row(
                        column_count=4,
                        placements=[
                            {
                                "placement_id": "bad",
                                "component_kind": "widget",
                                "component_name": "today",
                                "starting_column": 2,
                                "column_span": 4,  # 2+4 > column_count=4
                                "prop_overrides": {},
                                "display_config": {},
                                "nested_rows": None,
                            }
                        ],
                    )
                ],
            },
        )
        assert resp.status_code == 400

    def test_legacy_placements_payload_returns_400(self, client):
        ctx = _make_platform_admin_token()
        resp = client.post(
            "/api/platform/admin/visual-editor/compositions/",
            headers=_admin_headers(ctx),
            json={
                "scope": "platform_default",
                "focus_type": "scheduling",
                "placements": [
                    {
                        "placement_id": "a",
                        "component_kind": "widget",
                        "component_name": "today",
                        "grid": {
                            "column_start": 1,
                            "column_span": 6,
                            "row_start": 1,
                            "row_span": 3,
                        },
                        "prop_overrides": {},
                        "display_config": {},
                    }
                ],
            },
        )
        assert resp.status_code == 400
        body = resp.json()
        # Error message points at the rows-based contract.
        assert "rows" in body["detail"].lower() or "R-3.0" in body["detail"]

    def test_anonymous_rejected(self, client):
        resp = client.get("/api/platform/admin/visual-editor/compositions/")
        assert resp.status_code in (401, 403)

    def test_resolve_falls_back_through_chain(self, client):
        ctx = _make_platform_admin_token()
        client.post(
            "/api/platform/admin/visual-editor/compositions/",
            headers=_admin_headers(ctx),
            json={
                "scope": "vertical_default",
                "focus_type": "scheduling",
                "vertical": "funeral_home",
                "rows": [_row(placements=[_placement("fh1")])],
            },
        )
        resp = client.get(
            "/api/platform/admin/visual-editor/compositions/resolve?focus_type=scheduling&vertical=funeral_home",
            headers=_admin_headers(ctx),
        )
        assert resp.json()["source"] == "vertical_default"
        resp_mfg = client.get(
            "/api/platform/admin/visual-editor/compositions/resolve?focus_type=scheduling&vertical=manufacturing",
            headers=_admin_headers(ctx),
        )
        assert resp_mfg.json()["source"] is None
