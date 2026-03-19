import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ManufacturerDirectorySelection(Base):
    __tablename__ = "manufacturer_directory_selections"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    directory_entry_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("funeral_home_directory.id"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    customer_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    invitation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    actioned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    tenant = relationship("Company", foreign_keys=[tenant_id])
    directory_entry = relationship(
        "FuneralHomeDirectory", foreign_keys=[directory_entry_id]
    )
