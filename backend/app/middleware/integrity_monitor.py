"""SQLAlchemy integrity error listener — logs data_integrity incidents.

Hooks into the engine's ``handle_error`` event so that every
``IntegrityError`` (FK violation, unique constraint, etc.) is
automatically captured as a platform incident.

Uses a **separate** DB session to avoid contaminating the failed
transaction, and never blocks the original exception.
"""

import logging

from sqlalchemy import event
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


def register_integrity_listener(engine) -> None:
    """Attach a handle_error listener that logs IntegrityError incidents."""

    @event.listens_for(engine, "handle_error")
    def _on_db_error(exception_context):
        if not isinstance(exception_context.original_exception, IntegrityError):
            return  # only interested in integrity errors

        try:
            from app.database import SessionLocal
            from app.services.platform.platform_health_service import log_incident

            with SessionLocal() as monitor_db:
                log_incident(
                    db=monitor_db,
                    category="data_integrity",
                    severity="high",
                    source="healthcheck",
                    error_message=str(
                        exception_context.original_exception
                    )[:500],
                    context={
                        "statement": str(
                            exception_context.statement
                        )[:200]
                        if exception_context.statement
                        else None,
                    },
                )
                monitor_db.commit()
        except Exception:
            # Never block on monitor failure — the original exception
            # must propagate unimpeded.
            logger.debug(
                "integrity_monitor: failed to log incident", exc_info=True
            )
