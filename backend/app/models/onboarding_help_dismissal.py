import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OnboardingHelpDismissal(Base):
    __tablename__ = "onboarding_help_dismissals"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "employee_id",
            "help_key",
            name="uq_onboarding_help_dismissal",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    employee_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    help_key: Mapped[str] = mapped_column(String(100), nullable=False)
    dismissed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    company = relationship("Company", backref="onboarding_help_dismissals")
    employee = relationship("User", backref="onboarding_help_dismissals")
