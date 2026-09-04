"""Standing-set overrides — tiers 2 and 3 of the cascade.

    code role template  →  tenant override  →  user override
                            ^^^^^^^^^^^^^^^     ^^^^^^^^^^^^^
                            this model, user_id NULL / non-NULL

The role tier is code-declared (`note/registry.py`), not stored — a role's
standing set is a design artifact that ships with the vertical, not tenant data.

⚠️ AN ABSENT ROW AND AN EMPTY `entries` ARE DIFFERENT STATES. No row means
"inherit the tier beneath". A row with `entries == []` means "inherit nothing —
show no standing set". `entries` is therefore NOT NULL, so absence is
expressible exactly once.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StandingSetConfig(Base):
    __tablename__ = "standing_set_configs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: NULL => the tenant override. Non-NULL => that user's override.
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    entries: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @property
    def tier(self) -> str:
        return "user" if self.user_id else "tenant"
