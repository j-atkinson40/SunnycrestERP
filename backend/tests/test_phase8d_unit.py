"""Workflow Arc Phase 8d — unit tests for shared infrastructure
registration.

Confirms the two new migrations are correctly wired into:
  - workflow_engine._SERVICE_METHOD_REGISTRY (2 pipeline entries)
  - triage.engine._DIRECT_QUERIES (2 direct-query builders)
  - triage.action_handlers.HANDLERS (6 handlers)
  - triage.platform_defaults (2 queue configs)
  - default_workflows.FUNERAL_HOME_WORKFLOWS + TIER_1_WORKFLOWS (seeds)
  - alembic migration chain (r38 → r39 → r40)

Does NOT exercise side effects — parity and queue-latency gates
live in their own test modules (`test_aftercare_migration_parity`,
`test_catalog_fetch_migration_parity`, `test_phase8d_triage_latency`).
"""

from __future__ import annotations

import pytest


# ── Workflow engine registration ────────────────────────────────────


class TestWorkflowEngineRegistry:
    def test_both_pipelines_registered(self):
        from app.services.workflow_engine import _SERVICE_METHOD_REGISTRY

        keys = set(_SERVICE_METHOD_REGISTRY.keys())
        assert "aftercare.run_pipeline" in keys
        assert "catalog_fetch.run_staged_fetch" in keys

    def test_aftercare_allowed_kwargs(self):
        from app.services.workflow_engine import _SERVICE_METHOD_REGISTRY

        _, allowed = _SERVICE_METHOD_REGISTRY["aftercare.run_pipeline"]
        assert "dry_run" in allowed
        assert "trigger_source" in allowed

    def test_catalog_fetch_allowed_kwargs(self):
        from app.services.workflow_engine import _SERVICE_METHOD_REGISTRY

        _, allowed = _SERVICE_METHOD_REGISTRY[
            "catalog_fetch.run_staged_fetch"
        ]
        assert "dry_run" in allowed
        assert "trigger_source" in allowed

    def test_import_paths_resolve(self):
        """Safelist entries must point at importable callables."""
        from app.services.workflow_engine import (
            _SERVICE_METHOD_REGISTRY,
            _resolve_callable,
        )

        for key in (
            "aftercare.run_pipeline",
            "catalog_fetch.run_staged_fetch",
        ):
            import_path, _ = _SERVICE_METHOD_REGISTRY[key]
            fn = _resolve_callable(import_path)
            assert callable(fn), f"{key} → {import_path} is not callable"


# ── Triage engine direct-query registration ─────────────────────────


class TestDirectQueryRegistration:
    def test_both_queues_have_direct_query(self):
        from app.services.triage.engine import _DIRECT_QUERIES

        assert "aftercare_triage" in _DIRECT_QUERIES
        assert "catalog_fetch_triage" in _DIRECT_QUERIES

    def test_direct_queries_are_callable(self):
        from app.services.triage.engine import _DIRECT_QUERIES

        assert callable(_DIRECT_QUERIES["aftercare_triage"])
        assert callable(_DIRECT_QUERIES["catalog_fetch_triage"])


# ── Handler registration ─────────────────────────────────────────────


