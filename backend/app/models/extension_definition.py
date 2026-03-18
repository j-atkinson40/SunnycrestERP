"""Extension definition — the master catalog of all platform extensions."""

import json
import uuid

from sqlalchemy import Boolean, Column, DateTime, Integer, Numeric, String, Text, func

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

    # ── Catalog fields ──
    tagline = Column(String(300), nullable=True)
    category = Column(String(40), nullable=False, default="workflow")
    publisher = Column(String(30), nullable=False, default="first_party")
    applicable_verticals = Column(Text, nullable=True)  # JSON array
    default_enabled_for = Column(Text, nullable=True)  # JSON array
    access_model = Column(String(30), nullable=False, default="included")
    required_plan_tier = Column(String(40), nullable=True)
    addon_price_monthly = Column(Numeric(10, 2), nullable=True)
    status = Column(String(30), nullable=False, default="active")
    screenshots = Column(Text, nullable=True)  # JSON array of {url, caption}
    feature_bullets = Column(Text, nullable=True)  # JSON array of strings
    setup_required = Column(Boolean, default=False)
    setup_config_schema = Column(Text, nullable=True)  # JSON Schema for setup wizard
    hooks_registered = Column(Text, nullable=True)  # JSON array of hook names
    group = Column(String(60), nullable=True)
    cannot_disable = Column(Boolean, default=False)
    sort_order = Column(Integer, default=100)
    requested_by_tenant_id = Column(String(36), nullable=True)
    is_customer_requested = Column(Boolean, default=False)
    notify_me_count = Column(Integer, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    @property
    def schema_dict(self) -> dict:
        if not self.config_schema:
            return {}
        return json.loads(self.config_schema)

    def _json_list(self, field_value) -> list:
        if not field_value:
            return []
        return json.loads(field_value)

    @property
    def applicable_verticals_list(self) -> list[str]:
        return self._json_list(self.applicable_verticals)

    @property
    def default_enabled_for_list(self) -> list[str]:
        return self._json_list(self.default_enabled_for)

    @property
    def screenshots_list(self) -> list[dict]:
        return self._json_list(self.screenshots)

    @property
    def feature_bullets_list(self) -> list[str]:
        return self._json_list(self.feature_bullets)

    @property
    def hooks_registered_list(self) -> list[str]:
        return self._json_list(self.hooks_registered)

    @property
    def setup_config_schema_dict(self) -> dict:
        if not self.setup_config_schema:
            return {}
        return json.loads(self.setup_config_schema)
