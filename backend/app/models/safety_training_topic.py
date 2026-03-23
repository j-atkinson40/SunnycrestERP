import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SafetyTrainingTopic(Base):
    __tablename__ = "safety_training_topics"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    month_number: Mapped[int] = mapped_column(Integer, nullable=False)
    topic_key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    osha_standard: Mapped[str | None] = mapped_column(String(100), nullable=True)
    osha_standard_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    suggested_duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    target_roles = mapped_column(JSONB, nullable=True)
    key_points = mapped_column(JSONB, nullable=True)
    discussion_questions = mapped_column(JSONB, nullable=True)
    pdf_filename_template: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_high_risk: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
