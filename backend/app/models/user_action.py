"""UserAction — stores command bar action history per user."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserAction(Base):
    __tablename__ = "user_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    action_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    raw_input: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    result_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    action_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    input_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
