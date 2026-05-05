"""Workshop API routes — Phase 1D Workshop template-type registration +
per-tenant Tune mode customization.

Per BRIDGEABLE_MASTER §3.26.14 Workshop primitive canon: this router
exposes the Workshop service layer to frontend consumers (Phase 1D
Tune mode chrome consumers).

**Endpoint set** (Phase 1D pattern-establisher):

- ``GET /workshop/template-types`` — list registered template-types,
  optionally filtered by vertical
- ``GET /workshop/personalization-studio/{template_type}/tenant-config``
  — read tenant Tune mode configuration (admin-gated)
- ``PATCH /workshop/personalization-studio/{template_type}/tenant-config``
  — update tenant Tune mode configuration with Tune mode boundary
  enforcement (admin-gated)

**Authorization**: tenant config endpoints are admin-gated per
canonical Workshop access discipline (Workshop authoring requires
``workshop.author`` permission per §3.26.14 three-tier access model;
admin role canonically grants this scope).

**Anti-pattern guards explicit at API substrate**:
- §2.4.4 Anti-pattern 9 (primitive proliferation): Tune mode boundary
  enforced at service layer; API surfaces 422 on violation.
- §2.4.4 Anti-pattern 8 (vertical-specific code creep): API is generic
  Workshop substrate; per-template dispatch via ``template_type`` path
  parameter.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models import User
from app.services.workshop import registry as workshop_registry
from app.services.workshop import tenant_config as workshop_tenant_config
from app.services.workshop.tenant_config import (
    WorkshopTuneModeBoundaryViolation,
    WorkshopTuneModeError,
    WorkshopTuneModeNotFound,
)


router = APIRouter()


# ─────────────────────────────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────────────────────────────


class TemplateTypeDescriptorResponse(BaseModel):
    """Workshop template-type registry entry surfaced via API."""

    template_type: str
    display_name: str
    description: str
    applicable_verticals: list[str]
    applicable_authoring_contexts: list[str]
    empty_canvas_state_factory_key: str
    tune_mode_dimensions: list[str]
    sort_order: int


class TenantConfigResponse(BaseModel):
    """Per-tenant Tune mode configuration response.

    Mirrors the canonical shape from
    ``workshop.tenant_config.get_tenant_personalization_config``.
    Permissive shape (Pydantic ``extra="allow"``) so future Tune mode
    dimensions surface without schema bumps.
    """

    template_type: str
    display_labels: dict[str, str]
    emblem_catalog: list[str]
    font_catalog: list[str]
    legacy_print_catalog: list[str]
    defaults: dict[str, Any]
    vinyl_symbols: list[str]


class TenantConfigUpdateRequest(BaseModel):
    """Per-tenant Tune mode configuration update request.

    Partial-update semantics: only present dimensions are written.
    Each dimension key MUST match a registered Tune mode dimension for
    the template-type per registry; service layer raises 422 on
    boundary violation.
    """

    display_labels: dict[str, str] | None = Field(
        default=None,
        description=(
            "Map from canonical option_type → tenant display label. "
            "Keys outside CANONICAL_OPTION_TYPES rejected with 422 per "
            "§3.26.11.12.19.2 vocabulary scope freeze."
        ),
    )
    emblem_catalog: list[str] | None = Field(
        default=None,
        description=(
            "Subset of canonical-default emblem catalog. Empty list "
            "resets to canonical default at read time. Cannot add "
            "entries outside canonical default per Anti-pattern 9 guard."
        ),
    )
    font_catalog: list[str] | None = None
    legacy_print_catalog: list[str] | None = None


# ─────────────────────────────────────────────────────────────────────
# Error translation
# ─────────────────────────────────────────────────────────────────────


def _translate(exc: WorkshopTuneModeError) -> HTTPException:
    return HTTPException(status_code=exc.http_status, detail=str(exc))


def _descriptor_to_response(
    d: workshop_registry.TemplateTypeDescriptor,
) -> TemplateTypeDescriptorResponse:
    return TemplateTypeDescriptorResponse(
        template_type=d.template_type,
        display_name=d.display_name,
        description=d.description,
        applicable_verticals=list(d.applicable_verticals),
        applicable_authoring_contexts=list(d.applicable_authoring_contexts),
        empty_canvas_state_factory_key=d.empty_canvas_state_factory_key,
        tune_mode_dimensions=list(d.tune_mode_dimensions),
        sort_order=d.sort_order,
    )


# ─────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────


@router.get(
    "/template-types",
    response_model=list[TemplateTypeDescriptorResponse],
)
def list_template_types(
    vertical: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TemplateTypeDescriptorResponse]:
    """List Workshop template-types registered at canonical substrate.

    Optional ``vertical`` filter narrows to template-types whose
    ``applicable_verticals`` includes the value or contains ``"*"``.
    Tenant-scoped via authentication; no per-tenant filtering applied
    at registry level (template-types are platform substrate).
    """
    descriptors = workshop_registry.list_template_types(vertical=vertical)
    return [_descriptor_to_response(d) for d in descriptors]


@router.get(
    "/personalization-studio/{template_type}/tenant-config",
    response_model=TenantConfigResponse,
)
def get_tenant_config(
    template_type: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> TenantConfigResponse:
    """Read per-tenant Tune mode configuration.

    Returns the resolved config (tenant overrides + canonical defaults)
    for chrome consumption per §14.14.2 + §14.14.1 visual canon.

    Admin-gated per Workshop access discipline (§3.26.14 three-tier
    access model — Tune mode authoring requires ``workshop.author``
    canonically held by admin role).
    """
    try:
        config = workshop_tenant_config.get_tenant_personalization_config(
            db,
            company_id=current_user.company_id,
            template_type=template_type,
        )
        return TenantConfigResponse(**config)
    except WorkshopTuneModeNotFound as exc:
        raise _translate(exc) from exc
    except WorkshopTuneModeError as exc:
        raise _translate(exc) from exc


@router.patch(
    "/personalization-studio/{template_type}/tenant-config",
    response_model=TenantConfigResponse,
)
def update_tenant_config(
    template_type: str,
    body: TenantConfigUpdateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> TenantConfigResponse:
    """Update per-tenant Tune mode configuration.

    Partial-update semantics — only dimensions present in body are
    written. Tune mode boundary enforced at service layer per
    §3.26.11.12.19.2:

    - ``display_labels`` keys must be in ``CANONICAL_OPTION_TYPES``
    - Catalog values must be subsets of canonical-default catalogs
    - Dimension keys must be registered for the template-type

    Boundary violations return HTTP 422.
    """
    # Pydantic ``model_dump`` with ``exclude_unset=True`` — only
    # present fields propagate to service layer (partial update).
    updates = body.model_dump(exclude_unset=True, exclude_none=True)
    if not updates:
        # No-op update — return current config unchanged.
        try:
            config = workshop_tenant_config.get_tenant_personalization_config(
                db,
                company_id=current_user.company_id,
                template_type=template_type,
            )
            return TenantConfigResponse(**config)
        except WorkshopTuneModeError as exc:
            raise _translate(exc) from exc

    try:
        config = workshop_tenant_config.update_tenant_personalization_config(
            db,
            company_id=current_user.company_id,
            template_type=template_type,
            updates=updates,
        )
        db.commit()
        return TenantConfigResponse(**config)
    except WorkshopTuneModeBoundaryViolation as exc:
        db.rollback()
        raise _translate(exc) from exc
    except WorkshopTuneModeError as exc:
        db.rollback()
        raise _translate(exc) from exc
