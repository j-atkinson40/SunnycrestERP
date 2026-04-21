"""Workflow Arc Phase 8d.1 — unit tests for shared infrastructure
registration.

Confirms the safety_program migration is correctly wired into:
  - workflow_engine._SERVICE_METHOD_REGISTRY (1 pipeline entry)
  - triage.engine._DIRECT_QUERIES (1 direct-query builder)
  - triage.ai_question._RELATED_ENTITY_BUILDERS (1 related-entities builder)
  - triage.action_handlers.HANDLERS (3 handlers)
  - triage.platform_defaults (1 queue config WITH AI panel)
  - default_workflows.TIER_1_WORKFLOWS (migrated seed shape)
  - scheduler.py (APScheduler cron RETIRED)

Does NOT exercise side effects — parity + latency gates live in
their own test modules.
"""

from __future__ import annotations

import pytest


class TestWorkflowEngineRegistry:
    def test_pipeline_registered(self):
        from app.services.workflow_engine import _SERVICE_METHOD_REGISTRY

        assert "safety_program.run_generation_pipeline" in (
            _SERVICE_METHOD_REGISTRY
        )

    def test_allowed_kwargs(self):
        from app.services.workflow_engine import _SERVICE_METHOD_REGISTRY

        _, allowed = _SERVICE_METHOD_REGISTRY[
            "safety_program.run_generation_pipeline"
        ]
        assert "dry_run" in allowed
        assert "trigger_source" in allowed

    def test_import_path_resolves(self):
        from app.services.workflow_engine import (
            _SERVICE_METHOD_REGISTRY,
            _resolve_callable,
        )

        import_path, _ = _SERVICE_METHOD_REGISTRY[
            "safety_program.run_generation_pipeline"
        ]
        fn = _resolve_callable(import_path)
        assert callable(fn)


class TestDirectQueryRegistration:
    def test_queue_has_direct_query(self):
        from app.services.triage.engine import _DIRECT_QUERIES

        assert "safety_program_triage" in _DIRECT_QUERIES
        assert callable(_DIRECT_QUERIES["safety_program_triage"])


class TestRelatedEntityBuilderRegistration:
    def test_ai_panel_has_related_entity_builder(self):
        from app.services.triage.ai_question import (
            _RELATED_ENTITY_BUILDERS,
        )

        assert "safety_program_triage" in _RELATED_ENTITY_BUILDERS
        assert callable(
            _RELATED_ENTITY_BUILDERS["safety_program_triage"]
        )


class TestHandlerRegistration:
    def test_three_handlers_registered(self):
        from app.services.triage.action_handlers import HANDLERS

        for key in (
            "safety_program.approve",
            "safety_program.reject",
            "safety_program.request_review",
        ):
            assert key in HANDLERS, f"Missing handler: {key}"
            assert callable(HANDLERS[key])

    def test_reject_without_reason_errors(self):
        """Handler returns {'status': 'errored', ...} not raise on
        missing reason."""
        from app.services.triage.action_handlers import HANDLERS

        class _FakeUser:
            id = "u-1"
            company_id = "c-1"

        class _FakeDb:
            def query(self, *a, **k):
                raise AssertionError(
                    "Handler should error before DB access."
                )

        r = HANDLERS["safety_program.reject"]({
            "db": _FakeDb(),
            "user": _FakeUser(),
            "entity_id": "gen-1",
            "entity_type": "safety_program_generation",
            "queue_id": "safety_program_triage",
            "action_id": "reject",
            "reason": None,
            "reason_code": None,
            "note": None,
            "payload": {},
        })
        assert r["status"] == "errored"
        assert "required" in r["message"].lower()

    def test_request_review_without_note_errors(self):
        from app.services.triage.action_handlers import HANDLERS

        class _FakeUser:
            id = "u-1"
            company_id = "c-1"

        class _FakeDb:
            def query(self, *a, **k):
                raise AssertionError(
                    "Handler should error before DB access."
                )

        r = HANDLERS["safety_program.request_review"]({
            "db": _FakeDb(),
            "user": _FakeUser(),
            "entity_id": "gen-1",
            "entity_type": "safety_program_generation",
            "queue_id": "safety_program_triage",
            "action_id": "request_review",
            "reason": None,
            "reason_code": None,
            "note": "",
            "payload": {},
        })
        assert r["status"] == "errored"
        assert "note" in r["message"].lower()


def _platform_config(queue_id: str):
    import app.services.triage  # noqa: F401
    from app.services.triage.registry import _PLATFORM_CONFIGS

    return _PLATFORM_CONFIGS.get(queue_id)


