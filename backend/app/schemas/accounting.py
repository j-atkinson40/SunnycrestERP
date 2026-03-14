from datetime import datetime

from pydantic import BaseModel


class AccountingProviderInfo(BaseModel):
    key: str
    name: str
    description: str
    supports_sync: bool


class AccountingConfigResponse(BaseModel):
    provider: str
    connected: bool
    last_sync_at: datetime | None = None
    error: str | None = None
    details: dict = {}


class AccountingProviderUpdate(BaseModel):
    provider: str  # none, sage_csv, quickbooks_online


class SyncRequest(BaseModel):
    sync_type: str  # customers, invoices, payments, bills, bill_payments, inventory
    direction: str = "push"  # push, pull, bidirectional
    date_from: datetime | None = None
    date_to: datetime | None = None


class SyncResultResponse(BaseModel):
    success: bool
    records_synced: int = 0
    records_failed: int = 0
    sync_log_id: str | None = None
    error_message: str | None = None
    details: dict | None = None


class ProviderAccountResponse(BaseModel):
    id: str
    name: str
    account_type: str
    number: str | None = None
    is_active: bool = True


class AccountMappingResponse(BaseModel):
    internal_id: str
    internal_name: str
    provider_id: str | None = None
    provider_name: str | None = None


class AccountMappingUpdate(BaseModel):
    internal_id: str
    provider_id: str


class QBOConnectResponse(BaseModel):
    authorization_url: str
    state: str
