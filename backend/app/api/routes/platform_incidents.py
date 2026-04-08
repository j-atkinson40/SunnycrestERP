"""Platform incidents API — internal-only endpoints for the self-repair system.

Authenticated via X-Internal-Key header (not JWT). Called by:
- Playwright incident reporter (test failures)
- Nightly health jobs
- Future automated monitoring systems
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.config import settings
from app.constants.platform_incidents import (
    INCIDENT_CATEGORIES,
    INCIDENT_SEVERITIES,
    INCIDENT_SOURCES,
)
from app.database import SessionLocal
from app.models.platform_incident import PlatformIncident
from app.services.platform.platform_health_service import log_incident

router = APIRouter()


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------


def require_internal_key(x_internal_key: str = Header(None)):
    """Validate the X-Internal-Key header against env INTERNAL_API_KEY."""
    if not settings.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Internal API key not configured on this server",
        )
    if not x_internal_key or x_internal_key != settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid internal API key")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class IncidentCreate(BaseModel):
    category: str
    severity: str = "medium"
    source: str = "manual"
    tenant_id: Optional[str] = None
    error_message: str
    stack_trace: Optional[str] = None
    context: Optional[dict] = None

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if v not in INCIDENT_CATEGORIES:
            raise ValueError(
                f"Invalid category '{v}'. Must be one of: "
                f"{list(INCIDENT_CATEGORIES.keys())}"
            )
        return v

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        if v not in INCIDENT_SEVERITIES:
            raise ValueError(
                f"Invalid severity '{v}'. Must be one of: {INCIDENT_SEVERITIES}"
            )
        return v

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        if v not in INCIDENT_SOURCES:
            raise ValueError(
                f"Invalid source '{v}'. Must be one of: {INCIDENT_SOURCES}"
            )
        return v


class IncidentResponse(BaseModel):
    id: str
    category: str
    severity: str
    resolution_tier: Optional[str]
    resolution_status: str
    was_repeat: bool
    fingerprint: Optional[str]
    tenant_id: Optional[str]
    source: Optional[str]
    error_message: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/incidents", status_code=201, response_model=IncidentResponse)
def create_incident(
    body: IncidentCreate,
    _auth: None = Depends(require_internal_key),
    db: Session = Depends(get_db),
):
    """Log a new platform incident. Called by Playwright reporter and automated systems."""
    incident = log_incident(
        db=db,
        category=body.category,
        error_message=body.error_message,
        tenant_id=body.tenant_id,
        severity=body.severity,
        source=body.source,
        stack_trace=body.stack_trace,
        context=body.context,
    )
    db.commit()
    return incident


@router.get("/incidents", response_model=list[IncidentResponse])
def list_incidents(
    tenant_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    _auth: None = Depends(require_internal_key),
    db: Session = Depends(get_db),
):
    """List platform incidents with optional filters."""
    q = db.query(PlatformIncident)

    if tenant_id:
        q = q.filter(PlatformIncident.tenant_id == tenant_id)
    if status:
        q = q.filter(PlatformIncident.resolution_status == status)
    if category:
        q = q.filter(PlatformIncident.category == category)

    return (
        q.order_by(PlatformIncident.created_at.desc())
        .limit(limit)
        .all()
    )
