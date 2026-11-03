from datetime import datetime

from pydantic import BaseModel, field_validator

from app.core.areas import KNOWN_AREAS


def _validate_areas(value: list[str] | None) -> list[str] | None:
    """Reject area keys that do not exist.

    ⚠️ **AN UNKNOWN KEY MUST 422, NOT PASS THROUGH.** `limited_to_areas` is the
    security boundary: `enforce_area_limit` allows a route only when its
    `area:<key>` tag matches one of these strings. A typo like `"payrol"` would
    therefore produce a role that is limited to an area NOTHING is tagged with —
    locked out of everything but the common shell set, and looking deliberate.
    Validating here makes that unexpressible rather than merely unlikely.

    An EMPTY list is valid and means exactly that: limited to nothing. `None`
    means not limited, which is the unrestricted default every existing role has.
    """
    if value is None:
        return None
    unknown = sorted(set(value) - set(KNOWN_AREAS))
    if unknown:
        raise ValueError(
            f"unknown area key(s): {unknown}. Known areas: {sorted(KNOWN_AREAS)}. "
            f"An area exists when a router is tagged `area:<key>` at "
            f"registration — see app/core/areas.py."
        )
    # Deduplicated and ordered so two writes of the same set compare equal in
    # the audit trail instead of showing a change that did not happen.
    return sorted(set(value))


class RoleCreate(BaseModel):
    name: str
    slug: str
    description: str | None = None
    permission_keys: list[str] = []
    #: None = not limited (the default, and what every pre-2026-11-03 role is).
    limited_to_areas: list[str] | None = None

    _check_areas = field_validator("limited_to_areas")(_validate_areas)


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    #: ⚠️ `None` HERE IS AMBIGUOUS AND THE SERVICE RESOLVES IT WITH
    #: `model_fields_set`, NOT WITH A NULL CHECK. Omitting the field means
    #: "leave the areas alone"; sending `null` explicitly means "make this role
    #: unlimited". A plain `is not None` test cannot tell those apart, so
    #: clearing a limit would be impossible — the same distinction
    #: `SpaceConfig.default_home_route` needed.
    limited_to_areas: list[str] | None = None

    _check_areas = field_validator("limited_to_areas")(_validate_areas)


class RoleResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: str | None
    is_system: bool
    is_active: bool
    permission_keys: list[str]
    #: Returned so a limited role and an unlimited one never look the same in
    #: any list that renders this schema.
    limited_to_areas: list[str] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RolePermissionUpdate(BaseModel):
    permission_keys: list[str]


class UserPermissionOverrideRequest(BaseModel):
    permission_key: str
    granted: bool


class UserPermissionOverridesResponse(BaseModel):
    effective_permissions: list[str]
    overrides: list[dict]
