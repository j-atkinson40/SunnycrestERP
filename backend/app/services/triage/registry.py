"""Triage queue config registry.

Two-tier resolution:

  1. PLATFORM DEFAULTS — in-code constants in `_PLATFORM_CONFIGS`
     seeded via `scripts/seed_triage_queues.py` which calls
     `register_platform_config(cfg)`. Same pattern as Phase 1's
     command_bar.registry — a module-level singleton keyed by
     queue_id. Avoids the VaultItem company_id NOT NULL constraint
     (VaultItem is per-tenant; platform configs are cross-tenant).
  2. TENANT OVERRIDES — `vault_items` rows with
       item_type = "triage_queue_config"
       source_entity_id = queue_id
       metadata_json.triage_queue_config = full Pydantic-validated shape
     When a tenant customizes a platform default, they store an
     override vault_item with the same queue_id; the registry
     prefers it over the platform default.

Loading strategy:
  - Called per request — no process-wide cache. Config count is
    tiny (<10 per tenant), loads cheap, freshness matters.
  - `list_queues_for_user` filters by permission + extension +
    vertical — the user sees only queues they can access.
  - Pydantic validation on override load. Malformed overrides log
    a warning and fall back to the platform default.

Seeding:
  - `scripts/seed_triage_queues.py` calls `register_platform_config`
    for every shipped queue. Idempotent — re-registering replaces.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.vault_item import VaultItem
from app.services.triage.types import (
    QueueNotFound,
    TriageQueueConfig,
)

logger = logging.getLogger(__name__)


# Sentinel values
ITEM_TYPE: str = "triage_queue_config"
METADATA_KEY: str = "triage_queue_config"


# ── Platform defaults (in-code singleton) ───────────────────────────


_PLATFORM_CONFIGS: dict[str, TriageQueueConfig] = {}


def register_platform_config(config: TriageQueueConfig) -> None:
    """Register or replace a platform-default config. Idempotent by
    queue_id. Called by the seed script."""
    _PLATFORM_CONFIGS[config.queue_id] = config


def reset_platform_configs() -> None:
    """Test helper — clear the in-code registry."""
    _PLATFORM_CONFIGS.clear()


def list_platform_configs() -> list[TriageQueueConfig]:
    return list(_PLATFORM_CONFIGS.values())


# ── Tenant overrides (vault_items) ──────────────────────────────────


def _parse_override(vault_item: VaultItem) -> TriageQueueConfig | None:
    raw = (vault_item.metadata_json or {}).get(METADATA_KEY)
    if not isinstance(raw, dict):
        logger.warning(
            "triage queue override missing `%s` key on vault_item %s",
            METADATA_KEY, vault_item.id,
        )
        return None
    try:
        return TriageQueueConfig.from_dict(raw)
    except Exception:
        logger.exception(
            "Malformed triage queue override on vault_item %s", vault_item.id
        )
        return None


def _tenant_overrides(
    db: Session, *, company_id: str
) -> dict[str, TriageQueueConfig]:
    """Return {queue_id: TriageQueueConfig} for every valid override
    vault_item this tenant has. Invalid rows are silently skipped."""
    rows = (
        db.query(VaultItem)
        .filter(
            VaultItem.company_id == company_id,
            VaultItem.item_type == ITEM_TYPE,
            VaultItem.is_active.is_(True),
        )
        .all()
    )
    out: dict[str, TriageQueueConfig] = {}
    for row in rows:
        cfg = _parse_override(row)
        if cfg is not None:
            out[cfg.queue_id] = cfg
    return out


def list_all_configs(
    db: Session, *, company_id: str
) -> list[TriageQueueConfig]:
    """Every config visible to the tenant: platform defaults merged
    with tenant overrides (overrides win on same queue_id). Ordered
    by display_order asc, then name."""
    merged: dict[str, TriageQueueConfig] = dict(_PLATFORM_CONFIGS)
    merged.update(_tenant_overrides(db, company_id=company_id))
    return sorted(
        merged.values(),
        key=lambda c: (c.display_order, c.queue_name.lower()),
    )


def get_config(
    db: Session, *, company_id: str, queue_id: str
) -> TriageQueueConfig:
    for cfg in list_all_configs(db, company_id=company_id):
        if cfg.queue_id == queue_id:
            return cfg
    raise QueueNotFound(f"Triage queue {queue_id!r} not found")


# ── Permission / visibility filter ──────────────────────────────────


def list_queues_for_user(
    db: Session, *, user: User
) -> list[TriageQueueConfig]:
    """Configs the user can access. Applies:
      - config.enabled
      - config.required_permission (all must pass)
      - config.required_vertical (company vertical match)
      - config.required_extension (tenant extension enabled)
      - super_admin bypasses all gates
    """
    all_configs = list_all_configs(db, company_id=user.company_id)
    if getattr(user, "is_super_admin", False):
        return [c for c in all_configs if c.enabled]
    from app.models.company import Company
    from app.services.permission_service import user_has_permission

    company = (
        db.query(Company).filter(Company.id == user.company_id).first()
    )
    company_vertical = getattr(company, "vertical", None) if company else None

    out: list[TriageQueueConfig] = []
    for cfg in all_configs:
        if not cfg.enabled:
            continue
        if (
            cfg.required_vertical
            and cfg.required_vertical != company_vertical
        ):
            continue
        if cfg.required_extension and not _tenant_has_extension(
            db, user.company_id, cfg.required_extension
        ):
            continue
        all_perms_granted = all(
            user_has_permission(user, db, p) for p in (cfg.permissions or [])
        )
        if not all_perms_granted:
            continue
        out.append(cfg)
    return out


def _tenant_has_extension(db: Session, company_id: str, key: str) -> bool:
    from app.models.tenant_extension import TenantExtension

    return (
        db.query(TenantExtension.id)
        .filter(
            TenantExtension.tenant_id == company_id,
            TenantExtension.extension_key == key,
        )
        .first()
        is not None
    )


# ── Persistence helper (tenant overrides only) ──────────────────────


def upsert_tenant_override(
    db: Session, *, company_id: str, config: TriageQueueConfig
) -> VaultItem:
    """Insert or update a per-tenant override for an existing
    queue_id. Phase 5 doesn't ship a UI for this yet — exposed for
    programmatic customization + future API."""
    import uuid

    from app.models.vault import Vault

    existing = (
        db.query(VaultItem)
        .filter(
            VaultItem.company_id == company_id,
            VaultItem.item_type == ITEM_TYPE,
            VaultItem.source_entity_id == config.queue_id,
        )
        .first()
    )
    payload: dict[str, Any] = {METADATA_KEY: config.to_dict()}
    if existing is None:
        vault = (
            db.query(Vault).filter(Vault.company_id == company_id).first()
        )
        if vault is None:
            raise RuntimeError(
                f"Cannot create triage override — tenant {company_id!r} "
                "has no Vault row. Provision the tenant's vault first."
            )
        new = VaultItem(
            id=str(uuid.uuid4()),
            vault_id=vault.id,
            company_id=company_id,
            item_type=ITEM_TYPE,
            title=config.queue_name,
            description=config.description or None,
            source="system_generated",
            source_entity_id=config.queue_id,
            metadata_json=payload,
            is_active=True,
        )
        db.add(new)
        db.commit()
        db.refresh(new)
        return new
    else:
        existing.title = config.queue_name
        existing.description = config.description or None
        existing.metadata_json = payload
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing


# Compat alias so the seed script's import name works for either
# approach without needing a rewrite if we move to vault_item-backed
# platform configs in a future schema change.
upsert_platform_config = register_platform_config  # type: ignore[assignment]


__all__ = [
    "ITEM_TYPE",
    "METADATA_KEY",
    "register_platform_config",
    "reset_platform_configs",
    "list_platform_configs",
    "list_all_configs",
    "get_config",
    "list_queues_for_user",
    "upsert_platform_config",
    "upsert_tenant_override",
]
