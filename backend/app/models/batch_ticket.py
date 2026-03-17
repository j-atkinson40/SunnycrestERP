import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text, func

from app.database import Base


class BatchTicket(Base):
    __tablename__ = "batch_tickets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    pour_event_id = Column(String(36), ForeignKey("pour_events.id"), nullable=False)
    mix_design_id = Column(String(36), ForeignKey("mix_designs.id"), nullable=True)
    design_strength_psi = Column(Integer, nullable=True)
    water_cement_ratio = Column(Numeric(5, 3), nullable=True)
    slump_inches = Column(Numeric(5, 2), nullable=True)
    air_content_percent = Column(Numeric(5, 2), nullable=True)
    ambient_temp_f = Column(Integer, nullable=True)
    concrete_temp_f = Column(Integer, nullable=True)
    yield_cubic_yards = Column(Numeric(8, 2), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True)
