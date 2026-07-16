"""THE PARITY PIN + the param seam (Tenant Ponder-Editor P1, commit set 1).

The engine now merges WorkflowStepParam LIVE values into step config at fire
time. THE LICENSE for that seam is parity: a workflow nobody has overridden
must execute BYTE-IDENTICALLY to the pre-seam engine. These tests pin it at
the executor boundary — the resolved config actually HANDED to each step
executor is captured (monkeypatched pass-through wrappers) and compared
byte-for-byte (json, sort_keys) against the independently-computed pre-seam
resolution of the raw step config.

Fleet proof: every workflow row in the DB has ZERO live overlays (seeds
never set current_value) — the fleet is provably untouched by the seam.

The merge rule under test (the parity-safe reading of the dispatch):
  * ONLY explicitly-set values overlay (tenant current_value first, else a
    platform-level current_value). default_value NEVER merges — the step
    config as authored is already the platform default.
  * only DECLARED params (a platform row must exist) that are is_configurable.
  * invalid stored values fail the run LOUDLY (never a silent fallback).
"""
from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.workflow import Workflow, WorkflowStep, WorkflowStepParam
from app.services import workflow_engine
from app.services.workflow_engine import resolve_variables, start_run
from app.services.workflows.step_params import (
    StepParamValidationError,
    describe_step_params,
    live_param_overlays,
    merge_overlay,
    validate_param_value,
)


@pytest.fixture
def env():
    s = SessionLocal()
    company_id = s.execute(
        sql_text("SELECT id FROM companies WHERE is_active = true LIMIT 1")
    ).scalar()
    if not company_id:
        s.close()
        pytest.skip("no active company in the dev DB")
    workflows: list[str] = []
    yield {"db": s, "company_id": company_id, "workflows": workflows}
    s.rollback()
    if workflows:
        ids = list(workflows)
        s.execute(sql_text(
            "DELETE FROM moc_witness_marker WHERE run_id IN "
            "(SELECT id FROM workflow_runs WHERE workflow_id = ANY(:ids))"
        ), {"ids": ids})
        s.execute(sql_text(
            "DELETE FROM workflow_run_steps WHERE run_id IN "
            "(SELECT id FROM workflow_runs WHERE workflow_id = ANY(:ids))"
        ), {"ids": ids})
        s.execute(sql_text("DELETE FROM workflow_runs WHERE workflow_id = ANY(:ids)"), {"ids": ids})
        s.execute(sql_text("DELETE FROM workflow_step_params WHERE workflow_id = ANY(:ids)"), {"ids": ids})
        s.execute(sql_text("DELETE FROM workflow_steps WHERE workflow_id = ANY(:ids)"), {"ids": ids})
        s.execute(sql_text("DELETE FROM workflows WHERE id = ANY(:ids)"), {"ids": ids})
        s.commit()
    s.close()


def _mk_workflow(env, *, steps: list[dict], params: list[dict] | None = None,
                 trigger_type: str = "manual") -> str:
    """A test workflow + steps + declared platform params. Returns the id."""
    db = env["db"]
    wf_id = f"wf_test_seam_{uuid.uuid4().hex[:10]}"
    db.add(Workflow(
        id=wf_id, company_id=None, name=f"Seam test {wf_id[-6:]}",
        tier=1, scope="core", trigger_type=trigger_type, is_active=True,
    ))
    for i, st in enumerate(steps, start=1):
        db.add(WorkflowStep(
            workflow_id=wf_id, step_order=i, step_key=st["step_key"],
            step_type=st.get("step_type", "action"), config=st["config"],
        ))
    for p in params or []:
        db.add(WorkflowStepParam(
            workflow_id=wf_id, company_id=None,
            step_key=p["step_key"], param_key=p["param_key"],
            label=p.get("label", p["param_key"]),
            param_type=p.get("param_type", "text"),
            default_value=p.get("default_value"),
            current_value=p.get("current_value"),
            is_configurable=p.get("is_configurable", True),
            validation=p.get("validation"),
        ))
    db.commit()
    env["workflows"].append(wf_id)
    return wf_id


