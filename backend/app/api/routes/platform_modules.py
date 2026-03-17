"""Platform admin — module definitions, vertical presets, and tenant module management."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require_platform_role
from app.database import get_db
from app.models.platform_user import PlatformUser
from app.services import tenant_module_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SetModuleRequest(BaseModel):
    enabled: bool


class ApplyPresetRequest(BaseModel):
    preset_key: str


class BulkModulesRequest(BaseModel):
    module_keys: list[str]


class CreateTenantRequest(BaseModel):
    name: str
    slug: str
    vertical: str | None = None
    admin_email: str
    admin_password: str
    admin_first_name: str = "Admin"
    admin_last_name: str = "User"


# ---------------------------------------------------------------------------
# Module definitions
# ---------------------------------------------------------------------------


@router.get("/definitions")
def list_definitions(
    _user: PlatformUser = Depends(require_platform_role("super_admin", "support", "viewer")),
    db: Session = Depends(get_db),
):
    """List all module definitions."""
    return tenant_module_service.get_modules_by_category(db)


@router.get("/definitions/flat")
def list_definitions_flat(
    _user: PlatformUser = Depends(require_platform_role("super_admin", "support", "viewer")),
    db: Session = Depends(get_db),
):
    """List all module definitions as a flat list."""
    modules = tenant_module_service.list_module_definitions(db)
    return [
        {
            "key": m.key,
            "name": m.name,
            "description": m.description,
            "category": m.category,
            "icon": m.icon,
            "is_core": m.is_core,
            "dependencies": m.dependency_list,
            "sort_order": m.sort_order,
        }
        for m in modules
    ]


# ---------------------------------------------------------------------------
# Vertical presets
# ---------------------------------------------------------------------------


@router.get("/presets")
def list_presets(
    _user: PlatformUser = Depends(require_platform_role("super_admin", "support", "viewer")),
    db: Session = Depends(get_db),
):
    """List all vertical presets with their module lists."""
    return tenant_module_service.list_presets(db)


@router.get("/presets/{preset_key}")
def get_preset(
    preset_key: str,
    _user: PlatformUser = Depends(require_platform_role("super_admin", "support", "viewer")),
    db: Session = Depends(get_db),
):
    """Get a single preset by key."""
    result = tenant_module_service.get_preset(db, preset_key)
    if not result:
        raise HTTPException(status_code=404, detail="Preset not found")
    return result


# ---------------------------------------------------------------------------
# Tenant module management
# ---------------------------------------------------------------------------


@router.get("/tenants/{tenant_id}")
def get_tenant_modules(
    tenant_id: str,
    _user: PlatformUser = Depends(require_platform_role("super_admin", "support", "viewer")),
    db: Session = Depends(get_db),
):
    """Get all modules with their enabled/disabled state for a tenant."""
    return tenant_module_service.get_tenant_modules(db, tenant_id)


@router.put("/tenants/{tenant_id}/{module_key}")
def set_tenant_module(
    tenant_id: str,
    module_key: str,
    data: SetModuleRequest,
    user: PlatformUser = Depends(require_platform_role("super_admin")),
    db: Session = Depends(get_db),
):
    """Enable or disable a single module for a tenant."""
    return tenant_module_service.set_tenant_module(
        db, tenant_id, module_key, data.enabled, actor_id=user.id
    )


@router.post("/tenants/{tenant_id}/preset")
def apply_preset(
    tenant_id: str,
    data: ApplyPresetRequest,
    user: PlatformUser = Depends(require_platform_role("super_admin")),
    db: Session = Depends(get_db),
):
    """Apply a vertical preset to a tenant."""
    return tenant_module_service.apply_preset_to_tenant(
        db, tenant_id, data.preset_key, actor_id=user.id
    )


@router.post("/tenants/{tenant_id}/bulk")
def bulk_set_modules(
    tenant_id: str,
    data: BulkModulesRequest,
    user: PlatformUser = Depends(require_platform_role("super_admin")),
    db: Session = Depends(get_db),
):
    """Set the complete list of enabled modules for a tenant."""
    return tenant_module_service.bulk_set_tenant_modules(
        db, tenant_id, data.module_keys, actor_id=user.id
    )


# ---------------------------------------------------------------------------
# Tenant onboarding
# ---------------------------------------------------------------------------


@router.post("/onboard", status_code=201)
def onboard_tenant(
    data: CreateTenantRequest,
    user: PlatformUser = Depends(require_platform_role("super_admin")),
    db: Session = Depends(get_db),
):
    """Create a new tenant with initial admin user and optional vertical preset.

    This is the single entry point for tenant onboarding from the platform admin.
    """
    from app.core.security import hash_password as get_password_hash
    from app.models.company import Company
    from app.models.user import User
    from app.services.module_service import seed_company_modules

    # Check slug uniqueness
    existing = db.query(Company).filter(Company.slug == data.slug).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Slug '{data.slug}' already taken")

    # Check email uniqueness
    existing_user = db.query(User).filter(User.email == data.admin_email).first()
    if existing_user:
        raise HTTPException(status_code=409, detail=f"Email '{data.admin_email}' already in use")

    # Create company
    company = Company(
        name=data.name,
        slug=data.slug,
        vertical=data.vertical,
        is_active=True,
    )
    db.add(company)
    db.flush()

    # Seed legacy company_modules (keeps backward compat)
    seed_company_modules(db, company.id)

    # Create admin user
    from app.models.role import Role
    admin_role = db.query(Role).filter(
        Role.company_id == company.id, Role.name == "Admin"
    ).first()

    # If no admin role, create one
    if not admin_role:
        admin_role = Role(
            company_id=company.id,
            name="Admin",
            description="Full access administrator",
        )
        db.add(admin_role)
        db.flush()

    admin_user = User(
        email=data.admin_email,
        hashed_password=get_password_hash(data.admin_password),
        first_name=data.admin_first_name,
        last_name=data.admin_last_name,
        company_id=company.id,
        role_id=admin_role.id,
        is_active=True,
    )
    db.add(admin_user)
    db.flush()

    # Apply vertical preset if specified
    result = {"tenant_id": company.id, "slug": company.slug}
    if data.vertical and data.vertical != "custom":
        preset_result = tenant_module_service.apply_preset_to_tenant(
            db, company.id, data.vertical, actor_id=user.id
        )
        result["modules_enabled"] = preset_result["modules_enabled"]

        # Also enable the vertical's module in legacy company_modules table
        # so require_module() checks pass
        from app.models.company_module import CompanyModule
        vertical_module_map = {
            "funeral_home": "funeral_home",
            "manufacturing": "work_orders",
        }
        legacy_module = vertical_module_map.get(data.vertical)
        if legacy_module:
            legacy_rec = db.query(CompanyModule).filter(
                CompanyModule.company_id == company.id,
                CompanyModule.module == legacy_module,
            ).first()
            if legacy_rec:
                legacy_rec.enabled = True
            else:
                db.add(CompanyModule(
                    company_id=company.id, module=legacy_module, enabled=True
                ))
    else:
        # Just enable core modules
        tenant_module_service.apply_preset_to_tenant(
            db, company.id, "custom", actor_id=user.id
        )
        result["modules_enabled"] = 4  # core modules

    db.commit()
    return result
