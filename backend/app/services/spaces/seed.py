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
    MAX_SPACES_PER_USER,
    PinConfig,
    SpaceConfig,
    now_iso,
)

logger = logging.getLogger(__name__)


# ── Public API ───────────────────────────────────────────────────────


def seed_spaces_best_effort(
    db: Session,
    user: User,
    *,
    call_site: str,
) -> int:
    """Phase 8e.2.2 Space Invariant Enforcement helper.

    Single wrapper for every best-effort `seed_for_user` call site
    (auth_service.register_company, user_service.create_user,
    user_service.create_users_bulk, auth_service.login_user defensive
    re-seed). Catches any seeding exception so the caller's user-
    creation / login flow never fails on a Spaces issue, and emits a
    single structured log line (user_id, company_id, vertical,
    role_slug, exception type + message) per failure — the minimum
    signal an operator needs to trace which call site failed and why.

    Returns the number of newly-seeded spaces, or 0 on exception.
    """
    try:
        return seed_for_user(db, user=user)
    except Exception as exc:
        # Resolve vertical + role_slug for the diagnostic line without
        # raising — if these lookups themselves fail we still emit the
        # original seeding failure with best-effort context.
        vertical: str | None = None
        role_slug: str | None = None
        try:
            vertical = _resolve_tenant_vertical(db, user.company_id)
        except Exception:
            pass
        try:
            slugs = _current_role_slugs(db, user)
            role_slug = slugs[0] if slugs else None
        except Exception:
            pass

        logger.warning(
            "spaces.seed_for_user failed "
            "call_site=%s user_id=%s company_id=%s vertical=%s "
            "role_slug=%s exc_type=%s exc_msg=%s",
            call_site,
            user.id,
            user.company_id,
            vertical,
            role_slug,
            type(exc).__name__,
            str(exc),
        )
        # Defensive rollback — seed_for_user commits internally but a
        # partial write before the exception may have left the session
        # in a mixed state. Callers (e.g. login_user) shouldn't care
        # about this side effect; we clean up so their subsequent
        # commit doesn't trip on orphaned dirty attributes.
        try:
            db.rollback()
        except Exception:
            pass
        return 0


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

    # Workflow Arc Phase 8a — seed system spaces (Settings etc.)
    # based on live permissions. Idempotent via
    # preferences.system_spaces_seeded. Re-runs on role change
    # pick up newly-granted admin permission without forcing the
    # user-space re-seed (which is gated by ROLE_CHANGE_RESEED_ENABLED
    # in user_service.update_user).
    created_total += _apply_system_spaces(db, user, prefs)

    _save_prefs(db, user, prefs)
    return created_total


def _apply_system_spaces(
    db: Session,
    user: User,
    prefs: dict[str, Any],
) -> int:
    """Append system spaces (Settings etc.) to prefs['spaces']
    based on the user's current permissions. Tracked via
    preferences.system_spaces_seeded list[str] of template_ids."""
    system_templates = reg.get_system_space_templates_for_user(db, user)
    already_seeded = set(prefs.get("system_spaces_seeded", []))
    # Phase 8e.2.3 — lenient load mirrors _apply_templates.
    spaces = _load_spaces_lenient(prefs, user_id=user.id)
    existing_names = {s.name.lower() for s in spaces}
    existing_system_ids = {
        s.space_id.replace("sys_", "", 1)
        for s in spaces
        if s.is_system and s.space_id.startswith("sys_")
    }

    added = 0
    for tpl in system_templates:
        # Idempotency: skip if the template_id is already in the
        # per-user array OR we see a system space with matching id
        # prefix OR a space with the same name exists.
        if tpl.template_id in already_seeded:
            continue
        if tpl.template_id in existing_system_ids:
            already_seeded.add(tpl.template_id)
            continue
        if tpl.name.lower() in existing_names:
            already_seeded.add(tpl.template_id)
            continue

        # Phase 8e.2.3 — cap-breach guard parallel to _apply_templates.
        # User manual spaces + role templates already consumed the
        # allotment → system space (Settings) skipped with WARNING.
        # Rare in practice because system templates count is small (1
        # today), but matches the invariant: manual + templates
        # prioritized over system additions, user agency wins.
        # Template_id stays OUT of system_spaces_seeded when skipped
        # so next login (after user deletes something) will retry.
        if len(spaces) >= MAX_SPACES_PER_USER:
            logger.warning(
                "spaces.seed cap-breach skip (system) "
                "user_id=%s company_id=%s template_id=%r template_name=%r "
                "current_spaces=%d max=%d",
                user.id,
                user.company_id,
                tpl.template_id,
                tpl.name,
                len(spaces),
                MAX_SPACES_PER_USER,
            )
            continue

        new_space = SpaceConfig(
            # Stable space_id so the same user re-seeding doesn't
            # create duplicates and the dot nav can key on it.
            space_id=f"sys_{tpl.template_id}",
            name=tpl.name,
            icon=tpl.icon,
            accent=tpl.accent,
            display_order=tpl.display_order,
            is_default=False,
            density=tpl.density,
            is_system=True,
            default_home_route=tpl.default_home_route,
            pins=_build_pins_from_seeds(db, user, tpl.pins),
            created_at=now_iso(),
            updated_at=now_iso(),
        )
        spaces.append(new_space)
        existing_names.add(tpl.name.lower())
        already_seeded.add(tpl.template_id)
        added += 1

    if added > 0:
        prefs["spaces"] = [s.to_dict() for s in spaces]
    prefs["system_spaces_seeded"] = sorted(already_seeded)
    return added


