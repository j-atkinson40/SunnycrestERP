from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Network Relationship schemas
# ---------------------------------------------------------------------------


class NetworkRelationshipCreate(BaseModel):
    target_company_id: str
    relationship_type: str = Field(
        ..., description="supplier, customer, partner, affiliated"
    )
    permissions: str | None = None  # JSON string
    notes: str | None = None


class NetworkRelationshipUpdate(BaseModel):
    relationship_type: str | None = None
    status: str | None = None
    permissions: str | None = None
    notes: str | None = None


class CompanySummary(BaseModel):
    id: str
    name: str
    slug: str

    class Config:
        from_attributes = True


class NetworkRelationshipResponse(BaseModel):
    id: str
    requesting_company_id: str
    target_company_id: str
    relationship_type: str
    status: str
    permissions: str | None = None
    notes: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime
    requesting_company: CompanySummary | None = None
    target_company: CompanySummary | None = None

    class Config:
        from_attributes = True


class PaginatedRelationships(BaseModel):
    items: list[NetworkRelationshipResponse]
    total: int
    page: int
    per_page: int


# ---------------------------------------------------------------------------
# Network Transaction schemas
# ---------------------------------------------------------------------------


class NetworkTransactionCreate(BaseModel):
    relationship_id: str
    target_company_id: str
    transaction_type: str = Field(
        ..., description="order, invoice, payment, case_transfer, status_update"
    )
    source_record_type: str | None = None
    source_record_id: str | None = None
    target_record_type: str | None = None
    target_record_id: str | None = None
    payload: str | None = None  # JSON string


class NetworkTransactionResponse(BaseModel):
    id: str
    relationship_id: str
    source_company_id: str
    target_company_id: str
    transaction_type: str
    source_record_type: str | None = None
    source_record_id: str | None = None
    target_record_type: str | None = None
    target_record_id: str | None = None
    payload: str | None = None
    status: str
    error_message: str | None = None
    created_by: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class PaginatedTransactions(BaseModel):
    items: list[NetworkTransactionResponse]
    total: int
    page: int
    per_page: int


class NetworkStats(BaseModel):
    total_relationships: int
    active_relationships: int
    pending_relationships: int
    total_transactions: int
    transactions_30d: int
