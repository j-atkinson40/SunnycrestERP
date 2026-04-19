"""Phase 3b tests — Draft CRUD, activation, rollback, test-run, audit log.

Tests invoke route handlers directly against an in-memory SQLite DB,
mirroring the pattern established by test_intelligence_phase3a.py.
Admin permission (`require_admin`) is not reached in unit-test mode;
super_admin enforcement is tested via direct helper call.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import JSON, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.database import Base
from app.models.intelligence import (
    IntelligenceExecution,
    IntelligencePrompt,
    IntelligencePromptAuditLog,
    IntelligencePromptVersion,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:")

    from app.models.agent import AgentJob  # noqa: F401
    from app.models.company import Company  # noqa: F401
    from app.models.role import Role  # noqa: F401
    from app.models.user import User  # noqa: F401
    from app.models.workflow import WorkflowRun, WorkflowRunStep  # noqa: F401

    tables_needed = [
        "companies",
        "roles",
        "users",
        "agent_jobs",
        "workflows",
        "workflow_runs",
        "workflow_run_steps",
        "intelligence_prompts",
        "intelligence_prompt_versions",
        "intelligence_model_routes",
        "intelligence_experiments",
        "intelligence_conversations",
        "intelligence_executions",
        "intelligence_messages",
        "intelligence_prompt_audit_log",
    ]
    tables = [
        Base.metadata.tables[t]
        for t in tables_needed
        if t in Base.metadata.tables
    ]

    jsonb_swaps: list[tuple] = []
    for t in tables:
        for col in t.columns:
            if isinstance(col.type, JSONB):
                jsonb_swaps.append((col, col.type))
                col.type = JSON()

    Base.metadata.create_all(eng, tables=tables)

    for col, original in jsonb_swaps:
        col.type = original
    return eng


@pytest.fixture
def db(engine):
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn)
    yield session
    session.close()
    trans.rollback()
    conn.close()


@pytest.fixture
def company(db):
    from app.models.company import Company

    c = Company(
        id=str(uuid.uuid4()),
        name="Test Co",
        slug="testco",
        is_active=True,
    )
    db.add(c)
    db.flush()
    return c


@pytest.fixture
def admin_role(db, company):
    from app.models.role import Role

    r = Role(
        id=str(uuid.uuid4()),
        company_id=company.id,
        name="Admin",
        slug="admin",
        is_system=True,
    )
    db.add(r)
    db.flush()
    return r


@pytest.fixture
def admin_user(db, company, admin_role):
    from app.models.user import User

    u = User(
        id=str(uuid.uuid4()),
        company_id=company.id,
        email="admin@test.co",
        first_name="Ada",
        last_name="Admin",
        hashed_password="x",
        is_active=True,
        is_super_admin=False,
        role_id=admin_role.id,
    )
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def super_admin_user(db, company, admin_role):
    from app.models.user import User

    u = User(
        id=str(uuid.uuid4()),
        company_id=company.id,
        email="super@test.co",
        first_name="Sam",
        last_name="Super",
        hashed_password="x",
        is_active=True,
        is_super_admin=True,
        role_id=admin_role.id,
    )
    db.add(u)
    db.flush()
    return u


def _make_prompt(db, key, *, company_id=None, domain="scribe"):
    p = IntelligencePrompt(
        id=str(uuid.uuid4()),
        company_id=company_id,
        prompt_key=key,
        display_name=f"Test {key}",
        domain=domain,
    )
    db.add(p)
    db.flush()
    return p


def _make_version(
    db,
    prompt_id,
    *,
    version_number=1,
    status="active",
    system="say hello to {{ name }}",
    user_template="hi {{ name }}",
    variable_schema=None,
    model_preference="simple",
):
    v = IntelligencePromptVersion(
        id=str(uuid.uuid4()),
        prompt_id=prompt_id,
        version_number=version_number,
        system_prompt=system,
        user_template=user_template,
        variable_schema=variable_schema or {"name": {"required": True}},
        model_preference=model_preference,
        status=status,
        activated_at=datetime.now(timezone.utc) if status == "active" else None,
    )
    db.add(v)
    db.flush()
    return v


@pytest.fixture
def tenant_prompt(db, company):
    """Tenant-scoped prompt — admin can edit, super_admin not required."""
    p = _make_prompt(db, "scribe.tenant_test", company_id=company.id)
    v = _make_version(db, p.id, version_number=1, status="active")
    return p, v


@pytest.fixture
def platform_prompt(db):
    """Platform-global prompt — requires super_admin to edit."""
    p = _make_prompt(db, "briefing.platform_test", company_id=None)
    v = _make_version(db, p.id, version_number=1, status="active")
    return p, v


# ---------------------------------------------------------------------------
# Draft creation
# ---------------------------------------------------------------------------


class TestDraftCreate:
    def test_create_draft_from_active_version(self, db, admin_user, tenant_prompt):
        from app.api.routes.intelligence import create_draft_endpoint
        from app.schemas.intelligence import DraftCreateRequest

        prompt, active = tenant_prompt
        draft = create_draft_endpoint(
            prompt_id=prompt.id,
            body=DraftCreateRequest(changelog="adding context"),
            current_user=admin_user, db=db,
        )
        assert draft.status == "draft"
        assert draft.version_number == 2
        assert draft.system_prompt == active.system_prompt
        assert draft.changelog == "adding context"

    def test_create_draft_requires_existing_prompt(self, db, admin_user):
        from fastapi import HTTPException
        from app.api.routes.intelligence import create_draft_endpoint
        from app.schemas.intelligence import DraftCreateRequest

        with pytest.raises(HTTPException) as exc:
            create_draft_endpoint(
                prompt_id="nonexistent",
                body=DraftCreateRequest(),
                current_user=admin_user, db=db,
            )
        assert exc.value.status_code == 404

    def test_only_one_draft_at_a_time(self, db, admin_user, tenant_prompt):
        from fastapi import HTTPException
        from app.api.routes.intelligence import create_draft_endpoint
        from app.schemas.intelligence import DraftCreateRequest

        prompt, _ = tenant_prompt
        # First draft — OK
        create_draft_endpoint(
            prompt_id=prompt.id,
            body=DraftCreateRequest(),
            current_user=admin_user, db=db,
        )
        # Second draft — 409
        with pytest.raises(HTTPException) as exc:
            create_draft_endpoint(
                prompt_id=prompt.id,
                body=DraftCreateRequest(),
                current_user=admin_user, db=db,
            )
        assert exc.value.status_code == 409

    def test_platform_prompt_draft_requires_super_admin(
        self, db, admin_user, super_admin_user, platform_prompt
    ):
        from fastapi import HTTPException
        from app.api.routes.intelligence import create_draft_endpoint
        from app.schemas.intelligence import DraftCreateRequest

        prompt, _ = platform_prompt
        # Admin — denied
        with pytest.raises(HTTPException) as exc:
            create_draft_endpoint(
                prompt_id=prompt.id,
                body=DraftCreateRequest(),
                current_user=admin_user, db=db,
            )
        assert exc.value.status_code == 403
        # Super admin — allowed
        draft = create_draft_endpoint(
            prompt_id=prompt.id,
            body=DraftCreateRequest(),
            current_user=super_admin_user, db=db,
        )
        assert draft.status == "draft"


# ---------------------------------------------------------------------------
# Draft update / delete
# ---------------------------------------------------------------------------


class TestDraftMutation:
    def test_update_draft_only_works_on_drafts(
        self, db, admin_user, tenant_prompt
    ):
        from app.api.routes.intelligence import (
            create_draft_endpoint,
            update_draft_endpoint,
        )
        from app.schemas.intelligence import DraftCreateRequest, DraftUpdateRequest

        prompt, _ = tenant_prompt
        draft = create_draft_endpoint(
            prompt_id=prompt.id,
            body=DraftCreateRequest(),
            current_user=admin_user, db=db,
        )
        updated = update_draft_endpoint(
            prompt_id=prompt.id,
            version_id=draft.id,
            body=DraftUpdateRequest(system_prompt="NEW SYSTEM"),
            current_user=admin_user, db=db,
        )
        assert updated.system_prompt == "NEW SYSTEM"

    def test_update_draft_returns_409_on_active(self, db, admin_user, tenant_prompt):
        from fastapi import HTTPException
        from app.api.routes.intelligence import update_draft_endpoint
        from app.schemas.intelligence import DraftUpdateRequest

        prompt, active = tenant_prompt
        with pytest.raises(HTTPException) as exc:
            update_draft_endpoint(
                prompt_id=prompt.id,
                version_id=active.id,
                body=DraftUpdateRequest(system_prompt="bad"),
                current_user=admin_user, db=db,
            )
        assert exc.value.status_code == 409

    def test_delete_draft_only_on_drafts(self, db, admin_user, tenant_prompt):
        from fastapi import HTTPException
        from app.api.routes.intelligence import (
            create_draft_endpoint,
            delete_draft_endpoint,
        )
        from app.schemas.intelligence import DraftCreateRequest

        prompt, active = tenant_prompt
        draft = create_draft_endpoint(
            prompt_id=prompt.id,
            body=DraftCreateRequest(),
            current_user=admin_user, db=db,
        )
        # Delete draft — OK
        delete_draft_endpoint(
            prompt_id=prompt.id,
            version_id=draft.id,
            current_user=admin_user, db=db,
        )
        # Delete active — 409
        with pytest.raises(HTTPException) as exc:
            delete_draft_endpoint(
                prompt_id=prompt.id,
                version_id=active.id,
                current_user=admin_user, db=db,
            )
        assert exc.value.status_code == 409


# ---------------------------------------------------------------------------
# Activation
# ---------------------------------------------------------------------------


class TestActivation:
    def test_activate_requires_changelog(self, db, admin_user, tenant_prompt):
        from pydantic import ValidationError
        from app.schemas.intelligence import ActivateRequest

        # The schema constrains changelog min_length=1 — empty raises pydantic
        with pytest.raises(ValidationError):
            ActivateRequest(changelog="")

    def test_activate_archives_previous_active(
        self, db, admin_user, tenant_prompt
    ):
        from app.api.routes.intelligence import (
            activate_draft_endpoint,
            create_draft_endpoint,
        )
        from app.schemas.intelligence import ActivateRequest, DraftCreateRequest

        prompt, prev_active = tenant_prompt
        draft = create_draft_endpoint(
            prompt_id=prompt.id,
            body=DraftCreateRequest(),
            current_user=admin_user, db=db,
        )
        new_active = activate_draft_endpoint(
            prompt_id=prompt.id,
            version_id=draft.id,
            body=ActivateRequest(changelog="promote v2"),
            current_user=admin_user, db=db,
        )
        db.refresh(prev_active)
        assert new_active.status == "active"
        assert prev_active.status == "retired"

    def test_activate_platform_prompt_requires_super_admin(
        self, db, admin_user, super_admin_user, platform_prompt
    ):
        from fastapi import HTTPException
        from app.api.routes.intelligence import (
            activate_draft_endpoint,
            create_draft_endpoint,
        )
        from app.schemas.intelligence import ActivateRequest, DraftCreateRequest

        prompt, _ = platform_prompt
        draft = create_draft_endpoint(
            prompt_id=prompt.id,
            body=DraftCreateRequest(),
            current_user=super_admin_user, db=db,
        )
        # Plain admin can't activate platform edits
        with pytest.raises(HTTPException) as exc:
            activate_draft_endpoint(
                prompt_id=prompt.id,
                version_id=draft.id,
                body=ActivateRequest(
                    changelog="bad", confirmation_text=prompt.prompt_key,
                ),
                current_user=admin_user, db=db,
            )
        assert exc.value.status_code == 403

    def test_activate_platform_prompt_requires_confirmation_text(
        self, db, super_admin_user, platform_prompt
    ):
        from fastapi import HTTPException
        from app.api.routes.intelligence import (
            activate_draft_endpoint,
            create_draft_endpoint,
        )
        from app.schemas.intelligence import ActivateRequest, DraftCreateRequest

        prompt, _ = platform_prompt
        draft = create_draft_endpoint(
            prompt_id=prompt.id,
            body=DraftCreateRequest(),
            current_user=super_admin_user, db=db,
        )
        # Missing confirmation_text — 400
        with pytest.raises(HTTPException) as exc:
            activate_draft_endpoint(
                prompt_id=prompt.id,
                version_id=draft.id,
                body=ActivateRequest(changelog="change", confirmation_text=None),
                current_user=super_admin_user, db=db,
            )
        assert exc.value.status_code == 400
        # Wrong confirmation_text — 400
        with pytest.raises(HTTPException) as exc:
            activate_draft_endpoint(
                prompt_id=prompt.id,
                version_id=draft.id,
                body=ActivateRequest(
                    changelog="change", confirmation_text="wrong",
                ),
                current_user=super_admin_user, db=db,
            )
        assert exc.value.status_code == 400
        # Correct — succeeds
        result = activate_draft_endpoint(
            prompt_id=prompt.id,
            version_id=draft.id,
            body=ActivateRequest(
                changelog="change", confirmation_text=prompt.prompt_key,
            ),
            current_user=super_admin_user, db=db,
        )
        assert result.status == "active"

    def test_activate_tenant_prompt_does_not_require_confirmation(
        self, db, admin_user, tenant_prompt
    ):
        from app.api.routes.intelligence import (
            activate_draft_endpoint,
            create_draft_endpoint,
        )
        from app.schemas.intelligence import ActivateRequest, DraftCreateRequest

        prompt, _ = tenant_prompt
        draft = create_draft_endpoint(
            prompt_id=prompt.id,
            body=DraftCreateRequest(),
            current_user=admin_user, db=db,
        )
        result = activate_draft_endpoint(
            prompt_id=prompt.id,
            version_id=draft.id,
            body=ActivateRequest(changelog="go"),
            current_user=admin_user, db=db,
        )
        assert result.status == "active"


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------


class TestRollback:
    def test_rollback_creates_new_version_not_reactivation(
        self, db, admin_user, tenant_prompt
    ):
        from app.api.routes.intelligence import (
            activate_draft_endpoint,
            create_draft_endpoint,
            rollback_endpoint,
        )
        from app.schemas.intelligence import (
            ActivateRequest,
            DraftCreateRequest,
            RollbackRequest,
        )

        prompt, v1 = tenant_prompt
        # Activate a v2 so v1 becomes retired
        draft = create_draft_endpoint(
            prompt_id=prompt.id,
            body=DraftCreateRequest(),
            current_user=admin_user, db=db,
        )
        activate_draft_endpoint(
            prompt_id=prompt.id,
            version_id=draft.id,
            body=ActivateRequest(changelog="to v2"),
            current_user=admin_user, db=db,
        )
        db.refresh(v1)
        assert v1.status == "retired"

        # Rollback to v1 — creates v3 (new version), v1 stays retired
        new_v = rollback_endpoint(
            prompt_id=prompt.id,
            version_id=v1.id,
            body=RollbackRequest(changelog="v2 had bug"),
            current_user=admin_user, db=db,
        )
        assert new_v.version_number == 3
        assert new_v.status == "active"
        db.refresh(v1)
        assert v1.status == "retired"  # not reactivated
        assert new_v.system_prompt == v1.system_prompt  # content matches v1

    def test_rollback_archives_current_active(
        self, db, admin_user, tenant_prompt
    ):
        from app.api.routes.intelligence import (
            activate_draft_endpoint,
            create_draft_endpoint,
            rollback_endpoint,
        )
        from app.schemas.intelligence import (
            ActivateRequest,
            DraftCreateRequest,
            RollbackRequest,
        )

        prompt, v1 = tenant_prompt
        draft = create_draft_endpoint(
            prompt_id=prompt.id,
            body=DraftCreateRequest(),
            current_user=admin_user, db=db,
        )
        v2 = activate_draft_endpoint(
            prompt_id=prompt.id,
            version_id=draft.id,
            body=ActivateRequest(changelog="to v2"),
            current_user=admin_user, db=db,
        )

        rollback_endpoint(
            prompt_id=prompt.id,
            version_id=v1.id,
            body=RollbackRequest(changelog="back to v1"),
            current_user=admin_user, db=db,
        )
        db.refresh(v2)
        assert v2.status == "retired"


# ---------------------------------------------------------------------------
# Test-run
# ---------------------------------------------------------------------------


class TestTestRun:
    def test_test_run_sets_is_test_execution_flag(
        self, db, admin_user, tenant_prompt, monkeypatch
    ):
        """Exercise the test_run endpoint end-to-end with a stubbed Anthropic
        client (injected via the `client_factory` test seam on
        `intelligence_service.execute`) so the persisted execution row can
        be inspected."""
        from app.api.routes.intelligence import test_run_endpoint
        from app.schemas.intelligence import TestRunRequest
        from app.services.intelligence import intelligence_service

        # Seed the "simple" model route so the router resolves it.
        from app.models.intelligence import IntelligenceModelRoute

        db.add(
            IntelligenceModelRoute(
                id=str(uuid.uuid4()),
                route_key="simple",
                primary_model="claude-haiku-test",
                fallback_model="claude-haiku-test",
                input_cost_per_million=Decimal("1"),
                output_cost_per_million=Decimal("5"),
                max_tokens_default=1024,
                temperature_default=0.2,
                is_active=True,
            )
        )
        db.flush()

        # Stub Anthropic — shape matches what the service reads
        class _Block:
            type = "text"
            text = '{"ok":true}'

        class _Resp:
            content = [_Block()]
            usage = type("U", (), {"input_tokens": 10, "output_tokens": 3})()
            model = "claude-haiku-test"
            stop_reason = "end_turn"

        class _Messages:
            def create(self, **kwargs):
                return _Resp()

        class _Client:
            messages = _Messages()

        # Patch `_get_client` — the exact seam the service calls when no
        # `client_factory` kwarg is supplied. Our test_run_endpoint doesn't
        # pass a factory, so this is the lowest-impact shim.
        monkeypatch.setattr(
            intelligence_service, "_get_client", lambda: _Client()
        )

        prompt, active = tenant_prompt
        result = test_run_endpoint(
            prompt_id=prompt.id,
            version_id=active.id,
            body=TestRunRequest(variables={"name": "World"}),
            current_user=admin_user, db=db,
        )
        assert result.is_test_execution is True
        assert result.caller_module == "intelligence.admin_test_run"

    def test_test_run_excluded_from_stats(self, db, admin_user, tenant_prompt):
        """Stats endpoints must filter is_test_execution=True rows."""
        from app.api.routes.intelligence import (
            overall_stats_endpoint,
            prompt_stats_endpoint,
        )

        prompt, active = tenant_prompt
        # Seed: 3 production + 2 test
        now = datetime.now(timezone.utc)
        for i in range(3):
            db.add(
                IntelligenceExecution(
                    id=str(uuid.uuid4()),
                    company_id=admin_user.company_id,
                    prompt_id=prompt.id,
                    prompt_version_id=active.id,
                    status="success",
                    input_tokens=10, output_tokens=5,
                    cost_usd=Decimal("0.01"),
                    latency_ms=100,
                    is_test_execution=False,
                    created_at=now - timedelta(hours=i),
                )
            )
        for i in range(2):
            db.add(
                IntelligenceExecution(
                    id=str(uuid.uuid4()),
                    company_id=admin_user.company_id,
                    prompt_id=prompt.id,
                    prompt_version_id=active.id,
                    status="success",
                    input_tokens=10, output_tokens=5,
                    cost_usd=Decimal("0.01"),
                    latency_ms=100,
                    is_test_execution=True,
                    created_at=now - timedelta(hours=i + 3),
                )
            )
        db.flush()

        prompt_stats = prompt_stats_endpoint(
            prompt_id=prompt.id, days=30,
            current_user=admin_user, db=db,
        )
        assert prompt_stats.total_executions == 3

        overall = overall_stats_endpoint(
            days=30, current_user=admin_user, db=db,
        )
        assert overall.total_executions == 3


class TestExecutionLogFiltering:
    def test_execution_log_hides_test_by_default(
        self, db, admin_user, tenant_prompt
    ):
        from app.api.routes.intelligence import list_executions_endpoint

        prompt, active = tenant_prompt
        for is_test in (False, True, False):
            db.add(
                IntelligenceExecution(
                    id=str(uuid.uuid4()),
                    company_id=admin_user.company_id,
                    prompt_id=prompt.id,
                    prompt_version_id=active.id,
                    status="success",
                    is_test_execution=is_test,
                    created_at=datetime.now(timezone.utc),
                )
            )
        db.flush()

        # Default: test executions hidden
        hidden = list_executions_endpoint(
            prompt_key=None, caller_module=None, caller_entity_type=None,
            caller_entity_id=None, execution_status=None, company_id=None,
            since_days=30, start_date=None, end_date=None,
            include_test_executions=False,
            sort="created_desc", limit=500, offset=0,
            current_user=admin_user, db=db,
        )
        assert len(hidden) == 2

        # Opt-in: see all
        shown = list_executions_endpoint(
            prompt_key=None, caller_module=None, caller_entity_type=None,
            caller_entity_id=None, execution_status=None, company_id=None,
            since_days=30, start_date=None, end_date=None,
            include_test_executions=True,
            sort="created_desc", limit=500, offset=0,
            current_user=admin_user, db=db,
        )
        assert len(shown) == 3


# ---------------------------------------------------------------------------
# Variable schema validation
# ---------------------------------------------------------------------------


class TestVariableSchemaValidation:
    def test_catches_undeclared_vars(self, db, admin_user, tenant_prompt):
        from fastapi import HTTPException
        from app.api.routes.intelligence import (
            activate_draft_endpoint,
            create_draft_endpoint,
            update_draft_endpoint,
        )
        from app.schemas.intelligence import (
            ActivateRequest,
            DraftCreateRequest,
            DraftUpdateRequest,
        )

        prompt, _ = tenant_prompt
        draft = create_draft_endpoint(
            prompt_id=prompt.id,
            body=DraftCreateRequest(),
            current_user=admin_user, db=db,
        )
        # Reference {{ missing }} not in schema
        update_draft_endpoint(
            prompt_id=prompt.id,
            version_id=draft.id,
            body=DraftUpdateRequest(
                user_template="hi {{ name }} and {{ missing }}",
                variable_schema={"name": {"required": True}},
            ),
            current_user=admin_user, db=db,
        )
        with pytest.raises(HTTPException) as exc:
            activate_draft_endpoint(
                prompt_id=prompt.id,
                version_id=draft.id,
                body=ActivateRequest(changelog="go"),
                current_user=admin_user, db=db,
            )
        assert exc.value.status_code == 400
        assert "undeclared" in str(exc.value.detail).lower()

    def test_catches_unused_vars(self, db, admin_user, tenant_prompt):
        from fastapi import HTTPException
        from app.api.routes.intelligence import (
            activate_draft_endpoint,
            create_draft_endpoint,
            update_draft_endpoint,
        )
        from app.schemas.intelligence import (
            ActivateRequest,
            DraftCreateRequest,
            DraftUpdateRequest,
        )

        prompt, _ = tenant_prompt
        draft = create_draft_endpoint(
            prompt_id=prompt.id,
            body=DraftCreateRequest(),
            current_user=admin_user, db=db,
        )
        # Schema declares 'unused' but template doesn't reference it
        update_draft_endpoint(
            prompt_id=prompt.id,
            version_id=draft.id,
            body=DraftUpdateRequest(
                user_template="hi {{ name }}",
                variable_schema={
                    "name": {"required": True},
                    "unused": {"required": True},
                },
            ),
            current_user=admin_user, db=db,
        )
        with pytest.raises(HTTPException) as exc:
            activate_draft_endpoint(
                prompt_id=prompt.id,
                version_id=draft.id,
                body=ActivateRequest(changelog="go"),
                current_user=admin_user, db=db,
            )
        assert exc.value.status_code == 400
        assert "unused" in str(exc.value.detail).lower()

    def test_optional_unused_variable_is_allowed(
        self, db, admin_user, tenant_prompt
    ):
        from app.api.routes.intelligence import (
            activate_draft_endpoint,
            create_draft_endpoint,
            update_draft_endpoint,
        )
        from app.schemas.intelligence import (
            ActivateRequest,
            DraftCreateRequest,
            DraftUpdateRequest,
        )

        prompt, _ = tenant_prompt
        draft = create_draft_endpoint(
            prompt_id=prompt.id,
            body=DraftCreateRequest(),
            current_user=admin_user, db=db,
        )
        update_draft_endpoint(
            prompt_id=prompt.id,
            version_id=draft.id,
            body=DraftUpdateRequest(
                user_template="hi {{ name }}",
                variable_schema={
                    "name": {"required": True},
                    "suffix": {"optional": True},  # declared but unused — OK
                },
            ),
            current_user=admin_user, db=db,
        )
        # Should NOT raise
        result = activate_draft_endpoint(
            prompt_id=prompt.id,
            version_id=draft.id,
            body=ActivateRequest(changelog="optional unused fine"),
            current_user=admin_user, db=db,
        )
        assert result.status == "active"


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


class TestAuditLog:
    def test_audit_log_created_on_activation(
        self, db, admin_user, tenant_prompt
    ):
        from app.api.routes.intelligence import (
            activate_draft_endpoint,
            create_draft_endpoint,
            list_prompt_audit_endpoint,
        )
        from app.schemas.intelligence import ActivateRequest, DraftCreateRequest

        prompt, _ = tenant_prompt
        draft = create_draft_endpoint(
            prompt_id=prompt.id,
            body=DraftCreateRequest(changelog="seed"),
            current_user=admin_user, db=db,
        )
        activate_draft_endpoint(
            prompt_id=prompt.id,
            version_id=draft.id,
            body=ActivateRequest(changelog="go"),
            current_user=admin_user, db=db,
        )

        log = list_prompt_audit_endpoint(
            prompt_id=prompt.id, limit=50, offset=0,
            current_user=admin_user, db=db,
        )
        actions = [e.action for e in log]
        assert "create_draft" in actions
        assert "activate" in actions
        # Most recent first
        assert log[0].action == "activate"
        assert log[0].actor_email == admin_user.email
        assert log[0].changelog_summary == "go"

    def test_audit_log_created_on_rollback(
        self, db, admin_user, tenant_prompt
    ):
        from app.api.routes.intelligence import (
            activate_draft_endpoint,
            create_draft_endpoint,
            list_prompt_audit_endpoint,
            rollback_endpoint,
        )
        from app.schemas.intelligence import (
            ActivateRequest,
            DraftCreateRequest,
            RollbackRequest,
        )

        prompt, v1 = tenant_prompt
        d = create_draft_endpoint(
            prompt_id=prompt.id,
            body=DraftCreateRequest(),
            current_user=admin_user, db=db,
        )
        activate_draft_endpoint(
            prompt_id=prompt.id, version_id=d.id,
            body=ActivateRequest(changelog="v2"),
            current_user=admin_user, db=db,
        )
        rollback_endpoint(
            prompt_id=prompt.id, version_id=v1.id,
            body=RollbackRequest(changelog="back to v1"),
            current_user=admin_user, db=db,
        )

        log = list_prompt_audit_endpoint(
            prompt_id=prompt.id, limit=50, offset=0,
            current_user=admin_user, db=db,
        )
        actions = [e.action for e in log]
        assert "rollback" in actions
        rollback_entry = next(e for e in log if e.action == "rollback")
        assert rollback_entry.meta_json.get("rolled_back_to_version_number") == 1


# ---------------------------------------------------------------------------
# Edit-permission preflight
# ---------------------------------------------------------------------------


class TestEditPermissionPreflight:
    def test_tenant_prompt_allows_admin(self, db, admin_user, tenant_prompt):
        from app.api.routes.intelligence import get_edit_permission_endpoint

        prompt, _ = tenant_prompt
        perm = get_edit_permission_endpoint(
            prompt_id=prompt.id,
            current_user=admin_user, db=db,
        )
        assert perm.can_edit is True
        assert perm.requires_super_admin is False
        assert perm.requires_confirmation_text is False

    def test_platform_prompt_blocks_non_super(
        self, db, admin_user, platform_prompt
    ):
        from app.api.routes.intelligence import get_edit_permission_endpoint

        prompt, _ = platform_prompt
        perm = get_edit_permission_endpoint(
            prompt_id=prompt.id,
            current_user=admin_user, db=db,
        )
        assert perm.can_edit is False
        assert perm.requires_super_admin is True
        assert perm.requires_confirmation_text is True
        assert "super_admin" in (perm.reason or "")

    def test_platform_prompt_allows_super(
        self, db, super_admin_user, platform_prompt
    ):
        from app.api.routes.intelligence import get_edit_permission_endpoint

        prompt, _ = platform_prompt
        perm = get_edit_permission_endpoint(
            prompt_id=prompt.id,
            current_user=super_admin_user, db=db,
        )
        assert perm.can_edit is True
        assert perm.requires_super_admin is True
        assert perm.requires_confirmation_text is True
