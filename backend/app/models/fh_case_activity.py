import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSON

from app.database import Base


class FHCaseActivity(Base):
    """Timeline / audit log entry for a funeral home case."""

    __tablename__ = "fh_case_activity"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    case_id = Column(String(36), ForeignKey("fh_cases.id"), nullable=False, index=True)

    activity_type = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    performed_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    metadata_ = Column("metadata", JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
