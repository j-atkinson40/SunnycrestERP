"""Note surface — the shell and the standing-set register (session 1 of 5).

Prose composition, peek, settling, deferral and owner/backup routing are
sessions 2-5. Pulse is untouched; /home still serves it until session 5.
"""

from app.services.note.counts import resolve_count  # noqa: F401
from app.services.note.registry import (  # noqa: F401
    FALLBACK_TEMPLATE,
    ROLE_TEMPLATES,
    template_for,
    validate_entries,
)
from app.services.note.service import (  # noqa: F401
    get_or_create_note,
    render_standing_set,
    resolve_standing_set,
    set_override,
    tenant_today,
)
from app.services.note.types import (  # noqa: F401
    MAX_STANDING_ENTRIES,
    ResolvedStandingEntry,
    StandingEntry,
    StandingSetError,
)
