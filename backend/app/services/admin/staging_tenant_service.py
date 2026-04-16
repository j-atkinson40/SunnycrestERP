"""Staging tenant creator — seeded tenant for testing/demos.

Safety: refuses to run if pointed at production database.
"""

import os
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.admin_staging_tenant import AdminStagingTenant
from app.models.company import Company
from app.models.platform_user import PlatformUser
from app.models.user import User


PRESETS = {
    "manufacturing_standard": {
        "label": "Standard Manufacturing",
        "vertical": "manufacturing",
        "description": "Realistic production data for a Wilbert licensee",
        "seed_orders": 15,
        "seed_products": 25,
        "seed_users": 4,
        "seed_vault_items": 10,
    },
    "manufacturing_minimal": {
        "label": "Minimal Manufacturing",
        "vertical": "manufacturing",
        "description": "Bare minimum to login",
        "seed_orders": 0,
        "seed_products": 3,
        "seed_users": 1,
        "seed_vault_items": 0,
    },
    "manufacturing_demo": {
        "label": "Demo Manufacturing",
        "vertical": "manufacturing",
        "description": "Clean polished demo data",
        "seed_orders": 8,
        "seed_products": 15,
        "seed_users": 3,
        "seed_vault_items": 5,
    },
    "funeral_home_standard": {
        "label": "Standard Funeral Home",
        "vertical": "funeral_home",
        "description": "Realistic funeral home with active cases",
        "seed_cases": 20,
        "seed_users": 4,
    },
    "cemetery_standard": {
        "label": "Standard Cemetery",
        "vertical": "cemetery",
        "description": "Cemetery with plots + sections",
        "seed_users": 3,
    },
    "crematory_standard": {
        "label": "Standard Crematory",
        "vertical": "crematory",
        "description": "Crematory with active cases",
        "seed_users": 3,
    },
}


def _verify_staging_environment():
    """Hard safety check: refuse to run in production.

    Raises immediately if DATABASE_URL contains 'production' or environment is not staging/dev.
    """
    env = os.getenv("ENVIRONMENT", "dev").lower()
    db_url = os.getenv("DATABASE_URL", "").lower()
    if env == "production":
        raise RuntimeError(
            "SAFETY: Refusing to create staging tenant — ENVIRONMENT=production"
        )
    # Also refuse if DATABASE_URL looks like production (heuristic)
    if "production" in db_url or "prod-" in db_url:
        raise RuntimeError(
            "SAFETY: Refusing to create staging tenant — DATABASE_URL appears to be production"
        )


def list_presets() -> list[dict]:
    return [
        {"key": k, **v} for k, v in PRESETS.items()
    ]


def create_staging_tenant(
    db: Session,
    admin: PlatformUser,
    vertical: str,
    preset: str,
    company_name: str | None = None,
) -> dict:
    """Create a fully seeded staging tenant. Returns company_id + credentials.

    Safety: verifies environment before any writes.
    """
    _verify_staging_environment()

    if preset not in PRESETS:
        raise ValueError(f"Unknown preset: {preset}")

    preset_cfg = PRESETS[preset]
    if preset_cfg["vertical"] != vertical:
        raise ValueError(f"Preset {preset} is for vertical {preset_cfg['vertical']}, not {vertical}")

    # Auto-generate tenant name + slug if not provided
    short_id = str(uuid.uuid4())[:8]
    name = company_name or f"Bridgeable Test {vertical.title()} {short_id}"
    slug = f"test-{vertical}-{short_id}".lower().replace("_", "-")

    # Create company
    company = Company(
        id=str(uuid.uuid4()),
        name=name,
        slug=slug,
        is_active=True,
        vertical=vertical,
    )
    db.add(company)
    db.flush()

    # Create admin user + temp password
    temp_password = secrets.token_urlsafe(12)
    admin_email = f"admin+{short_id}@getbridgeable.com"
    admin_user = User(
        id=str(uuid.uuid4()),
        company_id=company.id,
        email=admin_email,
        hashed_password=hash_password(temp_password),
        first_name="Test",
        last_name="Admin",
        role="admin",
        is_active=True,
    )
    db.add(admin_user)

    # Additional seed users based on preset
    seed_users_cnt = preset_cfg.get("seed_users", 1)
    created_users = [{"email": admin_email, "password": temp_password, "role": "admin"}]
    role_templates = [
        ("office", "office"),
        ("driver", "driver"),
        ("production", "production"),
    ]
    for i in range(min(seed_users_cnt - 1, len(role_templates))):
        rname, rkey = role_templates[i]
        u_email = f"{rname}+{short_id}@getbridgeable.com"
        u_pw = secrets.token_urlsafe(12)
        u = User(
            id=str(uuid.uuid4()),
            company_id=company.id,
            email=u_email,
            hashed_password=hash_password(u_pw),
            first_name="Test",
            last_name=rname.title(),
            role=rkey,
            is_active=True,
        )
        db.add(u)
        created_users.append({"email": u_email, "password": u_pw, "role": rkey})

    # Record staging tenant provenance
    staging_record = AdminStagingTenant(
        company_id=company.id,
        created_by_admin_id=admin.id,
        vertical=vertical,
        preset=preset,
        temp_admin_email=admin_email,
        temp_admin_password=temp_password,
    )
    db.add(staging_record)

    db.commit()
    db.refresh(company)
    db.refresh(staging_record)

    return {
        "company_id": company.id,
        "tenant_slug": company.slug,
        "company_name": company.name,
        "vertical": vertical,
        "preset": preset,
        "users": created_users,
        "staging_record_id": staging_record.id,
        "login_url": f"https://{company.slug}.getbridgeable.com",
    }


def list_staging_tenants(db: Session, limit: int = 50) -> list[AdminStagingTenant]:
    return (
        db.query(AdminStagingTenant)
        .filter(AdminStagingTenant.is_archived == False)  # noqa: E712
        .order_by(AdminStagingTenant.created_at.desc())
        .limit(limit)
        .all()
    )


def archive_staging_tenant(db: Session, staging_id: str) -> AdminStagingTenant:
    rec = db.query(AdminStagingTenant).filter(AdminStagingTenant.id == staging_id).first()
    if not rec:
        raise ValueError("Staging tenant not found")
    rec.is_archived = True
    db.commit()
    db.refresh(rec)
    return rec
