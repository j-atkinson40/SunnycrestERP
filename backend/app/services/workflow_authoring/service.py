"""Workflow-authoring generation service (Builder AI Assistant Phase 1a)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.workflow_template import WorkflowTemplate
from app.services.intelligence import intelligence_service
from app.services.nl_creation.entity_registry import list_entity_configs
from app.services.workflow_templates import (
    CanvasValidationError,
    validate_canvas_state,
)

# The managed prompt seeded by scripts/seed_workflow_authoring_prompt.py. Its
# system_prompt bakes the static grounding (node-type vocab + canvas_state
# schema + validator rules); its user_template consumes the variables below.
AUTHORING_PROMPT_KEY = "authoring.workflow_canvas"


def serialize_nl_entities() -> list[dict[str, Any]]:
    """The NL-entity catalog as structured grounding for legible placeholder
    bindings (entity types + their fields). Static (the registry is global) —
    NOT the Vault binding catalog (deferred); enough for the model to emit
    sensible binding placeholders the author can wire."""
    entities: list[dict[str, Any]] = []
    for config in list_entity_configs():
        entities.append(
            {
                "entity_type": str(config.entity_type),
                "fields": [
                    {
                        "key": fx.field_key,
                        "label": fx.field_label,
                        "type": str(fx.field_type),
                        "required": fx.required,
                    }
                    for fx in config.field_extractors
                ],
            }
        )
    return entities


def list_active_workflow_types(db: Session) -> list[dict[str, Any]]:
    """The existing workflow-type catalog (active templates) as grounding —
    naming + what already exists. Reuses the workflow_templates table directly
    (server-side; realm-agnostic) rather than the platform-admin HTTP endpoint."""
    rows = (
        db.query(
            WorkflowTemplate.workflow_type,
            WorkflowTemplate.vertical,
            WorkflowTemplate.display_name,
        )
        .filter(WorkflowTemplate.is_active.is_(True))
        .all()
    )
    seen: set[tuple[str, str | None]] = set()
    out: list[dict[str, Any]] = []
    for workflow_type, vertical, display_name in rows:
        key = (workflow_type, vertical)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "workflow_type": workflow_type,
                "vertical": vertical,
                "display_name": display_name,
            }
        )
    return out


def generate_workflow_canvas(
    db: Session,
    *,
    company_id: str | None,
    nl: str,
    vertical: str,
    workflow_type: str,
    current_canvas_state: dict[str, Any] | None = None,
    triggered_by_user_id: str | None = None,
) -> dict[str, Any]:
    """NL → a workflow canvas_state, gated by the existing server-side
    validator. Returns the emitted canvas_state + the validation verdict (the
    1a proof: does the model emit valid STRUCTURE?). Never raises on a bad
    generation — surfaces it via `valid=False` + `validation_error` so the
    caller (1b's review loop) can decide.
    """
    variables = {
        "nl_request": nl,
        "vertical": vertical,
        "workflow_type": workflow_type,
        "existing_workflow_types": json.dumps(list_active_workflow_types(db)),
        "nl_entities": json.dumps(serialize_nl_entities()),
        "current_canvas_state": (
            json.dumps(current_canvas_state)
            if current_canvas_state
            else "(none — generate a brand-new workflow)"
        ),
    }

    # execute() RAISES (not returns) on a missing prompt
    # (PromptNotFoundError), missing model route (ModelRouteNotFoundError), a
    # missing template variable (MissingVariableError), or a model-call failure
    # (AllModelsFailedError — e.g. ANTHROPIC_API_KEY unset on this deploy). The
    # "never raises" contract above means we MUST guard it: any raise becomes a
    # graceful valid=False verdict the caller (1b's review loop) can surface,
    # NOT an HTTP 500. The most common real-world cause is an unconfigured AI
    # environment, which should read as ai_status="error", not a crash.
    try:
        result = intelligence_service.execute(
            db,
            prompt_key=AUTHORING_PROMPT_KEY,
            variables=variables,
            company_id=company_id,
            caller_module="workflow_authoring",
        )
    except Exception as exc:  # noqa: BLE001 — contract: never raise to the caller
        return {
            "ai_status": "error",
            "ai_execution_id": None,
            "ai_latency_ms": None,
            "model_used": None,
            "canvas_state": None,
            "valid": False,
            "validation_error": (
                f"generation could not run ({type(exc).__name__}: {exc})"
            ),
        }

    base = {
        "ai_status": result.status,
        "ai_execution_id": result.execution_id,
        "ai_latency_ms": result.latency_ms,
        "model_used": result.model_used,
    }

    # The model call itself failed (rate-limited / api error / non-JSON).
    if result.status not in ("success", "fallback_used"):
        return {
            **base,
            "canvas_state": None,
            "valid": False,
            "validation_error": (
                f"generation did not produce a config "
                f"(status={result.status}: {result.error_message or 'no detail'})"
            ),
        }

    canvas_state = result.response_parsed
    if not isinstance(canvas_state, dict):
        return {
            **base,
            "canvas_state": canvas_state,
            "valid": False,
            "validation_error": "model output was not a canvas_state object",
        }

    # THE GATE — the SAME server-side validator the human edit path uses.
    valid = True
    validation_error: str | None = None
    try:
        validate_canvas_state(canvas_state)
    except CanvasValidationError as exc:
        valid = False
        validation_error = str(exc)

    return {
        **base,
        "canvas_state": canvas_state,
        "valid": valid,
        "validation_error": validation_error,
    }
