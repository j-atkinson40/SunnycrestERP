"""Background job handlers.

Each handler is a function that accepts (db, company_id, payload_dict)
and returns a result dict. Handlers are registered in the HANDLER_REGISTRY
and dispatched by the worker process.
"""

import json
import logging

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _sync_accounting(db: Session, company_id: str, payload: dict) -> dict:
    """Run an accounting provider sync."""
    from app.services.accounting import get_provider

    sync_type = payload.get("sync_type", "customers")
    direction = payload.get("direction", "push")
    date_from = payload.get("date_from")
    date_to = payload.get("date_to")

    provider = get_provider(db, company_id)

    from datetime import datetime

    df = datetime.fromisoformat(date_from) if date_from else None
    dt = datetime.fromisoformat(date_to) if date_to else None

    sync_map = {
        "customers": lambda: provider.sync_customers(direction),
        "invoices": lambda: provider.sync_invoices(df, dt),
        "payments": lambda: provider.sync_payments(df, dt),
        "bills": lambda: provider.sync_bills(df, dt),
        "bill_payments": lambda: provider.sync_bill_payments(df, dt),
        "inventory": lambda: provider.sync_inventory_transactions(df, dt),
    }

    fn = sync_map.get(sync_type)
    if not fn:
        return {"success": False, "error": f"Unknown sync type: {sync_type}"}

    result = fn()
    return {
        "success": result.success,
        "records_synced": result.records_synced,
        "records_failed": result.records_failed,
        "error_message": result.error_message,
    }


def _export_sage(db: Session, company_id: str, payload: dict) -> dict:
    """Generate a Sage CSV export."""
    from datetime import datetime

    from app.services.sage_export_service import generate_sage_csv

    date_from = datetime.fromisoformat(payload["date_from"])
    date_to = datetime.fromisoformat(payload["date_to"])
    actor_id = payload.get("actor_id")

    csv_string, count, sync_log_id = generate_sage_csv(
        db, company_id, date_from, date_to, actor_id
    )
    return {
        "records_exported": count,
        "sync_log_id": sync_log_id,
        "csv_length": len(csv_string),
    }


def _send_notification(db: Session, company_id: str, payload: dict) -> dict:
    """Create an in-app notification."""
    from app.services.notification_service import create_notification

    notification = create_notification(
        db,
        company_id=company_id,
        user_id=payload["user_id"],
        title=payload["title"],
        message=payload.get("message", ""),
        notification_type=payload.get("type", "info"),
    )
    return {"notification_id": notification.id}


# ---------------------------------------------------------------------------
# Handler registry — maps job_type strings to handler functions
# ---------------------------------------------------------------------------

HANDLER_REGISTRY: dict[str, callable] = {
    "sync_accounting": _sync_accounting,
    "export_sage": _export_sage,
    "send_notification": _send_notification,
}


def execute_job(db: Session, company_id: str, job_type: str, payload_json: str | None) -> dict:
    """Execute a job by type. Called by the worker process."""
    handler = HANDLER_REGISTRY.get(job_type)
    if not handler:
        raise ValueError(f"Unknown job type: {job_type}")

    payload = json.loads(payload_json) if payload_json else {}
    return handler(db, company_id, payload)
