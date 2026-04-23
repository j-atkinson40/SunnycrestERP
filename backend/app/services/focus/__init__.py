"""Focus primitive services — Phase A Session 4.

Persistence + 3-tier layout resolution for the Focus primitive.
See `focus_session_service.py` for the public API.
"""

from app.services.focus.focus_session_service import (
    close_session,
    create_or_resume_session,
    get_active_session,
    get_layout_default,
    get_recent_closed_session,
    list_recent_closed_sessions,
    resolve_layout_state,
    set_layout_default,
    update_layout_state,
)


__all__ = [
    "close_session",
    "create_or_resume_session",
    "get_active_session",
    "get_layout_default",
    "get_recent_closed_session",
    "list_recent_closed_sessions",
    "resolve_layout_state",
    "set_layout_default",
    "update_layout_state",
]