class TestHandlerRegistration:
    def test_aftercare_handlers_registered(self):
        from app.services.triage.action_handlers import HANDLERS

        for key in (
            "aftercare.send",
            "aftercare.skip",
            "aftercare.request_review",
        ):
            assert key in HANDLERS, f"Missing handler: {key}"
            assert callable(HANDLERS[key])

    def test_catalog_fetch_handlers_registered(self):
        from app.services.triage.action_handlers import HANDLERS

        for key in (
            "catalog_fetch.approve",
            "catalog_fetch.reject",
            "catalog_fetch.request_review",
        ):
            assert key in HANDLERS, f"Missing handler: {key}"
            assert callable(HANDLERS[key])

    def test_handlers_return_status_on_missing_inputs(self):
        """Handlers should return {'status': 'errored', ...} rather
        than raise when given a malformed ctx (e.g. missing reason)."""
        from app.services.triage.action_handlers import HANDLERS

        class _FakeUser:
            id = "u-1"
            company_id = "c-1"

        class _FakeDb:
            def query(self, *a, **k):
                raise AssertionError(
                    "Handler should error on missing inputs before "
                    "touching the database."
                )

        # aftercare.skip requires `reason`.
        r = HANDLERS["aftercare.skip"]({
            "db": _FakeDb(),
            "user": _FakeUser(),
            "entity_id": "anom-1",
            "entity_type": "agent_anomaly",
            "queue_id": "aftercare_triage",
            "action_id": "skip",
            "reason": None,
            "reason_code": None,
            "note": None,
            "payload": {},
        })
        assert r["status"] == "errored"
        assert "reason" in r["message"].lower()

        # catalog_fetch.reject requires `reason`.
        r = HANDLERS["catalog_fetch.reject"]({
            "db": _FakeDb(),
            "user": _FakeUser(),
            "entity_id": "log-1",
            "entity_type": "urn_catalog_sync_log",
            "queue_id": "catalog_fetch_triage",
            "action_id": "reject",
            "reason": "",
            "reason_code": None,
            "note": None,
            "payload": {},
        })
        assert r["status"] == "errored"
        assert "reason" in r["message"].lower()


# ── Platform-default queue configs ───────────────────────────────────


def _platform_config(queue_id: str):
    """Read a platform-default config directly from the registry
    singleton without needing a DB. Platform configs are tenant-
    independent; tenant overrides are the only thing that needs a
    DB session + company_id."""
    import app.services.triage  # noqa: F401 — side effect: load platform_defaults
    from app.services.triage.registry import _PLATFORM_CONFIGS

    return _PLATFORM_CONFIGS.get(queue_id)


class TestQueueConfigs:
    def test_aftercare_queue_registered(self):
        config = _platform_config("aftercare_triage")
        assert config is not None
        assert config.queue_id == "aftercare_triage"
        assert config.item_entity_type == "fh_aftercare_case"
        assert config.required_vertical == "funeral_home"
        assert config.source_direct_query_key == "aftercare_triage"

    def test_catalog_fetch_queue_registered(self):
        config = _platform_config("catalog_fetch_triage")
        assert config is not None
        assert config.queue_id == "catalog_fetch_triage"
        assert config.item_entity_type == "catalog_sync_log"
        assert config.required_vertical == "manufacturing"
        assert config.required_extension == "urn_sales"

    def test_no_ai_question_panels_on_phase8d_queues(self):
        """User-approved scope decision: no AI question panels on
        audit/retry workspaces (aftercare + catalog_fetch). If a
        future phase wants to add one, this invariant must be
        explicitly lifted."""
        from app.services.triage.types import ContextPanelType

        for queue_id in ("aftercare_triage", "catalog_fetch_triage"):
            config = _platform_config(queue_id)
            assert config is not None
            for panel in config.context_panels:
                assert panel.panel_type != ContextPanelType.AI_QUESTION, (
                    f"{queue_id} has an AI question panel — "
                    "violates Phase 8d scope decision. If this is "
                    "intentional, update test_phase8d_unit.py to "
                    "document the change."
                )
            assert config.intelligence.ai_questions_enabled is False, (
                f"{queue_id} has ai_questions_enabled=True — "
                "violates Phase 8d scope decision."
            )

    def test_queue_action_handlers_resolve(self):
        """Every ActionConfig.handler on a Phase 8d queue must point
        to a registered HANDLERS entry or the generic 'skip' /
        'escalate' entries."""
        from app.services.triage.action_handlers import HANDLERS

        for queue_id in ("aftercare_triage", "catalog_fetch_triage"):
            config = _platform_config(queue_id)
            for action in config.action_palette:
                assert action.handler in HANDLERS, (
                    f"{queue_id}/{action.action_id} → "
                    f"handler {action.handler!r} not in HANDLERS"
                )


# ── Workflow seed shape ──────────────────────────────────────────────