def _set_override(env, wf_id: str, step_key: str, param_key: str, value,
                  *, company_id=None, param_type="text", validation=None):
    db = env["db"]
    db.add(WorkflowStepParam(
        workflow_id=wf_id, company_id=company_id or env["company_id"],
        step_key=step_key, param_key=param_key, label=param_key,
        param_type=param_type, default_value=None, current_value=value,
        is_configurable=True, validation=validation,
    ))
    db.commit()


class _Capture:
    """Pass-through wrappers around the two executor entry points, recording
    the resolved config each one is HANDED (the pin's boundary)."""

    def __init__(self, monkeypatch):
        self.action_configs: list[dict] = []
        self.condition_configs: list[dict] = []
        real_action = workflow_engine._execute_action
        real_condition = workflow_engine._evaluate_condition

        def spy_action(db, resolved_config, run, current_company, **kw):
            self.action_configs.append(resolved_config)
            return real_action(db, resolved_config, run, current_company, **kw)

        def spy_condition(resolved_config):
            self.condition_configs.append(resolved_config)
            return real_condition(resolved_config)

        monkeypatch.setattr(workflow_engine, "_execute_action", spy_action)
        monkeypatch.setattr(workflow_engine, "_evaluate_condition", spy_condition)


def _bytes(cfg) -> str:
    return json.dumps(cfg, sort_keys=True, default=str)


# ─────────────────────────────────────────────────────────────────────────────
# 1 — THE PARITY PIN (first, non-negotiable)
# ─────────────────────────────────────────────────────────────────────────────


class TestParityPin:
    def test_seeds_never_ship_live_values(self):
        """The durable fleet invariant: no seed dict declares current_value,
        and the seed writer never sets it — so a FRESH install has zero live
        overlays and the seam provably does not touch the seeded fleet.

        (Deliberately NOT a DB-emptiness scan: the moment an operator
        legitimately sets a param — which happened on dev the day this
        shipped — a live overlay is correct state, not a regression.)"""
        import inspect

        from app.data import default_workflows as dw
        from app.data import seed_workflows as sw

        declared = []
        for wf in dw.ALL_DEFAULT_WORKFLOWS:
            for p in wf.get("params", []) or []:
                if p.get("current_value") is not None:
                    declared.append((wf.get("id"), p.get("param_key")))
        assert declared == [], f"seed dicts declare live values: {declared}"
        # And the seed writer's upsert record never carries current_value.
        src = inspect.getsource(sw.seed_default_workflows)
        assert '"current_value"' not in src

    def test_unoverridden_resolved_configs_byte_identical(self, env, monkeypatch):
        """The representative sample — action + condition-branch + declared-
        params-without-values + a {ref}-resolving config. The resolved config
        handed to every executor is byte-identical to the pre-seam resolution
        of the raw step config."""
        wf_id = _mk_workflow(env, steps=[
            {"step_key": "notify", "step_type": "action",
             "config": {"action_type": "show_confirmation",
                        "message": "for {current_company.name}"}},
            {"step_key": "branch", "step_type": "condition",
             "config": {"field": "x", "operator": "==", "value": "never"}},
            {"step_key": "confirm", "step_type": "action",
             "config": {"action_type": "show_confirmation", "message": "done"}},
        ], params=[
            # DECLARED with defaults but NO explicit value anywhere — the
            # parity rule says these must NOT merge.
            {"step_key": "notify", "param_key": "notify_roles",
             "param_type": "role_multi_select", "default_value": ["admin"]},
            {"step_key": "confirm", "param_key": "include_zero_balance",
             "param_type": "toggle", "default_value": False},
        ])
        cap = _Capture(monkeypatch)
        run = start_run(env["db"], wf_id, env["company_id"], None, "test")
        assert run.status == "completed"

        db = env["db"]
        steps = {
            s.step_key: s for s in
            db.query(WorkflowStep).filter(WorkflowStep.workflow_id == wf_id)
        }
        company = db.execute(
            sql_text("SELECT name FROM companies WHERE id = :i"),
            {"i": env["company_id"]},
        ).scalar()
        # Pre-seam expectation, computed independently of the engine loop.
        expected_notify = {"action_type": "show_confirmation",
                           "message": f"for {company}"}
        expected_confirm = dict(steps["confirm"].config)
        expected_branch = dict(steps["branch"].config)

        got = {c["message"]: c for c in cap.action_configs}
        assert _bytes(got[f"for {company}"]) == _bytes(expected_notify)
        assert _bytes(got["done"]) == _bytes(expected_confirm)
        assert len(cap.condition_configs) == 1
        assert _bytes(cap.condition_configs[0]) == _bytes(expected_branch)
        # And explicitly: no declared-param key leaked into any config.
        for cfg in cap.action_configs:
            assert "notify_roles" not in cfg
            assert "include_zero_balance" not in cfg

    def test_approval_gated_pause_prompt_untouched(self, env):
        """The input (approval-gated) shape: the pause prompt handed to the UI
        is the RAW step config, params or no params."""
        wf_id = _mk_workflow(env, steps=[
            {"step_key": "gate", "step_type": "input",
             "config": {"prompt": "Review flagged statements"}},
        ], params=[
            {"step_key": "gate", "param_key": "reviewer_note",
             "param_type": "text", "default_value": "check twice"},
        ])
        run = start_run(env["db"], wf_id, env["company_id"], None, "test")
        assert run.status == "awaiting_input"
        rs = env["db"].execute(sql_text(
            "SELECT output_data FROM workflow_run_steps WHERE run_id = :r"
        ), {"r": run.id}).scalar()
        assert rs["prompt"] == {"prompt": "Review flagged statements"}

    def test_marker_witness_live_effect_unchanged(self, env):
        """The real-effect witness: a record_marker workflow (the T-2.1b
        witness row — real, loud, benign) with declared-but-unset params
        writes exactly the row it always wrote."""
        wf_id = _mk_workflow(env, steps=[
            {"step_key": "mark", "step_type": "action",
             "config": {"action_type": "record_marker",
                        "note": "param-seam parity witness"}},
        ], params=[
            {"step_key": "mark", "param_key": "dry_run",
             "param_type": "boolean", "default_value": False},
        ])
        run = start_run(env["db"], wf_id, env["company_id"], None, "test")
        assert run.status == "completed"
        rows = env["db"].execute(sql_text(
            "SELECT note FROM moc_witness_marker WHERE run_id = :r"
        ), {"r": run.id}).fetchall()
        assert [r[0] for r in rows] == ["param-seam parity witness"]

    def test_merge_overlay_identity_without_overlay(self):
        """No overlay → the SAME object back (nothing copied or reordered)."""
        cfg = {"a": 1, "b": {"c": 2}}
        assert merge_overlay(cfg, None) is cfg
        assert merge_overlay(cfg, {}) is cfg


