"""(c) build arc Phase B — Pending-Attention Notification Backfill.

One-time deploy-time backfill that synthesizes Notification rows for
pre-existing awaiting-attention substrate rows whose state transition
predated the (c) producer-site dispatch code. Without this backfill,
the producer-site dispatches added in Phase B fire ONLY for new state
transitions from this commit forward; rows already in pending/awaiting
state at deploy time would otherwise stay silent.

Substrates covered (per audit Q1):
- Task — open tasks with assignee (task_assigned)
- SocialServiceCertificate — status='pending_approval' (ss_cert_pending_approval)
- AgentJob — status='awaiting_approval' (cash_receipts_matching / ar_collections /
    expense_categorization → agent_anomaly_pending; month_end_close →
    agent_job_awaiting_approval; fh_aftercare_7day → funeral_followup_pending)
- UrnCatalogSyncLog — publication_state='pending_review' (catalog_sync_pending_review)
- SafetyProgramGeneration — status='pending_review' (safety_program_pending_review)
- WorkflowReviewItem — decision IS NULL (workflow_review_pending)
- WorkflowEmailClassification — tier IS NULL (email_unclassified_pending)

Idempotency (Option A pattern matching Phase 6 / 8b.5 / 8d.1 canon):
for each candidate row, check whether a Notification already exists
keyed on (company_id, category, source_reference_type, source_reference_id);
if yes, skip; if no, dispatch via the producer-site helper. Safe to
re-run; second run is a no-op for already-backfilled rows.

CLI:
    python -m scripts.seed_pending_attention_backfill --apply
    python -m scripts.seed_pending_attention_backfill --apply --tenant-slug testco
    python -m scripts.seed_pending_attention_backfill            # dry-run

Safety: refuses to run if ENVIRONMENT=production per the broader
seed-script convention. Operator runs explicitly on staging + can
override per-tenant in production via a separate ad-hoc invocation
once they're confident the dispatch behavior is correct.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Any

# Allow `python -m scripts.seed_pending_attention_backfill` from backend/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.agent import AgentJob
from app.models.agent_anomaly import AgentAnomaly  # noqa: F401  (registers model)
from app.models.company import Company
from app.models.notification import Notification
from app.models.safety_program_generation import SafetyProgramGeneration
from app.models.safety_training_topic import SafetyTrainingTopic
from app.models.social_service_certificate import SocialServiceCertificate
from app.models.task import Task
from app.models.urn_catalog_sync_log import UrnCatalogSyncLog
from app.models.workflow_review_item import WorkflowReviewItem
from app.models.email_classification import WorkflowEmailClassification
from app.models.email_primitive import EmailMessage
from app.services import notification_service


logger = logging.getLogger("seed_pending_attention_backfill")
logging.basicConfig(level=logging.INFO, format="%(message)s")


# ── Idempotency check ────────────────────────────────────────────────


def _already_dispatched(
    db: Session,
    *,
    company_id: str,
    category: str,
    source_reference_type: str,
    source_reference_id: str,
) -> bool:
    """Returns True if a Notification already exists for this
    (category, source_reference) pair. Option A idempotent guard."""
    existing = (
        db.query(Notification)
        .filter(
            Notification.company_id == company_id,
            Notification.category == category,
            Notification.source_reference_type == source_reference_type,
            Notification.source_reference_id == source_reference_id,
        )
        .first()
    )
    return existing is not None


# ── Per-substrate backfill helpers ───────────────────────────────────


def _backfill_tasks(db: Session, company_id: str) -> int:
    """Open tasks with an assignee get a task_assigned notification."""
    rows = (
        db.query(Task)
        .filter(
            Task.company_id == company_id,
            Task.status == "open",
            Task.is_active.is_(True),
            Task.assignee_user_id.isnot(None),
        )
        .all()
    )
    fired = 0
    for t in rows:
        if _already_dispatched(
            db,
            company_id=company_id,
            category="task_assigned",
            source_reference_type="task",
            source_reference_id=t.id,
        ):
            continue
        # Skip self-assignment (Lock 3 parity)
        if t.assignee_user_id == t.created_by_user_id:
            continue
        notification_service.create_notification(
            db,
            company_id=company_id,
            user_id=t.assignee_user_id,
            title=f"Task assigned: {t.title}",
            message=t.description or t.title,
            type="info",
            category="task_assigned",
            link=f"/tasks/{t.id}",
            actor_id=t.created_by_user_id,
            source_reference_type="task",
            source_reference_id=t.id,
        )
        fired += 1
    return fired


def _backfill_ss_certs(db: Session, company_id: str) -> int:
    rows = (
        db.query(SocialServiceCertificate)
        .filter(
            SocialServiceCertificate.company_id == company_id,
            SocialServiceCertificate.status == "pending_approval",
        )
        .all()
    )
    fired = 0
    for cert in rows:
        if _already_dispatched(
            db,
            company_id=company_id,
            category="ss_cert_pending_approval",
            source_reference_type="social_service_certificate",
            source_reference_id=cert.id,
        ):
            continue
        notification_service.notify_users_with_permission(
            db,
            company_id=company_id,
            permission_key="invoice.approve",
            title=(
                f"Social service certificate pending approval "
                f"({cert.certificate_number})"
            ),
            message=(
                f"Certificate {cert.certificate_number} is pending approval."
            ),
            type="info",
            category="ss_cert_pending_approval",
            link=f"/social-service-certificates/{cert.id}",
            source_reference_type="social_service_certificate",
            source_reference_id=cert.id,
        )
        fired += 1
    return fired


def _backfill_agent_jobs(db: Session, company_id: str) -> int:
    """AgentJob rows in awaiting_approval (or aftercare COMPLETE-with-anomalies)
    get a category-appropriate notification."""
    fired = 0

    # awaiting_approval cohort
    rows = (
        db.query(AgentJob)
        .filter(
            AgentJob.tenant_id == company_id,
            AgentJob.status == "awaiting_approval",
        )
        .all()
    )
    for job in rows:
        job_type = (job.job_type or "").strip()
        anomaly_count = int(job.anomaly_count or 0)

        if job_type in (
            "cash_receipts_matching",
            "ar_collections",
            "expense_categorization",
        ):
            if job_type == "expense_categorization" and anomaly_count == 0:
                continue
            category = "agent_anomaly_pending"
            title = (
                f"{anomaly_count} {job_type.replace('_', ' ')} "
                f"{'item needs' if anomaly_count == 1 else 'items need'} review"
            )
            permission = "invoice.approve"
        elif job_type == "month_end_close":
            category = "agent_job_awaiting_approval"
            period_label = (
                str(job.period_end) if job.period_end else "current period"
            )
            title = f"Month-end close ready to review ({period_label})"
            permission = "invoice.approve"
        else:
            continue  # unknown job_type — skip

        if _already_dispatched(
            db,
            company_id=company_id,
            category=category,
            source_reference_type="agent_job",
            source_reference_id=job.id,
        ):
            continue

        notification_service.notify_users_with_permission(
            db,
            company_id=company_id,
            permission_key=permission,
            title=title,
            message=f"Agent job {job.id} is awaiting review.",
            type="info",
            category=category,
            link=f"/agents/{job.id}/review",
            actor_user_id=job.triggered_by,
            source_reference_type="agent_job",
            source_reference_id=job.id,
        )
        fired += 1

    # Aftercare cohort — fh_aftercare_7day jobs with unresolved anomalies
    aftercare_jobs = (
        db.query(AgentJob)
        .filter(
            AgentJob.tenant_id == company_id,
            AgentJob.job_type == "fh_aftercare_7day",
            AgentJob.anomaly_count > 0,
        )
        .all()
    )
    for job in aftercare_jobs:
        if _already_dispatched(
            db,
            company_id=company_id,
            category="funeral_followup_pending",
            source_reference_type="agent_job",
            source_reference_id=job.id,
        ):
            continue
        staged = int(job.anomaly_count or 0)
        notification_service.notify_users_with_permission(
            db,
            company_id=company_id,
            permission_key="fh_cases.aftercare",
            title=(
                f"Aftercare follow-up due: {staged} "
                f"{'case' if staged == 1 else 'cases'}"
            ),
            message=(
                f"{staged} aftercare 7-day follow-up "
                f"{'item is' if staged == 1 else 'items are'} ready for review."
            ),
            type="info",
            category="funeral_followup_pending",
            link="/triage/aftercare_triage",
            actor_user_id=job.triggered_by,
            source_reference_type="agent_job",
            source_reference_id=job.id,
        )
        fired += 1

    return fired


def _backfill_catalog_sync(db: Session, company_id: str) -> int:
    rows = (
        db.query(UrnCatalogSyncLog)
        .filter(
            UrnCatalogSyncLog.tenant_id == company_id,
            UrnCatalogSyncLog.publication_state == "pending_review",
        )
        .all()
    )
    fired = 0
    for log in rows:
        if _already_dispatched(
            db,
            company_id=company_id,
            category="catalog_sync_pending_review",
            source_reference_type="urn_catalog_sync_log",
            source_reference_id=log.id,
        ):
            continue
        notification_service.notify_users_with_permission(
            db,
            company_id=company_id,
            permission_key="invoice.approve",
            title=(
                f"Urn catalog sync pending review "
                f"({log.products_updated or 0} product changes)"
            ),
            message=(
                f"A Wilbert urn catalog fetch staged "
                f"{log.products_updated or 0} product changes for review."
            ),
            type="info",
            category="catalog_sync_pending_review",
            link="/triage/catalog_fetch_triage",
            source_reference_type="urn_catalog_sync_log",
            source_reference_id=log.id,
        )
        fired += 1
    return fired


def _backfill_safety_programs(db: Session, company_id: str) -> int:
    rows = (
        db.query(SafetyProgramGeneration)
        .filter(
            SafetyProgramGeneration.tenant_id == company_id,
            SafetyProgramGeneration.status == "pending_review",
        )
        .all()
    )
    fired = 0
    for gen in rows:
        if _already_dispatched(
            db,
            company_id=company_id,
            category="safety_program_pending_review",
            source_reference_type="safety_program_generation",
            source_reference_id=gen.id,
        ):
            continue
        topic = (
            db.query(SafetyTrainingTopic)
            .filter(SafetyTrainingTopic.id == gen.topic_id)
            .first()
        )
        topic_title = topic.title if topic else f"generation {gen.id}"
        notification_service.notify_users_with_permission(
            db,
            company_id=company_id,
            permission_key="safety.trainer.approve",
            title=f"Safety program ready for review: {topic_title}",
            message=(
                "An AI-generated safety program is staged for "
                "safety-trainer review."
            ),
            type="info",
            category="safety_program_pending_review",
            link=f"/safety/programs/{gen.id}",
            source_reference_type="safety_program_generation",
            source_reference_id=gen.id,
        )
        fired += 1
    return fired


def _backfill_workflow_reviews(db: Session, company_id: str) -> int:
    rows = (
        db.query(WorkflowReviewItem)
        .filter(
            WorkflowReviewItem.company_id == company_id,
            WorkflowReviewItem.decision.is_(None),
        )
        .all()
    )
    fired = 0
    for item in rows:
        if _already_dispatched(
            db,
            company_id=company_id,
            category="workflow_review_pending",
            source_reference_type="workflow_review_item",
            source_reference_id=item.id,
        ):
            continue
        notification_service.notify_users_with_permission(
            db,
            company_id=company_id,
            permission_key="admin",
            title=f"Workflow review needed: {item.review_focus_id}",
            message=(
                f"A workflow run is paused on a review step "
                f"({item.review_focus_id}) and is awaiting decision."
            ),
            type="info",
            category="workflow_review_pending",
            link="/triage/workflow_review_triage",
            source_reference_type="workflow_review_item",
            source_reference_id=item.id,
        )
        fired += 1
    return fired


def _backfill_unclassified_emails(db: Session, company_id: str) -> int:
    rows = (
        db.query(WorkflowEmailClassification)
        .filter(
            WorkflowEmailClassification.tenant_id == company_id,
            WorkflowEmailClassification.tier.is_(None),
        )
        .all()
    )
    fired = 0
    for row in rows:
        if _already_dispatched(
            db,
            company_id=company_id,
            category="email_unclassified_pending",
            source_reference_type="workflow_email_classification",
            source_reference_id=row.id,
        ):
            continue
        msg = (
            db.query(EmailMessage)
            .filter(EmailMessage.id == row.email_message_id)
            .first()
        )
        subject = (msg.subject if msg and msg.subject else "(no subject)")[:80]
        notification_service.notify_users_with_permission(
            db,
            company_id=company_id,
            permission_key="admin",
            title=f"Unclassified email needs routing ({subject})",
            message=(
                "An inbound email failed all three classification tiers "
                "and needs manual routing."
            ),
            type="warning",
            category="email_unclassified_pending",
            link="/triage/email_unclassified_triage",
            source_reference_type="workflow_email_classification",
            source_reference_id=row.id,
        )
        fired += 1
    return fired


# ── Driver ───────────────────────────────────────────────────────────


_BACKFILL_HANDLERS: list[tuple[str, Any]] = [
    ("tasks", _backfill_tasks),
    ("ss_certs", _backfill_ss_certs),
    ("agent_jobs", _backfill_agent_jobs),
    ("catalog_sync", _backfill_catalog_sync),
    ("safety_programs", _backfill_safety_programs),
    ("workflow_reviews", _backfill_workflow_reviews),
    ("unclassified_emails", _backfill_unclassified_emails),
]


def backfill_for_tenant(
    db: Session, *, company_id: str, dry_run: bool = False
) -> dict[str, int]:
    """Run all backfill handlers for one tenant. Returns counts per
    substrate. Idempotent — re-running is a no-op for already-dispatched
    rows."""
    counts: dict[str, int] = {}
    for name, handler in _BACKFILL_HANDLERS:
        try:
            count = handler(db, company_id)
        except Exception:
            logger.exception(
                "backfill handler %s failed for company_id=%s — continuing",
                name,
                company_id,
            )
            count = 0
        counts[name] = count
        logger.info(
            "  %-22s %d dispatched (company_id=%s)",
            name,
            count,
            company_id,
        )

    if dry_run:
        db.rollback()
    else:
        db.commit()
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill pending-attention notifications for "
        "pre-existing substrate rows ((c) build arc Phase B)."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually commit notifications. Without --apply, runs in "
        "dry-run mode and rolls back at the end.",
    )
    parser.add_argument(
        "--tenant-slug",
        default=None,
        help="Optionally scope to a single tenant by slug. Default: all "
        "active tenants.",
    )
    args = parser.parse_args()

    if os.getenv("ENVIRONMENT", "").lower() == "production":
        print("SAFETY: Refusing to run in production.")
        return 2

    dry_run = not args.apply
    if dry_run:
        print("DRY-RUN — pass --apply to commit notifications.")

    db: Session = SessionLocal()
    try:
        tenants_q = db.query(Company).filter(Company.is_active.is_(True))
        if args.tenant_slug:
            tenants_q = tenants_q.filter(Company.slug == args.tenant_slug)
        tenants = tenants_q.all()

        if not tenants:
            print(
                f"No active tenants matched "
                f"(slug={args.tenant_slug!r} if scoped)."
            )
            return 0

        grand_total = 0
        for co in tenants:
            print(f"\nTenant {co.slug} ({co.id}):")
            counts = backfill_for_tenant(
                db, company_id=co.id, dry_run=dry_run
            )
            tenant_total = sum(counts.values())
            grand_total += tenant_total
            print(f"  TOTAL for {co.slug}: {tenant_total}")

        verb = "would dispatch" if dry_run else "dispatched"
        print(
            f"\n{verb} {grand_total} notifications across "
            f"{len(tenants)} tenant(s)."
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
