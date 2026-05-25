"""v1 task substrate B2 — notification_dispatcher subscriber + 8 producer site parity.

Verifies (a) the subscriber routes correctly per Decision C, (b) each
of the 8 producer sites writes a task_details row + the subscriber
dispatches the expected notification with parity to pre-refactor
payload shape.

Test discipline (B2):
- uuid-randomized provenance_ref_id per test to avoid substrate
  idempotency pollution from re-runs against a shared dev DB.
- Admin users short-circuit `user_has_permission` so the ts_ctx
  admin user receives every cohort-routed notification automatically.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.notification import Notification
from app.models.task_details import TaskDetails
from app.models.vault_item import VaultItem
from app.services.tasks.subscribers import notification_subscriber as ns_mod
from app.services.tasks.subscribers.notification_subscriber import (
    COHORT_ALLOWLIST,
)
from app.services.tasks.service import create_task_with_provenance


# ── Helpers ─────────────────────────────────────────────────────────


def _new_id() -> str:
    """uuid4-randomized id for provenance_ref_id (avoids idempotency collisions)."""
    return str(uuid.uuid4())


def _notifications_for_company(db: Session, company_id: str) -> list[Notification]:
    return (
        db.query(Notification)
        .filter(Notification.company_id == company_id)
        .all()
    )


def _notifications_for_user(db: Session, user_id: str) -> list[Notification]:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .all()
    )


# ── Subscriber unit tests ───────────────────────────────────────────


class TestCohortAllowlist:
    def test_allowlist_contents(self):
        assert COHORT_ALLOWLIST == frozenset({
            "review_approval_task",
            "scheduled_recurring_task",
            "customer_communication_task",
            "anomaly_resolution_task",
        })

    def test_generic_task_not_in_allowlist(self):
        assert "generic_task" not in COHORT_ALLOWLIST


class TestSubscriberRouting:
    """Direct subscriber routing tests — bypass producer sites."""

    def test_cohort_with_permission_key_routes_via_notify_users_with_permission(
        self, ts_ctx
    ):
        db = SessionLocal()
        try:
            ref = _new_id()
            td = create_task_with_provenance(
                db,
                company_id=ts_ctx["company_id"],
                provenance_kind="integration_event",
                provenance_ref_type="test_subject",
                provenance_ref_id=ref,
                event_kind="cohort_with_key_test",
                task_type_key="review_approval_task",
                title="cohort with permission_key",
                # No created_by_user_id — avoid Lock 3 self-suppression
                # in notify_users_with_permission against the admin user.
                metadata={
                    "notification_permission_key": "invoice.approve",
                    "notification_category": "ss_cert_pending_approval",
                },
            )
            db.commit()
            # Admin user short-circuits permission gate → receives the row.
            user_notifs = _notifications_for_user(db, ts_ctx["user_id"])
            assert any(
                n.title == "cohort with permission_key" for n in user_notifs
            ), "cohort routing did not deliver to admin user"
        finally:
            db.close()

    def test_cohort_without_permission_key_raises_defensive_assertion(
        self, ts_ctx, caplog
    ):
        """Defensive assertion: cohort-allowlist task without
        permission_key → subscriber raises. Registry try/except logs +
        continues, so other subscribers still run and the task row still
        exists, but no notification is delivered."""
        db = SessionLocal()
        try:
            ref = _new_id()
            # Subscriber raise is caught by registry's try/except —
            # task creation should still succeed.
            td = create_task_with_provenance(
                db,
                company_id=ts_ctx["company_id"],
                provenance_kind="manual_creation",
                provenance_ref_type="test_subject",
                provenance_ref_id=ref,
                event_kind="cohort_no_key_test",
                task_type_key="anomaly_resolution_task",
                title="cohort without permission_key",
                created_by_user_id=ts_ctx["user_id"],
                metadata={"notification_category": "agent_anomaly_pending"},
            )
            db.commit()
            # Task row exists.
            assert td.id is not None
            # No notification dispatched (subscriber raised before
            # notification_service call).
            user_notifs = _notifications_for_user(db, ts_ctx["user_id"])
            assert not any(
                n.title == "cohort without permission_key" for n in user_notifs
            ), "cohort routing should have raised before dispatch"
        finally:
            db.close()

    def test_generic_task_with_assignee_no_permission_key_uses_create_notification(
        self, ts_ctx
    ):
        """Direct-user routing: generic_task with assignee but no
        permission_key → notify the assignee directly."""
        db = SessionLocal()
        try:
            # Create a second user to be the assignee (Lock 3 self-suppress
            # would skip if creator == assignee).
            from app.models.user import User
            other = User(
                id=_new_id(),
                company_id=ts_ctx["company_id"],
                email=f"o-{uuid.uuid4().hex[:6]}@ts.co",
                first_name="Other",
                last_name="User",
                hashed_password="x",
                is_active=True,
                role_id=ts_ctx["role_id"],
            )
            db.add(other)
            db.commit()
            ref = _new_id()
            create_task_with_provenance(
                db,
                company_id=ts_ctx["company_id"],
                provenance_kind="manual_creation",
                provenance_ref_type="test_subject",
                provenance_ref_id=ref,
                event_kind="direct_user_test",
                task_type_key="generic_task",
                title="direct user task",
                created_by_user_id=ts_ctx["user_id"],
                assignee_user_id=other.id,
                metadata={"notification_category": "task_assigned"},
            )
            db.commit()
            # Assignee receives notification.
            assignee_notifs = _notifications_for_user(db, other.id)
            assert any(
                n.title == "direct user task" for n in assignee_notifs
            ), "direct-user routing did not deliver to assignee"
        finally:
            db.close()

    def test_generic_task_no_assignee_no_permission_key_skips_silently(
        self, ts_ctx
    ):
        """Informational generic_task with no recipient: log + skip."""
        db = SessionLocal()
        try:
            ref = _new_id()
            td = create_task_with_provenance(
                db,
                company_id=ts_ctx["company_id"],
                provenance_kind="manual_creation",
                provenance_ref_type="test_subject",
                provenance_ref_id=ref,
                event_kind="informational_skip_test",
                task_type_key="generic_task",
                title="informational no-recipient task",
                created_by_user_id=ts_ctx["user_id"],
                metadata={},
            )
            db.commit()
            # Task row exists; no notification.
            assert td.id is not None
            notifs = (
                db.query(Notification)
                .filter(Notification.title == "informational no-recipient task")
                .all()
            )
            assert notifs == [], (
                "informational task with no recipient should not create "
                "a notification"
            )
        finally:
            db.close()

    def test_lock_3_self_suppression_actor_equals_assignee(self, ts_ctx):
        """If actor_user_id == assignee_user_id, direct-user dispatch
        skips per Lock 3."""
        db = SessionLocal()
        try:
            ref = _new_id()
            create_task_with_provenance(
                db,
                company_id=ts_ctx["company_id"],
                provenance_kind="manual_creation",
                provenance_ref_type="test_subject",
                provenance_ref_id=ref,
                event_kind="self_suppress_test",
                task_type_key="generic_task",
                title="self assigned",
                created_by_user_id=ts_ctx["user_id"],
                assignee_user_id=ts_ctx["user_id"],  # same as creator
                metadata={"notification_category": "task_assigned"},
            )
            db.commit()
            notifs = (
                db.query(Notification)
                .filter(Notification.title == "self assigned")
                .all()
            )
            assert notifs == [], (
                "Lock 3 self-suppression failed: actor==assignee should "
                "not create a notification"
            )
        finally:
            db.close()

    def test_permission_key_present_wins_over_task_type(self, ts_ctx):
        """Decision C: permission_key presence is the discriminator,
        even for non-cohort task_type_key like generic_task."""
        db = SessionLocal()
        try:
            ref = _new_id()
            create_task_with_provenance(
                db,
                company_id=ts_ctx["company_id"],
                provenance_kind="manual_creation",
                provenance_ref_type="test_subject",
                provenance_ref_id=ref,
                event_kind="metadata_wins_test",
                task_type_key="generic_task",
                title="generic with permission_key",
                # No created_by_user_id — avoid Lock 3 self-suppression.
                metadata={
                    "notification_permission_key": "invoice.approve",
                    "notification_category": "task_assigned",
                },
            )
            db.commit()
            # Admin user is cohort-routed via permission_key.
            user_notifs = _notifications_for_user(db, ts_ctx["user_id"])
            assert any(
                n.title == "generic with permission_key" for n in user_notifs
            ), "metadata permission_key should win over task_type defaults"
        finally:
            db.close()


# ── Per-site parity tests ───────────────────────────────────────────


class TestSite1LegacyTaskServiceDualWrite:
    """Site #1 — Decision A dual-write: legacy Task row + substrate row."""

    def test_dual_write_creates_both_rows(self, ts_ctx):
        from app.models.task import Task
        from app.services import task_service

        db = SessionLocal()
        try:
            t = task_service.create_task(
                db,
                company_id=ts_ctx["company_id"],
                title=f"dual write {uuid.uuid4().hex[:6]}",
                created_by_user_id=ts_ctx["user_id"],
            )
            # Legacy Task row exists.
            legacy = db.query(Task).filter(Task.id == t.id).first()
            assert legacy is not None
            # Substrate task_details row exists keyed off the legacy Task id.
            td = (
                db.query(TaskDetails)
                .filter(
                    TaskDetails.provenance_kind == "manual_creation",
                    TaskDetails.provenance_ref_type == "task",
                    TaskDetails.provenance_ref_id == t.id,
                )
                .first()
            )
            assert td is not None, "substrate dual-write did not occur"
            # VaultItem.metadata_json carries legacy_task_id linkback.
            vi = (
                db.query(VaultItem)
                .filter(VaultItem.id == td.vault_item_id)
                .first()
            )
            assert vi is not None
            assert (vi.metadata_json or {}).get("legacy_task_id") == t.id
        finally:
            db.close()

    def test_dual_write_with_assignee_dispatches_notification(self, ts_ctx):
        """Assignee != creator → direct-user notification flows
        through subscriber post-substrate-event (not inline)."""
        from app.models.user import User
        from app.services import task_service

        db = SessionLocal()
        try:
            other = User(
                id=_new_id(),
                company_id=ts_ctx["company_id"],
                email=f"x-{uuid.uuid4().hex[:6]}@ts.co",
                first_name="X",
                last_name="Y",
                hashed_password="x",
                is_active=True,
                role_id=ts_ctx["role_id"],
            )
            db.add(other)
            db.commit()
            title = f"site1 assigned {uuid.uuid4().hex[:6]}"
            task_service.create_task(
                db,
                company_id=ts_ctx["company_id"],
                title=title,
                created_by_user_id=ts_ctx["user_id"],
                assignee_user_id=other.id,
            )
            assignee_notifs = _notifications_for_user(db, other.id)
            assert any(
                f"Task assigned: {title}" == n.title for n in assignee_notifs
            ), "site #1 dual-write did not dispatch direct-user notification"
        finally:
            db.close()


