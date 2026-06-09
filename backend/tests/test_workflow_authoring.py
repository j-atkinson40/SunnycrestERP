"""Builder AI Assistant Phase 1a — workflow-authoring generation (backend).

Local gate (no Claude call): the NL-entities grounding shape + the
validator-GATE logic (a valid emitted config passes, an invalid one is caught
and surfaced). The generation-QUALITY proof (does the real model emit valid
structure?) is the staging Claude-API e2e (workflow-authoring.spec.ts) — it
needs a real Sonnet call + the seeded prompt, so it can't run here.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import workflow_authoring
from app.services.workflow_authoring import service as wa_service


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


# ── A valid canvas_state (passes validate_canvas_state) + an invalid one ──
_VALID_CANVAS = {
    "version": 1,
    "nodes": [
        {"id": "n_start", "type": "start", "label": "Start", "position": {"x": 0, "y": 0}, "config": {}},
        {"id": "n_end", "type": "end", "label": "End", "position": {"x": 0, "y": 120}, "config": {}},
    ],
    "edges": [{"id": "e1", "source": "n_start", "target": "n_end"}],
}
_INVALID_CANVAS_ORPHAN_EDGE = {
    "version": 1,
    "nodes": [
        {"id": "n_start", "type": "start", "label": "Start", "position": {"x": 0, "y": 0}, "config": {}},
    ],
    "edges": [{"id": "e1", "source": "n_start", "target": "n_ghost"}],  # dangling
}


def _fake_result(*, status="success", parsed=None, error_message=None):
    return SimpleNamespace(
        execution_id="exec-test",
        status=status,
        response_parsed=parsed,
        latency_ms=42,
        model_used="claude-sonnet-4-6",
        error_message=error_message,
    )


def _patch_execute(monkeypatch, result):
    monkeypatch.setattr(
        wa_service.intelligence_service, "execute", lambda *a, **k: result
    )


# ── serialize_nl_entities ──

def test_serialize_nl_entities_shape():
    entities = workflow_authoring.serialize_nl_entities()
    assert isinstance(entities, list) and len(entities) > 0
    sample = entities[0]
    assert set(sample.keys()) == {"entity_type", "fields"}
    assert isinstance(sample["entity_type"], str)
    field = sample["fields"][0]
    assert set(field.keys()) == {"key", "label", "type", "required"}
    assert isinstance(field["required"], bool)
    # The 4 Phase-4 NL entity types are present.
    types = {e["entity_type"] for e in entities}
    assert {"case", "event", "contact"}.issubset(types)


# ── list_active_workflow_types ──

def test_list_active_workflow_types_returns_list(db_session):
    out = workflow_authoring.list_active_workflow_types(db_session)
    assert isinstance(out, list)
    if out:
        assert {"workflow_type", "vertical", "display_name"}.issubset(out[0].keys())


# ── the validator GATE ──

def test_gate_passes_a_valid_emitted_canvas(db_session, monkeypatch):
    _patch_execute(monkeypatch, _fake_result(parsed=_VALID_CANVAS))
    out = workflow_authoring.generate_workflow_canvas(
        db_session, company_id=None, nl="commit → case → done",
        vertical="funeral_home", workflow_type="test_wf",
    )
    assert out["valid"] is True
    assert out["validation_error"] is None
    assert out["canvas_state"] == _VALID_CANVAS
    assert out["ai_status"] == "success"
    assert out["ai_execution_id"] == "exec-test"


def test_gate_catches_an_invalid_emitted_canvas(db_session, monkeypatch):
    _patch_execute(monkeypatch, _fake_result(parsed=_INVALID_CANVAS_ORPHAN_EDGE))
    out = workflow_authoring.generate_workflow_canvas(
        db_session, company_id=None, nl="x", vertical="funeral_home", workflow_type="t",
    )
    assert out["valid"] is False
    assert out["validation_error"] and "declared node id" in out["validation_error"]
    # The (invalid) config is still returned so 1b can show what was attempted.
    assert out["canvas_state"] == _INVALID_CANVAS_ORPHAN_EDGE


def test_gate_handles_a_failed_generation(db_session, monkeypatch):
    _patch_execute(
        monkeypatch,
        _fake_result(status="rate_limited", parsed=None, error_message="429"),
    )
    out = workflow_authoring.generate_workflow_canvas(
        db_session, company_id=None, nl="x", vertical="funeral_home", workflow_type="t",
    )
    assert out["valid"] is False
    assert out["canvas_state"] is None
    assert "rate_limited" in out["validation_error"]


def test_gate_handles_execute_raising(db_session, monkeypatch):
    """execute() RAISES (not returns) on a missing prompt / model route /
    variable / unconfigured AI (AllModelsFailedError). The service must turn
    that into a graceful valid=False verdict, NOT propagate to an HTTP 500.
    This is the staging-500 regression: pre-fix, an unseeded prompt or an
    unset ANTHROPIC_API_KEY 500'd the /generate endpoint."""

    def _boom(*a, **k):
        raise RuntimeError("PromptNotFoundError: authoring.workflow_canvas")

    monkeypatch.setattr(wa_service.intelligence_service, "execute", _boom)
    out = workflow_authoring.generate_workflow_canvas(
        db_session, company_id=None, nl="x", vertical="funeral_home", workflow_type="t",
    )
    assert out["valid"] is False
    assert out["canvas_state"] is None
    assert out["ai_status"] == "error"
    assert "generation could not run" in out["validation_error"]
    assert "PromptNotFoundError" in out["validation_error"]


