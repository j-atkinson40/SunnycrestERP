import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OrderPersonalizationPhoto(Base):
    __tablename__ = "order_personalization_photos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), nullable=False)
    order_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("sales_orders.id"), nullable=True)
    quote_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("quotes.id"), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("order_personalization_tasks.id"), nullable=True)

    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uploaded_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    task = relationship("OrderPersonalizationTask")
    uploader = relationship("User", foreign_keys=[uploaded_by])