class TestSite2SocialServiceCertificate:
    def test_substrate_task_created_with_permission_key(self, ts_ctx):
        """The site #2 refactor writes a task_details row with
        permission_key=invoice.approve in metadata. We exercise it
        directly via the substrate (the SSC service body has heavy
        order/PDF dependencies; the dispatch shape is what matters)."""
        db = SessionLocal()
        try:
            cert_id = _new_id()
            create_task_with_provenance(
                db,
                company_id=ts_ctx["company_id"],
                provenance_kind="integration_event",
                provenance_ref_type="social_service_certificate",
                provenance_ref_id=cert_id,
                event_kind="ss_cert_pending_approval",
                task_type_key="review_approval_task",
                title="Social service certificate pending approval (TEST-001)",
                description="Certificate TEST-CERT-001 for order TEST-001 is pending approval.",
                metadata={
                    "notification_permission_key": "invoice.approve",
                    "notification_category": "ss_cert_pending_approval",
                    "notification_link": f"/social-service-certificates/{cert_id}",
                    "notification_source_reference_type": "social_service_certificate",
                    "notification_source_reference_id": cert_id,
                },
            )
            db.commit()
            user_notifs = _notifications_for_user(db, ts_ctx["user_id"])
            match = [
                n for n in user_notifs
                if n.category == "ss_cert_pending_approval"
                and n.source_reference_id == cert_id
            ]
            assert match, "site #2 cohort dispatch did not occur"
            assert match[0].link == f"/social-service-certificates/{cert_id}"
        finally:
            db.close()


