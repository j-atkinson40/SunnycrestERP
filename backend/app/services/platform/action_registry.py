"""Platform action_type registry — substrate consolidation.

Per Calendar Step 1 discovery Q1 confirmation + §3.26.16.17 Phase B
Q13 refinement direction note: a single canonical registry of every
action_type that funnels through ``platform_action_tokens``. Email
ships ``quote_approval`` at September scope; Calendar Step 4 will
register 5 entries (§3.26.16.17); SMS Step 4 + Phone Step 4 will
register their respective 5 entries each (§3.26.17.18 + §3.26.18.20).

**Pattern parallels** (canon precedent):
  - ``app.services.triage.platform_defaults`` — side-effect-imported
    on package init; calls ``register_platform_config`` for each
    canonical queue
  - ``app.services.command_bar.registry`` — singleton ActionRegistryEntry
    dict seeded at module load
  - ``WIDGET_DEFINITIONS`` in ``app.services.widgets.widget_registry`` —
    in-code constants with cross-vertical filtering

**Each primitive's package init side-effect-imports its registrations**
so the registry is populated by the first import. Email package init
imports ``email_action_service`` which calls ``register_action_type``
for ``quote_approval``. Future Calendar Step 4 will follow the same
pattern.

**Validation discipline**: ``ACTION_TYPE_REGISTRY`` IS the validation
surface. Replaces the per-primitive ``ACTION_TYPES`` tuple check with
a central registry lookup. NO database CHECK constraint on
``action_type`` — that would require a migration every time a primitive
registers a new action_type (anti-pattern). The DB-level CHECK is on
``linked_entity_type`` only (4-value enum locked at r70).

**Cross-primitive isolation**: each ActionTypeDescriptor declares its
``primitive`` field; ``commit_action`` validates that the supplied
``linked_entity_type`` matches an expected value for the action_type's
primitive (e.g. ``quote_approval`` only valid against
``linked_entity_type='email_message'``).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Canonical primitive vocabulary — locked by r70 + r77 CHECK constraint.
#
# r70 shipped the canonical 4-primitive enum (email/calendar/sms/phone).
# r77 extended canonical enum with ``generation_focus`` per Phase 1E
# Personalization Studio family approval — Generation Focus is
# canonically the 5th primitive class consuming Path B substrate.
# ─────────────────────────────────────────────────────────────────────

PrimitiveType = Literal["email", "calendar", "sms", "phone", "generation_focus"]

# Canonical mapping from primitive → expected linked_entity_type values.
# Driven by canonical action_target_type semantics per §3.26.15.17 +
# §3.26.16.17 + §3.26.17.18 + §3.26.18.20 + Phase 1E
# (§3.26.11.12.19.5 family approval canonical site). Each primitive's
# tokens always link to that primitive's canonical entity.
PRIMITIVE_LINKED_ENTITY_TYPES: dict[PrimitiveType, str] = {
    "email": "email_message",
    "calendar": "calendar_event",
    "sms": "sms_message",
    "phone": "phone_call",
    "generation_focus": "generation_focus_instance",
}


# ─────────────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────────────


class ActionRegistryError(Exception):
    """Raised when registry invariants are violated."""


# ─────────────────────────────────────────────────────────────────────
# ActionTypeDescriptor — canonical registry shape
# ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ActionTypeDescriptor:
    """Describes a single action_type that flows through platform_action_tokens.

    Attributes:
        action_type: Canonical action_type string (e.g. "quote_approval").
            Unique across the platform — registry enforces no duplicates.
        primitive: Owner primitive ("email" | "calendar" | "sms" | "phone").
            Drives the linked_entity_type compatibility check at commit.
        target_entity_type: action_target_type per canonical action shape
            (§3.26.15.17 + §3.26.16.17). E.g. "quote", "fh_case",
            "sales_order", "cross_tenant_event", "calendar_event".
        outcomes: Tuple of legal outcomes for this action_type. Driven
            by canonical status flow per §3.26.15.17 (e.g. "approve",
            "reject", "request_changes" for quote_approval; "accept",
            "decline", "counter_propose" for calendar action_types).
        terminal_outcomes: Subset of outcomes that put the action in a
            terminal state. "request_changes" on quote_approval is
            terminal (action_status="changes_requested"); calendar's
            "counter_propose" is terminal at the original action's
            level but spawns a new action.
        requires_completion_note: Subset of outcomes that require a
            completion_note at commit time. e.g. ("request_changes",)
            for quote_approval — note carries the requested-changes
            text. Empty default — most actions don't require notes.
        commit_handler: Callable invoked by ``commit_action`` after
            validation + state transition. Signature:
                ``handler(db, *, action, outcome, completion_metadata, ...) -> None``
            Performs primitive-specific state propagation
            (e.g. quote_approval → Quote.status update; service_date_acceptance
            → FHCase.service_date set + cross-tenant pairing finalize).
            Receives the updated action dict + the resolved outcome +
            completion_metadata captured from the actor at commit time.

    Per Calendar Step 1 discovery Q1 confirmation: this central registry
    is the architectural deliverable that Calendar Step 4 + SMS Step 4
    + Phone Step 4 inherit. Building it now amortizes ~6+ hours across
    three downstream Step 4 arcs.
    """

    action_type: str
    primitive: PrimitiveType
    target_entity_type: str
    outcomes: tuple[str, ...]
    terminal_outcomes: tuple[str, ...]
    commit_handler: Callable[..., Any]
    requires_completion_note: tuple[str, ...] = ()


# ─────────────────────────────────────────────────────────────────────
# Module-level singleton — populated via side-effect-import discipline.
# ─────────────────────────────────────────────────────────────────────


_REGISTRY: dict[str, ActionTypeDescriptor] = {}


def register_action_type(descriptor: ActionTypeDescriptor) -> None:
    """Register an ActionTypeDescriptor at module load time.

    Idempotent — re-registering the same action_type with an identical
    descriptor is a no-op (matches triage registry precedent for
    development reload cycles + test fixture re-imports). Re-registering
    with a different descriptor logs a WARNING + replaces (last-wins
    semantics like the triage registry); production paths should never
    hit this branch since descriptors are module-level constants.
    """
    existing = _REGISTRY.get(descriptor.action_type)
    if existing is not None and existing != descriptor:
        logger.warning(
            "register_action_type: replacing existing descriptor for "
            "action_type=%s (existing.primitive=%s; new.primitive=%s)",
            descriptor.action_type,
            existing.primitive,
            descriptor.primitive,
        )
    _REGISTRY[descriptor.action_type] = descriptor


def get_action_type(action_type: str) -> ActionTypeDescriptor:
    """Look up a registered ActionTypeDescriptor by action_type string.

    Raises ``ActionRegistryError`` (translated to HTTP 400 by the
    platform action service) when the action_type is not registered.
    """
    descriptor = _REGISTRY.get(action_type)
    if descriptor is None:
        raise ActionRegistryError(
            f"Unknown action_type: {action_type!r}. Registered action_types: "
            f"{sorted(_REGISTRY.keys())}"
        )
    return descriptor


def list_action_types_for_primitive(
    primitive: PrimitiveType,
) -> list[ActionTypeDescriptor]:
    """Return all action_types registered against the given primitive."""
    return [
        d for d in _REGISTRY.values() if d.primitive == primitive
    ]


def list_all_action_types() -> list[ActionTypeDescriptor]:
    """Return every registered ActionTypeDescriptor (debugging + admin)."""
    return list(_REGISTRY.values())


def is_registered(action_type: str) -> bool:
    """Cheap existence check without raising."""
    return action_type in _REGISTRY


def expected_linked_entity_type(action_type: str) -> str:
    """Resolve the canonical linked_entity_type for a given action_type.

    Used by ``platform_action_service.commit_action`` to validate that
    the token's linked_entity_type matches the expected value for the
    action_type's owning primitive.
    """
    descriptor = get_action_type(action_type)
    return PRIMITIVE_LINKED_ENTITY_TYPES[descriptor.primitive]


# ─────────────────────────────────────────────────────────────────────
# Test-only reset hook
# ─────────────────────────────────────────────────────────────────────


def _reset_registry_for_tests() -> None:
    """Clear the registry. For test isolation only.

    Production callers MUST NOT use this. Tests that register synthetic
    descriptors should snapshot + restore via the registry's dict
    rather than fully reset (preserves Email's quote_approval baseline
    for the rest of the test session).
    """
    _REGISTRY.clear()
