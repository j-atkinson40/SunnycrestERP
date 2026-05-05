"""Workflow template service — Phase 4 of the Admin Visual Editor.
Authoring + inheritance resolution + tenant fork lifecycle.
"""

from app.services.workflow_templates.canvas_validator import (
    CanvasValidationError,
    VALID_NODE_TYPES,
    validate_canvas_state,
)
from app.services.workflow_templates.template_service import (
    ForkNotFound,
    InvalidTemplateShape,
    TemplateNotFound,
    TemplateScopeMismatch,
    WorkflowTemplateError,
    accept_merge,
    create_template,
    fork_for_tenant,
    get_dependent_forks,
    get_fork,
    get_pending_merges,
    get_template,
    list_forks,
    list_templates,
    mark_pending_merge,
    reject_merge,
    resolve_workflow,
    update_template,
)

__all__ = [
    # Validator
    "CanvasValidationError",
    "VALID_NODE_TYPES",
    "validate_canvas_state",
    # Errors
    "WorkflowTemplateError",
    "TemplateNotFound",
    "TemplateScopeMismatch",
    "InvalidTemplateShape",
    "ForkNotFound",
    # Template CRUD
    "list_templates",
    "get_template",
    "create_template",
    "update_template",
    "get_dependent_forks",
    # Fork lifecycle
    "fork_for_tenant",
    "list_forks",
    "get_fork",
    "mark_pending_merge",
    "accept_merge",
    "reject_merge",
    "get_pending_merges",
    # Resolution
    "resolve_workflow",
]