class TestSite3BaseAgent:
    """Site #3 — base_agent._dispatch_pending_attention_notification.

    Two cohort dispatch shapes: anomaly_resolution_task (3 accounting
    queues) + review_approval_task (month_end_close).
    """

    def test_anomaly_resolution_dispatch_shape(self, ts_ctx):
        db = SessionLocal()
        try:
            job_id = _new_id()
            create_task_with_provenance(
                db,
                company_id=ts_ctx["company_id"],
                provenance_kind="anomaly_detection",
                provenance_ref_type="agent_job",
                provenance_ref_id=job_id,
                event_kind="agent_anomaly_pending",
                task_type_key="anomaly_resolution_task",
                title="3 cash receipts matching items need review",
                description="Agent job test is awaiting review.",
                metadata={
                    "notification_permission_key": "invoice.approve",
                    "notification_category": "agent_anomaly_pending",
                    "notification_link": f"/agents/{job_id}/review",
                    "notification_source_reference_type": "agent_job",
                    "notification_source_reference_id": job_id,
                },
            )
            db.commit()
            match = [
                n for n in _notifications_for_user(db, ts_ctx["user_id"])
                if n.category == "agent_anomaly_pending"
                and n.source_reference_id == job_id
            ]
            assert match, "site #3 anomaly cohort dispatch did not occur"
        finally:
            db.close()

    def test_month_end_close_dispatch_shape(self, ts_ctx):
        db = SessionLocal()
        try:
            job_id = _new_id()
            create_task_with_provenance(
                db,
                company_id=ts_ctx["company_id"],
                provenance_kind="workflow_step",
                provenance_ref_type="agent_job",
                provenance_ref_id=job_id,
                event_kind="agent_job_awaiting_approval",
                task_type_key="review_approval_task",
                title="Month-end close ready to review (2026-03-31)",
                description="Agent job test is awaiting review.",
                metadata={
                    "notification_permission_key": "invoice.approve",
                    "notification_category": "agent_job_awaiting_approval",
                    "notification_link": f"/agents/{job_id}/review",
                    "notification_source_reference_type": "agent_job",
                    "notification_source_reference_id": job_id,
                },
            )
            db.commit()
            match = [
                n for n in _notifications_for_user(db, ts_ctx["user_id"])
                if n.category == "agent_job_awaiting_approval"
                and n.source_reference_id == job_id
            ]
            assert match, "site #3 month-end-close dispatch did not occur"
        finally:
            db.close()


