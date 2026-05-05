"""Platform Themes service — CRUD + inheritance resolution.

Inheritance is computed at READ time (`resolve_theme`) so a change
at vertical_default scope propagates to every tenant in that
vertical that hasn't overridden the affected tokens. The merge
order is platform_default → vertical_default → tenant_override
(deeper scope wins).

Mode is part of theme identity. Light + dark are independent
records; resolving for `mode='light'` only walks light-mode rows.

Versioning: every save deactivates the prior active row at the
same (scope, vertical, tenant_id, mode) tuple and inserts a new
active row with `version = prior.version + 1`. Inactive rows
accumulate as a versioned audit trail without violating the
partial unique index.
"""

from __future__ import annotations

from typing import Iterable, Literal, Mapping
from sqlalchemy.orm import Session

from app.models.platform_theme import (
    MODE_DARK,
    MODE_LIGHT,
    PlatformTheme,
    SCOPE_PLATFORM_DEFAULT,
    SCOPE_TENANT_OVERRIDE,
    SCOPE_VERTICAL_DEFAULT,
)


Mode = Literal["light", "dark"]
Scope = Literal["platform_default", "vertical_default", "tenant_override"]

_VALID_SCOPES: tuple[str, ...] = (
    SCOPE_PLATFORM_DEFAULT,
    SCOPE_VERTICAL_DEFAULT,
    SCOPE_TENANT_OVERRIDE,
)
_VALID_MODES: tuple[str, ...] = (MODE_LIGHT, MODE_DARK)


class ThemeServiceError(Exception):
    """Base exception for the theme service."""


class ThemeNotFound(ThemeServiceError):
    pass


class ThemeScopeMismatch(ThemeServiceError):
    """Scope/vertical/tenant_id triple violates the canonical shape."""


class InvalidThemeShape(ThemeServiceError):
    """Mode is not light/dark, or token_overrides is not a dict."""


# ─── Validation helpers ──────────────────────────────────────────


def _validate_mode(mode: str) -> None:
    if mode not in _VALID_MODES:
        raise InvalidThemeShape(
            f"mode must be one of {_VALID_MODES}, got {mode!r}"
        )


def _validate_scope_keys(
    scope: str,
    vertical: str | None,
    tenant_id: str | None,
) -> None:
    """Mirror the DB CHECK constraint at the application boundary so
    we 400-out cleanly instead of relying on Postgres to barf."""
    if scope not in _VALID_SCOPES:
        raise InvalidThemeShape(f"scope must be one of {_VALID_SCOPES}")
    if scope == SCOPE_PLATFORM_DEFAULT and (vertical is not None or tenant_id is not None):
        raise ThemeScopeMismatch(
            "platform_default rows must have vertical=None and tenant_id=None"
        )
    if scope == SCOPE_VERTICAL_DEFAULT and (vertical is None or tenant_id is not None):
        raise ThemeScopeMismatch(
            "vertical_default rows must have vertical set and tenant_id=None"
        )
    if scope == SCOPE_TENANT_OVERRIDE and (tenant_id is None or vertical is not None):
        raise ThemeScopeMismatch(
            "tenant_override rows must have tenant_id set and vertical=None"
        )


def _validate_overrides(token_overrides: Mapping[str, object]) -> dict:
    if not isinstance(token_overrides, dict):
        raise InvalidThemeShape(
            "token_overrides must be a mapping of token name → value"
        )
    cleaned: dict[str, object] = {}
    for k, v in token_overrides.items():
        if not isinstance(k, str) or not k:
            raise InvalidThemeShape(
                f"token name keys must be non-empty strings, got {k!r}"
            )
        if v is None:
            # Explicit null = "remove this override"; treat as absent.
            continue
        cleaned[k] = v
    return cleaned


# ─── CRUD ────────────────────────────────────────────────────────


def list_themes(
    db: Session,
    *,
    scope: str | None = None,
    vertical: str | None = None,
    tenant_id: str | None = None,
    mode: str | None = None,
    include_inactive: bool = False,
) -> list[PlatformTheme]:
    """Return theme rows matching the filters.

    Active-only by default. Pass `include_inactive=True` for the
    full version trail (Phase 3 history UI consumer).
    """
    q = db.query(PlatformTheme)
    if scope is not None:
        if scope not in _VALID_SCOPES:
            raise InvalidThemeShape(f"scope filter invalid: {scope!r}")
        q = q.filter(PlatformTheme.scope == scope)
    if vertical is not None:
        q = q.filter(PlatformTheme.vertical == vertical)
    if tenant_id is not None:
        q = q.filter(PlatformTheme.tenant_id == tenant_id)
    if mode is not None:
        _validate_mode(mode)
        q = q.filter(PlatformTheme.mode == mode)
    if not include_inactive:
        q = q.filter(PlatformTheme.is_active.is_(True))
    return q.order_by(PlatformTheme.created_at.desc()).all()


def get_theme(db: Session, theme_id: str) -> PlatformTheme:
    row = db.query(PlatformTheme).filter(PlatformTheme.id == theme_id).first()
    if not row:
        raise ThemeNotFound(theme_id)
    return row


