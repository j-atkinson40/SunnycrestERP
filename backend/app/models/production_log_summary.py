import uuid
from datetime import datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ProductionLogSummary(Base):
    __tablename__ = "production_log_summaries"
    __table_args__ = (
        UniqueConstraint("tenant_id", "summary_date", name="uq_prod_log_summary_tenant_date"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    summary_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    total_units_produced: Mapped[int] = mapped_column(Integer, default=0)
    products_produced: Mapped[str | None] = mapped_column(Text, nullable=True)
    recalculated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    company = relationship("Company")
