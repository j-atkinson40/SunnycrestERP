"""Quick-quote / quick-order template used by the Order Entry Station."""

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class QuickQuoteTemplate(Base):
    __tablename__ = "quick_quote_templates"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=True, index=True
    )
    template_name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_label: Mapped[str] = mapped_column(String(100), nullable=False)
    display_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    product_line: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # wastewater, redi_rock, rosetta, funeral_vaults
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_system_template: Mapped[bool] = mapped_column(Boolean, default=False)

    # JSON-serialized via Text
    line_items: Mapped[str | None] = mapped_column(Text, nullable=True)
    variable_fields: Mapped[str | None] = mapped_column(Text, nullable=True)

    slide_over_width: Mapped[int] = mapped_column(Integer, default=640)
    primary_action: Mapped[str] = mapped_column(
        String(20), default="split"
    )  # quote, order, split
    quote_template_key: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    # If True, this template is hidden outside its assigned season(s)
    seasonal_only: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    tenant = relationship("Company", foreign_keys=[tenant_id])

    # ── Convenience JSON accessors ──────────────────────────────────────

    @property
    def line_items_parsed(self) -> list[dict]:
        if not self.line_items:
            return []
        return json.loads(self.line_items)

    @property
    def variable_fields_parsed(self) -> list[dict]:
        if not self.variable_fields:
            return []
        return json.loads(self.variable_fields)
