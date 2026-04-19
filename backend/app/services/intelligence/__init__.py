"""Bridgeable Intelligence — unified AI layer.

The primary entry point is intelligence_service.execute(). Every AI call in the
platform should flow through it. Callers hand off a prompt_key + variables +
caller linkage; the service loads the active prompt version (with tenant
override support), renders it, resolves the model, calls the provider with
fallback, persists an execution row, and returns the result.

All callers are migrated in Phase 2. Phase 1 just ships the backbone.
"""

from app.services.intelligence import chat_service, extraction_service
from app.services.intelligence.cost_service import compute_cost
from app.services.intelligence.experiment_service import (
    assign_variant,
    collect_daily_breakdown as experiment_daily_breakdown,
    collect_p95_per_variant as experiment_p95,
    conclude as conclude_experiment,
    find_running_for_prompt,
    is_ready_to_conclude,
    start as start_experiment,
    stop as stop_experiment,
)
from app.services.intelligence.intelligence_service import (
    IntelligenceError,
    IntelligenceResult,
    MissingVariableError,
    PromptNotFoundError,
    execute,
)
from app.services.intelligence.model_router import (
    ModelRouteNotFoundError,
    resolve_model,
    route_with_fallback,
)
from app.services.intelligence.prompt_registry import (
    PromptVersionNotReadyError,
    activate_version,
    create_version,
    get_active_version,
    list_prompts,
    retire_version,
)
from app.services.intelligence.prompt_renderer import (
    compute_input_hash,
    render,
    validate_variables,
)

__all__ = [
    "IntelligenceError",
    "IntelligenceResult",
    "MissingVariableError",
    "PromptNotFoundError",
    "PromptVersionNotReadyError",
    "ModelRouteNotFoundError",
    "activate_version",
    "assign_variant",
    "compute_cost",
    "compute_input_hash",
    "conclude_experiment",
    "create_version",
    "execute",
    "get_active_version",
    "is_ready_to_conclude",
    "list_prompts",
    "render",
    "resolve_model",
    "retire_version",
    "route_with_fallback",
    "validate_variables",
]