# ── Internal helpers ─────────────────────────────────────────────────


def _load_spaces_lenient(
    prefs: dict[str, Any], *, user_id: str | None = None
) -> list[SpaceConfig]:
    """Load `prefs['spaces']` into SpaceConfig, skipping malformed
    entries with a WARNING instead of raising.

    Canonical shape requires `space_id`, `name`, `icon`, `accent`,
    `display_order`, etc. Pre-Phase-8e test fixtures and some legacy
    migrations wrote minimal shapes like `{id, name, accent}` that
    fail `SpaceConfig.from_dict`. Without this lenient loader, a
    single malformed entry aborts seed for the whole user — which
    means retrofit migrations skip any user whose preferences
    carries fixture junk.

    Production data is always canonical (written via crud/seed),
    so this is primarily a safety net against dev DB residue. It
    also means a future schema addition to SpaceConfig can roll out
    with backward-compat: old entries are silently dropped instead
    of breaking the seed path.
    """
    spaces_raw = prefs.get("spaces") or []
    out: list[SpaceConfig] = []
    for i, raw in enumerate(spaces_raw):
        try:
            out.append(SpaceConfig.from_dict(raw))
        except Exception as exc:
            logger.warning(
                "spaces.seed malformed space entry skipped "
                "user_id=%s index=%d exc_type=%s exc_msg=%s keys=%r",
                user_id,
                i,
                type(exc).__name__,
                str(exc),
                sorted(raw.keys()) if isinstance(raw, dict) else "<non-dict>",
            )
    return out


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

    Phase 8e.2.3 — cap-breach guard: if appending the next template
    would exceed `MAX_SPACES_PER_USER`, skip the template with a
    structured warning rather than breach silently. User agency
    wins: manual spaces + earlier-in-iteration templates stay;
    later-in-iteration templates are dropped. Matches the umbrella
    principle (configurable thereafter — user's existing content is
    sacrosanct). Retrofit migrations (r47) hit this for users who
    have ~5+ manual spaces and a role template producing 3 more.
    """
    # Phase 8e.2.3 — lenient load so malformed legacy entries don't
    # crash the seed. Real prod data always canonical; this is
    # safety net for dev DB residue + future schema additions.
    spaces = _load_spaces_lenient(prefs, user_id=user.id)
    existing_names = {s.name.lower() for s in spaces}

    # Phase 8e.2.3 — partial-seed accounting for the end-of-run
    # summary line. Separate bucket from `added` so operators see
    # both "how many made it" and "how many dropped to cap."
    skipped_due_to_cap: list[str] = []
    total_templates = len(templates)

    added = 0
    for template in templates:
        if template.name.lower() in existing_names:
            logger.info(
                "Skipping seed of space %r for user %s (already present)",
                template.name, user.id,
            )
            continue

        # Phase 8e.2.3 — cap-breach guard. System spaces go through a
        # separate path (_apply_system_spaces) and aren't counted here;
        # that pass gets its own headroom check.
        if len(spaces) >= MAX_SPACES_PER_USER:
            skipped_due_to_cap.append(template.name)
            logger.warning(
                "spaces.seed cap-breach skip "
                "user_id=%s company_id=%s role_slug=%s template_name=%r "
                "current_spaces=%d max=%d",
                user.id,
                user.company_id,
                role_slug,
                template.name,
                len(spaces),
                MAX_SPACES_PER_USER,
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
            default_home_route=template.default_home_route,
            # Phase 8e.2 — portal modifier fields carry through from
            # template to the user's stored SpaceConfig.
            access_mode=template.access_mode,
            tenant_branding=template.tenant_branding,
            write_mode=template.write_mode,
            session_timeout_minutes=template.session_timeout_minutes,
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

    # Phase 8e.2.3 — end-of-pass summary line. Emitted at INFO when
    # any cap-breach skipping occurred so operators see partial-seed
    # events without the WARN per-template lines dominating the log.
    # Only logged when total > 0 AND partial to keep log volume low.
    if skipped_due_to_cap and total_templates > 0:
        logger.info(
            "spaces.seed partial-seed "
            "user_id=%s role_slug=%s added=%d/%d skipped_names=%r",
            user.id,
            role_slug,
            added,
            total_templates,
            skipped_due_to_cap,
        )
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


__all__ = ["seed_for_user", "seed_spaces_best_effort"]