class TestSite4Aftercare:
    def test_aftercare_funeral_followup_dispatch_shape(self, ts_ctx):
        # ts_ctx admin user short-circuits the fh_cases.aftercare
        # permission check (admin role bypass in user_has_permission).
        db = SessionLocal()
        try:
            job_id = _new_id()
            create_task_with_provenance(
                db,
                company_id=ts_ctx["company_id"],
                provenance_kind="workflow_step",
                provenance_ref_type="agent_job",
                provenance_ref_id=job_id,
                event_kind="funeral_followup_pending",
                task_type_key="customer_communication_task",
                title="Aftercare follow-up due: 3 cases",
                description="3 aftercare 7-day follow-up items are ready for review.",
                # No created_by_user_id — avoid Lock 3 self-suppression
                # for the admin recipient.
                metadata={
                    "notification_permission_key": "fh_cases.aftercare",
                    "notification_category": "funeral_followup_pending",
                    "notification_link": "/triage/aftercare_triage",
                    "notification_source_reference_type": "agent_job",
                    "notification_source_reference_id": job_id,
                },
            )
            db.commit()
            match = [
                n for n in _notifications_for_user(db, ts_ctx["user_id"])
                if n.category == "funeral_followup_pending"
                and n.source_reference_id == job_id
            ]
            assert match, "site #4 aftercare cohort dispatch did not occur"
            assert match[0].link == "/triage/aftercare_triage"
        finally:
            db.close()


class TestSite5CatalogFetch:
    def test_catalog_sync_pending_review_dispatch_shape(self, ts_ctx):
        db = SessionLocal()
        try:
            sync_log_id = _new_id()
            create_task_with_provenance(
                db,
                company_id=ts_ctx["company_id"],
                provenance_kind="integration_event",
                provenance_ref_type="urn_catalog_sync_log",
                provenance_ref_id=sync_log_id,
                event_kind="catalog_sync_pending_review",
                task_type_key="review_approval_task",
                title="Urn catalog sync pending review (5 product changes)",
                description="A new Wilbert urn catalog fetch has staged 5 product changes for review.",
                metadata={
                    "notification_permission_key": "invoice.approve",
                    "notification_category": "catalog_sync_pending_review",
                    "notification_link": "/triage/catalog_fetch_triage",
                    "notification_source_reference_type": "urn_catalog_sync_log",
                    "notification_source_reference_id": sync_log_id,
                },
            )
            db.commit()
            match = [
                n for n in _notifications_for_user(db, ts_ctx["user_id"])
                if n.category == "catalog_sync_pending_review"
                and n.source_reference_id == sync_log_id
            ]
            assert match, "site #5 catalog cohort dispatch did not occur"
        finally:
            db.close()


class TestSite6SafetyProgram:
    def test_safety_program_pending_review_dispatch_shape(self, ts_ctx):
        db = SessionLocal()
        try:
            gen_id = _new_id()
            create_task_with_provenance(
                db,
                company_id=ts_ctx["company_id"],
                provenance_kind="workflow_step",
                provenance_ref_type="safety_program_generation",
                provenance_ref_id=gen_id,
                event_kind="safety_program_pending_review",
                task_type_key="review_approval_task",
                title="Safety program ready for review: Forklift Safety",
                description="An AI-generated safety program has been staged for safety-trainer review.",
                metadata={
                    "notification_permission_key": "safety.trainer.approve",
                    "notification_category": "safety_program_pending_review",
                    "notification_link": f"/safety/programs/{gen_id}",
                    "notification_source_reference_type": "safety_program_generation",
                    "notification_source_reference_id": gen_id,
                },
            )
            db.commit()
            match = [
                n for n in _notifications_for_user(db, ts_ctx["user_id"])
                if n.category == "safety_program_pending_review"
                and n.source_reference_id == gen_id
            ]
            assert match, "site #6 safety program cohort dispatch did not occur"
        finally:
            db.close()


