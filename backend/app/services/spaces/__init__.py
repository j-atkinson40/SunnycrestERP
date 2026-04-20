"""Spaces — per-user workspace contexts (Phase 3 of UI/UX Arc).

Public surface:

    from app.services.spaces import (
        # types
        SpaceConfig, PinConfig, ResolvedSpace, ResolvedPin,
        AccentName, PinType, DensityName,
        MAX_SPACES_PER_USER, MAX_PINS_PER_SPACE,
        SpaceError, SpaceNotFound, SpacePermissionDenied,
        SpaceLimitExceeded, PinNotFound,
        # crud
        get_spaces_for_user, get_space, get_active_space_id,
        create_space, update_space, delete_space,
        set_active_space, reorder_spaces,
        add_pin, remove_pin, reorder_pins,
        # seed
        seed_for_user,
    )

Storage: User.preferences.spaces (JSONB array). No dedicated table,
no migration — reuses the r32 User.preferences column from Phase 2.

See `backend/app/services/spaces/registry.py` for role-template
definitions.
"""

from app.services.spaces.crud import (
    add_pin,
    create_space,
    delete_space,
    get_active_space_id,
    get_space,
    get_spaces_for_user,
    remove_pin,
    reorder_pins,
    reorder_spaces,
    set_active_space,
    update_space,
)
from app.services.spaces.seed import seed_for_user
from app.services.spaces.types import (
    MAX_PINS_PER_SPACE,
    MAX_SPACES_PER_USER,
    AccentName,
    DensityName,
    PinConfig,
    PinNotFound,
    PinType,
    ResolvedPin,
    ResolvedSpace,
    SpaceConfig,
    SpaceError,
    SpaceLimitExceeded,
    SpaceNotFound,
    SpacePermissionDenied,
)

__all__ = [
    # Types
    "SpaceConfig",
    "PinConfig",
    "ResolvedSpace",
    "ResolvedPin",
    "AccentName",
    "PinType",
    "DensityName",
    "MAX_SPACES_PER_USER",
    "MAX_PINS_PER_SPACE",
    "SpaceError",
    "SpaceNotFound",
    "SpacePermissionDenied",
    "SpaceLimitExceeded",
    "PinNotFound",
    # CRUD
    "get_spaces_for_user",
    "get_space",
    "get_active_space_id",
    "create_space",
    "update_space",
    "delete_space",
    "set_active_space",
    "reorder_spaces",
    "add_pin",
    "remove_pin",
    "reorder_pins",
    # Seed
    "seed_for_user",
]
