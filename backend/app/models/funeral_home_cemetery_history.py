import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FuneralHomeCemeteryHistory(Base):
    __tablename__ = "funeral_home_cemetery_history"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "customer_id",
            "cemetery_id",
            name="uq_fh_cemetery_history",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=False
    )
    cemetery_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cemeteries.id"), nullable=False
    )

    order_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_order_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    company = relationship("Company")
    customer = relationship("Customer")
    cemetery = relationship("Cemetery", back_populates="fh_history")
