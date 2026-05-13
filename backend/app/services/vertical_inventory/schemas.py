"""Pydantic schemas for Studio overview inventory.

See `service.py` for the inventory-building logic.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


Scope = Literal["platform", "vertical"]


class SectionInventoryEntry(BaseModel):
    """One row per section card on the Studio overview.

    `count` is None when no backend count source exists for the
    section (Registry inspector is frontend-in-memory; Plugin
    Registry under vertical scope is suppressed since the catalog
    is platform-global). Frontend renders the card without the
    count display when count is None.
    """

    key: str
    label: str
    count: int | None


class RecentEditEntry(BaseModel):
    """One row in the UNION'd recent-edits feed.

    `editor_email` is None when `updated_by` was NULL on the source
    row OR when the table has no `updated_by` column at all
    (document_templates). Per Studio 1a-ii decision 6, the frontend
    SILENTLY OMITS attribution when this is null — no "by —"
    placeholder.

    `deep_link_path` is the Studio URL the entity opens at (e.g.
    `/studio/manufacturing/themes?theme_id=<uuid>`); frontend just
    wraps the row in `<Link to={deep_link_path}>`.
    """

    section: str
    entity_name: str
    entity_id: str
    editor_email: str | None
    edited_at: datetime
    deep_link_path: str


class InventoryResponse(BaseModel):
    scope: Scope
    vertical_slug: str | None
    sections: list[SectionInventoryEntry]
    recent_edits: list[RecentEditEntry]
