"""Operations board models — settings, production log, summaries, replies."""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OperationsBoardSettings(Base):
    __tablename__ = "operations_board_settings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "employee_id", name="uq_ops_board_settings_employee"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    # Core zone toggles (fixed columns)
    zone_briefing_visible: Mapped[bool] = mapped_column(Boolean, server_default="true")
    zone_announcements_visible: Mapped[bool] = mapped_column(Boolean, server_default="true")
    zone_production_log_visible: Mapped[bool] = mapped_column(Boolean, server_default="true")
    # Core button toggles (fixed columns)
    button_log_incident: Mapped[bool] = mapped_column(Boolean, server_default="true")
    button_safety_observation: Mapped[bool] = mapped_column(Boolean, server_default="true")
    button_qc_check: Mapped[bool] = mapped_column(Boolean, server_default="true")
    button_log_product: Mapped[bool] = mapped_column(Boolean, server_default="true")
    button_end_of_day: Mapped[bool] = mapped_column(Boolean, server_default="true")
    button_equipment_inspection: Mapped[bool] = mapped_column(Boolean, server_default="true")
    # Core behavior settings (fixed)
    voice_entry_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    eod_reminder_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    eod_reminder_time: Mapped[str] = mapped_column(String(5), server_default="16:00")
    # Extension and contributor settings (JSONB — extensible)
    contributor_settings: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    employee = relationship("User", foreign_keys=[employee_id])

    def get_setting(self, key: str, default: bool = True) -> bool:
        """Get a setting value — checks fixed columns first, then contributor_settings JSONB."""
        if hasattr(self, key) and key != "contributor_settings":
            return getattr(self, key, default)
        return (self.contributor_settings or {}).get(key, default)


class DailyProductionSummary(Base):
    __tablename__ = "daily_production_summaries"
    __table_args__ = (
        UniqueConstraint("tenant_id", "summary_date", name="uq_daily_prod_summary_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    summary_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="draft")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    posted_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    notes_for_tomorrow: Mapped[str | None] = mapped_column(Text, nullable=True)
    has_qc_failures: Mapped[bool] = mapped_column(Boolean, server_default="false")
    qc_failure_acknowledged_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    qc_failure_acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    contributor_data: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    entries = relationship("OpsProductionLogEntry", back_populates="summary")


class OpsProductionLogEntry(Base):
    __tablename__ = "ops_production_log_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    summary_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("daily_production_summaries.id"), nullable=True)
    product_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("products.id"), nullable=True)
    product_name_raw: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    logged_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    qc_status: Mapped[str] = mapped_column(String(20), server_default="not_checked")
    qc_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    qc_checked_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    qc_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_excluded_from_inventory: Mapped[bool] = mapped_column(Boolean, server_default="false")
    entry_method: Mapped[str] = mapped_column(String(20), server_default="manual")
    raw_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    contributor_key: Mapped[str | None] = mapped_column(String(50), nullable=True)
    contributor_data: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    component_type: Mapped[str] = mapped_column(String(20), server_default="complete")
    component_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    summary = relationship("DailyProductionSummary", back_populates="entries")
    product = relationship("Product", foreign_keys=[product_id])
    logger = relationship("User", foreign_keys=[logged_by])


class AnnouncementReply(Base):
    __tablename__ = "announcement_replies"
    __table_args__ = (
        UniqueConstraint("announcement_id", "employee_id", name="uq_announcement_reply_emp"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    announcement_id: Mapped[str] = mapped_column(String(36), ForeignKey("announcements.id"), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    reply_type: Mapped[str] = mapped_column(String(20), nullable=False)
    replied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    previous_reply_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    announcement = relationship("Announcement", foreign_keys=[announcement_id])
    employee = relationship("User", foreign_keys=[employee_id])
