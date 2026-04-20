"""Spaces — role-based seeding.

Same idempotency pattern as Phase 2's saved_views/seed.py. On user
creation OR role change, iterate user's current roles; for each
role not yet in `preferences.spaces_seeded_for_roles`, seed the
corresponding templates. Commit, append the role to the array.

Template additions AFTER a role has been seeded do NOT backfill.
Phase 3 accepts this trade-off; future arcs can bump a role-version
or run a one-off script.

The spec: "User with no roles: Seed a single 'General' space with
minimal pins. Don't leave them with zero spaces." — handled here
via `registry.FALLBACK_TEMPLATE`.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.company import Company
from app.models.role import Role
from app.models.user import User
from app.services.spaces import registry as reg
from app.services.spaces.types import (
    PinConfig,
    SpaceConfig,
    now_iso,
)

logger = logging.getLogger(__name__)


# ── Public API ───────────────────────────────────────────────────────


def seed_for_user(
    db: Session,
    *,
    user: User,
    tenant_vertical: str | None = None,
) -> int:
    """Idempotent seed of spaces for the user's current roles.

    Arguments:
        db: active DB session
        user: the user to seed
        tenant_vertical: optional — resolved from company if absent.

    Returns the number of new spaces created.
    """
    vertical = tenant_vertical or _resolve_tenant_vertical(db, user.company_id)

    current_roles = _current_role_slugs(db, user)
    prefs = dict(user.preferences or {})
    already_seeded = list(prefs.get("spaces_seeded_for_roles", []))

    # Zero-role case: seed the fallback General space once under
    # the sentinel "__no_role__" idempotency key.
    if not current_roles:
        if "__no_role__" in already_seeded:
            return 0
        created = _apply_templates(
            db,
            user,
            prefs,
            templates=[reg.FALLBACK_TEMPLATE],
            role_slug="__no_role__",
        )
        already_seeded.append("__no_role__")
        prefs["spaces_seeded_for_roles"] = already_seeded
        _save_prefs(db, user, prefs)
        return created

    new_roles = [r for r in current_roles if r not in already_seeded]
    if not new_roles:
        return 0

    created_total = 0
    for role_slug in new_roles:
        templates = reg.get_templates(vertical, role_slug)
        # `get_templates` never returns empty — always includes
        # FALLBACK if the (vertical, role) miss.
        created_total += _apply_templates(
            db,
            user,
            prefs,
            templates=templates,
            role_slug=role_slug,
        )
        already_seeded.append(role_slug)

    prefs["spaces_seeded_for_roles"] = already_seeded
    _save_prefs(db, user, prefs)
    return created_total


# ── Internal helpers ─────────────────────────────────────────────────


def _apply_templates(
    db: Session,
    user: User,
    prefs: dict[str, Any],
    *,
    templates: list[reg.SpaceTemplate],
    role_slug: str,
) -> int:
    """Add new SpaceConfig entries to `prefs["spaces"]` for each
    template. Mutates `prefs` in place. Returns count added.

    Idempotency safety-net: if a space with the same
    `source_template` (stored on the space via a sentinel pin — no,
    wait, spaces themselves don't have source keys today) —
    reduces to "by name + role" match. If an existing space already
    has the template's (role_slug, template_id) fingerprint in its
    name, skip. Phase 3 relies PRIMARILY on the
    `spaces_seeded_for_roles` array; this pass is belt-and-
    suspenders against a scenario where the array is missing but
    the space somehow was seeded (e.g. manual DB edit).
    """
    spaces_raw = prefs.get("spaces") or []
    spaces: list[SpaceConfig] = [SpaceConfig.from_dict(s) for s in spaces_raw]
    existing_names = {s.name.lower() for s in spaces}

    added = 0
    for template in templates:
        if template.name.lower() in existing_names:
            logger.info(
                "Skipping seed of space %r for user %s (already present)",
                template.name, user.id,
            )
            continue

        new_space = SpaceConfig(
            space_id=SpaceConfig.new_id(),
            name=template.name,
            icon=template.icon,
            accent=template.accent,
            display_order=len(spaces),
            is_default=template.is_default,
            density=template.density,
            pins=_build_pins_from_seeds(db, user, template.pins),
            created_at=now_iso(),
            updated_at=now_iso(),
        )

        # Only the FIRST is_default=True across all templates
        # applied in this run flips the flag; additional defaults
        # lose to whatever set it first. (Two roles each seeding a
        # default is unusual; last-write-wins is acceptable.)
        if new_space.is_default and any(s.is_default for s in spaces):
            new_space.is_default = False

        spaces.append(new_space)
        existing_names.add(template.name.lower())
        added += 1

    # No current active space? Set the first default we have.
    if prefs.get("active_space_id") is None:
        for sp in spaces:
            if sp.is_default:
                prefs["active_space_id"] = sp.space_id
                break

    prefs["spaces"] = [s.to_dict() for s in spaces]
    return added


def _build_pins_from_seeds(
    db: Session,
    user: User,
    pin_seeds: list[reg.PinSeed],
) -> list[PinConfig]:
    """Resolve `PinSeed` list to stored `PinConfig` list.

    Saved-view seed keys that don't resolve for this user produce a
    pin stored with `target_id=""` and `target_seed_key` preserved.
    The pin renders as "unavailable" at read time. This keeps the
    pin present if/when the saved view later shows up (though Phase
    3 doesn't yet re-resolve on saved-view creation — users would
    need to re-pin, which is a one-click operation).

    For nav_item pins, we simply store the href as `target_id`.
    """
    out: list[PinConfig] = []
    for i, seed in enumerate(pin_seeds):
        if seed.pin_type == "saved_view":
            # seed.target IS the seed_key.
            out.append(
                PinConfig(
                    pin_id=PinConfig.new_id(),
                    pin_type="saved_view",
                    target_id="",  # placeholder; read path uses target_seed_key
                    display_order=i,
                    label_override=seed.label_override,
                    target_seed_key=seed.target,
                )
            )
        elif seed.pin_type == "triage_queue":
            # seed.target IS the queue_id (stable in-code identifier).
            # No seed_key indirection needed — queue_ids are platform
            # defaults, not user-created UUIDs.
            out.append(
                PinConfig(
                    pin_id=PinConfig.new_id(),
                    pin_type="triage_queue",
                    target_id=seed.target,
                    display_order=i,
                    label_override=seed.label_override,
                )
            )
        else:
            out.append(
                PinConfig(
                    pin_id=PinConfig.new_id(),
                    pin_type="nav_item",
                    target_id=seed.target,
                    display_order=i,
                    label_override=seed.label_override,
                )
            )
    return out


def _resolve_tenant_vertical(db: Session, company_id: str) -> str | None:
    co = db.query(Company).filter(Company.id == company_id).first()
    if co is None:
        return None
    return getattr(co, "vertical", None)


def _current_role_slugs(db: Session, user: User) -> list[str]:
    """Single role today via role_id. Returned as a list to match
    the multi-role future (matches Phase 2's pattern)."""
    if user.role_id is None:
        return []
    role = db.query(Role).filter(Role.id == user.role_id).first()
    return [role.slug] if role and role.slug else []


def _save_prefs(db: Session, user: User, prefs: dict[str, Any]) -> None:
    user.preferences = prefs
    flag_modified(user, "preferences")
    db.commit()
    db.refresh(user)


__all__ = ["seed_for_user"]
