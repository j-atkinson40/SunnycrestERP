import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, func

from app.database import Base


class FHCaseContact(Base):
    """Contact person associated with a funeral home case."""

    __tablename__ = "fh_case_contacts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    case_id = Column(String(36), ForeignKey("fh_cases.id"), nullable=False, index=True)

    contact_type = Column(String(30), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    relationship_to_deceased = Column(String(100), nullable=True)

    phone_primary = Column(String(20), nullable=True)
    phone_secondary = Column(String(20), nullable=True)
    email = Column(String(200), nullable=True)

    address = Column(String(300), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(2), nullable=True)
    zip = Column(String(10), nullable=True)

    is_primary = Column(Boolean, default=False)
    receives_portal_access = Column(Boolean, default=False)
    portal_invite_sent_at = Column(DateTime(timezone=True), nullable=True)
    portal_last_login_at = Column(DateTime(timezone=True), nullable=True)

    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True)
