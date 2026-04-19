"""Phase 3a tests — Admin UI read-surface endpoints.

Covers the new list filters, stats aggregations, and the single-version
detail endpoint added in Phase 3a. Tests invoke the route handlers
directly against an in-memory SQLite database with seeded executions,
mirroring the pattern established by test_intelligence.py.

Auth is exercised via the require_admin dependency — handlers receive
a mock User with the admin role stamped in.
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
    IntelligenceModelRoute,
    IntelligencePrompt,
    IntelligencePromptVersion,
)


# ---------------------------------------------------------------------------
# Fixtures — shared in-memory SQLite, seeded data
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
    """Mock admin user — route handlers receive this as current_user.

    Note: we invoke handlers directly rather than through the FastAPI app,
    so `require_admin` (the FastAPI dependency) never runs. The unit tests
    exercise handler logic with a stamped admin user; a separate source-level
    lint confirms every endpoint declares require_admin.
    """
    from app.models.user import User

    u = User(
        id=str(uuid.uuid4()),
        company_id=company.id,
        email="admin@test.co",
        first_name="Admin",
        last_name="User",
        hashed_password="x",
        is_active=True,
        role_id=admin_role.id,
    )
    db.add(u)
    db.flush()
    return u


def _make_prompt(db, key, *, company_id=None, domain="scribe", caller_module=None):
    p = IntelligencePrompt(
        id=str(uuid.uuid4()),
        company_id=company_id,
        prompt_key=key,
        display_name=f"Test {key}",
        description=f"Description for {key}",
        domain=domain,
        caller_module=caller_module,
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
    model_preference="simple",
    system="system",
    user_template="user {{ name }}",
):
    v = IntelligencePromptVersion(
        id=str(uuid.uuid4()),
        prompt_id=prompt_id,
        version_number=version_number,
        system_prompt=system,
        user_template=user_template,
        variable_schema={"name": {"required": True}},
        model_preference=model_preference,
        status=status,
        activated_at=datetime.now(timezone.utc) if status == "active" else None,
    )
    db.add(v)
    db.flush()
    return v


def _make_execution(
    db,
    *,
    prompt_id=None,
    prompt_version_id=None,
    prompt_key=None,  # for prompt_key filter on list endpoint
    company_id=None,
    status="success",
    model_used="claude-haiku-4-5",
    caller_module="test.module",
    input_tokens=100,
    output_tokens=50,
    latency_ms=500,
    cost_usd="0.001",
    created_at=None,
    caller_entity_type=None,
    caller_entity_id=None,
    error_message=None,
):
    e = IntelligenceExecution(
        id=str(uuid.uuid4()),
        company_id=company_id,
        prompt_id=prompt_id,
        prompt_version_id=prompt_version_id,
        model_used=model_used,
        status=status,
        caller_module=caller_module,
        caller_entity_type=caller_entity_type,
        caller_entity_id=caller_entity_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        cost_usd=Decimal(str(cost_usd)),
        created_at=created_at or datetime.now(timezone.utc),
        error_message=error_message,
    )
    db.add(e)
    db.flush()
    return e


@pytest.fixture
def seeded(db, company, admin_user):
    """Three prompts + versions + a realistic spread of executions."""
    # Platform-global prompt
    p1 = _make_prompt(db, "scribe.extract", domain="scribe", caller_module="scribe.extractor")
    v1 = _make_version(db, p1.id, model_preference="simple")

    # Tenant-specific prompt
    p2 = _make_prompt(
        db, "briefing.daily", company_id=company.id, domain="briefing",
        caller_module="briefing.generator",
    )
    v2 = _make_version(db, p2.id, model_preference="haiku_cheap")

    # Another platform prompt
    p3 = _make_prompt(db, "accounting.classify", domain="accounting", caller_module="acct.classifier")
    v3 = _make_version(db, p3.id, model_preference="extraction")

    now = datetime.now(timezone.utc)
    # 20 successful executions of p1 over last 5 days
    for i in range(20):
        _make_execution(
            db,
            prompt_id=p1.id,
            prompt_version_id=v1.id,
            company_id=None,  # platform
            caller_module="scribe.extractor",
            created_at=now - timedelta(hours=i * 6),
            cost_usd="0.0020",
            latency_ms=400 + i * 10,
        )

    # 10 executions of p2, 2 are errors
    for i in range(10):
        _make_execution(
            db,
            prompt_id=p2.id,
            prompt_version_id=v2.id,
            company_id=company.id,
            caller_module="briefing.generator",
            status="error" if i < 2 else "success",
            error_message="boom" if i < 2 else None,
            created_at=now - timedelta(hours=i * 12),
            cost_usd="0.0005",
            latency_ms=200,
        )

    # 5 executions of p3
    for i in range(5):
        _make_execution(
            db,
            prompt_id=p3.id,
            prompt_version_id=v3.id,
            company_id=None,
            caller_module="acct.classifier",
            created_at=now - timedelta(days=i),
            cost_usd="0.0100",
            latency_ms=1200,
        )

    db.flush()
    return {"p1": p1, "v1": v1, "p2": p2, "v2": v2, "p3": p3, "v3": v3}


# ---------------------------------------------------------------------------
# Tests — /prompts list
# ---------------------------------------------------------------------------


class TestListPrompts:
    def test_returns_all_visible_with_30d_stats(self, db, admin_user, seeded):
        from app.api.routes.intelligence import list_prompts_endpoint

        items = list_prompts_endpoint(
            domain=None,
            include_platform=True,
            search=None,
            caller_module=None,
            model_preference=None,
            is_active=None,
            limit=200,
            offset=0,
            current_user=admin_user,
            db=db,
        )
        assert len(items) == 3
        keys = {i.prompt_key for i in items}
        assert keys == {"scribe.extract", "briefing.daily", "accounting.classify"}

        # Stats are populated
        extract = next(i for i in items if i.prompt_key == "scribe.extract")
        assert extract.executions_30d == 20
        assert extract.error_rate_30d == 0.0
        assert extract.avg_latency_ms_30d is not None
        assert extract.active_version_id is not None
        assert extract.active_model_preference == "simple"

        briefing = next(i for i in items if i.prompt_key == "briefing.daily")
        assert briefing.executions_30d == 10
        assert briefing.error_rate_30d == pytest.approx(0.2)

    def test_filter_by_search(self, db, admin_user, seeded):
        from app.api.routes.intelligence import list_prompts_endpoint

        items = list_prompts_endpoint(
            domain=None, include_platform=True,
            search="briefing",
            caller_module=None, model_preference=None, is_active=None,
            limit=200, offset=0,
            current_user=admin_user, db=db,
        )
        assert len(items) == 1
        assert items[0].prompt_key == "briefing.daily"

    def test_filter_by_model_preference(self, db, admin_user, seeded):
        from app.api.routes.intelligence import list_prompts_endpoint

        items = list_prompts_endpoint(
            domain=None, include_platform=True,
            search=None, caller_module=None,
            model_preference="extraction",
            is_active=None,
            limit=200, offset=0,
            current_user=admin_user, db=db,
        )
        assert len(items) == 1
        assert items[0].prompt_key == "accounting.classify"

    def test_filter_by_caller_module(self, db, admin_user, seeded):
        from app.api.routes.intelligence import list_prompts_endpoint

        items = list_prompts_endpoint(
            domain=None, include_platform=True,
            search=None,
            caller_module="acct.classifier",
            model_preference=None, is_active=None,
            limit=200, offset=0,
            current_user=admin_user, db=db,
        )
        assert len(items) == 1
        assert items[0].prompt_key == "accounting.classify"

    def test_pagination(self, db, admin_user, seeded):
        from app.api.routes.intelligence import list_prompts_endpoint

        first = list_prompts_endpoint(
            domain=None, include_platform=True,
            search=None, caller_module=None, model_preference=None, is_active=None,
            limit=2, offset=0,
            current_user=admin_user, db=db,
        )
        second = list_prompts_endpoint(
            domain=None, include_platform=True,
            search=None, caller_module=None, model_preference=None, is_active=None,
            limit=2, offset=2,
            current_user=admin_user, db=db,
        )
        assert len(first) == 2
        assert len(second) == 1
        # No overlap
        assert {i.id for i in first}.isdisjoint({i.id for i in second})


# ---------------------------------------------------------------------------
# Tests — /prompts/{id} detail + version endpoint
# ---------------------------------------------------------------------------


class TestPromptDetail:
    def test_returns_versions_and_stats(self, db, admin_user, seeded):
        from app.api.routes.intelligence import get_prompt_endpoint

        resp = get_prompt_endpoint(
            prompt_id=seeded["p1"].id,
            current_user=admin_user, db=db,
        )
        assert resp.prompt_key == "scribe.extract"
        assert resp.active_version_id == seeded["v1"].id
        assert len(resp.versions) == 1
        assert resp.versions[0].system_prompt == "system"
        assert resp.executions_30d == 20

    def test_404_for_unknown_prompt(self, db, admin_user):
        from fastapi import HTTPException
        from app.api.routes.intelligence import get_prompt_endpoint

        with pytest.raises(HTTPException) as exc_info:
            get_prompt_endpoint(
                prompt_id="nonexistent",
                current_user=admin_user, db=db,
            )
        assert exc_info.value.status_code == 404

    def test_404_for_other_tenant_prompt(self, db, admin_user):
        """Cross-tenant prompts are invisible (404) even to admins."""
        from fastapi import HTTPException
        from app.api.routes.intelligence import get_prompt_endpoint
        from app.models.company import Company

        # Create another tenant + a prompt owned by them
        other = Company(id=str(uuid.uuid4()), name="Other", slug="other", is_active=True)
        db.add(other)
        db.flush()
        p = _make_prompt(db, "other.secret", company_id=other.id)

        with pytest.raises(HTTPException) as exc_info:
            get_prompt_endpoint(prompt_id=p.id, current_user=admin_user, db=db)
        assert exc_info.value.status_code == 404


class TestPromptVersionDetail:
    def test_returns_full_version_content(self, db, admin_user, seeded):
        from app.api.routes.intelligence import get_prompt_version_endpoint

        v = get_prompt_version_endpoint(
            prompt_id=seeded["p1"].id,
            version_id=seeded["v1"].id,
            current_user=admin_user, db=db,
        )
        assert v.system_prompt == "system"
        assert v.user_template == "user {{ name }}"
        assert v.model_preference == "simple"

    def test_404_when_version_belongs_to_other_prompt(self, db, admin_user, seeded):
        from fastapi import HTTPException
        from app.api.routes.intelligence import get_prompt_version_endpoint

        with pytest.raises(HTTPException) as exc_info:
            get_prompt_version_endpoint(
                prompt_id=seeded["p1"].id,  # not the owner of v2
                version_id=seeded["v2"].id,
                current_user=admin_user, db=db,
            )
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Tests — /executions list
# ---------------------------------------------------------------------------


class TestListExecutions:
    def test_returns_tenant_and_platform_executions(self, db, admin_user, seeded):
        from app.api.routes.intelligence import list_executions_endpoint

        items = list_executions_endpoint(
            prompt_key=None, caller_module=None, caller_entity_type=None,
            caller_entity_id=None, execution_status=None, company_id=None,
            since_days=30, start_date=None, end_date=None, sort="created_desc",
            limit=500, offset=0,
            current_user=admin_user, db=db,
        )
        # 20 + 10 + 5 = 35 total
        assert len(items) == 35

    def test_filter_by_prompt_key(self, db, admin_user, seeded):
        from app.api.routes.intelligence import list_executions_endpoint

        items = list_executions_endpoint(
            prompt_key="briefing.daily",
            caller_module=None, caller_entity_type=None,
            caller_entity_id=None, execution_status=None, company_id=None,
            since_days=30, start_date=None, end_date=None, sort="created_desc",
            limit=500, offset=0,
            current_user=admin_user, db=db,
        )
        assert len(items) == 10
        assert all(i.prompt_key == "briefing.daily" for i in items)

    def test_filter_by_status_error(self, db, admin_user, seeded):
        from app.api.routes.intelligence import list_executions_endpoint

        items = list_executions_endpoint(
            prompt_key=None, caller_module=None, caller_entity_type=None,
            caller_entity_id=None,
            execution_status="error",
            company_id=None,
            since_days=30, start_date=None, end_date=None, sort="created_desc",
            limit=500, offset=0,
            current_user=admin_user, db=db,
        )
        assert len(items) == 2
        assert all(i.status == "error" for i in items)

    def test_filter_by_company_platform(self, db, admin_user, seeded):
        from app.api.routes.intelligence import list_executions_endpoint

        items = list_executions_endpoint(
            prompt_key=None, caller_module=None, caller_entity_type=None,
            caller_entity_id=None, execution_status=None,
            company_id="platform",
            since_days=30, start_date=None, end_date=None, sort="created_desc",
            limit=500, offset=0,
            current_user=admin_user, db=db,
        )
        # p1 (20) and p3 (5) are platform-global; p2 (10) is tenant-scoped
        assert len(items) == 25

    def test_sort_cost_desc(self, db, admin_user, seeded):
        from app.api.routes.intelligence import list_executions_endpoint

        items = list_executions_endpoint(
            prompt_key=None, caller_module=None, caller_entity_type=None,
            caller_entity_id=None, execution_status=None, company_id=None,
            since_days=30, start_date=None, end_date=None,
            sort="cost_desc",
            limit=5, offset=0,
            current_user=admin_user, db=db,
        )
        # p3 executions have the highest cost (0.01)
        costs = [i.cost_usd for i in items if i.cost_usd is not None]
        assert costs == sorted(costs, reverse=True)
        assert items[0].cost_usd == Decimal("0.01")


class TestExecutionDetail:
    def test_returns_full_detail(self, db, admin_user, seeded):
        from app.api.routes.intelligence import get_execution_endpoint

        # Get one execution to look up
        execution_id = db.query(IntelligenceExecution).first().id
        resp = get_execution_endpoint(
            execution_id=execution_id,
            current_user=admin_user, db=db,
        )
        assert resp.id == execution_id
        # All linkage columns should be serializable (absent = None)
        assert resp.caller_fh_case_id is None

    def test_404_for_unknown(self, db, admin_user):
        from fastapi import HTTPException
        from app.api.routes.intelligence import get_execution_endpoint

        with pytest.raises(HTTPException) as exc_info:
            get_execution_endpoint(
                execution_id="nope",
                current_user=admin_user, db=db,
            )
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Tests — stats endpoints
# ---------------------------------------------------------------------------


class TestPromptStats:
    def test_returns_totals_and_daily_breakdown(self, db, admin_user, seeded):
        from app.api.routes.intelligence import prompt_stats_endpoint

        resp = prompt_stats_endpoint(
            prompt_id=seeded["p1"].id,
            days=30,
            current_user=admin_user, db=db,
        )
        assert resp.prompt_key == "scribe.extract"
        assert resp.total_executions == 20
        assert resp.success_count == 20
        assert resp.error_count == 0
        assert resp.avg_latency_ms is not None
        assert resp.p95_latency_ms is not None
        assert resp.total_cost_usd == Decimal("0.0400")  # 20 * 0.002
        assert resp.total_input_tokens == 2000
        assert resp.total_output_tokens == 1000
        # At least one daily bucket
        assert len(resp.daily_breakdown) >= 1


class TestOverallStats:
    def test_returns_aggregates_and_top_lists(self, db, admin_user, seeded):
        from app.api.routes.intelligence import overall_stats_endpoint

        resp = overall_stats_endpoint(
            days=30,
            current_user=admin_user, db=db,
        )
        assert resp.total_executions == 35
        assert resp.error_count == 2
        assert resp.error_rate == pytest.approx(2 / 35)
        assert len(resp.top_prompts_by_volume) == 3
        # scribe.extract has the most executions (20)
        assert resp.top_prompts_by_volume[0].prompt_key == "scribe.extract"
        assert resp.top_prompts_by_volume[0].count == 20
        # accounting.classify has the highest cost (5 * 0.01 = 0.05)
        assert resp.top_prompts_by_cost[0].prompt_key == "accounting.classify"


# ---------------------------------------------------------------------------
# Tests — caller-modules discovery
# ---------------------------------------------------------------------------


class TestCallerModules:
    def test_returns_distinct_modules_with_counts(self, db, admin_user, seeded):
        from app.api.routes.intelligence import list_caller_modules_endpoint

        resp = list_caller_modules_endpoint(
            since_days=30,
            current_user=admin_user, db=db,
        )
        modules = {r.caller_module: r.execution_count for r in resp}
        assert modules["scribe.extractor"] == 20
        assert modules["briefing.generator"] == 10
        assert modules["acct.classifier"] == 5


# ---------------------------------------------------------------------------
# Tests — /models endpoint (already existed, regression test)
# ---------------------------------------------------------------------------


class TestModelRoutes:
    def test_returns_all_active(self, db, admin_user):
        from app.api.routes.intelligence import list_models_endpoint

        # Seed a couple of routes
        db.add(
            IntelligenceModelRoute(
                route_key="rt1",
                primary_model="claude-x",
                input_cost_per_million=Decimal("1"),
                output_cost_per_million=Decimal("5"),
            )
        )
        db.add(
            IntelligenceModelRoute(
                route_key="rt2",
                primary_model="claude-y",
                input_cost_per_million=Decimal("2"),
                output_cost_per_million=Decimal("10"),
            )
        )
        db.flush()

        resp = list_models_endpoint(current_user=admin_user, db=db)
        keys = {r.route_key for r in resp}
        assert "rt1" in keys
        assert "rt2" in keys


# ---------------------------------------------------------------------------
# Tests — admin-only enforcement (relies on require_admin being declared)
# ---------------------------------------------------------------------------


class TestAdminOnly:
    def test_phase3a_endpoints_depend_on_require_admin(self):
        """Every Phase 3a endpoint must use require_admin. Source-level
        lint — guarantees non-admin users get 403 even without FastAPI
        middleware running in this unit-test harness."""
        from pathlib import Path
        import re

        source = (
            Path(__file__).resolve().parent.parent
            / "app" / "api" / "routes" / "intelligence.py"
        ).read_text(encoding="utf-8")

        # Every route handler for a new endpoint must declare require_admin
        # as its current_user dependency. Look for specific decorators (which
        # may be multi-line — use `in` over the normalized source).
        for path in (
            '"/stats/prompt/{prompt_id}"',
            '"/stats/overall"',
            '"/caller-modules"',
            '"/prompts/{prompt_id}/versions/{version_id}"',
        ):
            assert path in source, f"Phase 3a route missing: {path}"

        # Tools used across all endpoints — spot check a sample uses
        # require_admin not get_current_user
        # The prompt_stats/overall_stats/caller_modules handlers must not
        # reference get_current_user as their admin gate.
        pattern = re.compile(
            r"def (prompt_stats_endpoint|overall_stats_endpoint|"
            r"list_caller_modules_endpoint|get_prompt_version_endpoint)"
            r"\(.*?\)\s*:", re.DOTALL,
        )
        for m in pattern.finditer(source):
            signature_block = source[m.start() : m.end()]
            assert "Depends(require_admin)" in signature_block, (
                f"Handler {m.group(1)} does not use require_admin"
            )
