"""Union rotation list models — location-aware rotation for disinterment,
Saturday, and Sunday job types.

Tables: union_rotation_lists, union_rotation_members, union_rotation_assignments
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UnionRotationList(Base):
    """A named rotation list scoped to a tenant and optionally a location."""

    __tablename__ = "union_rotation_lists"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    location_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
    )  # NULL = all locations; populated = location-specific
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # hazard_pay, day_of_week, manual
    trigger_config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="'{}'"
    )
    assignment_mode: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # sole_driver, longest_day
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    company = relationship("Company", foreign_keys=[company_id])
    location = relationship("Company", foreign_keys=[location_id])
    members = relationship(
        "UnionRotationMember",
        back_populates="rotation_list",
        order_by="UnionRotationMember.rotation_position",
    )
    assignments = relationship(
        "UnionRotationAssignment", back_populates="rotation_list"
    )


class UnionRotationMember(Base):
    """An employee on a rotation list with a position and last-assigned tracking."""

    __tablename__ = "union_rotation_members"
    __table_args__ = (
        UniqueConstraint(
            "list_id", "rotation_position", name="uq_rotation_member_position"
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    list_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("union_rotation_lists.id"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    rotation_position: Mapped[int] = mapped_column(Integer, nullable=False)
    last_assigned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_assignment_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    last_assignment_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    # Relationships
    rotation_list = relationship("UnionRotationList", back_populates="members")
    user = relationship("User")


class UnionRotationAssignment(Base):
    """Record of a rotation assignment — links a member to a job."""

    __tablename__ = "union_rotation_assignments"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    list_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("union_rotation_lists.id"),
        nullable=False,
        index=True,
    )
    member_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("union_rotation_members.id"),
        nullable=False,
        index=True,
    )
    assignment_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # disinterment, funeral_saturday, etc.
    assignment_id: Mapped[str] = mapped_column(
        String(36), nullable=False
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    assigned_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    rotation_list = relationship(
        "UnionRotationList", back_populates="assignments"
    )
    member = relationship("UnionRotationMember")
    assigned_by = relationship("User", foreign_keys=[assigned_by_user_id])
