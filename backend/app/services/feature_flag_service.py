"""Feature flag service with in-memory TTL cache.

Cache can be swapped to Redis by replacing _cache with a Redis-backed dict.
Target: <2ms flag checks when cache is warm.
"""

import time
from threading import Lock

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.feature_flag import FeatureFlag
from app.models.flag_audit_log import FlagAuditLog
from app.models.tenant_feature_flag import TenantFeatureFlag

_CACHE_TTL = 60  # seconds
_cache: dict[str, tuple[float, dict[str, bool]]] = {}  # tenant_id -> (expires_at, {flag_key: enabled})
_global_cache: tuple[float, dict[str, bool]] | None = None  # (expires_at, {flag_key: default_enabled})
_lock = Lock()


def _invalidate_tenant(tenant_id: str) -> None:
    """Remove a tenant's cached flags."""
    with _lock:
        _cache.pop(tenant_id, None)


def _invalidate_global() -> None:
    """Clear the global defaults cache."""
    global _global_cache
    with _lock:
        _global_cache = None
        _cache.clear()


def _load_global_defaults(db: Session) -> dict[str, bool]:
    """Load all flag defaults from DB."""
    global _global_cache
    now = time.monotonic()

    with _lock:
        if _global_cache and _global_cache[0] > now:
            return _global_cache[1]

    flags = db.query(FeatureFlag).all()
    defaults = {f.key: f.default_enabled for f in flags}

    with _lock:
        _global_cache = (now + _CACHE_TTL, defaults)
    return defaults


def _load_tenant_flags(db: Session, tenant_id: str) -> dict[str, bool]:
    """Load resolved flags for a tenant (defaults + overrides)."""
    now = time.monotonic()

    with _lock:
        cached = _cache.get(tenant_id)
        if cached and cached[0] > now:
            return cached[1]

    defaults = _load_global_defaults(db)
    resolved = dict(defaults)

    overrides = (
        db.query(TenantFeatureFlag)
        .join(FeatureFlag, TenantFeatureFlag.flag_id == FeatureFlag.id)
        .filter(TenantFeatureFlag.tenant_id == tenant_id)
        .all()
    )
    # Need flag keys — query them
    if overrides:
        flag_ids = [o.flag_id for o in overrides]
        flag_map = {
            f.id: f.key
            for f in db.query(FeatureFlag).filter(FeatureFlag.id.in_(flag_ids)).all()
        }
        for o in overrides:
            key = flag_map.get(o.flag_id)
            if key:
                resolved[key] = o.enabled

    with _lock:
        _cache[tenant_id] = (now + _CACHE_TTL, resolved)
    return resolved


def is_enabled(db: Session, tenant_id: str, flag_key: str) -> bool:
    """Check if a feature flag is enabled for a tenant. <2ms when cached."""
    flags = _load_tenant_flags(db, tenant_id)
    # If flag doesn't exist, default to False
    return flags.get(flag_key, False)


def get_all_flags_for_tenant(db: Session, tenant_id: str) -> dict[str, bool]:
    """Get all resolved flags for a tenant."""
    return _load_tenant_flags(db, tenant_id)


def get_all_flags(db: Session) -> list[FeatureFlag]:
    """Get all global flag definitions."""
    return db.query(FeatureFlag).order_by(FeatureFlag.category, FeatureFlag.key).all()


def get_flag_by_key(db: Session, flag_key: str) -> FeatureFlag | None:
    """Get a single flag by key."""
    return db.query(FeatureFlag).filter(FeatureFlag.key == flag_key).first()


def create_flag(db: Session, data: dict) -> FeatureFlag:
    """Create a new feature flag."""
    flag = FeatureFlag(**data)
    db.add(flag)
    db.commit()
    db.refresh(flag)
    _invalidate_global()
    return flag


def update_flag(db: Session, flag_id: str, data: dict) -> FeatureFlag | None:
    """Update a feature flag's properties."""
    flag = db.query(FeatureFlag).filter(FeatureFlag.id == flag_id).first()
    if not flag:
        return None
    for k, v in data.items():
        if v is not None:
            setattr(flag, k, v)
    db.commit()
    db.refresh(flag)
    _invalidate_global()
    return flag


def delete_flag(db: Session, flag_id: str) -> bool:
    """Delete a feature flag and all its overrides."""
    flag = db.query(FeatureFlag).filter(FeatureFlag.id == flag_id).first()
    if not flag:
        return False
    db.query(TenantFeatureFlag).filter(TenantFeatureFlag.flag_id == flag_id).delete()
    db.delete(flag)
    db.commit()
    _invalidate_global()
    return True


