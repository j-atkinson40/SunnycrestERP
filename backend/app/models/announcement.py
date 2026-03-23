import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Announcement(Base):
    __tablename__ = "announcements"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )

    # Content
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="info"
    )  # info, warning, critical

    # Targeting
    target_type: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="everyone"
    )  # everyone, functional_area, employee_type, specific_employees
    target_value: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )  # area key, employee type, or null for everyone
    target_employee_ids = mapped_column(
        JSONB, nullable=True
    )  # list of user IDs for specific_employees targeting

    # Lifecycle
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    pin_to_top: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Content type
    content_type: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="announcement"
    )  # announcement, note, safety_notice

    # Safety notice fields (only populated when content_type = 'safety_notice')
    safety_category: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )  # procedure, equipment_alert, osha_reminder, incident_followup, training_assignment, toolbox_talk
    requires_acknowledgment: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    is_compliance_relevant: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    document_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    document_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    linked_equipment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tenant_equipment_items.id"), nullable=True
    )
    linked_incident_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("safety_incidents.id"), nullable=True
    )
    linked_training_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("safety_training_events.id"), nullable=True
    )
    acknowledgment_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reminder_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Operations board
    is_operations_board: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    reply_options_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    reads = relationship("AnnouncementRead", back_populates="announcement", cascade="all, delete-orphan")
    linked_equipment = relationship("TenantEquipmentItem", foreign_keys=[linked_equipment_id])
    linked_incident = relationship("SafetyIncident", foreign_keys=[linked_incident_id])
    linked_training = relationship("SafetyTrainingEvent", foreign_keys=[linked_training_id])
