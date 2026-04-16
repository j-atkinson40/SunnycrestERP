"""Admin deployment — tracks pushes to production with test coverage state."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AdminDeployment(Base):
    __tablename__ = "admin_deployments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    affected_verticals: Mapped[list] = mapped_column(JSON, nullable=False)
    affected_features: Mapped[list | None] = mapped_column(JSON, nullable=True)
    git_commit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    deployed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    logged_by_admin_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("platform_users.id"), nullable=True
    )
    is_tested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    test_run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("admin_audit_runs.id"), nullable=True
    )