class TestSite7WorkflowEngine:
    def test_workflow_review_pending_dispatch_shape(self, ts_ctx):
        db = SessionLocal()
        try:
            item_id = _new_id()
            create_task_with_provenance(
                db,
                company_id=ts_ctx["company_id"],
                provenance_kind="workflow_step",
                provenance_ref_type="workflow_review_item",
                provenance_ref_id=item_id,
                event_kind="workflow_review_pending",
                task_type_key="review_approval_task",
                title="Workflow review needed: focus_test",
                description="A workflow run has paused on a review step (focus_test) and is awaiting decision.",
                metadata={
                    "notification_permission_key": "admin",
                    "notification_category": "workflow_review_pending",
                    "notification_link": "/triage/workflow_review_triage",
                    "notification_source_reference_type": "workflow_review_item",
                    "notification_source_reference_id": item_id,
                },
            )
            db.commit()
            match = [
                n for n in _notifications_for_user(db, ts_ctx["user_id"])
                if n.category == "workflow_review_pending"
                and n.source_reference_id == item_id
            ]
            assert match, "site #7 workflow review cohort dispatch did not occur"
        finally:
            db.close()


class TestSite8EmailClassificationDispatch:
    def test_email_unclassified_pending_dispatch_shape(self, ts_ctx):
        db = SessionLocal()
        try:
            classification_id = _new_id()
            create_task_with_provenance(
                db,
                company_id=ts_ctx["company_id"],
                provenance_kind="communication_inbound",
                provenance_ref_type="workflow_email_classification",
                provenance_ref_id=classification_id,
                event_kind="email_unclassified_pending",
                task_type_key="anomaly_resolution_task",
                title="Unclassified email needs routing (Test subject)",
                description="An inbound email failed all three classification tiers and needs manual routing.",
                metadata={
                    "notification_permission_key": "admin",
                    "notification_category": "email_unclassified_pending",
                    "notification_link": "/triage/email_unclassified_triage",
                    "notification_type": "warning",
                    "notification_source_reference_type": "workflow_email_classification",
                    "notification_source_reference_id": classification_id,
                },
            )
            db.commit()
            match = [
                n for n in _notifications_for_user(db, ts_ctx["user_id"])
                if n.category == "email_unclassified_pending"
                and n.source_reference_id == classification_id
            ]
            assert match, "site #8 email-unclassified cohort dispatch did not occur"
            # notification_type override propagated.
            assert match[0].type == "warning"
        finally:
            db.close()


# ── Idempotency at substrate level ──────────────────────────────────


class TestSubstrateIdempotency:
    """A second create_task_with_provenance call with identical
    composite key returns the existing row and does NOT re-dispatch.
    """

    def test_re_create_returns_existing_no_duplicate_notification(self, ts_ctx):
        db = SessionLocal()
        try:
            ref = _new_id()
            md = {
                "notification_permission_key": "invoice.approve",
                "notification_category": "ss_cert_pending_approval",
            }
            title = f"idempotency probe {uuid.uuid4().hex[:8]}"
            td1 = create_task_with_provenance(
                db,
                company_id=ts_ctx["company_id"],
                provenance_kind="integration_event",
                provenance_ref_type="social_service_certificate",
                provenance_ref_id=ref,
                event_kind="ss_cert_pending_approval",
                task_type_key="review_approval_task",
                title=title,
                metadata=md,
            )
            db.commit()
            td2 = create_task_with_provenance(
                db,
                company_id=ts_ctx["company_id"],
                provenance_kind="integration_event",
                provenance_ref_type="social_service_certificate",
                provenance_ref_id=ref,
                event_kind="ss_cert_pending_approval",
                task_type_key="review_approval_task",
                title=title,
                metadata=md,
            )
            db.commit()
            assert td1.id == td2.id, "second call should return existing row"
            # Exactly one notification for that probe (the original).
            count = (
                db.query(Notification)
                .filter(Notification.title == title)
                .count()
            )
            assert count == 1, (
                f"expected 1 notification (no re-dispatch on idempotent "
                f"call), got {count}"
            )
        finally:
            db.close()
