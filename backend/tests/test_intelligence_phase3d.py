"""Phase 3d — ai_prompt step type for the workflow engine.

Covers:
  - _execute_ai_prompt happy path: calls intelligence_service.execute,
    stores response_parsed fields + execution_id in output_data
  - Plain-text responses (no force_json) surface as {output.step.text}
  - Variables pre-resolved by resolve_variables reach the managed prompt
  - Caller linkage populates from trigger_context.entity_type
  - Workflow run context threads workflow_run_id + run_step_id
  - Errors surface the step as failed, run as failed
  - Downstream steps can reference output fields via {output.step.field}
  - validate_ai_prompt_steps catches missing prompt_key
  - validate_ai_prompt_steps catches missing required variable
  - validate_ai_prompt_steps catches forward reference to non-prior step
  - step-types endpoint includes ai_prompt
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import JSON, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.database import Base
from app.models.intelligence import (
    IntelligenceExecution,
    IntelligencePrompt,
    IntelligencePromptVersion,
)
from app.models.workflow import (
    Workflow,
    WorkflowRun,
    WorkflowStep,
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

    tables_needed = [
        "companies",
        "roles",
        "users",
        "agent_jobs",
        "workflows",
        "workflow_runs",
        "workflow_steps",
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
        id=str(uuid.uuid4()), name="Test Co", slug="testco", is_active=True
    )
    db.add(c)
    db.flush()
    return c


@pytest.fixture
def workflow(db, company):
    w = Workflow(
        id=str(uuid.uuid4()),
        company_id=company.id,
        name="Test WF",
        trigger_type="manual",
        trigger_config={},
    )
    db.add(w)
    db.flush()
    return w


@pytest.fixture
def prompt_with_schema(db):
    """Platform-global prompt with required var `name` + optional `extra`."""
    p = IntelligencePrompt(
        id=str(uuid.uuid4()),
        company_id=None,
        prompt_key="wf.test_extract",
        display_name="Test WF extract",
        domain="workflow",
    )
    db.add(p)
    db.flush()
    v = IntelligencePromptVersion(
        id=str(uuid.uuid4()),
        prompt_id=p.id,
        version_number=1,
        system_prompt="system",
        user_template="hi {{ name }}",
        variable_schema={
            "name": {"required": True},
            "extra": {"optional": True},
        },
        model_preference="simple",
        force_json=True,
        status="active",
        activated_at=datetime.now(timezone.utc),
    )
    db.add(v)
    db.flush()
    return p, v


def _intel_result(
    *,
    status="success",
    parsed=None,
    text="ok",
    error=None,
    exec_id="exec-1",
):
    return SimpleNamespace(
        execution_id=exec_id,
        prompt_id="p-1",
        prompt_version_id="v-1",
        model_used="claude-haiku",
        status=status,
        response_text=text,
        response_parsed=parsed,
        rendered_system_prompt="(mocked)",
        rendered_user_prompt="(mocked)",
        input_tokens=10,
        output_tokens=5,
        latency_ms=42,
        cost_usd=Decimal("0.0001"),
        experiment_variant=None,
        fallback_used=False,
        error_message=error,
    )


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------


class TestExecuteAiPrompt:
    def test_happy_path_stores_parsed_fields(self, db, company, workflow):
        from app.services.workflow_engine import _execute_ai_prompt
        from app.services import intelligence

        run = WorkflowRun(
            id=str(uuid.uuid4()),
            workflow_id=workflow.id,
            company_id=company.id,
            trigger_source="manual",
            trigger_context={},
            status="running",
        )
        db.add(run)
        db.flush()

        with patch.object(
            intelligence.intelligence_service,
            "execute",
            return_value=_intel_result(
                parsed={"name": "Hopkins", "confidence": 0.93},
                text='{"name":"Hopkins"}',
                exec_id="E-42",
            ),
        ) as mock_exec:
            out = _execute_ai_prompt(
                db,
                resolved_config={
                    "prompt_key": "wf.test_extract",
                    "variables": {"name": "Hopkins"},
                },
                run=run,
                run_step_id="rs-1",
                step_key="extract",
            )

        # Parsed fields spread at the top level
        assert out["name"] == "Hopkins"
        assert out["confidence"] == 0.93
        # Linkage + metadata preserved
        assert out["_execution_id"] == "E-42"
        assert out["_status"] == "success"

        # Service invoked with expected linkage
        kwargs = mock_exec.call_args.kwargs
        assert kwargs["prompt_key"] == "wf.test_extract"
        assert kwargs["variables"] == {"name": "Hopkins"}
        assert kwargs["company_id"] == company.id
        assert kwargs["caller_module"] == (
            f"workflow_engine.{workflow.id}.extract"
        )
        assert kwargs["caller_workflow_run_id"] == run.id
        assert kwargs["caller_workflow_run_step_id"] == "rs-1"

    def test_plain_text_response_surfaces_as_text_field(
        self, db, company, workflow
    ):
        from app.services.workflow_engine import _execute_ai_prompt
        from app.services import intelligence

        run = WorkflowRun(
            id=str(uuid.uuid4()),
            workflow_id=workflow.id,
            company_id=company.id,
            trigger_source="manual",
            trigger_context={},
            status="running",
        )
        db.add(run)
        db.flush()

        with patch.object(
            intelligence.intelligence_service,
            "execute",
            return_value=_intel_result(
                parsed=None,
                text="Some helpful free-form summary.",
            ),
        ):
            out = _execute_ai_prompt(
                db,
                resolved_config={
                    "prompt_key": "wf.summarize",
                    "variables": {"input": "x"},
                },
                run=run,
                run_step_id="rs-1",
                step_key="summarize",
            )
        assert out["text"] == "Some helpful free-form summary."
        assert "name" not in out  # No parsed fields

    def test_populates_fh_case_linkage_from_trigger_context(
        self, db, company, workflow
    ):
        from app.services.workflow_engine import _execute_ai_prompt
        from app.services import intelligence

        case_id = str(uuid.uuid4())
        run = WorkflowRun(
            id=str(uuid.uuid4()),
            workflow_id=workflow.id,
            company_id=company.id,
            trigger_source="event",
            trigger_context={
                "entity_type": "funeral_case",
                "entity_id": case_id,
            },
            status="running",
        )
        db.add(run)
        db.flush()

        with patch.object(
            intelligence.intelligence_service,
            "execute",
            return_value=_intel_result(parsed={"ok": True}),
        ) as mock_exec:
            _execute_ai_prompt(
                db,
                resolved_config={"prompt_key": "wf.test_extract"},
                run=run,
                run_step_id="rs-x",
                step_key="step_x",
            )

        kwargs = mock_exec.call_args.kwargs
        # Generic linkage
        assert kwargs["caller_entity_type"] == "funeral_case"
        assert kwargs["caller_entity_id"] == case_id
        # Specialty linkage — routes funeral_case → caller_fh_case_id
        assert kwargs["caller_fh_case_id"] == case_id

    def test_unknown_entity_type_skips_specialty_linkage(
        self, db, company, workflow
    ):
        from app.services.workflow_engine import _execute_ai_prompt
        from app.services import intelligence

        run = WorkflowRun(
            id=str(uuid.uuid4()),
            workflow_id=workflow.id,
            company_id=company.id,
            trigger_source="event",
            trigger_context={
                "entity_type": "widget",
                "entity_id": "w-1",
            },
            status="running",
        )
        db.add(run)
        db.flush()

        with patch.object(
            intelligence.intelligence_service,
            "execute",
            return_value=_intel_result(parsed={"ok": True}),
        ) as mock_exec:
            _execute_ai_prompt(
                db,
                resolved_config={"prompt_key": "wf.test_extract"},
                run=run,
                run_step_id="rs-x",
                step_key="step_x",
            )

        kwargs = mock_exec.call_args.kwargs
        assert kwargs["caller_entity_type"] == "widget"
        assert kwargs["caller_entity_id"] == "w-1"
        # No specialty column for `widget`
        assert "caller_fh_case_id" not in kwargs
        assert "caller_kb_document_id" not in kwargs

    def test_execute_error_raises_to_fail_step(
        self, db, company, workflow
    ):
        from app.services.workflow_engine import _execute_ai_prompt
        from app.services import intelligence

        run = WorkflowRun(
            id=str(uuid.uuid4()),
            workflow_id=workflow.id,
            company_id=company.id,
            trigger_source="manual",
            trigger_context={},
            status="running",
        )
        db.add(run)
        db.flush()

        with patch.object(
            intelligence.intelligence_service,
            "execute",
            return_value=_intel_result(
                status="error",
                parsed=None,
                text="",
                error="Anthropic timeout",
            ),
        ):
            with pytest.raises(RuntimeError) as exc:
                _execute_ai_prompt(
                    db,
                    resolved_config={"prompt_key": "wf.test_extract"},
                    run=run,
                    run_step_id="rs-1",
                    step_key="x",
                )
        assert "Anthropic timeout" in str(exc.value)

    def test_missing_prompt_key_raises(self, db, company, workflow):
        from app.services.workflow_engine import _execute_ai_prompt

        run = WorkflowRun(
            id=str(uuid.uuid4()),
            workflow_id=workflow.id,
            company_id=company.id,
            trigger_source="manual",
            trigger_context={},
            status="running",
        )
        db.add(run)
        db.flush()

        with pytest.raises(ValueError):
            _execute_ai_prompt(
                db,
                resolved_config={"variables": {"name": "x"}},
                run=run,
                run_step_id="rs-1",
                step_key="x",
            )


# ---------------------------------------------------------------------------
# Integration with _execute_step — downstream references
# ---------------------------------------------------------------------------


class TestStepIntegration:
    def test_ai_prompt_output_available_to_downstream_step(
        self, db, company, workflow
    ):
        """Verify that resolve_variables sees {output.ai_step.field} after the
        ai_prompt step has run by populating outputs_by_key ourselves — this
        mirrors what _execute_step does."""
        from app.services.workflow_engine import (
            _execute_ai_prompt,
            resolve_variables,
        )
        from app.services import intelligence

        run = WorkflowRun(
            id=str(uuid.uuid4()),
            workflow_id=workflow.id,
            company_id=company.id,
            trigger_source="manual",
            trigger_context={},
            status="running",
            input_data={},
            output_data={},
        )
        db.add(run)
        db.flush()

        with patch.object(
            intelligence.intelligence_service,
            "execute",
            return_value=_intel_result(
                parsed={"company_name": "Hopkins", "confidence": 0.9},
            ),
        ):
            out = _execute_ai_prompt(
                db,
                resolved_config={
                    "prompt_key": "wf.test_extract",
                    "variables": {"name": "Hopkins"},
                },
                run=run,
                run_step_id="rs-1",
                step_key="extract",
            )

        outputs_by_key = {"extract": out}

        # Downstream step references {output.extract.company_name}
        resolved = resolve_variables(
            {"subject": "Match for {output.extract.company_name}"},
            run=run,
            step_outputs=outputs_by_key,
        )
        assert resolved == {"subject": "Match for Hopkins"}


# ---------------------------------------------------------------------------
# Save-time validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_missing_prompt_key_flagged(self, db, company, prompt_with_schema):
        from app.services.workflow_engine import validate_ai_prompt_steps

        errs = validate_ai_prompt_steps(
            db,
            company.id,
            [
                {
                    "step_order": 1,
                    "step_key": "extract",
                    "step_type": "ai_prompt",
                    "config": {},
                }
            ],
        )
        assert errs
        assert any("prompt_key" in e.lower() for e in errs)

    def test_unknown_prompt_flagged(self, db, company):
        from app.services.workflow_engine import validate_ai_prompt_steps

        errs = validate_ai_prompt_steps(
            db,
            company.id,
            [
                {
                    "step_order": 1,
                    "step_key": "x",
                    "step_type": "ai_prompt",
                    "config": {"prompt_key": "nonexistent.prompt"},
                }
            ],
        )
        assert errs
        assert any("not found" in e.lower() for e in errs)

    def test_missing_required_variable_flagged(
        self, db, company, prompt_with_schema
    ):
        from app.services.workflow_engine import validate_ai_prompt_steps

        errs = validate_ai_prompt_steps(
            db,
            company.id,
            [
                {
                    "step_order": 1,
                    "step_key": "extract",
                    "step_type": "ai_prompt",
                    "config": {
                        "prompt_key": "wf.test_extract",
                        "variables": {},  # missing `name`
                    },
                }
            ],
        )
        assert errs
        assert any("name" in e and "required" in e.lower() for e in errs)

    def test_optional_variable_not_flagged(
        self, db, company, prompt_with_schema
    ):
        from app.services.workflow_engine import validate_ai_prompt_steps

        errs = validate_ai_prompt_steps(
            db,
            company.id,
            [
                {
                    "step_order": 1,
                    "step_key": "extract",
                    "step_type": "ai_prompt",
                    "config": {
                        "prompt_key": "wf.test_extract",
                        "variables": {"name": "Hopkins"},
                        # `extra` is optional — not flagged as missing
                    },
                }
            ],
        )
        assert errs == []

    def test_forward_reference_flagged(self, db, company, prompt_with_schema):
        """Variables pointing at {output.X.…} where X comes later or doesn't
        exist are flagged."""
        from app.services.workflow_engine import validate_ai_prompt_steps

        errs = validate_ai_prompt_steps(
            db,
            company.id,
            [
                {
                    "step_order": 1,
                    "step_key": "extract",
                    "step_type": "ai_prompt",
                    "config": {
                        "prompt_key": "wf.test_extract",
                        "variables": {
                            "name": "{output.future_step.thing}",
                        },
                    },
                }
            ],
        )
        assert errs
        assert any(
            "future_step" in e and "before" in e.lower() for e in errs
        )


# ---------------------------------------------------------------------------
# Step-types discovery endpoint
# ---------------------------------------------------------------------------


class TestStepTypesEndpoint:
    def test_ai_prompt_listed(self):
        from app.api.routes.workflows import list_step_types

        # No DB or auth needed — pure static response
        resp = list_step_types(current_user=MagicMock())
        keys = {t["key"] for t in resp["step_types"]}
        assert "ai_prompt" in keys
        # Label/description on the ai_prompt entry
        ai = next(t for t in resp["step_types"] if t["key"] == "ai_prompt")
        assert "AI" in ai["label"]
        assert "intelligence" in ai["description"].lower()
