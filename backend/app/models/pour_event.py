import uuid

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class PourEvent(Base):
    __tablename__ = "pour_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    pour_event_number = Column(String(50), nullable=False)
    pour_date = Column(Date, nullable=False)
    pour_time = Column(String(20), nullable=True)
    crew_notes = Column(Text, nullable=True)
    status = Column(String(30), default="planned")
    batch_ticket_id = Column(String(36), nullable=True)
    cure_schedule_id = Column(String(36), ForeignKey("cure_schedules.id"), nullable=True)
    cure_start_at = Column(DateTime(timezone=True), nullable=True)
    cure_complete_at = Column(DateTime(timezone=True), nullable=True)
    actual_release_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True)


class PourEventWorkOrder(Base):
    __tablename__ = "pour_event_work_orders"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    pour_event_id = Column(String(36), ForeignKey("pour_events.id"), nullable=False)
    work_order_id = Column(String(36), ForeignKey("work_orders.id"), nullable=False)
    quantity_in_this_pour = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
