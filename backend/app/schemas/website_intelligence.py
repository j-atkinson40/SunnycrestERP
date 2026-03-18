"""Schemas for Website Intelligence feature."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SuggestionResponse(BaseModel):
    id: str
    suggestion_type: str
    suggestion_key: str
    suggestion_label: str
    confidence: float
    evidence: str | None
    status: str
    confidence_label: str  # computed: "High confidence" / "Likely" / "Possible"

    model_config = ConfigDict(from_attributes=True)


class WebsiteIntelligenceResponse(BaseModel):
    id: str
    tenant_id: str
    website_url: str
    scrape_status: str
    analysis_result: dict | None
    suggestions: list[SuggestionResponse]
    summary: str | None
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost: float | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SuggestionUpdateRequest(BaseModel):
    status: str  # "accepted" or "dismissed"


class WebsiteIntelligenceCreate(BaseModel):
    website_url: str
