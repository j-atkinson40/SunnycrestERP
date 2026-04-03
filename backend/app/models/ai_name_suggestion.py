"""AiNameSuggestion — suggested professional name corrections for shorthand company names."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AiNameSuggestion(Base):
    __tablename__ = "ai_name_suggestions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    master_company_id: Mapped[str] = mapped_column(String(36), ForeignKey("company_entities.id", ondelete="CASCADE"), nullable=False)

    current_name: Mapped[str] = mapped_column(String(500), nullable=False)
    current_city: Mapped[str | None] = mapped_column(String(200), nullable=True)
    current_state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    current_address: Mapped[str | None] = mapped_column(String(500), nullable=True)

    suggested_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    suggested_address_line1: Mapped[str | None] = mapped_column(String(500), nullable=True)
    suggested_city: Mapped[str | None] = mapped_column(String(200), nullable=True)
    suggested_state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    suggested_zip: Mapped[str | None] = mapped_column(String(20), nullable=True)
    suggested_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    suggested_website: Mapped[str | None] = mapped_column(String(500), nullable=True)

    suggestion_source: Mapped[str | None] = mapped_column(String(30), nullable=True)
    google_places_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    source_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    status: Mapped[str] = mapped_column(String(20), server_default="pending")
    reviewed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_name: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
