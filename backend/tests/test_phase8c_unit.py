"""Workflow Arc Phase 8c — unit tests for shared infrastructure
registration.

Confirms the three new migrations are correctly wired into:
  - workflow_engine._SERVICE_METHOD_REGISTRY (3 pipeline entries)
  - triage.engine._DIRECT_QUERIES (3 direct-query builders)
  - triage.ai_question._RELATED_ENTITY_BUILDERS (3 builders)
  - triage.action_handlers.HANDLERS (9 handlers)
  - triage.platform_defaults (3 queue configs)
  - default_workflows.TIER_1_WORKFLOWS (3 migrated seeds)
"""

from __future__ import annotations

import pytest


class TestWorkflowEngineRegistry:
    def test_all_three_pipelines_registered(self):
        from app.services.workflow_engine import _SERVICE_METHOD_REGISTRY

        keys = set(_SERVICE_METHOD_REGISTRY.keys())
        # Phase 8b (cash_receipts) baseline.
        assert "cash_receipts.run_match_pipeline" in keys
        # Phase 8c additions.
        assert "month_end_close.run_close_pipeline" in keys
        assert "ar_collections.run_collections_pipeline" in keys
        assert (
            "expense_categorization.run_categorization_pipeline" in keys
        )

    def test_month_end_close_allowed_kwargs_include_period(self):
        """Month-end close accepts period_start + period_end kwargs
        so the workflow can be invoked with explicit periods."""
        from app.services.workflow_engine import _SERVICE_METHOD_REGISTRY

        _, allowed = _SERVICE_METHOD_REGISTRY[
            "month_end_close.run_close_pipeline"
        ]
        assert "dry_run" in allowed
        assert "trigger_source" in allowed
        assert "period_start" in allowed
        assert "period_end" in allowed


class TestDirectQueryRegistration:
    def test_all_three_queues_have_direct_query(self):
        from app.services.triage.engine import _DIRECT_QUERIES

        assert "month_end_close_triage" in _DIRECT_QUERIES
        assert "ar_collections_triage" in _DIRECT_QUERIES
        assert "expense_categorization_triage" in _DIRECT_QUERIES


class TestRelatedEntityBuilderRegistration:
    def test_all_three_queues_have_related_builder(self):
        from app.services.triage.ai_question import _RELATED_ENTITY_BUILDERS

        assert "month_end_close_triage" in _RELATED_ENTITY_BUILDERS
        assert "ar_collections_triage" in _RELATED_ENTITY_BUILDERS
        assert "expense_categorization_triage" in _RELATED_ENTITY_BUILDERS


class TestActionHandlerRegistration:
    def test_month_end_close_handlers_registered(self):
        from app.services.triage.action_handlers import HANDLERS

        assert "month_end_close.approve" in HANDLERS
        assert "month_end_close.reject" in HANDLERS
        assert "month_end_close.request_review" in HANDLERS

    def test_ar_collections_handlers_registered(self):
        from app.services.triage.action_handlers import HANDLERS

        assert "ar_collections.send" in HANDLERS
        assert "ar_collections.skip" in HANDLERS
        assert "ar_collections.request_review" in HANDLERS

    def test_expense_categorization_handlers_registered(self):
        from app.services.triage.action_handlers import HANDLERS

        assert "expense_categorization.approve" in HANDLERS
        assert "expense_categorization.reject" in HANDLERS
        assert "expense_categorization.request_review" in HANDLERS


class TestPlatformDefaultQueues:
    def test_all_three_queues_are_platform_defaults(self):
        from app.services.triage import list_platform_configs

        ids = {c.queue_id for c in list_platform_configs()}
        assert "month_end_close_triage" in ids
        assert "ar_collections_triage" in ids
        assert "expense_categorization_triage" in ids

    def test_month_end_close_queue_config_shape(self):
        from app.services.triage import list_platform_configs

        cfg = next(
            c for c in list_platform_configs()
            if c.queue_id == "month_end_close_triage"
        )
        assert cfg.item_entity_type == "month_end_close_job"
        action_ids = {a.action_id for a in cfg.action_palette}
        assert {"approve", "reject", "request_review"}.issubset(action_ids)
        # Approve carries the permission gate + confirmation_required.
        approve = next(
            a for a in cfg.action_palette if a.action_id == "approve"
        )
        assert approve.required_permission == "invoice.approve"
        assert approve.confirmation_required is True
        # AI question panel wires the Phase 8c prompt key.
        ai_panel = next(
            p for p in cfg.context_panels
            if p.ai_prompt_key == "triage.month_end_close_context_question"
        )
        assert ai_panel is not None

    def test_ar_collections_queue_config_shape(self):
        from app.services.triage import list_platform_configs

        cfg = next(
            c for c in list_platform_configs()
            if c.queue_id == "ar_collections_triage"
        )
        assert cfg.item_entity_type == "ar_collections_draft"
        action_ids = {a.action_id for a in cfg.action_palette}
        assert {"send", "skip", "request_review"}.issubset(action_ids)
        send = next(
            a for a in cfg.action_palette if a.action_id == "send"
        )
        assert send.required_permission == "invoice.approve"

    def test_expense_categorization_queue_config_shape(self):
        from app.services.triage import list_platform_configs

        cfg = next(
            c for c in list_platform_configs()
            if c.queue_id == "expense_categorization_triage"
        )
        assert cfg.item_entity_type == "expense_line_review"
        action_ids = {a.action_id for a in cfg.action_palette}
        assert {"approve", "reject", "request_review"}.issubset(
            action_ids
        )


