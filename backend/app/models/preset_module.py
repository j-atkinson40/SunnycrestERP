"""Join table linking vertical presets to module definitions."""

import uuid
from sqlalchemy import Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class PresetModule(Base):
    __tablename__ = "preset_modules"
    __table_args__ = (
        UniqueConstraint("preset_id", "module_key", name="uq_preset_module"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    preset_id = Column(String(36), ForeignKey("vertical_presets.id"), nullable=False)
    module_key = Column(String(80), nullable=False)

    preset = relationship("VerticalPreset", back_populates="modules")
