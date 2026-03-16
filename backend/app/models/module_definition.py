"""Module definition — master registry of all available platform modules."""

import uuid
import json
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func
from app.database import Base


class ModuleDefinition(Base):
    __tablename__ = "module_definitions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key = Column(String(80), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=False, default="business")
    icon = Column(String(50), nullable=True)
    sort_order = Column(Integer, default=0)
    is_core = Column(Boolean, default=False)
    dependencies = Column(Text, nullable=True)  # JSON array of module keys
    feature_flags = Column(Text, nullable=True)  # JSON array of flag keys
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    @property
    def dependency_list(self) -> list[str]:
        if not self.dependencies:
            return []
        return json.loads(self.dependencies)

    @property
    def feature_flag_list(self) -> list[str]:
        if not self.feature_flags:
            return []
        return json.loads(self.feature_flags)
