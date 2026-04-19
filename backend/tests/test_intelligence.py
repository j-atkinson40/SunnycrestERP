"""Unit tests for Bridgeable Intelligence — Phase 1 backbone.

Covers:
  prompt_registry — tenant override, activation retires prior, incomplete draft
  prompt_renderer — Jinja2 render, missing required vars, response_schema
  model_router   — fallback chain, records which model used
  experiment     — deterministic variant assignment, traffic split, conclude
  cost_service   — per-model cost computation from route table
"""

import uuid
from collections import Counter
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import JSON, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.database import Base
from app.models.intelligence import (
    IntelligenceExecution,
    IntelligenceExperiment,
    IntelligenceModelRoute,
    IntelligencePrompt,
    IntelligencePromptVersion,
)
from app.services.intelligence import (
    cost_service,
    experiment_service,
    model_router,
    prompt_registry,
    prompt_renderer,
)
from app.services.intelligence.model_router import (
    AllModelsFailedError,
    ModelRouteNotFoundError,
    ResolvedRoute,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def engine():
    """In-memory SQLite engine, with JSONB silently remapped to JSON for testability.

    The intelligence tables reference companies/users/workflow_runs/workflow_run_steps/
    agent_jobs; we create just those + the intelligence tables to keep the
    schema minimal.
    """
    eng = create_engine("sqlite:///:memory:")

    # Create companies, users, agent_jobs, workflow_runs, workflow_run_steps so
    # our FK targets exist; these models are already on Base.metadata via imports.
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

    # SQLite doesn't support JSONB — swap types for the duration of create_all
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
def company_id(db):
    from app.models.company import Company

    c = Company(
        id=str(uuid.uuid4()),
        name="Test Co",
        slug="testco",
        is_active=True,
    )
    db.add(c)
    db.flush()
    return c.id


@pytest.fixture
def model_routes(db):
    """Seed two model routes so router tests can resolve them."""
    routes = [
        IntelligenceModelRoute(
            route_key="simple",
            primary_model="claude-haiku-4-5-20251001",
            fallback_model="claude-haiku-4-5-20251001",
            input_cost_per_million=Decimal("1.00"),
            output_cost_per_million=Decimal("5.00"),
            max_tokens_default=1024,
            temperature_default=0.2,
            is_active=True,
        ),
        IntelligenceModelRoute(
            route_key="extraction",
            primary_model="claude-sonnet-4-6",
            fallback_model="claude-haiku-4-5-20251001",
            input_cost_per_million=Decimal("3.00"),
            output_cost_per_million=Decimal("15.00"),
            max_tokens_default=4096,
            temperature_default=0.2,
            is_active=True,
        ),
    ]
    for r in routes:
        db.add(r)
    db.flush()
    return routes


def _make_prompt(db, key, company_id=None, domain="scribe") -> IntelligencePrompt:
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
    system="hello {{ name }}",
    user="hi {{ name }}",
    model_preference="simple",
    status="active",
    version_number=1,
    force_json=False,
    response_schema=None,
    variable_schema=None,
) -> IntelligencePromptVersion:
    v = IntelligencePromptVersion(
        id=str(uuid.uuid4()),
        prompt_id=prompt_id,
        version_number=version_number,
        system_prompt=system,
        user_template=user,
        variable_schema=variable_schema or {"name": {"required": True, "type": "string"}},
        response_schema=response_schema,
        model_preference=model_preference,
        force_json=force_json,
        status=status,
    )
    db.add(v)
    db.flush()
    return v


# ═══════════════════════════════════════════════════════════════════════
# prompt_registry
# ═══════════════════════════════════════════════════════════════════════


