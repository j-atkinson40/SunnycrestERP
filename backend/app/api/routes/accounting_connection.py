"""Accounting connection onboarding & management endpoints.

Handles the three-stage accounting connection flow:
  Stage 1 — Select software (or skip / send to accountant)
  Stage 2 — Connect (QBO OAuth, QBD Web Connector, Sage 100)
  Stage 3 — Configure sync settings & account mappings
"""

import json
import secrets
import time
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.config import settings
from app.database import get_db
from app.models.accounting_connection import AccountingConnection
from app.models.company import Company
from app.models.customer_accounting_mapping import CustomerAccountingMapping
from app.models.user import User
from app.services.onboarding_service import check_completion

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas (inline — small set, co-located with routes)
# ---------------------------------------------------------------------------


class ConnectionStatusResponse(BaseModel):
    id: str | None = None
    provider: str | None = None
    status: str  # not_started | connecting | connected | error | disconnected | skipped
    setup_stage: str | None = None
    qbo_company_name: str | None = None
    sage_version: str | None = None
    sage_connection_method: str | None = None
    sage_csv_schedule: str | None = None
    last_sync_at: str | None = None
    last_sync_status: str | None = None
    last_sync_error: str | None = None
    accountant_email: str | None = None
    accountant_name: str | None = None
    skip_count: int = 0
    skipped_at: str | None = None
    sync_config: dict | None = None
    account_mappings: dict | None = None
    connection_attempt_count: int = 0
    income_account_mappings: dict | None = None
    csv_column_mappings: dict | None = None
    customer_match_completed: bool = False


class SelectProviderRequest(BaseModel):
    provider: str  # quickbooks_online | quickbooks_desktop | sage_100


class SkipRequest(BaseModel):
    pass  # empty body — just POST to skip


class SendToAccountantRequest(BaseModel):
    email: str
    name: str | None = None
    message: str | None = None


class SageConfigRequest(BaseModel):
    version: str | None = None
    connection_method: str  # api | csv
    api_endpoint: str | None = None
    csv_schedule: str | None = None  # manual | daily | weekly


class SyncConfigRequest(BaseModel):
    sync_customers: bool = True
    sync_invoices: bool = True
    sync_payments: bool = True
    sync_inventory: bool = False


class AccountMappingsRequest(BaseModel):
    mappings: dict  # { internal_key: provider_account_id }


class CompleteSetupRequest(BaseModel):
    pass


class CustomerMatchItem(BaseModel):
    customer_id: str
    qbo_customer_id: str | None = None
    qbd_customer_id: str | None = None
    sage_customer_id: str | None = None
    match_method: str = "auto_matched"
    confidence: float = 1.0


class ConfirmCustomerMatchesRequest(BaseModel):
    matches: list[CustomerMatchItem]


class IncomeAccountMappingsRequest(BaseModel):
    default_account: str
    category_mappings: dict  # { category_key: account_id }


class SageDetectVersionRequest(BaseModel):
    server_url: str


class SageAnalyzeCsvRequest(BaseModel):
    export_type: str  # invoice_history | customer_list | cash_receipts
    csv_headers: list[str]
    sample_rows: list[list[str]]


class SageSaveCsvConfigRequest(BaseModel):
    export_type: str
    mappings: dict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_or_create_connection(
    db: Session, company_id: str
) -> AccountingConnection:
    """Get existing connection or create a new one."""
    conn = (
        db.query(AccountingConnection)
        .filter(AccountingConnection.company_id == company_id)
        .first()
    )
    if not conn:
        conn = AccountingConnection(
            id=str(uuid.uuid4()),
            company_id=company_id,
            provider="",
            status="not_started",
            setup_stage="select_software",
        )
        db.add(conn)
        db.flush()
    return conn


def _to_response(conn: AccountingConnection) -> ConnectionStatusResponse:
    return ConnectionStatusResponse(
        id=conn.id,
        provider=conn.provider or None,
        status=conn.status,
        setup_stage=conn.setup_stage,
        qbo_company_name=conn.qbo_company_name,
        sage_version=conn.sage_version,
        sage_connection_method=conn.sage_connection_method,
        sage_csv_schedule=conn.sage_csv_schedule,
        last_sync_at=conn.last_sync_at.isoformat() if conn.last_sync_at else None,
        last_sync_status=conn.last_sync_status,
        last_sync_error=conn.last_sync_error,
        accountant_email=conn.accountant_email,
        accountant_name=conn.accountant_name,
        skip_count=conn.skip_count,
        skipped_at=conn.skipped_at.isoformat() if conn.skipped_at else None,
        sync_config=conn.sync_config,
        account_mappings=conn.account_mappings,
        connection_attempt_count=conn.connection_attempt_count,
        income_account_mappings=conn.income_account_mappings,
        csv_column_mappings=conn.csv_column_mappings,
        customer_match_completed=conn.customer_match_completed,
    )


