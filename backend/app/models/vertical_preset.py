"""Vertical preset — predefined module bundles for different business types."""

import uuid
from sqlalchemy import Column, DateTime, Integer, String, Text, func
from sqlalchemy.orm import relationship
from app.database import Base


class VerticalPreset(Base):
    __tablename__ = "vertical_presets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key = Column(String(50), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String(50), nullable=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    modules = relationship("PresetModule", back_populates="preset", cascade="all, delete-orphan")
