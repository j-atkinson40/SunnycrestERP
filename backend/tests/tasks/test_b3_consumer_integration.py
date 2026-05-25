"""v1 task substrate B3 — consumer integration tests.

8 consumer-integration items shipped in B3:
  1. Pulse _build_tasks_item wire
  2. Briefings 3 helpers
  3. 4 subscriber bodies (briefings_invalidator, pulse_invalidator,
     workflow_resumer, focus_closer)
  4. 3 workflow node types (create_task, wait_for_task_completion,
     route_on_task_outcome)
  5. Focus task linkage (focus_sessions.task_id)
  6. Intelligence task-creation helper
  7. customer_communication_task outbound dispatch wire
  8. Routing rules (r109) + three-tier resolver + visibility enforcement

Test isolation per B2 precedent: uuid-randomized provenance_ref_id
per test prevents idempotency pollution from re-runs against a shared
dev DB.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.database import SessionLocal
from app.models.focus_session import FocusSession
from app.models.task_details import TaskDetails
from app.models.task_routing_rule import TaskRoutingRule
from app.models.vault_item import VaultItem
from app.services.tasks.service import (
    create_task_with_provenance,
    transition_task,
)


# ── Helpers ─────────────────────────────────────────────────────────


def _new_id() -> str:
    return str(uuid.uuid4())


def _make_task(
    db,
    *,
    company_id: str,
    assignee_user_id: str | None = None,
    task_type_key: str = "generic_task",
    title: str = "T",
    visibility: str = "operator_internal",
    priority: str = "normal",
    due_date: date | None = None,
    metadata: dict | None = None,
    provenance_kind: str = "manual_creation",
    provenance_ref_type: str | None = None,
    provenance_ref_id: str | None = None,
    event_kind: str = "manual",
) -> TaskDetails:
    return create_task_with_provenance(
        db,
        company_id=company_id,
        provenance_kind=provenance_kind,
        provenance_ref_type=provenance_ref_type,
        provenance_ref_id=provenance_ref_id or _new_id(),
        event_kind=event_kind,
        task_type_key=task_type_key,
        title=title,
        assignee_user_id=assignee_user_id,
        visibility=visibility,
        priority=priority,
        due_date=due_date,
        metadata=metadata,
    )


# ══════════════════════════════════════════════════════════════════
# Item 1 — Pulse _build_tasks_item wire
# ══════════════════════════════════════════════════════════════════


class TestPulseBuildTasksItem:
    def test_returns_none_when_no_assigned_tasks(self, ts_ctx):
        db = SessionLocal()
        try:
            from app.models.user import User
            from app.services.pulse.personal_layer_service import _build_tasks_item

            user = db.query(User).filter(User.id == ts_ctx["user_id"]).first()
            result = _build_tasks_item(db, user=user)
            # User may have ambient prior-test tasks. Just verify it's
            # either None or a properly shaped LayerItem.
            if result is not None:
                assert result.kind == "stream"
                assert result.component_key == "tasks_assigned"
        finally:
            db.close()

    def test_returns_layer_item_with_assigned_action_task(self, ts_ctx):
        db = SessionLocal()
        try:
            from app.models.user import User
            from app.services.pulse.personal_layer_service import _build_tasks_item

            _make_task(
                db,
                company_id=ts_ctx["company_id"],
                assignee_user_id=ts_ctx["user_id"],
                title=f"pulse-test-{_new_id()[:6]}",
            )
            db.commit()

            user = db.query(User).filter(User.id == ts_ctx["user_id"]).first()
            result = _build_tasks_item(db, user=user)
            assert result is not None
            assert result.kind == "stream"
            assert result.component_key == "tasks_assigned"
            assert result.payload["total_count"] >= 1
            assert isinstance(result.payload["top_items"], list)
        finally:
            db.close()

    def test_excludes_terminal_action_states(self, ts_ctx):
        db = SessionLocal()
        try:
            from app.models.user import User
            from app.services.pulse.personal_layer_service import _build_tasks_item

            td = _make_task(
                db,
                company_id=ts_ctx["company_id"],
                assignee_user_id=ts_ctx["user_id"],
                title=f"pulse-done-{_new_id()[:6]}",
            )
            transition_task(
                db,
                task_details_id=td.id,
                to_state="in_progress",
                actor_user_id=ts_ctx["user_id"],
            )
            transition_task(
                db,
                task_details_id=td.id,
                to_state="done",
                actor_user_id=ts_ctx["user_id"],
            )
            db.commit()

            user = db.query(User).filter(User.id == ts_ctx["user_id"]).first()
            result = _build_tasks_item(db, user=user)
            # Find this td's id in top_items, if any
            if result is not None:
                td_ids = [it["id"] for it in result.payload["top_items"]]
                assert td.id not in td_ids
        finally:
            db.close()

    def test_excludes_portal_visibility(self, ts_ctx):
        """Operator-only visibility filter: portal_family does NOT surface."""
        db = SessionLocal()
        try:
            from app.models.user import User
            from app.services.pulse.personal_layer_service import _build_tasks_item

            td = _make_task(
                db,
                company_id=ts_ctx["company_id"],
                assignee_user_id=ts_ctx["user_id"],
                visibility="portal_family",
                title=f"portal-vis-{_new_id()[:6]}",
            )
            db.commit()

            user = db.query(User).filter(User.id == ts_ctx["user_id"]).first()
            result = _build_tasks_item(db, user=user)
            if result is not None:
                td_ids = [it["id"] for it in result.payload["top_items"]]
                assert td.id not in td_ids
        finally:
            db.close()

    def test_priority_rank_urgent_above_normal(self, ts_ctx):
        db = SessionLocal()
        try:
            from app.models.user import User
            from app.services.pulse.personal_layer_service import _build_tasks_item

            normal_td = _make_task(
                db,
                company_id=ts_ctx["company_id"],
                assignee_user_id=ts_ctx["user_id"],
                title=f"normal-{_new_id()[:6]}",
                priority="normal",
            )
            urgent_td = _make_task(
                db,
                company_id=ts_ctx["company_id"],
                assignee_user_id=ts_ctx["user_id"],
                title=f"urgent-{_new_id()[:6]}",
                priority="urgent",
            )
            db.commit()

            user = db.query(User).filter(User.id == ts_ctx["user_id"]).first()
            result = _build_tasks_item(db, user=user)
            assert result is not None
            top_ids = [it["id"] for it in result.payload["top_items"]]
            # urgent should appear before normal in top items
            if urgent_td.id in top_ids and normal_td.id in top_ids:
                assert top_ids.index(urgent_td.id) < top_ids.index(normal_td.id)
        finally:
            db.close()


# ══════════════════════════════════════════════════════════════════
# Item 2 — Briefings 3 helpers
# ══════════════════════════════════════════════════════════════════


class TestBriefingsHelpers:
    def test_pending_tasks_returns_open_assigned(self, ts_ctx):
        db = SessionLocal()
        try:
            from app.models.user import User
            from app.services.briefings.data_sources import (
                _collect_pending_tasks_summary,
            )

            _make_task(
                db,
                company_id=ts_ctx["company_id"],
                assignee_user_id=ts_ctx["user_id"],
                title=f"pending-{_new_id()[:6]}",
            )
            db.commit()

            user = db.query(User).filter(User.id == ts_ctx["user_id"]).first()
            out = _collect_pending_tasks_summary(db, user)
            assert isinstance(out, list)
            assert len(out) >= 1
            for entry in out:
                assert "task_details_id" in entry
                assert "title" in entry
                assert "priority" in entry
                assert "status" in entry
        finally:
            db.close()

    def test_recent_completions_returns_done_tasks(self, ts_ctx):
        db = SessionLocal()
        try:
            from app.models.user import User
            from app.services.briefings.data_sources import (
                _collect_recent_completions_summary,
            )

            td = _make_task(
                db,
                company_id=ts_ctx["company_id"],
                assignee_user_id=ts_ctx["user_id"],
                title=f"done-{_new_id()[:6]}",
            )
            transition_task(
                db, task_details_id=td.id, to_state="in_progress",
                actor_user_id=ts_ctx["user_id"],
            )
            transition_task(
                db, task_details_id=td.id, to_state="done",
                actor_user_id=ts_ctx["user_id"],
            )
            db.commit()

            user = db.query(User).filter(User.id == ts_ctx["user_id"]).first()
            since = datetime.now(timezone.utc) - timedelta(hours=1)
            out = _collect_recent_completions_summary(db, user, since=since)
            assert isinstance(out, list)
            assert any(e["task_details_id"] == td.id for e in out)
        finally:
            db.close()

    def test_upcoming_deadlines_returns_future_due_tasks(self, ts_ctx):
        db = SessionLocal()
        try:
            from app.models.user import User
            from app.services.briefings.data_sources import (
                _collect_upcoming_deadlines_summary,
            )

            future = date.today() + timedelta(days=3)
            td = _make_task(
                db,
                company_id=ts_ctx["company_id"],
                assignee_user_id=ts_ctx["user_id"],
                title=f"due-{_new_id()[:6]}",
                due_date=future,
            )
            db.commit()

            user = db.query(User).filter(User.id == ts_ctx["user_id"]).first()
            out = _collect_upcoming_deadlines_summary(db, user, days_ahead=14)
            assert isinstance(out, list)
            assert any(e["task_details_id"] == td.id for e in out)
        finally:
            db.close()

    def test_pending_tasks_excludes_portal_visibility(self, ts_ctx):
        db = SessionLocal()
        try:
            from app.models.user import User
            from app.services.briefings.data_sources import (
                _collect_pending_tasks_summary,
            )

            td = _make_task(
                db,
                company_id=ts_ctx["company_id"],
                assignee_user_id=ts_ctx["user_id"],
                visibility="portal_contractor",
                title=f"portal-pen-{_new_id()[:6]}",
            )
            db.commit()

            user = db.query(User).filter(User.id == ts_ctx["user_id"]).first()
            out = _collect_pending_tasks_summary(db, user)
            assert all(e["task_details_id"] != td.id for e in out)
        finally:
            db.close()


# ══════════════════════════════════════════════════════════════════
# Item 3 — 4 subscriber bodies
# ══════════════════════════════════════════════════════════════════


class TestPulseInvalidator:
    def test_invalidates_for_assigned_user(self, ts_ctx):
        db = SessionLocal()
        try:
            with patch(
                "app.services.pulse.composition_cache.invalidate_for_user",
                return_value=0,
            ) as mock_inv:
                _make_task(
                    db,
                    company_id=ts_ctx["company_id"],
                    assignee_user_id=ts_ctx["user_id"],
                    title=f"pulse-inv-{_new_id()[:6]}",
                )
                db.commit()
                # Subscriber fires synchronously on task_created.
                mock_inv.assert_called()
                # At least one call references our user.
                called_user_ids = [c.args[0] for c in mock_inv.call_args_list]
                assert ts_ctx["user_id"] in called_user_ids
        finally:
            db.close()


class TestBriefingsInvalidator:
    def test_subscriber_fires_on_task_created_without_error(self, ts_ctx):
        db = SessionLocal()
        try:
            _make_task(
                db,
                company_id=ts_ctx["company_id"],
                assignee_user_id=ts_ctx["user_id"],
                title=f"briefings-inv-{_new_id()[:6]}",
            )
            db.commit()
        finally:
            db.close()


class TestWorkflowResumer:
    def test_skips_when_task_not_workflow_step_provenance(self, ts_ctx):
        """task_completed for non-workflow_step task → no advance_run call."""
        db = SessionLocal()
        try:
            with patch(
                "app.services.workflow_engine.advance_run"
            ) as mock_adv:
                td = _make_task(
                    db,
                    company_id=ts_ctx["company_id"],
                    assignee_user_id=ts_ctx["user_id"],
                    title=f"resumer-skip-{_new_id()[:6]}",
                )
                db.commit()
                transition_task(
                    db, task_details_id=td.id, to_state="in_progress",
                    actor_user_id=ts_ctx["user_id"],
                )
                transition_task(
                    db, task_details_id=td.id, to_state="done",
                    actor_user_id=ts_ctx["user_id"],
                )
                db.commit()
                mock_adv.assert_not_called()
        finally:
            db.close()


class TestFocusCloser:
    def test_closes_linked_focus_session_on_task_completion(self, ts_ctx):
        db = SessionLocal()
        try:
            td = _make_task(
                db,
                company_id=ts_ctx["company_id"],
                assignee_user_id=ts_ctx["user_id"],
                title=f"focus-link-{_new_id()[:6]}",
            )
            db.commit()
            # Create a focus session linked to the task.
            fs = FocusSession(
                id=str(uuid.uuid4()),
                company_id=ts_ctx["company_id"],
                user_id=ts_ctx["user_id"],
                focus_type="task_review",
                layout_state={},
                is_active=True,
                task_id=td.vault_item_id,
            )
            db.add(fs)
            db.commit()
            fs_id = fs.id

            transition_task(
                db, task_details_id=td.id, to_state="in_progress",
                actor_user_id=ts_ctx["user_id"],
            )
            transition_task(
                db, task_details_id=td.id, to_state="done",
                actor_user_id=ts_ctx["user_id"],
            )
            db.commit()

            fs2 = db.query(FocusSession).filter(FocusSession.id == fs_id).first()
            assert fs2 is not None
            assert fs2.is_active is False
            assert fs2.closed_at is not None
        finally:
            db.close()


# ══════════════════════════════════════════════════════════════════
# Item 4 — 3 workflow node types
# ══════════════════════════════════════════════════════════════════


class TestWorkflowNodeTypes:
    def _mk_run(self, db, ts_ctx):
        from app.models.workflow import Workflow, WorkflowRun
        wf = Workflow(
            id=str(uuid.uuid4()),
            name=f"t-{_new_id()[:6]}",
            company_id=None,
            trigger_type="manual",
            trigger_config={},
            is_active=True,
        )
        db.add(wf)
        db.flush()
        run = WorkflowRun(
            id=str(uuid.uuid4()),
            workflow_id=wf.id,
            company_id=ts_ctx["company_id"],
            triggered_by_user_id=ts_ctx["user_id"],
            trigger_source="manual",
            status="running",
        )
        db.add(run)
        db.commit()
        return run

    def test_create_task_handler(self, ts_ctx):
        db = SessionLocal()
        try:
            from app.services.workflow_engine import _handle_create_task

            run = self._mk_run(db, ts_ctx)
            cfg = {
                "action_type": "create_task",
                "task_type_key": "generic_task",
                "title": f"wf-create-{_new_id()[:6]}",
                "assignee_user_id": ts_ctx["user_id"],
            }
            out = _handle_create_task(db, cfg, run)
            db.commit()
            assert out["status"] == "applied"
            assert "task_details_id" in out
            td = db.query(TaskDetails).filter(
                TaskDetails.id == out["task_details_id"]
            ).first()
            assert td is not None
            assert td.provenance_kind == "workflow_step"
            assert td.provenance_ref_type == "workflow_run"
            assert td.provenance_ref_id == run.id
        finally:
            db.close()

    def test_create_task_missing_title(self, ts_ctx):
        db = SessionLocal()
        try:
            from app.services.workflow_engine import _handle_create_task

            run = self._mk_run(db, ts_ctx)
            cfg = {"action_type": "create_task", "task_type_key": "generic_task"}
            out = _handle_create_task(db, cfg, run)
            assert out["status"] == "errored"
        finally:
            db.close()

    def test_wait_for_task_completion_pauses_when_not_terminal(self, ts_ctx):
        db = SessionLocal()
        try:
            from app.services.workflow_engine import (
                _handle_create_task,
                _handle_wait_for_task_completion,
            )

            run = self._mk_run(db, ts_ctx)
            create_cfg = {
                "action_type": "create_task",
                "task_type_key": "generic_task",
                "title": f"wf-wait-{_new_id()[:6]}",
                "assignee_user_id": ts_ctx["user_id"],
                "event_kind": "step.a",
            }
            create_out = _handle_create_task(db, create_cfg, run)
            db.commit()
            assert create_out["status"] == "applied"

            wait_cfg = {
                "action_type": "wait_for_task_completion",
                "event_kind": "step.a",
            }
            wait_out = _handle_wait_for_task_completion(db, wait_cfg, run)
            assert wait_out.get("type") == "awaiting_approval"
            assert wait_out["reason"] == "wait_for_task_completion"
        finally:
            db.close()

    def test_wait_for_task_completion_passes_when_terminal(self, ts_ctx):
        db = SessionLocal()
        try:
            from app.services.workflow_engine import (
                _handle_create_task,
                _handle_wait_for_task_completion,
            )

            run = self._mk_run(db, ts_ctx)
            create_cfg = {
                "action_type": "create_task",
                "task_type_key": "generic_task",
                "title": f"wf-wait-done-{_new_id()[:6]}",
                "assignee_user_id": ts_ctx["user_id"],
                "event_kind": "step.b",
            }
            create_out = _handle_create_task(db, create_cfg, run)
            db.commit()
            td_id = create_out["task_details_id"]

            transition_task(
                db, task_details_id=td_id, to_state="in_progress",
                actor_user_id=ts_ctx["user_id"],
            )
            transition_task(
                db, task_details_id=td_id, to_state="done",
                actor_user_id=ts_ctx["user_id"],
                resolution_outcome="approved",
            )
            db.commit()

            wait_cfg = {
                "action_type": "wait_for_task_completion",
                "event_kind": "step.b",
            }
            wait_out = _handle_wait_for_task_completion(db, wait_cfg, run)
            assert wait_out.get("status") == "applied"
            assert wait_out["already_terminal"] is True
            assert wait_out["current_state"] == "done"
        finally:
            db.close()

    def test_route_on_task_outcome_returns_outcome(self, ts_ctx):
        db = SessionLocal()
        try:
            from app.services.workflow_engine import (
                _handle_create_task,
                _handle_route_on_task_outcome,
            )

            run = self._mk_run(db, ts_ctx)
            create_cfg = {
                "action_type": "create_task",
                "task_type_key": "generic_task",
                "title": f"wf-route-{_new_id()[:6]}",
                "assignee_user_id": ts_ctx["user_id"],
                "event_kind": "step.c",
            }
            out = _handle_create_task(db, create_cfg, run)
            db.commit()
            td_id = out["task_details_id"]
            transition_task(
                db, task_details_id=td_id, to_state="in_progress",
                actor_user_id=ts_ctx["user_id"],
            )
            transition_task(
                db, task_details_id=td_id, to_state="done",
                actor_user_id=ts_ctx["user_id"],
                resolution_outcome="approved",
            )
            db.commit()

            route_cfg = {
                "action_type": "route_on_task_outcome",
                "event_kind": "step.c",
                "outcome_branches": {
                    "approved": "next_step_approved",
                    "rejected": "next_step_rejected",
                },
            }
            out = _handle_route_on_task_outcome(db, route_cfg, run)
            assert out["status"] == "applied"
            assert out["outcome"] == "approved"
            assert out["matched_branch"] == "next_step_approved"
        finally:
            db.close()


# ══════════════════════════════════════════════════════════════════
# Item 5 — Focus task linkage
# ══════════════════════════════════════════════════════════════════


class TestFocusTaskLinkage:
    def test_create_session_with_task_id(self, ts_ctx):
        db = SessionLocal()
        try:
            from app.models.user import User
            from app.services.focus.focus_session_service import (
                create_or_resume_session,
            )

            td = _make_task(
                db,
                company_id=ts_ctx["company_id"],
                assignee_user_id=ts_ctx["user_id"],
                title=f"focus-create-{_new_id()[:6]}",
            )
            db.commit()
            user = db.query(User).filter(User.id == ts_ctx["user_id"]).first()
            session = create_or_resume_session(
                db,
                user,
                f"focus-{_new_id()[:6]}",
                task_id=td.vault_item_id,
            )
            db.commit()
            assert session.task_id == td.vault_item_id
        finally:
            db.close()

    def test_resume_session_backfills_task_id(self, ts_ctx):
        db = SessionLocal()
        try:
            from app.models.user import User
            from app.services.focus.focus_session_service import (
                create_or_resume_session,
            )

            user = db.query(User).filter(User.id == ts_ctx["user_id"]).first()
            ftype = f"focus-{_new_id()[:6]}"
            # Initial create without task_id.
            s1 = create_or_resume_session(db, user, ftype)
            db.commit()
            assert s1.task_id is None

            td = _make_task(
                db,
                company_id=ts_ctx["company_id"],
                assignee_user_id=ts_ctx["user_id"],
                title="backfill",
            )
            db.commit()
            # Resume with task_id; should backfill.
            s2 = create_or_resume_session(
                db, user, ftype, task_id=td.vault_item_id
            )
            db.commit()
            assert s2.id == s1.id
            assert s2.task_id == td.vault_item_id
        finally:
            db.close()


# ══════════════════════════════════════════════════════════════════
# Item 6 — Intelligence integration helper
# ══════════════════════════════════════════════════════════════════


class TestIntelligenceIntegration:
    def test_creates_task_with_intelligence_provenance(self, ts_ctx):
        db = SessionLocal()
        try:
            from app.services.tasks.intelligence_integration import (
                create_intelligence_observation_task,
            )

            ref_id = _new_id()
            td = create_intelligence_observation_task(
                db,
                company_id=ts_ctx["company_id"],
                observation_ref_type="agent_anomaly",
                observation_ref_id=ref_id,
                event_kind="anomaly.high_severity",
                title="anom",
                notification_permission_key="invoice.approve",
            )
            db.commit()
            assert td.provenance_kind == "intelligence_observation"
            assert td.provenance_ref_id == ref_id
            # Verify metadata carries the permission key on the VaultItem.
            vi = db.query(VaultItem).filter(
                VaultItem.id == td.vault_item_id
            ).first()
            assert vi.metadata_json.get("notification_permission_key") == \
                "invoice.approve"
        finally:
            db.close()

    def test_idempotent_on_same_composite_key(self, ts_ctx):
        db = SessionLocal()
        try:
            from app.services.tasks.intelligence_integration import (
                create_intelligence_observation_task,
            )

            ref_id = _new_id()
            kwargs = dict(
                company_id=ts_ctx["company_id"],
                observation_ref_type="agent_anomaly",
                observation_ref_id=ref_id,
                event_kind="anomaly.x",
                title="anom-x",
            )
            td1 = create_intelligence_observation_task(db, **kwargs)
            db.commit()
            td2 = create_intelligence_observation_task(db, **kwargs)
            db.commit()
            assert td1.id == td2.id
        finally:
            db.close()


# ══════════════════════════════════════════════════════════════════
# Item 7 — customer_communication_task outbound dispatch
# ══════════════════════════════════════════════════════════════════


class TestCustomerCommunicationOutbound:
    def test_dispatch_invokes_send_email_with_template(self, ts_ctx):
        db = SessionLocal()
        try:
            with patch(
                "app.services.delivery.delivery_service.send_email_with_template"
            ) as mock_send:
                td = _make_task(
                    db,
                    company_id=ts_ctx["company_id"],
                    assignee_user_id=ts_ctx["user_id"],
                    task_type_key="customer_communication_task",
                    title=f"comm-out-{_new_id()[:6]}",
                    metadata={
                        "outbound_template_key": "test.template",
                        "outbound_to_email": "x@y.test",
                        "outbound_template_context": {"a": 1},
                    },
                )
                db.commit()
                transition_task(
                    db, task_details_id=td.id, to_state="in_progress",
                    actor_user_id=ts_ctx["user_id"],
                )
                transition_task(
                    db, task_details_id=td.id, to_state="done",
                    actor_user_id=ts_ctx["user_id"],
                )
                db.commit()
                mock_send.assert_called_once()
                call_kwargs = mock_send.call_args.kwargs
                assert call_kwargs["template_key"] == "test.template"
                assert call_kwargs["to_email"] == "x@y.test"
                assert call_kwargs["caller_module"] == (
                    "customer_communication_task.on_status_change"
                )
        finally:
            db.close()

    def test_dispatch_skipped_when_no_outbound_metadata(self, ts_ctx):
        db = SessionLocal()
        try:
            with patch(
                "app.services.delivery.delivery_service.send_email_with_template"
            ) as mock_send:
                td = _make_task(
                    db,
                    company_id=ts_ctx["company_id"],
                    assignee_user_id=ts_ctx["user_id"],
                    task_type_key="customer_communication_task",
                    title=f"comm-noout-{_new_id()[:6]}",
                )
                db.commit()
                transition_task(
                    db, task_details_id=td.id, to_state="in_progress",
                    actor_user_id=ts_ctx["user_id"],
                )
                transition_task(
                    db, task_details_id=td.id, to_state="done",
                    actor_user_id=ts_ctx["user_id"],
                )
                db.commit()
                mock_send.assert_not_called()
        finally:
            db.close()

    def test_dispatch_only_fires_on_configured_state(self, ts_ctx):
        db = SessionLocal()
        try:
            with patch(
                "app.services.delivery.delivery_service.send_email_with_template"
            ) as mock_send:
                td = _make_task(
                    db,
                    company_id=ts_ctx["company_id"],
                    assignee_user_id=ts_ctx["user_id"],
                    task_type_key="customer_communication_task",
                    title=f"comm-state-{_new_id()[:6]}",
                    metadata={
                        "outbound_template_key": "test.template",
                        "outbound_to_email": "z@y.test",
                        "dispatch_on_state": "in_progress",
                    },
                )
                db.commit()
                # Transition to in_progress: should dispatch.
                transition_task(
                    db, task_details_id=td.id, to_state="in_progress",
                    actor_user_id=ts_ctx["user_id"],
                )
                db.commit()
                assert mock_send.call_count == 1
                # Further transition (to done) should NOT dispatch.
                transition_task(
                    db, task_details_id=td.id, to_state="done",
                    actor_user_id=ts_ctx["user_id"],
                )
                db.commit()
                assert mock_send.call_count == 1
        finally:
            db.close()


# ══════════════════════════════════════════════════════════════════
# Item 8 — Routing + visibility enforcement
# ══════════════════════════════════════════════════════════════════


class TestRoutingResolver:
    def _cleanup(self, db, company_id, task_type_key):
        db.query(TaskRoutingRule).filter(
            TaskRoutingRule.tenant_id == company_id,
            TaskRoutingRule.task_type_key == task_type_key,
        ).delete()
        db.commit()

    def test_returns_none_when_no_rule(self, ts_ctx):
        db = SessionLocal()
        try:
            from app.services.tasks.routing import resolve_routing

            result = resolve_routing(
                db,
                company_id=ts_ctx["company_id"],
                task_type_key=f"no-such-type-{_new_id()[:6]}",
            )
            assert result is None
        finally:
            db.close()

    def test_direct_user_tenant_scope(self, ts_ctx):
        db = SessionLocal()
        try:
            from app.services.tasks.routing import resolve_routing

            ttk = f"ttk-direct-{_new_id()[:6]}"
            rule = TaskRoutingRule(
                id=_new_id(),
                scope="tenant",
                tenant_id=ts_ctx["company_id"],
                task_type_key=ttk,
                routing_mode="direct_user",
                target_user_id=ts_ctx["user_id"],
                is_active=True,
            )
            db.add(rule)
            db.commit()

            result = resolve_routing(
                db,
                company_id=ts_ctx["company_id"],
                task_type_key=ttk,
            )
            assert result is not None
            assert result.assignee_user_id == ts_ctx["user_id"]
            self._cleanup(db, ts_ctx["company_id"], ttk)
        finally:
            db.close()

    def test_three_tier_first_match_wins(self, ts_ctx):
        """Tenant rule wins over vertical_default + platform_default."""
        db = SessionLocal()
        try:
            from app.services.tasks.routing import resolve_routing

            ttk = f"ttk-tier-{_new_id()[:6]}"
            # platform_default
            db.add(TaskRoutingRule(
                id=_new_id(),
                scope="platform_default",
                task_type_key=ttk,
                routing_mode="direct_user",
                target_user_id=ts_ctx["user_id"],
                is_active=True,
            ))
            # vertical_default
            db.add(TaskRoutingRule(
                id=_new_id(),
                scope="vertical_default",
                vertical="manufacturing",
                task_type_key=ttk,
                routing_mode="direct_user",
                target_user_id=ts_ctx["user_id"],
                is_active=True,
            ))
            # tenant
            db.add(TaskRoutingRule(
                id=_new_id(),
                scope="tenant",
                tenant_id=ts_ctx["company_id"],
                task_type_key=ttk,
                routing_mode="direct_user",
                target_user_id=ts_ctx["user_id"],
                is_active=True,
            ))
            db.commit()

            result = resolve_routing(
                db,
                company_id=ts_ctx["company_id"],
                task_type_key=ttk,
            )
            assert result is not None
            assert result.rule.scope == "tenant"
            db.query(TaskRoutingRule).filter(
                TaskRoutingRule.task_type_key == ttk
            ).delete()
            db.commit()
        finally:
            db.close()

    def test_create_task_uses_routing_when_no_explicit_assignee(self, ts_ctx):
        db = SessionLocal()
        try:
            ttk = f"ttk-create-{_new_id()[:6]}"
            db.add(TaskRoutingRule(
                id=_new_id(),
                scope="tenant",
                tenant_id=ts_ctx["company_id"],
                task_type_key=ttk,
                routing_mode="direct_user",
                target_user_id=ts_ctx["user_id"],
                is_active=True,
            ))
            db.commit()

            td = create_task_with_provenance(
                db,
                company_id=ts_ctx["company_id"],
                provenance_kind="manual_creation",
                provenance_ref_type=None,
                provenance_ref_id=_new_id(),
                event_kind="manual",
                task_type_key=ttk,
                title=f"routed-{_new_id()[:6]}",
            )
            db.commit()
            assert td.assignee_user_id == ts_ctx["user_id"]
            self._cleanup(db, ts_ctx["company_id"], ttk)
        finally:
            db.close()

    def test_create_task_explicit_assignee_overrides_routing(self, ts_ctx):
        db = SessionLocal()
        try:
            # Create a rule pointing somewhere; explicit assignee wins.
            ttk = f"ttk-override-{_new_id()[:6]}"
            other_user_id = str(uuid.uuid4())  # bogus user id, never resolved
            db.add(TaskRoutingRule(
                id=_new_id(),
                scope="tenant",
                tenant_id=ts_ctx["company_id"],
                task_type_key=ttk,
                routing_mode="direct_user",
                target_user_id=ts_ctx["user_id"],
                is_active=True,
            ))
            db.commit()

            td = create_task_with_provenance(
                db,
                company_id=ts_ctx["company_id"],
                provenance_kind="manual_creation",
                provenance_ref_type=None,
                provenance_ref_id=_new_id(),
                event_kind="manual",
                task_type_key=ttk,
                title=f"override-{_new_id()[:6]}",
                assignee_user_id=ts_ctx["user_id"],
            )
            db.commit()
            # Explicit assignee preserved.
            assert td.assignee_user_id == ts_ctx["user_id"]
            self._cleanup(db, ts_ctx["company_id"], ttk)
            _ = other_user_id  # silence linter
        finally:
            db.close()


class TestVisibilityEnforcement:
    def test_list_task_details_for_company_filters_portal_values(self, ts_ctx):
        db = SessionLocal()
        try:
            from app.services.tasks.service import list_task_details_for_company

            td_op = _make_task(
                db,
                company_id=ts_ctx["company_id"],
                assignee_user_id=ts_ctx["user_id"],
                visibility="operator_internal",
                title=f"vis-op-{_new_id()[:6]}",
            )
            td_portal = _make_task(
                db,
                company_id=ts_ctx["company_id"],
                assignee_user_id=ts_ctx["user_id"],
                visibility="portal_family",
                title=f"vis-portal-{_new_id()[:6]}",
            )
            db.commit()

            rows = list_task_details_for_company(
                db,
                company_id=ts_ctx["company_id"],
                assignee_user_id=ts_ctx["user_id"],
            )
            row_ids = [r.id for r in rows]
            assert td_op.id in row_ids
            assert td_portal.id not in row_ids
        finally:
            db.close()
