"""Phase 3c tests — Experiment lifecycle (draft → running → completed),
variant assignment determinism, promote (with audit + super_admin gate),
results aggregation with daily breakdown + p95, permission enforcement.

Tests invoke handlers directly against in-memory SQLite, following the
pattern established by test_intelligence_phase3a/3b.
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
    IntelligenceExperiment,
    IntelligencePrompt,
    IntelligencePromptAuditLog,
    IntelligencePromptVersion,
)


# ---------------------------------------------------------------------------
# Fixtures — shared in-memory SQLite
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

    c = Company(id=str(uuid.uuid4()), name="Test Co", slug="testco", is_active=True)
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
    db, prompt_id, *, version_number=1, status="active", model_preference="simple"
):
    v = IntelligencePromptVersion(
        id=str(uuid.uuid4()),
        prompt_id=prompt_id,
        version_number=version_number,
        system_prompt=f"System v{version_number}",
        user_template=f"Hi {{{{ name }}}} from v{version_number}",
        variable_schema={"name": {"required": True}},
        model_preference=model_preference,
        status=status,
        activated_at=datetime.now(timezone.utc) if status == "active" else None,
    )
    db.add(v)
    db.flush()
    return v


@pytest.fixture
def tenant_prompt_two_versions(db, company):
    """Tenant prompt with v1 active + v2 retired — ready for experiment."""
    p = _make_prompt(db, "scribe.exp_test", company_id=company.id)
    v1 = _make_version(db, p.id, version_number=1, status="active")
    v2 = _make_version(db, p.id, version_number=2, status="retired")
    return p, v1, v2


@pytest.fixture
def platform_prompt_two_versions(db):
    p = _make_prompt(db, "briefing.exp_test", company_id=None)
    v1 = _make_version(db, p.id, version_number=1, status="active")
    v2 = _make_version(db, p.id, version_number=2, status="retired")
    return p, v1, v2


# ---------------------------------------------------------------------------
# Create / start
# ---------------------------------------------------------------------------


class TestCreateExperiment:
    def test_create_draft(self, db, admin_user, tenant_prompt_two_versions):
        from app.api.routes.intelligence import create_experiment_endpoint
        from app.schemas.intelligence import ExperimentCreate

        prompt, v1, v2 = tenant_prompt_two_versions
        exp = create_experiment_endpoint(
            body=ExperimentCreate(
                prompt_id=prompt.id,
                name="v1 vs v2",
                hypothesis="v2 reduces hallucination",
                version_a_id=v1.id,
                version_b_id=v2.id,
                traffic_split=50,
                start_immediately=False,
            ),
            current_user=admin_user, db=db,
        )
        assert exp.status == "draft"
        assert exp.started_at is None

    def test_create_and_start_immediately(
        self, db, admin_user, tenant_prompt_two_versions
    ):
        from app.api.routes.intelligence import create_experiment_endpoint
        from app.schemas.intelligence import ExperimentCreate

        prompt, v1, v2 = tenant_prompt_two_versions
        exp = create_experiment_endpoint(
            body=ExperimentCreate(
                prompt_id=prompt.id,
                name="v1 vs v2",
                version_a_id=v1.id,
                version_b_id=v2.id,
                start_immediately=True,
            ),
            current_user=admin_user, db=db,
        )
        assert exp.status == "running"
        assert exp.started_at is not None

    def test_variants_must_differ(self, db, admin_user, tenant_prompt_two_versions):
        from fastapi import HTTPException
        from app.api.routes.intelligence import create_experiment_endpoint
        from app.schemas.intelligence import ExperimentCreate

        prompt, v1, _ = tenant_prompt_two_versions
        with pytest.raises(HTTPException) as exc:
            create_experiment_endpoint(
                body=ExperimentCreate(
                    prompt_id=prompt.id,
                    name="bad",
                    version_a_id=v1.id,
                    version_b_id=v1.id,
                ),
                current_user=admin_user, db=db,
            )
        assert exc.value.status_code == 400

    def test_cannot_run_multiple_experiments_on_same_prompt(
        self, db, admin_user, tenant_prompt_two_versions
    ):
        from fastapi import HTTPException
        from app.api.routes.intelligence import create_experiment_endpoint
        from app.schemas.intelligence import ExperimentCreate

        prompt, v1, v2 = tenant_prompt_two_versions
        create_experiment_endpoint(
            body=ExperimentCreate(
                prompt_id=prompt.id, name="first",
                version_a_id=v1.id, version_b_id=v2.id,
                start_immediately=True,
            ),
            current_user=admin_user, db=db,
        )
        with pytest.raises(HTTPException) as exc:
            create_experiment_endpoint(
                body=ExperimentCreate(
                    prompt_id=prompt.id, name="second",
                    version_a_id=v1.id, version_b_id=v2.id,
                    start_immediately=True,
                ),
                current_user=admin_user, db=db,
            )
        assert exc.value.status_code == 409

    def test_platform_experiment_requires_super_admin(
        self, db, admin_user, super_admin_user, platform_prompt_two_versions
    ):
        from fastapi import HTTPException
        from app.api.routes.intelligence import create_experiment_endpoint
        from app.schemas.intelligence import ExperimentCreate

        prompt, v1, v2 = platform_prompt_two_versions
        # Admin — blocked
        with pytest.raises(HTTPException) as exc:
            create_experiment_endpoint(
                body=ExperimentCreate(
                    prompt_id=prompt.id, name="blocked",
                    version_a_id=v1.id, version_b_id=v2.id,
                ),
                current_user=admin_user, db=db,
            )
        assert exc.value.status_code == 403
        # Super admin — allowed
        exp = create_experiment_endpoint(
            body=ExperimentCreate(
                prompt_id=prompt.id, name="ok",
                version_a_id=v1.id, version_b_id=v2.id,
            ),
            current_user=super_admin_user, db=db,
        )
        assert exp.status == "running"


class TestStartExperiment:
    def test_start_requires_draft(self, db, admin_user, tenant_prompt_two_versions):
        from fastapi import HTTPException
        from app.api.routes.intelligence import (
            create_experiment_endpoint,
            start_experiment_endpoint,
        )
        from app.schemas.intelligence import ExperimentCreate

        prompt, v1, v2 = tenant_prompt_two_versions
        # Create running directly — cannot be started again
        exp = create_experiment_endpoint(
            body=ExperimentCreate(
                prompt_id=prompt.id, name="x",
                version_a_id=v1.id, version_b_id=v2.id,
                start_immediately=True,
            ),
            current_user=admin_user, db=db,
        )
        with pytest.raises(HTTPException) as exc:
            start_experiment_endpoint(
                experiment_id=exp.id, current_user=admin_user, db=db,
            )
        # Wrong status — 400
        assert exc.value.status_code == 400

    def test_start_draft_to_running(self, db, admin_user, tenant_prompt_two_versions):
        from app.api.routes.intelligence import (
            create_experiment_endpoint,
            start_experiment_endpoint,
        )
        from app.schemas.intelligence import ExperimentCreate

        prompt, v1, v2 = tenant_prompt_two_versions
        exp = create_experiment_endpoint(
            body=ExperimentCreate(
                prompt_id=prompt.id, name="x",
                version_a_id=v1.id, version_b_id=v2.id,
                start_immediately=False,
            ),
            current_user=admin_user, db=db,
        )
        result = start_experiment_endpoint(
            experiment_id=exp.id, current_user=admin_user, db=db,
        )
        assert result.status == "running"
        assert result.started_at is not None


# ---------------------------------------------------------------------------
# Variant assignment determinism
# ---------------------------------------------------------------------------


class TestVariantAssignment:
    def test_same_input_hash_same_variant(self, db, tenant_prompt_two_versions):
        from app.services.intelligence import experiment_service

        prompt, v1, v2 = tenant_prompt_two_versions
        exp = IntelligenceExperiment(
            id=str(uuid.uuid4()),
            company_id=None,
            prompt_id=prompt.id,
            name="x",
            version_a_id=v1.id,
            version_b_id=v2.id,
            traffic_split=50,
            min_sample_size=100,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        db.add(exp)
        db.flush()
        # Same input_hash always lands in same variant
        a = experiment_service.assign_variant(exp, "deterministic-hash-1")
        b = experiment_service.assign_variant(exp, "deterministic-hash-1")
        assert a == b

    def test_traffic_split_zero_always_a(self, db, tenant_prompt_two_versions):
        from app.services.intelligence import experiment_service

        prompt, v1, v2 = tenant_prompt_two_versions
        exp = IntelligenceExperiment(
            id=str(uuid.uuid4()),
            prompt_id=prompt.id,
            name="x",
            version_a_id=v1.id, version_b_id=v2.id,
            traffic_split=0,  # Nothing to B
            min_sample_size=100, status="running",
        )
        assignments = {
            experiment_service.assign_variant(exp, f"hash-{i}") for i in range(50)
        }
        assert assignments == {"a"}

    def test_traffic_split_hundred_always_b(self, db, tenant_prompt_two_versions):
        from app.services.intelligence import experiment_service

        prompt, v1, v2 = tenant_prompt_two_versions
        exp = IntelligenceExperiment(
            id=str(uuid.uuid4()),
            prompt_id=prompt.id,
            name="x",
            version_a_id=v1.id, version_b_id=v2.id,
            traffic_split=100,  # Everything to B
            min_sample_size=100, status="running",
        )
        assignments = {
            experiment_service.assign_variant(exp, f"hash-{i}") for i in range(50)
        }
        assert assignments == {"b"}


# ---------------------------------------------------------------------------
# Stop / promote
# ---------------------------------------------------------------------------


class TestStop:
    def test_stop_running_experiment(
        self, db, admin_user, tenant_prompt_two_versions
    ):
        from app.api.routes.intelligence import (
            create_experiment_endpoint,
            stop_experiment_endpoint,
        )
        from app.schemas.intelligence import (
            ExperimentCreate,
            ExperimentStopRequest,
        )

        prompt, v1, v2 = tenant_prompt_two_versions
        exp = create_experiment_endpoint(
            body=ExperimentCreate(
                prompt_id=prompt.id, name="x",
                version_a_id=v1.id, version_b_id=v2.id,
                start_immediately=True,
            ),
            current_user=admin_user, db=db,
        )
        result = stop_experiment_endpoint(
            experiment_id=exp.id,
            body=ExperimentStopRequest(reason="test concluded early"),
            current_user=admin_user, db=db,
        )
        assert result.status == "completed"
        assert result.conclusion_notes == "test concluded early"
        # Prompt still has v1 active — stop does NOT pick a winner
        db.refresh(v1)
        assert v1.status == "active"

        # Audit row written
        audit = (
            db.query(IntelligencePromptAuditLog)
            .filter(
                IntelligencePromptAuditLog.prompt_id == prompt.id,
                IntelligencePromptAuditLog.action == "experiment_stop",
            )
            .first()
        )
        assert audit is not None


class TestPromote:
    def test_promote_creates_active_from_variant(
        self, db, admin_user, tenant_prompt_two_versions
    ):
        from app.api.routes.intelligence import (
            create_experiment_endpoint,
            promote_experiment_endpoint,
        )
        from app.schemas.intelligence import (
            ExperimentCreate,
            ExperimentPromoteRequest,
        )

        prompt, v1, v2 = tenant_prompt_two_versions
        exp = create_experiment_endpoint(
            body=ExperimentCreate(
                prompt_id=prompt.id, name="x",
                version_a_id=v1.id, version_b_id=v2.id,
                start_immediately=True,
            ),
            current_user=admin_user, db=db,
        )
        result = promote_experiment_endpoint(
            experiment_id=exp.id,
            body=ExperimentPromoteRequest(
                variant_version_id=v2.id,
                changelog="B wins clearly",
            ),
            current_user=admin_user, db=db,
        )
        assert result.status == "completed"
        assert result.winner_version_id == v2.id

        # v2 is now active; v1 retired
        db.refresh(v1)
        db.refresh(v2)
        assert v2.status == "active"
        assert v1.status == "retired"

        # Audit row written
        audit = (
            db.query(IntelligencePromptAuditLog)
            .filter(
                IntelligencePromptAuditLog.prompt_id == prompt.id,
                IntelligencePromptAuditLog.action == "experiment_promote",
            )
            .first()
        )
        assert audit is not None
        assert audit.meta_json.get("winner_variant") == "b"

    def test_promote_requires_super_admin_for_platform(
        self,
        db,
        admin_user,
        super_admin_user,
        platform_prompt_two_versions,
    ):
        from fastapi import HTTPException
        from app.api.routes.intelligence import (
            create_experiment_endpoint,
            promote_experiment_endpoint,
        )
        from app.schemas.intelligence import (
            ExperimentCreate,
            ExperimentPromoteRequest,
        )

        prompt, v1, v2 = platform_prompt_two_versions
        exp = create_experiment_endpoint(
            body=ExperimentCreate(
                prompt_id=prompt.id, name="x",
                version_a_id=v1.id, version_b_id=v2.id,
                start_immediately=True,
            ),
            current_user=super_admin_user, db=db,
        )
        # Admin blocked even with correct confirmation_text
        with pytest.raises(HTTPException) as exc:
            promote_experiment_endpoint(
                experiment_id=exp.id,
                body=ExperimentPromoteRequest(
                    variant_version_id=v2.id,
                    changelog="go",
                    confirmation_text=prompt.prompt_key,
                ),
                current_user=admin_user, db=db,
            )
        assert exc.value.status_code == 403
        # Super admin with correct confirmation — succeeds
        result = promote_experiment_endpoint(
            experiment_id=exp.id,
            body=ExperimentPromoteRequest(
                variant_version_id=v2.id,
                changelog="go",
                confirmation_text=prompt.prompt_key,
            ),
            current_user=super_admin_user, db=db,
        )
        assert result.status == "completed"

    def test_promote_requires_confirmation_text_for_platform(
        self, db, super_admin_user, platform_prompt_two_versions
    ):
        from fastapi import HTTPException
        from app.api.routes.intelligence import (
            create_experiment_endpoint,
            promote_experiment_endpoint,
        )
        from app.schemas.intelligence import (
            ExperimentCreate,
            ExperimentPromoteRequest,
        )

        prompt, v1, v2 = platform_prompt_two_versions
        exp = create_experiment_endpoint(
            body=ExperimentCreate(
                prompt_id=prompt.id, name="x",
                version_a_id=v1.id, version_b_id=v2.id,
                start_immediately=True,
            ),
            current_user=super_admin_user, db=db,
        )
        with pytest.raises(HTTPException) as exc:
            promote_experiment_endpoint(
                experiment_id=exp.id,
                body=ExperimentPromoteRequest(
                    variant_version_id=v2.id,
                    changelog="go",
                    confirmation_text="wrong",
                ),
                current_user=super_admin_user, db=db,
            )
        assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# Results aggregation
# ---------------------------------------------------------------------------


class TestResults:
    def test_results_per_variant_and_daily(
        self, db, admin_user, tenant_prompt_two_versions
    ):
        from app.api.routes.intelligence import (
            create_experiment_endpoint,
            get_experiment_results_endpoint,
        )
        from app.schemas.intelligence import ExperimentCreate

        prompt, v1, v2 = tenant_prompt_two_versions
        exp = create_experiment_endpoint(
            body=ExperimentCreate(
                prompt_id=prompt.id, name="x",
                version_a_id=v1.id, version_b_id=v2.id,
                start_immediately=True,
            ),
            current_user=admin_user, db=db,
        )

        now = datetime.now(timezone.utc)
        # 10 A, 10 B; A has 1 error, B has 3 errors
        for i in range(10):
            db.add(
                IntelligenceExecution(
                    id=str(uuid.uuid4()),
                    company_id=admin_user.company_id,
                    prompt_id=prompt.id,
                    prompt_version_id=v1.id,
                    experiment_id=exp.id,
                    experiment_variant="a",
                    status="error" if i == 0 else "success",
                    input_tokens=100, output_tokens=50,
                    latency_ms=200,
                    cost_usd=Decimal("0.01"),
                    created_at=now - timedelta(hours=i),
                )
            )
        for i in range(10):
            db.add(
                IntelligenceExecution(
                    id=str(uuid.uuid4()),
                    company_id=admin_user.company_id,
                    prompt_id=prompt.id,
                    prompt_version_id=v2.id,
                    experiment_id=exp.id,
                    experiment_variant="b",
                    status="error" if i < 3 else "success",
                    input_tokens=100, output_tokens=50,
                    latency_ms=400,
                    cost_usd=Decimal("0.02"),
                    created_at=now - timedelta(hours=i),
                )
            )
        db.flush()

        res = get_experiment_results_endpoint(
            experiment_id=exp.id, current_user=admin_user, db=db,
        )
        a = next(v for v in res.variants if v.variant == "a")
        b = next(v for v in res.variants if v.variant == "b")
        assert a.sample_count == 10
        assert a.error_count == 1
        assert b.sample_count == 10
        assert b.error_count == 3
        assert res.p95_latency_ms["a"] == 200
        assert res.p95_latency_ms["b"] == 400
        assert len(res.daily_breakdown) >= 1


# ---------------------------------------------------------------------------
# List + get detail
# ---------------------------------------------------------------------------


class TestList:
    def test_list_decorates_counts_and_version_numbers(
        self, db, admin_user, tenant_prompt_two_versions
    ):
        from app.api.routes.intelligence import (
            create_experiment_endpoint,
            list_experiments_endpoint,
        )
        from app.schemas.intelligence import ExperimentCreate

        prompt, v1, v2 = tenant_prompt_two_versions
        exp = create_experiment_endpoint(
            body=ExperimentCreate(
                prompt_id=prompt.id, name="x",
                version_a_id=v1.id, version_b_id=v2.id,
                start_immediately=True,
            ),
            current_user=admin_user, db=db,
        )
        # Two executions — one per variant
        for variant, version in [("a", v1), ("b", v2)]:
            db.add(
                IntelligenceExecution(
                    id=str(uuid.uuid4()),
                    company_id=admin_user.company_id,
                    prompt_id=prompt.id,
                    prompt_version_id=version.id,
                    experiment_id=exp.id,
                    experiment_variant=variant,
                    status="success",
                    input_tokens=10, output_tokens=5,
                    latency_ms=100,
                    cost_usd=Decimal("0.01"),
                    created_at=datetime.now(timezone.utc),
                )
            )
        db.flush()

        items = list_experiments_endpoint(
            status_filter=None, prompt_id=None,
            limit=100, offset=0,
            current_user=admin_user, db=db,
        )
        assert len(items) == 1
        item = items[0]
        assert item.prompt_key == prompt.prompt_key
        assert item.version_a_number == 1
        assert item.version_b_number == 2
        assert item.variant_a_count == 1
        assert item.variant_b_count == 1


class TestGetDetail:
    def test_get_detail_and_tenant_isolation(
        self, db, admin_user, tenant_prompt_two_versions
    ):
        from fastapi import HTTPException
        from app.api.routes.intelligence import (
            create_experiment_endpoint,
            get_experiment_endpoint,
        )
        from app.schemas.intelligence import ExperimentCreate

        prompt, v1, v2 = tenant_prompt_two_versions
        exp = create_experiment_endpoint(
            body=ExperimentCreate(
                prompt_id=prompt.id, name="x",
                version_a_id=v1.id, version_b_id=v2.id,
                start_immediately=True,
            ),
            current_user=admin_user, db=db,
        )
        result = get_experiment_endpoint(
            experiment_id=exp.id, current_user=admin_user, db=db,
        )
        assert result.id == exp.id

        # Cross-tenant visibility — create a user in a different company
        from app.models.company import Company
        from app.models.user import User

        other_co = Company(
            id=str(uuid.uuid4()), name="Other", slug="other", is_active=True
        )
        db.add(other_co)
        db.flush()
        other_user = User(
            id=str(uuid.uuid4()),
            company_id=other_co.id,
            email="x@other.co",
            first_name="X", last_name="Y",
            hashed_password="x",
            is_active=True,
            is_super_admin=False,
            role_id=admin_user.role_id,
        )
        db.add(other_user)
        db.flush()

        with pytest.raises(HTTPException) as exc:
            get_experiment_endpoint(
                experiment_id=exp.id, current_user=other_user, db=db,
            )
        assert exc.value.status_code == 404