class TestWorkflowSeedShape:
    def test_aftercare_seed_uses_call_service_method(self):
        from app.data.default_workflows import FUNERAL_HOME_WORKFLOWS

        seed = next(
            w for w in FUNERAL_HOME_WORKFLOWS if w["id"] == "wf_fh_aftercare_7day"
        )
        # Single step that dispatches via call_service_method —
        # legacy send_email + log_vault_item step types retired.
        assert len(seed["steps"]) == 1
        step = seed["steps"][0]
        assert step["config"]["action_type"] == "call_service_method"
        assert step["config"]["method_name"] == "aftercare.run_pipeline"
        # Trigger type unchanged — still time_after_event 7 days
        # after service_date at 10:00 local.
        assert seed["trigger_type"] == "time_after_event"
        assert seed["trigger_config"]["offset_days"] == 7

    def test_catalog_fetch_seed_uses_call_service_method(self):
        from app.data.default_workflows import TIER_1_WORKFLOWS

        seed = next(
            w for w in TIER_1_WORKFLOWS if w["id"] == "wf_sys_catalog_fetch"
        )
        assert len(seed["steps"]) == 1
        step = seed["steps"][0]
        assert step["config"]["action_type"] == "call_service_method"
        assert (
            step["config"]["method_name"]
            == "catalog_fetch.run_staged_fetch"
        )
        assert seed["vertical"] == "manufacturing"
        assert seed["trigger_type"] == "scheduled"

    def test_no_system_job_action_type_in_phase8d_seeds(self):
        """Post-8d, neither wf_fh_aftercare_7day nor
        wf_sys_catalog_fetch should still reference the bare
        `system_job` / `send_email` / `log_vault_item` action
        types — those were replaced with call_service_method."""
        from app.data.default_workflows import (
            TIER_1_WORKFLOWS,
            FUNERAL_HOME_WORKFLOWS,
        )

        for seed_list in (TIER_1_WORKFLOWS, FUNERAL_HOME_WORKFLOWS):
            for seed in seed_list:
                if seed["id"] not in (
                    "wf_fh_aftercare_7day",
                    "wf_sys_catalog_fetch",
                ):
                    continue
                for step in seed["steps"]:
                    assert step["config"]["action_type"] == (
                        "call_service_method"
                    ), (
                        f"{seed['id']}/{step['step_key']} uses "
                        f"{step['config']['action_type']!r}; expected "
                        "'call_service_method'"
                    )


# ── Migration chain ──────────────────────────────────────────────────


def _load_migration_module(rev_id: str):
    """Alembic versions aren't on sys.path — load by file path."""
    import importlib.util
    from pathlib import Path

    here = Path(__file__).resolve().parent.parent
    path = here / "alembic" / "versions" / f"{rev_id}.py"
    spec = importlib.util.spec_from_file_location(
        f"_phase8d_migrations.{rev_id}", path
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestMigrationChain:
    def test_r38_r39_r40_are_importable(self):
        """Migration modules exist and expose upgrade/downgrade +
        correct revision metadata."""
        for rev_id, down_rev in (
            ("r38_fix_vertical_scope_backfill", "r37_approval_gate_email_template"),
            ("r39_catalog_publication_state", "r38_fix_vertical_scope_backfill"),
            ("r40_aftercare_email_template", "r39_catalog_publication_state"),
        ):
            mod = _load_migration_module(rev_id)
            assert mod.revision == rev_id
            assert mod.down_revision == down_rev
            assert callable(mod.upgrade)
            assert callable(mod.downgrade)

    def test_r38_target_list_matches_audit(self):
        """The 10 known-misclassified workflow IDs must be the
        canonical target list. Drift between the migration's target
        and the regression test's target is itself a bug."""
        mod = _load_migration_module("r38_fix_vertical_scope_backfill")
        from tests.test_r38_scope_backfill_fix import (
            EXPECTED_VERTICAL_WORKFLOW_IDS,
        )

        assert set(mod.MISCLASSIFIED_VERTICAL_WORKFLOWS) == (
            EXPECTED_VERTICAL_WORKFLOW_IDS
        )


# ── Email template seed ──────────────────────────────────────────────


class TestAftercareTemplateSeed:
    def test_aftercare_seed_defined(self):
        from app.services.documents._template_seeds import _aftercare_seeds

        seeds = _aftercare_seeds()
        assert len(seeds) == 1
        seed = seeds[0]
        assert seed["template_key"] == "email.fh_aftercare_7day"
        assert seed["document_type"] == "email"
        assert seed["output_format"] == "html"
        assert "family_surname" in seed["body_template"]
        assert "family_surname" in seed["subject_template"]