class TestPromptRegistry:
    def test_platform_prompt_visible_to_tenant(self, db, company_id):
        platform = _make_prompt(db, "scribe.x")
        _make_version(db, platform.id)
        resolved = prompt_registry.get_prompt(db, "scribe.x", company_id)
        assert resolved.id == platform.id

    def test_tenant_override_beats_platform(self, db, company_id):
        platform = _make_prompt(db, "scribe.y")
        _make_version(db, platform.id, system="PLATFORM SYSTEM")
        override = _make_prompt(db, "scribe.y", company_id=company_id)
        _make_version(db, override.id, system="TENANT SYSTEM")

        resolved = prompt_registry.get_active_version(db, "scribe.y", company_id)
        assert resolved.system_prompt == "TENANT SYSTEM"

    def test_activate_retires_prior_active(self, db):
        p = _make_prompt(db, "scribe.z")
        v1 = _make_version(db, p.id, version_number=1, status="active")
        v2 = _make_version(db, p.id, version_number=2, status="draft")

        prompt_registry.activate_version(db, v2.id)

        db.refresh(v1)
        db.refresh(v2)
        assert v1.status == "retired"
        assert v2.status == "active"
        assert v2.activated_at is not None

    def test_activate_rejects_incomplete_draft(self, db):
        p = _make_prompt(db, "scribe.broken")
        v = _make_version(db, p.id, system="", user="", model_preference="")
        with pytest.raises(prompt_registry.PromptVersionNotReadyError) as exc:
            prompt_registry.activate_version(db, v.id)
        detail = str(exc.value)
        assert "system_prompt" in detail
        assert "user_template" in detail
        assert "model_preference" in detail

    def test_missing_prompt_raises(self, db, company_id):
        with pytest.raises(prompt_registry.PromptNotFoundError):
            prompt_registry.get_active_version(db, "does.not.exist", company_id)


# ═══════════════════════════════════════════════════════════════════════
# prompt_renderer
# ═══════════════════════════════════════════════════════════════════════


class TestPromptRenderer:
    def test_render_substitutes_variables(self, db):
        p = _make_prompt(db, "renderer.sub")
        v = _make_version(
            db,
            p.id,
            system="You are {{ role }}.",
            user="Hello {{ name }}.",
            variable_schema={
                "role": {"required": True},
                "name": {"required": True},
            },
        )
        system, user = prompt_renderer.render(v, {"role": "assistant", "name": "Jimmy"})
        assert system == "You are assistant."
        assert user == "Hello Jimmy."

    def test_missing_required_variable_raises(self, db):
        p = _make_prompt(db, "renderer.missing")
        v = _make_version(
            db,
            p.id,
            system="Hi",
            user="Hello {{ name }}",
            variable_schema={"name": {"required": True}},
        )
        with pytest.raises(prompt_renderer.MissingVariableError) as exc:
            prompt_renderer.render(v, {})
        assert "name" in str(exc.value)

    def test_undeclared_template_ref_is_required(self, db):
        """A variable referenced in the template but not declared is still required."""
        p = _make_prompt(db, "renderer.undecl")
        v = _make_version(
            db,
            p.id,
            system="Mentioning {{ undeclared }}",
            user="body",
            variable_schema={},  # empty schema
        )
        with pytest.raises(prompt_renderer.MissingVariableError) as exc:
            prompt_renderer.render(v, {})
        assert "undeclared" in str(exc.value)

    def test_input_hash_deterministic(self, db):
        h1 = prompt_renderer.compute_input_hash("sys", "user", "simple")
        h2 = prompt_renderer.compute_input_hash("sys", "user", "simple")
        assert h1 == h2

    def test_input_hash_changes_with_model_preference(self, db):
        h1 = prompt_renderer.compute_input_hash("sys", "user", "simple")
        h2 = prompt_renderer.compute_input_hash("sys", "user", "reasoning")
        assert h1 != h2

    def test_response_schema_required_keys(self):
        schema = {"required": ["intent", "confidence"]}
        # passes
        prompt_renderer.validate_response_against_schema(
            {"intent": "x", "confidence": 0.9}, schema
        )
        # missing key → raises
        with pytest.raises(prompt_renderer.ResponseSchemaValidationError):
            prompt_renderer.validate_response_against_schema({"intent": "x"}, schema)


# ═══════════════════════════════════════════════════════════════════════
# model_router
# ═══════════════════════════════════════════════════════════════════════


