import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Notification(Base):
    """Bridgeable notification row.

    Phase V-1d absorbed SafetyAlert into this model — the `severity`,
    `due_date`, `acknowledged_by_user_id`, `acknowledged_at`,
    `source_reference_type`, and `source_reference_id` columns all
    preserve alert-flavor semantics. Safety alerts now live in this
    table with `category='safety_alert'`.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        Index(
            "ix_notifications_user_unread",
            "company_id",
            "user_id",
            "is_read",
        ),
        Index("ix_notifications_user_created", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="info"
    )
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    actor_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # ── V-1d alert-flavor columns (from former SafetyAlert model) ─────
    severity: Mapped[str | None] = mapped_column(String(16), nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    acknowledged_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Polymorphic linkage back to the thing the notification is about.
    # Replaces SafetyAlert.reference_type / reference_id.
    source_reference_type: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    source_reference_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    acknowledged_by = relationship(
        "User", foreign_keys=[acknowledged_by_user_id]
    )
