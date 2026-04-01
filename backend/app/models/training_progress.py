import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TrainingProgress(Base):
    __tablename__ = "training_progress"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "training_key", "stage_key",
            name="uq_training_progress_user_stage",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    training_key: Mapped[str] = mapped_column(String(100), nullable=False)
    stage_key: Mapped[str] = mapped_column(String(50), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user = relationship("User")
