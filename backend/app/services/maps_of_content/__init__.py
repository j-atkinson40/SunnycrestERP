"""Maps of Content — service (Phase 1, backend-only, realm-agnostic).

Artifact-first admin navigation: authored pages whose rows are typed
references into the four wired Studio builders (workflows / focuses /
widgets / documents). The service operates on company_id + actor_id
primitives — no request/user objects — so the tenant router
(get_current_user) and the platform-admin router (get_current_platform_user)
consume it identically (CLAUDE.md realm-agnostic service-layer pattern).

Settled decisions (MoC Phase 0):
- new admin surface (not folded into an existing builder);
- lean single table (sections + rows as JSONB; no version trail);
- orphan-tolerant AT READ: a row whose artifact was deleted resolves to
  available=False and renders unavailable — it never errors the page;
- three-tier scope shape, vertical tier populated, tenant tier empty;
- the four ALREADY-WIRED builders only (no speculative builder keys).
"""

from app.services.maps_of_content.service import (
    BUILDERS,
    InvalidReference,
    create_page,
    delete_page,
    get_page,
    list_pages,
    read_for_context,
    read_page,
    resolve_for_context,
    resolve_references,
    update_page,
)

__all__ = [
    "BUILDERS",
    "InvalidReference",
    "create_page",
    "delete_page",
    "get_page",
    "list_pages",
    "read_for_context",
    "read_page",
    "resolve_for_context",
    "resolve_references",
    "update_page",
]
