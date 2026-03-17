import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON

from app.database import Base


class FHObituary(Base):
    """Obituary content for a funeral home case, with AI generation and family approval tracking."""

    __tablename__ = "fh_obituaries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    case_id = Column(String(36), ForeignKey("fh_cases.id"), nullable=False, index=True)

    content = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default="draft")

    generated_by = Column(String(30), nullable=True)
    ai_prompt_used = Column(Text, nullable=True)

    family_approved_at = Column(DateTime(timezone=True), nullable=True)
    family_approved_by_contact_id = Column(String(36), ForeignKey("fh_case_contacts.id"), nullable=True)
    family_approval_notes = Column(Text, nullable=True)

    version = Column(Integer, nullable=False, default=1)
    published_locations = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True)
