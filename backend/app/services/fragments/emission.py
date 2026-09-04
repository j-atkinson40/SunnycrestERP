"""Fragment emission — audience gate, then condition, then instances.

⚠️ AUDIENCE FAILURE MEANS NON-EXISTENCE, NOT INERT RENDERING. Per DECISIONS
2026-09-04 ("Prose fragments declare four things"): "lacking the permission
means the fragment does not exist rather than rendering inert." So a fragment
whose audience predicate fails is never evaluated — its condition does not run,
it produces no instance, and nothing about it reaches the caller. This is
stronger than filtering the output, and the difference is observable: a
disabled-but-present fragment leaks the existence of work the user may not know
about, which on a prose surface means leaking a sentence about it.

The gate reads the EXISTING permission system —
`permission_service.user_has_permission` and `module_service.is_module_enabled`
— exactly as `command_bar/retrieval.py:241-249` does. No parallel system.

⚠️ WHAT THIS MODULE DELIBERATELY DOES NOT DO. Per the dispatch's do-not-build
line: there is no fragment-keyed cache invalidation here. The salvage
investigation established that `pulse.composition_cache.invalidate_for_user`
evicts every cached composition for a user across all work_areas hashes and
minute windows — whole-surface eviction, which re-composes everything and so
re-words everything, defeating the wording stability the contract exists to
protect. Fragment-keyed invalidation is real new work and belongs to the
surface arc.

THE SEAM IS HERE: `emit_for_user` is a pure read. Nothing caches its result and
nothing invalidates it. The surface arc adds a cache keyed on
`(user_id, fragment_id, instance_key)` and drives eviction from per-fragment
condition_inputs divergence rather than from whole-user eviction. Do not build
across this seam from either side.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Sequence

from sqlalchemy.orm import Session

from app.models.user import User
from app.services.fragments.registry import get_registry
from app.services.fragments.types import (
    FragmentDeclaration,
    FragmentInstance,
)

logger = logging.getLogger(__name__)


class FragmentEmissionError(RuntimeError):
    """An instance violated a declaration at emission time."""


@dataclass(frozen=True)
class EmittedFragment:
    """A declaration paired with one of its instances, ready to compose.

    The note surface consumes a list of these. It carries the declaration by
    reference rather than by copy so the renderer reads `kind`, `dismissible`,
    `target_surface`/`target_key` off the single source of truth.
    """

    declaration: FragmentDeclaration
    instance: FragmentInstance

    @property
    def fragment_id(self) -> str:
        return self.declaration.fragment_id

    @property
    def priority(self) -> int:
        return self.instance.payload.priority


def audience_admits(db: Session, user: User, decl: FragmentDeclaration) -> bool:
    """Evaluate declaration (1) against the existing permission system.

    Mirrors the command-bar gate pipeline, including the `admin` short-circuit
    that `permission_service.user_has_permission` already implements
    internally, so this function does not re-derive role logic.
    """
    from app.services.module_service import is_module_enabled
    from app.services.permission_service import user_has_permission

    aud = decl.audience

    if aud.required_permission and not user_has_permission(
        user, db, aud.required_permission
    ):
        return False

    if aud.required_module and not is_module_enabled(
        db, user.company_id, aud.required_module
    ):
        return False

    if aud.required_extension:
        from app.services.extension_service import is_extension_enabled

        if not is_extension_enabled(db, user.company_id, aud.required_extension):
            return False

    return True


def _validate_instance(
    decl: FragmentDeclaration, inst: FragmentInstance
) -> None:
    """Enforce the per-instance half of declaration (3), plus (2)'s snapshot.

    ⚠️ NON-EMPTY SCOPE IS THE POINT. Per DECISIONS 2026-09-04: a fragment
    "opens the scheduling Focus already scoped to tomorrow, not a generic
    surface the user then filters," and "an href with no scope carry does not
    satisfy this." An empty scope IS an href with no scope carry wearing a
    dict, so it is rejected here rather than degrading silently into the
    behaviour the decision was written to prevent.
    """
    if not inst.instance_key or not inst.instance_key.strip():
        raise FragmentEmissionError(
            f"{decl.fragment_id}: instance_key is required — the surface arc "
            "keys deferral and settling on it."
        )
    if not inst.scope:
        raise FragmentEmissionError(
            f"{decl.fragment_id}/{inst.instance_key}: declaration (3) requires "
            "a NON-EMPTY scope. A fragment must carry scope into what it "
            "opens; an empty scope is an unscoped href in a dict."
        )
    if inst.condition_inputs is None:
        raise FragmentEmissionError(
            f"{decl.fragment_id}/{inst.instance_key}: declaration (2) requires "
            "condition_inputs — the enumerable snapshot the surface arc's "
            "deferral diffs to wake a prompt on divergence."
        )


def emit_for_user(
    db: Session,
    *,
    user: User,
    fragment_ids: Sequence[str] | None = None,
) -> list[EmittedFragment]:
    """Emit every fragment instance this user should see, highest priority first.

    `fragment_ids` restricts evaluation to named types (tests, and the surface
    arc's per-fragment regeneration). None means all registered types.

    A condition that raises is logged and skipped: one bad fragment type must
    not blank the note. This mirrors the task-subscriber registry's isolated
    try/except per subscriber.
    """
    out: list[EmittedFragment] = []

    for fragment_id, decl in get_registry().items():
        if fragment_ids is not None and fragment_id not in fragment_ids:
            continue

        # (1) AUDIENCE — non-existence, not inert. The condition below never
        # runs for a user the audience excludes.
        if not audience_admits(db, user, decl):
            continue

        try:
            instances = decl.condition(db, user=user) or []
        except Exception:
            logger.exception(
                "fragment condition failed, skipping: %s", fragment_id
            )
            continue

        for inst in instances:
            try:
                _validate_instance(decl, inst)
            except FragmentEmissionError:
                logger.exception(
                    "fragment instance rejected: %s", fragment_id
                )
                continue
            out.append(EmittedFragment(declaration=decl, instance=inst))

    # Urgency order. DECISIONS 2026-09-04 ("two registers"): prose fragments
    # are "composed, ordered by urgency" — unlike the standing set, which is
    # positionally stable and must never reorder.
    out.sort(key=lambda e: (-e.priority, e.fragment_id, e.instance.instance_key))
    return out
