"""Admin smoke test result — lightweight read-only production health check per tenant."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AdminSmokeTestResult(Base):
    __tablename__ = "admin_smoke_test_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    deployment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("admin_deployments.id"), nullable=True
    )
    triggered_by_admin_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("platform_users.id"), nullable=True
    )
    trigger: Mapped[str] = mapped_column(String(50), nullable=False)   # post_deployment | manual | scheduled
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    checks_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checks_passed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checks_failed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    failures: Mapped[list | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