class TestQueueConfig:
    def test_queue_registered(self):
        config = _platform_config("safety_program_triage")
        assert config is not None
        assert config.queue_id == "safety_program_triage"
        assert config.item_entity_type == "safety_program_generation"
        assert config.required_vertical == "manufacturing"
        assert config.required_extension is None
        assert config.source_direct_query_key == "safety_program_triage"

    def test_ai_panel_included(self):
        """Phase 8d.1 scope decision: AI panel IS included."""
        from app.services.triage.types import ContextPanelType

        config = _platform_config("safety_program_triage")
        ai_panels = [
            p for p in config.context_panels
            if p.panel_type == ContextPanelType.AI_QUESTION
        ]
        assert len(ai_panels) == 1, (
            "Phase 8d.1 approved AI panel inclusion — scope decision. "
            "If removed, update test_phase8d1_unit.py."
        )
        ai_panel = ai_panels[0]
        assert ai_panel.ai_prompt_key == (
            "triage.safety_program_context_question"
        )
        # Four suggested questions per approved spec.
        assert len(ai_panel.suggested_questions) == 4
        assert config.intelligence.ai_questions_enabled is True

    def test_related_entities_panel_included(self):
        from app.services.triage.types import ContextPanelType

        config = _platform_config("safety_program_triage")
        related_panels = [
            p for p in config.context_panels
            if p.panel_type == ContextPanelType.RELATED_ENTITIES
        ]
        assert len(related_panels) == 1

    def test_action_palette_shape(self):
        config = _platform_config("safety_program_triage")
        ids = {a.action_id for a in config.action_palette}
        assert ids == {"approve", "reject", "request_review"}
        by_id = {a.action_id: a for a in config.action_palette}
        assert by_id["approve"].required_permission == (
            "safety.trainer.approve"
        )
        assert by_id["reject"].required_permission == (
            "safety.trainer.approve"
        )
        # request_review is open (no permission gate) per approved scope.
        assert by_id["request_review"].required_permission is None
        # Required reasons correctly gated.
        assert by_id["reject"].requires_reason is True
        assert by_id["request_review"].requires_reason is True
        # Snooze NOT in the palette — flow_controls.snooze_enabled is False.
        assert config.flow_controls.snooze_enabled is False

    def test_action_handlers_resolve(self):
        from app.services.triage.action_handlers import HANDLERS

        config = _platform_config("safety_program_triage")
        for action in config.action_palette:
            assert action.handler in HANDLERS


class TestWorkflowSeedShape:
    def test_seed_uses_call_service_method(self):
        from app.data.default_workflows import TIER_1_WORKFLOWS

        seed = next(
            w for w in TIER_1_WORKFLOWS
            if w["id"] == "wf_sys_safety_program_gen"
        )
        # Post-8d.1: single step via call_service_method.
        assert len(seed["steps"]) == 1
        step = seed["steps"][0]
        assert step["config"]["action_type"] == "call_service_method"
        assert step["config"]["method_name"] == (
            "safety_program.run_generation_pipeline"
        )
        # Trigger shape preserved from pre-migration.
        assert seed["trigger_type"] == "scheduled"
        assert seed["trigger_config"]["cron"] == "0 6 1 * *"
        assert seed["trigger_config"]["timezone"] == "America/New_York"
        assert seed["vertical"] == "manufacturing"
        # agent_registry_key NOT set (never was — skipping
        # alpha→beta badge choreography as audited).
        assert "agent_registry_key" not in seed


class TestSchedulerCronRetirement:
    """The APScheduler cron entry for safety_program_generation MUST
    be retired. Double-fire risk: both the APScheduler cron and the
    workflow scheduler's `scheduled` dispatch would fire on the same
    1st-of-month tick, calling the same run_monthly_generation path
    twice. Phase 8d.1 removes the APScheduler entry — workflow
    scheduler is the single-owner firing path."""

    def test_job_registry_has_no_safety_program_entry(self):
        from app.scheduler import JOB_REGISTRY

        # The retirement comment is kept; the active JOB_REGISTRY
        # entry is gone.
        assert "safety_program_generation" not in JOB_REGISTRY


class TestAIPromptSeed:
    def test_prompt_key_exists(self):
        """After running scripts/seed_triage_phase8d1.py at least
        once, the prompt must exist as a platform-global (company_id
        IS NULL) row."""
        from app.database import SessionLocal
        from app.models.intelligence import (
            IntelligencePrompt,
            IntelligencePromptVersion,
        )

        db = SessionLocal()
        try:
            prompt = (
                db.query(IntelligencePrompt)
                .filter(
                    IntelligencePrompt.company_id.is_(None),
                    IntelligencePrompt.prompt_key == (
                        "triage.safety_program_context_question"
                    ),
                )
                .first()
            )
            if prompt is None:
                pytest.skip(
                    "Run scripts/seed_triage_phase8d1.py before this test "
                    "(one-time seed, re-run is a no-op)."
                )
            assert prompt.domain == "triage"

            # Exactly one active version.
            active = (
                db.query(IntelligencePromptVersion)
                .filter(
                    IntelligencePromptVersion.prompt_id == prompt.id,
                    IntelligencePromptVersion.status == "active",
                )
                .all()
            )
            assert len(active) == 1
            v = active[0]
            # Prompt includes the vertical-appropriate terminology block.
            assert "PRECAST CONCRETE" in v.system_prompt
            # Force-JSON for structured answer.
            assert v.force_json is True
        finally:
            db.close()
