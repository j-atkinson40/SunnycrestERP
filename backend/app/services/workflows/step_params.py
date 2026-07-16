"""Step-param overlays — the engine seam (Tenant Ponder-Editor P1).

Phase 8a shipped the soft-customization substrate (`WorkflowStepParam`:
platform defaults with company_id NULL + tenant overrides with company_id
set) but the execution engine never consumed it — params flowed to the UI
only (`routes/workflows.py::_load_step_params`). This module is the ONE
resolution path all three consumers now share:

  * the ENGINE (`workflow_engine._drive_run`) merges live overlays into
    step config at fire time;
  * the ROUTE (`_load_step_params`) delegates its describe shape here;
  * the PONDER derivation reads the same effective values the fire would
    use — the beat shows what the fire does, by construction.

THE PARITY RULE (the license): only EXPLICITLY-SET values overlay.
`default_value` never merges — the step config as authored IS the platform
default; seeds ship platform rows with current_value NULL. An overlay
exists only when someone deliberately set `current_value` (tenant override
wins over a platform-level live value). A workflow nobody has touched
therefore executes byte-identically to the pre-seam engine — pinned by
`tests/test_step_param_seam.py`.

LOUD ON INVALID: a bad stored value must not silently fall back. Overlay
resolution validates every live value against its declared param_type +
validation; failure raises StepParamValidationError, which the engine
surfaces as a FAILED run (H1 escalation routes it) — the invalid state is
visible, never swallowed.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.workflow import WorkflowStepParam

logger = logging.getLogger(__name__)


class StepParamValidationError(ValueError):
    """A param value that fails its declared type/validation — raised loudly
    at write time (HTTP 400) and at fire time (run fails, H1 escalates)."""


# ── Value validation (shared by the write endpoints + the fire-time merge) ──

_BOOL_TYPES = ("boolean", "toggle")
# user_multi_select holds user UUIDs — the audience grammar's "specific
# people" escape hatch (roles aren't always exact). Existence is checked at
# the WRITE boundary (the admin route, where a db session lives); here the
# shape check keeps fire-time resolution pure.
_LIST_TYPES = ("email_list", "role_multi_select", "user_multi_select")


def _is_template_ref(value: str) -> bool:
    """Params may hold engine variable refs (e.g. '{order.fh_email}')."""
    v = value.strip()
    return v.startswith("{") and v.endswith("}")


def validate_param_value(
    *,
    param_type: str,
    validation: dict | None,
    value: Any,
    label: str = "param",
) -> None:
    """Validate one value against its declared type + validation block.
    Raises StepParamValidationError with a named reason. None is always
    valid (None = 'not set / cleared')."""
    if value is None:
        return
    rules = validation or {}

    if param_type in _BOOL_TYPES:
        if not isinstance(value, bool):
            raise StepParamValidationError(
                f"{label}: expected true/false, got {type(value).__name__}"
            )
        return

    if param_type == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise StepParamValidationError(
                f"{label}: expected a number, got {type(value).__name__}"
            )
        lo, hi = rules.get("min"), rules.get("max")
        if lo is not None and value < lo:
            raise StepParamValidationError(f"{label}: {value} is below the minimum {lo}")
        if hi is not None and value > hi:
            raise StepParamValidationError(f"{label}: {value} is above the maximum {hi}")
        return

    if param_type == "email":
        if not isinstance(value, str) or not value.strip():
            raise StepParamValidationError(f"{label}: expected an email address")
        if "@" not in value and not _is_template_ref(value):
            raise StepParamValidationError(
                f"{label}: {value!r} is not an email address or a {{ref}}"
            )
        return

    if param_type in _LIST_TYPES:
        if not isinstance(value, list) or any(
            not isinstance(x, str) or not x.strip() for x in value
        ):
            raise StepParamValidationError(
                f"{label}: expected a list of non-empty strings"
            )
        if param_type == "email_list":
            for x in value:
                if "@" not in x and not _is_template_ref(x):
                    raise StepParamValidationError(
                        f"{label}: {x!r} is not an email address or a {{ref}}"
                    )
        return

    if param_type == "text":
        if not isinstance(value, str):
            raise StepParamValidationError(
                f"{label}: expected text, got {type(value).__name__}"
            )
        max_len = rules.get("max_length")
        if max_len is not None and len(value) > max_len:
            raise StepParamValidationError(
                f"{label}: {len(value)} chars exceeds the {max_len}-char maximum"
            )
        return

    # An unknown param_type can't be value-checked here — accept with a
    # warning (the declaration is the platform's; rejecting would brick a
    # future type). This is accept-with-visibility, not a silent fallback.
    logger.warning(
        "step-param %s has unvalidatable param_type %r — value accepted unchecked",
        label, param_type,
    )


# ── The one resolution path ─────────────────────────────────────────────────


def _rows(db: Session, workflow_id: str, company_id: str | None):
    platform = (
        db.query(WorkflowStepParam)
        .filter(
            WorkflowStepParam.workflow_id == workflow_id,
            WorkflowStepParam.company_id.is_(None),
        )
        .all()
    )
    overrides: dict[tuple[str, str], WorkflowStepParam] = {}
    if company_id:
        overrides = {
            (p.step_key, p.param_key): p
            for p in db.query(WorkflowStepParam)
            .filter(
                WorkflowStepParam.workflow_id == workflow_id,
                WorkflowStepParam.company_id == company_id,
            )
            .all()
        }
    return platform, overrides


def live_param_overlays(
    db: Session, workflow_id: str, company_id: str | None = None
) -> dict[str, dict[str, Any]]:
    """The fire-time overlay map: {step_key: {param_key: value}} holding ONLY
    explicitly-set live values — tenant current_value first, else a
    platform-level current_value (a deliberate platform-admin act; seeds
    never set it). Undeclared params never appear (the tenant row must have
    a declared platform default); non-configurable params never overlay.

    Every returned value is VALIDATED against its declaration — an invalid
    stored value raises StepParamValidationError (loud; the engine fails the
    run rather than silently falling back)."""
    platform, overrides = _rows(db, workflow_id, company_id)
    out: dict[str, dict[str, Any]] = {}
    for p in platform:
        if not p.is_configurable:
            continue
        override = overrides.get((p.step_key, p.param_key))
        value = None
        if override is not None and override.current_value is not None:
            value = override.current_value
        elif p.current_value is not None:
            value = p.current_value
        if value is None:
            continue
        validate_param_value(
            param_type=p.param_type,
            validation=p.validation,
            value=value,
            label=f"{p.step_key}.{p.param_key}",
        )
        out.setdefault(p.step_key, {})[p.param_key] = value
    return out


def describe_step_params(
    db: Session, workflow_id: str, company_id: str | None = None
) -> list[dict]:
    """The UI/derivation shape — merged platform defaults + live values +
    tenant overrides, one dict per declared param. `effective_value` is what
    fire time would USE for a value-consuming key (tenant override ??
    platform live value ?? default); `live` says whether an explicit value
    would actually overlay the step config at fire time."""
    platform, overrides = _rows(db, workflow_id, company_id)
    out = []
    for p in platform:
        override = overrides.get((p.step_key, p.param_key))
        tenant_value = override.current_value if override else None
        effective = (
            tenant_value
            if tenant_value is not None
            else (p.current_value if p.current_value is not None else p.default_value)
        )
        out.append({
            "step_key": p.step_key,
            "param_key": p.param_key,
            "label": p.label,
            "description": p.description,
            "param_type": p.param_type,
            "default_value": p.default_value,
            "platform_value": p.current_value,
            "current_value": tenant_value,
            "effective_value": effective,
            "live": tenant_value is not None or p.current_value is not None,
            "is_configurable": p.is_configurable,
            "validation": p.validation,
        })
    return out


def merge_overlay(config: dict, overlay: dict[str, Any] | None) -> dict:
    """Shallow-merge a step's live overlay into its config. No overlay →
    the SAME object back (the byte-parity guarantee — nothing is copied,
    nothing reordered, nothing added)."""
    if not overlay:
        return config
    return {**(config or {}), **overlay}
