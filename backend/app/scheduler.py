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


def job_profile_update():
    """Cemetery enrichment pass for funeral home behavioral profiles."""
    from app.services.behavioral_analytics_service import enrich_funeral_home_profiles
    _run_per_tenant("PROFILE_UPDATE", enrich_funeral_home_profiles)


def job_draft_invoice_generator():
    from app.services.draft_invoice_service import generate_draft_invoices
    _run_per_tenant("DRAFT_INVOICE_GENERATOR", generate_draft_invoices)


def job_ar_balance_reconciliation():
    """Daily: reconcile stored customer AR balances against actual invoice totals."""
    from app.services.proactive_agents import run_ar_balance_reconciliation
    _run_per_tenant("AR_BALANCE_RECONCILIATION", run_ar_balance_reconciliation)


def job_discount_expiry_monitor():
    """Daily at 8am: alert on early payment discounts expiring within 3 days."""
    from app.services.proactive_agents import run_discount_expiry_monitor
    _run_per_tenant("DISCOUNT_EXPIRY_MONITOR", run_discount_expiry_monitor)


def job_payment_pattern_enrichment():
    """Weekly: enrich customer behavioral profiles with payment patterns."""
    from app.services.proactive_agents import enrich_payment_patterns
    _run_per_tenant("PAYMENT_PATTERN_ENRICHMENT", enrich_payment_patterns)


def job_network_readiness():
    """Weekly: find new cemetery tenants and create connection suggestions for nearby manufacturers."""
    from app.services.network_intelligence_service import suggest_cemetery_connections_for_new_tenants
    _run_global("NETWORK_READINESS", suggest_cemetery_connections_for_new_tenants)


def job_onboarding_pattern():
    """Run onboarding timeline prediction for all tenants."""
    from app.models.company import Company
    from app.services.network_intelligence_service import predict_onboarding_timeline

    tenant_ids = _get_active_tenant_ids()
    logger.info(f"[ONBOARDING_PATTERN] Starting for {len(tenant_ids)} tenants")
    success = 0
    errors = 0
    for tid in tenant_ids:
        db = SessionLocal()
        try:
            company = db.query(Company).filter(Company.id == tid).first()
            tenant_type = getattr(company, "preset", "manufacturing") if company else "manufacturing"
            predict_onboarding_timeline(db, tid, tenant_type)
            success += 1
        except Exception as e:
            errors += 1
            logger.error(f"[ONBOARDING_PATTERN] Error for tenant {tid}: {e}", exc_info=True)
        finally:
            db.close()
    logger.info(f"[ONBOARDING_PATTERN] Complete: {success} ok, {errors} errors")


# ---------------------------------------------------------------------------
# Job registry — maps names to wrapper functions (for manual trigger)
# ---------------------------------------------------------------------------

JOB_REGISTRY: dict[str, callable] = {
    "draft_invoice_generator": job_draft_invoice_generator,
    "network_readiness": job_network_readiness,
    "ar_aging_monitor": job_ar_aging_monitor,
    "ar_balance_reconciliation": job_ar_balance_reconciliation,
    "discount_expiry_monitor": job_discount_expiry_monitor,
    "payment_pattern_enrichment": job_payment_pattern_enrichment,
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
    "onboarding_pattern": job_onboarding_pattern,
    "profile_update": job_profile_update,
}


# ---------------------------------------------------------------------------
# Schedule registration
# ---------------------------------------------------------------------------


def register_all_jobs():
    """Register all jobs with their cron schedules."""

    # DAILY at 6pm ET — end-of-day draft invoice generation
    scheduler.add_job(
        job_draft_invoice_generator,
        CronTrigger(hour=18, minute=0),
        id="draft_invoice_generator",
        name="draft_invoice_generator",
        replace_existing=True,
        misfire_grace_time=3600,
    )

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

    # DAILY at 2am ET — AR balance reconciliation (drift detection)
    scheduler.add_job(
        job_ar_balance_reconciliation,
        CronTrigger(hour=2, minute=0),
        id="ar_balance_reconciliation",
        name="ar_balance_reconciliation",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # DAILY at 8am ET — discount expiry alerts
    scheduler.add_job(
        job_discount_expiry_monitor,
        CronTrigger(hour=8, minute=0),
        id="discount_expiry_monitor",
        name="discount_expiry_monitor",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # WEEKLY Saturday at 2am ET — payment pattern enrichment
    scheduler.add_job(
        job_payment_pattern_enrichment,
        CronTrigger(day_of_week="sat", hour=2, minute=0),
        id="payment_pattern_enrichment",
        name="payment_pattern_enrichment",
        replace_existing=True,
        misfire_grace_time=7200,
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

    # DAILY at 7:00am — vault reorder suggestions (delivery-aware)
    scheduler.add_job(
        job_reorder_suggestion,
        CronTrigger(hour=7, minute=0),
        id="reorder_suggestion",
        name="reorder_suggestion",
        replace_existing=True,
        misfire_grace_time=3600,
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

    # MONTHLY 1st at 4am — onboarding pattern analysis
    scheduler.add_job(
        job_onboarding_pattern,
        CronTrigger(day=1, hour=4, minute=13),
        id="onboarding_pattern",
        name="onboarding_pattern",
        replace_existing=True,
        misfire_grace_time=86400,
    )

    # WEEKLY Sunday at 3am — funeral home behavioral profile enrichment
    scheduler.add_job(
        job_profile_update,
        CronTrigger(day_of_week="sun", hour=3, minute=17),
        id="profile_update",
        name="profile_update",
        replace_existing=True,
        misfire_grace_time=7200,
    )

    # WEEKLY Sunday at 3:30am — cemetery network readiness (new tenant connection suggestions)
    scheduler.add_job(
        job_network_readiness,
        CronTrigger(day_of_week="sun", hour=3, minute=30),
        id="network_readiness",
        name="network_readiness",
        replace_existing=True,
        misfire_grace_time=7200,
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