class TestMigratedWorkflowSeeds:
    """Three Phase 8c seed rows are in TIER_1_WORKFLOWS with cleared
    agent_registry_key + real call_service_method steps."""

    @pytest.mark.parametrize(
        "wf_id,expected_method",
        [
            (
                "wf_sys_month_end_close",
                "month_end_close.run_close_pipeline",
            ),
            (
                "wf_sys_ar_collections",
                "ar_collections.run_collections_pipeline",
            ),
            (
                "wf_sys_expense_categorization",
                "expense_categorization.run_categorization_pipeline",
            ),
        ],
    )
    def test_migrated_seed_has_call_service_method_step(
        self, wf_id, expected_method
    ):
        from app.data.default_workflows import TIER_1_WORKFLOWS

        wf = next(w for w in TIER_1_WORKFLOWS if w["id"] == wf_id)
        # Phase 8c-beta: agent_registry_key is NOT set on the seed
        # (the 8a-backfilled column gets cleared at tenant seeding
        # time once the real steps are declared).
        assert "agent_registry_key" not in wf
        # First step should be call_service_method → expected method.
        first_step = wf["steps"][0]
        assert first_step["step_type"] == "action"
        assert (
            first_step["config"]["action_type"] == "call_service_method"
        )
        assert first_step["config"]["method_name"] == expected_method

    def test_expense_categorization_trigger_switched_to_scheduled(self):
        """Phase 8c explicit deviation: event → scheduled cron."""
        from app.data.default_workflows import TIER_1_WORKFLOWS

        wf = next(
            w for w in TIER_1_WORKFLOWS
            if w["id"] == "wf_sys_expense_categorization"
        )
        assert wf["trigger_type"] == "scheduled"
        assert wf["trigger_config"]["cron"] == "*/15 * * * *"

    def test_month_end_close_trigger_remains_manual(self):
        from app.data.default_workflows import TIER_1_WORKFLOWS

        wf = next(
            w for w in TIER_1_WORKFLOWS
            if w["id"] == "wf_sys_month_end_close"
        )
        assert wf["trigger_type"] == "manual"

    def test_ar_collections_trigger_remains_scheduled(self):
        from app.data.default_workflows import TIER_1_WORKFLOWS

        wf = next(
            w for w in TIER_1_WORKFLOWS
            if w["id"] == "wf_sys_ar_collections"
        )
        assert wf["trigger_type"] == "scheduled"
        assert wf["trigger_config"]["cron"] == "0 23 * * *"


class TestAdapterEdgeCases:
    """Basic edge-case coverage for the three new adapters."""

    def test_month_end_close_reject_requires_reason(self):
        from app.services.workflows.month_end_close_adapter import reject_close

        class _FakeUser:
            id = "u1"
            company_id = "c1"

        import pytest as _pytest

        with _pytest.raises(ValueError):
            reject_close(
                db=None, user=_FakeUser(),
                agent_job_id="anything", reason="",
            )

    def test_ar_collections_skip_requires_reason(self):
        from app.services.workflows.ar_collections_adapter import skip_customer

        class _FakeUser:
            id = "u1"
            company_id = "c1"

        import pytest as _pytest

        with _pytest.raises(ValueError):
            skip_customer(
                db=None, user=_FakeUser(),
                anomaly_id="a1", reason="",
            )

    def test_expense_reject_requires_reason(self):
        from app.services.workflows.expense_categorization_adapter import reject_line

        class _FakeUser:
            id = "u1"
            company_id = "c1"

        import pytest as _pytest

        with _pytest.raises(ValueError):
            reject_line(
                db=None, user=_FakeUser(),
                anomaly_id="a1", reason="",
            )
