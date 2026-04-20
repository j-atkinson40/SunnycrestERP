"""Phase 6 — briefing package + API + scheduler + legacy-regression tests.

Covers:
  - Briefing Pydantic types + preferences CRUD + legacy blocklist → allowlist
    translation
  - Data sources (legacy context builders reused, triage queues aggregated,
    Call Intelligence preserved)
  - Generator (prompt call parsed, stub fallback on AI failure)
  - /v2 API endpoints (7 endpoints + permission scoping + tenant isolation)
  - Scheduler sweep logic (window fire, DB idempotency)
  - Space-awareness (different active_space → different section emphasis)
  - Call Intelligence integration (overnight_calls present when RC
    extractions exist, absent when not)
  - Legacy regression (legacy briefing_service.py context builders still
    callable; /briefings/briefing endpoint unchanged)

Intelligence calls are monkey-patched where needed — we don't hit the
live Anthropic API in tests. The space-awareness + narrative tests
assert on the rendered PROMPT variables (i.e. what the AI would see),
not the AI output, so they're deterministic.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _make_ctx(
    *,
    role_slug: str = "admin",
    vertical: str = "manufacturing",
    active_space: str | None = None,
):
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
            name=f"P6-{suffix}",
            slug=f"p6-{suffix}",
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
        prefs: dict = {}
        if active_space:
            space_id = str(uuid.uuid4())
            prefs = {
                "active_space_id": space_id,
                "spaces": [{"id": space_id, "name": active_space, "accent": "warm"}],
            }
        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"u-{suffix}@p6.co",
            first_name="Phase6",
            last_name="User",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,
            role_id=role.id,
            preferences=prefs,
        )
        db.add(user)
        db.commit()
        token = create_access_token({"sub": user.id, "company_id": co.id})
        return {
            "user_id": user.id,
            "company_id": co.id,
            "token": token,
            "slug": co.slug,
            "active_space": active_space,
        }
    finally:
        db.close()


@pytest.fixture
def tenant_ctx():
    return _make_ctx(role_slug="admin", vertical="manufacturing")


@pytest.fixture
def auth(tenant_ctx):
    return {
        "Authorization": f"Bearer {tenant_ctx['token']}",
        "X-Company-Slug": tenant_ctx["slug"],
    }


# ── Types + preferences ──────────────────────────────────────────────


class TestPreferences:
    def test_defaults(self, db_session, tenant_ctx):
        from app.models.user import User
        from app.services.briefings import get_preferences

        user = db_session.query(User).filter(User.id == tenant_ctx["user_id"]).first()
        prefs = get_preferences(user)
        assert prefs.morning_enabled is True
        assert prefs.evening_enabled is True
        assert prefs.morning_delivery_time == "07:00"
        assert prefs.evening_delivery_time == "17:00"
        assert "greeting" in prefs.morning_sections
        assert "day_summary" in prefs.evening_sections

    def test_seed_is_idempotent(self, db_session, tenant_ctx):
        from app.models.user import User
        from app.services.briefings import seed_preferences_for_user

        user = db_session.query(User).filter(User.id == tenant_ctx["user_id"]).first()
        a = seed_preferences_for_user(db_session, user)
        db_session.refresh(user)
        b = seed_preferences_for_user(db_session, user)
        # Same sections + role tracked.
        assert a.morning_sections == b.morning_sections
        assert "briefings_seeded_for_roles" in (user.preferences or {})

    def test_legacy_blocklist_translates_to_allowlist(
        self, db_session, tenant_ctx
    ):
        """Spec item #6 — AssistantProfile.disabled_briefing_items
        blocklist minus DEFAULT_SECTIONS → Phase 6 allowlist."""
        from app.models.assistant_profile import AssistantProfile
        from app.models.user import User
        from app.services.briefings import (
            MORNING_DEFAULT_SECTIONS,
            seed_preferences_for_user,
        )

        user = db_session.query(User).filter(User.id == tenant_ctx["user_id"]).first()
        ap = AssistantProfile(
            user_id=user.id,
            company_id=user.company_id,
            disabled_briefing_items=["flags", "overnight_calls"],
        )
        db_session.add(ap)
        db_session.commit()
        prefs = seed_preferences_for_user(db_session, user)
        # Translated: defaults minus disabled.
        assert "flags" not in prefs.morning_sections
        assert "overnight_calls" not in prefs.morning_sections
        # Other default sections preserved.
        assert "greeting" in prefs.morning_sections
        # Total count matches expectation.
        expected = [s for s in MORNING_DEFAULT_SECTIONS if s not in {"flags", "overnight_calls"}]
        assert prefs.morning_sections == expected

    def test_update_preferences_validates(self, db_session, tenant_ctx):
        from app.models.user import User
        from app.services.briefings import update_preferences

        user = db_session.query(User).filter(User.id == tenant_ctx["user_id"]).first()
        prefs = update_preferences(
            db_session,
            user,
            {"morning_delivery_time": "06:30", "morning_channels": ["in_app"]},
        )
        assert prefs.morning_delivery_time == "06:30"
        assert prefs.morning_channels == ["in_app"]


# ── Data sources ────────────────────────────────────────────────────


class TestDataSources:
    def test_collect_morning(self, db_session, tenant_ctx):
        from app.models.user import User
        from app.services.briefings import collect_data_for_morning_briefing

        user = db_session.query(User).filter(User.id == tenant_ctx["user_id"]).first()
        ctx = collect_data_for_morning_briefing(db_session, user)
        assert ctx.user_first_name == "Phase6"
        assert ctx.today_iso == date.today().isoformat()
        # Legacy builder output populated (executive always runs).
        assert "executive" in ctx.legacy_context

    def test_queue_summaries_aggregated(self, db_session, tenant_ctx):
        """Phase 5 integration — queue_summaries populated when queues
        have pending items. Seeds a task so task_triage has a count."""
        from app.models.user import User
        from app.services.briefings import collect_data_for_morning_briefing
        from app.services.task_service import create_task

        user = db_session.query(User).filter(User.id == tenant_ctx["user_id"]).first()
        create_task(
            db_session,
            company_id=user.company_id,
            title="Briefing data-source test",
            created_by_user_id=user.id,
            assignee_user_id=user.id,
            priority="normal",
        )
        ctx = collect_data_for_morning_briefing(db_session, user)
        # task_triage should appear.
        queue_ids = [q["queue_id"] for q in ctx.queue_summaries]
        assert "task_triage" in queue_ids

    def test_call_intelligence_integration(self, db_session, tenant_ctx):
        """Spec item #8 — preserve legacy _build_call_summary path.

        When RingCentralCallLog rows exist for yesterday, `overnight_calls`
        is populated. When absent, it's None.
        """
        from app.models.user import User
        from app.services.briefings import collect_data_for_morning_briefing

        user = db_session.query(User).filter(User.id == tenant_ctx["user_id"]).first()

        # No RC logs seeded → overnight_calls should be None / absent.
        ctx_empty = collect_data_for_morning_briefing(db_session, user)
        assert ctx_empty.overnight_calls is None

        # Seed a RingCentralCallLog for yesterday.
        try:
            from app.models.ringcentral_call_log import RingCentralCallLog
        except ImportError:
            pytest.skip("RingCentralCallLog model unavailable in this build")

        yesterday = datetime.now(timezone.utc).replace(
            hour=22, minute=0, second=0, microsecond=0
        ) - timedelta(days=1)
        log = RingCentralCallLog(
            id=str(uuid.uuid4()),
            tenant_id=user.company_id,
            started_at=yesterday,
            call_status="voicemail",
            order_created=False,
        )
        db_session.add(log)
        db_session.commit()

        ctx_with_calls = collect_data_for_morning_briefing(db_session, user)
        assert ctx_with_calls.overnight_calls is not None
        assert ctx_with_calls.overnight_calls.get("total") == 1
        assert ctx_with_calls.overnight_calls.get("voicemails") == 1


# ── Generator ───────────────────────────────────────────────────────


class TestGenerator:
    def test_stub_fallback_on_ai_failure(
        self, db_session, tenant_ctx, monkeypatch
    ):
        """When Intelligence fails, generator returns the deterministic stub
        narrative (so the user sees something). Narrative contains greeting
        + day of week."""
        from app.models.user import User
        from app.services.briefings import (
            collect_data_for_morning_briefing,
            generate_morning_briefing,
        )

        class _StubResult:
            status = "error"
            response_parsed = None
            response_text = None
            input_tokens = 0
            output_tokens = 0
            cost_usd = None
            latency_ms = 0

        monkeypatch.setattr(
            "app.services.intelligence.intelligence_service.execute",
            lambda *a, **k: _StubResult(),
        )

        user = db_session.query(User).filter(User.id == tenant_ctx["user_id"]).first()
        ctx = collect_data_for_morning_briefing(db_session, user)
        result = generate_morning_briefing(db_session, user, ctx)
        assert result.briefing_type == "morning"
        assert "Phase6" in result.narrative_text  # user first name
        assert result.generation_duration_ms is not None

    def test_parse_valid_ai_response(self, db_session, tenant_ctx, monkeypatch):
        """Well-shaped AI response returns narrative + validated sections."""
        from app.models.user import User
        from app.services.briefings import (
            collect_data_for_morning_briefing,
            generate_morning_briefing,
        )

        class _OkResult:
            status = "success"
            response_parsed = {
                "narrative_text": "Good morning, Phase6. It's Monday. All clear.",
                "structured_sections": {
                    "greeting": "Good morning, Phase6.",
                    "flags": [{"severity": "info", "title": "Nothing flagged"}],
                },
            }
            response_text = "..."
            input_tokens = 1234
            output_tokens = 456
            cost_usd = Decimal("0.003")
            latency_ms = 1800

        monkeypatch.setattr(
            "app.services.intelligence.intelligence_service.execute",
            lambda *a, **k: _OkResult(),
        )

        user = db_session.query(User).filter(User.id == tenant_ctx["user_id"]).first()
        ctx = collect_data_for_morning_briefing(db_session, user)
        result = generate_morning_briefing(db_session, user, ctx)
        assert "Good morning, Phase6" in result.narrative_text
        assert result.structured_sections.greeting == "Good morning, Phase6."
        assert result.structured_sections.flags == [
            {"severity": "info", "title": "Nothing flagged"}
        ]
        assert result.input_tokens == 1234
        assert result.intelligence_cost_usd == Decimal("0.003")


# ── Space-awareness (BLOCKING per spec item #7) ─────────────────────


class TestSpaceAwareness:
    @pytest.mark.parametrize(
        "space_name,expected_token",
        [
            ("Arrangement", "Arrangement"),
            ("Administrative", "Administrative"),
            ("Production", "Production"),
        ],
    )
    def test_active_space_reaches_prompt_variables(
        self, db_session, space_name, expected_token, monkeypatch
    ):
        """The prompt MUST receive active_space_name, so its Jinja branches
        can emphasize sections differently per space. We intercept the
        Intelligence call and assert on the variables passed."""
        from app.models.user import User
        from app.services.briefings import (
            collect_data_for_morning_briefing,
            generate_morning_briefing,
        )

        ctx_data = _make_ctx(
            role_slug="admin", vertical="manufacturing", active_space=space_name
        )

        captured: dict = {}

        class _Result:
            status = "success"
            response_parsed = {
                "narrative_text": f"Space: {space_name}.",
                "structured_sections": {"greeting": f"Space: {space_name}."},
            }
            response_text = None
            input_tokens = 0
            output_tokens = 0
            cost_usd = None
            latency_ms = 0

        def _fake_execute(db, prompt_key, variables=None, **kw):
            captured["prompt_key"] = prompt_key
            captured["variables"] = variables or {}
            return _Result()

        monkeypatch.setattr(
            "app.services.intelligence.intelligence_service.execute",
            _fake_execute,
        )

        user = (
            db_session.query(User)
            .filter(User.id == ctx_data["user_id"])
            .first()
        )
        data_ctx = collect_data_for_morning_briefing(db_session, user)
        generate_morning_briefing(db_session, user, data_ctx)

        # Prompt receives active_space_name — that's what branches the Jinja.
        assert captured["prompt_key"] == "briefing.morning"
        assert captured["variables"].get("active_space_name") == expected_token

    def test_different_spaces_produce_different_generation_contexts(
        self, db_session, monkeypatch
    ):
        """Two users with different active spaces produce briefings whose
        generation_context records the different space names. This is the
        minimal measurable assertion that space selection reaches the
        persisted record (beyond just the prompt variables)."""
        from app.models.user import User
        from app.services.briefings import (
            collect_data_for_morning_briefing,
            generate_morning_briefing,
        )

        arr = _make_ctx(
            role_slug="admin", vertical="manufacturing", active_space="Arrangement"
        )
        adm = _make_ctx(
            role_slug="admin",
            vertical="manufacturing",
            active_space="Administrative",
        )

        class _R:
            status = "success"
            response_parsed = {
                "narrative_text": "ok",
                "structured_sections": {"greeting": "ok"},
            }
            response_text = None
            input_tokens = 0
            output_tokens = 0
            cost_usd = None
            latency_ms = 0

        monkeypatch.setattr(
            "app.services.intelligence.intelligence_service.execute",
            lambda *a, **k: _R(),
        )

        arr_user = db_session.query(User).filter(User.id == arr["user_id"]).first()
        adm_user = db_session.query(User).filter(User.id == adm["user_id"]).first()

        arr_ctx = collect_data_for_morning_briefing(db_session, arr_user)
        adm_ctx = collect_data_for_morning_briefing(db_session, adm_user)

        arr_result = generate_morning_briefing(db_session, arr_user, arr_ctx)
        adm_result = generate_morning_briefing(db_session, adm_user, adm_ctx)

        assert arr_result.active_space_name == "Arrangement"
        assert adm_result.active_space_name == "Administrative"


# ── /v2 API ─────────────────────────────────────────────────────────


class TestBriefingsV2API:
    def test_preferences_get_and_patch(self, client, auth):
        r = client.get("/api/v1/briefings/v2/preferences", headers=auth)
        assert r.status_code == 200
        prefs = r.json()
        assert prefs["morning_enabled"] is True
        r2 = client.patch(
            "/api/v1/briefings/v2/preferences",
            json={"morning_delivery_time": "06:45"},
            headers=auth,
        )
        assert r2.status_code == 200
        assert r2.json()["morning_delivery_time"] == "06:45"

    def test_list_empty(self, client, auth):
        r = client.get("/api/v1/briefings/v2", headers=auth)
        assert r.status_code == 200
        assert r.json() == []

    def test_latest_null_when_none(self, client, auth):
        r = client.get(
            "/api/v1/briefings/v2/latest?briefing_type=morning", headers=auth
        )
        assert r.status_code == 200
        assert r.json() in (None, {})

    def test_generate_creates_briefing(self, client, auth, monkeypatch):
        class _R:
            status = "success"
            response_parsed = {
                "narrative_text": "Good morning, Phase6. Clean start.",
                "structured_sections": {
                    "greeting": "Good morning, Phase6.",
                },
            }
            response_text = None
            input_tokens = 100
            output_tokens = 50
            cost_usd = Decimal("0.001")
            latency_ms = 1000

        monkeypatch.setattr(
            "app.services.intelligence.intelligence_service.execute",
            lambda *a, **k: _R(),
        )
        r = client.post(
            "/api/v1/briefings/v2/generate",
            json={"briefing_type": "morning", "deliver": False},
            headers=auth,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["briefing_type"] == "morning"
        assert "Good morning" in body["narrative_text"]
        assert body["structured_sections"]["greeting"] == "Good morning, Phase6."

        # Latest endpoint now returns it.
        r2 = client.get(
            "/api/v1/briefings/v2/latest?briefing_type=morning", headers=auth
        )
        assert r2.status_code == 200
        latest = r2.json()
        assert latest is not None
        assert latest["id"] == body["id"]

    def test_mark_read(self, client, auth, monkeypatch):
        class _R:
            status = "success"
            response_parsed = {
                "narrative_text": "n",
                "structured_sections": {"greeting": "n"},
            }
            response_text = None
            input_tokens = 0
            output_tokens = 0
            cost_usd = None
            latency_ms = 0

        monkeypatch.setattr(
            "app.services.intelligence.intelligence_service.execute",
            lambda *a, **k: _R(),
        )
        gen = client.post(
            "/api/v1/briefings/v2/generate",
            json={"briefing_type": "morning", "deliver": False},
            headers=auth,
        )
        bid = gen.json()["id"]
        r = client.post(
            f"/api/v1/briefings/v2/{bid}/mark-read", headers=auth
        )
        assert r.status_code == 200
        assert r.json()["read_at"] is not None

    def test_auth_required(self, client):
        r = client.get("/api/v1/briefings/v2")
        assert r.status_code in (401, 403)

    def test_tenant_isolation(self, client, auth):
        """A briefing generated for tenant A is 404 for tenant B."""

        class _R:
            status = "success"
            response_parsed = {
                "narrative_text": "n",
                "structured_sections": {"greeting": "n"},
            }
            response_text = None
            input_tokens = 0
            output_tokens = 0
            cost_usd = None
            latency_ms = 0

        import unittest.mock as mock

        with mock.patch(
            "app.services.intelligence.intelligence_service.execute",
            return_value=_R(),
        ):
            gen = client.post(
                "/api/v1/briefings/v2/generate",
                json={"briefing_type": "morning"},
                headers=auth,
            )
            bid = gen.json()["id"]

        other_ctx = _make_ctx(role_slug="admin", vertical="manufacturing")
        other_auth = {
            "Authorization": f"Bearer {other_ctx['token']}",
            "X-Company-Slug": other_ctx["slug"],
        }
        r = client.get(f"/api/v1/briefings/v2/{bid}", headers=other_auth)
        assert r.status_code == 404


# ── Scheduler sweep ─────────────────────────────────────────────────


class TestSweep:
    def test_window_fire_logic(self):
        from datetime import datetime as _dt
        from zoneinfo import ZoneInfo

        from app.services.briefings.scheduler_integration import _window_fired

        tz = ZoneInfo("America/New_York")
        # Simulate local 07:10 — window should include 07:00 target.
        local_now = _dt(2026, 4, 21, 7, 10, 0, tzinfo=tz)
        assert _window_fired(local_now, "07:00", 15) is True
        assert _window_fired(local_now, "06:30", 15) is False  # outside window
        assert _window_fired(local_now, "07:30", 15) is False  # in future

    def test_already_generated_skip(self, db_session, tenant_ctx, monkeypatch):
        """Sweep skips users who already have a briefing of that type today."""
        from app.models.briefing import Briefing
        from app.services.briefings.scheduler_integration import (
            _already_generated_today,
        )

        # Seed a row for today.
        today = date.today()
        b = Briefing(
            id=str(uuid.uuid4()),
            company_id=tenant_ctx["company_id"],
            user_id=tenant_ctx["user_id"],
            briefing_type="morning",
            generated_at=datetime.now(timezone.utc),
            delivery_channels=[],
            narrative_text="seed",
            structured_sections={"greeting": "seed"},
        )
        db_session.add(b)
        db_session.commit()

        assert (
            _already_generated_today(
                db_session, tenant_ctx["user_id"], "morning", today
            )
            is True
        )
        assert (
            _already_generated_today(
                db_session, tenant_ctx["user_id"], "evening", today
            )
            is False
        )


# ── Legacy coexistence (BLOCKING per spec item #11) ─────────────────


class TestLegacyCoexistence:
    def test_legacy_briefings_endpoint_still_registered(self, client, auth):
        """Legacy `/briefings/briefing` + `/briefings/action-items` endpoints
        stay functional — they're what `MorningBriefingCard` consumes."""
        # Note: legacy endpoint returns 200 with reason=no_profile for a user
        # without an employee_profile, which is the fixture's default.
        r = client.get("/api/v1/briefings/briefing", headers=auth)
        assert r.status_code == 200
        r2 = client.get("/api/v1/briefings/action-items", headers=auth)
        assert r2.status_code == 200

    def test_legacy_prompt_still_seeded(self, db_session):
        """`briefing.daily_summary` (legacy) must still be active — Phase 6
        adds briefing.morning/evening alongside it, doesn't retire it."""
        from app.models.intelligence import (
            IntelligencePrompt,
            IntelligencePromptVersion,
        )

        legacy = (
            db_session.query(IntelligencePrompt)
            .filter(
                IntelligencePrompt.company_id.is_(None),
                IntelligencePrompt.prompt_key == "briefing.daily_summary",
            )
            .first()
        )
        assert legacy is not None, "Legacy daily_summary prompt must stay seeded"
        active = (
            db_session.query(IntelligencePromptVersion)
            .filter(
                IntelligencePromptVersion.prompt_id == legacy.id,
                IntelligencePromptVersion.status == "active",
            )
            .first()
        )
        assert active is not None

    def test_legacy_context_builders_still_importable(self, db_session, tenant_ctx):
        """Phase 6 depends on importing the legacy context builders. If
        someone renames one in briefing_service.py, this test fails."""
        from app.services.briefing_service import (
            _build_call_summary,
            _build_executive_context,
            _build_funeral_scheduling_context,
            _build_invoicing_ar_context,
            _build_precast_scheduling_context,
            _build_safety_compliance_context,
        )

        # Smoke-call two of the builders we most rely on.
        exec_ctx = _build_executive_context(db_session, tenant_ctx["company_id"])
        assert isinstance(exec_ctx, dict)
        calls = _build_call_summary(db_session, tenant_ctx["company_id"])
        assert isinstance(calls, dict)

    def test_new_phase6_prompts_seeded(self, db_session):
        """Phase 6 seed script produces briefing.morning + briefing.evening."""
        from app.models.intelligence import (
            IntelligencePrompt,
            IntelligencePromptVersion,
        )

        for key in ("briefing.morning", "briefing.evening"):
            prompt = (
                db_session.query(IntelligencePrompt)
                .filter(
                    IntelligencePrompt.company_id.is_(None),
                    IntelligencePrompt.prompt_key == key,
                )
                .first()
            )
            assert prompt is not None, f"{key} must be seeded"
            active = (
                db_session.query(IntelligencePromptVersion)
                .filter(
                    IntelligencePromptVersion.prompt_id == prompt.id,
                    IntelligencePromptVersion.status == "active",
                )
                .first()
            )
            assert active is not None, f"{key} must have an active version"
