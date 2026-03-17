import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class CureSchedule(Base):
    __tablename__ = "cure_schedules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    duration_hours = Column(Integer, nullable=False)
    minimum_strength_release_percent = Column(Integer, nullable=False, default=70)
    temperature_adjusted = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True)
