"""ExtensionWidget — tracks which extension widgets are active per tenant.

Created when an extension is enabled, removed when disabled.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ExtensionWidget(Base):
    __tablename__ = "extension_widgets"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    extension_slug: Mapped[str] = mapped_column(String(100), nullable=False)
    widget_id: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "extension_slug", "widget_id", name="uq_extension_widget"
        ),
    )
