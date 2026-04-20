"""NL Creation API — Phase 4.

Three endpoints:

  POST /api/v1/nl-creation/extract
      Debounced per-keystroke extraction. Returns ExtractionResult.
      User-scoped. Accepts active_space_id for space-aware extraction.
      Hot path: p50 < 600ms, p99 < 1200ms (BLOCKING CI gate).

  POST /api/v1/nl-creation/create
      Materialize an entity from an ExtractionResult (possibly with
      user corrections). Returns the new entity_id + navigate URL.

  GET  /api/v1/nl-creation/entity-types
      Registry dump. Frontend uses it to know the field list per
      entity type without hard-coding.

All endpoints tenant-scope via get_current_user. Permission gating
honors NLEntityConfig.required_permission on /create.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.nl_creation import (
    CreationValidationError,
    ExtractionRequest,
    FieldExtraction,
    NLCreationError,
    UnknownEntityType,
    create as nl_create,
    extract as nl_extract,
    list_entity_configs,
)
from app.services.permission_service import user_has_permission

router = APIRouter()


# ── Pydantic request / response shapes ───────────────────────────────


class _FieldExtractionBody(BaseModel):
    field_key: str
    field_label: str
    extracted_value: Any
    display_value: str
    confidence: float
    source: Literal[
        "structured_parser",
        "entity_resolver",
        "ai_extraction",
        "space_default",
    ]
    resolved_entity_id: str | None = None
    resolved_entity_type: str | None = None


class _ExtractRequest(BaseModel):
    entity_type: Literal["case", "event", "contact"]
    natural_language: str
    active_space_id: str | None = None
    prior_extractions: list[_FieldExtractionBody] = Field(default_factory=list)


class _ExtractResponse(BaseModel):
    entity_type: str
    extractions: list[_FieldExtractionBody]
    missing_required: list[str]
    raw_input: str
    extraction_ms: int
    ai_execution_id: str | None = None
    ai_latency_ms: int | None = None
    space_default_fields: list[str] = Field(default_factory=list)


class _CreateRequest(BaseModel):
    entity_type: Literal["case", "event", "contact"]
    extractions: list[_FieldExtractionBody]
    raw_input: str = ""


class _CreateResponse(BaseModel):
    entity_id: str
    entity_type: str
    navigate_url: str


class _FieldSchemaResponse(BaseModel):
    field_key: str
    field_label: str
    field_type: str
    required: bool
    enum_values: list[str] | None = None
    has_structured_parser: bool
    has_entity_resolver: bool
    ai_hint: str | None = None


class _EntityTypeResponse(BaseModel):
    entity_type: str
    display_name: str
    ai_prompt_key: str
    navigate_url_template: str
    required_permission: str | None
    fields: list[_FieldSchemaResponse]
    space_defaults: dict[str, dict[str, Any]]


# ── Helpers ──────────────────────────────────────────────────────────


def _body_to_extraction(body: _FieldExtractionBody) -> FieldExtraction:
    return FieldExtraction(
        field_key=body.field_key,
        field_label=body.field_label,
        extracted_value=body.extracted_value,
        display_value=body.display_value,
        confidence=body.confidence,
        source=body.source,
        resolved_entity_id=body.resolved_entity_id,
        resolved_entity_type=body.resolved_entity_type,
    )


def _extraction_to_body(e: FieldExtraction) -> _FieldExtractionBody:
    return _FieldExtractionBody(
        field_key=e.field_key,
        field_label=e.field_label,
        extracted_value=e.extracted_value,
        display_value=e.display_value,
        confidence=e.confidence,
        source=e.source,
        resolved_entity_id=e.resolved_entity_id,
        resolved_entity_type=e.resolved_entity_type,
    )


def _translate(exc: NLCreationError) -> HTTPException:
    return HTTPException(status_code=exc.http_status, detail=str(exc))


# ── Routes ───────────────────────────────────────────────────────────


@router.post("/extract", response_model=_ExtractResponse)
def extract_endpoint(
    body: _ExtractRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _ExtractResponse:
    """Extract fields from NL input. Hot path — debounced 300ms
    client-side; p50 < 600ms backend target."""
    import time as _t_time
    from app.services import arc_telemetry as _arc_t
    _t0 = _t_time.perf_counter()
    _errored = False

    request = ExtractionRequest(
        entity_type=body.entity_type,
        natural_language=body.natural_language,
        tenant_id=current_user.company_id,
        user_id=current_user.id,
        active_space_id=body.active_space_id,
        prior_extractions=[
            _body_to_extraction(e) for e in body.prior_extractions
        ],
    )
    try:
        result = nl_extract(db, request=request, user=current_user)
    except NLCreationError as exc:
        _errored = True
        raise _translate(exc) from exc
    finally:
        _arc_t.record(
            "nl_extract",
            (_t_time.perf_counter() - _t0) * 1000.0,
            errored=_errored,
        )

    return _ExtractResponse(
        entity_type=result.entity_type,
        extractions=[_extraction_to_body(e) for e in result.extractions],
        missing_required=result.missing_required,
        raw_input=result.raw_input,
        extraction_ms=result.extraction_ms,
        ai_execution_id=result.ai_execution_id,
        ai_latency_ms=result.ai_latency_ms,
        space_default_fields=result.space_default_fields,
    )


@router.post("/create", response_model=_CreateResponse, status_code=201)
def create_endpoint(
    body: _CreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _CreateResponse:
    """Materialize the entity. Permission gate enforced via the
    entity config's `required_permission`. Validation errors become
    400; unknown entity types 404."""
    from app.services.nl_creation import get_entity_config

    config = get_entity_config(body.entity_type)
    if config is None:
        raise HTTPException(
            status_code=404, detail=f"Unknown entity_type: {body.entity_type}"
        )
    if config.required_permission and not user_has_permission(
        current_user, db, config.required_permission
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                f"Missing permission {config.required_permission!r} for "
                f"creating {body.entity_type}"
            ),
        )

    try:
        result = nl_create(
            db,
            user=current_user,
            entity_type=body.entity_type,
            extractions=[_body_to_extraction(e) for e in body.extractions],
            raw_input=body.raw_input,
        )
    except CreationValidationError as exc:
        raise _translate(exc) from exc
    except UnknownEntityType as exc:
        raise _translate(exc) from exc
    except NLCreationError as exc:
        raise _translate(exc) from exc

    return _CreateResponse(
        entity_id=result["entity_id"],
        entity_type=result["entity_type"],
        navigate_url=result["navigate_url"],
    )


@router.get(
    "/entity-types", response_model=list[_EntityTypeResponse]
)
def list_entity_types_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[_EntityTypeResponse]:
    """List all supported entity types + their field schemas.

    Client uses this on mount to know which entities can route to
    the NL overlay. Permission gates applied here — entities the
    user can't create via `required_permission` are hidden.
    """
    out: list[_EntityTypeResponse] = []
    for cfg in list_entity_configs():
        if cfg.required_permission and not user_has_permission(
            current_user, db, cfg.required_permission
        ):
            continue
        out.append(
            _EntityTypeResponse(
                entity_type=cfg.entity_type,
                display_name=cfg.display_name,
                ai_prompt_key=cfg.ai_prompt_key,
                navigate_url_template=cfg.navigate_url_template,
                required_permission=cfg.required_permission,
                fields=[
                    _FieldSchemaResponse(
                        field_key=fx.field_key,
                        field_label=fx.field_label,
                        field_type=fx.field_type,
                        required=fx.required,
                        enum_values=fx.enum_values,
                        has_structured_parser=fx.structured_parser is not None,
                        has_entity_resolver=fx.entity_resolver_config is not None,
                        ai_hint=fx.ai_hint,
                    )
                    for fx in cfg.field_extractors
                ],
                space_defaults=cfg.space_defaults,
            )
        )
    return out
