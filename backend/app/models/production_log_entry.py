import uuid
from datetime import datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ProductionLogEntry(Base):
    __tablename__ = "production_log_entries"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    log_date: Mapped[datetime] = mapped_column(Date, nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id"), nullable=False
    )
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity_produced: Mapped[int] = mapped_column(Integer, nullable=False)
    mix_design_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    mix_design_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    batch_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    entered_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    entry_method: Mapped[str] = mapped_column(
        String(20), nullable=False, default="manual"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    company = relationship("Company")
    product = relationship("Product")
    user = relationship("User")
