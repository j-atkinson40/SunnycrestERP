import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class QCInspectionTemplate(Base):
    __tablename__ = "qc_inspection_templates"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    product_category: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    template_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    wilbert_warranty_compliant: Mapped[bool] = mapped_column(
        Boolean, default=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    company = relationship("Company")
    steps = relationship(
        "QCInspectionStep",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="QCInspectionStep.step_order",
    )


class QCInspectionStep(Base):
    __tablename__ = "qc_inspection_steps"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    template_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("qc_inspection_templates.id"),
        nullable=False,
        index=True,
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    step_name: Mapped[str] = mapped_column(String(200), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    inspection_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default="visual"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    pass_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_required: Mapped[bool] = mapped_column(Boolean, default=False)
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    template = relationship("QCInspectionTemplate", back_populates="steps")


class QCInspection(Base):
    __tablename__ = "qc_inspections"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    inventory_item_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("inventory_items.id"),
        nullable=True,
        index=True,
    )
    template_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("qc_inspection_templates.id"),
        nullable=False,
        index=True,
    )
    product_category: Mapped[str] = mapped_column(String(50), nullable=False)
    product_type: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    inspector_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending"
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    overall_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    certificate_number: Mapped[str | None] = mapped_column(
        String(20), unique=True, nullable=True
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
    company = relationship("Company")
    inventory_item = relationship("InventoryItem")
    template = relationship("QCInspectionTemplate")
    inspector = relationship("User", foreign_keys=[inspector_id])
    step_results = relationship(
        "QCStepResult",
        back_populates="inspection",
        cascade="all, delete-orphan",
    )
    disposition = relationship(
        "QCDisposition",
        back_populates="inspection",
        uselist=False,
        cascade="all, delete-orphan",
    )
    media = relationship(
        "QCMedia",
        back_populates="inspection",
        cascade="all, delete-orphan",
    )
    rework_records = relationship(
        "QCReworkRecord",
        back_populates="inspection",
        foreign_keys="QCReworkRecord.inspection_id",
        cascade="all, delete-orphan",
    )


class QCStepResult(Base):
    __tablename__ = "qc_step_results"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    inspection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("qc_inspections.id"),
        nullable=False,
        index=True,
    )
    step_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("qc_inspection_steps.id"),
        nullable=False,
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    result: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    defect_type_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("qc_defect_types.id"),
        nullable=True,
    )
    defect_severity: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    inspection = relationship("QCInspection", back_populates="step_results")
    step = relationship("QCInspectionStep")
    defect_type = relationship("QCDefectType")
    media = relationship(
        "QCMedia",
        back_populates="step_result",
        cascade="all, delete-orphan",
    )


class QCMedia(Base):
    __tablename__ = "qc_media"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    step_result_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("qc_step_results.id"),
        nullable=True,
        index=True,
    )
    inspection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("qc_inspections.id"),
        nullable=False,
        index=True,
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    caption: Mapped[str | None] = mapped_column(String(500), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    step_result = relationship("QCStepResult", back_populates="media")
    inspection = relationship("QCInspection", back_populates="media")


class QCDefectType(Base):
    __tablename__ = "qc_defect_types"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    defect_name: Mapped[str] = mapped_column(String(200), nullable=False)
    product_category: Mapped[str] = mapped_column(String(50), nullable=False)
    default_severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default="minor"
    )
    default_disposition: Mapped[str] = mapped_column(
        String(30), nullable=False, default="hold_pending_review"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    company = relationship("Company")


class QCDisposition(Base):
    __tablename__ = "qc_dispositions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    inspection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("qc_inspections.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    decided_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    disposition: Mapped[str] = mapped_column(String(30), nullable=False)
    disposition_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    rework_instructions: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    inspection = relationship("QCInspection", back_populates="disposition")
    decider = relationship("User", foreign_keys=[decided_by])


class QCReworkRecord(Base):
    __tablename__ = "qc_rework_records"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    inspection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("qc_inspections.id"),
        nullable=False,
        index=True,
    )
    original_inspection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("qc_inspections.id"),
        nullable=False,
        index=True,
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    rework_description: Mapped[str] = mapped_column(Text, nullable=False)
    rework_completed_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    rework_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    re_inspection_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("qc_inspections.id"),
        nullable=True,
    )

    # Relationships
    inspection = relationship(
        "QCInspection",
        back_populates="rework_records",
        foreign_keys=[inspection_id],
    )
    original_inspection = relationship(
        "QCInspection", foreign_keys=[original_inspection_id]
    )
    re_inspection = relationship(
        "QCInspection", foreign_keys=[re_inspection_id]
    )
    completed_by_user = relationship("User", foreign_keys=[rework_completed_by])
