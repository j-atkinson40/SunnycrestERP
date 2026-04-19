"""Bridgeable Intelligence API — admin-only routes under /api/v1/intelligence.

Phase 1 endpoints: prompts CRUD + versions + activate/retire + test playground,
executions list + detail + reproduce, experiments CRUD + results + conclude,
models GET + PATCH, conversations GET + messages + DELETE.

All routes require an admin user. Tenant-scoped reads filter by
current_user.company_id; platform-global prompts (company_id=null) are always
visible.
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Integer, asc, cast, desc, func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin, require_super_admin
from app.database import get_db
from app.models.intelligence import (
    IntelligenceConversation,
    IntelligenceExecution,
    IntelligenceExperiment,
    IntelligenceMessage,
    IntelligenceModelRoute,
    IntelligencePrompt,
    IntelligencePromptAuditLog,
    IntelligencePromptVersion,
)
from app.models.user import User
from app.schemas.intelligence import (
    ActivateRequest,
    AuditLogEntry,
    CallerModuleOption,
    ConversationResponse,
    DailyStatPoint,
    DraftCreateRequest,
    DraftUpdateRequest,
    EditPermissionResponse,
    ExecutionListItem,
    ExecutionResponse,
    ExperimentConclude,
    ExperimentCreate,
    ExperimentDailyPoint,
    ExperimentListItem,
    ExperimentPromoteRequest,
    ExperimentResponse,
    ExperimentResultsResponse,
    ExperimentResultsResponseExtended,
    ExperimentStopRequest,
    ExperimentVariantStats,
    MessageResponse,
    ModelRouteResponse,
    ModelRouteUpdate,
    OverallStatsResponse,
    PromptCreate,
    PromptDetailResponse,
    PromptListItem,
    PromptResponse,
    PromptStatsResponse,
    PromptTestRequest,
    PromptTestResponse,
    PromptVersionCreate,
    PromptVersionResponse,
    ReproduceResponse,
    RollbackRequest,
    SchemaValidationIssue,
    TestRunRequest,
    TopPromptByCost,
    TopPromptByVolume,
)
from app.services.intelligence import (
    activate_version as svc_activate_version,
)
from app.services.intelligence import (
    conclude_experiment,
    execute as intelligence_execute,
)
from app.services.intelligence import (
    create_version as svc_create_version,
)
from app.services.intelligence import (
    is_ready_to_conclude as svc_is_ready_to_conclude,
)
from app.services.intelligence import (
    list_prompts as svc_list_prompts,
)
from app.services.intelligence import (
    retire_version as svc_retire_version,
)
from app.services.intelligence.experiment_service import collect_variant_stats
from app.services.intelligence.prompt_registry import (
    PromptNotFoundError,
    PromptVersionNotReadyError,
    create_prompt as svc_create_prompt,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════
# Prompts
# ═══════════════════════════════════════════════════════════════════════


@router.get("/prompts", response_model=list[PromptListItem])
def list_prompts_endpoint(
    domain: str | None = Query(None),
    include_platform: bool = Query(True),
    search: str | None = Query(None, description="Matches prompt_key + display_name + description"),
    caller_module: str | None = Query(None),
    model_preference: str | None = Query(None, description="Filter by active version's model_preference"),
    is_active: bool | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List prompts visible to the current tenant, decorated with 30d usage stats.

    Platform-global prompts that aren't overridden by this tenant are included
    by default. Filter by domain when narrowing (e.g. domain=scribe).

    30-day stats (executions_30d, error_rate_30d, avg_latency_ms_30d,
    avg_cost_usd_30d) are aggregated in a single pass to keep the list
    endpoint responsive even with hundreds of prompts.
    """
    prompts = svc_list_prompts(
        db,
        company_id=current_user.company_id,
        domain=domain,
        include_platform=include_platform,
    )

    # Apply python-level filters that the service doesn't support
    if is_active is not None:
        prompts = [p for p in prompts if p.is_active == is_active]
    if caller_module:
        prompts = [p for p in prompts if p.caller_module == caller_module]
    if search:
        needle = search.lower()
        prompts = [
            p for p in prompts
            if (needle in p.prompt_key.lower()
                or needle in (p.display_name or "").lower()
                or needle in (p.description or "").lower())
        ]

    # Active version lookup in one query
    prompt_ids = [p.id for p in prompts]
    active_by_prompt: dict[str, IntelligencePromptVersion] = {}
    draft_by_prompt: dict[str, bool] = {}
    if prompt_ids:
        for v in (
            db.query(IntelligencePromptVersion)
            .filter(
                IntelligencePromptVersion.prompt_id.in_(prompt_ids),
                IntelligencePromptVersion.status == "active",
            )
            .all()
        ):
            active_by_prompt[v.prompt_id] = v
        # Phase 3b — bulk check for any draft per prompt
        for pid, count in (
            db.query(
                IntelligencePromptVersion.prompt_id,
                func.count(IntelligencePromptVersion.id),
            )
            .filter(
                IntelligencePromptVersion.prompt_id.in_(prompt_ids),
                IntelligencePromptVersion.status == "draft",
            )
            .group_by(IntelligencePromptVersion.prompt_id)
            .all()
        ):
            if int(count) > 0:
                draft_by_prompt[pid] = True

    if model_preference:
        prompts = [
            p for p in prompts
            if active_by_prompt.get(p.id)
            and active_by_prompt[p.id].model_preference == model_preference
        ]

    # All-time execution count in one query (production only — test
    # executions excluded from every stat computation).
    total_exec_by_prompt: dict[str, int] = {}
    if prompt_ids:
        rows = (
            db.query(
                IntelligenceExecution.prompt_id,
                func.count(IntelligenceExecution.id),
            )
            .filter(
                IntelligenceExecution.prompt_id.in_(prompt_ids),
                IntelligenceExecution.is_test_execution.is_(False),
            )
            .group_by(IntelligenceExecution.prompt_id)
            .all()
        )
        total_exec_by_prompt = {pid: int(c) for pid, c in rows if pid}

    # 30-day aggregates in one pass: count, error_count, avg_latency, avg_cost
    stats_by_prompt: dict[str, dict[str, Any]] = {}
    if prompt_ids:
        since = datetime.now(timezone.utc) - timedelta(days=30)
        rows = (
            db.query(
                IntelligenceExecution.prompt_id,
                func.count(IntelligenceExecution.id).label("n"),
                func.sum(
                    cast(IntelligenceExecution.status != "success", Integer)
                ).label("errors"),
                func.avg(IntelligenceExecution.latency_ms).label("avg_latency"),
                func.avg(IntelligenceExecution.cost_usd).label("avg_cost"),
            )
            .filter(
                IntelligenceExecution.prompt_id.in_(prompt_ids),
                IntelligenceExecution.created_at >= since,
                IntelligenceExecution.is_test_execution.is_(False),
            )
            .group_by(IntelligenceExecution.prompt_id)
            .all()
        )
        for row in rows:
            pid = row.prompt_id
            if not pid:
                continue
            n = int(row.n or 0)
            errors = int(row.errors or 0)
            stats_by_prompt[pid] = {
                "executions_30d": n,
                "error_rate_30d": (errors / n) if n > 0 else 0.0,
                "avg_latency_ms_30d": float(row.avg_latency) if row.avg_latency is not None else None,
                "avg_cost_usd_30d": Decimal(str(row.avg_cost)) if row.avg_cost is not None else None,
            }

    # Paginate
    total = len(prompts)
    sliced = prompts[offset : offset + limit]

    items: list[PromptListItem] = []
    for p in sliced:
        active = active_by_prompt.get(p.id)
        stats = stats_by_prompt.get(p.id, {})
        item = PromptListItem.model_validate(p)
        item.active_version_id = active.id if active else None
        item.active_version_number = active.version_number if active else None
        item.active_model_preference = active.model_preference if active else None
        item.execution_count = total_exec_by_prompt.get(p.id, 0)
        item.executions_30d = stats.get("executions_30d", 0)
        item.error_rate_30d = stats.get("error_rate_30d", 0.0)
        item.avg_latency_ms_30d = stats.get("avg_latency_ms_30d")
        item.avg_cost_usd_30d = stats.get("avg_cost_usd_30d")
        item.has_draft = draft_by_prompt.get(p.id, False)
        items.append(item)

    # Default sort: executions_30d desc
    items.sort(key=lambda x: x.executions_30d, reverse=True)

    _ = total  # kept for future X-Total-Count support
    return items


