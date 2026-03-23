import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EmployeeBriefing(Base):
    __tablename__ = "employee_briefings"
    __table_args__ = (
        UniqueConstraint("company_id", "user_id", "briefing_date", name="uq_employee_briefing_daily"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    briefing_date: Mapped[date] = mapped_column(Date, nullable=False)
    primary_area: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    context_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    generated_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_items: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    token_usage: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    generation_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    was_cached: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    company = relationship("Company", backref="employee_briefings")
    user = relationship("User", backref="employee_briefings")