def test_gate_handles_non_object_output(db_session, monkeypatch):
    _patch_execute(monkeypatch, _fake_result(parsed=["not", "an", "object"]))
    out = workflow_authoring.generate_workflow_canvas(
        db_session, company_id=None, nl="x", vertical="funeral_home", workflow_type="t",
    )
    assert out["valid"] is False
    assert "not a canvas_state object" in out["validation_error"]


def test_generate_response_model_accepts_the_guard_error_shape():
    """The route's GenerateResponse MUST serialize the service's graceful
    failure shape. Regression: GenerateResponse.ai_execution_id was declared
    `str` (non-optional), so when execute() raised and the guard returned
    ai_execution_id=None, GenerateResponse(**result) raised a Pydantic
    ValidationError -> HTTP 500 — defeating the guard on EVERY failure mode
    (missing prompt / route / key). The 3-shape staging e2e caught this; this
    test pins it. The service and the route response model must agree on shape."""
    from app.api.routes.workflow_authoring import GenerateResponse

    # The exact dict the guard returns on a raised execute().
    guard_error = {
        "ai_status": "error",
        "ai_execution_id": None,
        "ai_latency_ms": None,
        "model_used": None,
        "canvas_state": None,
        "valid": False,
        "validation_error": "generation could not run (PromptNotFoundError: ...)",
    }
    resp = GenerateResponse(**guard_error)  # must NOT raise
    assert resp.valid is False
    assert resp.ai_status == "error"
    assert resp.ai_execution_id is None


def test_a_branching_acyclic_canvas_passes_the_gate(db_session, monkeypatch):
    # A multi-branch funeral-shaped structure (the e2e's shape, hand-built):
    # commit → case → decision → {burial, cremation} → join → obituary → end.
    canvas = {
        "version": 1,
        "nodes": [
            {"id": "n_start", "type": "start", "position": {"x": 0, "y": 0}, "config": {}},
            {"id": "n_case", "type": "generate_document", "position": {"x": 0, "y": 120}, "config": {}},
            {"id": "n_decide", "type": "decision", "position": {"x": 0, "y": 240}, "config": {}},
            {"id": "n_burial", "type": "action", "position": {"x": 200, "y": 360}, "config": {}},
            {"id": "n_crem", "type": "action", "position": {"x": 400, "y": 360}, "config": {}},
            {"id": "n_join", "type": "parallel_join", "position": {"x": 300, "y": 480}, "config": {}},
            {"id": "n_obit", "type": "generate_document", "position": {"x": 300, "y": 600}, "config": {}},
            {"id": "n_end", "type": "end", "position": {"x": 300, "y": 720}, "config": {}},
        ],
        "edges": [
            {"id": "e1", "source": "n_start", "target": "n_case"},
            {"id": "e2", "source": "n_case", "target": "n_decide"},
            {"id": "e3", "source": "n_decide", "target": "n_burial", "condition": "burial"},
            {"id": "e4", "source": "n_decide", "target": "n_crem", "condition": "cremation"},
            {"id": "e5", "source": "n_burial", "target": "n_join"},
            {"id": "e6", "source": "n_crem", "target": "n_join"},
            {"id": "e7", "source": "n_join", "target": "n_obit"},
            {"id": "e8", "source": "n_obit", "target": "n_end"},
        ],
    }
    _patch_execute(monkeypatch, _fake_result(parsed=canvas))
    out = workflow_authoring.generate_workflow_canvas(
        db_session, company_id=None, nl="multi-branch funeral",
        vertical="funeral_home", workflow_type="funeral_cascade",
    )
    assert out["valid"] is True, out["validation_error"]
