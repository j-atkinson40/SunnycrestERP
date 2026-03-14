"""Background job worker process.

Run with: python worker.py

Continuously polls for pending jobs and executes them.
Uses Redis for fast notification, falls back to DB polling.
"""

import logging
import signal
import sys
import time
import traceback

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("worker")

# Ensure app modules are importable
sys.path.insert(0, ".")

from app.database import SessionLocal
from app.jobs import execute_job
from app.services import job_queue_service

# Graceful shutdown
_shutdown = False


def _signal_handler(sig, frame):
    global _shutdown
    logger.info("Shutdown signal received, finishing current job...")
    _shutdown = True


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


def run_worker(poll_interval: float = 2.0):
    """Main worker loop."""
    logger.info("Worker started (poll_interval=%.1fs)", poll_interval)

    while not _shutdown:
        db = SessionLocal()
        try:
            job = job_queue_service.dequeue(db)
            if job is None:
                db.close()
                time.sleep(poll_interval)
                continue

            logger.info(
                "Processing job %s (type=%s, attempt=%d/%d)",
                job.id, job.job_type, job.retry_count + 1, job.max_retries,
            )

            try:
                result = execute_job(db, job.company_id, job.job_type, job.payload)
                job_queue_service.complete_job(db, job, result)
            except Exception as exc:
                error_msg = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
                logger.error("Job %s failed: %s", job.id, exc)
                job_queue_service.fail_job(db, job, error_msg)

        except Exception as exc:
            logger.error("Worker error: %s", exc)
            time.sleep(poll_interval)
        finally:
            db.close()

    logger.info("Worker shutdown complete")


if __name__ == "__main__":
    run_worker()
