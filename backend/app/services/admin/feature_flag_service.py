"""Admin feature flag service with per-tenant overrides."""

from sqlalchemy.orm import Session

from app.models.admin_feature_flag import AdminFeatureFlag, AdminFeatureFlagOverride


def list_flags(db: Session) -> list[dict]:
    flags = db.query(AdminFeatureFlag).order_by(AdminFeatureFlag.category, AdminFeatureFlag.flag_key).all()
    out = []
    for f in flags:
        overrides = (
            db.query(AdminFeatureFlagOverride)
            .filter(AdminFeatureFlagOverride.flag_key == f.flag_key)
            .all()
        )
        out.append({
            "flag_key": f.flag_key,
            "description": f.description,
            "default_enabled": f.default_enabled,
            "category": f.category,
            "overrides": [
                {"company_id": o.company_id, "is_enabled": o.is_enabled}
                for o in overrides
            ],
        })
    return out


def set_default(db: Session, flag_key: str, default_enabled: bool) -> AdminFeatureFlag:
    flag = db.query(AdminFeatureFlag).filter(AdminFeatureFlag.flag_key == flag_key).first()
    if not flag:
        raise ValueError(f"Flag not found: {flag_key}")
    flag.default_enabled = default_enabled
    db.commit()
    db.refresh(flag)
    return flag


def set_override(
    db: Session,
    flag_key: str,
    company_id: str,
    is_enabled: bool,
    admin_id: str | None = None,
) -> AdminFeatureFlagOverride:
    flag = db.query(AdminFeatureFlag).filter(AdminFeatureFlag.flag_key == flag_key).first()
    if not flag:
        raise ValueError(f"Flag not found: {flag_key}")

    override = (
        db.query(AdminFeatureFlagOverride)
        .filter(
            AdminFeatureFlagOverride.flag_key == flag_key,
            AdminFeatureFlagOverride.company_id == company_id,
        )
        .first()
    )
    if override:
        override.is_enabled = is_enabled
        override.set_by_admin_id = admin_id
    else:
        override = AdminFeatureFlagOverride(
            flag_key=flag_key,
            company_id=company_id,
            is_enabled=is_enabled,
            set_by_admin_id=admin_id,
        )
        db.add(override)
    db.commit()
    db.refresh(override)
    return override


def remove_override(db: Session, flag_key: str, company_id: str) -> bool:
    override = (
        db.query(AdminFeatureFlagOverride)
        .filter(
            AdminFeatureFlagOverride.flag_key == flag_key,
            AdminFeatureFlagOverride.company_id == company_id,
        )
        .first()
    )
    if not override:
        return False
    db.delete(override)
    db.commit()
    return True


def is_enabled_for(db: Session, flag_key: str, company_id: str) -> bool:
    """Override takes precedence over default. Returns False if flag missing."""
    override = (
        db.query(AdminFeatureFlagOverride)
        .filter(
            AdminFeatureFlagOverride.flag_key == flag_key,
            AdminFeatureFlagOverride.company_id == company_id,
        )
        .first()
    )
    if override:
        return override.is_enabled
    flag = db.query(AdminFeatureFlag).filter(AdminFeatureFlag.flag_key == flag_key).first()
    return flag.default_enabled if flag else False
