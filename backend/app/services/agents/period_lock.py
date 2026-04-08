"""Period lock service — prevents financial writes to closed accounting periods."""

import logging
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.period_lock import PeriodLock

logger = logging.getLogger(__name__)


class PeriodAlreadyLockedError(Exception):
    """Raised when attempting to lock an already-locked period."""

    def __init__(self, lock: PeriodLock):
        self.lock = lock
        super().__init__(
            f"Period {lock.period_start} – {lock.period_end} is already locked "
            f"(locked at {lock.locked_at})"
        )


class PeriodLockedError(HTTPException):
    """Raised when a financial write targets a locked period."""

    def __init__(self, lock: PeriodLock):
        detail = (
            f"Period {lock.period_start} – {lock.period_end} is locked. "
            f"Locked by: {lock.lock_reason or 'agent job'} on {lock.locked_at:%Y-%m-%d}. "
            f"Contact admin to unlock."
        )
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class PeriodLockService:
    """Service for managing accounting period locks."""

    @staticmethod
    def lock_period(
        db: Session,
        tenant_id: str,
        period_start: date,
        period_end: date,
        agent_job_id: str | None = None,
        locked_by: str | None = None,
        reason: str | None = None,
    ) -> PeriodLock:
        """Create a period lock. Raises PeriodAlreadyLockedError if overlap exists."""
        existing = PeriodLockService._find_overlapping_lock(
            db, tenant_id, period_start, period_end
        )
        if existing:
            raise PeriodAlreadyLockedError(existing)

        import uuid
        lock = PeriodLock(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            period_start=period_start,
            period_end=period_end,
            locked_by=locked_by,
            lock_reason=reason,
            agent_job_id=agent_job_id,
            locked_at=datetime.now(timezone.utc),
        )
        db.add(lock)
        db.commit()
        db.refresh(lock)
        logger.info(
            "Period locked: %s – %s for tenant %s (job=%s)",
            period_start, period_end, tenant_id, agent_job_id,
        )
        return lock

    @staticmethod
    def is_period_locked(
        db: Session,
        tenant_id: str,
        period_start: date,
        period_end: date,
    ) -> bool:
        """Return True if any active lock overlaps with the given date range."""
        return PeriodLockService._find_overlapping_lock(
            db, tenant_id, period_start, period_end
        ) is not None

    @staticmethod
    def check_date_in_locked_period(
        db: Session,
        tenant_id: str,
        target_date: date,
    ) -> PeriodLock | None:
        """Return the active lock if target_date falls within a locked period.

        Called before financial writes to prevent posting to closed periods.
        """
        return (
            db.query(PeriodLock)
            .filter(
                PeriodLock.tenant_id == tenant_id,
                PeriodLock.is_active == True,
                PeriodLock.period_start <= target_date,
                PeriodLock.period_end >= target_date,
            )
            .first()
        )

    @staticmethod
    def unlock_period(
        db: Session,
        lock_id: str,
        unlocked_by: str,
    ) -> PeriodLock:
        """Admin-only unlock. Sets is_active=False."""
        lock = (
            db.query(PeriodLock)
            .filter(PeriodLock.id == lock_id, PeriodLock.is_active == True)
            .first()
        )
        if not lock:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Active period lock not found",
            )

        lock.is_active = False
        lock.unlocked_by = unlocked_by
        lock.unlocked_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(lock)
        logger.info("Period unlocked: %s by user %s", lock_id, unlocked_by)
        return lock

    @staticmethod
    def get_active_locks(db: Session, tenant_id: str) -> list[PeriodLock]:
        """List all active period locks for a tenant."""
        return (
            db.query(PeriodLock)
            .filter(
                PeriodLock.tenant_id == tenant_id,
                PeriodLock.is_active == True,
            )
            .order_by(PeriodLock.period_start.desc())
            .all()
        )

    @staticmethod
    def _find_overlapping_lock(
        db: Session,
        tenant_id: str,
        period_start: date,
        period_end: date,
    ) -> PeriodLock | None:
        """Find an active lock that overlaps with the given date range.

        Overlap logic: NOT (lock_end < start OR lock_start > end)
        """
        return (
            db.query(PeriodLock)
            .filter(
                PeriodLock.tenant_id == tenant_id,
                PeriodLock.is_active == True,
                PeriodLock.period_start <= period_end,
                PeriodLock.period_end >= period_start,
            )
            .first()
        )
