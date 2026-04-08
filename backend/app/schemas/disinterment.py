"""Pydantic schemas for disinterment case management, charge types,
union rotation lists, and public intake form.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Disinterment Charge Types
# ---------------------------------------------------------------------------


class ChargeTypeCreate(BaseModel):
    name: str = Field(..., max_length=120)
    calculation_type: str = Field(..., pattern=r"^(flat|per_mile|per_unit|hourly)$")
    default_rate: Decimal = Field(default=Decimal("0.00"))
    requires_input: bool = False
    input_label: str | None = None
    is_hazard_pay: bool = False
    sort_order: int = 0


class ChargeTypeUpdate(BaseModel):
    name: str | None = None
    calculation_type: str | None = None
    default_rate: Decimal | None = None
    requires_input: bool | None = None
    input_label: str | None = None
    is_hazard_pay: bool | None = None
    sort_order: int | None = None
    active: bool | None = None


class ChargeTypeResponse(BaseModel):
    id: str
    company_id: str
    name: str
    calculation_type: str
    default_rate: Decimal
    requires_input: bool
    input_label: str | None
    is_hazard_pay: bool
    sort_order: int
    active: bool
    created_at: datetime | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Union Rotation Lists
# ---------------------------------------------------------------------------


class RotationListCreate(BaseModel):
    location_id: str | None = None
    name: str = Field(..., max_length=120)
    description: str | None = None
    trigger_type: str = Field(..., pattern=r"^(hazard_pay|day_of_week|manual)$")
    trigger_config: dict = Field(default_factory=dict)
    assignment_mode: str = Field(..., pattern=r"^(sole_driver|longest_day)$")


class RotationListUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    location_id: str | None = None
    trigger_type: str | None = None
    trigger_config: dict | None = None
    assignment_mode: str | None = None
    active: bool | None = None


class RotationMemberResponse(BaseModel):
    id: str
    list_id: str
    user_id: str
    user_name: str | None = None
    rotation_position: int
    last_assigned_at: datetime | None
    last_assignment_id: str | None
    last_assignment_type: str | None
    active: bool

    model_config = {"from_attributes": True}


class RotationMemberReorder(BaseModel):
    """Full replacement of member list (drag-drop save)."""
    members: list[dict] = Field(
        ...,
        description="List of {user_id, rotation_position, active} entries",
    )


class RotationMemberToggle(BaseModel):
    active: bool


class RotationListResponse(BaseModel):
    id: str
    company_id: str
    location_id: str | None
    location_name: str | None = None
    name: str
    description: str | None
    trigger_type: str
    trigger_config: dict
    assignment_mode: str
    active: bool
    member_count: int = 0
    last_assignment_at: datetime | None = None
    created_at: datetime | None

    model_config = {"from_attributes": True}


class RotationAssignmentResponse(BaseModel):
    id: str
    list_id: str
    member_id: str
    member_name: str | None = None
    assignment_type: str
    assignment_id: str
    assigned_at: datetime | None
    assigned_by_user_id: str | None
    assigned_by_name: str | None = None
    notes: str | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Disinterment Cases
# ---------------------------------------------------------------------------

VALID_STATUSES = {
    "intake",
    "quoted",
    "quote_accepted",
    "signatures_pending",
    "signatures_complete",
    "scheduled",
    "complete",
    "cancelled",
}


class NextOfKinEntry(BaseModel):
    name: str
    email: str
    phone: str | None = None
    relationship: str


class DisintermentCaseCreate(BaseModel):
    """Minimal — creates a shell case with intake token."""
    decedent_name: str = Field(default="Pending Intake", max_length=200)


class DisintermentCaseUpdate(BaseModel):
    """Staff review/edit of intake data."""
    decedent_name: str | None = None
    date_of_death: date | None = None
    date_of_burial: date | None = None
    reason: str | None = None
    destination: str | None = None
    vault_description: str | None = None
    cemetery_id: str | None = None
    cemetery_lot_section: str | None = None
    cemetery_lot_space: str | None = None
    funeral_home_id: str | None = None
    funeral_director_contact_id: str | None = None
    next_of_kin: list[NextOfKinEntry] | None = None


class DisintermentScheduleRequest(BaseModel):
    scheduled_date: date
    assigned_driver_id: str | None = None
    assigned_crew: list[str] = Field(default_factory=list)


class SignatureStatus(BaseModel):
    party: str
    status: str
    signed_at: datetime | None


class DisintermentCaseResponse(BaseModel):
    id: str
    company_id: str
    case_number: str
    status: str

    # Decedent
    decedent_name: str
    date_of_death: date | None
    date_of_burial: date | None
    reason: str | None
    destination: str | None
    vault_description: str | None

    # Cemetery
    cemetery_id: str | None
    cemetery_name: str | None = None
    cemetery_lot_section: str | None
    cemetery_lot_space: str | None
    fulfilling_location_id: str | None
    fulfilling_location_name: str | None = None

    # Relationships
    funeral_home_id: str | None
    funeral_home_name: str | None = None
    funeral_director_contact_id: str | None
    next_of_kin: list[dict]

    # Intake
    intake_token: str | None
    intake_submitted_at: datetime | None

    # Quote
    quote_id: str | None
    accepted_quote_amount: Decimal | None
    has_hazard_pay: bool

    # Signatures
    docusign_envelope_id: str | None
    signatures: list[SignatureStatus] = []

    # Scheduling
    scheduled_date: date | None
    assigned_driver_id: str | None
    assigned_driver_name: str | None = None
    assigned_crew: list
    rotation_assignment_id: str | None

    # Completion
    completed_at: datetime | None
    invoice_id: str | None

    # Audit
    created_by_user_id: str | None
    created_at: datetime | None
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class DisintermentCaseListItem(BaseModel):
    id: str
    case_number: str
    decedent_name: str
    status: str
    cemetery_name: str | None = None
    funeral_home_name: str | None = None
    scheduled_date: date | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


class PaginatedDisintermentCases(BaseModel):
    items: list[DisintermentCaseListItem]
    total: int
    page: int
    per_page: int


# ---------------------------------------------------------------------------
# Public Intake Form
# ---------------------------------------------------------------------------


class IntakeFormData(BaseModel):
    """Public intake form submission — no auth."""
    decedent_name: str = Field(..., max_length=200)
    date_of_death: date | None = None
    date_of_burial: date | None = None
    vault_description: str | None = None

    # Cemetery
    cemetery_name: str | None = None
    cemetery_city: str | None = None
    cemetery_state: str | None = None
    cemetery_lot_section: str | None = None
    cemetery_lot_space: str | None = None

    # Reason & destination
    reason: str = Field(..., max_length=500)
    destination: str = Field(..., max_length=500)

    # Funeral home contact
    funeral_director_name: str = Field(..., max_length=200)
    funeral_director_email: str = Field(..., max_length=300)
    funeral_director_phone: str | None = None
    funeral_home_name: str | None = None

    # Next of kin
    next_of_kin: list[NextOfKinEntry] = Field(default_factory=list)

    # Confirmation
    confirmed_accurate: bool = True


class IntakeTokenResponse(BaseModel):
    """Response when validating a public intake token."""
    case_number: str
    status: str
    already_submitted: bool
    company_name: str | None = None


class IntakeSubmitResponse(BaseModel):
    case_number: str
    message: str = "Intake submitted successfully. We will be in touch to confirm the quote and next steps."


# ---------------------------------------------------------------------------
# Cemetery Location
# ---------------------------------------------------------------------------


class CemeteryLocationUpdate(BaseModel):
    fulfilling_location_id: str