# ─────────────────────────────────────────────────────────────────────────────
# 2 — The merge (declared-only, explicit-only, tenant-over-platform)
# ─────────────────────────────────────────────────────────────────────────────


class TestOverlayMerge:
    def _base_wf(self, env):
        return _mk_workflow(env, steps=[
            {"step_key": "send", "step_type": "action",
             "config": {"action_type": "show_confirmation", "message": "send it",
                        "reply_to": "authored@config.example"}},
        ], params=[
            {"step_key": "send", "param_key": "reply_to", "param_type": "email",
             "default_value": None},
            {"step_key": "send", "param_key": "from_name", "param_type": "text",
             "default_value": None},
        ])

    def test_tenant_override_merges_into_executor_config(self, env, monkeypatch):
        wf_id = self._base_wf(env)
        _set_override(env, wf_id, "send", "reply_to", "billing@tenant.example",
                      param_type="email")
        cap = _Capture(monkeypatch)
        run = start_run(env["db"], wf_id, env["company_id"], None, "test")
        assert run.status == "completed"
        assert cap.action_configs[0]["reply_to"] == "billing@tenant.example"
        # Un-overridden keys untouched:
        assert cap.action_configs[0]["message"] == "send it"
        assert "from_name" not in cap.action_configs[0]

    def test_platform_live_value_merges_when_no_tenant_override(self, env, monkeypatch):
        wf_id = self._base_wf(env)
        db = env["db"]
        row = (
            db.query(WorkflowStepParam)
            .filter(WorkflowStepParam.workflow_id == wf_id,
                    WorkflowStepParam.param_key == "from_name",
                    WorkflowStepParam.company_id.is_(None))
            .one()
        )
        row.current_value = "Sunnycrest Billing"
        db.commit()
        cap = _Capture(monkeypatch)
        start_run(db, wf_id, env["company_id"], None, "test")
        assert cap.action_configs[0]["from_name"] == "Sunnycrest Billing"

    def test_tenant_override_wins_over_platform_live_value(self, env, monkeypatch):
        wf_id = self._base_wf(env)
        db = env["db"]
        row = (
            db.query(WorkflowStepParam)
            .filter(WorkflowStepParam.workflow_id == wf_id,
                    WorkflowStepParam.param_key == "reply_to",
                    WorkflowStepParam.company_id.is_(None))
            .one()
        )
        row.current_value = "platform@example.com"
        db.commit()
        _set_override(env, wf_id, "send", "reply_to", "tenant@example.com",
                      param_type="email")
        cap = _Capture(monkeypatch)
        start_run(db, wf_id, env["company_id"], None, "test")
        assert cap.action_configs[0]["reply_to"] == "tenant@example.com"

    def test_undeclared_param_never_merges(self, env, monkeypatch):
        """A tenant row with NO matching platform declaration is ignored — the
        platform authors what's tweakable."""
        wf_id = self._base_wf(env)
        _set_override(env, wf_id, "send", "sneaky_key", "boo")
        cap = _Capture(monkeypatch)
        start_run(env["db"], wf_id, env["company_id"], None, "test")
        assert "sneaky_key" not in cap.action_configs[0]

    def test_non_configurable_param_never_merges(self, env, monkeypatch):
        wf_id = _mk_workflow(env, steps=[
            {"step_key": "send", "step_type": "action",
             "config": {"action_type": "show_confirmation", "message": "m"}},
        ], params=[
            {"step_key": "send", "param_key": "locked", "param_type": "text",
             "default_value": None, "is_configurable": False},
        ])
        _set_override(env, wf_id, "send", "locked", "nope")
        cap = _Capture(monkeypatch)
        start_run(env["db"], wf_id, env["company_id"], None, "test")
        assert "locked" not in cap.action_configs[0]

    def test_cleared_override_stops_merging(self, env, monkeypatch):
        wf_id = self._base_wf(env)
        _set_override(env, wf_id, "send", "reply_to", None, param_type="email")
        cap = _Capture(monkeypatch)
        start_run(env["db"], wf_id, env["company_id"], None, "test")
        # config's authored reply_to survives; the NULL override didn't clobber it
        assert cap.action_configs[0]["reply_to"] == "authored@config.example"

    def test_overlay_values_resolve_variable_refs(self, env, monkeypatch):
        """Overlay merges BEFORE resolve_variables — a {ref}-holding value
        resolves exactly like an authored config value would."""
        wf_id = self._base_wf(env)
        _set_override(env, wf_id, "send", "from_name", "{current_company.name}",
                      param_type="text")
        cap = _Capture(monkeypatch)
        start_run(env["db"], wf_id, env["company_id"], None, "test")
        company = env["db"].execute(
            sql_text("SELECT name FROM companies WHERE id = :i"),
            {"i": env["company_id"]},
        ).scalar()
        assert cap.action_configs[0]["from_name"] == company

    def test_dry_run_preview_carries_effective_value(self, env):
        """SYMMETRY: the dry-run trace records the MERGED config — the preview
        shows what the fire would do, by construction."""
        wf_id = self._base_wf(env)
        _set_override(env, wf_id, "send", "reply_to", "preview@tenant.example",
                      param_type="email")
        run = start_run(env["db"], wf_id, env["company_id"], None, "test",
                        dry_run=True)
        assert run.status == "completed"
        out = (run.output_data or {}).get("send") or {}
        assert out.get("suppressed") is True
        assert "reply_to" in (out.get("config_keys") or [])


