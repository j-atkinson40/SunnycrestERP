"""Pydantic schemas for the signing API — Phase D-4."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ── Admin: envelope creation ─────────────────────────────────────────


class PartyCreateRequest(BaseModel):
    signing_order: int = Field(..., ge=1)
    role: str = Field(..., min_length=1, max_length=64)
    display_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    phone: str | None = Field(None, max_length=32)


class FieldCreateRequest(BaseModel):
    signing_order: int = Field(..., ge=1)  # which party
    field_type: str  # signature | initial | date | typed_name | checkbox | text
    anchor_string: str | None = Field(None, max_length=255)
    page_number: int | None = None
    position_x: float | None = None
    position_y: float | None = None
    width: float | None = None
    height: float | None = None
    required: bool = True
    label: str | None = Field(None, max_length=255)
    default_value: str | None = None


class EnvelopeCreateRequest(BaseModel):
    document_id: str
    subject: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    routing_type: str = Field("sequential", pattern="^(sequential|parallel)$")
    expires_in_days: int = Field(30, ge=1, le=365)
    parties: list[PartyCreateRequest]
    fields: list[FieldCreateRequest] = Field(default_factory=list)


class EnvelopeVoidRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=2000)


# ── Responses ─────────────────────────────────────────────────────────


class PartyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    envelope_id: str
    signing_order: int
    role: str
    display_name: str
    email: str
    phone: str | None = None
    status: str
    sent_at: datetime | None = None
    viewed_at: datetime | None = None
    consented_at: datetime | None = None
    signed_at: datetime | None = None
    declined_at: datetime | None = None
    decline_reason: str | None = None
    signing_ip_address: str | None = None
    signature_type: str | None = None
    typed_signature_name: str | None = None
    notification_sent_count: int = 0
    last_notification_sent_at: datetime | None = None


class FieldResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    envelope_id: str
    party_id: str
    field_type: str
    anchor_string: str | None = None
    page_number: int | None = None
    position_x: float | None = None
    position_y: float | None = None
    width: float | None = None
    height: float | None = None
    required: bool
    label: str | None = None
    default_value: str | None = None
    value: str | None = None


class EnvelopeListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    company_id: str
    document_id: str
    subject: str
    description: str | None = None
    routing_type: str
    status: str
    expires_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class EnvelopeDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    company_id: str
    document_id: str
    subject: str
    description: str | None = None
    routing_type: str
    status: str
    document_hash: str
    expires_at: datetime | None = None
    completed_at: datetime | None = None
    voided_at: datetime | None = None
    void_reason: str | None = None
    certificate_document_id: str | None = None
    created_by_user_id: str
    created_at: datetime
    updated_at: datetime
    parties: list[PartyResponse]
    fields: list[FieldResponse]


class SignatureEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    envelope_id: str
    party_id: str | None = None
    sequence_number: int
    event_type: str
    actor_user_id: str | None = None
    actor_party_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    meta_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


# ── Public signer schemas ────────────────────────────────────────────


class SignerStatusResponse(BaseModel):
    """What the signer sees on landing — enough to render the correct state
    without exposing envelope internals across-tenant."""

    envelope_status: str
    party_status: str
    envelope_subject: str
    envelope_description: str | None = None
    party_display_name: str
    party_role: str
    signing_order: int
    routing_type: str
    expires_at: datetime | None = None
    is_my_turn: bool
    document_title: str
    company_name: str
    signed_by_previous_parties: list[dict[str, Any]] = Field(
        default_factory=list
    )


class ConsentRequest(BaseModel):
    consent_text: str = Field(..., min_length=1, max_length=5000)


class SignRequest(BaseModel):
    signature_type: str = Field(..., pattern="^(drawn|typed|uploaded)$")
    signature_data: str = Field(..., min_length=1)
    typed_signature_name: str | None = None
    field_values: dict[str, str] = Field(default_factory=dict)


class DeclineRequest(BaseModel):
    reason: str = Field(..., min_length=10, max_length=500)


class SignActionResponse(BaseModel):
    """Generic success response for public signer actions."""

    success: bool = True
    party_status: str
    envelope_status: str
    message: str | None = None
