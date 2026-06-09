"""Workflow authoring — platform-realm route (Builder AI Assistant Phase 1b).

Phase 1a shipped the generation path as a TENANT route
(`/api/v1/workflow-authoring/*`, `get_current_user`, `company_id` from the
tenant user) and explicitly deferred the Studio surface realm to 1b:

    "Tenant-scoped … the eventual Studio surface realm is a 1b concern —
     1a's generation just RETURNS a canvas_state, realm-agnostic."

1b's consumer is the Studio Workflow editor, which authors VERTICAL-DEFAULT
workflows in the PLATFORM-ADMIN realm (`get_current_platform_user`, no single
tenant → no `company_id`). The 1a service `generate_workflow_canvas` is already
realm-agnostic (`company_id: str | None`; the unit tests pass `None`), so this
is the canonical "realm-agnostic service layer" pattern (CLAUDE.md
WB-cycle-followup-2): a thin platform route over the SAME service with
`company_id=None`. Generation is grounded by vertical + workflow_type against
the platform-global seeded prompt (`company_id=None` prompt lookup) — which is
the correct expression of platform authoring (you're authoring the DEFAULT, not
acting as any tenant).

The tenant route stays UNTOUCHED — it still serves the 1a Claude-API e2e. This
route serves the realm the actual 1b consumer runs in.

  POST /api/platform/admin/visual-editor/workflow-authoring/generate
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_platform_user
from app.database import get_db
from app.models.platform_user import PlatformUser
from app.services import workflow_authoring

router = APIRouter()


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
    # Optional — the service's graceful failure path (execute() raised) returns
    # ai_execution_id=None. Mirrors the 1a-hotfix-#2 tenant-route shape so the
    # guard's own output serializes instead of 500ing.
    ai_execution_id: str | None = None
    ai_latency_ms: int | None = None
    model_used: str | None = None


@router.post("/generate", response_model=GenerateResponse)
def generate(
    body: GenerateRequest,
    current_user: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> GenerateResponse:
    """NL → a workflow canvas_state, gated by the existing server-side
    validator. Platform realm: `company_id=None` (platform authoring of
    vertical-default workflows has no single tenant — grounding is by vertical +
    workflow_type against the platform-global prompt). Reuses the SAME
    realm-agnostic service the tenant route uses (1a-proven, validator-gated)."""
    result = workflow_authoring.generate_workflow_canvas(
        db,
        company_id=None,
        nl=body.nl,
        vertical=body.vertical,
        workflow_type=body.workflow_type,
        current_canvas_state=body.current_canvas_state,
        triggered_by_user_id=None,
    )
    return GenerateResponse(**result)
