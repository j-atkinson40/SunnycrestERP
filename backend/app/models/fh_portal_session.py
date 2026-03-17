import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, func

from app.database import Base


class FHPortalSession(Base):
    """Family portal session — token-based access for case contacts."""

    __tablename__ = "fh_portal_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    case_id = Column(String(36), ForeignKey("fh_cases.id"), nullable=False)
    contact_id = Column(String(36), ForeignKey("fh_case_contacts.id"), nullable=False)

    access_token = Column(String(100), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    last_accessed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
