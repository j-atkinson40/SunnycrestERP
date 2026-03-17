import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BillOfMaterials(Base):
    __tablename__ = "bill_of_materials"
    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "version",
            "company_id",
            name="uq_bom_product_version_company",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    modified_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    modified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    company = relationship("Company")
    product = relationship("Product", foreign_keys=[product_id])
    lines = relationship(
        "BOMLine",
        back_populates="bom",
        cascade="all, delete-orphan",
        order_by="BOMLine.sort_order",
    )
    creator = relationship("User", foreign_keys=[created_by])


class BOMLine(Base):
    __tablename__ = "bom_lines"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    bom_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("bill_of_materials.id"), nullable=False, index=True
    )
    component_product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id"), nullable=False, index=True
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), nullable=False
    )
    unit_of_measure: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    waste_factor_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0")
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_optional: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    bom = relationship("BillOfMaterials", back_populates="lines")
    component_product = relationship("Product", foreign_keys=[component_product_id])
