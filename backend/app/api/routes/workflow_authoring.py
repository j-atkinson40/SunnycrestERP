"""Workflow authoring — Builder AI Assistant Phase 1a (backend, no UI).

Tenant-scoped (the AI substrate is tenant-scoped via company_id; the eventual
Studio surface realm is a 1b concern — 1a's generation just RETURNS a
canvas_state, realm-agnostic). Mirrors the nl_creation route shape.

  GET  /api/v1/workflow-authoring/nl-entities  — grounding dump (binding hints)
  POST /api/v1/workflow-authoring/generate     — NL → validated canvas_state
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services import workflow_authoring

router = APIRouter()


class NLEntitiesResponse(BaseModel):
    entities: list[dict[str, Any]]


@router.get("/nl-entities", response_model=NLEntitiesResponse)
def get_nl_entities(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NLEntitiesResponse:
    """The NL-entity catalog (entity types + fields) used to ground legible
    placeholder bindings in generated workflows."""
    return NLEntitiesResponse(entities=workflow_authoring.serialize_nl_entities())


class GenerateRequest(BaseModel):
    nl: str = Field(..., min_length=1, description="Natural-language workflow spec")
    vertical: str = Field(..., description="Tenant vertical (funeral_home, manufacturing, …)")
    workflow_type: str = Field(..., description="The workflow type/slug being authored")
    current_canvas_state: dict[str, Any] | None = Field(
        default=None,
        description="Optional — the current canvas_state to EDIT (omit to generate fresh)",
    )


class GenerateResponse(BaseModel):
    canvas_state: dict[str, Any] | list[Any] | None
    valid: bool
    validation_error: str | None
    ai_status: str
    # Optional: the service's graceful failure path (execute() raised — missing
    # prompt / route / key) returns ai_execution_id=None. Declaring this `str`
    # (non-optional) made Pydantic reject the guard's own output -> 500, the
    # exact thing the guard exists to prevent. None is the honest value when no
    # execution row was created.
    ai_execution_id: str | None = None
    ai_latency_ms: int | None = None
    model_used: str | None = None


@router.post("/generate", response_model=GenerateResponse)
def generate(
    body: GenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GenerateResponse:
    """NL → a workflow canvas_state, gated by the existing server-side
    validator. The response carries the emitted config + the validation verdict
    (1a proves the model emits valid STRUCTURE; config quality is 1b/1c)."""
    result = workflow_authoring.generate_workflow_canvas(
        db,
        company_id=current_user.company_id,
        nl=body.nl,
        vertical=body.vertical,
        workflow_type=body.workflow_type,
        current_canvas_state=body.current_canvas_state,
        triggered_by_user_id=current_user.id,
    )
    return GenerateResponse(**result)
