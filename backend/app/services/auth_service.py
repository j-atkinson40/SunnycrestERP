from fastapi import HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
    verify_pin,
)
from app.models.company import Company
from app.models.role import Role
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.company import CompanyRegisterRequest
from app.services import audit_service
from app.services.module_service import seed_company_modules
from app.services.role_service import seed_default_roles


def register_company(db: Session, data: CompanyRegisterRequest) -> dict:
    """Register a new company and its first admin user."""
    existing_company = (
        db.query(Company).filter(Company.slug == data.company_slug).first()
    )
    if existing_company:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Company slug already taken",
        )

    company = Company(name=data.company_name, slug=data.company_slug)
    db.add(company)
    db.flush()

    # Seed default roles and modules for the new company
    admin_role, _employee_role = seed_default_roles(db, company.id)
    seed_company_modules(db, company.id)

    existing_user = (
        db.query(User)
        .filter(User.email == data.email, User.company_id == company.id)
        .first()
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        first_name=data.first_name,
        last_name=data.last_name,
        role_id=admin_role.id,
        company_id=company.id,
    )
    db.add(user)

    # Create TenantHealthScore so the tenant appears on the operator dashboard
    try:
        import uuid as _uuid
        from app.models.tenant_health_score import TenantHealthScore
        health_row = TenantHealthScore(
            id=str(_uuid.uuid4()),
            tenant_id=str(company.id),
            score="unknown",
        )
        db.add(health_row)
    except Exception:
        pass  # non-critical — score will be created on first health calc

    db.commit()
    db.refresh(company)
    db.refresh(user)

    # Phase 8e.2.2 Space Invariant Enforcement — seed role-based
    # default spaces for the first admin of the new tenant. The other
    # Phase-2 / Phase-6 seeds (saved views, briefing prefs) aren't
    # plumbed through this path deliberately — `register_company` is
    # a greenfield-tenant path and the user lands on a dashboard
    # where those seeds aren't yet load-bearing. Spaces are the one
    # opinionated default that shows up immediately in the DotNav, so
    # this is the call site where absence of seeding is user-visible.
    # Best-effort — failures log structured warning but don't break
    # tenant registration.
    from app.services.spaces.seed import seed_spaces_best_effort

    seed_spaces_best_effort(db, user, call_site="register_company")

    # Phase W-3a — auto-seed default product lines per tenant vertical.
    # Per [BRIDGEABLE_MASTER §5.2.1](../../BRIDGEABLE_MASTER.md): vault
    # is the auto-seeded baseline for every manufacturing-vertical
    # tenant, NOT extension-gated. Other verticals get their own
    # baseline (funeral_services for funeral_home, etc.).
    # Best-effort — per-line failures inside the helper don't propagate
    # but a top-level exception here would still be defensive (log +
    # continue) so registration completes.
    try:
        from app.services import product_line_service

        product_line_service.seed_default_product_lines(db, company)
    except Exception:
        # Mirror the spaces-seed defensive pattern. The helper itself
        # logs per-line failures; this catch is for unexpected import /
        # session errors.
        import logging
        logging.getLogger(__name__).exception(
            "Failed to seed default product lines for company %s",
            company.id,
        )
        try:
            db.rollback()
        except Exception:
            pass

    return {"company": company, "user": user}


def register_user(db: Session, data: RegisterRequest, company: Company) -> User:
    """Register a user within an existing company."""
    existing = (
        db.query(User)
        .filter(User.email == data.email, User.company_id == company.id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered in this company",
        )

    # First user in this company becomes admin, otherwise employee
    company_user_count = (
        db.query(User).filter(User.company_id == company.id).count()
    )
    role_slug = "admin" if company_user_count == 0 else "employee"
    role = (
        db.query(Role)
        .filter(
            Role.company_id == company.id,
            Role.slug == role_slug,
            Role.is_system == True,  # noqa: E712
        )
        .first()
    )
    if not role:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"System role '{role_slug}' not found for company",
        )

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        first_name=data.first_name,
        last_name=data.last_name,
        role_id=role.id,
        company_id=company.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Saved Views Phase 2: seed role-based default views for the new
    # user. Idempotent + best-effort — a seed failure must never
    # block user registration. Same defensive pattern as V-1d
    # notification fan-outs.
    try:
        from app.services.saved_views.seed import seed_for_user as seed_saved_views

        seed_saved_views(db, user=user)
    except Exception:  # pragma: no cover — best-effort
        import logging
        logging.getLogger(__name__).exception(
            "Saved views seed failed for newly-registered user %s (non-fatal)",
            user.id,
        )

    # Spaces Phase 3: seed role-based default spaces + pins. Same
    # defensive pattern. Runs AFTER saved-view seeding so seed_key
    # pins can resolve to the user's freshly-created saved views.
    try:
        from app.services.spaces.seed import seed_for_user as seed_spaces

        seed_spaces(db, user=user)
    except Exception:  # pragma: no cover — best-effort
        import logging
        logging.getLogger(__name__).exception(
            "Spaces seed failed for newly-registered user %s (non-fatal)",
            user.id,
        )

    return user


