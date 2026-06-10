"""Job Coordination Focus service (JCF-1).

Public surface for the assembly substrate: order-launched instance spawn,
the FocusShare grant lifecycle + read-guard, the Focus-scoped thread, and
decision-bounded closure (close → auto-revoke). See DECISIONS.md
2026-06-10 for the settled decisions this implements.
"""

from app.services.coordination_focus.service import (
    AccessDenied,
    can_access,
    close_instance,
    ensure_instance_for_order,
    get_active_share,
    get_instance,
    grant_share,
    list_messages,
    post_message,
    read_instance,
    revoke_share,
)

__all__ = [
    "AccessDenied",
    "can_access",
    "close_instance",
    "ensure_instance_for_order",
    "get_active_share",
    "get_instance",
    "grant_share",
    "list_messages",
    "post_message",
    "read_instance",
    "revoke_share",
]
