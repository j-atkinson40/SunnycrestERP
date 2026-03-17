import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class MixDesign(Base):
    __tablename__ = "mix_designs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    mix_design_code = Column(String(50), nullable=False)
    name = Column(String(200), nullable=False)
    design_strength_psi = Column(Integer, nullable=False)
    cement_type = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    npca_approved = Column(Boolean, default=False)
    cure_schedule_id = Column(String(36), ForeignKey("cure_schedules.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True)
