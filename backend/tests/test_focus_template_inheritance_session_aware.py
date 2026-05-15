"""Focus Template Inheritance — session-aware update tests (sub-arc C-2.1.1).

Covers the session-aware update semantics added in r102:

  - Updates within an explicit edit session (matching session_id +
    < EDIT_SESSION_WINDOW_SECONDS since last touch) mutate the
    existing row in place. No version bump.
  - Updates outside the session window OR with a different session
    token version-bump per the B-1 behavior. Prior row deactivated;
    new row at version+1.
  - Updates without an `edit_session_id` version-bump (B-1 fallback).
  - Updates targeting an INACTIVE core_id raise StaleCoreVersionError
    carrying the active core's id, which the route layer translates
    to HTTP 410 Gone with `active_core_id` in the response body.

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
    StaleCoreVersionError,
    create_core,
    get_core_by_id,
    get_core_by_slug,
    resolve_focus,
    update_core,
    create_template,
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


def _make_core(db, *, slug: str = "scheduling-kanban", **kwargs) -> FocusCore:
    defaults = dict(
        core_slug=slug,
        display_name="Scheduling Kanban",
        description="Kanban core",
        registered_component_kind="focus-core",
        registered_component_name="SchedulingKanbanCore",
        default_starting_column=0,
        default_column_span=12,
        default_row_index=0,
        min_column_span=8,
        max_column_span=12,
        canvas_config={},
    )
    defaults.update(kwargs)
    return create_core(db, **defaults)


@pytest.fixture
def tenant_company():
    s = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"FTI SAW {suffix}",
            slug=f"ftisaw-{suffix}",
            is_active=True,
            vertical="funeral_home",
        )
        s.add(co)
        s.commit()
        yield co.id
        s.delete(co)
        s.commit()
    finally:
        s.close()


# ═══ Service-layer tests ═══════════════════════════════════════════


class TestSessionAwareUpdate:
    def test_update_with_session_token_mutates_in_place(self, db):
        c = _make_core(db, slug="kb-saw-1")
        original_id = c.id
        original_version = c.version
        session_id = str(uuid.uuid4())

        updated = update_core(
            db,
            c.id,
            display_name="Renamed In Place",
            edit_session_id=session_id,
            updated_by=None,
        )

        # In-place mutation: same id, same version.
        assert updated.id == original_id
        assert updated.version == original_version
        assert updated.is_active is True
        assert updated.display_name == "Renamed In Place"
        assert str(updated.last_edit_session_id) == session_id
        assert updated.last_edit_session_at is not None

    def test_consecutive_same_session_updates_stay_in_place(self, db):
        c = _make_core(db, slug="kb-saw-2")
        session_id = str(uuid.uuid4())
        original_id = c.id

        # First update — sets the session pointer.
        r1 = update_core(
            db, c.id, display_name="v-a",
            edit_session_id=session_id, updated_by=None,
        )
        # Second update — same session, should still mutate in place.
        r2 = update_core(
            db, r1.id, display_name="v-b",
            edit_session_id=session_id, updated_by=None,
        )
        # Third update — same session, still in place.
        r3 = update_core(
            db, r2.id, display_name="v-c",
            edit_session_id=session_id, updated_by=None,
        )

        assert r1.id == original_id
        assert r2.id == original_id
        assert r3.id == original_id
        assert r3.version == 1  # unchanged across the scrub session
        assert r3.display_name == "v-c"

        # Confirm: only one row exists for this slug.
        all_rows = (
            db.query(FocusCore).filter(FocusCore.core_slug == "kb-saw-2").all()
        )
        assert len(all_rows) == 1

    def test_different_session_triggers_version_bump(self, db):
        c = _make_core(db, slug="kb-saw-3")
        session_a = str(uuid.uuid4())
        session_b = str(uuid.uuid4())

        r1 = update_core(
            db, c.id, display_name="v-a",
            edit_session_id=session_a, updated_by=None,
        )
        # Different session — should version-bump.
        r2 = update_core(
            db, r1.id, display_name="v-b",
            edit_session_id=session_b, updated_by=None,
        )

        assert r1.id == c.id  # first edit stayed in place
        assert r2.id != r1.id  # second edit forked
        assert r2.version == r1.version + 1
        # Prior row marked inactive.
        db.refresh(r1)
        assert r1.is_active is False
        # New row carries the new session token.
        assert str(r2.last_edit_session_id) == session_b

    def test_stale_session_window_triggers_version_bump(self, db):
        c = _make_core(db, slug="kb-saw-4")
        session_id = str(uuid.uuid4())

        r1 = update_core(
            db, c.id, display_name="v-a",
            edit_session_id=session_id, updated_by=None,
        )
        # Backdate the timestamp past the 5-min window.
        stale_ts = datetime.now(timezone.utc) - timedelta(
            seconds=EDIT_SESSION_WINDOW_SECONDS + 60
        )
        r1.last_edit_session_at = stale_ts
        db.commit()

        # Same session id, but window expired.
        r2 = update_core(
            db, r1.id, display_name="v-b",
            edit_session_id=session_id, updated_by=None,
        )
        assert r2.id != r1.id
        assert r2.version == r1.version + 1

    def test_update_without_session_token_version_bumps(self, db):
        """B-1 backward-compat: callers that omit edit_session_id
        keep getting version bumps."""
        c = _make_core(db, slug="kb-saw-5")
        r2 = update_core(db, c.id, display_name="v2", updated_by=None)
        assert r2.id != c.id
        assert r2.version == c.version + 1
        db.refresh(c)
        assert c.is_active is False

    def test_in_place_mutation_preserves_unset_fields(self, db):
        c = _make_core(db, slug="kb-saw-6")
        session_id = str(uuid.uuid4())
        original_description = c.description
        original_chrome = dict(c.chrome or {})

        # Only touch display_name — description + chrome should
        # carry through.
        updated = update_core(
            db, c.id, display_name="new",
            edit_session_id=session_id, updated_by=None,
        )
        assert updated.description == original_description
        assert dict(updated.chrome or {}) == original_chrome

    def test_in_place_mutation_advances_session_at_each_call(self, db):
        c = _make_core(db, slug="kb-saw-7")
        session_id = str(uuid.uuid4())

        r1 = update_core(
            db, c.id, display_name="a",
            edit_session_id=session_id, updated_by=None,
        )
        t1 = r1.last_edit_session_at
        # Tiny sleep would be flaky — re-fetch + re-update and assert
        # timestamp advanced (or equal — both are tolerated, but the
        # field should be set).
        r2 = update_core(
            db, r1.id, display_name="b",
            edit_session_id=session_id, updated_by=None,
        )
        assert r2.last_edit_session_at is not None
        assert r2.last_edit_session_at >= t1

    def test_update_against_inactive_core_raises_stale(self, db):
        c1 = _make_core(db, slug="kb-saw-8")
        # First touch under session A — mutates in place (c1 stays
        # active; the session pointer is now session_a).
        c1_id = c1.id
        update_core(
            db, c1.id, display_name="v1b",
            edit_session_id=str(uuid.uuid4()), updated_by=None,
        )
        # Now a DIFFERENT session — this version-bumps because
        # session_b doesn't match the row's session_a pointer.
        c2 = update_core(
            db, c1_id, display_name="v2",
            edit_session_id=str(uuid.uuid4()), updated_by=None,
        )
        assert c2.id != c1_id  # bumped
        # Now try to update the inactive id.
        with pytest.raises(StaleCoreVersionError) as ei:
            update_core(
                db, c1_id, display_name="never",
                edit_session_id=str(uuid.uuid4()), updated_by=None,
            )
        assert ei.value.inactive_id == c1_id
        assert ei.value.active_id == c2.id
        assert ei.value.slug == "kb-saw-8"

    def test_in_place_mutation_does_not_create_new_row(self, db):
        c = _make_core(db, slug="kb-saw-9")
        session_id = str(uuid.uuid4())
        for i in range(5):
            update_core(
                db, c.id, display_name=f"v-{i}",
                edit_session_id=session_id, updated_by=None,
            )
        # Single row only.
        rows = (
            db.query(FocusCore)
            .filter(FocusCore.core_slug == "kb-saw-9")
            .all()
        )
        assert len(rows) == 1
        assert rows[0].version == 1
        assert rows[0].display_name == "v-4"

    def test_in_place_mutation_chrome_persists(self, db):
        c = _make_core(db, slug="kb-saw-10")
        session_id = str(uuid.uuid4())

        updated = update_core(
            db, c.id,
            chrome={"preset": "frosted", "elevation": 50},
            edit_session_id=session_id, updated_by=None,
        )
        # In-place: same id, chrome persisted.
        assert updated.id == c.id
        assert dict(updated.chrome) == {"preset": "frosted", "elevation": 50}

        # Refetch from DB to confirm persistence.
        fresh = get_core_by_id(db, c.id)
        assert dict(fresh.chrome) == {"preset": "frosted", "elevation": 50}


# ═══ Cascade tests ═════════════════════════════════════════════════


class TestSessionAwareCascade:
    def test_resolver_sees_in_place_chrome_change(self, db, tenant_company):
        c = _make_core(db, slug="kb-saw-cas-1")
        _ = create_template(
            db,
            scope="vertical_default",
            vertical="funeral_home",
            template_slug="cas-tpl-1",
            display_name="Cascade Template",
            inherits_from_core_id=c.id,
            rows=[],
            canvas_config={},
        )
        session_id = str(uuid.uuid4())

        # In-place mutate chrome to a new preset.
        update_core(
            db, c.id,
            chrome={"preset": "frosted"},
            edit_session_id=session_id, updated_by=None,
        )

        resolved = resolve_focus(
            db, template_slug="cas-tpl-1", vertical="funeral_home",
            tenant_id=tenant_company,
        )
        # Active core's chrome surfaces in the resolved blob.
        assert resolved.resolved_chrome is not None
        assert resolved.resolved_chrome.get("preset") == "frosted"

    def test_in_place_mutation_propagates_through_template_without_reversioning(
        self, db, tenant_company
    ):
        """Critical property: an in-place chrome mutation (Tier 1)
        flows through to resolved_chrome immediately, with NO need
        for templates to be re-versioned or re-pointed. This is the
        whole point of session-aware mutation: 30 scrub frames don't
        produce 30 templates-needing-re-cascade."""
        c = _make_core(db, slug="kb-saw-cas-2")
        _ = create_template(
            db,
            scope="vertical_default",
            vertical="funeral_home",
            template_slug="cas-tpl-2",
            display_name="Cascade Template 2",
            inherits_from_core_id=c.id,
            rows=[],
            canvas_config={},
        )

        sid = str(uuid.uuid4())
        # In-place mutate (same session as first touch).
        update_core(
            db, c.id, chrome={"preset": "modal"},
            edit_session_id=sid, updated_by=None,
        )
        # Same id; new chrome.
        active = get_core_by_slug(db, "kb-saw-cas-2")
        assert active.id == c.id
        assert dict(active.chrome).get("preset") == "modal"

        resolved = resolve_focus(
            db, template_slug="cas-tpl-2", vertical="funeral_home",
            tenant_id=tenant_company,
        )
        assert resolved.resolved_chrome is not None
        assert resolved.resolved_chrome.get("preset") == "modal"

    def test_resolved_chrome_reflects_in_place_edits_across_session(
        self, db, tenant_company
    ):
        """Many in-place edits during one editor session all surface
        through the resolver against the SAME template row — no
        cascade-staleness anywhere along the way.
        """
        c = _make_core(db, slug="kb-saw-cas-3")
        _ = create_template(
            db,
            scope="vertical_default",
            vertical="funeral_home",
            template_slug="cas-tpl-3",
            display_name="Cascade Template 3",
            inherits_from_core_id=c.id,
            rows=[],
            canvas_config={},
        )
        sid = str(uuid.uuid4())
        for elevation in (10, 30, 60, 90):
            update_core(
                db, c.id, chrome={"preset": "card", "elevation": elevation},
                edit_session_id=sid, updated_by=None,
            )
            r = resolve_focus(
                db, template_slug="cas-tpl-3", vertical="funeral_home",
                tenant_id=tenant_company,
            )
            assert r.resolved_chrome is not None
            assert r.resolved_chrome.get("preset") == "card"
            assert r.resolved_chrome.get("elevation") == elevation

        # Confirm: only one row for the slug — no version bumps
        # accumulated.
        rows = (
            db.query(FocusCore)
            .filter(FocusCore.core_slug == "kb-saw-cas-3")
            .all()
        )
        assert len(rows) == 1
        assert rows[0].version == 1


# ═══ API surface — 410 Gone for stale core ═══════════════════════


@pytest.fixture
def api_ctx():
    """Minimal platform-admin context for hitting the PUT endpoint."""
    s = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        platform_admin = PlatformUser(
            id=str(uuid.uuid4()),
            email=f"saw-{suffix}@bridgeable.test",
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


class TestApiStaleCoreReturns410:
    def test_put_against_inactive_returns_410_with_active_id(
        self, client, api_ctx
    ):
        s = SessionLocal()
        try:
            c1 = create_core(
                s,
                core_slug="kb-saw-api-1",
                display_name="API Saw",
                registered_component_kind="focus-core",
                registered_component_name="X",
                canvas_config={},
            )
            inactive_id = c1.id
            # First touch under session A — mutates in place. Row
            # now has session_a pointer.
            update_core(
                s, c1.id, display_name="v1b",
                edit_session_id=str(uuid.uuid4()), updated_by=None,
            )
            # Different session — version-bumps. Now c1 is inactive.
            c2 = update_core(
                s, c1.id, display_name="v2",
                edit_session_id=str(uuid.uuid4()), updated_by=None,
            )
            assert c2.id != inactive_id
            active_id = c2.id
        finally:
            s.close()

        headers = {"Authorization": f"Bearer {api_ctx['platform_token']}"}
        res = client.put(
            f"{API_ROOT}/cores/{inactive_id}",
            json={"display_name": "should-fail", "edit_session_id": str(uuid.uuid4())},
            headers=headers,
        )
        assert res.status_code == 410
        body = res.json()
        # FastAPI wraps detail as either string or structured dict.
        detail = body.get("detail")
        assert isinstance(detail, dict)
        assert detail.get("inactive_core_id") == inactive_id
        assert detail.get("active_core_id") == active_id
        assert detail.get("slug") == "kb-saw-api-1"

    def test_put_with_session_round_trips_metadata(self, client, api_ctx):
        s = SessionLocal()
        try:
            c = create_core(
                s,
                core_slug="kb-saw-api-2",
                display_name="API Round Trip",
                registered_component_kind="focus-core",
                registered_component_name="X",
                canvas_config={},
            )
            core_id = c.id
        finally:
            s.close()

        headers = {"Authorization": f"Bearer {api_ctx['platform_token']}"}
        sid = str(uuid.uuid4())
        res = client.put(
            f"{API_ROOT}/cores/{core_id}",
            json={"display_name": "round", "edit_session_id": sid},
            headers=headers,
        )
        assert res.status_code == 200
        body = res.json()
        assert body["id"] == core_id  # in-place — id unchanged
        assert body["version"] == 1  # version unchanged
        assert body.get("last_edit_session_id") == sid
        assert body.get("last_edit_session_at") is not None


# ═══ Migration reversibility smoke ═════════════════════════════════


class TestMigrationR102:
    def test_columns_exist(self, db):
        """The model + DB schema agree on the new r102 columns."""
        c = _make_core(db, slug="kb-saw-mig-1")
        # Initial: both fields NULL.
        assert c.last_edit_session_id is None
        assert c.last_edit_session_at is None
        # After a session-aware update, both populated.
        sid = str(uuid.uuid4())
        updated = update_core(
            db, c.id, display_name="x",
            edit_session_id=sid, updated_by=None,
        )
        assert str(updated.last_edit_session_id) == sid
        assert updated.last_edit_session_at is not None
