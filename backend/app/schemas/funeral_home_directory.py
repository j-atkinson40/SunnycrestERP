"""Schemas for Funeral Home Directory and manufacturer customer onboarding."""

from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Directory entry response
# ---------------------------------------------------------------------------


class DirectoryEntryResponse(BaseModel):
    id: str
    place_id: str
    name: str
    address: str | None = None
    city: str | None = None
    state_code: str | None = None
    zip_code: str | None = None
    phone: str | None = None
    website: str | None = None
    google_rating: float | None = None
    google_review_count: int | None = None
    latitude: float | None = None
    longitude: float | None = None

    model_config = {"from_attributes": True}


class DirectoryListResponse(BaseModel):
    entries: list[DirectoryEntryResponse]
    total: int
    cached: bool = False


# ---------------------------------------------------------------------------
# Platform match response
# ---------------------------------------------------------------------------


class PlatformMatchResponse(BaseModel):
    id: str
    name: str
    slug: str | None = None

    model_config = {"from_attributes": True}


class PlatformMatchListResponse(BaseModel):
    matches: list[PlatformMatchResponse]
    total: int


# ---------------------------------------------------------------------------
# Selection request (Step 2 — pick from directory)
# ---------------------------------------------------------------------------


class SelectionItem(BaseModel):
    directory_entry_id: str
    action: str = Field(
        default="skipped",
        description="One of: added_as_customer, skipped, invited",
    )
    invite: bool = False


class SelectionRequest(BaseModel):
    selections: list[SelectionItem]


class SelectionResponse(BaseModel):
    created_customers: int
    invitations_sent: int
    skipped: int


# ---------------------------------------------------------------------------
# Manual customer request (Step 3 — add manually)
# ---------------------------------------------------------------------------


class ManualCustomerItem(BaseModel):
    name: str
    city: str | None = None
    phone: str | None = None
    invite: bool = False


class ManualCustomerRequest(BaseModel):
    customers: list[ManualCustomerItem]


class ManualCustomerResponse(BaseModel):
    created_customers: int


# ---------------------------------------------------------------------------
# Refresh request
# ---------------------------------------------------------------------------


class RefreshRequest(BaseModel):
    latitude: float
    longitude: float
    radius_miles: int = Field(default=50, ge=1, le=200)
