"""RingCentral call log — records inbound/outbound calls for Call Intelligence."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RingCentralCallLog(Base):
    __tablename__ = "ringcentral_call_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)

    # RingCentral identifiers
    rc_call_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    rc_session_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    rc_recording_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Call metadata
    direction: Mapped[str] = mapped_column(String(20), nullable=False, default="inbound")
    call_status: Mapped[str] = mapped_column(String(30), nullable=False, default="completed")
    caller_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    caller_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    callee_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    callee_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    extension_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Linked entities
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    company_entity_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("company_entities.id"), nullable=True)
    customer_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("customers.id"), nullable=True)

    # Timestamps
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Transcription
    transcription: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcription_source: Mapped[str | None] = mapped_column(String(30), nullable=True)  # deepgram, ringcentral

    # Order linkage
    order_created: Mapped[bool] = mapped_column(Boolean, default=False)
    order_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("sales_orders.id"), nullable=True)

    # Extra data
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    extraction = relationship("RingCentralCallExtraction", back_populates="call_log", uselist=False)
    order = relationship("SalesOrder", foreign_keys=[order_id])
    company_entity = relationship("CompanyEntity", foreign_keys=[company_entity_id])