# ---------------------------------------------------------------------------
# GET status
# ---------------------------------------------------------------------------


@router.get("/status", response_model=ConnectionStatusResponse)
def get_connection_status(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get the current accounting connection status."""
    conn = (
        db.query(AccountingConnection)
        .filter(AccountingConnection.company_id == current_user.company_id)
        .first()
    )
    if not conn:
        return ConnectionStatusResponse(status="not_started")
    return _to_response(conn)


# ---------------------------------------------------------------------------
# Stage 1 — Select provider
# ---------------------------------------------------------------------------


@router.post("/select-provider", response_model=ConnectionStatusResponse)
def select_provider(
    body: SelectProviderRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Select the accounting software provider."""
    valid = {"quickbooks_online", "quickbooks_desktop", "sage_100"}
    if body.provider not in valid:
        raise HTTPException(400, f"Invalid provider. Must be one of: {', '.join(valid)}")

    conn = _get_or_create_connection(db, current_user.company_id)
    conn.provider = body.provider
    conn.status = "connecting"
    conn.setup_stage = "connect"
    conn.updated_at = datetime.now(UTC)

    # Also set on company for existing provider factory
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if company:
        provider_map = {
            "quickbooks_online": "quickbooks_online",
            "quickbooks_desktop": "quickbooks_desktop",
            "sage_100": "sage_csv",
        }
        company.accounting_provider = provider_map.get(body.provider, body.provider)

    db.commit()
    db.refresh(conn)
    return _to_response(conn)


# ---------------------------------------------------------------------------
# Stage 1 — Skip
# ---------------------------------------------------------------------------


@router.post("/skip", response_model=ConnectionStatusResponse)
def skip_accounting(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Skip accounting setup. Increments skip counter."""
    conn = _get_or_create_connection(db, current_user.company_id)
    conn.status = "skipped"
    conn.skip_count = (conn.skip_count or 0) + 1
    conn.skipped_at = datetime.now(UTC)
    conn.updated_at = datetime.now(UTC)

    # Store in company settings for banner logic
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if company:
        company.set_setting("accounting_connection_status", "skipped")
        company.set_setting("accounting_skip_count", conn.skip_count)
        company.set_setting("accounting_skipped_at", conn.skipped_at.isoformat())

    db.commit()
    db.refresh(conn)
    return _to_response(conn)


# ---------------------------------------------------------------------------
# Stage 1 — Send to accountant
# ---------------------------------------------------------------------------


@router.post("/send-to-accountant", response_model=ConnectionStatusResponse)
def send_to_accountant(
    body: SendToAccountantRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Generate a 7-day token and store accountant info."""
    conn = _get_or_create_connection(db, current_user.company_id)
    conn.accountant_email = body.email
    conn.accountant_name = body.name
    conn.accountant_token = secrets.token_urlsafe(32)
    conn.accountant_token_expires_at = datetime.now(UTC) + timedelta(days=7)
    conn.status = "connecting"
    conn.setup_stage = "connect"
    conn.updated_at = datetime.now(UTC)

    # Store in company settings for banner logic
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if company:
        company.set_setting("accounting_connection_status", "pending_accountant")
        company.set_setting("accounting_accountant_email", body.email)

    db.commit()
    db.refresh(conn)

    # TODO: Send email to accountant with setup link
    # For now, the token is generated and stored

    return _to_response(conn)


# ---------------------------------------------------------------------------
# Stage 2 — QBO connect (initiates OAuth)
# ---------------------------------------------------------------------------


@router.post("/qbo/connect")
def qbo_connect(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Generate QBO OAuth authorization URL."""
    conn = _get_or_create_connection(db, current_user.company_id)
    if conn.provider != "quickbooks_online":
        raise HTTPException(400, "Provider is not QuickBooks Online")

    try:
        from app.services.accounting.qbo_oauth_service import generate_auth_url

        url, state = generate_auth_url(current_user.company_id)
        return {"authorization_url": url, "state": state}
    except ImportError:
        # QBO OAuth service not available — return placeholder
        return {
            "authorization_url": f"/api/v1/accounting/qbo/callback?mock=true&company={current_user.company_id}",
            "state": secrets.token_urlsafe(16),
        }


@router.post("/qbo/connected", response_model=ConnectionStatusResponse)
def qbo_mark_connected(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Mark QBO as connected after OAuth callback succeeds."""
    conn = _get_or_create_connection(db, current_user.company_id)
    conn.status = "connected"
    conn.setup_stage = "configure_sync"
    conn.connected_by = current_user.id
    conn.connected_at = datetime.now(UTC)
    conn.updated_at = datetime.now(UTC)

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if company:
        company.set_setting("accounting_connection_status", "connected")

    db.commit()
    db.refresh(conn)
    return _to_response(conn)


# ---------------------------------------------------------------------------
# Stage 2 — Sage 100 configuration
# ---------------------------------------------------------------------------


@router.post("/sage/configure", response_model=ConnectionStatusResponse)
def sage_configure(
    body: SageConfigRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Configure Sage 100 connection details."""
    conn = _get_or_create_connection(db, current_user.company_id)
    if conn.provider != "sage_100":
        raise HTTPException(400, "Provider is not Sage 100")

    conn.sage_version = body.version
    conn.sage_connection_method = body.connection_method
    conn.sage_api_endpoint = body.api_endpoint
    conn.sage_csv_schedule = body.csv_schedule
    conn.status = "connected"
    conn.setup_stage = "configure_sync"
    conn.connected_by = current_user.id
    conn.connected_at = datetime.now(UTC)
    conn.updated_at = datetime.now(UTC)

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if company:
        company.set_setting("accounting_connection_status", "connected")
        if body.connection_method == "csv":
            company.accounting_provider = "sage_csv"
        else:
            company.accounting_provider = "sage_100"

    db.commit()
    db.refresh(conn)
    return _to_response(conn)


# ---------------------------------------------------------------------------
# Stage 3 — Sync configuration
# ---------------------------------------------------------------------------


@router.post("/sync-config", response_model=ConnectionStatusResponse)
def update_sync_config(
    body: SyncConfigRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update sync configuration toggles."""
    conn = (
        db.query(AccountingConnection)
        .filter(AccountingConnection.company_id == current_user.company_id)
        .first()
    )
    if not conn:
        raise HTTPException(404, "No accounting connection found")

    conn.sync_config = {
        "sync_customers": body.sync_customers,
        "sync_invoices": body.sync_invoices,
        "sync_payments": body.sync_payments,
        "sync_inventory": body.sync_inventory,
    }
    conn.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(conn)
    return _to_response(conn)


@router.post("/account-mappings", response_model=ConnectionStatusResponse)
def update_account_mappings(
    body: AccountMappingsRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update account mappings."""
    conn = (
        db.query(AccountingConnection)
        .filter(AccountingConnection.company_id == current_user.company_id)
        .first()
    )
    if not conn:
        raise HTTPException(404, "No accounting connection found")

    conn.account_mappings = body.mappings
    conn.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(conn)
    return _to_response(conn)


# ---------------------------------------------------------------------------
# Complete setup
# ---------------------------------------------------------------------------


@router.post("/complete", response_model=ConnectionStatusResponse)
def complete_setup(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Mark accounting setup as complete."""
    conn = (
        db.query(AccountingConnection)
        .filter(AccountingConnection.company_id == current_user.company_id)
        .first()
    )
    if not conn:
        raise HTTPException(404, "No accounting connection found")

    conn.setup_stage = "complete"
    conn.updated_at = datetime.now(UTC)

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if company:
        company.set_setting("accounting_connection_status", "connected")

    # Mark checklist item as complete
    check_completion(db, current_user.company_id, "connect_accounting")

    db.commit()
    db.refresh(conn)
    return _to_response(conn)


# ---------------------------------------------------------------------------
# Disconnect
# ---------------------------------------------------------------------------


@router.post("/disconnect", response_model=ConnectionStatusResponse)
def disconnect(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Disconnect accounting provider."""
    conn = (
        db.query(AccountingConnection)
        .filter(AccountingConnection.company_id == current_user.company_id)
        .first()
    )
    if not conn:
        raise HTTPException(404, "No accounting connection found")

    conn.status = "disconnected"
    conn.setup_stage = "select_software"
    # Clear sensitive data
    conn.qbo_access_token_encrypted = None
    conn.qbo_refresh_token_encrypted = None
    conn.sage_api_key_encrypted = None
    conn.updated_at = datetime.now(UTC)

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if company:
        company.set_setting("accounting_connection_status", "disconnected")
        company.accounting_provider = None

    db.commit()
    db.refresh(conn)
    return _to_response(conn)


# ---------------------------------------------------------------------------
# Dismiss skip banner (session-level, stored in company settings)
# ---------------------------------------------------------------------------


@router.post("/dismiss-banner")
def dismiss_banner(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Dismiss the accounting setup reminder banner for this session."""
    # This is actually tracked on the frontend via sessionStorage
    # But we provide an endpoint in case we want server-side tracking later
    return {"dismissed": True}


# ---------------------------------------------------------------------------
# Pre-connection data audit
# ---------------------------------------------------------------------------


@router.get("/pre-audit")
def get_pre_connection_audit(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Pre-connection data audit. Counts customers, invoices, estimates potential duplicates."""
    from app.models.customer import Customer
    from app.models.invoice import Invoice

    customer_count = (
        db.query(Customer)
        .filter(Customer.company_id == current_user.company_id)
        .count()
    )
    invoice_count = (
        db.query(Invoice)
        .filter(Invoice.company_id == current_user.company_id)
        .count()
    )

    # Estimate potential duplicates - customers with common business suffixes
    potential_dupes = (
        db.query(Customer)
        .filter(
            Customer.company_id == current_user.company_id,
            or_(
                Customer.name.ilike("%LLC%"),
                Customer.name.ilike("%Inc%"),
                Customer.name.ilike("%Funeral Home%"),
                Customer.name.ilike("%Chapel%"),
                Customer.name.ilike("%Memorial%"),
            ),
        )
        .count()
    )
    potential_dupes = min(potential_dupes, customer_count // 5) if customer_count > 0 else 0

    return {
        "customer_count": customer_count,
        "potential_duplicates": potential_dupes,
        "invoice_count": invoice_count,
        "sync_frequency": {
            "invoices": "immediately on creation",
            "payments": "every 15 minutes",
            "customers": "immediately on creation",
        },
    }


# ---------------------------------------------------------------------------
# Customer matching — confirm matches
# ---------------------------------------------------------------------------


@router.post("/customer-matches/confirm")
def confirm_customer_matches(
    body: ConfirmCustomerMatchesRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Save customer accounting mappings after matching UI."""
    conn = (
        db.query(AccountingConnection)
        .filter(AccountingConnection.company_id == current_user.company_id)
        .first()
    )
    if not conn:
        raise HTTPException(404, "No accounting connection found")

    created = []
    for match in body.matches:
        mapping = CustomerAccountingMapping(
            id=str(uuid.uuid4()),
            company_id=current_user.company_id,
            customer_id=match.customer_id,
            qbo_customer_id=match.qbo_customer_id,
            qbd_customer_id=match.qbd_customer_id,
            sage_customer_id=match.sage_customer_id,
            match_method=match.match_method,
            match_confidence=match.confidence,
            matched_at=datetime.now(UTC),
        )
        db.add(mapping)
        created.append(mapping.id)

    conn.customer_match_completed = True
    conn.updated_at = datetime.now(UTC)
    db.commit()

    return {
        "matched": len(created),
        "mapping_ids": created,
        "customer_match_completed": True,
    }


# ---------------------------------------------------------------------------
# QBO income accounts (placeholder)
# ---------------------------------------------------------------------------


@router.post("/qbo/income-accounts")
def qbo_income_accounts(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return mock QBO income accounts list for the mapping UI."""
    return {
        "accounts": [
            {"id": "1", "name": "Sales Income", "type": "Income", "number": "4000"},
            {"id": "2", "name": "Product Sales", "type": "Income", "number": "4100"},
            {"id": "3", "name": "Delivery Income", "type": "Income", "number": "4300"},
            {"id": "4", "name": "Other Income", "type": "Income", "number": "4500"},
            {"id": "5", "name": "Service Revenue", "type": "Income", "number": "4600"},
        ]
    }


# ---------------------------------------------------------------------------
# Income account mappings
# ---------------------------------------------------------------------------


@router.post("/income-account-mappings")
def save_income_account_mappings(
    body: IncomeAccountMappingsRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Save income account mappings to accounting_connections JSONB."""
    conn = (
        db.query(AccountingConnection)
        .filter(AccountingConnection.company_id == current_user.company_id)
        .first()
    )
    if not conn:
        raise HTTPException(404, "No accounting connection found")

    conn.income_account_mappings = {
        "default_account": body.default_account,
        "category_mappings": body.category_mappings,
    }
    conn.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(conn)

    return {
        "saved": True,
        "income_account_mappings": conn.income_account_mappings,
    }


# ---------------------------------------------------------------------------
# Sage version detection (placeholder)
# ---------------------------------------------------------------------------


@router.post("/sage/detect-version")
def sage_detect_version(
    body: SageDetectVersionRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Attempt to detect Sage version from a server URL (placeholder)."""
    return {
        "detected": False,
        "message": "Could not reach server",
    }


# ---------------------------------------------------------------------------
# Sage CSV analysis — AI-powered column mapping
# ---------------------------------------------------------------------------

EXPECTED_FIELDS = {
    "invoice_history": [
        "invoice_number",
        "customer_id",
        "customer_name",
        "invoice_date",
        "invoice_amount",
        "balance_due",
        "payment_terms",
    ],
    "customer_list": [
        "customer_id",
        "customer_name",
        "address",
        "city",
        "state",
        "zip",
        "phone",
        "email",
    ],
    "cash_receipts": [
        "receipt_number",
        "customer_id",
        "customer_name",
        "receipt_date",
        "amount",
        "invoice_number",
    ],
}


@router.post("/sage/analyze-csv")
def sage_analyze_csv(
    body: SageAnalyzeCsvRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """AI-powered column mapping for Sage CSV imports."""
    if body.export_type not in EXPECTED_FIELDS:
        raise HTTPException(
            400,
            f"Invalid export_type. Must be one of: {', '.join(EXPECTED_FIELDS.keys())}",
        )

    expected = EXPECTED_FIELDS[body.export_type]

    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(
            503,
            "ANTHROPIC_API_KEY not configured — cannot analyze CSV columns",
        )

    import anthropic

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    # Build sample data display
    sample_display = "Headers: " + " | ".join(body.csv_headers) + "\n"
    for i, row in enumerate(body.sample_rows[:3]):
        sample_display += f"Row {i + 1}: " + " | ".join(str(v) for v in row) + "\n"

    prompt = f"""Analyze this CSV export and map the columns to the expected fields.

CSV Data:
{sample_display}

Expected fields to map to: {json.dumps(expected)}

For each expected field, determine which CSV column (by header name) best matches it.
Return a JSON object with this exact structure:
{{
  "mappings": {{
    "<expected_field>": {{
      "csv_column": "<header_name or null if no match>",
      "confidence": <0.0 to 1.0>
    }}
  }},
  "unmapped_csv_columns": ["<headers that don't map to any expected field>"]
}}

Return ONLY the JSON object, no other text."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    # Parse the response
    response_text = message.content[0].text.strip()
    # Handle potential markdown code blocks
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        # Remove first and last lines (``` markers)
        response_text = "\n".join(lines[1:-1])

    try:
        result = json.loads(response_text)
    except json.JSONDecodeError:
        raise HTTPException(
            500,
            "Failed to parse AI response for column mapping",
        )

    return {
        "export_type": body.export_type,
        "expected_fields": expected,
        "mappings": result.get("mappings", {}),
        "unmapped_csv_columns": result.get("unmapped_csv_columns", []),
    }


# ---------------------------------------------------------------------------
# Sage CSV config — save column mappings for reuse
# ---------------------------------------------------------------------------


@router.post("/sage/save-csv-config")
def sage_save_csv_config(
    body: SageSaveCsvConfigRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Save CSV column mappings for reuse."""
    conn = (
        db.query(AccountingConnection)
        .filter(AccountingConnection.company_id == current_user.company_id)
        .first()
    )
    if not conn:
        raise HTTPException(404, "No accounting connection found")

    # Merge with existing configs (one per export_type)
    existing = conn.csv_column_mappings or {}
    existing[body.export_type] = body.mappings
    conn.csv_column_mappings = existing
    conn.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(conn)

    return {
        "saved": True,
        "export_type": body.export_type,
        "csv_column_mappings": conn.csv_column_mappings,
    }


# ---------------------------------------------------------------------------
# Sync log — paginated
# ---------------------------------------------------------------------------


@router.get("/sync-log")
def get_sync_log(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sync_type_filter: str | None = Query(None),
    status_filter: str | None = Query(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Paginated sync log from sync_logs table."""
    from app.models.sync_log import SyncLog

    query = db.query(SyncLog).filter(
        SyncLog.company_id == current_user.company_id
    )

    if sync_type_filter:
        query = query.filter(SyncLog.sync_type == sync_type_filter)
    if status_filter:
        query = query.filter(SyncLog.status == status_filter)

    total = query.count()
    items = (
        query.order_by(SyncLog.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return {
        "items": [
            {
                "id": item.id,
                "sync_type": item.sync_type,
                "source": item.source,
                "destination": item.destination,
                "status": item.status,
                "records_processed": item.records_processed,
                "records_failed": item.records_failed,
                "error_message": item.error_message,
                "started_at": item.started_at.isoformat() if item.started_at else None,
                "completed_at": item.completed_at.isoformat() if item.completed_at else None,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in items
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


# ---------------------------------------------------------------------------
# Sync health dashboard
# ---------------------------------------------------------------------------


@router.get("/sync-health")
def get_sync_health(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Dashboard data: connection status, this week's sync counts, recent errors."""
    from app.models.sync_log import SyncLog

    conn = (
        db.query(AccountingConnection)
        .filter(AccountingConnection.company_id == current_user.company_id)
        .first()
    )

    week_ago = datetime.now(UTC) - timedelta(days=7)

    # Count sync_logs by status for this week
    week_logs = (
        db.query(SyncLog)
        .filter(
            SyncLog.company_id == current_user.company_id,
            SyncLog.created_at >= week_ago,
        )
    )

    total_syncs = week_logs.count()
    successful_syncs = week_logs.filter(SyncLog.status == "completed").count()
    failed_syncs = week_logs.filter(SyncLog.status == "failed").count()
    in_progress_syncs = week_logs.filter(SyncLog.status == "in_progress").count()

    # Sync counts by type
    type_counts_raw = (
        db.query(SyncLog.sync_type, func.count(SyncLog.id))
        .filter(
            SyncLog.company_id == current_user.company_id,
            SyncLog.created_at >= week_ago,
        )
        .group_by(SyncLog.sync_type)
        .all()
    )
    sync_counts_by_type = {row[0]: row[1] for row in type_counts_raw}

    # Recent errors (last 5)
    recent_errors = (
        db.query(SyncLog)
        .filter(
            SyncLog.company_id == current_user.company_id,
            SyncLog.status == "failed",
        )
        .order_by(SyncLog.created_at.desc())
        .limit(5)
        .all()
    )

    return {
        "connection": {
            "status": conn.status if conn else "not_started",
            "provider": conn.provider if conn else None,
            "last_sync_at": conn.last_sync_at.isoformat() if conn and conn.last_sync_at else None,
            "last_sync_status": conn.last_sync_status if conn else None,
        },
        "this_week": {
            "total": total_syncs,
            "successful": successful_syncs,
            "failed": failed_syncs,
            "in_progress": in_progress_syncs,
            "by_type": sync_counts_by_type,
        },
        "recent_errors": [
            {
                "id": err.id,
                "sync_type": err.sync_type,
                "error_message": err.error_message,
                "created_at": err.created_at.isoformat() if err.created_at else None,
            }
            for err in recent_errors
        ],
    }


# ---------------------------------------------------------------------------
# Test connection
# ---------------------------------------------------------------------------


@router.post("/test-connection")
def test_connection(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Test connection health. Returns latency and status."""
    conn = (
        db.query(AccountingConnection)
        .filter(AccountingConnection.company_id == current_user.company_id)
        .first()
    )
    if not conn:
        return {"healthy": False, "latency_ms": 0, "error": "No accounting connection found"}

    if conn.status not in ("connected", "connecting"):
        return {"healthy": False, "latency_ms": 0, "error": f"Connection status is '{conn.status}'"}

    # For now, test basic DB connectivity as a health check proxy
    start = time.monotonic()
    try:
        db.execute(text("SELECT 1"))
        latency_ms = int((time.monotonic() - start) * 1000)
        return {"healthy": True, "latency_ms": latency_ms, "error": None}
    except Exception as e:
        latency_ms = int((time.monotonic() - start) * 1000)
        return {"healthy": False, "latency_ms": latency_ms, "error": str(e)}


# ---------------------------------------------------------------------------
# Increment connection attempt
# ---------------------------------------------------------------------------


@router.post("/increment-attempt")
def increment_attempt(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Increment connection_attempt_count on accounting_connections."""
    conn = _get_or_create_connection(db, current_user.company_id)
    conn.connection_attempt_count = (conn.connection_attempt_count or 0) + 1
    conn.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(conn)

    return {"connection_attempt_count": conn.connection_attempt_count}