def _find_active(
    db: Session,
    *,
    scope: str,
    vertical: str | None,
    tenant_id: str | None,
    mode: str,
) -> PlatformTheme | None:
    return (
        db.query(PlatformTheme)
        .filter(
            PlatformTheme.scope == scope,
            PlatformTheme.vertical.is_(vertical) if vertical is None else PlatformTheme.vertical == vertical,
            PlatformTheme.tenant_id.is_(tenant_id) if tenant_id is None else PlatformTheme.tenant_id == tenant_id,
            PlatformTheme.mode == mode,
            PlatformTheme.is_active.is_(True),
        )
        .first()
    )


def create_theme(
    db: Session,
    *,
    scope: str,
    vertical: str | None = None,
    tenant_id: str | None = None,
    mode: str,
    token_overrides: Mapping[str, object] | None = None,
    actor_user_id: str | None = None,
) -> PlatformTheme:
    """Create a new active theme row.

    If an active row already exists at the same tuple, it is
    deactivated first (write-side versioning); the new row's
    version is `prior.version + 1`.
    """
    _validate_scope_keys(scope, vertical, tenant_id)
    _validate_mode(mode)
    overrides = _validate_overrides(token_overrides or {})

    existing = _find_active(
        db,
        scope=scope,
        vertical=vertical,
        tenant_id=tenant_id,
        mode=mode,
    )

    next_version = 1
    if existing is not None:
        existing.is_active = False
        next_version = existing.version + 1

    row = PlatformTheme(
        scope=scope,
        vertical=vertical,
        tenant_id=tenant_id,
        mode=mode,
        token_overrides=dict(overrides),
        version=next_version,
        is_active=True,
        created_by=actor_user_id,
        updated_by=actor_user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_theme(
    db: Session,
    theme_id: str,
    *,
    token_overrides: Mapping[str, object],
    actor_user_id: str | None = None,
) -> PlatformTheme:
    """Replace `token_overrides` on the theme identified by id and
    bump version. The prior row is deactivated; a new active row
    is inserted carrying the same (scope, vertical, tenant_id, mode)
    plus the new overrides + incremented version.

    Returning the new active row mirrors HTTP-PATCH semantics from
    the caller's perspective even though the storage is append-
    only for audit.
    """
    prior = get_theme(db, theme_id)
    if not prior.is_active:
        raise ThemeServiceError(
            f"cannot update inactive theme {theme_id!r} — fetch the active "
            f"row at the same tuple instead",
        )

    overrides = _validate_overrides(token_overrides)
    prior.is_active = False
    new_row = PlatformTheme(
        scope=prior.scope,
        vertical=prior.vertical,
        tenant_id=prior.tenant_id,
        mode=prior.mode,
        token_overrides=dict(overrides),
        version=prior.version + 1,
        is_active=True,
        created_by=actor_user_id,
        updated_by=actor_user_id,
    )
    db.add(new_row)
    db.commit()
    db.refresh(new_row)
    return new_row


# ─── Inheritance resolution ──────────────────────────────────────


def resolve_theme(
    db: Session,
    *,
    mode: str,
    vertical: str | None = None,
    tenant_id: str | None = None,
) -> dict:
    """Return the fully-merged token override map for the given
    mode + scope context.

    Resolution order:
        platform_default(mode)
            <- vertical_default(vertical, mode) if vertical given
            <- tenant_override(tenant_id, mode) if tenant_id given

    Deeper scope wins. Returns `{tokens: {...}, sources: [...],
    mode: ..., vertical: ..., tenant_id: ...}`. The `sources`
    array tells the editor which scopes contributed (and at what
    version), so the inheritance indicator in the UI can render
    "overridden at vertical-default v3" without a second query.
    """
    _validate_mode(mode)

    sources: list[dict] = []
    merged: dict = {}

    platform_row = _find_active(
        db,
        scope=SCOPE_PLATFORM_DEFAULT,
        vertical=None,
        tenant_id=None,
        mode=mode,
    )
    if platform_row is not None:
        merged.update(dict(platform_row.token_overrides or {}))
        sources.append(
            {
                "scope": SCOPE_PLATFORM_DEFAULT,
                "id": platform_row.id,
                "version": platform_row.version,
                "applied_keys": list((platform_row.token_overrides or {}).keys()),
            }
        )

    if vertical is not None:
        vertical_row = _find_active(
            db,
            scope=SCOPE_VERTICAL_DEFAULT,
            vertical=vertical,
            tenant_id=None,
            mode=mode,
        )
        if vertical_row is not None:
            merged.update(dict(vertical_row.token_overrides or {}))
            sources.append(
                {
                    "scope": SCOPE_VERTICAL_DEFAULT,
                    "vertical": vertical,
                    "id": vertical_row.id,
                    "version": vertical_row.version,
                    "applied_keys": list((vertical_row.token_overrides or {}).keys()),
                }
            )

    if tenant_id is not None:
        tenant_row = _find_active(
            db,
            scope=SCOPE_TENANT_OVERRIDE,
            vertical=None,
            tenant_id=tenant_id,
            mode=mode,
        )
        if tenant_row is not None:
            merged.update(dict(tenant_row.token_overrides or {}))
            sources.append(
                {
                    "scope": SCOPE_TENANT_OVERRIDE,
                    "tenant_id": tenant_id,
                    "id": tenant_row.id,
                    "version": tenant_row.version,
                    "applied_keys": list((tenant_row.token_overrides or {}).keys()),
                }
            )

    return {
        "tokens": merged,
        "sources": sources,
        "mode": mode,
        "vertical": vertical,
        "tenant_id": tenant_id,
    }
