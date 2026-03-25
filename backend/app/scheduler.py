"""APScheduler-based cron scheduling for all agent jobs.

Starts with the FastAPI app, runs jobs on their defined schedules,
catches errors without crashing, and logs execution details.
"""

import logging
from datetime import date, datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import SessionLocal

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="America/New_York")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_active_tenant_ids() -> list[str]:
    """Get all active tenant IDs."""
    db = SessionLocal()
    try:
        from app.models.company import Company
        tenants = db.query(Company.id).filter(Company.is_active.is_(True)).all()
        return [t.id for t in tenants]
    except Exception as e:
        logger.error(f"Failed to get active tenants: {e}")
        return []
    finally:
        db.close()


def _run_per_tenant(job_name: str, func, *extra_args):
    """Run a function for each active tenant with its own DB session."""
    tenant_ids = _get_active_tenant_ids()
    logger.info(f"[{job_name}] Starting for {len(tenant_ids)} tenants")
    success = 0
    errors = 0
    for tid in tenant_ids:
        db = SessionLocal()
        try:
            func(db, tid, *extra_args)
            success += 1
        except Exception as e:
            errors += 1
            logger.error(f"[{job_name}] Error for tenant {tid}: {e}", exc_info=True)
        finally:
            db.close()
    logger.info(f"[{job_name}] Complete: {success} ok, {errors} errors")


def _run_global(job_name: str, func):
    """Run a function once with its own DB session (not per-tenant)."""
    logger.info(f"[{job_name}] Starting")
    db = SessionLocal()
    try:
        result = func(db)
        logger.info(f"[{job_name}] Complete: {result}")
    except Exception as e:
        logger.error(f"[{job_name}] Error: {e}", exc_info=True)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Job wrappers — each catches its own errors
# ---------------------------------------------------------------------------


def job_ar_aging_monitor():
    from app.services.agent_service import run_ar_aging_monitor
    _run_per_tenant("AR_AGING_MONITOR", run_ar_aging_monitor)


def job_collections_sequence():
    from app.services.agent_service import run_collections_sequence
    _run_per_tenant("COLLECTIONS_SEQUENCE", run_collections_sequence)


def job_ap_upcoming_payments():
    from app.services.agent_service import run_ap_upcoming_payments
    _run_per_tenant("AP_UPCOMING_PAYMENTS", run_ap_upcoming_payments)


def job_reorder_suggestion():
    from app.services.proactive_agents import run_reorder_suggestion_job
    _run_per_tenant("REORDER_SUGGESTION", run_reorder_suggestion_job)


def job_receiving_discrepancy_monitor():
    from app.services.proactive_agents import run_receiving_discrepancy_monitor
    _run_per_tenant("RECEIVING_DISCREPANCY", run_receiving_discrepancy_monitor)


def job_balance_reduction_advisor():
    from app.services.proactive_agents import run_balance_reduction_advisor
    _run_per_tenant("BALANCE_REDUCTION", run_balance_reduction_advisor)


def job_missing_entry_detector():
    from app.services.proactive_agents import run_missing_entry_detector
    _run_per_tenant("MISSING_ENTRY_DETECTOR", run_missing_entry_detector)


def job_tax_filing_prep():
    from app.services.proactive_agents import run_tax_filing_prep
    _run_per_tenant("TAX_FILING_PREP", run_tax_filing_prep)


def job_uncleared_check_monitor():
    from app.services.proactive_agents import run_uncleared_check_monitor
    _run_per_tenant("UNCLEARED_CHECK_MONITOR", run_uncleared_check_monitor)


def job_financial_health_score():
    from app.services.financial_health_service import run_daily_score
    today = date.today()
    _run_per_tenant("FINANCIAL_HEALTH_SCORE", run_daily_score, today)


def job_cross_system_synthesis():
    from app.services.cross_system_insight_service import detect_all_insights
    _run_per_tenant("CROSS_SYSTEM_SYNTHESIS", detect_all_insights)


def job_network_snapshot():
    from app.services.network_intelligence_service import build_platform_health_snapshot
    _run_global("NETWORK_SNAPSHOT", build_platform_health_snapshot)


# ---------------------------------------------------------------------------
# Job registry — maps names to wrapper functions (for manual trigger)
# ---------------------------------------------------------------------------

JOB_REGISTRY: dict[str, callable] = {
    "ar_aging_monitor": job_ar_aging_monitor,
    "collections_sequence": job_collections_sequence,
    "ap_upcoming_payments": job_ap_upcoming_payments,
    "reorder_suggestion": job_reorder_suggestion,
    "receiving_discrepancy_monitor": job_receiving_discrepancy_monitor,
    "balance_reduction_advisor": job_balance_reduction_advisor,
    "missing_entry_detector": job_missing_entry_detector,
    "tax_filing_prep": job_tax_filing_prep,
    "uncleared_check_monitor": job_uncleared_check_monitor,
    "financial_health_score": job_financial_health_score,
    "cross_system_synthesis": job_cross_system_synthesis,
    "network_snapshot": job_network_snapshot,
}


# ---------------------------------------------------------------------------
# Schedule registration
# ---------------------------------------------------------------------------


def register_all_jobs():
    """Register all jobs with their cron schedules."""

    # NIGHTLY at 11pm ET — core agent monitoring
    nightly_jobs = [
        ("ar_aging_monitor", job_ar_aging_monitor, "0"),
        ("collections_sequence", job_collections_sequence, "5"),
        ("ap_upcoming_payments", job_ap_upcoming_payments, "10"),
        ("receiving_discrepancy_monitor", job_receiving_discrepancy_monitor, "15"),
        ("balance_reduction_advisor", job_balance_reduction_advisor, "20"),
        ("missing_entry_detector", job_missing_entry_detector, "25"),
        ("tax_filing_prep", job_tax_filing_prep, "30"),
        ("uncleared_check_monitor", job_uncleared_check_monitor, "35"),
    ]
    for name, func, minute_offset in nightly_jobs:
        scheduler.add_job(
            func,
            CronTrigger(hour=23, minute=int(minute_offset)),
            id=name,
            name=name,
            replace_existing=True,
            misfire_grace_time=3600,
        )

    # DAILY at 5am — financial health score
    scheduler.add_job(
        job_financial_health_score,
        CronTrigger(hour=5, minute=3),
        id="financial_health_score",
        name="financial_health_score",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # DAILY at 6am — cross-system synthesis
    scheduler.add_job(
        job_cross_system_synthesis,
        CronTrigger(hour=6, minute=7),
        id="cross_system_synthesis",
        name="cross_system_synthesis",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # WEEKLY Monday at 6am — reorder suggestions
    scheduler.add_job(
        job_reorder_suggestion,
        CronTrigger(day_of_week="mon", hour=6, minute=12),
        id="reorder_suggestion",
        name="reorder_suggestion",
        replace_existing=True,
        misfire_grace_time=7200,
    )

    # MONTHLY 1st at 2am — network snapshot
    scheduler.add_job(
        job_network_snapshot,
        CronTrigger(day=1, hour=2, minute=17),
        id="network_snapshot",
        name="network_snapshot",
        replace_existing=True,
        misfire_grace_time=86400,
    )

    logger.info(f"Registered {len(scheduler.get_jobs())} scheduled jobs")


def start_scheduler():
    """Start the scheduler with all jobs registered."""
    register_all_jobs()
    scheduler.start()
    logger.info("APScheduler started")


def shutdown_scheduler():
    """Gracefully shut down the scheduler."""
    scheduler.shutdown(wait=False)
    logger.info("APScheduler shut down")
