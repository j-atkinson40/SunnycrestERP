"""Phase 1E family-approval flow — Path B substrate consumption +
ActionTypeDescriptor registration + service-layer flow.

Per §3.26.11.12.19 Personalization Studio canonical category +
§3.26.11.12.21 reviewer-paths canonical (3 outcomes: approve /
request_changes / decline) + §2.5 Portal Extension Pattern (family
portal as canonical Spaces configuration + magic-link substrate per
§3.26.11.9 + Path B platform_action_tokens substrate).

**Pattern A canonical-pattern-establisher discipline** (Q-naming
canonical resolution at session 6 build prompt):
  - ``action_type="personalization_studio_family_approval"`` is
    template_type-agnostic; Step 2 (Urn Vault Personalization Studio)
    REUSES this canonical descriptor rather than registering a new
    ``urn_vault_personalization_studio_family_approval``. Pattern A
    preserves canonical-restraint-discipline per §3.26.7.5.
  - Per-template state propagation lives at the service-layer (canvas
    state commit logic) — the ActionTypeDescriptor commit_handler
    dispatches to per-outcome handlers operating on the canonical
    Generation Focus instance shape; template_type discriminator does
    not branch the action substrate.

**Canonical 3-outcome reviewer-paths per §3.26.11.12.21**:
  - ``approve`` — terminal; commits memorial spec to FH case;
    family_approval_status → "approved"; lifecycle_state → "committed";
    DocumentShare grant integration point flagged (Phase 1F wires).
  - ``request_changes`` — non-terminal; family signals canvas needs
    revision; family_approval_status → "rejected" (canonical model
    enum) with completion_note carrying the requested-changes rationale;
    lifecycle_state reverts to "draft"; FH director adjusts canvas;
    new ``request_family_approval`` call issues fresh ActionToken.
  - ``decline`` — terminal; family rejects this approach entirely;
    family_approval_status → "rejected"; lifecycle_state → "abandoned";
    completion_note required per canonical-rationale discipline.

**Canonical anti-pattern guards explicit at canonical-pattern-
establisher boundary**:
  - §2.5.4 Anti-pattern 13 (net-new portal substrate construction
    rejected) — magic-link issuance via Path B platform_action_tokens
    substrate; no separate ``family_portal_action_tokens`` table.
  - §2.5.4 Anti-pattern 14 (portal-specific feature creep rejected) —
    ActionTypeDescriptor registers against existing central registry;
    per-outcome handlers operate on canonical Generation Focus instance
    + canonical Document substrate; no new persistence shape.
  - §2.5.4 Anti-pattern 15 (portal authentication-substrate fragmentation
    rejected) — token authentication via Path B substrate; family is
    NOT a PortalUser identity; magic-link is sole authentication factor
    per §3.26.11.9.
  - §2.5.4 Anti-pattern 16 (cross-realm privilege bleed rejected) —
    JWT realm "portal" enforcement at portal endpoints (route layer);
    portal token cannot consume tenant-realm endpoints + vice versa.
  - §2.5.4 Anti-pattern 17 (template-declared canonical action
    vocabulary bypassing rejected) — 3 outcomes are canonical; no
    drift. Service-layer rejects unknown outcome via descriptor.outcomes.
  - §2.5.4 Anti-pattern 19 (per-portal authentication mechanism
    proliferation rejected) — magic-link is single canonical mechanism
    for family approval at September scope.
  - §3.26.11.12.16 Anti-pattern 1 (schema substrate guard) — action
    schema lives canonically at this module; service-layer enforces
    canonical shape; FE consumes canonical shape.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.generation_focus_instance import GenerationFocusInstance
from app.services.platform.action_registry import (
    ActionTypeDescriptor,
    register_action_type,
)
from app.services.platform.action_service import (
    ActionAlreadyCompleted,
    ActionError,
    ActionNotFound,
    ActionTokenInvalid,
    consume_action_token,
)
from app.services.platform.action_service import (
    commit_action as _platform_commit_action,
)
from app.services.platform.action_service import (
    issue_action_token as _platform_issue_action_token,
)
from app.services.platform.action_service import (
    lookup_action_token as _platform_lookup_action_token,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Canonical vocabulary — Phase 1E + §3.26.11.12.21 reviewer-paths.
# ─────────────────────────────────────────────────────────────────────

ACTION_TYPE_FAMILY_APPROVAL = "personalization_studio_family_approval"

# Canonical 3-outcome reviewer-paths per §3.26.11.12.21. Pattern A
# template_type-agnostic — Step 2 (Urn Vault Personalization Studio)
# reuses canonical descriptor.
ACTION_OUTCOMES_FAMILY_APPROVAL: tuple[str, ...] = (
    "approve",
    "request_changes",
    "decline",
)

# All 3 are terminal at the action-payload level (the action transitions
# to a non-pending status). request_changes is *operationally*
# non-terminal in that the FH director adjusts canvas + issues a new
# action token; that's a new entry at action_payload['actions'][next_idx].
ACTION_TERMINAL_OUTCOMES: tuple[str, ...] = ACTION_OUTCOMES_FAMILY_APPROVAL

# Per §3.26.11.12.21 + canonical-rationale discipline: request_changes
# + decline require a completion_note rationale (family must explain
# the signal). approve is rationale-optional.
REQUIRES_COMPLETION_NOTE: tuple[str, ...] = ("request_changes", "decline")

# action_status values stored on the action object inside
# generation_focus_instances.action_payload.actions[]
ACTION_STATUSES = (
    "pending",
    "approved",
    "changes_requested",
    "declined",
)

# Canonical primitive_path for magic-link URL composition per
# §3.26.11.9 + Path B build_magic_link_url. Phase 1E uses
# "personalization-studio" — surfaces the Generation Focus template
# domain at the URL boundary; family portal Space rendering routes
# through this path.
MAGIC_LINK_PRIMITIVE_PATH = "personalization-studio"


# ─────────────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────────────


class FamilyApprovalError(ActionError):
    """Base error for family-approval flow."""


class FamilyApprovalInvalidContext(FamilyApprovalError):
    """Raised when authoring_context is not 'funeral_home_with_family'.

    Per §3.26.11.12.19.3 Q3 canonical pairing: family approval is
    canonical FH-vertical pairing only (Mfg-vertical authoring contexts
    don't have family canonical participation).
    """


# ─────────────────────────────────────────────────────────────────────
# Action shape helpers (Phase 1E canonical shape)
# ─────────────────────────────────────────────────────────────────────


def build_family_approval_action(
    *,
    instance: GenerationFocusInstance,
    decedent_name: str | None,
    vault_product_name: str | None,
    fh_director_name: str | None,
    family_email: str,
    fh_case_id: str | None,
) -> dict[str, Any]:
    """Build a canonical personalization_studio_family_approval action.

    Phase 1E canonical shape — the action object embeds the at-the-time-of-
    request snapshot so the family magic-link surface renders authoritative
    context even if the canvas state evolves between request + family
    decision.
    """
    metadata: dict[str, Any] = {
        "decedent_name": decedent_name,
        "vault_product_name": vault_product_name,
        "fh_director_name": fh_director_name,
        "family_email": family_email,
    }
    if fh_case_id:
        metadata["fh_case_id"] = fh_case_id

    return {
        "action_type": ACTION_TYPE_FAMILY_APPROVAL,
        "action_target_type": "generation_focus_instance",
        "action_target_id": instance.id,
        "action_metadata": metadata,
        "action_status": "pending",
        "action_completed_at": None,
        "action_completed_by": None,
        "action_completion_metadata": None,
    }


def get_instance_actions(
    instance: GenerationFocusInstance,
) -> list[dict[str, Any]]:
    """Return the actions list from action_payload, defaulting to []."""
    payload = instance.action_payload or {}
    actions = payload.get("actions")
    if not isinstance(actions, list):
        return []
    return actions


def get_action_at_index(
    instance: GenerationFocusInstance, action_idx: int
) -> dict[str, Any]:
    """Get a specific action by index. Raises ActionNotFound if missing."""
    actions = get_instance_actions(instance)
    if action_idx < 0 or action_idx >= len(actions):
        raise ActionNotFound(
            f"Action index {action_idx} not found on instance {instance.id}"
        )
    return actions[action_idx]


def append_action_to_instance(
    instance: GenerationFocusInstance,
    action: dict[str, Any],
) -> int:
    """Append a new action to instance.action_payload['actions'].

    JSONB columns require explicit replacement of the dict;
    mutating the nested dict in place doesn't trigger SQLAlchemy dirty
    tracking on the parent. Returns the new action_idx.
    """
    payload = dict(instance.action_payload or {})
    actions = list(payload.get("actions") or [])
    new_idx = len(actions)
    actions.append(action)
    payload["actions"] = actions
    instance.action_payload = payload
    return new_idx


# ─────────────────────────────────────────────────────────────────────
# Service layer — request_family_approval + process_family_approval
# ─────────────────────────────────────────────────────────────────────


def request_family_approval(
    db: Session,
    *,
    instance: GenerationFocusInstance,
    family_email: str,
    fh_director_user_id: str | None = None,
    fh_director_name: str | None = None,
    decedent_name: str | None = None,
    vault_product_name: str | None = None,
) -> tuple[int, str]:
    """Issue a family-approval ActionToken + append action to instance.

    **Canonical FH-vertical pairing enforcement** per §3.26.11.12.19.3:
    rejects unless ``instance.authoring_context ==
    "funeral_home_with_family"`` — Mfg-vertical contexts have no family
    participation per canon.

    The caller (route handler) is responsible for dispatching the
    ``email.personalization_studio_family_approval_request`` managed
    email template carrying the magic-link URL composed from the
    returned token.

    Args:
        instance: Generation Focus instance carrying the canvas to be
            approved. Must be in ``authoring_context=
            "funeral_home_with_family"`` per Q3 canonical pairing.
        family_email: Recipient email for the magic-link.
        fh_director_user_id: Canonical actor attribution for audit.
        fh_director_name: Display name for action_metadata snapshot.
        decedent_name: Display name for action_metadata snapshot.
        vault_product_name: Display name for action_metadata snapshot.

    Returns:
        Tuple of ``(action_idx, raw_token)`` — the caller embeds the
        token in the magic-link URL via
        ``build_magic_link_url(primitive_path="personalization-studio")``.

    Raises:
        FamilyApprovalInvalidContext: authoring_context not
            'funeral_home_with_family'.
        FamilyApprovalError: instance lifecycle_state is terminal
            (committed / abandoned).
    """
    if instance.authoring_context != "funeral_home_with_family":
        raise FamilyApprovalInvalidContext(
            f"Family approval is canonical FH-vertical pairing only; "
            f"instance authoring_context={instance.authoring_context!r} "
            f"per §3.26.11.12.19.3."
        )

    if instance.lifecycle_state in ("committed", "abandoned"):
        raise FamilyApprovalError(
            f"Cannot request family approval on instance in terminal "
            f"lifecycle_state={instance.lifecycle_state!r}."
        )

    # Resolve canonical fh_case_id from linked_entity per Q3 canonical
    # pairing (authoring_context=funeral_home_with_family ↔
    # linked_entity_type=fh_case).
    fh_case_id = (
        instance.linked_entity_id
        if instance.linked_entity_type == "fh_case"
        else None
    )

    # Build canonical action shape + append to action_payload.
    action = build_family_approval_action(
        instance=instance,
        decedent_name=decedent_name,
        vault_product_name=vault_product_name,
        fh_director_name=fh_director_name,
        family_email=family_email,
        fh_case_id=fh_case_id,
    )
    action_idx = append_action_to_instance(instance, action)

    # Issue Path B platform_action_tokens row — canonical
    # linked_entity_type='generation_focus_instance' (extended in r77
    # CHECK constraint + r77 PrimitiveType Literal).
    token = _platform_issue_action_token(
        db,
        tenant_id=instance.company_id,
        linked_entity_type="generation_focus_instance",
        linked_entity_id=instance.id,
        action_idx=action_idx,
        action_type=ACTION_TYPE_FAMILY_APPROVAL,
        recipient_email=family_email,
    )

    # Update Generation Focus instance lifecycle metadata.
    now = datetime.now(timezone.utc)
    instance.family_approval_status = "requested"
    instance.family_approval_requested_at = now
    instance.last_active_at = now
    if fh_director_user_id:
        # opened_by can be None for instance opened via auto-pickup;
        # we don't overwrite. But we do stamp last_active for audit.
        pass

    db.flush()

    logger.info(
        "personalization_studio.request_family_approval: instance_id=%s "
        "action_idx=%s fh_director_user_id=%s family_email=%s",
        instance.id,
        action_idx,
        fh_director_user_id,
        family_email,
    )
    return action_idx, token


def process_family_approval_token(
    db: Session,
    *,
    token: str,
) -> tuple[GenerationFocusInstance, dict[str, Any]]:
    """Resolve a family-approval token + return (instance, action).

    Used by the family portal Space rendering at the approval surface
    (canonical GET /portal/personalization-studio/family-approval/{token}).
    Validates token + cross-primitive isolation (rejects tokens whose
    linked_entity_type != 'generation_focus_instance').

    Stamps ``last_clicked_at`` + increments ``click_count`` on the
    token row as a side effect (per Path B canonical click-audit).

    Returns:
        Tuple of ``(instance, action)`` where action is the action dict
        at the token's action_idx.

    Raises:
        ActionTokenInvalid (401): token not found or token's
            linked_entity_type != 'generation_focus_instance'
            (cross-primitive isolation per substrate-consolidation
            discipline).
        ActionTokenAlreadyConsumed (409): token consumed or revoked.
        ActionTokenExpired (410): token expired.
    """
    token_row = _platform_lookup_action_token(db, token=token)

    # Cross-primitive isolation guard — Anti-pattern 16 (cross-realm
    # privilege bleed) at substrate boundary. A calendar token cannot
    # be consumed at the personalization-studio route + vice versa.
    if token_row["linked_entity_type"] != "generation_focus_instance":
        raise ActionTokenInvalid(
            f"Token linked_entity_type "
            f"{token_row['linked_entity_type']!r} is not "
            f"'generation_focus_instance'."
        )

    if token_row["action_type"] != ACTION_TYPE_FAMILY_APPROVAL:
        raise ActionTokenInvalid(
            f"Token action_type {token_row['action_type']!r} is not "
            f"{ACTION_TYPE_FAMILY_APPROVAL!r}."
        )

    instance = (
        db.query(GenerationFocusInstance)
        .filter(GenerationFocusInstance.id == token_row["linked_entity_id"])
        .first()
    )
    if instance is None:
        raise ActionNotFound(
            f"Generation Focus instance "
            f"{token_row['linked_entity_id']!r} not found for token."
        )

    # Tenant isolation — token's tenant_id must match instance's
    # company_id (sanity check; canonically true by construction).
    if instance.company_id != token_row["tenant_id"]:
        raise ActionTokenInvalid(
            "Token tenant_id mismatch with instance company_id."
        )

    action = get_action_at_index(instance, token_row["action_idx"])
    return instance, action


def commit_family_approval_via_token(
    db: Session,
    *,
    token: str,
    outcome: str,
    completion_note: str | None = None,
    actor_email: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    """Commit a family-approval outcome via magic-link token (atomic).

    Canonical magic-link commit path per §3.26.11.9 + Path B
    consume_action_token canonical: token validation + state propagation
    + token consumption happen atomically. Re-commit on a terminal
    action returns 409.

    This is the canonical entry point for the family portal POST
    endpoint (``POST /portal/personalization-studio/family-approval/{token}``).
    """
    instance, action = process_family_approval_token(db, token=token)
    token_row = _platform_lookup_action_token(db, token=token)
    action_idx = token_row["action_idx"]

    # Auth method canonical: magic_link (kill-the-portal pattern per
    # §3.26.11.9 — family is non-Bridgeable user; token IS the
    # authentication factor).
    updated_action = _platform_commit_action(
        db,
        action=action,
        outcome=outcome,
        actor_user_id=None,
        actor_email=actor_email or token_row["recipient_email"],
        auth_method="magic_link",
        completion_note=completion_note,
        ip_address=ip_address,
        user_agent=user_agent,
        # forwarded handler kwargs:
        instance=instance,
        action_idx=action_idx,
    )

    # Atomic token consumption — single-shot per §3.26.15.17 +
    # §3.26.16.18 magic-link discipline.
    consume_action_token(db, token=token)

    return updated_action


# ─────────────────────────────────────────────────────────────────────
# Per-outcome commit handler — registered against central registry.
# Pattern A canonical-pattern-establisher (template_type-agnostic).
# ─────────────────────────────────────────────────────────────────────


def _commit_handler_family_approval(
    db: Session,
    *,
    action: dict[str, Any],
    outcome: str,
    descriptor: ActionTypeDescriptor,
    actor_user_id: str | None,
    actor_email: str | None,
    auth_method: str,
    completion_metadata: dict[str, Any],
    completion_note: str | None,
    ip_address: str | None,
    user_agent: str | None,
    # forwarded by service-layer commit facade:
    instance: GenerationFocusInstance,
    action_idx: int,
    **_: Any,
) -> dict[str, Any]:
    """Family-approval canonical commit handler — 3-outcome dispatch.

    Per §3.26.11.12.21 reviewer-paths canonical:
      - approve → terminal; commits memorial spec to FH case;
        family_approval_status="approved"; lifecycle_state="committed";
        DocumentShare grant integration point (Phase 1F wires).
      - request_changes → action-terminal but operationally non-terminal;
        family_approval_status="rejected" (canonical model enum) with
        completion_note rationale; lifecycle_state reverts to "draft";
        FH director adjusts; new request_family_approval issues fresh
        token at action_payload['actions'][next_idx].
      - decline → terminal; family_approval_status="rejected";
        lifecycle_state="abandoned"; completion_note required.
    """
    # 1. Map outcome → action_status (canonical per ACTION_STATUSES).
    if outcome == "approve":
        new_action_status = "approved"
        new_family_status = "approved"
        new_lifecycle = "committed"
    elif outcome == "request_changes":
        new_action_status = "changes_requested"
        # The canonical CANONICAL_FAMILY_APPROVAL_STATUSES enum is
        # (not_requested, requested, approved, rejected). request_changes
        # is canonically a "rejected" status at the model level + the
        # service layer reverts lifecycle_state to "draft" so the FH
        # director can adjust + re-request.
        new_family_status = "rejected"
        new_lifecycle = "draft"
    elif outcome == "decline":
        new_action_status = "declined"
        new_family_status = "rejected"
        new_lifecycle = "abandoned"
    else:
        raise ActionError(f"Unhandled outcome: {outcome}")

    now = datetime.now(timezone.utc)

    # 2. Update the action object inside action_payload.actions[].
    payload = dict(instance.action_payload or {})
    actions = list(payload.get("actions") or [])
    if action_idx < 0 or action_idx >= len(actions):
        raise ActionNotFound(
            f"Action index {action_idx} not found on instance {instance.id}"
        )
    if actions[action_idx].get("action_status") != "pending":
        raise ActionAlreadyCompleted(
            f"Action already in terminal state "
            f"{actions[action_idx].get('action_status')!r}."
        )

    updated_action = dict(actions[action_idx])
    updated_action["action_status"] = new_action_status
    updated_action["action_completed_at"] = now.isoformat()
    updated_action["action_completed_by"] = actor_user_id or actor_email
    updated_action["action_completion_metadata"] = completion_metadata
    actions[action_idx] = updated_action
    payload["actions"] = actions
    instance.action_payload = payload

    # 3. Generation Focus instance state propagation.
    instance.family_approval_status = new_family_status
    instance.family_approval_decided_at = now
    instance.lifecycle_state = new_lifecycle
    instance.last_active_at = now

    if outcome == "approve":
        # Canonical "memorial spec committed to FH case" semantics.
        # Phase 1E ships the lifecycle transition; the canonical
        # DocumentShare grant for cross-tenant Mfg visibility (so the
        # vault manufacturer fulfilling the order sees the approved
        # canvas) is the Phase 1F integration point per build prompt.
        instance.committed_at = now
        if actor_user_id:
            instance.committed_by_user_id = actor_user_id
        # NOTE: Phase 1F integration point — DocumentShare grant fires
        # here from a hook in family_approval_post_commit_dispatch.

    elif outcome == "decline":
        instance.abandoned_at = now
        if actor_user_id:
            instance.abandoned_by_user_id = actor_user_id

    db.flush()

    logger.info(
        "personalization_studio.family_approval_committed instance_id=%s "
        "action_idx=%s outcome=%s auth_method=%s lifecycle=%s",
        instance.id,
        action_idx,
        outcome,
        auth_method,
        new_lifecycle,
    )
    return updated_action


# ─────────────────────────────────────────────────────────────────────
# Side-effect registration — runs at module import time so the central
# registry is populated when personalization_studio package imports
# this module via its __init__. Idempotent per registry semantics.
# ─────────────────────────────────────────────────────────────────────


register_action_type(
    ActionTypeDescriptor(
        action_type=ACTION_TYPE_FAMILY_APPROVAL,
        primitive="generation_focus",
        target_entity_type="generation_focus_instance",
        outcomes=ACTION_OUTCOMES_FAMILY_APPROVAL,
        terminal_outcomes=ACTION_TERMINAL_OUTCOMES,
        requires_completion_note=REQUIRES_COMPLETION_NOTE,
        commit_handler=_commit_handler_family_approval,
    )
)


# ─────────────────────────────────────────────────────────────────────
# Public exports
# ─────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────
# Phase 1F — Post-commit DocumentShare grant dispatch
#
# Per Phase 1F build prompt + §3.26.11.12.19.4 cross-tenant DocumentShare
# grant timing canonical (Q2 baked: full disclosure per-instance via
# grant): when family approves at family portal Space, FH→Mfg
# DocumentShare grant fires with PTR-level consent gating per Q4 r75
# substrate.
#
# Canonical separation: Phase 1E (`_commit_handler_family_approval`)
# commits canonical lifecycle (active→committed) atomically inside the
# Path B substrate dispatcher; Phase 1F runs AS a post-commit hook
# AFTER the lifecycle transition is durable. Failures at Phase 1F do
# NOT roll back the canonical Phase 1E commit — the family's canonical
# decision stands regardless of cross-tenant share fate. Failures
# surface to FH-tenant admins via canonical V-1d notification + return
# canonical dispatch outcome to the route handler for FE chrome
# consumption.
#
# Anti-pattern guards explicit:
#   - §2.5.4 Anti-pattern 13 (net-new portal substrate construction
#     rejected) — D-6 substrate consumption verbatim; no separate
#     personalization-studio share table.
#   - §3.26.11.12.19.4 full-disclosure-per-instance canon — entire
#     canvas state (decedent name + dates + emblem + font + nameplate
#     + canvas layout) surfaces verbatim via D-6 grant; no field-level
#     masking. Distinct from §3.26.11.10 default cross-tenant Focus
#     masking; Q2 baked Phase 1A.
#   - §2.5.4 Anti-pattern 14 (portal-specific feature creep rejected)
#     — grant fire dispatches via canonical D-6 grant_share +
#     canonical email.personalization_studio_share_granted template
#     (Phase 1E substrate); zero net-new mechanism.
# ─────────────────────────────────────────────────────────────────────


# Canonical PTR relationship_type for FH↔Mfg pair per platform tenant
# relationship canon (matches scripts/seed_fh_demo.py canonical seed
# value). Sunnycrest demo: Hopkins FH (tenant_id) ↔ Sunnycrest Mfg
# (supplier_tenant_id).
CANONICAL_PTR_RELATIONSHIP_TYPE_FH_MANUFACTURER = "fh_manufacturer"


# Canonical r75 column name on PlatformTenantRelationship for
# personalization_studio cross-tenant sharing consent. Mirrors
# ``ptr_consent_service.PERSONALIZATION_STUDIO_CONSENT_COLUMN``.
PTR_CONSENT_COLUMN = "personalization_studio_cross_tenant_sharing_consent"


# Canonical Phase 1E managed email template_key per Phase 1E seed
# (``email.personalization_studio_share_granted``) — Phase 1F consumes.
SHARE_GRANTED_TEMPLATE_KEY = "email.personalization_studio_share_granted"


# Canonical caller_module attribution per D-6 source_module audit
# convention (matches statement_pdf_service / delivery_service
# precedent shape).
CANONICAL_CALLER_MODULE = "personalization_studio.family_approval_post_commit_dispatch"


class PostCommitDispatchOutcome:
    """Canonical dispatch outcome shape — returned to route handler for
    FE chrome consumption. Public-mutable shape (not a frozen dataclass)
    so route handler can serialize directly to JSON response.
    """

    # Outcome codes — canonical 5-state vocabulary at Phase 1F:
    # ``granted``                 — happy path: D-6 grant fired + email dispatched
    # ``ptr_missing``             — no active fh_manufacturer PTR found
    # ``consent_default``         — PTR consent at ``default`` (no flow initiated)
    # ``consent_pending_outbound``— FH requested, Mfg has not accepted
    # ``consent_pending_inbound`` — Mfg requested, FH has not accepted
    OUTCOME_GRANTED = "granted"
    OUTCOME_PTR_MISSING = "ptr_missing"
    OUTCOME_CONSENT_DEFAULT = "consent_default"
    OUTCOME_CONSENT_PENDING_OUTBOUND = "consent_pending_outbound"
    OUTCOME_CONSENT_PENDING_INBOUND = "consent_pending_inbound"

    OUTCOMES_FAILURE: tuple[str, ...] = (
        OUTCOME_PTR_MISSING,
        OUTCOME_CONSENT_DEFAULT,
        OUTCOME_CONSENT_PENDING_OUTBOUND,
        OUTCOME_CONSENT_PENDING_INBOUND,
    )


def _resolve_active_fh_manufacturer_ptr(
    db: Session,
    *,
    fh_tenant_id: str,
):
    """Resolve the canonical active fh_manufacturer PTR for an FH tenant.

    Returns the canonical PTR row when an active fh_manufacturer PTR
    exists with ``tenant_id == fh_tenant_id``; returns None when no
    active PTR exists (canonical no-Mfg-connection state).

    Per canonical PTR shape: ``tenant_id`` = FH side; ``supplier_tenant_id``
    = Mfg side. The canonical fh_manufacturer PTR is the FH-side row
    pointing at the Mfg supplier.

    Per canonical September scope: each FH canonically connects to one
    Mfg via canonical fh_manufacturer PTR. When multiple active rows
    exist (canonical multi-Mfg scenario), this returns the first row
    canonically — multi-Mfg routing canonicalization deferred per
    §3.26.7.5 architectural restraint discipline.
    """
    from app.models.platform_tenant_relationship import (
        PlatformTenantRelationship,
    )

    return (
        db.query(PlatformTenantRelationship)
        .filter(
            PlatformTenantRelationship.tenant_id == fh_tenant_id,
            PlatformTenantRelationship.supplier_tenant_id.is_not(None),
            PlatformTenantRelationship.relationship_type
            == CANONICAL_PTR_RELATIONSHIP_TYPE_FH_MANUFACTURER,
            PlatformTenantRelationship.status == "active",
        )
        .first()
    )


def _resolve_reverse_ptr(
    db: Session,
    *,
    forward_ptr,
):
    """Resolve the canonical reverse PTR row for a given forward PTR.

    Per canonical bilateral PTR pair pattern (Calendar Step 4.1
    precedent + r75 personalization_studio canon): each canonical PTR
    has a reverse-direction row carrying the partner's perspective on
    canonical bilateral consent state. Reverse row matches by
    ``tenant_id == forward.supplier_tenant_id`` +
    ``supplier_tenant_id == forward.tenant_id`` + same relationship_type.

    Returns reverse row when present; returns None when partner has no
    PTR row in this relationship_type (canonical missing-reverse state).
    """
    from app.models.platform_tenant_relationship import (
        PlatformTenantRelationship,
    )

    return (
        db.query(PlatformTenantRelationship)
        .filter(
            PlatformTenantRelationship.tenant_id
            == forward_ptr.supplier_tenant_id,
            PlatformTenantRelationship.supplier_tenant_id
            == forward_ptr.tenant_id,
            PlatformTenantRelationship.relationship_type
            == forward_ptr.relationship_type,
        )
        .first()
    )


def _consent_state_outcome_code(forward_state: str | None) -> str | None:
    """Map canonical r75 4-state consent value → PostCommitDispatchOutcome
    failure code. Returns None when state is canonical ``active`` (happy
    path; canonical grant precondition met).
    """
    if forward_state == "active":
        return None
    if forward_state == "pending_outbound":
        return PostCommitDispatchOutcome.OUTCOME_CONSENT_PENDING_OUTBOUND
    if forward_state == "pending_inbound":
        return PostCommitDispatchOutcome.OUTCOME_CONSENT_PENDING_INBOUND
    # Canonical default — covers ``default`` value AND missing-column
    # defensive NULL (legacy rows pre-r75 read NULL until backfilled;
    # canonical privacy-preserving fallback per §3.26.16.6).
    return PostCommitDispatchOutcome.OUTCOME_CONSENT_DEFAULT


def family_approval_post_commit_dispatch(
    db: Session,
    *,
    instance: GenerationFocusInstance,
) -> dict[str, Any]:
    """Phase 1F post-commit DocumentShare grant dispatch.

    Called AFTER ``commit_family_approval_via_token`` returns successfully
    on canonical ``approve`` outcome. Resolves canonical fh_manufacturer
    PTR + verifies canonical r75 personalization_studio consent state +
    fires canonical D-6 ``grant_share()`` + dispatches canonical
    ``email.personalization_studio_share_granted`` template.

    Canonical separation per §3.26.16.6 + canonical Phase 1E ↔ Phase 1F
    boundary: failures DO NOT roll back the canonical Phase 1E lifecycle
    commit — the family's canonical decision is durable regardless of
    canonical cross-tenant share fate. Failures surface to FH-tenant
    admins via canonical V-1d ``notify_tenant_admins`` + return
    canonical dispatch outcome dict for canonical FE chrome consumption.

    Args:
        instance: canonical Generation Focus instance at canonical
            committed lifecycle_state with canonical ``family_approval_status
            == 'approved'``.

    Returns:
        Canonical dispatch outcome dict with canonical keys:
          - ``outcome``: ``PostCommitDispatchOutcome.OUTCOME_*`` string
          - ``share_id``: canonical DocumentShare.id (granted only) or None
          - ``target_company_id``: canonical Mfg tenant id (when resolved) or None
          - ``target_company_name``: canonical Mfg tenant display name (when resolved) or None
          - ``relationship_id``: canonical FH-side PTR row id (when resolved) or None
          - ``error_detail``: canonical operator-friendly error copy (failure modes only) or None

    Pre-conditions (caller-enforced):
      - ``instance.lifecycle_state == 'committed'``
      - ``instance.family_approval_status == 'approved'``
      - ``instance.authoring_context == 'funeral_home_with_family'``

    The function does NOT raise on canonical failure modes — returns
    canonical outcome dict instead. Unexpected exceptions (DB errors,
    R2 failures, etc.) propagate per canonical fail-loud discipline.
    """
    from app.models.canonical_document import Document
    from app.models.company import Company
    from app.services.documents import document_sharing_service

    # Defensive precondition checks — guard at canonical post-commit
    # boundary. Caller (route handler) already ensures these via the
    # commit flow; this is canonical defense-in-depth.
    if instance.authoring_context != "funeral_home_with_family":
        raise FamilyApprovalInvalidContext(
            f"Post-commit dispatch canonical FH-vertical only; "
            f"instance authoring_context={instance.authoring_context!r}."
        )
    if instance.family_approval_status != "approved":
        raise FamilyApprovalError(
            f"Post-commit dispatch requires family_approval_status="
            f"'approved'; got {instance.family_approval_status!r}."
        )
    if instance.document_id is None:
        raise FamilyApprovalError(
            f"Instance {instance.id!r} has no canonical Document "
            f"substrate; cannot fire DocumentShare grant."
        )

    fh_tenant_id = instance.company_id

    # ─── Step 1: resolve canonical fh_manufacturer PTR ──────────────
    forward_ptr = _resolve_active_fh_manufacturer_ptr(
        db, fh_tenant_id=fh_tenant_id
    )
    if forward_ptr is None:
        outcome_dict = {
            "outcome": PostCommitDispatchOutcome.OUTCOME_PTR_MISSING,
            "share_id": None,
            "target_company_id": None,
            "target_company_name": None,
            "relationship_id": None,
            "error_detail": (
                "No active manufacturer connection found. The funeral "
                "home must be connected to a manufacturer via canonical "
                "platform tenant relationship before approved memorial "
                "designs can be shared for fulfillment."
            ),
        }
        _notify_fh_admins_dispatch_failure(
            db,
            instance=instance,
            outcome_dict=outcome_dict,
        )
        logger.warning(
            "personalization_studio.post_commit_dispatch ptr_missing "
            "instance_id=%s fh_tenant_id=%s",
            instance.id,
            fh_tenant_id,
        )
        return outcome_dict

    target_company_id = forward_ptr.supplier_tenant_id
    target_company = (
        db.query(Company).filter(Company.id == target_company_id).first()
    )
    target_company_name = (
        target_company.name if target_company is not None else None
    )

    # ─── Step 2: verify canonical r75 PTR consent state ─────────────
    forward_state = getattr(forward_ptr, PTR_CONSENT_COLUMN, None)
    consent_failure_code = _consent_state_outcome_code(forward_state)

    if consent_failure_code is not None:
        outcome_dict = {
            "outcome": consent_failure_code,
            "share_id": None,
            "target_company_id": target_company_id,
            "target_company_name": target_company_name,
            "relationship_id": forward_ptr.id,
            "error_detail": _consent_failure_copy(
                consent_failure_code,
                target_company_name=target_company_name,
            ),
        }
        _notify_fh_admins_dispatch_failure(
            db,
            instance=instance,
            outcome_dict=outcome_dict,
        )
        logger.warning(
            "personalization_studio.post_commit_dispatch consent_state="
            "%s instance_id=%s relationship_id=%s",
            forward_state,
            instance.id,
            forward_ptr.id,
        )
        return outcome_dict

    # ─── Step 3: fire canonical D-6 grant_share ────────────────────
    document = (
        db.query(Document).filter(Document.id == instance.document_id).first()
    )
    if document is None:
        raise FamilyApprovalError(
            f"Canonical Document {instance.document_id!r} not found "
            f"for instance {instance.id!r}; canonical invariant violated."
        )

    fh_director_user_id = (
        instance.committed_by_user_id or instance.opened_by_user_id
    )

    try:
        share = document_sharing_service.grant_share(
            db,
            document=document,
            target_company_id=target_company_id,
            granted_by_user_id=fh_director_user_id,
            reason=(
                f"Memorial design approved by family — "
                f"shared for fulfillment"
            ),
            source_module=CANONICAL_CALLER_MODULE,
            enforce_relationship=True,
        )
    except document_sharing_service.SharingError as exc:
        # Canonical existing-active-share (409) — idempotent: surface
        # the canonical existing share without erroring at canonical
        # post-commit boundary.
        if getattr(exc, "http_status", None) == 409:
            existing_share = document_sharing_service.get_active_share(
                db,
                document_id=document.id,
                target_company_id=target_company_id,
            )
            if existing_share is not None:
                return {
                    "outcome": PostCommitDispatchOutcome.OUTCOME_GRANTED,
                    "share_id": existing_share.id,
                    "target_company_id": target_company_id,
                    "target_company_name": target_company_name,
                    "relationship_id": forward_ptr.id,
                    "error_detail": None,
                }
        raise

    # ─── Step 4: dispatch canonical share_granted email ────────────
    _dispatch_share_granted_email(
        db,
        instance=instance,
        share=share,
        document=document,
        target_company_id=target_company_id,
        target_company_name=target_company_name,
    )

    logger.info(
        "personalization_studio.post_commit_dispatch granted "
        "instance_id=%s document_id=%s share_id=%s "
        "target_company_id=%s",
        instance.id,
        document.id,
        share.id,
        target_company_id,
    )

    return {
        "outcome": PostCommitDispatchOutcome.OUTCOME_GRANTED,
        "share_id": share.id,
        "target_company_id": target_company_id,
        "target_company_name": target_company_name,
        "relationship_id": forward_ptr.id,
        "error_detail": None,
    }


def _consent_failure_copy(
    outcome_code: str,
    *,
    target_company_name: str | None,
) -> str:
    """Canonical operator-friendly error copy per failure mode.

    Surfaced to FH-tenant admins via canonical V-1d notification +
    returned in canonical dispatch outcome dict for canonical FE
    chrome consumption.
    """
    mfg_name = target_company_name or "the connected manufacturer"
    if outcome_code == PostCommitDispatchOutcome.OUTCOME_CONSENT_DEFAULT:
        return (
            f"Cross-tenant Personalization Studio sharing consent has "
            f"not been requested between this funeral home and "
            f"{mfg_name}. Request consent before approved memorial "
            f"designs can be shared for fulfillment."
        )
    if outcome_code == PostCommitDispatchOutcome.OUTCOME_CONSENT_PENDING_OUTBOUND:
        return (
            f"Awaiting {mfg_name} acceptance of the cross-tenant "
            f"Personalization Studio sharing consent request. The "
            f"approved memorial design cannot be shared until the "
            f"manufacturer accepts."
        )
    if outcome_code == PostCommitDispatchOutcome.OUTCOME_CONSENT_PENDING_INBOUND:
        return (
            f"{mfg_name} has requested cross-tenant Personalization "
            f"Studio sharing consent. Accept the request before "
            f"approved memorial designs can be shared for fulfillment."
        )
    return ""


def _notify_fh_admins_dispatch_failure(
    db: Session,
    *,
    instance: GenerationFocusInstance,
    outcome_dict: dict[str, Any],
) -> None:
    """Canonical V-1d notification fan-out to FH-tenant admins on
    canonical Phase 1F dispatch failure.

    Canonical category ``personalization_studio_share_failed`` per
    canonical V-1d notification convention. Best-effort — wrapped so
    notification failures never bubble through canonical dispatch path
    per V-1d discipline (mirrors document_sharing_service grant_share
    notification fan-out pattern).
    """
    try:
        from app.services import notification_service

        notification_service.notify_tenant_admins(
            db,
            company_id=instance.company_id,
            title=(
                "Approved memorial design could not be shared with "
                "manufacturer"
            ),
            message=outcome_dict.get("error_detail")
            or "Cross-tenant share dispatch failed.",
            type="warning",
            category="personalization_studio_share_failed",
            link=(
                f"/personalization-studio/instances/{instance.id}"
            ),
            source_reference_type="generation_focus_instance",
            source_reference_id=instance.id,
        )
    except Exception:  # noqa: BLE001 — best-effort notification
        logger.exception(
            "personalization_studio.post_commit_dispatch notification "
            "fan-out failed instance_id=%s",
            instance.id,
        )


def _dispatch_share_granted_email(
    db: Session,
    *,
    instance: GenerationFocusInstance,
    share,
    document,
    target_company_id: str,
    target_company_name: str | None,
) -> None:
    """Dispatch canonical ``email.personalization_studio_share_granted``
    template to canonical Mfg-tenant admin recipients.

    Per canonical Phase 1E template seed (Phase 1F substrate-consumes
    Phase 1E-shipped template). Best-effort per canonical email
    dispatch discipline (Step 4.1 contract): email failure NEVER
    blocks canonical D-6 grant fire — canonical share row is durable
    regardless of canonical email dispatch outcome.
    """
    try:
        from app.models import User
        from app.models.company import Company
        from app.models.role import Role
        from app.services.delivery import delivery_service

        # Resolve canonical FH-tenant display name for canonical email
        # template variable owner_tenant_name.
        fh_company = (
            db.query(Company).filter(Company.id == instance.company_id).first()
        )
        fh_tenant_name = fh_company.name if fh_company is not None else "the funeral home"

        # Canonical decedent name from canonical instance action_payload
        # snapshot (Phase 1E request_family_approval canonical attribution
        # captures decedent_name in action metadata).
        decedent_name: str | None = None
        actions = get_instance_actions(instance)
        if actions:
            metadata = actions[-1].get("action_metadata") or {}
            decedent_name = metadata.get("decedent_name")

        # Per canonical V-1d admin fan-out pattern: one
        # DocumentDelivery row per Mfg-tenant admin (preserves per-admin
        # audit + bounce attribution per Step 5.1 canonical).
        mfg_admins = (
            db.query(User)
            .join(Role, User.role_id == Role.id)
            .filter(
                User.company_id == target_company_id,
                User.is_active.is_(True),
                Role.slug == "admin",
            )
            .all()
        )

        canvas_url = f"/personalization-studio/from-share/{share.id}"

        for admin in mfg_admins:
            recipient_first_name = (
                (admin.first_name or "").strip() or "there"
            )
            try:
                delivery_service.send_email_with_template(
                    db,
                    company_id=target_company_id,
                    to_email=admin.email,
                    to_name=(
                        f"{(admin.first_name or '').strip()} "
                        f"{(admin.last_name or '').strip()}"
                    ).strip()
                    or admin.email,
                    template_key=SHARE_GRANTED_TEMPLATE_KEY,
                    template_context={
                        "owner_tenant_name": fh_tenant_name,
                        "partner_tenant_name": (
                            target_company_name or "your organization"
                        ),
                        "recipient_first_name": recipient_first_name,
                        "decedent_name": decedent_name or "the decedent",
                        "canvas_url": canvas_url,
                    },
                    caller_module=(
                        "personalization_studio."
                        "family_approval_post_commit_dispatch"
                    ),
                    metadata={
                        "instance_id": instance.id,
                        "share_id": share.id,
                        "phase": "phase_1f_share_granted",
                    },
                )
            except Exception:  # noqa: BLE001 — per-recipient best-effort
                logger.exception(
                    "personalization_studio.post_commit_dispatch email "
                    "send failed share_id=%s admin_email=%s",
                    share.id,
                    admin.email,
                )
    except Exception:  # noqa: BLE001 — outer best-effort
        logger.exception(
            "personalization_studio.post_commit_dispatch email "
            "dispatch outer failure share_id=%s",
            share.id,
        )


__all__ = [
    # Vocabulary
    "ACTION_TYPE_FAMILY_APPROVAL",
    "ACTION_OUTCOMES_FAMILY_APPROVAL",
    "ACTION_TERMINAL_OUTCOMES",
    "ACTION_STATUSES",
    "REQUIRES_COMPLETION_NOTE",
    "MAGIC_LINK_PRIMITIVE_PATH",
    "CANONICAL_PTR_RELATIONSHIP_TYPE_FH_MANUFACTURER",
    "PTR_CONSENT_COLUMN",
    "SHARE_GRANTED_TEMPLATE_KEY",
    "CANONICAL_CALLER_MODULE",
    # Action shape helpers
    "build_family_approval_action",
    "get_instance_actions",
    "get_action_at_index",
    "append_action_to_instance",
    # Service layer
    "request_family_approval",
    "process_family_approval_token",
    "commit_family_approval_via_token",
    # Phase 1F post-commit dispatch
    "family_approval_post_commit_dispatch",
    "PostCommitDispatchOutcome",
    # Errors
    "FamilyApprovalError",
    "FamilyApprovalInvalidContext",
]
