"""Fragment registry — code-declared types, config-enabled per tenant.

⚠️ THE SPLIT, AND WHY IT IS THIS WAY. Fragment TYPES are code-declared: a
condition is a real query, and queries live in code. Per-tenant and per-role
ENABLEMENT is configuration. The dispatch called this the expected shape and
instructed a STOP if the codebase contradicted it. It does not — the shape was
verified against three existing registries before this module was written:

  • `command_bar/registry.py` — module-level dict, lazy `_ensure_seeded()`,
    `reset_registry()` test escape hatch, gates stored as opaque strings and
    applied at query time by `retrieval.py:241-249`.
  • `vault/hub_registry.py` — the pattern command_bar's docstring says it
    mirrors.
  • `triage/platform_defaults.py` + `triage/registry.py::list_queues_for_user`
    — platform defaults declared in code, per-tenant config stored as data in
    `vault_items.metadata_json.triage_queue_config`, gates applied at read.

This module follows that lifecycle exactly. Registration is the code half;
`emission.emit_for_user` applies the audience gate at read time, which is the
config half's evaluation point.

⚠️ REGISTRATION IS WHERE THE FOUR DECLARATIONS ARE ENFORCED. A fragment type
missing any of them raises `FragmentDeclarationError` at import, not at render.
The enforcement is deliberately loud and early: a fragment that reaches a user
without a declared audience is a permission leak, and one without a declared
end transition is a prompt that can never leave the note.
"""

from __future__ import annotations

import logging
from typing import Mapping

from app.services.fragments.types import (
    Audience,
    FragmentDeclaration,
    FragmentDeclarationError,
)

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, FragmentDeclaration] = {}
_SEEDED = False

#: Surfaces a fragment may open. Kept as a tuple rather than re-deriving from
#: the Literal so the failure mode on a typo is a registration error naming the
#: valid set, not a silent pass.
_VALID_TARGET_SURFACES = ("peek", "focus", "window")
_VALID_KINDS = ("prompt", "non_prompt")


def _validate(decl: FragmentDeclaration) -> None:
    """Enforce the four declarations. Raises rather than warning.

    Each check names which of the four failed, because the whole point of the
    contract is that "underspecified" is a specific, reportable condition
    rather than a judgement call.
    """
    if not decl.fragment_id or not decl.fragment_id.strip():
        raise FragmentDeclarationError("fragment_id is required and non-empty.")

    if decl.kind not in _VALID_KINDS:
        raise FragmentDeclarationError(
            f"{decl.fragment_id}: kind must be one of {_VALID_KINDS}, "
            f"got {decl.kind!r}."
        )

    # (1) AUDIENCE — must be declared. `Audience.any_authenticated()` is a
    # valid, explicit answer; `None` is not an answer at all.
    if not isinstance(decl.audience, Audience):
        raise FragmentDeclarationError(
            f"{decl.fragment_id}: declaration (1) AUDIENCE is missing. Declare "
            "an Audience — use Audience.any_authenticated() to state "
            "explicitly that any authenticated tenant user sees it."
        )

    # (2) CONDITION — must be callable.
    if not callable(decl.condition):
        raise FragmentDeclarationError(
            f"{decl.fragment_id}: declaration (2) CONDITION is missing or not "
            "callable. A condition is (db, *, user) -> Sequence[FragmentInstance]."
        )

    # (3) TARGET — the type-level half. The scope half is enforced per-instance
    # at emission, because scope varies by instance and a type-level check
    # cannot see it.
    if decl.target_surface not in _VALID_TARGET_SURFACES:
        raise FragmentDeclarationError(
            f"{decl.fragment_id}: declaration (3) TARGET is invalid — "
            f"target_surface must be one of {_VALID_TARGET_SURFACES}, got "
            f"{decl.target_surface!r}."
        )
    if not decl.target_key or not decl.target_key.strip():
        raise FragmentDeclarationError(
            f"{decl.fragment_id}: declaration (3) TARGET is incomplete — "
            "target_key names what is opened and is required."
        )

    # (4) END TRANSITION — required iff prompt, forbidden otherwise.
    if decl.kind == "prompt" and decl.end_transition is None:
        raise FragmentDeclarationError(
            f"{decl.fragment_id}: declaration (4) END TRANSITION is missing. A "
            "prompt must declare how it resolves — it has no dismiss path, so "
            "without this it could never leave the note."
        )
    if decl.kind == "non_prompt" and decl.end_transition is not None:
        raise FragmentDeclarationError(
            f"{decl.fragment_id}: a non_prompt fragment must NOT declare an end "
            "transition — it exits by dismiss. Declaring one means this is "
            "probably a prompt."
        )


def register_fragment(decl: FragmentDeclaration) -> None:
    """Register one fragment type. Validates the four declarations first."""
    _validate(decl)
    if decl.fragment_id in _REGISTRY:
        raise FragmentDeclarationError(
            f"{decl.fragment_id}: already registered. Fragment ids are unique; "
            "re-registration is a collision, not an update."
        )
    _REGISTRY[decl.fragment_id] = decl
    logger.debug("fragment registered: %s (%s)", decl.fragment_id, decl.kind)


def _ensure_seeded() -> None:
    """Populate platform fragment types on first access.

    Lazy rather than import-time, mirroring `command_bar.registry`: the seed
    imports condition functions which import services, and an import-time seed
    makes that graph load-order-sensitive.
    """
    global _SEEDED
    if _SEEDED:
        return
    _SEEDED = True
    from app.services.fragments import platform_defaults

    platform_defaults.seed()


def get_registry() -> Mapping[str, FragmentDeclaration]:
    """All registered fragment types, keyed by fragment_id."""
    _ensure_seeded()
    return dict(_REGISTRY)


def get_fragment(fragment_id: str) -> FragmentDeclaration | None:
    _ensure_seeded()
    return _REGISTRY.get(fragment_id)


def reset_registry() -> None:
    """Test escape hatch. Mirrors `command_bar.registry.reset_registry`."""
    global _SEEDED
    _REGISTRY.clear()
    _SEEDED = False
