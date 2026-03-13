from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.sync_log import SyncLog


def create_sync_log(
    db: Session,
    company_id: str,
    sync_type: str,
    source: str,
    destination: str,
) -> SyncLog:
    """Create a new sync log entry with status 'in_progress'."""
    log = SyncLog(
        company_id=company_id,
        sync_type=sync_type,
        source=source,
        destination=destination,
        status="in_progress",
        started_at=datetime.now(timezone.utc),
    )
    db.add(log)
    db.flush()
    return log


def complete_sync_log(
    db: Session,
    sync_log: SyncLog,
    records_processed: int,
    records_failed: int,
    error_message: str | None = None,
) -> SyncLog:
    """Mark a sync log as completed or failed."""
    sync_log.records_processed = records_processed
    sync_log.records_failed = records_failed
    sync_log.error_message = error_message
    sync_log.status = "failed" if error_message and records_processed == 0 else "completed"
    sync_log.completed_at = datetime.now(timezone.utc)
    return sync_log


def get_sync_logs(
    db: Session,
    company_id: str,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    """List sync logs for a company with pagination."""
    query = db.query(SyncLog).filter(SyncLog.company_id == company_id)
    total = query.count()
    logs = (
        query.order_by(SyncLog.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {"items": logs, "total": total, "page": page, "per_page": per_page}


def get_sync_log(db: Session, sync_log_id: str, company_id: str) -> SyncLog | None:
    """Get a single sync log by ID."""
    return (
        db.query(SyncLog)
        .filter(SyncLog.id == sync_log_id, SyncLog.company_id == company_id)
        .first()
    )
