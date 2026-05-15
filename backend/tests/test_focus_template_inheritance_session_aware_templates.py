"""Focus Template Inheritance — session-aware update tests for Tier 2
templates (sub-arc C-2.1.2).

Mirrors `test_focus_template_inheritance_session_aware.py` for Tier 1
cores. Covers the session-aware update semantics added in r103:

  - Updates within an explicit edit session (matching session_id +
    < EDIT_SESSION_WINDOW_SECONDS since last touch) mutate the
    existing row in place. No version bump.
  - Updates outside the session window OR with a different session
    token version-bump per the B-1 behavior. Prior row deactivated;
    new row at version+1.
  - Updates without an `edit_session_id` version-bump (B-1 fallback).
  - Updates targeting an INACTIVE template_id raise
    StaleTemplateVersionError carrying the active template's id,
    which the route layer translates to HTTP 410 Gone with
    `active_template_id` in the response body.

Tests share a clean-slate autouse fixture; companies are torn down on
cleanup.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.database import SessionLocal
from app.models.company import Company
from app.models.focus_composition import FocusComposition
from app.models.focus_core import FocusCore
from app.models.focus_template import FocusTemplate
from app.models.platform_user import PlatformUser
from app.services.focus_template_inheritance import (
    EDIT_SESSION_WINDOW_SECONDS,
    StaleTemplateVersionError,
    create_core,
    create_template,
    get_template_by_id,
    update_template,
)


API_ROOT = "/api/platform/admin/focus-template-inheritance"


# ─── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture(autouse=True)
def _cleanup():
    def _wipe():
        s = SessionLocal()
        try:
            s.query(FocusComposition).delete()
            s.query(FocusTemplate).delete()
            s.query(FocusCore).delete()
            s.commit()
        finally:
            s.close()

    _wipe()
    yield
    _wipe()


def _make_core(db, *, slug: str = "kt-1") -> FocusCore:
    return create_core(
        db,
        core_slug=slug,
        display_name="Test Core",
        description=None,
        registered_component_kind="focus-core",
        registered_component_name="TestCore",
        default_starting_column=0,
        default_column_span=12,
        default_row_index=0,
        min_column_span=8,
        max_column_span=12,
        canvas_config={},
    )


def _make_template(
    db,
    *,
    core_id: str,
    slug: str = "kt-tpl-1",
    scope: str = "platform_default",
    vertical: str | None = None,
) -> FocusTemplate:
    return create_template(
        db,
        scope=scope,
        vertical=vertical,
        template_slug=slug,
        display_name="Test Template",
        description="desc",
        inherits_from_core_id=core_id,
        rows=[],
        canvas_config={},
    )


# ═══ Tier 2 — Session-aware update ═════════════════════════════════


class TestTemplateSessionAwareUpdate:
    def test_update_with_session_token_mutates_in_place(self, db):
        c = _make_core(db, slug="saw-c-1")
        t = _make_template(db, core_id=c.id, slug="saw-t-1")
        original_id = t.id
        original_version = t.version
        sid = str(uuid.uuid4())

        updated = update_template(
            db,
            t.id,
            display_name="Renamed In Place",
            edit_session_id=sid,
            updated_by=None,
        )
        assert updated.id == original_id
        assert updated.version == original_version
        assert updated.is_active is True
        assert updated.display_name == "Renamed In Place"
        assert str(updated.last_edit_session_id) == sid
        assert updated.last_edit_session_at is not None

    def test_consecutive_same_session_updates_stay_in_place(self, db):
        c = _make_core(db, slug="saw-c-2")
        t = _make_template(db, core_id=c.id, slug="saw-t-2")
        sid = str(uuid.uuid4())
        original_id = t.id

        r1 = update_template(
            db, t.id, display_name="v-a",
            edit_session_id=sid, updated_by=None,
        )
        r2 = update_template(
            db, r1.id, display_name="v-b",
            edit_session_id=sid, updated_by=None,
        )
        r3 = update_template(
            db, r2.id, display_name="v-c",
            edit_session_id=sid, updated_by=None,
        )

        assert r1.id == original_id
        assert r2.id == original_id
        assert r3.id == original_id
        assert r3.version == 1
        assert r3.display_name == "v-c"

        all_rows = (
            db.query(FocusTemplate)
            .filter(FocusTemplate.template_slug == "saw-t-2")
            .all()
        )
        assert len(all_rows) == 1

    def test_different_session_triggers_version_bump(self, db):
        c = _make_core(db, slug="saw-c-3")
        t = _make_template(db, core_id=c.id, slug="saw-t-3")
        sid_a = str(uuid.uuid4())
        sid_b = str(uuid.uuid4())

        r1 = update_template(
            db, t.id, display_name="v-a",
            edit_session_id=sid_a, updated_by=None,
        )
        r2 = update_template(
            db, r1.id, display_name="v-b",
            edit_session_id=sid_b, updated_by=None,
        )

        assert r1.id == t.id
        assert r2.id != r1.id
        assert r2.version == r1.version + 1
        db.refresh(r1)
        assert r1.is_active is False
        assert str(r2.last_edit_session_id) == sid_b

    def test_stale_session_window_triggers_version_bump(self, db):
        c = _make_core(db, slug="saw-c-4")
        t = _make_template(db, core_id=c.id, slug="saw-t-4")
        sid = str(uuid.uuid4())

        r1 = update_template(
            db, t.id, display_name="v-a",
            edit_session_id=sid, updated_by=None,
        )
        stale_ts = datetime.now(timezone.utc) - timedelta(
            seconds=EDIT_SESSION_WINDOW_SECONDS + 60
        )
        r1.last_edit_session_at = stale_ts
        db.commit()

        r2 = update_template(
            db, r1.id, display_name="v-b",
            edit_session_id=sid, updated_by=None,
        )
        assert r2.id != r1.id
        assert r2.version == r1.version + 1

    def test_update_without_session_token_version_bumps(self, db):
        """B-1 backward-compat: callers that omit edit_session_id
        keep getting version bumps."""
        c = _make_core(db, slug="saw-c-5")
        t = _make_template(db, core_id=c.id, slug="saw-t-5")
        r2 = update_template(db, t.id, display_name="v2", updated_by=None)
        assert r2.id != t.id
        assert r2.version == t.version + 1
        db.refresh(t)
        assert t.is_active is False

    def test_in_place_mutation_preserves_unset_fields(self, db):
        c = _make_core(db, slug="saw-c-6")
        t = _make_template(db, core_id=c.id, slug="saw-t-6")
        # Pre-seed substrate, chrome_overrides, typography via a
        # version-bump update.
        t2 = update_template(
            db, t.id,
            chrome_overrides={"preset": "frosted"},
            substrate={"preset": "morning-warm"},
            typography={"preset": "card-text"},
            updated_by=None,
        )
        sid = str(uuid.uuid4())
        # Only touch display_name — other fields should carry through.
        updated = update_template(
            db, t2.id, display_name="renamed",
            edit_session_id=sid, updated_by=None,
        )
        assert dict(updated.chrome_overrides) == {"preset": "frosted"}
        assert dict(updated.substrate) == {"preset": "morning-warm"}
        assert dict(updated.typography) == {"preset": "card-text"}

    def test_in_place_mutation_advances_session_at_each_call(self, db):
        c = _make_core(db, slug="saw-c-7")
        t = _make_template(db, core_id=c.id, slug="saw-t-7")
        sid = str(uuid.uuid4())

        r1 = update_template(
            db, t.id, display_name="a",
            edit_session_id=sid, updated_by=None,
        )
        t1 = r1.last_edit_session_at
        r2 = update_template(
            db, r1.id, display_name="b",
            edit_session_id=sid, updated_by=None,
        )
        assert r2.last_edit_session_at is not None
        assert r2.last_edit_session_at >= t1

    def test_update_against_inactive_template_raises_stale(self, db):
        c = _make_core(db, slug="saw-c-8")
        t1 = _make_template(db, core_id=c.id, slug="saw-t-8")
        t1_id = t1.id
        # First touch — session A — mutates in place.
        update_template(
            db, t1.id, display_name="v1b",
            edit_session_id=str(uuid.uuid4()), updated_by=None,
        )
        # Different session — version-bumps. Now t1 is inactive.
        t2 = update_template(
            db, t1_id, display_name="v2",
            edit_session_id=str(uuid.uuid4()), updated_by=None,
        )
        assert t2.id != t1_id
        with pytest.raises(StaleTemplateVersionError) as ei:
            update_template(
                db, t1_id, display_name="never",
                edit_session_id=str(uuid.uuid4()), updated_by=None,
            )
        assert ei.value.inactive_id == t1_id
        assert ei.value.active_id == t2.id
        assert ei.value.slug == "saw-t-8"
        assert ei.value.scope == "platform_default"
        assert ei.value.vertical is None

    def test_in_place_mutation_does_not_create_new_row(self, db):
        c = _make_core(db, slug="saw-c-9")
        t = _make_template(db, core_id=c.id, slug="saw-t-9")
        sid = str(uuid.uuid4())
        for i in range(5):
            update_template(
                db, t.id, display_name=f"v-{i}",
                edit_session_id=sid, updated_by=None,
            )
        rows = (
            db.query(FocusTemplate)
            .filter(FocusTemplate.template_slug == "saw-t-9")
            .all()
        )
        assert len(rows) == 1
        assert rows[0].version == 1
        assert rows[0].display_name == "v-4"

    def test_in_place_mutation_chrome_overrides_persist(self, db):
        c = _make_core(db, slug="saw-c-10")
        t = _make_template(db, core_id=c.id, slug="saw-t-10")
        sid = str(uuid.uuid4())

        updated = update_template(
            db, t.id,
            chrome_overrides={"preset": "frosted", "elevation": 50},
            edit_session_id=sid, updated_by=None,
        )
        assert updated.id == t.id
        assert dict(updated.chrome_overrides) == {
            "preset": "frosted", "elevation": 50
        }
        fresh = get_template_by_id(db, t.id)
        assert dict(fresh.chrome_overrides) == {
            "preset": "frosted", "elevation": 50
        }


# ═══ API surface — 410 Gone for stale template ═════════════════════


@pytest.fixture
def api_ctx():
    """Minimal platform-admin context for hitting the PUT endpoint."""
    s = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        platform_admin = PlatformUser(
            id=str(uuid.uuid4()),
            email=f"saw-t-{suffix}@bridgeable.test",
            hashed_password="x",
            first_name="P",
            last_name="A",
            role="super_admin",
            is_active=True,
        )
        s.add(platform_admin)
        s.commit()
        token = create_access_token({"sub": platform_admin.id}, realm="platform")
        yield {"platform_token": token, "platform_user_id": platform_admin.id}
    finally:
        s2 = SessionLocal()
        try:
            s2.query(PlatformUser).filter(
                PlatformUser.id == platform_admin.id
            ).delete()
            s2.commit()
        finally:
            s2.close()
        s.close()


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


class TestTemplateApiStaleReturns410:
    def test_put_against_inactive_returns_410_with_active_id(
        self, client, api_ctx
    ):
        s = SessionLocal()
        try:
            core = create_core(
                s,
                core_slug="saw-api-core-1",
                display_name="X",
                registered_component_kind="focus-core",
                registered_component_name="X",
                canvas_config={},
            )
            tpl = create_template(
                s,
                scope="platform_default",
                vertical=None,
                template_slug="saw-api-tpl-1",
                display_name="T1",
                description=None,
                inherits_from_core_id=core.id,
                rows=[],
                canvas_config={},
            )
            inactive_id = tpl.id
            # First touch — session A — mutates in place.
            update_template(
                s, tpl.id, display_name="v1b",
                edit_session_id=str(uuid.uuid4()), updated_by=None,
            )
            # Different session — version-bumps.
            tpl2 = update_template(
                s, tpl.id, display_name="v2",
                edit_session_id=str(uuid.uuid4()), updated_by=None,
            )
            active_id = tpl2.id
            assert active_id != inactive_id
        finally:
            s.close()

        headers = {"Authorization": f"Bearer {api_ctx['platform_token']}"}
        res = client.put(
            f"{API_ROOT}/templates/{inactive_id}",
            json={
                "display_name": "should-fail",
                "edit_session_id": str(uuid.uuid4()),
            },
            headers=headers,
        )
        assert res.status_code == 410
        body = res.json()
        detail = body.get("detail")
        assert isinstance(detail, dict)
        assert detail.get("inactive_template_id") == inactive_id
        assert detail.get("active_template_id") == active_id
        assert detail.get("slug") == "saw-api-tpl-1"
        assert detail.get("scope") == "platform_default"
        assert detail.get("vertical") is None

    def test_put_with_session_round_trips_metadata(self, client, api_ctx):
        s = SessionLocal()
        try:
            core = create_core(
                s,
                core_slug="saw-api-core-2",
                display_name="X",
                registered_component_kind="focus-core",
                registered_component_name="X",
                canvas_config={},
            )
            tpl = create_template(
                s,
                scope="platform_default",
                vertical=None,
                template_slug="saw-api-tpl-2",
                display_name="T1",
                description=None,
                inherits_from_core_id=core.id,
                rows=[],
                canvas_config={},
            )
            template_id = tpl.id
        finally:
            s.close()

        headers = {"Authorization": f"Bearer {api_ctx['platform_token']}"}
        sid = str(uuid.uuid4())
        res = client.put(
            f"{API_ROOT}/templates/{template_id}",
            json={"display_name": "round", "edit_session_id": sid},
            headers=headers,
        )
        assert res.status_code == 200
        body = res.json()
        assert body["id"] == template_id
        assert body["version"] == 1
        assert body.get("last_edit_session_id") == sid
        assert body.get("last_edit_session_at") is not None


# ═══ Migration reversibility smoke ═════════════════════════════════


class TestMigrationR103:
    def test_columns_exist(self, db):
        """The model + DB schema agree on the new r103 columns."""
        c = _make_core(db, slug="saw-mig-c-1")
        t = _make_template(db, core_id=c.id, slug="saw-mig-t-1")
        assert t.last_edit_session_id is None
        assert t.last_edit_session_at is None
        sid = str(uuid.uuid4())
        updated = update_template(
            db, t.id, display_name="x",
            edit_session_id=sid, updated_by=None,
        )
        assert str(updated.last_edit_session_id) == sid
        assert updated.last_edit_session_at is not None
