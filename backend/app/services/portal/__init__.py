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
from app.services.portal.branding import set_portal_branding
from app.services.portal.user_service import (
    PortalUserSummary,
    deactivate_portal_user,
    invite_portal_user,
    issue_admin_reset_password,
    list_portal_users_for_tenant,
    reactivate_portal_user,
    resend_invite,
    resolve_driver_for_portal_user,
    unlock_portal_user,
    update_portal_user_profile,
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
    "set_portal_branding",
    "resolve_driver_for_portal_user",
    # Phase 8e.2.1 admin surface
    "PortalUserSummary",
    "list_portal_users_for_tenant",
    "update_portal_user_profile",
    "deactivate_portal_user",
    "reactivate_portal_user",
    "unlock_portal_user",
    "issue_admin_reset_password",
    "resend_invite",
]
