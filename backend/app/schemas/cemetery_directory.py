"""Schemas for Cemetery Directory and manufacturer cemetery onboarding."""

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Directory entry response
# ---------------------------------------------------------------------------


class CemeteryDirectoryEntryResponse(BaseModel):
    id: str
    place_id: str
    name: str
    address: str | None = None
    city: str | None = None
    state_code: str | None = None
    zip_code: str | None = None
    county: str | None = None
    google_rating: float | None = None
    google_review_count: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    # True if this place_id already has a CemeteryDirectorySelection for this company
    already_added: bool = False
    distance_miles: float | None = None
    source: str = "google_places"

    model_config = {"from_attributes": True}


class CemeteryDirectoryListResponse(BaseModel):
    entries: list[CemeteryDirectoryEntryResponse]
    total: int
    cached: bool = False


# ---------------------------------------------------------------------------
# Selection request — equipment settings per cemetery
# ---------------------------------------------------------------------------


class CemeteryEquipmentSettings(BaseModel):
    provides_lowering_device: bool = False
    provides_grass: bool = False
    provides_tent: bool = False
    provides_chairs: bool = False


class CemeterySelectionItem(BaseModel):
    place_id: str
    name: str
    action: str = Field(
        default="skip",
        description="One of: add, skip",
    )
    equipment: CemeteryEquipmentSettings = Field(default_factory=CemeteryEquipmentSettings)
    county: str | None = None
    equipment_note: str | None = None


class CemeteryManualEntry(BaseModel):
    name: str
    city: str | None = None
    state: str | None = None
    county: str | None = None
    equipment: CemeteryEquipmentSettings = Field(default_factory=CemeteryEquipmentSettings)
    equipment_note: str | None = None


class CemeterySelectionRequest(BaseModel):
    selections: list[CemeterySelectionItem] = Field(default_factory=list)
    manual_entries: list[CemeteryManualEntry] = Field(default_factory=list)


class CemeterySelectionResponse(BaseModel):
    created: int
    skipped: int
    errors: int = 0


# ---------------------------------------------------------------------------
# Refresh request
# ---------------------------------------------------------------------------


class CemeteryRefreshRequest(BaseModel):
    radius_miles: int = Field(default=50, ge=1, le=200)


# ---------------------------------------------------------------------------
# Platform cemetery matches (Step 0 of wizard)
# ---------------------------------------------------------------------------


class CemeteryPlatformMatchResponse(BaseModel):
    id: str
    name: str
    city: str | None = None
    state: str | None = None
    connected: bool = False


class CemeteryPlatformMatchListResponse(BaseModel):
    matches: list[CemeteryPlatformMatchResponse]
    total: int


class CemeteryPlatformConnectRequest(BaseModel):
    cemetery_tenant_id: str


class CemeteryPlatformConnectResponse(BaseModel):
    connected: bool
    cemetery_id: str | None = None