def login_user(db: Session, data: LoginRequest, company: Company) -> TokenResponse:
    """Login scoped to a specific company. Supports email+password or username+PIN."""
    from datetime import datetime as dt, timezone as tz

    if data.email:
        # ── Office/Management track: email + password ──
        user = (
            db.query(User)
            .filter(User.email == data.email, User.company_id == company.id)
            .first()
        )
        if not user or not verify_password(data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
    else:
        # ── Production/Delivery track: username + PIN ──
        user = (
            db.query(User)
            .filter(
                User.username == data.username,
                User.company_id == company.id,
                User.track == "production_delivery",
            )
            .first()
        )
        if not user or not user.pin_encrypted or not verify_pin(data.pin, user.pin_encrypted):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or PIN",
            )
        # Update last console login
        user.last_console_login_at = dt.now(tz.utc)

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    # Phase 8e.2.2 Space Invariant Enforcement — defensive re-seed.
    # Phase 8e.2.3 — gate widened: fires when EITHER spaces is empty
    # OR spaces_seeded_for_roles is empty. Stronger invariant: a
    # user is "seeded" only when they've been through the seed flow
    # for their current role(s), not merely when they have some
    # spaces. This catches "James-shape" users who created spaces
    # manually before any seed hook existed — their spaces array
    # is non-empty but the seed marker is NULL/empty, so template
    # defaults were never applied. r47 handles this at deploy; this
    # login check is the self-healing safety net for any user the
    # migration skipped or who was created between migration run
    # and full hook rollout. O(1) cost when populated (two dict-key
    # reads).
    #
    # Production-track users (username + PIN) intentionally go
    # through this path too; the PIN login branch above already
    # writes user.last_console_login_at in the same commit, so
    # adding a seed here keeps that single-commit discipline.
    _prefs = user.preferences or {}
    # Phase W-4a — third invariant: every user must have every
    # currently-visible system space template seeded. New system
    # templates added post-canon (Phase W-4a "home" template) won't
    # surface for existing users without this gate widening, because
    # `spaces_seeded_for_roles` is populated and the prior 8e.2.2
    # gate would short-circuit. Cheap check: compare seeded
    # template_ids against the visible-to-this-user set; mismatch
    # triggers re-seed (idempotent — _apply_system_spaces skips
    # already-seeded entries).
    _missing_system_templates = False
    if _prefs.get("spaces"):
        try:
            from app.services.spaces.registry import (
                get_system_space_templates_for_user,
            )

            _seen = set(_prefs.get("system_spaces_seeded", []))
            _expected = {
                tpl.template_id
                for tpl in get_system_space_templates_for_user(db, user)
            }
            if _expected - _seen:
                _missing_system_templates = True
        except Exception:
            # Defensive: registry import failure must not block login.
            pass

    if (
        not _prefs.get("spaces")
        or not _prefs.get("spaces_seeded_for_roles")
        or _missing_system_templates
    ):
        from app.services.spaces.seed import seed_spaces_best_effort

        seed_spaces_best_effort(db, user, call_site="login_user")

    token_data = {"sub": user.id, "company_id": company.id}

    # Production users get additional claims and shorter token TTL
    if user.track == "production_delivery":
        token_data["track"] = "production_delivery"
        token_data["console_access"] = user.console_access or []
        db.commit()
        return TokenResponse(
            access_token=create_access_token(
                token_data, expires_minutes=settings.CONSOLE_TOKEN_EXPIRE_MINUTES
            ),
            refresh_token=create_refresh_token(token_data),
        )

    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


def refresh_tokens(
    db: Session, refresh_token: str, company: Company
) -> TokenResponse:
    """Refresh tokens scoped to a specific company."""
    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
        user_id = payload.get("sub")
        token_company_id = payload.get("company_id")
        if not user_id or token_company_id != company.id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user = (
        db.query(User)
        .filter(User.id == user_id, User.company_id == company.id)
        .first()
    )
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    token_data = {"sub": user.id, "company_id": company.id}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


def change_password(
    db: Session, user: User, current_password: str, new_password: str
) -> None:
    """Change own password. Verifies current password first."""
    if not verify_password(current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    user.hashed_password = hash_password(new_password)

    audit_service.log_action(
        db,
        user.company_id,
        "password_changed",
        "user",
        user.id,
        user_id=user.id,
    )

    db.commit()