# ─────────────────────────────────────────────────────────────────────────────
# 3 — LOUD on invalid (never a silent fallback)
# ─────────────────────────────────────────────────────────────────────────────


class TestLoudInvalid:
    def test_invalid_stored_override_fails_the_run_loudly(self, env):
        wf_id = _mk_workflow(env, steps=[
            {"step_key": "scan", "step_type": "action",
             "config": {"action_type": "show_confirmation", "message": "m"}},
        ], params=[
            {"step_key": "scan", "param_key": "warning_days_ahead",
             "param_type": "number", "default_value": 30,
             "validation": {"min": 7, "max": 90}},
        ])
        _set_override(env, wf_id, "scan", "warning_days_ahead", 3,
                      param_type="number", validation={"min": 7, "max": 90})
        run = start_run(env["db"], wf_id, env["company_id"], None, "test")
        assert run.status == "failed"
        assert "Step-param override invalid" in (run.error_message or "")
        assert "warning_days_ahead" in (run.error_message or "")
        # No step executed — the run failed BEFORE any effect.
        n = env["db"].execute(sql_text(
            "SELECT count(*) FROM workflow_run_steps WHERE run_id = :r"
        ), {"r": run.id}).scalar()
        assert n == 0

    @pytest.mark.parametrize("param_type,validation,bad", [
        ("number", {"min": 7, "max": 90}, 91),
        ("number", None, "not-a-number"),
        ("boolean", None, "yes"),
        ("toggle", None, 1),
        ("email", None, "not-an-email"),
        ("email_list", None, ["ok@x.com", "nope"]),
        ("email_list", None, "flat-string"),
        ("role_multi_select", None, ["admin", ""]),
        ("role_multi_select", None, "admin"),
        ("text", {"max_length": 3}, "toolong"),
        ("text", None, 42),
    ])
    def test_validate_param_value_rejects(self, param_type, validation, bad):
        with pytest.raises(StepParamValidationError):
            validate_param_value(param_type=param_type, validation=validation,
                                 value=bad, label="t")

    @pytest.mark.parametrize("param_type,validation,ok", [
        ("number", {"min": 7, "max": 90}, 30),
        ("boolean", None, True),
        ("toggle", None, False),
        ("email", None, "a@b.com"),
        ("email", None, "{order.fh_email}"),          # template refs are legal
        ("email_list", None, ["a@b.com", "{order.fh_email}"]),
        ("role_multi_select", None, ["admin", "office"]),
        ("text", {"max_length": 10}, "short"),
        ("text", None, ""),
    ])
    def test_validate_param_value_accepts(self, param_type, validation, ok):
        validate_param_value(param_type=param_type, validation=validation,
                             value=ok, label="t")

    def test_none_always_valid(self):
        validate_param_value(param_type="number", validation={"min": 1},
                             value=None, label="t")


