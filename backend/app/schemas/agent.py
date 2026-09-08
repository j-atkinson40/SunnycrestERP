"""Pydantic schemas for accounting agent infrastructure."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AgentJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETE = "complete"
    FAILED = "failed"


#: ⚠️ `agent_jobs.status` HAS TWO SPELLINGS FOR ONE TERMINAL STATE, BOTH LIVE.
#: `AgentJobStatus.COMPLETE` is canonical and is what `BaseAgent` and
#: `approval_gate` write. `"completed"` is written by the older
#: `agent_service` / `proactive_agents` path and is STILL BEING PRODUCED —
#: measured in production 2026-09-08: 3,208 `complete` (from 2026-08-03) and
#: 840 `completed` (from 2026-05-07, most recent 2026-09-07).
#:
#: The two partition cleanly by job_type: `completed` comes only from
#: `collections_sequence`, `ap_upcoming_payments` and `ar_aging_monitor`.
#: So a query scoped to a job_type that uses one spelling is unaffected — which
#: is why most `status == "complete"` filters in this codebase are correct.
#:
#: ⚠️ A QUERY THAT DOES **NOT** SCOPE BY job_type MUST USE THIS TUPLE. Filtering
#: on one spelling there silently drops the other's jobs, and nothing about the
#: result looks wrong. Normalising the data to one spelling is a production
#: write and is held with James; until then this is the honest vocabulary.
COMPLETE_STATUSES: tuple[str, ...] = ("complete", "completed")


class AgentJobType(str, Enum):
    MONTH_END_CLOSE = "month_end_close"
    AR_COLLECTIONS = "ar_collections"
    UNBILLED_ORDERS = "unbilled_orders"
    CASH_RECEIPTS_MATCHING = "cash_receipts_matching"
    EXPENSE_CATEGORIZATION = "expense_categorization"
    ESTIMATED_TAX_PREP = "estimated_tax_prep"
    INVENTORY_RECONCILIATION = "inventory_reconciliation"
    BUDGET_VS_ACTUAL = "budget_vs_actual"
    PREP_1099 = "1099_prep"
    YEAR_END_CLOSE = "year_end_close"
    TAX_PACKAGE = "tax_package"
    ANNUAL_BUDGET = "annual_budget"


class AnomalySeverity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


# ---------------------------------------------------------------------------
# Shared sub-models
# ---------------------------------------------------------------------------


class RunStepLog(BaseModel):
    step_number: int
    step_name: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    message: str
    anomaly_count: int = 0


class AnomalyItem(BaseModel):
    severity: AnomalySeverity
    anomaly_type: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    description: str
    amount: Optional[Decimal] = None


class StepResult(BaseModel):
    """Returned by every BaseAgent.run_step() implementation."""
    message: str
    data: dict = {}
    anomalies: list[AnomalyItem] = []


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class AgentJobCreate(BaseModel):
    job_type: AgentJobType
    period_start: date
    period_end: date
    dry_run: bool = True


class ApprovalAction(BaseModel):
    action: Literal["approve", "reject"]
    rejection_reason: Optional[str] = None
    resolution_notes: Optional[dict] = None


class AnomalyResolve(BaseModel):
    resolution_note: str


class AgentScheduleCreate(BaseModel):
    job_type: AgentJobType
    is_enabled: bool = False
    cron_expression: Optional[str] = None
    run_day_of_month: Optional[int] = None
    run_hour: Optional[int] = None
    timezone: str = "America/New_York"
    auto_approve: bool = False
    notify_emails: list[str] = []


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class AgentJobResponse(BaseModel):
    id: str
    tenant_id: str
    job_type: str
    status: str
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    dry_run: bool = True
    triggered_by: Optional[str] = None
    trigger_type: str = "manual"
    run_log: list = []
    report_payload: Optional[dict] = None
    anomaly_count: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    approval_token: Optional[str] = None
    rejection_reason: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AgentJobListItem(BaseModel):
    """Lighter version for list views — no run_log or report_payload."""
    id: str
    tenant_id: str
    job_type: str
    status: str
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    dry_run: bool = True
    anomaly_count: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AgentAnomalyResponse(BaseModel):
    id: str
    agent_job_id: str
    agent_run_step_id: Optional[str] = None
    severity: str
    anomaly_type: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    description: str
    amount: Optional[Decimal] = None
    resolved: bool = False
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_note: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PeriodLockResponse(BaseModel):
    id: str
    tenant_id: str
    period_start: date
    period_end: date
    locked_at: Optional[datetime] = None
    lock_reason: Optional[str] = None
    locked_by: Optional[str] = None
    is_active: bool = True

    model_config = {"from_attributes": True}


class AgentScheduleResponse(BaseModel):
    id: str
    tenant_id: str
    job_type: str
    is_enabled: bool
    cron_expression: Optional[str] = None
    run_day_of_month: Optional[int] = None
    run_hour: Optional[int] = None
    timezone: str
    auto_approve: bool
    notify_emails: list = []
    last_run_at: Optional[datetime] = None
    last_job_id: Optional[str] = None

    model_config = {"from_attributes": True}
