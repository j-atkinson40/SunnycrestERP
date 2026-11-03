import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("slug", "company_id", name="uq_roles_slug_company"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ⚠️ NULLABLE, AND NULL IS A VALUE. NULL means no area restriction was ever
    # established — today's behaviour for every existing role, never backfilled.
    # `[]` means limited to nothing. See app/core/areas.py and r221.
    #
    # There is no `default=` here on purpose: a Python-side default would make
    # every newly-created role limited, and a model default is invisible to
    # `information_schema` and to the drift guard (CLAUDE.md §5, "a DEFAULT can
    # live in more than one layer").
    limited_to_areas: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    modified_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )

    company = relationship("Company", back_populates="roles")
    permissions = relationship(
        "RolePermission", back_populates="role", cascade="all, delete-orphan"
    )
    users = relationship("User", back_populates="role_obj", foreign_keys="[User.role_id]")