# ─────────────────────────────────────────────────────────────────────────────
# 4 — One resolution path (describe == what fire time uses)
# ─────────────────────────────────────────────────────────────────────────────


class TestDescribeSymmetry:
    def test_effective_value_chain(self, env):
        wf_id = _mk_workflow(env, steps=[
            {"step_key": "send", "step_type": "action",
             "config": {"action_type": "show_confirmation", "message": "m"}},
        ], params=[
            {"step_key": "send", "param_key": "from_name", "param_type": "text",
             "default_value": "Default Co"},
        ])
        db = env["db"]

        def one():
            rows = describe_step_params(db, wf_id, env["company_id"])
            return next(r for r in rows if r["param_key"] == "from_name")

        # default only — effective is the default, NOT live
        p = one()
        assert p["effective_value"] == "Default Co" and p["live"] is False

        # platform live value
        row = (
            db.query(WorkflowStepParam)
            .filter(WorkflowStepParam.workflow_id == wf_id,
                    WorkflowStepParam.company_id.is_(None))
            .one()
        )
        row.current_value = "Platform Live"
        db.commit()
        p = one()
        assert p["effective_value"] == "Platform Live" and p["live"] is True
        assert p["platform_value"] == "Platform Live"

        # tenant override wins
        _set_override(env, wf_id, "send", "from_name", "Tenant Wins")
        p = one()
        assert p["effective_value"] == "Tenant Wins" and p["live"] is True
        assert p["current_value"] == "Tenant Wins"

        # and the fire-time map agrees exactly
        overlays = live_param_overlays(db, wf_id, env["company_id"])
        assert overlays == {"send": {"from_name": "Tenant Wins"}}
