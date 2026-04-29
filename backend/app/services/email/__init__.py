"""Email Primitive service layer — Phase W-4b Layer 1 (§3.26.15).

This package implements the *conversation/thread/inbox* infrastructure
described in BRIDGEABLE_MASTER §3.26.15. It is deliberately distinct
from the platform's existing transactional-send infrastructure
(``app.services.email_service``, ``app.services.delivery_service``,
``app.services.legacy_email_service``, ``app.services.platform_email_service``).

  - Existing (Phase D-7 / Phase 5 platform email):
    fire-and-forget audit log of one-shot transactional sends
    (statement emails, signing invites, briefing notifications)
    routed through Resend. Stays untouched.

  - This package (W-4b §3.26.15):
    threaded inbox + provider abstraction + per-user state +
    cross-tenant native messaging + Workshop email-template
    integration + Intelligence integration.

Step 1 ships entity foundation + provider abstraction stubs +
EmailAccount service layer + UI for tenant admins to create/manage
EmailAccount + EmailAccountAccess records. Subsequent Steps 2-N
(sync, outbound, inbox UI, composition, Workshop integration,
Intelligence) build atop this foundation.
"""

from app.services.email import account_service
from app.services.email.providers import (
    EmailProvider,
    PROVIDER_REGISTRY,
    get_provider_class,
)

__all__ = [
    "account_service",
    "EmailProvider",
    "PROVIDER_REGISTRY",
    "get_provider_class",
]
