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
    initial_settings: dict | None = None  # e.g. {"spring_burials_enabled": true}
    website_url: str | None = None


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
    import json as _json
    company = Company(
        name=data.name,
        slug=data.slug,
        vertical=data.vertical,
        is_active=True,
        settings_json=_json.dumps(data.initial_settings) if data.initial_settings else None,
    )
    db.add(company)
    db.flush()

    # Seed default roles
    from app.services.role_service import seed_default_roles
    admin_role, _employee_role = seed_default_roles(db, company.id)

    # Seed legacy company_modules — all disabled initially, then enable per vertical
    from app.models.company_module import CompanyModule
    from app.core.modules import AVAILABLE_MODULES
    for module_key in AVAILABLE_MODULES:
        db.add(CompanyModule(
            company_id=company.id,
            module=module_key,
            enabled=(module_key == "core"),  # only core enabled by default
        ))
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

    # Enable modules based on vertical
    # Each vertical gets only the modules it needs
    VERTICAL_MODULES = {
        "funeral_home": ["core", "funeral_home"],
        "manufacturing": ["core", "sales", "purchasing", "inventory", "daily_production_log",
                          "driver_delivery", "safety_management"],
    }

    result = {"tenant_id": company.id, "slug": company.slug}
    modules_to_enable = VERTICAL_MODULES.get(
        data.vertical or "custom",
        ["core", "products", "inventory", "sales", "purchasing"],  # default/custom
    )

    for mod_key in modules_to_enable:
        rec = db.query(CompanyModule).filter(
            CompanyModule.company_id == company.id,
            CompanyModule.module == mod_key,
        ).first()
        if rec:
            rec.enabled = True
        else:
            db.add(CompanyModule(
                company_id=company.id, module=mod_key, enabled=True
            ))
    result["modules_enabled"] = len(modules_to_enable)

    # Try applying the new-style preset too (for TenantModuleConfig)
    try:
        tenant_module_service.apply_preset_to_tenant(
            db, company.id, data.vertical or "custom", actor_id=user.id
        )
    except Exception:
        pass  # Non-fatal if preset not seeded yet

    # Seed vertical-specific data
    if data.vertical == "funeral_home":
        from app.services.ftc_compliance_service import seed_ftc_price_list
        seed_ftc_price_list(db, company.id)

    # Initialize onboarding checklist
    try:
        from app.services.onboarding_service import initialize_checklist
        preset = data.vertical or "manufacturing"
        initialize_checklist(db, company.id, preset)
        result["onboarding_initialized"] = True
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to initialize onboarding: {e}")
        result["onboarding_initialized"] = False

    # Kick off website intelligence if URL provided
    if data.website_url:
        try:
            from app.models.website_intelligence import TenantWebsiteIntelligence

            intel = TenantWebsiteIntelligence(
                tenant_id=company.id,
                website_url=data.website_url,
                scrape_status="pending",
            )
            db.add(intel)
            db.flush()
            result["website_intelligence"] = "pending"
        except Exception as e:
            import logging as _logging

            _logging.getLogger(__name__).warning(
                f"Failed to create website intelligence record: {e}"
            )

    db.commit()

    # Start background scrape after commit (needs committed tenant_id)
    if data.website_url:
        try:
            import threading
            import logging as _logging
            _log = _logging.getLogger("website_intelligence")

            # Quick network diagnostic (synchronous, fast)
            try:
                import requests as _req
                _log.info(f"Testing connectivity to {data.website_url}...")
                test_resp = _req.head(
                    data.website_url,
                    timeout=10,
                    allow_redirects=True,
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                _log.info(f"Connectivity OK: {test_resp.status_code} from {test_resp.url}")
                result["network_test"] = f"OK: {test_resp.status_code}"
            except Exception as net_err:
                import traceback
                root = net_err
                while root.__cause__ or root.__context__:
                    root = root.__cause__ or root.__context__
                detail = f"{type(net_err).__name__}: {net_err} | Root: {type(root).__name__}: {root}"
                _log.error(f"Connectivity FAILED: {detail}")
                _log.error(traceback.format_exc())
                result["network_test"] = f"FAILED: {detail}"

                # Store the detailed error directly on the intelligence record
                from app.models.website_intelligence import TenantWebsiteIntelligence
                intel_rec = db.query(TenantWebsiteIntelligence).filter(
                    TenantWebsiteIntelligence.tenant_id == company.id
                ).first()
                if intel_rec:
                    intel_rec.scrape_status = "failed"
                    intel_rec.error_message = detail[:2000]
                    db.commit()

            def _run_scrape_background(tid: str, url: str):
                _log.info(f"Background scrape starting for tenant {tid}: {url}")
                try:
                    from app.services.website_intelligence_job import (
                        run_website_intelligence,
                    )
                    run_website_intelligence(None, tid, url)
                    _log.info(f"Background scrape completed for tenant {tid}")
                except Exception as exc:
                    import traceback as _tb
                    _log.error(f"Background scrape FAILED for tenant {tid}: {exc}")
                    _log.error(_tb.format_exc())

            # Only start background scrape if network test passed
            if "OK" in result.get("network_test", ""):
                thread = threading.Thread(
                    target=_run_scrape_background,
                    args=(company.id, data.website_url),
                    daemon=True,
                )
                thread.start()
                _log.info(f"Background scrape thread started for {company.id}")
            else:
                _log.warning("Skipping background scrape — network test failed")
        except Exception as e:
            import logging as _logging
            _logging.getLogger(__name__).warning(
                f"Failed to start website intelligence: {e}"
            )

    return result
