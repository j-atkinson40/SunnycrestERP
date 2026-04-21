"""Portal services package — Workflow Arc Phase 8e.2.

Portal-as-space-with-modifiers infrastructure. See
`SPACES_ARCHITECTURE.md` §10 for the architecture reference.

Public surface:

    from app.services.portal import (
        # Auth
        PortalAuthError,
        PortalLoginLocked,
        PortalLoginInvalid,
        authenticate_portal_user,
        create_portal_tokens,
        verify_portal_refresh_token,
        # Admin CRUD (minimal — Phase 8e.2.1 ships the full UI)
        invite_portal_user,
        # Branding
        get_portal_branding,
        # Driver-data resolver
        resolve_driver_for_portal_user,
    )
"""

from app.services.portal.auth import (
    PortalAuthError,
    PortalLoginInvalid,
    PortalLoginLocked,
    authenticate_portal_user,
    create_portal_tokens,
    verify_portal_refresh_token,
)
from app.services.portal.branding import get_portal_branding
from app.services.portal.user_service import (
    invite_portal_user,
    resolve_driver_for_portal_user,
)

__all__ = [
    "PortalAuthError",
    "PortalLoginInvalid",
    "PortalLoginLocked",
    "authenticate_portal_user",
    "create_portal_tokens",
    "verify_portal_refresh_token",
    "invite_portal_user",
    "get_portal_branding",
    "resolve_driver_for_portal_user",
]
