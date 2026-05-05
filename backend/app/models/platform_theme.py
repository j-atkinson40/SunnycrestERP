"""Platform Theme model — token override storage for the Admin
Visual Editor (Phase 2).

Inheritance chain at READ time:
    platform_default
        + vertical_default(vertical=X) overrides
            + tenant_override(tenant_id=Y) overrides
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


SCOPE_PLATFORM_DEFAULT = "platform_default"
SCOPE_VERTICAL_DEFAULT = "vertical_default"
SCOPE_TENANT_OVERRIDE = "tenant_override"

MODE_LIGHT = "light"
MODE_DARK = "dark"


class PlatformTheme(Base):
    """One row per (scope, vertical?, tenant_id?, mode) version.

    Active rows are unique per the partial index defined in r79;
    inactive rows accumulate as a version trail (write-side
    versioning — every save flips is_active on the prior row +
    inserts a new active row with version + 1).
    """

    __tablename__ = "platform_themes"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    vertical: Mapped[str | None] = mapped_column(String(32), nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=True,
    )
    mode: Mapped[str] = mapped_column(String(8), nullable=False)
    token_overrides: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    created_by: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "scope IN ('platform_default', 'vertical_default', 'tenant_override')",
            name="ck_platform_themes_scope",
        ),
        CheckConstraint(
            "mode IN ('light', 'dark')",
            name="ck_platform_themes_mode",
        ),
        CheckConstraint(
            """(
                (scope = 'platform_default'
                    AND vertical IS NULL AND tenant_id IS NULL)
                OR (scope = 'vertical_default'
                    AND vertical IS NOT NULL AND tenant_id IS NULL)
                OR (scope = 'tenant_override'
                    AND vertical IS NULL AND tenant_id IS NOT NULL)
            )""",
            name="ck_platform_themes_scope_keys",
        ),
    )

    def __repr__(self) -> str:
        ident = self.vertical or self.tenant_id or "platform"
        return (
            f"<PlatformTheme {self.scope}:{ident}:{self.mode} "
            f"v{self.version} active={self.is_active}>"
        )
