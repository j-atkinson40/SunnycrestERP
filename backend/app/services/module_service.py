from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.modules import AVAILABLE_MODULES, get_default_enabled_modules
from app.models.company_module import CompanyModule
from app.services import audit_service


def seed_company_modules(db: Session, company_id: str) -> list[CompanyModule]:
    """Create default module records for a new company. Idempotent."""
    existing = (
        db.query(CompanyModule.module)
        .filter(CompanyModule.company_id == company_id)
        .all()
    )
    existing_keys = {row[0] for row in existing}
    default_enabled = set(get_default_enabled_modules())

    modules = []
    for module_key in AVAILABLE_MODULES:
        if module_key not in existing_keys:
            mod = CompanyModule(
                company_id=company_id,
                module=module_key,
                enabled=module_key in default_enabled,
            )
            db.add(mod)
            modules.append(mod)

    if modules:
        db.flush()
    return modules


def get_company_modules(db: Session, company_id: str) -> list[dict]:
    """Return all modules with their enabled status and metadata."""
    records = (
        db.query(CompanyModule)
        .filter(CompanyModule.company_id == company_id)
        .all()
    )
    record_map = {r.module: r for r in records}

    result = []
    for module_key, meta in AVAILABLE_MODULES.items():
        record = record_map.get(module_key)
        result.append({
            "module": module_key,
            "enabled": record.enabled if record else meta["default_enabled"],
            "label": meta["label"],
            "description": meta["description"],
            "locked": meta.get("locked", False),
        })
    return result


def get_enabled_module_keys(db: Session, company_id: str) -> list[str]:
    """Return just the list of enabled module keys for a company.

    Falls back to AVAILABLE_MODULES default_enabled for modules that have
    no explicit CompanyModule record (i.e. the company pre-dates that module).
    """
    records = (
        db.query(CompanyModule)
        .filter(CompanyModule.company_id == company_id)
        .all()
    )
    record_map = {r.module: r.enabled for r in records}

    enabled = []
    for module_key, meta in AVAILABLE_MODULES.items():
        if module_key in record_map:
            if record_map[module_key]:
                enabled.append(module_key)
        elif meta.get("default_enabled"):
            enabled.append(module_key)
    return enabled


def is_module_enabled(db: Session, company_id: str, module: str) -> bool:
    """Check if a specific module is enabled for a company."""
    record = (
        db.query(CompanyModule)
        .filter(
            CompanyModule.company_id == company_id,
            CompanyModule.module == module,
        )
        .first()
    )
    if not record:
        # If no record exists, check default
        meta = AVAILABLE_MODULES.get(module)
        return meta["default_enabled"] if meta else False
    return record.enabled


def update_module_status(
    db: Session,
    company_id: str,
    module: str,
    enabled: bool,
    actor_id: str | None = None,
) -> CompanyModule:
    """Enable or disable a module for a company."""
    meta = AVAILABLE_MODULES.get(module)
    if not meta:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown module: {module}",
        )

    if meta.get("locked") and not enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Module '{module}' cannot be disabled",
        )

    record = (
        db.query(CompanyModule)
        .filter(
            CompanyModule.company_id == company_id,
            CompanyModule.module == module,
        )
        .first()
    )

    if not record:
        record = CompanyModule(
            company_id=company_id,
            module=module,
            enabled=enabled,
        )
        db.add(record)
    else:
        record.enabled = enabled

    audit_service.log_action(
        db, company_id, "updated", "company_module", record.id,
        user_id=actor_id,
        changes={"module": module, "enabled": enabled},
    )

    db.commit()
    db.refresh(record)
    return record
