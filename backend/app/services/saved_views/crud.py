"""Saved View CRUD — Phase 2.

The only module that round-trips between `SavedView` dataclasses
and `VaultItem` rows. Every other module in the saved_views package
works with typed dataclasses (from `types.py`) — no raw JSONB dicts
outside this file.

Storage: `metadata_json.saved_view_config` is the CANONICAL location
per the approved audit (no compatibility fallbacks, no dual-write).
Writes go there; reads come from there.

Visibility model (4 levels — matches Permissions.visibility):

  private       → only owner_user_id can see + execute
  role_shared   → owner + any user whose role.slug ∈ shared_with_roles
  user_shared   → owner + any user whose id ∈ shared_with_users
  tenant_public → every user in the view's tenant

Cross-tenant sharing is UI-unexposed; `shared_with_tenants` list
lives in the config for the backend masking path. crud doesn't
grant cross-tenant access — that's a separate future workflow.

Soft-delete: `delete_saved_view` flips `vault_items.is_active` to
False. Re-creating a view with the same title is allowed; no
unique constraint on title.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.role import Role
from app.models.user import User
from app.models.vault_item import VaultItem
from app.services.saved_views.types import (
    Permissions,
    Presentation,
    Query,
    SavedView,
    SavedViewConfig,
)


logger = logging.getLogger(__name__)


class SavedViewError(Exception):
    """CRUD failure. Carries `http_status` for the API layer."""

    def __init__(self, message: str, *, http_status: int = 400) -> None:
        super().__init__(message)
        self.http_status = http_status


class SavedViewNotFound(SavedViewError):
    def __init__(self, view_id: str) -> None:
        super().__init__(
            f"Saved view {view_id!r} not found", http_status=404
        )


class SavedViewPermissionDenied(SavedViewError):
    def __init__(self, view_id: str, reason: str) -> None:
        super().__init__(
            f"Access denied to saved view {view_id!r}: {reason}",
            http_status=403,
        )


# ── Helpers ──────────────────────────────────────────────────────────


def _get_or_create_company_vault(db: Session, company_id: str):
    """Resolve the tenant's Vault row — saved_view VaultItems need a
    vault_id and every tenant has one auto-created on first VaultItem
    write."""
    from app.services.vault_service import get_or_create_company_vault

    return get_or_create_company_vault(db, company_id)


def _user_role_slug(db: Session, user: User) -> str | None:
    if user.role_id is None:
        return None
    role = db.query(Role).filter(Role.id == user.role_id).first()
    return role.slug if role else None


def _can_user_see(db: Session, user: User, row: VaultItem, config: SavedViewConfig) -> bool:
    """Can `user` see this saved view?

    Rules (evaluated in order):
      1. Owner — always yes
      2. Super admin — always yes (tenant-admin override)
      3. Cross-tenant — only if user.company_id is in
         permissions.shared_with_tenants. Cross-tenant sees the
         view through masking, but access must be explicit.
      4. visibility='private'       → owner only (already handled)
      5. visibility='role_shared'   → role slug in shared_with_roles
      6. visibility='user_shared'   → user id in shared_with_users
      7. visibility='tenant_public' → same tenant as owner

    Returns False as the default.
    """
    perms = config.permissions
    # Cross-tenant access
    if user.company_id != row.company_id:
        return user.company_id in (perms.shared_with_tenants or [])

    # Same-tenant path
    if row.created_by == user.id or perms.owner_user_id == user.id:
        return True
    if getattr(user, "is_super_admin", False):
        return True
    if perms.visibility == "tenant_public":
        return True
    if perms.visibility == "user_shared":
        return user.id in (perms.shared_with_users or [])
    if perms.visibility == "role_shared":
        role_slug = _user_role_slug(db, user)
        return role_slug in (perms.shared_with_roles or [])
    # private — already handled by owner check above
    return False


def _can_user_edit(db: Session, user: User, row: VaultItem, config: SavedViewConfig) -> bool:
    """Only the owner (or super_admin) can edit a saved view in
    Phase 2. Future phases may add an 'editor' level to the
    visibility enum."""
    if row.created_by == user.id or config.permissions.owner_user_id == user.id:
        return True
    if getattr(user, "is_super_admin", False):
        return True
    return False


def _row_to_saved_view(row: VaultItem) -> SavedView:
    """Parse a VaultItem into a SavedView dataclass.

    Raises SavedViewError if the stored metadata is malformed.
    """
    meta = row.metadata_json or {}
    config_dict = meta.get("saved_view_config")
    if not config_dict:
        raise SavedViewError(
            f"VaultItem {row.id} has item_type=saved_view but no "
            f"metadata_json.saved_view_config. Data corruption?",
            http_status=500,
        )
    try:
        config = SavedViewConfig.from_dict(config_dict)
    except (KeyError, TypeError) as exc:
        raise SavedViewError(
            f"Saved view {row.id} has malformed config: {exc}",
            http_status=500,
        )
    return SavedView(
        id=row.id,
        company_id=row.company_id,
        title=row.title,
        description=row.description,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
        config=config,
    )


def _get_row(db: Session, view_id: str) -> VaultItem | None:
    return (
        db.query(VaultItem)
        .filter(
            VaultItem.id == view_id,
            VaultItem.item_type == "saved_view",
            VaultItem.is_active.is_(True),
        )
        .first()
    )


# ── Public API ───────────────────────────────────────────────────────


def create_saved_view(
    db: Session,
    *,
    user: User,
    title: str,
    description: str | None,
    config: SavedViewConfig,
    source_entity_id: str | None = None,
) -> SavedView:
    """Create a new saved view owned by `user` in their tenant.

    `source_entity_id` — optional external key, used by the seed
    service to achieve idempotency ("don't re-seed if this key
    already exists for this user").

    Config's `permissions.owner_user_id` is rewritten to `user.id`
    to enforce ownership from the server side (don't trust client-
    supplied owner fields).

    Pattern A enforcement (Phase W-4a Step 3, Layer 3): rejects
    creation when the config's `entity_type` isn't compatible with
    the tenant's vertical per the entity registry's
    allowed_verticals. Reference: BRIDGEABLE_MASTER §3.25 saved
    view vertical-scope inheritance amendment. Raises
    SavedViewError(http_status=400) on incompatibility.
    """
    if not title.strip():
        raise SavedViewError("title is required")

    # Pattern A enforcement: vertical-scope inheritance from data source.
    from app.models.company import Company
    from app.services.saved_views import registry

    company = db.query(Company).filter(Company.id == user.company_id).first()
    tenant_vertical = (
        getattr(company, "vertical", None) if company else None
    )
    entity_type = config.query.entity_type
    if not registry.is_entity_compatible_with_vertical(
        entity_type, tenant_vertical
    ):
        meta = registry.get_entity(entity_type)
        allowed = meta.allowed_verticals if meta else []
        raise SavedViewError(
            f"Cannot create saved view with entity_type={entity_type!r} "
            f"in {tenant_vertical!r} tenant. "
            f"Allowed verticals for this entity: {allowed!r}",
            http_status=400,
        )

    config.permissions.owner_user_id = user.id

    vault = _get_or_create_company_vault(db, user.company_id)
    row = VaultItem(
        id=str(uuid.uuid4()),
        vault_id=vault.id,
        company_id=user.company_id,
        item_type="saved_view",
        title=title.strip(),
        description=description,
        visibility="internal",  # VaultItem.visibility is orthogonal to
                                 # our config.permissions.visibility — the
                                 # VaultItem row is "internal" to allow
                                 # any in-tenant read; our config handles
                                 # the finer-grained gate.
        source="user_upload",
        source_entity_id=source_entity_id,
        created_by=user.id,
        metadata_json={"saved_view_config": config.to_dict()},
    )
    db.add(row)
    db.flush()
    db.commit()
    db.refresh(row)
    return _row_to_saved_view(row)


def get_saved_view(db: Session, *, user: User, view_id: str) -> SavedView:
    """Get a saved view by id, enforcing visibility.

    Returns a typed SavedView (NOT the VaultItem).

    Raises SavedViewNotFound if the row doesn't exist OR is soft-deleted.
    Raises SavedViewPermissionDenied if the user can't see the view
    per the visibility rules.
    """
    row = _get_row(db, view_id)
    if row is None:
        raise SavedViewNotFound(view_id)
    sv = _row_to_saved_view(row)
    if not _can_user_see(db, user, row, sv.config):
        raise SavedViewPermissionDenied(view_id, "not shared with you")
    return sv


def list_saved_views_for_user(
    db: Session,
    *,
    user: User,
    entity_type: str | None = None,
) -> list[SavedView]:
    """List every saved view this user can see, optionally filtered
    to a specific entity_type.

    Visible-to-user policy runs post-query in Python rather than as
    SQL because permissions.visibility is inside a JSONB blob and
    would require JSON operator filters that are hard to read + slow
    to plan. For Phase 2 scale (expected ~5-50 saved views per user)
    this is fine. Phase 3+ may migrate to a promoted column if N
    grows.

    Pattern A defense-in-depth (Phase W-4a Step 3, Layer 4): even
    if a cross-vertical saved view exists in storage (pre-Step-3
    contamination, or a future bug that bypasses the seed +
    creation gates), this read filter drops it before returning to
    the caller. The migration r62 cleans up existing contamination;
    this filter prevents leak in transit. Reference:
    BRIDGEABLE_MASTER §3.25 saved view vertical-scope inheritance
    amendment.
    """
    from app.models.company import Company
    from app.services.saved_views import registry as registry_mod

    company = db.query(Company).filter(Company.id == user.company_id).first()
    tenant_vertical = (
        getattr(company, "vertical", None) if company else None
    )

    q = db.query(VaultItem).filter(
        VaultItem.company_id == user.company_id,
        VaultItem.item_type == "saved_view",
        VaultItem.is_active.is_(True),
    )
    # Optional JSONB filter by entity_type — Postgres supports this.
    if entity_type is not None:
        q = q.filter(
            VaultItem.metadata_json["saved_view_config"]["query"]["entity_type"].astext
            == entity_type
        )
    # Use the partial index from r32.
    q = q.order_by(VaultItem.updated_at.desc())
    rows = q.all()

    out: list[SavedView] = []
    for row in rows:
        try:
            sv = _row_to_saved_view(row)
        except SavedViewError as exc:
            # Skip malformed rows rather than fail the whole list
            # — log and move on. Malformed rows should never exist
            # in prod, but defensive.
            logger.exception("Skipping malformed saved view %s: %s", row.id, exc)
            continue
        # Pattern A: drop cross-vertical instances at read time.
        if not registry_mod.is_entity_compatible_with_vertical(
            sv.config.query.entity_type, tenant_vertical
        ):
            logger.warning(
                "saved_views.list: filtered cross-vertical row %s "
                "(entity_type=%s) from tenant %s vertical=%s",
                row.id,
                sv.config.query.entity_type,
                user.company_id,
                tenant_vertical,
            )
            continue
        if _can_user_see(db, user, row, sv.config):
            out.append(sv)
    return out


def update_saved_view(
    db: Session,
    *,
    user: User,
    view_id: str,
    title: str | None = None,
    description: str | None = None,
    config: SavedViewConfig | None = None,
) -> SavedView:
    """Update title / description / config. Owner or super_admin only.

    Returns the refreshed SavedView.
    """
    row = _get_row(db, view_id)
    if row is None:
        raise SavedViewNotFound(view_id)
    current = _row_to_saved_view(row)
    if not _can_user_edit(db, user, row, current.config):
        raise SavedViewPermissionDenied(view_id, "editor permission required")

    if title is not None:
        stripped = title.strip()
        if not stripped:
            raise SavedViewError("title cannot be empty")
        row.title = stripped
    if description is not None:
        row.description = description
    if config is not None:
        # Force owner — don't trust client-supplied config to change
        # ownership of an existing view.
        config.permissions.owner_user_id = current.config.permissions.owner_user_id
        row.metadata_json = {
            **(row.metadata_json or {}),
            "saved_view_config": config.to_dict(),
        }

    db.commit()
    db.refresh(row)
    return _row_to_saved_view(row)


def delete_saved_view(db: Session, *, user: User, view_id: str) -> bool:
    """Soft-delete. Only the owner or super_admin may delete.

    Returns True. Raises SavedViewNotFound or SavedViewPermissionDenied.
    """
    row = _get_row(db, view_id)
    if row is None:
        raise SavedViewNotFound(view_id)
    current = _row_to_saved_view(row)
    if not _can_user_edit(db, user, row, current.config):
        raise SavedViewPermissionDenied(view_id, "owner permission required")
    row.is_active = False
    db.commit()
    return True


def duplicate_saved_view(
    db: Session,
    *,
    user: User,
    view_id: str,
    new_title: str,
) -> SavedView:
    """Duplicate an existing view into a new SavedView OWNED BY THE
    CALLER (not the source's owner).

    This is the canonical path to personalizing a shared or seeded
    view — user duplicates it into their own private copy and edits
    the copy.
    """
    row = _get_row(db, view_id)
    if row is None:
        raise SavedViewNotFound(view_id)
    current = _row_to_saved_view(row)
    if not _can_user_see(db, user, row, current.config):
        raise SavedViewPermissionDenied(view_id, "cannot duplicate a view you can't see")

    # New permissions: private + owned by caller.
    new_perms = Permissions(
        owner_user_id=user.id,
        visibility="private",
        shared_with_users=[],
        shared_with_roles=[],
        shared_with_tenants=[],
    )
    new_config = SavedViewConfig(
        query=current.config.query,
        presentation=current.config.presentation,
        permissions=new_perms,
        extras=dict(current.config.extras),
    )
    return create_saved_view(
        db,
        user=user,
        title=new_title,
        description=current.description,
        config=new_config,
    )