def set_flag_for_tenant(
    db: Session,
    tenant_id: str,
    flag_id: str,
    enabled: bool,
    notes: str | None = None,
    actor_id: str | None = None,
) -> TenantFeatureFlag:
    """Set or update a feature flag override for a tenant."""
    override = (
        db.query(TenantFeatureFlag)
        .filter(
            TenantFeatureFlag.tenant_id == tenant_id,
            TenantFeatureFlag.flag_id == flag_id,
        )
        .first()
    )
    flag = db.query(FeatureFlag).filter(FeatureFlag.id == flag_id).first()
    flag_key = flag.key if flag else "unknown"

    if override:
        override.enabled = enabled
        if notes is not None:
            override.notes = notes
        override.updated_by = actor_id
    else:
        override = TenantFeatureFlag(
            tenant_id=tenant_id,
            flag_id=flag_id,
            enabled=enabled,
            notes=notes,
            updated_by=actor_id,
        )
        db.add(override)

    # Audit log
    action = "toggled_on" if enabled else "toggled_off"
    db.add(FlagAuditLog(
        tenant_id=tenant_id,
        flag_key=flag_key,
        action=action,
        user_id=actor_id,
        details=notes,
    ))

    db.commit()
    db.refresh(override)
    _invalidate_tenant(tenant_id)
    return override


def remove_override(
    db: Session,
    tenant_id: str,
    flag_id: str,
    actor_id: str | None = None,
) -> bool:
    """Remove a tenant's override so it falls back to default."""
    override = (
        db.query(TenantFeatureFlag)
        .filter(
            TenantFeatureFlag.tenant_id == tenant_id,
            TenantFeatureFlag.flag_id == flag_id,
        )
        .first()
    )
    if not override:
        return False

    flag = db.query(FeatureFlag).filter(FeatureFlag.id == flag_id).first()
    flag_key = flag.key if flag else "unknown"

    db.delete(override)
    db.add(FlagAuditLog(
        tenant_id=tenant_id,
        flag_key=flag_key,
        action="override_removed",
        user_id=actor_id,
    ))
    db.commit()
    _invalidate_tenant(tenant_id)
    return True


def bulk_set_flag(
    db: Session,
    flag_id: str,
    tenant_ids: list[str],
    enabled: bool,
    actor_id: str | None = None,
) -> int:
    """Set a flag for multiple tenants at once."""
    count = 0
    for tid in tenant_ids:
        set_flag_for_tenant(db, tid, flag_id, enabled, actor_id=actor_id)
        count += 1
    return count


def get_tenants_with_flag_enabled(db: Session, flag_key: str) -> list[str]:
    """Get list of tenant IDs where a flag is explicitly enabled."""
    flag = db.query(FeatureFlag).filter(FeatureFlag.key == flag_key).first()
    if not flag:
        return []
    overrides = (
        db.query(TenantFeatureFlag.tenant_id)
        .filter(
            TenantFeatureFlag.flag_id == flag.id,
            TenantFeatureFlag.enabled.is_(True),
        )
        .all()
    )
    return [o[0] for o in overrides]


def get_flag_matrix(db: Session) -> dict:
    """Get the tenant x flag toggle matrix for admin UI."""
    flags = get_all_flags(db)
    tenants = db.query(Company).order_by(Company.name).all()
    overrides = db.query(TenantFeatureFlag).all()

    override_map: dict[str, dict[str, bool]] = {}
    for o in overrides:
        override_map.setdefault(o.flag_id, {})[o.tenant_id] = o.enabled

    return {
        "flags": flags,
        "tenants": [{"id": t.id, "name": t.name} for t in tenants],
        "overrides": override_map,
    }


def log_blocked_request(
    db: Session,
    tenant_id: str,
    flag_key: str,
    endpoint: str,
    user_id: str | None = None,
) -> None:
    """Log when a request is blocked by a disabled feature flag."""
    db.add(FlagAuditLog(
        tenant_id=tenant_id,
        flag_key=flag_key,
        action="blocked",
        endpoint=endpoint,
        user_id=user_id,
    ))
    db.commit()


def get_audit_logs(
    db: Session,
    page: int = 1,
    per_page: int = 50,
    flag_key: str | None = None,
    tenant_id: str | None = None,
    action: str | None = None,
) -> dict:
    """Get paginated flag audit logs with optional filters."""
    query = db.query(FlagAuditLog)
    if flag_key:
        query = query.filter(FlagAuditLog.flag_key == flag_key)
    if tenant_id:
        query = query.filter(FlagAuditLog.tenant_id == tenant_id)
    if action:
        query = query.filter(FlagAuditLog.action == action)

    total = query.count()
    items = (
        query.order_by(FlagAuditLog.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {"items": items, "total": total, "page": page, "per_page": per_page}
