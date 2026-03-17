import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, func

from app.database import Base


class FHDocument(Base):
    """Document uploaded for a funeral home case (death cert, permits, authorizations, etc.)."""

    __tablename__ = "fh_documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    case_id = Column(String(36), ForeignKey("fh_cases.id"), nullable=False, index=True)

    document_type = Column(String(40), nullable=False)
    document_name = Column(String(200), nullable=False)
    file_url = Column(String(500), nullable=False)

    uploaded_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
