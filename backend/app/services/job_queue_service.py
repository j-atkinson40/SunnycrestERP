"""Redis-backed job queue with database persistence.

Jobs are pushed to Redis for fast pickup by the worker process, and
persisted in the `jobs` table for monitoring, retry, and dead letter tracking.

When Redis is unavailable, jobs fall back to database-only polling.
"""

import json
import logging
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.redis import get_redis
from app.models.job_queue import Job

logger = logging.getLogger(__name__)

REDIS_QUEUE_KEY = "sunnycrest:job_queue"
REDIS_DLQ_KEY = "sunnycrest:dead_letter_queue"


# ---------------------------------------------------------------------------
# Enqueue
# ---------------------------------------------------------------------------


def enqueue(
    db: Session,
    company_id: str,
    job_type: str,
    payload: dict | None = None,
    priority: int = 5,
    max_retries: int = 3,
    delay_seconds: int = 0,
    created_by: str | None = None,
) -> Job:
    """Enqueue a new background job.

    Args:
        db: Database session
        company_id: Tenant ID
        job_type: Job type identifier (e.g., "sync_accounting")
        payload: JSON-serializable dict of job arguments
        priority: 1 (highest) to 10 (lowest)
        max_retries: Max retry attempts before moving to dead letter
        delay_seconds: Delay before job becomes eligible for pickup
        created_by: User ID who triggered the job

    Returns:
        The created Job record.
    """
    scheduled_at = datetime.now(timezone.utc)
    if delay_seconds > 0:
        scheduled_at += timedelta(seconds=delay_seconds)

    job = Job(
        company_id=company_id,
        job_type=job_type,
        payload=json.dumps(payload) if payload else None,
        priority=priority,
        max_retries=max_retries,
        scheduled_at=scheduled_at,
        created_by=created_by,
    )
    db.add(job)
    db.flush()

    # Push to Redis for fast pickup
    r = get_redis()
    if r:
        try:
            # Use sorted set with score = priority * 1e10 + timestamp
            score = priority * 1e10 + scheduled_at.timestamp()
            r.zadd(REDIS_QUEUE_KEY, {job.id: score})
        except Exception as exc:
            logger.warning("Failed to push job %s to Redis: %s", job.id, exc)

    db.commit()
    db.refresh(job)
    logger.info("Job enqueued: %s (type=%s, company=%s)", job.id, job_type, company_id)
    return job


# ---------------------------------------------------------------------------
# Dequeue (used by worker)
# ---------------------------------------------------------------------------


def dequeue(db: Session) -> Job | None:
    """Pick up the next eligible job for processing.

    Tries Redis first for O(1) pickup, falls back to database polling.
    """
    now = datetime.now(timezone.utc)

    r = get_redis()
    if r:
        try:
            # Get lowest-score job (highest priority, earliest scheduled)
            results = r.zrangebyscore(
                REDIS_QUEUE_KEY, "-inf", now.timestamp() * 1e10 + now.timestamp(),
                start=0, num=1,
            )
            if results:
                job_id = results[0]
                r.zrem(REDIS_QUEUE_KEY, job_id)
                job = db.query(Job).filter(Job.id == job_id, Job.status == "pending").first()
                if job:
                    job.status = "running"
                    job.started_at = now
                    db.commit()
                    return job
        except Exception as exc:
            logger.warning("Redis dequeue failed, falling back to DB: %s", exc)

    # Database fallback
    job = (
        db.query(Job)
        .filter(
            Job.status == "pending",
            Job.scheduled_at <= now,
        )
        .order_by(Job.priority.asc(), Job.scheduled_at.asc())
        .with_for_update(skip_locked=True)
        .first()
    )
    if job:
        job.status = "running"
        job.started_at = now
        db.commit()
    return job


# ---------------------------------------------------------------------------
# Complete / Fail / Retry
# ---------------------------------------------------------------------------


