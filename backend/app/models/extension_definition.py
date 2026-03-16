"""Extension definition — registered extensions that can be enabled per tenant."""

import json
import uuid

from sqlalchemy import Boolean, Column, DateTime, String, Text, func

from app.database import Base


class ExtensionDefinition(Base):
    __tablename__ = "extension_definitions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    extension_key = Column(String(100), unique=True, nullable=False, index=True)
    module_key = Column(String(80), nullable=False)
    display_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    config_schema = Column(Text, nullable=True)  # JSON schema for extension config
    version = Column(String(20), default="1.0.0")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    @property
    def schema_dict(self) -> dict:
        if not self.config_schema:
            return {}
        return json.loads(self.config_schema)
