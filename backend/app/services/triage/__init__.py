"""Triage — platform layer for queue-based decision work.

Phase 5 of the UI/UX arc. Seven-pluggable-component architecture:
Item Display, Action Palette, Context Panels, Embedded Actions,
Flow Controls, Collaboration, Intelligence. Each queue declares
which components it uses via a typed config stored as a vault item
(`item_type="triage_queue_config"`, `metadata_json.triage_queue_config`).

Every queue-based approval/review pattern in the platform
eventually plugs into this engine. Phase 5 proves it with two
queues: `task_triage` + `ss_cert_triage` (the latter migrated from
the bespoke `/social-service-certificates` UI as proof the engine
handles real approval flows without side-effect regressions).

Public surface:

    # orchestration
    start_session, get_session, end_session, next_item,
    apply_action, snooze_item, queue_count, sweep_expired_snoozes
    # registry
    list_queues_for_user, get_config, list_all_configs,
    upsert_platform_config, ITEM_TYPE, METADATA_KEY
    # handlers (for test introspection + extensibility)
    HANDLERS, get_handler, list_handler_keys
    # embedded actions
    run_playwright_action, trigger_workflow_action
    # types
    TriageQueueConfig, ActionConfig, ContextPanelConfig,
    EmbeddedActionConfig, FlowControlsConfig,
    CollaborationConfig, IntelligenceConfig, ItemDisplayConfig,
    SnoozePreset, TriageItemSummary, TriageActionResult,
    TriageSessionSummary, ActionType, ContextPanelType,
    TRIAGE_CONFIG_SCHEMA_VERSION, TriageError, QueueNotFound,
    SessionNotFound, ActionNotAllowed, NoPendingItems, HandlerError
"""

from app.services.triage.action_handlers import (
    HANDLERS,
    HandlerFn,
    get_handler,
    list_handler_keys,
)
# Platform defaults register at import time via side-effect. Import
# BEFORE any registry lookup so `list_all_configs` sees them.
from app.services.triage import platform_defaults as _platform_defaults  # noqa: F401
from app.services.triage.embedded_actions import (
    run_playwright_action,
    trigger_workflow_action,
)
from app.services.triage.engine import (
    apply_action,
    end_session,
    get_session,
    next_item,
    queue_count,
    snooze_item,
    start_session,
    sweep_expired_snoozes,
)
from app.services.triage.registry import (
    ITEM_TYPE,
    METADATA_KEY,
    get_config,
    list_all_configs,
    list_platform_configs,
    list_queues_for_user,
    register_platform_config,
    reset_platform_configs,
    upsert_platform_config,
    upsert_tenant_override,
)
from app.services.triage.types import (
    TRIAGE_CONFIG_SCHEMA_VERSION,
    ActionConfig,
    ActionNotAllowed,
    ActionType,
    CollaborationConfig,
    ContextPanelConfig,
    ContextPanelType,
    EmbeddedActionConfig,
    FlowControlsConfig,
    HandlerError,
    IntelligenceConfig,
    ItemDisplayConfig,
    NoPendingItems,
    QueueNotFound,
    SessionNotFound,
    SnoozePreset,
    TriageActionResult,
    TriageError,
    TriageItemSummary,
    TriageQueueConfig,
    TriageSessionSummary,
)

__all__ = [
    # orchestration
    "start_session",
    "get_session",
    "end_session",
    "next_item",
    "queue_count",
    "apply_action",
    "snooze_item",
    "sweep_expired_snoozes",
    # registry
    "list_queues_for_user",
    "list_all_configs",
    "list_platform_configs",
    "register_platform_config",
    "reset_platform_configs",
    "get_config",
    "upsert_platform_config",
    "upsert_tenant_override",
    "ITEM_TYPE",
    "METADATA_KEY",
    # handlers
    "HANDLERS",
    "HandlerFn",
    "get_handler",
    "list_handler_keys",
    # embedded
    "run_playwright_action",
    "trigger_workflow_action",
    # types
    "TRIAGE_CONFIG_SCHEMA_VERSION",
    "TriageQueueConfig",
    "ActionConfig",
    "ActionType",
    "ContextPanelConfig",
    "ContextPanelType",
    "EmbeddedActionConfig",
    "FlowControlsConfig",
    "CollaborationConfig",
    "IntelligenceConfig",
    "ItemDisplayConfig",
    "SnoozePreset",
    "TriageItemSummary",
    "TriageActionResult",
    "TriageSessionSummary",
    # errors
    "TriageError",
    "QueueNotFound",
    "SessionNotFound",
    "ActionNotAllowed",
    "NoPendingItems",
    "HandlerError",
]
