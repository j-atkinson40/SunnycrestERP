from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.api.company_resolver import get_current_company
from app.core.security import decode_token
from app.database import get_db
from app.models.api_key import ApiKey
from app.models.company import Company
from app.models.role import Role
from app.models.user import User
from app.services.permission_service import user_has_permission

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
        user_id: str = payload.get("sub")
        token_company_id: str = payload.get("company_id")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
        if token_company_id != company.id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token does not match this company",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user = (
        db.query(User)
        .filter(User.id == user_id, User.company_id == company.id)
        .first()
    )
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


def require_admin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Backward-compatible admin check using the new Role model."""
    role = db.query(Role).filter(Role.id == current_user.role_id).first()
    if not (role and role.is_system and role.slug == "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


def require_permission(permission_key: str):
    """
    Dependency factory for permission-based authorization.

    Usage: Depends(require_permission("users.view"))
    """

    def _check_permission(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if not user_has_permission(current_user, db, permission_key):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {permission_key}",
            )
        return current_user

    return _check_permission


def require_feature(flag_key: str):
    """
    Dependency factory for feature-flag-based authorization.
    Returns 404 (not 403) to hide the existence of disabled features.

    Usage: Depends(require_feature("feature.ai_assistant"))
    """

    def _check_feature(
        request: Request,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        from app.services.feature_flag_service import is_enabled, log_blocked_request

        if not is_enabled(db, current_user.company_id, flag_key):
            log_blocked_request(
                db,
                current_user.company_id,
                flag_key,
                str(request.url.path),
                user_id=current_user.id,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Not found",
            )
        return current_user

    return _check_feature


def require_module(module_name: str):
    """
    Dependency factory for module-based authorization.

    Usage: Depends(require_module("products"))
    """

    def _check_module(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        from app.services.module_service import is_module_enabled

        if not is_module_enabled(db, current_user.company_id, module_name):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Module '{module_name}' is not enabled for this company",
            )
        return current_user

    return _check_module


# ---------------------------------------------------------------------------
# API key authentication (separate from JWT user auth)
# ---------------------------------------------------------------------------


def get_api_key_auth(
    request: Request,
    db: Session = Depends(get_db),
) -> ApiKey:
    """Authenticate via X-API-Key header. For external integrations."""
    from app.services.api_key_service import record_usage, validate_api_key

    key_header = request.headers.get("X-API-Key")
    if not key_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-API-Key header required",
        )

    api_key, error = validate_api_key(db, key_header)
    if error:
        if error == "Rate limit exceeded":
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error,
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error,
        )

    # Record usage (non-error)
    record_usage(db, api_key.id, is_error=False)
    return api_key


def require_api_scope(scope: str):
    """Dependency factory for API key scope checking.

    Usage: Depends(require_api_scope("customers.read"))
    """

    def _check_scope(
        api_key: ApiKey = Depends(get_api_key_auth),
    ) -> ApiKey:
        from app.services.api_key_service import has_scope

        if not has_scope(api_key, scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key missing required scope: {scope}",
            )
        return api_key

    return _check_scope