class TestModelRouter:
    def test_resolve_model_happy_path(self, db, model_routes):
        route = model_router.resolve_model(db, "extraction")
        assert route.primary_model == "claude-sonnet-4-6"
        assert route.fallback_model == "claude-haiku-4-5-20251001"

    def test_resolve_unknown_raises(self, db, model_routes):
        with pytest.raises(ModelRouteNotFoundError):
            model_router.resolve_model(db, "nonexistent")

    def test_route_with_fallback_uses_primary_on_success(self, db, model_routes):
        route = model_router.resolve_model(db, "extraction")
        calls: list[str] = []

        def call(model_id):
            calls.append(model_id)
            return {"ok": True, "model": model_id}

        result = model_router.route_with_fallback(route, call)
        assert result.model_used == route.primary_model
        assert result.fallback_used is False
        assert calls == [route.primary_model]

    def test_route_with_fallback_falls_back_on_rate_limit(self, db, model_routes):
        route = model_router.resolve_model(db, "extraction")

        # Forge an exception class that has the retryable name
        class RateLimitError(Exception):
            pass

        calls: list[str] = []

        def call(model_id):
            calls.append(model_id)
            if model_id == route.primary_model:
                raise RateLimitError("primary rate limited")
            return {"fallback_ok": True}

        result = model_router.route_with_fallback(route, call)
        assert result.fallback_used is True
        assert result.model_used == route.fallback_model
        assert calls == [route.primary_model, route.fallback_model]

    def test_non_retryable_reraises(self, db, model_routes):
        route = model_router.resolve_model(db, "extraction")

        class AuthenticationError(Exception):
            pass  # not in _RETRYABLE_EXC_NAMES

        def call(model_id):
            raise AuthenticationError("bad creds")

        with pytest.raises(AuthenticationError):
            model_router.route_with_fallback(route, call)

    def test_both_fail_raises_all_models_failed(self, db, model_routes):
        route = model_router.resolve_model(db, "extraction")
        # Make primary and fallback distinct so fallback path is attempted
        assert route.primary_model != route.fallback_model

        class APITimeoutError(Exception):
            pass

        def call(model_id):
            raise APITimeoutError("timed out")

        with pytest.raises(AllModelsFailedError):
            model_router.route_with_fallback(route, call)


# ═══════════════════════════════════════════════════════════════════════
# cost_service
# ═══════════════════════════════════════════════════════════════════════


class TestCostService:
    def test_compute_cost_from_primary_model(self, db, model_routes):
        # extraction route: $3/M input, $15/M output
        cost = cost_service.compute_cost(db, "claude-sonnet-4-6", 1_000_000, 0)
        assert cost == Decimal("3.000000")

        cost = cost_service.compute_cost(db, "claude-sonnet-4-6", 0, 1_000_000)
        assert cost == Decimal("15.000000")

    def test_compute_cost_from_fallback_model(self, db, model_routes):
        # Haiku fallback on extraction: $1/M input, $5/M output
        # But Haiku is also the primary for 'simple' → primary match wins;
        # since we look up by model ID, this checks either route matches.
        cost = cost_service.compute_cost(db, "claude-haiku-4-5-20251001", 2_000_000, 0)
        # Should resolve to $1/M * 2 = $2
        assert cost == Decimal("2.000000")

    def test_unknown_model_returns_zero(self, db, model_routes):
        cost = cost_service.compute_cost(db, "made-up-model", 1000, 1000)
        assert cost == Decimal("0")

    def test_zero_tokens_short_circuits(self, db, model_routes):
        assert cost_service.compute_cost(db, "claude-sonnet-4-6", 0, 0) == Decimal("0")
        assert cost_service.compute_cost(db, "claude-sonnet-4-6", None, None) == Decimal("0")


# ═══════════════════════════════════════════════════════════════════════
# experiment_service
# ═══════════════════════════════════════════════════════════════════════


def _make_experiment(
    db,
    prompt_id: str,
    version_a_id: str,
    version_b_id: str,
    traffic_split: int = 50,
    min_sample_size: int = 100,
):
    exp = IntelligenceExperiment(
        id=str(uuid.uuid4()),
        company_id=None,
        prompt_id=prompt_id,
        name="Test",
        version_a_id=version_a_id,
        version_b_id=version_b_id,
        traffic_split=traffic_split,
        min_sample_size=min_sample_size,
        status="active",
    )
    db.add(exp)
    db.flush()
    return exp


