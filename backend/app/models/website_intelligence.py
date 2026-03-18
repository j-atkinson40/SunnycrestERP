"""Website Intelligence — scrape results and AI-generated onboarding suggestions."""

import json
import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, func

from app.database import Base


class TenantWebsiteIntelligence(Base):
    __tablename__ = "tenant_website_intelligence"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(
        String(36), ForeignKey("companies.id"), nullable=False, unique=True, index=True
    )
    website_url = Column(String(500), nullable=False)
    scrape_status = Column(String(20), nullable=False, default="pending")
    scrape_started_at = Column(DateTime(timezone=True), nullable=True)
    scrape_completed_at = Column(DateTime(timezone=True), nullable=True)
    raw_content = Column(Text, nullable=True)
    pages_scraped = Column(Text, nullable=True)  # JSON list of URLs
    analysis_result = Column(Text, nullable=True)  # JSON analysis output
    confidence_scores = Column(Text, nullable=True)  # JSON confidence map
    applied_to_onboarding = Column(Boolean, default=False)
    tenant_confirmed_at = Column(DateTime(timezone=True), nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    estimated_cost = Column(Numeric(8, 4), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    @property
    def analysis_dict(self) -> dict:
        if not self.analysis_result:
            return {}
        return json.loads(self.analysis_result)

    @property
    def pages_scraped_list(self) -> list[str]:
        if not self.pages_scraped:
            return []
        return json.loads(self.pages_scraped)

    @property
    def confidence_dict(self) -> dict:
        if not self.confidence_scores:
            return {}
        return json.loads(self.confidence_scores)


class WebsiteIntelligenceSuggestion(Base):
    __tablename__ = "website_intelligence_suggestions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    suggestion_type = Column(String(30), nullable=False)
    suggestion_key = Column(String(100), nullable=False)
    suggestion_label = Column(String(255), nullable=False)
    confidence = Column(Numeric(3, 2), nullable=False)
    evidence = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    dismissed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
