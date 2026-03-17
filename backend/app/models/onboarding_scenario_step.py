import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OnboardingScenarioStep(Base):
    __tablename__ = "onboarding_scenario_steps"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    scenario_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("onboarding_scenarios.id"), nullable=False, index=True
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    target_route: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    target_element: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    completion_trigger: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    completion_trigger_metadata: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    hint_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    scenario = relationship("OnboardingScenario", back_populates="steps")