def complete_job(db: Session, job: Job, result: dict | None = None) -> Job:
    """Mark a job as completed."""
    job.status = "completed"
    job.completed_at = datetime.now(timezone.utc)
    job.result = json.dumps(result) if result else None
    db.commit()
    logger.info("Job completed: %s (type=%s)", job.id, job.job_type)
    return job


def fail_job(db: Session, job: Job, error: str) -> Job:
    """Mark a job as failed. Schedules retry if attempts remain, otherwise dead-letters."""
    job.error_message = error
    job.retry_count += 1

    if job.retry_count < job.max_retries:
        # Exponential backoff: 30s, 120s, 480s...
        delay = 30 * (2 ** (job.retry_count - 1))
        job.status = "pending"
        job.scheduled_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
        job.started_at = None

        # Re-enqueue to Redis
        r = get_redis()
        if r:
            try:
                score = job.priority * 1e10 + job.scheduled_at.timestamp()
                r.zadd(REDIS_QUEUE_KEY, {job.id: score})
            except Exception:
                pass

        db.commit()
        logger.warning(
            "Job %s failed (attempt %d/%d), retrying in %ds: %s",
            job.id, job.retry_count, job.max_retries, delay, error,
        )
    else:
        # Dead letter
        job.status = "dead"
        job.completed_at = datetime.now(timezone.utc)

        r = get_redis()
        if r:
            try:
                r.lpush(REDIS_DLQ_KEY, job.id)
            except Exception:
                pass

        db.commit()
        logger.error(
            "Job %s dead-lettered after %d attempts: %s",
            job.id, job.retry_count, error,
        )

    return job


def retry_dead_job(db: Session, job_id: str) -> Job | None:
    """Manually retry a dead-lettered job."""
    job = db.query(Job).filter(Job.id == job_id, Job.status == "dead").first()
    if not job:
        return None

    job.status = "pending"
    job.retry_count = 0
    job.error_message = None
    job.scheduled_at = datetime.now(timezone.utc)
    job.started_at = None
    job.completed_at = None

    r = get_redis()
    if r:
        try:
            score = job.priority * 1e10 + job.scheduled_at.timestamp()
            r.zadd(REDIS_QUEUE_KEY, {job.id: score})
            r.lrem(REDIS_DLQ_KEY, 1, job.id)
        except Exception:
            pass

    db.commit()
    logger.info("Dead job %s manually retried", job.id)
    return job


# ---------------------------------------------------------------------------
# Monitoring queries
# ---------------------------------------------------------------------------


def get_queue_stats(db: Session) -> dict:
    """Get queue depth, worker status, and DLQ size."""
    counts = (
        db.query(Job.status, func.count(Job.id))
        .group_by(Job.status)
        .all()
    )
    stats = {status: count for status, count in counts}

    r = get_redis()
    redis_depth = 0
    dlq_size = 0
    if r:
        try:
            redis_depth = r.zcard(REDIS_QUEUE_KEY)
            dlq_size = r.llen(REDIS_DLQ_KEY)
        except Exception:
            pass

    return {
        "pending": stats.get("pending", 0),
        "running": stats.get("running", 0),
        "completed": stats.get("completed", 0),
        "failed": stats.get("failed", 0),
        "dead": stats.get("dead", 0),
        "redis_queue_depth": redis_depth,
        "redis_dlq_size": dlq_size,
        "redis_connected": r is not None,
    }


def get_jobs(
    db: Session,
    company_id: str | None = None,
    status: str | None = None,
    job_type: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    """List jobs with optional filters and pagination."""
    query = db.query(Job)
    if company_id:
        query = query.filter(Job.company_id == company_id)
    if status:
        query = query.filter(Job.status == status)
    if job_type:
        query = query.filter(Job.job_type == job_type)

    total = query.count()
    items = (
        query.order_by(Job.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {"items": items, "total": total, "page": page, "per_page": per_page}


def get_dead_letter_jobs(db: Session, page: int = 1, per_page: int = 20) -> dict:
    """List dead-lettered jobs."""
    return get_jobs(db, status="dead", page=page, per_page=per_page)
