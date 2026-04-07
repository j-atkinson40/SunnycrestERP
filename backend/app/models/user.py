import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", "company_id", name="uq_users_email_company"),
        Index(
            "uq_users_username_company",
            "company_id",
            "username",
            unique=True,
            postgresql_where="username IS NOT NULL",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("roles.id"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )

    # Two-track employee model
    track: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="office_management"
    )
    username: Mapped[str | None] = mapped_column(String(50), nullable=True)
    pin_encrypted: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pin_set_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    console_access = mapped_column(JSONB, nullable=True)
    idle_timeout_minutes: Mapped[int | None] = mapped_column(
        Integer, nullable=True, server_default="30"
    )
    last_console_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    modified_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )

    company = relationship("Company", back_populates="users", foreign_keys=[company_id])
    role_obj = relationship("Role", back_populates="users", foreign_keys=[role_id])
    permission_overrides = relationship(
        "UserPermissionOverride", back_populates="user", cascade="all, delete-orphan",
        foreign_keys="[UserPermissionOverride.user_id]",
    )
    profile = relationship(
        "EmployeeProfile", back_populates="user", uselist=False, cascade="all, delete-orphan",
        foreign_keys="[EmployeeProfile.user_id]",
    )
