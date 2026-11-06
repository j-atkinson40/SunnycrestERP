from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.company_resolver import get_current_company
from app.api.deps import get_current_user
from app.database import get_db
from app.models.company import Company
from app.models.role import Role
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    TokenResponse,
)
from app.schemas.company import CompanyResponse
from app.schemas.password import ChangePasswordRequest
from app.schemas.user import UserResponse
from app.services import audit_service
from app.services.auth_service import change_password, login_user, refresh_tokens
from app.services.extension_service import get_active_extension_keys
from app.services.module_service import get_enabled_module_keys
from app.services import employee_profile_service, functional_area_service
from app.services.permission_service import get_user_permissions

router = APIRouter()


def _user_to_response(user: User) -> dict:
    """Convert a User model to a response dict with role info."""
    data = UserResponse.model_validate(user).model_dump()
    if user.role_obj:
        data["role_name"] = user.role_obj.name
        data["role_slug"] = user.role_obj.slug
    return data


# ⚠️ **`POST /auth/register` WAS DELETED ON 2026-11-06. DO NOT REINSTATE IT.**
#
# It created a user inside an EXISTING company chosen by the `X-Company-Slug`
# header, with no credential of any kind required — so anyone who knew a
# tenant's address could create themselves a working login there. Measured on
# production: a 422 for an invalid body with no `Authorization` header, meaning
# the request reached body validation; all four live tenants were reachable;
# and there was a public page at `{slug}/register` routed beside `/login`.
#
# The registered user was `is_active=True` immediately with the password they
# chose. Role was `employee` — permissions `[]`, but `limited_to_areas` NULL,
# so `enforce_area_limit` early-returns and never confines them, leaving every
# endpoint gated only by `get_current_user` reachable. Or `admin`, if the
# company happened to have zero users.
#
# ⚠️ **IT WAS DELETED RATHER THAN GATED, AND THAT WAS THE RULING FOR A REASON:
# AN ABSENT ENDPOINT IS NOT A HOLE WITH A GUARD ON IT.** The capability is
# fully served by the invite flow — `tenant_invite.invite_user` plus
# `POST /invites/{token}/accept` — which requires `users.create`, hashes a
# single-use token, expires in 72 hours, and audits. Adding an invite-token
# check here would have produced a second, parallel implementation of that,
# and the weaker one would have been the one reachable without signing in.
#
# ⚠️ WHAT MADE IT SURVIVE SO LONG: a sweep for endpoints needing no sign-in
# EXCLUDED IT BY NAME, on the reasonable-sounding assumption that it was
# new-company signup. It was not. New-company signup is
# `POST /api/v1/companies/register`, a different route reached by a different
# page, and it refuses an existing slug with 409. One endpoint was credited
# with another's purpose, and the exclusion then hid it from every later sweep.
# See docs/investigations/2026-11-06-auth-register-open-registration.md.
#
# To invite someone: POST /users/invite.


@router.post("/login", response_model=TokenResponse)
def login(
    data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    result = login_user(db, data, company)

    # Log successful login — look up by email or username
    if data.email:
        user = db.query(User).filter(
            User.email == data.email, User.company_id == company.id
        ).first()
    else:
        user = db.query(User).filter(
            User.username == data.username, User.company_id == company.id
        ).first()
    if user:
        audit_service.log_action(
            db,
            company.id,
            "login",
            "session",
            user_id=user.id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        db.commit()

    return result


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    data: RefreshRequest,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    return refresh_tokens(db, data.refresh_token, company)


@router.post("/change-password")
def change_pwd(
    data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    change_password(db, current_user, data.current_password, data.new_password)
    return {"detail": "Password changed successfully"}


@router.get("/me")
def me(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    permissions = sorted(get_user_permissions(current_user, db))
    enabled_modules = get_enabled_module_keys(db, current_user.company_id)
    enabled_extensions = get_active_extension_keys(db, current_user.company_id)
    user_data = _user_to_response(current_user)

    # Get employee's active functional areas (filtered by tenant extensions)
    profile = employee_profile_service.get_profile(db, current_user.id)
    tenant_areas = functional_area_service.get_areas_for_tenant(db, current_user.company_id)
    active_areas = functional_area_service.get_active_areas_for_employee(
        profile.functional_areas if profile else None, tenant_areas
    )

    # ⚠️ **THE AREA RULE THE SERVER ACTUALLY ENFORCES, SO THE SHELL CAN STOP
    # KEEPING ITS OWN.** James's ruling of 2026-11-06, after a payroll-limited
    # user on production saw Financials, Agents, Production, Resale, Knowledge
    # Base and Settings in her sidebar while the server refused all 551 of the
    # endpoints behind them.
    #
    # The cause was two different lists. `enforce_area_limit` refuses by
    # `roles.limited_to_areas`; `navigation-service.ts::filterByPermission`
    # decided by `employee_profiles.functional_areas` — a different concept, on
    # a different table, written by a different code path. Hers was `[]`, and
    # the frontend read empty as "unrestricted" rather than "restricted to
    # nothing", so every item gating on `functionalArea` passed.
    #
    # ⚠️ `None` AND `[]` MEAN DIFFERENT THINGS HERE AND THE DISTINCTION IS THE
    # WHOLE POINT. `None` is "this role has no area limit" — the normal case,
    # every existing role. `[]` is "limited to nothing", which no admin can
    # currently configure but which must NOT read as unlimited if one ever
    # does. The frontend checks `=== null`, not falsiness.
    #
    # `mfa_enroll` is deliberately NOT unioned in. The server unions it when it
    # confines her, but it is not an administrable area and reporting it would
    # tell the shell to render a menu item for a role property no admin set.
    role = db.query(Role).filter(Role.id == current_user.role_id).first()
    limited_to_areas = getattr(role, "limited_to_areas", None) if role else None

    return {
        **user_data,
        "permissions": permissions,
        "enabled_modules": enabled_modules,
        "enabled_extensions": enabled_extensions,
        "functional_areas": active_areas,
        #: None = no area limit. A list = reachable areas, and nothing else.
        "limited_to_areas": limited_to_areas,
        "track": current_user.track or "office_management",
        "username": current_user.username,
        "console_access": current_user.console_access or [],
        "company": CompanyResponse.model_validate(company).model_dump(),
    }
