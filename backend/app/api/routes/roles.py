from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.permissions import PERMISSIONS
from app.database import get_db
from app.models.user import User
from app.schemas.role import (
    RoleCreate,
    RolePermissionUpdate,
    RoleResponse,
    RoleUpdate,
)
from app.services import role_service

router = APIRouter()


def _role_to_response(role) -> dict:
    """Convert a Role model to a response dict with permission_keys."""
    return {
        "id": role.id,
        "name": role.name,
        "slug": role.slug,
        "description": role.description,
        "is_system": role.is_system,
        "is_active": role.is_active,
        "permission_keys": [rp.permission_key for rp in role.permissions],
        # ⚠️ SURFACED SO A LIMITED ROLE AND AN UNLIMITED ONE NEVER LOOK THE SAME.
        # Every list that renders a role goes through here; omitting this is how
        # an admin ends up assigning an area-limited role believing it is a
        # normal one, or the reverse.
        "limited_to_areas": role.limited_to_areas,
        "created_at": role.created_at,
    }


# --- Static paths MUST come before /{role_id} to avoid path conflicts ---


@router.get("/permissions/registry")
def get_permission_registry(
    current_user: User = Depends(require_permission("roles.view")),
):
    """Return the full permission registry for the UI to render checkboxes."""
    return PERMISSIONS


@router.get("/areas")
def get_known_areas(
    current_user: User = Depends(require_permission("roles.view")),
):
    """The area keys a role may be limited to.

    ⚠️ **SERVED RATHER THAN HARDCODED IN THE UI, BECAUSE THERE MUST BE ONE
    PRODUCER OF THIS LIST.** `KNOWN_AREAS` is what `enforce_area_limit` and the
    `RoleCreate` validator both read; a second copy in the frontend would drift,
    and the failure would be an admin offered an area the server then rejects
    with a 422 — or worse, an area missing from the picker that nobody can grant.

    A separate endpoint rather than a field on `/permissions/registry`: that
    response is a flat module → actions map which the UI spreads directly, so
    adding a key would change its shape for its existing consumer.
    """
    from app.core.areas import COMMON_PREFIXES, KNOWN_AREAS

    return {
        "areas": sorted(KNOWN_AREAS),
        # Surfaced so the editor can explain what a limited role still reaches,
        # instead of the admin having to infer it.
        "always_available": [prefix for prefix, _reason in COMMON_PREFIXES],
    }


@router.get("", response_model=list[RoleResponse])
def list_roles(
    current_user: User = Depends(require_permission("roles.view")),
    db: Session = Depends(get_db),
):
    roles = role_service.get_roles(db, current_user.company_id)
    return [_role_to_response(r) for r in roles]


@router.post("", response_model=RoleResponse, status_code=201)
def create_role(
    data: RoleCreate,
    current_user: User = Depends(require_permission("roles.create")),
    db: Session = Depends(get_db),
):
    role = role_service.create_role(db, data, current_user.company_id, actor_id=current_user.id)
    return _role_to_response(role)


@router.get("/{role_id}", response_model=RoleResponse)
def get_role(
    role_id: str,
    current_user: User = Depends(require_permission("roles.view")),
    db: Session = Depends(get_db),
):
    role = role_service.get_role(db, role_id, current_user.company_id)
    return _role_to_response(role)


@router.patch("/{role_id}", response_model=RoleResponse)
def update_role(
    role_id: str,
    data: RoleUpdate,
    current_user: User = Depends(require_permission("roles.edit")),
    db: Session = Depends(get_db),
):
    role = role_service.update_role(db, role_id, data, current_user.company_id, actor_id=current_user.id)
    return _role_to_response(role)


@router.delete("/{role_id}", status_code=204)
def delete_role(
    role_id: str,
    current_user: User = Depends(require_permission("roles.delete")),
    db: Session = Depends(get_db),
):
    role_service.delete_role(db, role_id, current_user.company_id, actor_id=current_user.id)


@router.put("/{role_id}/permissions", response_model=RoleResponse)
def set_role_permissions(
    role_id: str,
    data: RolePermissionUpdate,
    current_user: User = Depends(require_permission("roles.edit")),
    db: Session = Depends(get_db),
):
    role = role_service.set_role_permissions(
        db, role_id, data.permission_keys, current_user.company_id,
        actor_id=current_user.id,
    )
    return _role_to_response(role)