class TestExperimentService:
    def test_assignment_deterministic(self, db):
        p = _make_prompt(db, "exp.det")
        va = _make_version(db, p.id, version_number=1, status="retired")
        vb = _make_version(db, p.id, version_number=2, status="active")
        exp = _make_experiment(db, p.id, va.id, vb.id, traffic_split=50)

        h = "deadbeef" * 8
        first = experiment_service.assign_variant(exp, h)
        for _ in range(1000):
            assert experiment_service.assign_variant(exp, h) == first

    def test_assignment_respects_traffic_split(self, db):
        p = _make_prompt(db, "exp.split")
        va = _make_version(db, p.id, version_number=1, status="retired")
        vb = _make_version(db, p.id, version_number=2, status="active")
        exp = _make_experiment(db, p.id, va.id, vb.id, traffic_split=50)

        # Sample 1000 different input hashes; ~50% should land in b
        counts = Counter()
        for i in range(1000):
            h = f"{i:064x}"
            counts[experiment_service.assign_variant(exp, h)] += 1
        # Within 5% margin
        assert 450 <= counts["b"] <= 550
        assert 450 <= counts["a"] <= 550

    def test_traffic_split_zero_and_hundred(self, db):
        p = _make_prompt(db, "exp.edges")
        va = _make_version(db, p.id, version_number=1, status="retired")
        vb = _make_version(db, p.id, version_number=2, status="active")
        exp0 = _make_experiment(db, p.id, va.id, vb.id, traffic_split=0)
        exp100 = _make_experiment(db, p.id, va.id, vb.id, traffic_split=100)

        for i in range(100):
            h = f"{i:064x}"
            assert experiment_service.assign_variant(exp0, h) == "a"
            assert experiment_service.assign_variant(exp100, h) == "b"

    def test_is_ready_to_conclude(self, db, company_id):
        p = _make_prompt(db, "exp.ready")
        va = _make_version(db, p.id, version_number=1, status="retired")
        vb = _make_version(db, p.id, version_number=2, status="active")
        exp = _make_experiment(db, p.id, va.id, vb.id, min_sample_size=3)

        # 2 per variant — not yet ready
        for variant in ("a", "a", "b", "b"):
            db.add(
                IntelligenceExecution(
                    id=str(uuid.uuid4()),
                    company_id=company_id,
                    experiment_id=exp.id,
                    experiment_variant=variant,
                    status="success",
                )
            )
        db.flush()
        assert experiment_service.is_ready_to_conclude(db, exp.id) is False

        # Add a 3rd for each variant → ready
        for variant in ("a", "b"):
            db.add(
                IntelligenceExecution(
                    id=str(uuid.uuid4()),
                    company_id=company_id,
                    experiment_id=exp.id,
                    experiment_variant=variant,
                    status="success",
                )
            )
        db.flush()
        assert experiment_service.is_ready_to_conclude(db, exp.id) is True

    def test_conclude_activates_winner(self, db):
        p = _make_prompt(db, "exp.conclude")
        va = _make_version(db, p.id, version_number=1, status="active")
        vb = _make_version(db, p.id, version_number=2, status="draft")
        exp = _make_experiment(db, p.id, va.id, vb.id)

        experiment_service.conclude(db, exp.id, vb.id, "B wins")

        db.refresh(exp)
        db.refresh(va)
        db.refresh(vb)
        # Phase 3c renamed "concluded" → "completed"; still accepts legacy.
        assert exp.status == "completed"
        assert exp.winner_version_id == vb.id
        assert va.status == "retired"
        assert vb.status == "active"

    def test_conclude_rejects_unrelated_version(self, db):
        p = _make_prompt(db, "exp.bad")
        va = _make_version(db, p.id, version_number=1, status="active")
        vb = _make_version(db, p.id, version_number=2, status="draft")
        exp = _make_experiment(db, p.id, va.id, vb.id)

        other = _make_version(db, p.id, version_number=3, status="draft")
        with pytest.raises(ValueError):
            experiment_service.conclude(db, exp.id, other.id)
