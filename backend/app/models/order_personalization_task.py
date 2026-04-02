import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OrderPersonalizationTask(Base):
    __tablename__ = "order_personalization_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    order_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("sales_orders.id"), nullable=True)
    quote_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("quotes.id"), nullable=True)
    order_line_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    task_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # nameplate, cover_emblem, lifes_reflections, legacy_standard, legacy_custom

    inscription_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    inscription_dates: Mapped[str | None] = mapped_column(Text, nullable=True)
    inscription_additional: Mapped[str | None] = mapped_column(Text, nullable=True)

    print_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    print_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    symbol: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_custom_legacy: Mapped[bool] = mapped_column(Boolean, server_default="false")

    status: Mapped[str] = mapped_column(String(20), server_default="pending")
    completed_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Legacy proof fields
    proof_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    tif_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_layout: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    approved_layout: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    company = relationship("Company")
    completed_by_user = relationship("User", foreign_keys=[completed_by])