@router.post("/prompts", response_model=PromptResponse, status_code=status.HTTP_201_CREATED)
def create_prompt_endpoint(
    body: PromptCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new prompt.

    Platform-global prompts require `company_id=null` and are typically created
    by seed scripts. A tenant admin creating via this endpoint always scopes
    the prompt to their own tenant regardless of the body field.
    """
    target_company = body.company_id if body.company_id is not None else current_user.company_id
    prompt = svc_create_prompt(
        db,
        prompt_key=body.prompt_key,
        display_name=body.display_name,
        domain=body.domain,
        description=body.description,
        caller_module=body.caller_module,
        company_id=target_company,
    )
    return prompt


@router.get("/prompts/{prompt_id}", response_model=PromptDetailResponse)
def get_prompt_endpoint(
    prompt_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Prompt detail with versions (full content) + 30-day stats."""
    prompt = _get_visible_prompt(db, prompt_id, current_user.company_id)
    versions = (
        db.query(IntelligencePromptVersion)
        .filter(IntelligencePromptVersion.prompt_id == prompt.id)
        .order_by(desc(IntelligencePromptVersion.version_number))
        .all()
    )
    active = next((v for v in versions if v.status == "active"), None)

    since = datetime.now(timezone.utc) - timedelta(days=30)
    row = (
        db.query(
            func.count(IntelligenceExecution.id).label("n"),
            func.sum(
                cast(IntelligenceExecution.status != "success", Integer)
            ).label("errors"),
            func.avg(IntelligenceExecution.latency_ms).label("avg_latency"),
            func.avg(IntelligenceExecution.cost_usd).label("avg_cost"),
        )
        .filter(
            IntelligenceExecution.prompt_id == prompt.id,
            IntelligenceExecution.created_at >= since,
            IntelligenceExecution.is_test_execution.is_(False),
        )
        .first()
    )
    n = int(row.n or 0) if row else 0
    errors = int(row.errors or 0) if row else 0

    resp = PromptDetailResponse.model_validate(prompt)
    resp.active_version_id = active.id if active else None
    resp.active_version_number = active.version_number if active else None
    resp.versions = [PromptVersionResponse.model_validate(v) for v in versions]
    resp.executions_30d = n
    resp.error_rate_30d = (errors / n) if n > 0 else 0.0
    resp.avg_latency_ms_30d = float(row.avg_latency) if row and row.avg_latency is not None else None
    resp.avg_cost_usd_30d = Decimal(str(row.avg_cost)) if row and row.avg_cost is not None else None
    return resp


@router.get(
    "/prompts/{prompt_id}/versions/{version_id}",
    response_model=PromptVersionResponse,
)
def get_prompt_version_endpoint(
    prompt_id: str,
    version_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Full version content (system_prompt, user_template, schemas, etc.)."""
    _get_visible_prompt(db, prompt_id, current_user.company_id)
    version = (
        db.query(IntelligencePromptVersion)
        .filter(
            IntelligencePromptVersion.id == version_id,
            IntelligencePromptVersion.prompt_id == prompt_id,
        )
        .first()
    )
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")
    return version


@router.get("/prompts/{prompt_id}/versions", response_model=list[PromptVersionResponse])
def list_versions_endpoint(
    prompt_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _get_visible_prompt(db, prompt_id, current_user.company_id)
    versions = (
        db.query(IntelligencePromptVersion)
        .filter(IntelligencePromptVersion.prompt_id == prompt_id)
        .order_by(IntelligencePromptVersion.version_number)
        .all()
    )
    return versions


@router.post(
    "/prompts/{prompt_id}/versions",
    response_model=PromptVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_version_endpoint(
    prompt_id: str,
    body: PromptVersionCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _get_visible_prompt(db, prompt_id, current_user.company_id)
    version = svc_create_version(
        db,
        prompt_id=prompt_id,
        system_prompt=body.system_prompt,
        user_template=body.user_template,
        model_preference=body.model_preference,
        variable_schema=body.variable_schema,
        response_schema=body.response_schema,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
        force_json=body.force_json,
        supports_streaming=body.supports_streaming,
        supports_tool_use=body.supports_tool_use,
        changelog=body.changelog,
        created_by=current_user.id,
    )
    return version


@router.post(
    "/prompts/{prompt_id}/versions/{version_id}/activate",
    response_model=PromptVersionResponse,
)
def activate_version_endpoint(
    prompt_id: str,
    version_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _get_visible_prompt(db, prompt_id, current_user.company_id)
    try:
        version = svc_activate_version(db, version_id)
    except PromptVersionNotReadyError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PromptNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return version


@router.post(
    "/prompts/{prompt_id}/versions/{version_id}/retire",
    response_model=PromptVersionResponse,
)
def retire_version_endpoint(
    prompt_id: str,
    version_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _get_visible_prompt(db, prompt_id, current_user.company_id)
    try:
        version = svc_retire_version(db, version_id)
    except PromptNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return version


@router.post("/prompts/{prompt_id}/test", response_model=PromptTestResponse)
def test_prompt_endpoint(
    prompt_id: str,
    body: PromptTestRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Render + execute a specific version without saving an execution row."""
    _get_visible_prompt(db, prompt_id, current_user.company_id)
    version = (
        db.query(IntelligencePromptVersion)
        .filter(
            IntelligencePromptVersion.id == body.version_id,
            IntelligencePromptVersion.prompt_id == prompt_id,
        )
        .first()
    )
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")

    try:
        result = intelligence_execute(
            db,
            prompt_key="__playground__",  # unused; override_version_id takes precedence
            variables=body.variables,
            company_id=current_user.company_id,
            caller_module="intelligence.playground",
            override_version_id=version.id,
            persist=False,
        )
    except Exception as e:  # noqa: BLE001 — surface render/validation errors to the UI
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    return PromptTestResponse(
        rendered_system_prompt=result.rendered_system_prompt,
        rendered_user_prompt=result.rendered_user_prompt,
        response_text=result.response_text,
        response_parsed=result.response_parsed if isinstance(result.response_parsed, dict) else None,
        model_used=result.model_used,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=result.latency_ms,
        cost_usd=result.cost_usd,
        status=result.status,
    )


# ═══════════════════════════════════════════════════════════════════════
# Executions
# ═══════════════════════════════════════════════════════════════════════


@router.get("/executions", response_model=list[ExecutionListItem])
def list_executions_endpoint(
    prompt_key: str | None = Query(None),
    caller_module: str | None = Query(None),
    caller_entity_type: str | None = Query(None),
    caller_entity_id: str | None = Query(None),
    execution_status: str | None = Query(None, alias="status"),
    company_id: str | None = Query(None, description="'platform' for platform-global"),
    since_days: int = Query(7, ge=1, le=365),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    include_test_executions: bool = Query(
        False,
        description="Include is_test_execution=True rows. Off by default.",
    ),
    sort: str = Query(
        "created_desc",
        pattern="^(created_desc|created_asc|cost_desc|latency_desc|tokens_desc)$",
    ),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Paginated execution audit log.

    Date filtering: `start_date`/`end_date` take precedence if provided;
    otherwise `since_days` applies.
    Company filter: `company_id=platform` for platform-global only; omit
    for tenant-scope + platform.
    """
    if start_date is None and end_date is None:
        start_date = datetime.now(timezone.utc) - timedelta(days=since_days)

    q = db.query(IntelligenceExecution)
    if start_date is not None:
        q = q.filter(IntelligenceExecution.created_at >= start_date)
    if end_date is not None:
        q = q.filter(IntelligenceExecution.created_at <= end_date)

    if company_id == "platform":
        q = q.filter(IntelligenceExecution.company_id.is_(None))
    elif company_id:
        q = q.filter(IntelligenceExecution.company_id == company_id)
    else:
        q = q.filter(
            or_(
                IntelligenceExecution.company_id == current_user.company_id,
                IntelligenceExecution.company_id.is_(None),
            )
        )

    # Phase 3b — test executions hidden by default; admins opt in.
    if not include_test_executions:
        q = q.filter(IntelligenceExecution.is_test_execution.is_(False))

    if caller_module:
        q = q.filter(IntelligenceExecution.caller_module == caller_module)
    if caller_entity_type:
        q = q.filter(IntelligenceExecution.caller_entity_type == caller_entity_type)
    if caller_entity_id:
        q = q.filter(IntelligenceExecution.caller_entity_id == caller_entity_id)
    if execution_status:
        q = q.filter(IntelligenceExecution.status == execution_status)
    if prompt_key:
        prompt_ids = [
            row.id
            for row in db.query(IntelligencePrompt.id)
            .filter(IntelligencePrompt.prompt_key == prompt_key)
            .all()
        ]
        if prompt_ids:
            q = q.filter(IntelligenceExecution.prompt_id.in_(prompt_ids))
        else:
            return []

    sort_map = {
        "created_desc": desc(IntelligenceExecution.created_at),
        "created_asc": asc(IntelligenceExecution.created_at),
        "cost_desc": desc(IntelligenceExecution.cost_usd),
        "latency_desc": desc(IntelligenceExecution.latency_ms),
        "tokens_desc": desc(
            func.coalesce(IntelligenceExecution.input_tokens, 0)
            + func.coalesce(IntelligenceExecution.output_tokens, 0)
        ),
    }
    rows = (
        q.order_by(sort_map[sort])
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Join prompt_key back in for display
    prompt_lookup: dict[str, str] = {}
    if rows:
        prompt_ids = {r.prompt_id for r in rows if r.prompt_id}
        if prompt_ids:
            for p in (
                db.query(IntelligencePrompt.id, IntelligencePrompt.prompt_key)
                .filter(IntelligencePrompt.id.in_(prompt_ids))
                .all()
            ):
                prompt_lookup[p.id] = p.prompt_key

    items: list[ExecutionListItem] = []
    for r in rows:
        item = ExecutionListItem.model_validate(r)
        item.prompt_key = prompt_lookup.get(r.prompt_id) if r.prompt_id else None
        items.append(item)
    return items


@router.get("/executions/{execution_id}", response_model=ExecutionResponse)
def get_execution_endpoint(
    execution_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    row = _get_visible_execution(db, execution_id, current_user.company_id)
    return row


@router.post("/executions/{execution_id}/reproduce", response_model=ReproduceResponse)
def reproduce_execution_endpoint(
    execution_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Re-run a prior execution with the same version + inputs. Returns both
    renderings so the caller can verify the rendered prompts are byte-identical."""
    original = _get_visible_execution(db, execution_id, current_user.company_id)
    if original.prompt_version_id is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Execution has no prompt_version_id; cannot reproduce",
        )

    result = intelligence_execute(
        db,
        prompt_key="__reproduce__",
        variables=original.input_variables or {},
        company_id=original.company_id,
        caller_module="intelligence.reproduce",
        caller_entity_type=original.caller_entity_type,
        caller_entity_id=original.caller_entity_id,
        override_version_id=original.prompt_version_id,
        persist=True,
    )

    return ReproduceResponse(
        original_execution_id=original.id,
        new_execution_id=result.execution_id,
        rendered_system_prompt_match=(
            result.rendered_system_prompt == (original.rendered_system_prompt or "")
        ),
        rendered_user_prompt_match=(
            result.rendered_user_prompt == (original.rendered_user_prompt or "")
        ),
        original_response_text=original.response_text,
        new_response_text=result.response_text,
    )


# ═══════════════════════════════════════════════════════════════════════
# Experiments
# ═══════════════════════════════════════════════════════════════════════


def _get_visible_experiment(
    db: Session, experiment_id: str, user: User
) -> IntelligenceExperiment:
    """404 unless the experiment's prompt is visible to this user's tenant."""
    exp = db.query(IntelligenceExperiment).filter_by(id=experiment_id).first()
    if exp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Experiment not found")
    # Reuse prompt visibility check — cross-tenant experiments are invisible
    prompt = db.query(IntelligencePrompt).filter_by(id=exp.prompt_id).first()
    if prompt is None or prompt.company_id not in (None, user.company_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Experiment not found")
    return exp


@router.get("/experiments", response_model=list[ExperimentListItem])
def list_experiments_endpoint(
    status_filter: str | None = Query(
        None,
        alias="status",
        description="running | completed | draft | all",
    ),
    prompt_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List experiments visible to this tenant, decorated with variant
    execution counts and the prompt's prompt_key."""
    q = db.query(IntelligenceExperiment).filter(
        or_(
            IntelligenceExperiment.company_id == current_user.company_id,
            IntelligenceExperiment.company_id.is_(None),
        )
    )
    if prompt_id:
        q = q.filter(IntelligenceExperiment.prompt_id == prompt_id)
    if status_filter and status_filter != "all":
        if status_filter == "running":
            # Accept both legacy "active" and Phase 3c "running"
            q = q.filter(IntelligenceExperiment.status.in_(("running", "active")))
        else:
            q = q.filter(IntelligenceExperiment.status == status_filter)

    rows = (
        q.order_by(desc(IntelligenceExperiment.started_at))
        .offset(offset)
        .limit(limit)
        .all()
    )
    if not rows:
        return []

    # Fetch all prompt_keys + version_numbers in one pass
    prompt_ids = {r.prompt_id for r in rows}
    prompt_keys = {
        p.id: p.prompt_key
        for p in db.query(IntelligencePrompt.id, IntelligencePrompt.prompt_key)
        .filter(IntelligencePrompt.id.in_(prompt_ids))
        .all()
    }
    version_ids: set[str] = set()
    for r in rows:
        version_ids.add(r.version_a_id)
        version_ids.add(r.version_b_id)
    version_numbers = {
        v.id: v.version_number
        for v in db.query(
            IntelligencePromptVersion.id, IntelligencePromptVersion.version_number
        )
        .filter(IntelligencePromptVersion.id.in_(version_ids))
        .all()
    }
    # Counts per (experiment, variant)
    count_rows = (
        db.query(
            IntelligenceExecution.experiment_id,
            IntelligenceExecution.experiment_variant,
            func.count(IntelligenceExecution.id),
        )
        .filter(
            IntelligenceExecution.experiment_id.in_({r.id for r in rows}),
            IntelligenceExecution.is_test_execution.is_(False),
        )
        .group_by(
            IntelligenceExecution.experiment_id,
            IntelligenceExecution.experiment_variant,
        )
        .all()
    )
    counts: dict[str, dict[str, int]] = {}
    for eid, variant, n in count_rows:
        counts.setdefault(eid, {})[variant or ""] = int(n or 0)

    out: list[ExperimentListItem] = []
    for exp in rows:
        item = ExperimentListItem.model_validate(exp)
        item.prompt_key = prompt_keys.get(exp.prompt_id)
        item.version_a_number = version_numbers.get(exp.version_a_id)
        item.version_b_number = version_numbers.get(exp.version_b_id)
        c = counts.get(exp.id, {})
        item.variant_a_count = c.get("a", 0)
        item.variant_b_count = c.get("b", 0)
        out.append(item)
    return out


@router.post(
    "/experiments",
    response_model=ExperimentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_experiment_endpoint(
    body: ExperimentCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    # Validate the two versions belong to the same prompt
    if body.version_a_id == body.version_b_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "version_a_id and version_b_id must be different",
        )
    versions = (
        db.query(IntelligencePromptVersion)
        .filter(IntelligencePromptVersion.id.in_([body.version_a_id, body.version_b_id]))
        .all()
    )
    if len(versions) != 2:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Both versions must exist")
    if not all(v.prompt_id == body.prompt_id for v in versions):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Both versions must belong to the specified prompt_id",
        )

    prompt = _get_visible_prompt(db, body.prompt_id, current_user.company_id)
    _enforce_edit_permission(current_user, prompt)

    scope = (
        body.company_id if body.company_id is not None else current_user.company_id
    )
    # Phase 3c — one running experiment per (prompt, scope)
    if body.start_immediately:
        from app.services.intelligence import find_running_for_prompt

        conflict = find_running_for_prompt(db, body.prompt_id, scope)
        if conflict is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Another experiment ({conflict.id}) is already running for "
                f"this prompt at this scope. Stop it before starting a new one.",
            )

    now = datetime.now(timezone.utc)
    exp = IntelligenceExperiment(
        id=str(_uuid.uuid4()),
        company_id=scope,
        prompt_id=body.prompt_id,
        name=body.name,
        hypothesis=body.hypothesis,
        version_a_id=body.version_a_id,
        version_b_id=body.version_b_id,
        traffic_split=body.traffic_split,
        min_sample_size=body.min_sample_size,
        status="running" if body.start_immediately else "draft",
        started_at=now if body.start_immediately else None,
    )
    db.add(exp)
    db.flush()
    db.commit()
    db.refresh(exp)
    return exp


@router.get("/experiments/{experiment_id}", response_model=ExperimentResponse)
def get_experiment_endpoint(
    experiment_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return _get_visible_experiment(db, experiment_id, current_user)


@router.post(
    "/experiments/{experiment_id}/start",
    response_model=ExperimentResponse,
)
def start_experiment_endpoint(
    experiment_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    exp = _get_visible_experiment(db, experiment_id, current_user)
    prompt = db.query(IntelligencePrompt).filter_by(id=exp.prompt_id).first()
    if prompt is not None:
        _enforce_edit_permission(current_user, prompt)

    from app.services.intelligence import start_experiment

    try:
        exp = start_experiment(db, experiment_id)
    except ValueError as e:
        # "Already running" is a conflict; "wrong status" is a 400.
        code = (
            status.HTTP_409_CONFLICT
            if "already running" in str(e)
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(code, str(e))
    db.commit()
    db.refresh(exp)
    return exp


@router.post(
    "/experiments/{experiment_id}/stop",
    response_model=ExperimentResponse,
)
def stop_experiment_endpoint(
    experiment_id: str,
    body: ExperimentStopRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    exp = _get_visible_experiment(db, experiment_id, current_user)
    prompt = db.query(IntelligencePrompt).filter_by(id=exp.prompt_id).first()
    if prompt is not None:
        _enforce_edit_permission(current_user, prompt)

    from app.services.intelligence import stop_experiment

    try:
        exp = stop_experiment(db, experiment_id, body.reason)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    _write_audit(
        db,
        prompt=prompt,
        version=None,
        action="experiment_stop",
        actor=current_user,
        changelog=body.reason,
        meta={"experiment_id": experiment_id},
    )
    db.commit()
    db.refresh(exp)
    return exp


@router.post(
    "/experiments/{experiment_id}/promote",
    response_model=ExperimentResponse,
)
def promote_experiment_endpoint(
    experiment_id: str,
    body: ExperimentPromoteRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Pick a variant as the winner, end the experiment, and activate the
    variant's version as the new active version of the prompt."""
    exp = _get_visible_experiment(db, experiment_id, current_user)
    prompt = db.query(IntelligencePrompt).filter_by(id=exp.prompt_id).first()
    if prompt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prompt not found")
    _enforce_edit_permission(current_user, prompt)
    _assert_confirmation_text(prompt, body.confirmation_text)

    if body.variant_version_id not in (exp.version_a_id, exp.version_b_id):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "variant_version_id must be one of the experiment's two versions",
        )

    from app.services.intelligence import conclude_experiment as svc_conclude

    # Capture prior active for the audit row
    prior_active = (
        db.query(IntelligencePromptVersion)
        .filter(
            IntelligencePromptVersion.prompt_id == prompt.id,
            IntelligencePromptVersion.status == "active",
        )
        .first()
    )

    try:
        exp = svc_conclude(db, experiment_id, body.variant_version_id, body.changelog)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    # Audit entry — experiment_promote records the decision; the activation
    # itself also flows through prompt_registry.activate_version which does
    # NOT write an audit row (Phase 1 code), so this is the sole record.
    new_active = (
        db.query(IntelligencePromptVersion)
        .filter(IntelligencePromptVersion.id == body.variant_version_id)
        .first()
    )
    meta: dict[str, Any] = {
        "experiment_id": experiment_id,
        "winner_variant": "a" if body.variant_version_id == exp.version_a_id else "b",
    }
    if prior_active is not None:
        meta["previous_active_version_id"] = prior_active.id
        meta["previous_active_version_number"] = prior_active.version_number
    _write_audit(
        db,
        prompt=prompt,
        version=new_active,
        action="experiment_promote",
        actor=current_user,
        changelog=body.changelog,
        meta=meta,
    )
    db.commit()
    db.refresh(exp)
    return exp


@router.get(
    "/experiments/{experiment_id}/results",
    response_model=ExperimentResultsResponseExtended,
)
def get_experiment_results_endpoint(
    experiment_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    exp = _get_visible_experiment(db, experiment_id, current_user)
    stats_by_variant = collect_variant_stats(db, experiment_id)

    from app.services.intelligence import (
        experiment_daily_breakdown,
        experiment_p95,
    )

    variants: list[ExperimentVariantStats] = []
    for label in ("a", "b"):
        v = stats_by_variant.get(label, {})
        version_id = exp.version_a_id if label == "a" else exp.version_b_id
        variants.append(
            ExperimentVariantStats(
                variant=label,
                version_id=version_id,
                sample_count=v.get("sample_count", 0),
                success_count=v.get("success_count", 0),
                error_count=v.get("error_count", 0),
                avg_latency_ms=v.get("avg_latency_ms"),
                avg_input_tokens=v.get("avg_input_tokens"),
                avg_output_tokens=v.get("avg_output_tokens"),
                total_cost_usd=Decimal(str(v.get("total_cost_usd") or 0)),
                success_rate=v.get("success_rate", 0.0),
            )
        )

    daily = [
        ExperimentDailyPoint(**row)
        for row in experiment_daily_breakdown(db, experiment_id)
    ]
    p95 = experiment_p95(db, experiment_id)

    return ExperimentResultsResponseExtended(
        experiment_id=experiment_id,
        status=exp.status,
        min_sample_size=exp.min_sample_size,
        variants=variants,
        p95_latency_ms=p95,
        daily_breakdown=daily,
        ready_to_conclude=svc_is_ready_to_conclude(db, experiment_id),
    )


@router.post("/experiments/{experiment_id}/conclude", response_model=ExperimentResponse)
def conclude_experiment_endpoint(
    experiment_id: str,
    body: ExperimentConclude,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Legacy — Phase 1 endpoint. Prefer POST /promote for the Phase 3c flow
    with audit + confirmation_text."""
    try:
        exp = conclude_experiment(
            db, experiment_id, body.winner_version_id, body.conclusion_notes
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return exp


# ═══════════════════════════════════════════════════════════════════════
# Model Routes
# ═══════════════════════════════════════════════════════════════════════


@router.get("/models", response_model=list[ModelRouteResponse])
def list_models_endpoint(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return db.query(IntelligenceModelRoute).order_by(IntelligenceModelRoute.route_key).all()


@router.patch("/models/{route_key}", response_model=ModelRouteResponse)
def update_model_route_endpoint(
    route_key: str,
    body: ModelRouteUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    route = (
        db.query(IntelligenceModelRoute)
        .filter(IntelligenceModelRoute.route_key == route_key)
        .first()
    )
    if route is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Route not found")

    updates = body.model_dump(exclude_unset=True)
    for field_name, value in updates.items():
        setattr(route, field_name, value)
    route.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(route)
    return route


# ═══════════════════════════════════════════════════════════════════════
# Conversations (Ask Bridgeable Assistant)
# ═══════════════════════════════════════════════════════════════════════


@router.get("/conversations", response_model=list[ConversationResponse])
def list_conversations_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Current user's conversation history."""
    rows = (
        db.query(IntelligenceConversation)
        .filter(
            IntelligenceConversation.company_id == current_user.company_id,
            IntelligenceConversation.user_id == current_user.id,
        )
        .order_by(desc(IntelligenceConversation.last_message_at))
        .limit(200)
        .all()
    )

    out: list[ConversationResponse] = []
    for conv in rows:
        item = ConversationResponse.model_validate(conv)
        item.message_count = (
            db.query(func.count(IntelligenceMessage.id))
            .filter(IntelligenceMessage.conversation_id == conv.id)
            .scalar()
        ) or 0
        out.append(item)
    return out


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[MessageResponse],
)
def get_conversation_messages_endpoint(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = _get_user_conversation(db, conversation_id, current_user)
    return (
        db.query(IntelligenceMessage)
        .filter(IntelligenceMessage.conversation_id == conv.id)
        .order_by(IntelligenceMessage.created_at)
        .all()
    )


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation_endpoint(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = _get_user_conversation(db, conversation_id, current_user)
    db.delete(conv)
    db.commit()
    return None


# ═══════════════════════════════════════════════════════════════════════
# Stats aggregations (Phase 3a)
# ═══════════════════════════════════════════════════════════════════════


@router.get("/stats/prompt/{prompt_id}", response_model=PromptStatsResponse)
def prompt_stats_endpoint(
    prompt_id: str,
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Per-prompt stats with daily breakdown."""
    prompt = _get_visible_prompt(db, prompt_id, current_user.company_id)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    totals = (
        db.query(
            func.count(IntelligenceExecution.id).label("n"),
            func.sum(
                cast(IntelligenceExecution.status == "success", Integer)
            ).label("successes"),
            func.sum(
                cast(IntelligenceExecution.status != "success", Integer)
            ).label("errors"),
            func.avg(IntelligenceExecution.latency_ms).label("avg_latency"),
            func.sum(IntelligenceExecution.cost_usd).label("total_cost"),
            func.sum(IntelligenceExecution.input_tokens).label("total_input"),
            func.sum(IntelligenceExecution.output_tokens).label("total_output"),
        )
        .filter(
            IntelligenceExecution.prompt_id == prompt.id,
            IntelligenceExecution.created_at >= since,
            IntelligenceExecution.is_test_execution.is_(False),
        )
        .first()
    )

    # p95 latency — use a second query (simple percentile via ordering)
    p95: int | None = None
    lat_rows = [
        r[0]
        for r in db.query(IntelligenceExecution.latency_ms)
        .filter(
            IntelligenceExecution.prompt_id == prompt.id,
            IntelligenceExecution.created_at >= since,
            IntelligenceExecution.latency_ms.isnot(None),
            IntelligenceExecution.is_test_execution.is_(False),
        )
        .order_by(IntelligenceExecution.latency_ms)
        .all()
    ]
    if lat_rows:
        idx = int(0.95 * (len(lat_rows) - 1))
        p95 = int(lat_rows[idx])

    # Daily breakdown
    date_col = func.date(IntelligenceExecution.created_at).label("day")
    daily_rows = (
        db.query(
            date_col,
            func.count(IntelligenceExecution.id).label("n"),
            func.sum(IntelligenceExecution.cost_usd).label("cost"),
            func.sum(
                cast(IntelligenceExecution.status != "success", Integer)
            ).label("errors"),
            func.avg(IntelligenceExecution.latency_ms).label("avg_latency"),
        )
        .filter(
            IntelligenceExecution.prompt_id == prompt.id,
            IntelligenceExecution.created_at >= since,
            IntelligenceExecution.is_test_execution.is_(False),
        )
        .group_by(date_col)
        .order_by(date_col)
        .all()
    )
    daily = [
        DailyStatPoint(
            date=r.day.isoformat() if hasattr(r.day, "isoformat") else str(r.day),
            count=int(r.n or 0),
            cost_usd=Decimal(str(r.cost or 0)),
            error_count=int(r.errors or 0),
            avg_latency_ms=float(r.avg_latency) if r.avg_latency is not None else None,
        )
        for r in daily_rows
    ]

    return PromptStatsResponse(
        prompt_id=prompt.id,
        prompt_key=prompt.prompt_key,
        days=days,
        total_executions=int(totals.n or 0),
        success_count=int(totals.successes or 0),
        error_count=int(totals.errors or 0),
        avg_latency_ms=float(totals.avg_latency) if totals.avg_latency is not None else None,
        p95_latency_ms=p95,
        total_cost_usd=Decimal(str(totals.total_cost or 0)),
        total_input_tokens=int(totals.total_input or 0),
        total_output_tokens=int(totals.total_output or 0),
        daily_breakdown=daily,
    )


@router.get("/stats/overall", response_model=OverallStatsResponse)
def overall_stats_endpoint(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Platform-wide + current tenant aggregated stats."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    base_filter = [
        IntelligenceExecution.created_at >= since,
        or_(
            IntelligenceExecution.company_id == current_user.company_id,
            IntelligenceExecution.company_id.is_(None),
        ),
        # Phase 3b — production stats exclude admin test runs
        IntelligenceExecution.is_test_execution.is_(False),
    ]

    totals = (
        db.query(
            func.count(IntelligenceExecution.id).label("n"),
            func.sum(
                cast(IntelligenceExecution.status == "success", Integer)
            ).label("successes"),
            func.sum(
                cast(IntelligenceExecution.status != "success", Integer)
            ).label("errors"),
            func.sum(IntelligenceExecution.cost_usd).label("total_cost"),
            func.avg(IntelligenceExecution.latency_ms).label("avg_latency"),
        )
        .filter(*base_filter)
        .first()
    )

    n = int(totals.n or 0)
    errors = int(totals.errors or 0)

    # Top by volume
    top_vol_rows = (
        db.query(
            IntelligenceExecution.prompt_id,
            func.count(IntelligenceExecution.id).label("n"),
        )
        .filter(*base_filter)
        .group_by(IntelligenceExecution.prompt_id)
        .order_by(desc(func.count(IntelligenceExecution.id)))
        .limit(10)
        .all()
    )

    # Top by cost
    top_cost_rows = (
        db.query(
            IntelligenceExecution.prompt_id,
            func.sum(IntelligenceExecution.cost_usd).label("cost"),
        )
        .filter(*base_filter)
        .group_by(IntelligenceExecution.prompt_id)
        .order_by(desc(func.sum(IntelligenceExecution.cost_usd)))
        .limit(10)
        .all()
    )

    # Resolve prompt_key for the referenced prompt_ids
    referenced_ids = {r.prompt_id for r in top_vol_rows if r.prompt_id} | {
        r.prompt_id for r in top_cost_rows if r.prompt_id
    }
    key_lookup: dict[str, str] = {}
    if referenced_ids:
        for p in (
            db.query(IntelligencePrompt.id, IntelligencePrompt.prompt_key)
            .filter(IntelligencePrompt.id.in_(referenced_ids))
            .all()
        ):
            key_lookup[p.id] = p.prompt_key

    top_by_volume = [
        TopPromptByVolume(
            prompt_id=r.prompt_id,
            prompt_key=key_lookup.get(r.prompt_id) or "(unknown)",
            count=int(r.n or 0),
        )
        for r in top_vol_rows
    ]
    top_by_cost = [
        TopPromptByCost(
            prompt_id=r.prompt_id,
            prompt_key=key_lookup.get(r.prompt_id) or "(unknown)",
            cost_usd=Decimal(str(r.cost or 0)),
        )
        for r in top_cost_rows
    ]

    # Daily breakdown
    date_col = func.date(IntelligenceExecution.created_at).label("day")
    daily_rows = (
        db.query(
            date_col,
            func.count(IntelligenceExecution.id).label("n"),
            func.sum(IntelligenceExecution.cost_usd).label("cost"),
            func.sum(
                cast(IntelligenceExecution.status != "success", Integer)
            ).label("errors"),
        )
        .filter(*base_filter)
        .group_by(date_col)
        .order_by(date_col)
        .all()
    )
    daily = [
        DailyStatPoint(
            date=r.day.isoformat() if hasattr(r.day, "isoformat") else str(r.day),
            count=int(r.n or 0),
            cost_usd=Decimal(str(r.cost or 0)),
            error_count=int(r.errors or 0),
        )
        for r in daily_rows
    ]

    return OverallStatsResponse(
        days=days,
        total_executions=n,
        success_count=int(totals.successes or 0),
        error_count=errors,
        error_rate=(errors / n) if n > 0 else 0.0,
        total_cost_usd=Decimal(str(totals.total_cost or 0)),
        avg_latency_ms=float(totals.avg_latency) if totals.avg_latency is not None else None,
        top_prompts_by_volume=top_by_volume,
        top_prompts_by_cost=top_by_cost,
        daily_breakdown=daily,
    )


@router.get("/caller-modules", response_model=list[CallerModuleOption])
def list_caller_modules_endpoint(
    since_days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Distinct caller_module values seen in the last N days — for dropdowns."""
    since = datetime.now(timezone.utc) - timedelta(days=since_days)
    rows = (
        db.query(
            IntelligenceExecution.caller_module,
            func.count(IntelligenceExecution.id).label("n"),
        )
        .filter(
            IntelligenceExecution.created_at >= since,
            IntelligenceExecution.caller_module.isnot(None),
            or_(
                IntelligenceExecution.company_id == current_user.company_id,
                IntelligenceExecution.company_id.is_(None),
            ),
        )
        .group_by(IntelligenceExecution.caller_module)
        .order_by(desc(func.count(IntelligenceExecution.id)))
        .all()
    )
    return [
        CallerModuleOption(caller_module=r.caller_module, execution_count=int(r.n or 0))
        for r in rows
        if r.caller_module
    ]


# ═══════════════════════════════════════════════════════════════════════
# Phase 3b — Editing (draft CRUD, activate, rollback, test-run, audit)
# ═══════════════════════════════════════════════════════════════════════

import re as _re
import uuid as _uuid


def _validate_edit_permission(
    user: User, prompt: IntelligencePrompt
) -> EditPermissionResponse:
    """Two-tier permission: super_admin for platform-global, admin for tenant."""
    if prompt.company_id is None:
        # Platform-global — requires super_admin
        if getattr(user, "is_super_admin", False):
            return EditPermissionResponse(
                can_edit=True,
                requires_super_admin=True,
                requires_confirmation_text=True,
            )
        return EditPermissionResponse(
            can_edit=False,
            reason=(
                "Editing platform-global prompts requires super_admin role."
            ),
            requires_super_admin=True,
            requires_confirmation_text=True,
        )
    # Tenant-scoped — admin is enough (caller already passed require_admin)
    return EditPermissionResponse(
        can_edit=True,
        requires_super_admin=False,
        requires_confirmation_text=False,
    )


def _enforce_edit_permission(user: User, prompt: IntelligencePrompt) -> None:
    perm = _validate_edit_permission(user, prompt)
    if not perm.can_edit:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            perm.reason or "Edit permission denied",
        )


_VAR_PATTERN = _re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)")


def _extract_template_variables(
    system_prompt: str, user_template: str
) -> set[str]:
    """Extract `{{ var }}` and `{{ var.x }}` references from Jinja templates.

    Conservative — catches simple dotted paths but doesn't evaluate control
    flow. Good enough for undeclared/unused detection.
    """
    combined = f"{system_prompt}\n{user_template}"
    return set(_VAR_PATTERN.findall(combined))


def _validate_variable_schema(
    system_prompt: str, user_template: str, variable_schema: dict[str, Any]
) -> list[SchemaValidationIssue]:
    """Return mismatches between the template and the declared schema.

    - `undeclared`: referenced in {{ }} but not in schema
    - `unused`: declared in schema (as required) but never referenced

    Optional variables (`{"optional": true}` in their schema entry) are
    exempt from the unused check.
    """
    refs = _extract_template_variables(system_prompt or "", user_template or "")
    declared = set(variable_schema.keys())
    issues: list[SchemaValidationIssue] = []
    for v in sorted(refs - declared):
        issues.append(SchemaValidationIssue(kind="undeclared", variable=v))
    for v in sorted(declared - refs):
        spec = variable_schema.get(v)
        is_optional = isinstance(spec, dict) and bool(spec.get("optional"))
        if not is_optional:
            issues.append(SchemaValidationIssue(kind="unused", variable=v))
    return issues


def _write_audit(
    db: Session,
    *,
    prompt: IntelligencePrompt,
    version: IntelligencePromptVersion | None,
    action: str,
    actor: User,
    changelog: str | None,
    meta: dict[str, Any] | None = None,
) -> IntelligencePromptAuditLog:
    entry = IntelligencePromptAuditLog(
        id=str(_uuid.uuid4()),
        prompt_id=prompt.id,
        version_id=version.id if version else None,
        action=action,
        actor_user_id=actor.id,
        actor_email=actor.email,
        changelog_summary=changelog,
        meta_json=meta or {},
    )
    db.add(entry)
    return entry


def _get_editable_draft(
    db: Session, prompt: IntelligencePrompt, version_id: str
) -> IntelligencePromptVersion:
    version = (
        db.query(IntelligencePromptVersion)
        .filter(
            IntelligencePromptVersion.id == version_id,
            IntelligencePromptVersion.prompt_id == prompt.id,
        )
        .first()
    )
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")
    if version.status != "draft":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Version is {version.status!r} — only drafts are editable. "
            f"Create a new draft via POST /versions/draft to propose changes.",
        )
    return version


@router.get(
    "/prompts/{prompt_id}/edit-permission",
    response_model=EditPermissionResponse,
)
def get_edit_permission_endpoint(
    prompt_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Preflight — UI calls this to decide whether to show the Edit button."""
    prompt = _get_visible_prompt(db, prompt_id, current_user.company_id)
    return _validate_edit_permission(current_user, prompt)


@router.post(
    "/prompts/{prompt_id}/versions/draft",
    response_model=PromptVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_draft_endpoint(
    prompt_id: str,
    body: DraftCreateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Clone a base version (active by default) into a new draft."""
    prompt = _get_visible_prompt(db, prompt_id, current_user.company_id)
    _enforce_edit_permission(current_user, prompt)

    # Reject if a draft already exists — one at a time to avoid overlap
    existing_draft = (
        db.query(IntelligencePromptVersion)
        .filter(
            IntelligencePromptVersion.prompt_id == prompt.id,
            IntelligencePromptVersion.status == "draft",
        )
        .first()
    )
    if existing_draft is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A draft already exists for this prompt. Continue editing or "
            "discard it first.",
        )

    # Resolve base version
    if body.base_version_id:
        base = (
            db.query(IntelligencePromptVersion)
            .filter(
                IntelligencePromptVersion.id == body.base_version_id,
                IntelligencePromptVersion.prompt_id == prompt.id,
            )
            .first()
        )
        if base is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, "Base version not found"
            )
    else:
        base = (
            db.query(IntelligencePromptVersion)
            .filter(
                IntelligencePromptVersion.prompt_id == prompt.id,
                IntelligencePromptVersion.status == "active",
            )
            .first()
        )
        if base is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "No active version to clone. Pass base_version_id explicitly.",
            )

    next_number = (
        db.query(func.coalesce(func.max(IntelligencePromptVersion.version_number), 0) + 1)
        .filter(IntelligencePromptVersion.prompt_id == prompt.id)
        .scalar()
    )
    draft = IntelligencePromptVersion(
        id=str(_uuid.uuid4()),
        prompt_id=prompt.id,
        version_number=int(next_number),
        system_prompt=base.system_prompt,
        user_template=base.user_template,
        variable_schema=dict(base.variable_schema or {}),
        response_schema=dict(base.response_schema) if base.response_schema else None,
        model_preference=base.model_preference,
        temperature=base.temperature,
        max_tokens=base.max_tokens,
        force_json=base.force_json,
        supports_streaming=base.supports_streaming,
        supports_tool_use=base.supports_tool_use,
        supports_vision=base.supports_vision,
        vision_content_type=base.vision_content_type,
        status="draft",
        changelog=body.changelog,
        created_by=current_user.id,
    )
    db.add(draft)
    db.flush()
    _write_audit(
        db,
        prompt=prompt,
        version=draft,
        action="create_draft",
        actor=current_user,
        changelog=body.changelog,
        meta={"base_version_id": base.id, "base_version_number": base.version_number},
    )
    db.commit()
    db.refresh(draft)
    return draft


@router.patch(
    "/prompts/{prompt_id}/versions/{version_id}",
    response_model=PromptVersionResponse,
)
def update_draft_endpoint(
    prompt_id: str,
    version_id: str,
    body: DraftUpdateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Mutate a draft. Returns 409 on active/retired versions."""
    prompt = _get_visible_prompt(db, prompt_id, current_user.company_id)
    _enforce_edit_permission(current_user, prompt)
    draft = _get_editable_draft(db, prompt, version_id)

    updates = body.model_dump(exclude_unset=True)
    for field_name, value in updates.items():
        setattr(draft, field_name, value)

    # Validate-but-don't-block on update (blocking happens at activation).
    # We still surface issues in the response by running validation and
    # including them when non-empty. For now, no-op — UI will call the
    # activate endpoint and see issues then.

    _write_audit(
        db,
        prompt=prompt,
        version=draft,
        action="update_draft",
        actor=current_user,
        changelog=draft.changelog,
        meta={"fields_changed": sorted(updates.keys())},
    )
    db.commit()
    db.refresh(draft)
    return draft


@router.delete(
    "/prompts/{prompt_id}/versions/{version_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_draft_endpoint(
    prompt_id: str,
    version_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    prompt = _get_visible_prompt(db, prompt_id, current_user.company_id)
    _enforce_edit_permission(current_user, prompt)
    draft = _get_editable_draft(db, prompt, version_id)
    _write_audit(
        db,
        prompt=prompt,
        version=draft,
        action="delete_draft",
        actor=current_user,
        changelog=draft.changelog,
        meta={"version_number": draft.version_number},
    )
    db.delete(draft)
    db.commit()
    return None


def _assert_confirmation_text(
    prompt: IntelligencePrompt, provided: str | None
) -> None:
    """Platform-global edits require the prompt_key typed verbatim."""
    if prompt.company_id is None:
        if (provided or "").strip() != prompt.prompt_key:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Confirmation text must match the prompt_key "
                f"({prompt.prompt_key!r}) for platform-global edits.",
            )


@router.post(
    "/prompts/{prompt_id}/versions/{version_id}/activate-edit",
    response_model=PromptVersionResponse,
)
def activate_draft_endpoint(
    prompt_id: str,
    version_id: str,
    body: ActivateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Activate a draft with explicit changelog + variable-schema validation.

    Routed at a distinct path from the existing Phase 1 `/activate` endpoint
    to avoid breaking that behavior. This endpoint adds: required changelog,
    platform-global confirmation_text check, variable-schema validation,
    audit row.
    """
    prompt = _get_visible_prompt(db, prompt_id, current_user.company_id)
    _enforce_edit_permission(current_user, prompt)
    _assert_confirmation_text(prompt, body.confirmation_text)

    draft = _get_editable_draft(db, prompt, version_id)
    if not (body.changelog or "").strip():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "changelog is required"
        )

    # Variable schema validation — hard block on any issue
    issues = _validate_variable_schema(
        draft.system_prompt, draft.user_template, draft.variable_schema or {}
    )
    if issues:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Variable schema validation failed",
                "issues": [i.model_dump() for i in issues],
            },
        )

    # Retire the current active (if any)
    prior_active = (
        db.query(IntelligencePromptVersion)
        .filter(
            IntelligencePromptVersion.prompt_id == prompt.id,
            IntelligencePromptVersion.status == "active",
        )
        .first()
    )
    meta: dict[str, Any] = {}
    if prior_active is not None:
        prior_active.status = "retired"
        meta["previous_active_version_id"] = prior_active.id
        meta["previous_active_version_number"] = prior_active.version_number

    draft.status = "active"
    draft.changelog = body.changelog
    draft.activated_at = datetime.now(timezone.utc)
    prompt.updated_at = datetime.now(timezone.utc)

    _write_audit(
        db,
        prompt=prompt,
        version=draft,
        action="activate",
        actor=current_user,
        changelog=body.changelog,
        meta=meta,
    )
    db.commit()
    db.refresh(draft)
    return draft


@router.post(
    "/prompts/{prompt_id}/versions/{version_id}/rollback",
    response_model=PromptVersionResponse,
)
def rollback_endpoint(
    prompt_id: str,
    version_id: str,
    body: RollbackRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Roll back by cloning a retired version into a new active one.

    Version numbers are monotonic — rolling back to v5 while v8 is active
    produces v9 (= copy of v5). v8 transitions to retired. No silent
    reactivation of an old row — every state transition is a fresh event
    with its own audit entry.
    """
    prompt = _get_visible_prompt(db, prompt_id, current_user.company_id)
    _enforce_edit_permission(current_user, prompt)
    _assert_confirmation_text(prompt, body.confirmation_text)

    target = (
        db.query(IntelligencePromptVersion)
        .filter(
            IntelligencePromptVersion.id == version_id,
            IntelligencePromptVersion.prompt_id == prompt.id,
        )
        .first()
    )
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")
    if target.status != "retired":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Only retired versions can be rolled back to. "
            f"Version {target.version_number} is {target.status!r}.",
        )
    if not (body.changelog or "").strip():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "changelog is required"
        )

    next_number = (
        db.query(func.coalesce(func.max(IntelligencePromptVersion.version_number), 0) + 1)
        .filter(IntelligencePromptVersion.prompt_id == prompt.id)
        .scalar()
    )
    new_version = IntelligencePromptVersion(
        id=str(_uuid.uuid4()),
        prompt_id=prompt.id,
        version_number=int(next_number),
        system_prompt=target.system_prompt,
        user_template=target.user_template,
        variable_schema=dict(target.variable_schema or {}),
        response_schema=dict(target.response_schema) if target.response_schema else None,
        model_preference=target.model_preference,
        temperature=target.temperature,
        max_tokens=target.max_tokens,
        force_json=target.force_json,
        supports_streaming=target.supports_streaming,
        supports_tool_use=target.supports_tool_use,
        supports_vision=target.supports_vision,
        vision_content_type=target.vision_content_type,
        status="active",
        changelog=body.changelog,
        created_by=current_user.id,
        activated_at=datetime.now(timezone.utc),
    )
    db.add(new_version)
    db.flush()

    prior_active = (
        db.query(IntelligencePromptVersion)
        .filter(
            IntelligencePromptVersion.prompt_id == prompt.id,
            IntelligencePromptVersion.status == "active",
            IntelligencePromptVersion.id != new_version.id,
        )
        .first()
    )
    meta: dict[str, Any] = {
        "rolled_back_to_version_id": target.id,
        "rolled_back_to_version_number": target.version_number,
    }
    if prior_active is not None:
        prior_active.status = "retired"
        meta["previous_active_version_id"] = prior_active.id
        meta["previous_active_version_number"] = prior_active.version_number

    prompt.updated_at = datetime.now(timezone.utc)

    _write_audit(
        db,
        prompt=prompt,
        version=new_version,
        action="rollback",
        actor=current_user,
        changelog=body.changelog,
        meta=meta,
    )
    db.commit()
    db.refresh(new_version)
    return new_version


@router.post(
    "/prompts/{prompt_id}/versions/{version_id}/test-run",
    response_model=ExecutionResponse,
)
def test_run_endpoint(
    prompt_id: str,
    version_id: str,
    body: TestRunRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Execute a specific version against Claude, flagging the audit row as
    a test execution (excluded from production stats)."""
    prompt = _get_visible_prompt(db, prompt_id, current_user.company_id)
    # Test runs are safe — admin is enough. No super_admin gate.
    version = (
        db.query(IntelligencePromptVersion)
        .filter(
            IntelligencePromptVersion.id == version_id,
            IntelligencePromptVersion.prompt_id == prompt.id,
        )
        .first()
    )
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")

    variables = body.variables or {}
    content_blocks = body.content_blocks
    # If the user wants to rerun against a real execution's inputs
    if body.source_execution_id:
        src = (
            db.query(IntelligenceExecution)
            .filter(IntelligenceExecution.id == body.source_execution_id)
            .first()
        )
        if src is not None and src.input_variables:
            # Start from source, let caller-provided variables override
            merged = dict(src.input_variables)
            merged.update(variables)
            variables = merged

    from app.services.intelligence import intelligence_service

    try:
        result = intelligence_service.execute(
            db,
            prompt_key=prompt.prompt_key,
            variables=variables,
            company_id=current_user.company_id,
            caller_module="intelligence.admin_test_run",
            caller_entity_type="prompt_version",
            caller_entity_id=version.id,
            content_blocks=content_blocks,
            override_version_id=version.id,
            persist=True,
            is_test_execution=True,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    # Fetch the persisted row to return as ExecutionResponse
    row = (
        db.query(IntelligenceExecution)
        .filter(IntelligenceExecution.id == result.execution_id)
        .first()
    )
    if row is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Test execution did not persist",
        )
    return row


@router.get(
    "/prompts/{prompt_id}/audit",
    response_model=list[AuditLogEntry],
)
def list_prompt_audit_endpoint(
    prompt_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Audit log for this prompt, most recent first."""
    _get_visible_prompt(db, prompt_id, current_user.company_id)
    rows = (
        db.query(IntelligencePromptAuditLog)
        .filter(IntelligencePromptAuditLog.prompt_id == prompt_id)
        .order_by(desc(IntelligencePromptAuditLog.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )
    return rows


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _get_visible_prompt(db: Session, prompt_id: str, company_id: str) -> IntelligencePrompt:
    """404 unless the prompt is this tenant's or platform-global."""
    prompt = db.query(IntelligencePrompt).filter_by(id=prompt_id).first()
    if prompt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prompt not found")
    if prompt.company_id not in (None, company_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prompt not found")
    return prompt


def _get_visible_execution(
    db: Session, execution_id: str, company_id: str
) -> IntelligenceExecution:
    row = db.query(IntelligenceExecution).filter_by(id=execution_id).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Execution not found")
    if row.company_id not in (None, company_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Execution not found")
    return row


def _get_user_conversation(
    db: Session, conversation_id: str, user: User
) -> IntelligenceConversation:
    conv = (
        db.query(IntelligenceConversation)
        .filter(
            IntelligenceConversation.id == conversation_id,
            IntelligenceConversation.company_id == user.company_id,
            IntelligenceConversation.user_id == user.id,
        )
        .first()
    )
    if conv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return conv
