"""Workflow Engine — executes multi-step workflows with variable resolution.

The engine processes steps sequentially, pauses for input steps (returning
an awaiting_input status), resumes via advance_run, executes action steps,
and evaluates conditions to branch.

Variable syntax: {input.step_key.field} {output.step_key.field}
                 {current_user.id} {current_company.name}
                 {current_record.field}
"""

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.user import User
from app.models.workflow import (
    Workflow,
    WorkflowEnrollment,
    WorkflowRun,
    WorkflowRunStep,
    WorkflowStep,
)


VARIABLE_PATTERN = re.compile(r"\{([^}]+)\}")


def _get_path(obj: Any, path: str) -> Any:
    """Walk a dotted path into a nested dict/object. Returns None if missing."""
    cur = obj
    for part in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = getattr(cur, part, None)
    return cur


def resolve_variables(
    template: Any,
    run: WorkflowRun | None,
    step_outputs: dict,
    current_user: User | None = None,
    current_company: Company | None = None,
) -> Any:
    """Replace {var.path} references in strings or dicts with real values.

    Handles strings, dicts, and lists recursively. Non-string leaves are
    returned unchanged. When the entire string is a single {ref}, the
    resolved value is returned as its original type (not stringified).
    """
    if isinstance(template, dict):
        return {k: resolve_variables(v, run, step_outputs, current_user, current_company) for k, v in template.items()}
    if isinstance(template, list):
        return [resolve_variables(v, run, step_outputs, current_user, current_company) for v in template]
    if not isinstance(template, str):
        return template

    def _resolve_ref(ref: str) -> Any:
        ref = ref.strip()
        if ref.startswith("input."):
            # {input.step_key} or {input.step_key.field}
            parts = ref[len("input."):].split(".", 1)
            step_key = parts[0]
            rest = parts[1] if len(parts) > 1 else None
            inputs = (run.input_data or {}) if run else {}
            val = inputs.get(step_key)
            if rest and isinstance(val, dict):
                return _get_path(val, rest)
            return val
        if ref.startswith("output."):
            # {output.step_key.field}
            parts = ref[len("output."):].split(".", 1)
            step_key = parts[0]
            rest = parts[1] if len(parts) > 1 else None
            val = step_outputs.get(step_key)
            if rest and val is not None:
                return _get_path(val, rest)
            return val
        if ref.startswith("current_user."):
            return _get_path(current_user, ref[len("current_user."):])
        if ref.startswith("current_company."):
            return _get_path(current_company, ref[len("current_company."):])
        if ref.startswith("current_record."):
            rec = (run.trigger_context or {}).get("record") if run else None
            return _get_path(rec, ref[len("current_record."):])
        return None

    # If the entire template IS a single reference, return the resolved
    # value in its native type (useful for {input.ask_case.id} → str).
    m = re.fullmatch(r"\{([^}]+)\}", template)
    if m:
        return _resolve_ref(m.group(1))

    # Otherwise inline-substitute each ref as a string.
    def _sub(match: re.Match) -> str:
        val = _resolve_ref(match.group(1))
        return "" if val is None else str(val)

    return VARIABLE_PATTERN.sub(_sub, template)


# ─────────────────────────────────────────────────────────────────────
# Workflow lookup
# ─────────────────────────────────────────────────────────────────────

def get_active_workflows_for_tenant(
    db: Session,
    company_id: str,
    vertical: str | None = None,
    trigger_type: str | None = None,
) -> list[Workflow]:
    """Return active workflows available to a tenant.

    Includes platform workflows (company_id IS NULL) matching vertical AND
    tenant-specific workflows (company_id = this tenant). Respects
    workflow_enrollments overrides for tier-2/3 workflows.
    """
    q = db.query(Workflow).filter(
        Workflow.is_active == True,  # noqa: E712
        Workflow.is_coming_soon == False,  # noqa: E712 — placeholders aren't runnable
        or_(
            Workflow.company_id.is_(None),
            Workflow.company_id == company_id,
        ),
    )
    if vertical:
        q = q.filter(or_(Workflow.vertical == vertical, Workflow.vertical.is_(None)))
    if trigger_type:
        q = q.filter(Workflow.trigger_type == trigger_type)

    workflows = q.all()

    # Apply enrollment overrides — tier 3 requires an active enrollment for this tenant
    enrollments = {
        e.workflow_id: e
        for e in db.query(WorkflowEnrollment).filter(WorkflowEnrollment.company_id == company_id).all()
    }

    result = []
    for w in workflows:
        enrollment = enrollments.get(w.id)
        if w.tier == 3:
            # Must have active enrollment
            if not enrollment or not enrollment.is_active:
                continue
        elif w.tier == 2 and enrollment and not enrollment.is_active:
            # Default-on but tenant opted out
            continue
        result.append(w)
    return result


def get_command_bar_workflows(
    db: Session,
    company_id: str,
    vertical: str | None,
    user_role: str | None,
    query: str,
) -> list[dict]:
    """Return workflow matches for the command bar, formatted + sorted."""
    q = (query or "").strip().lower()
    workflows = get_active_workflows_for_tenant(
        db, company_id, vertical=vertical, trigger_type="manual"
    )

    matches = []
    for w in workflows:
        keywords = (w.keywords or []) if isinstance(w.keywords, list) else []
        if not keywords:
            continue
        # Match score — keyword exact wins, then substring, then token overlap
        best = 0
        if q:
            for kw in keywords:
                kl = kw.lower()
                if kl == q:
                    best = max(best, 100)
                elif kl.startswith(q) or q.startswith(kl):
                    best = max(best, 80)
                elif q in kl or kl in q:
                    best = max(best, 60)
                else:
                    # Token overlap
                    q_tokens = set(q.split())
                    kw_tokens = set(kl.split())
                    overlap = len(q_tokens & kw_tokens)
                    if overlap and q_tokens:
                        best = max(best, int((overlap / len(q_tokens)) * 50))
            if best < 1:
                continue
        else:
            best = 1  # surface all when no query

        # Load first step for preview. For workflows that use the
        # natural-language overlay, show a descriptive hint rather
        # than "Ask: Which customer?" — the form prompt doesn't
        # reflect the actual input experience.
        first_preview = ""
        overlay_cfg = (w.overlay_config or {}) if hasattr(w, "overlay_config") else {}
        if isinstance(overlay_cfg, dict) and overlay_cfg.get("input_style") == "natural_language":
            first_preview = (w.description or "").strip()
            if len(first_preview) > 120:
                first_preview = first_preview[:120].rsplit(" ", 1)[0] + "…"
        else:
            first_step = (
                db.query(WorkflowStep)
                .filter(WorkflowStep.workflow_id == w.id)
                .order_by(WorkflowStep.step_order)
                .first()
            )
            if first_step and first_step.step_type == "input":
                cfg = first_step.config or {}
                first_preview = f"Ask: {cfg.get('prompt', '')}"
            elif first_step:
                first_preview = f"{first_step.step_type.title()}: {first_step.step_key}"

        matches.append({
            "type": "WORKFLOW",
            "id": f"wf_{w.id}",
            "workflow_id": w.id,
            "title": w.name,
            "subtitle": w.description or "",
            "icon": w.icon or "zap",
            "keywords": keywords,
            "priority": w.command_bar_priority,
            "first_step_preview": first_preview,
            "match_score": best,
        })

    # Sort: match score desc, then priority desc
    matches.sort(key=lambda m: (-m["match_score"], -m["priority"]))
    return matches


# ─────────────────────────────────────────────────────────────────────
# Run execution
# ─────────────────────────────────────────────────────────────────────

def _get_steps(db: Session, workflow_id: str) -> list[WorkflowStep]:
    return (
        db.query(WorkflowStep)
        .filter(WorkflowStep.workflow_id == workflow_id)
        .order_by(WorkflowStep.step_order)
        .all()
    )


def _step_outputs_by_key(db: Session, run: WorkflowRun) -> dict:
    rows = db.query(WorkflowRunStep).filter(WorkflowRunStep.run_id == run.id).all()
    return {r.step_key: r.output_data for r in rows if r.output_data is not None}


def start_run(
    db: Session,
    workflow_id: str,
    company_id: str,
    triggered_by_user_id: str | None,
    trigger_source: str,
    trigger_context: dict | None = None,
    initial_inputs: dict | None = None,
) -> WorkflowRun:
    """Create a run and execute steps until it pauses for input or completes."""
    run = WorkflowRun(
        workflow_id=workflow_id,
        company_id=company_id,
        triggered_by_user_id=triggered_by_user_id,
        trigger_source=trigger_source,
        trigger_context=trigger_context,
        status="running",
        input_data=dict(initial_inputs or {}),
        output_data={},
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    _drive_run(db, run)
    return run


def advance_run(db: Session, run_id: str, step_input: dict) -> WorkflowRun:
    """Provide input for a paused run and continue.

    Handles both ``awaiting_input`` (standard input step) and
    ``awaiting_approval`` (Playwright approval gate).
    """
    run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
    if not run:
        raise ValueError("Run not found")
    if run.status not in ("awaiting_input", "awaiting_approval"):
        raise ValueError(f"Run is not awaiting input or approval (status={run.status})")

    # Save the input / approval decision
    inputs = dict(run.input_data or {})
    for k, v in (step_input or {}).items():
        inputs[k] = v
    run.input_data = inputs

    if run.status == "awaiting_input":
        # Mark the currently-paused input step completed
        if run.current_step_id:
            rs = (
                db.query(WorkflowRunStep)
                .filter(
                    WorkflowRunStep.run_id == run.id,
                    WorkflowRunStep.step_id == run.current_step_id,
                )
                .first()
            )
            if rs:
                rs.status = "completed"
                rs.output_data = step_input
        run.status = "running"

    elif run.status == "awaiting_approval":
        # For approval, we need to re-run the current playwright step with
        # the approval flag now set in input_data. Roll current_step_id back
        # to the previous step so _drive_run re-enters the playwright step.
        steps = _get_steps(db, run.workflow_id)
        current_idx = next(
            (i for i, s in enumerate(steps) if s.id == run.current_step_id), -1
        )
        if current_idx > 0:
            run.current_step_id = steps[current_idx - 1].id
        else:
            run.current_step_id = None  # Re-start from beginning
        run.status = "running"

    db.commit()
    db.refresh(run)
    _drive_run(db, run)
    return run


def _drive_run(db: Session, run: WorkflowRun) -> None:
    """Execute steps from current_step_id onwards until pause or completion."""
    workflow = db.query(Workflow).filter(Workflow.id == run.workflow_id).first()
    if not workflow:
        _fail_run(db, run, "Workflow not found")
        return

    steps = _get_steps(db, run.workflow_id)
    if not steps:
        _complete_run(db, run)
        return

    # Determine the starting step
    if run.current_step_id:
        # Already completed the paused step; move to its next
        current = next((s for s in steps if s.id == run.current_step_id), None)
        if current:
            next_id = current.next_step_id
            current = next((s for s in steps if s.id == next_id), None) if next_id else _next_by_order(steps, current)
        else:
            current = steps[0]
    else:
        current = steps[0]

    # Current user + company context for variable resolution
    current_user = db.query(User).filter(User.id == run.triggered_by_user_id).first() if run.triggered_by_user_id else None
    current_company = db.query(Company).filter(Company.id == run.company_id).first()

    max_iterations = 50
    iteration = 0
    while current and iteration < max_iterations:
        iteration += 1
        outputs_by_key = _step_outputs_by_key(db, run)
        result = _execute_step(
            db, run, current, outputs_by_key, current_user, current_company
        )
        if result.get("pause"):
            # Awaiting input — record paused step, return
            run.current_step_id = current.id
            run.status = "awaiting_input"
            db.commit()
            return

        output = result.get("output", {})
        if isinstance(output, dict) and output.get("type") == "awaiting_approval":
            # Playwright step requires human approval before running
            run.current_step_id = current.id
            run.status = "awaiting_approval"
            # Store the approval metadata so the UI can render the prompt
            run.output_data = {**(run.output_data or {}), current.step_key: output}
            db.commit()
            return

        # Step completed; figure out next step
        next_step = _resolve_next_step(steps, current, result)
        if next_step is None:
            # End of workflow
            run.current_step_id = current.id
            _complete_run(db, run)
            return
        current = next_step

    # Safety
    _fail_run(db, run, f"Workflow exceeded {max_iterations} steps — possible loop")


def _next_by_order(steps: list[WorkflowStep], current: WorkflowStep) -> WorkflowStep | None:
    idx = next((i for i, s in enumerate(steps) if s.id == current.id), -1)
    return steps[idx + 1] if 0 <= idx < len(steps) - 1 else None


def _resolve_next_step(
    steps: list[WorkflowStep], current: WorkflowStep, result: dict
) -> WorkflowStep | None:
    # Condition steps use condition_true/false_step_id
    if current.step_type == "condition":
        target_id = (
            current.condition_true_step_id if result.get("condition_result")
            else current.condition_false_step_id
        )
        if target_id:
            return next((s for s in steps if s.id == target_id), None)
        return _next_by_order(steps, current)

    if current.next_step_id:
        return next((s for s in steps if s.id == current.next_step_id), None)
    return _next_by_order(steps, current)


def _execute_step(
    db: Session,
    run: WorkflowRun,
    step: WorkflowStep,
    outputs_by_key: dict,
    current_user: User | None,
    current_company: Company | None,
) -> dict:
    """Execute one step. Returns dict with pause / output / condition_result."""
    # Record the run step
    rs = WorkflowRunStep(
        run_id=run.id,
        step_id=step.id,
        step_key=step.step_key,
        status="running",
    )
    db.add(rs)
    db.commit()
    db.refresh(rs)

    try:
        if step.step_type == "input":
            # Pause for input. Config describes what to ask.
            # Don't mark step completed yet — advance_run will do that.
            rs.status = "pending"
            rs.output_data = {"awaiting_input": True, "prompt": step.config}
            db.commit()
            return {"pause": True, "prompt": step.config}

        # Resolve variables in the step config
        resolved_config = resolve_variables(
            step.config, run, outputs_by_key, current_user, current_company
        )

        if step.step_type == "action" or step.step_type == "output" or step.step_type == "notification":
            output = _execute_action(db, resolved_config, run, current_company)
        elif step.step_type == "condition":
            output = _evaluate_condition(resolved_config)
        elif step.step_type == "ai_prompt":
            # Phase 3d — invoke a managed intelligence prompt as a step
            output = _execute_ai_prompt(db, resolved_config, run, rs.id, step.step_key)
        elif step.step_type == "send_document":
            # Phase D-7 — dispatch through the delivery abstraction
            output = _execute_send_document(db, resolved_config, run, rs.id)
        else:
            output = {"status": "unknown_step_type", "step_type": step.step_type}

        # Store output back on the run
        outputs_by_key[step.step_key] = output
        run.output_data = {**(run.output_data or {}), step.step_key: output}

        rs.status = "completed"
        rs.output_data = output
        db.commit()

        return {"output": output, "condition_result": output.get("condition_result")}
    except Exception as e:
        rs.status = "failed"
        rs.error_message = str(e)[:500]
        db.commit()
        _fail_run(db, run, f"Step {step.step_key} failed: {e}")
        return {"error": str(e)}


def _execute_action(
    db: Session,
    resolved_config: dict,
    run: WorkflowRun,
    current_company: Company | None,
) -> dict:
    """Route an action step by action_type."""
    action_type = resolved_config.get("action_type")

    if action_type == "create_record":
        return _handle_create_record(db, resolved_config, run)
    if action_type == "update_record":
        return _handle_update_record(db, resolved_config, run)
    if action_type == "open_slide_over":
        # Frontend handles — just pass through the config
        return {
            "type": "open_slide_over",
            "record_type": resolved_config.get("record_type"),
            "record_id": resolved_config.get("record_id"),
            "mode": resolved_config.get("mode", "edit"),
        }
    if action_type == "show_confirmation":
        return {"type": "confirmation", "message": resolved_config.get("message", "Done")}
    if action_type == "send_notification":
        return _handle_send_notification(db, resolved_config, run)
    if action_type == "send_email":
        return {"type": "email_queued", "to": resolved_config.get("to"), "subject": resolved_config.get("subject")}
    if action_type == "log_vault_item":
        return _handle_log_vault_item(db, resolved_config, run)
    if action_type == "generate_document":
        return _handle_generate_document(db, resolved_config, run)
    if action_type == "playwright_action":
        return _handle_playwright_action(db, resolved_config, run)
    if action_type == "call_service_method":
        # Phase 8b — parity adapter dispatch. Calls a whitelisted
        # Python function by name + kwargs. The whitelist lives in
        # `_SERVICE_METHOD_REGISTRY` below and is the explicit
        # surface workflow definitions can invoke. This is how
        # agent migrations (8b-8f) plug real service logic into
        # the workflow engine without duplicating code.
        return _handle_call_service_method(db, resolved_config, run, current_company)

    return {"status": "unknown_action_type", "action_type": action_type}


def _handle_playwright_action(db: Session, config: dict, run: WorkflowRun) -> dict:
    """Execute a Playwright automation script as a workflow step.

    Config keys:
      script_name       : str  — key from PLAYWRIGHT_SCRIPTS registry
      input_mapping     : dict — {script_input_key: variable_ref_or_literal}
      output_mapping    : dict — {local_key: script_output_key}  (optional)
      requires_approval : bool — pause for human approval before running
      approval_prompt   : str  — message shown in the approval UI
      approval_threshold: int  — 0=always-approve, 1=always-require (default 1)

    Returns the script outputs merged with execution metadata.
    """
    import asyncio
    import json
    import logging
    from datetime import datetime, timezone

    logger = logging.getLogger(__name__)

    script_name = config.get("script_name", "")
    input_mapping = config.get("input_mapping") or {}
    output_mapping = config.get("output_mapping") or {}
    requires_approval = config.get("requires_approval", False)
    approval_prompt = config.get("approval_prompt", f"Approve automated action: {script_name}")

    # ── Approval gate ─────────────────────────────────────────────────
    if requires_approval:
        # Check if this step already has an approval stored on the run
        approval_key = f"_approval_{run.current_step_id or script_name}"
        already_approved = (run.input_data or {}).get(approval_key)
        if not already_approved:
            return {
                "type": "awaiting_approval",
                "script_name": script_name,
                "approval_prompt": approval_prompt,
                "approval_key": approval_key,
            }

    # ── Resolve inputs ─────────────────────────────────────────────────
    resolved_inputs = dict(input_mapping)  # already resolved by resolve_variables call above

    # ── Get script ─────────────────────────────────────────────────────
    from app.services.playwright_scripts import get_script
    script = get_script(script_name)
    if script is None:
        return {
            "type": "playwright_error",
            "error": f"Unknown Playwright script: '{script_name}'. "
                     f"Check Settings → External Accounts for available scripts.",
            "script_name": script_name,
        }

    # ── Get credentials ─────────────────────────────────────────────────
    from app.services import credential_service
    credentials = credential_service.get_credentials(
        db, company_id=run.company_id, service_key=script.service_key
    )
    if credentials is None:
        return {
            "type": "playwright_error",
            "error": f"No credentials configured for '{script.service_key}'. "
                     f"Go to Settings → External Accounts to connect your account.",
            "script_name": script_name,
            "service_key": script.service_key,
        }

    # ── Create execution log entry ────────────────────────────────────
    from app.models.playwright_execution_log import PlaywrightExecutionLog
    log_entry = PlaywrightExecutionLog(
        id=str(uuid.uuid4()),
        workflow_run_id=run.id,
        company_id=run.company_id,
        script_name=script_name,
        service_key=script.service_key,
        status="running",
        input_data=resolved_inputs,  # safe — no credentials here
        started_at=datetime.now(timezone.utc),
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)

    # ── Execute script in isolated event loop ─────────────────────────
    try:
        loop = asyncio.new_event_loop()
        try:
            script_result = loop.run_until_complete(
                script.execute(resolved_inputs, credentials)
            )
        finally:
            loop.close()

        # ── Map outputs ──────────────────────────────────────────────
        final_output: dict = {}
        for local_key, script_key in output_mapping.items():
            final_output[local_key] = script_result.get(script_key)
        # Also include all script outputs directly
        final_output.update(script_result)
        final_output["type"] = "playwright_success"
        final_output["script_name"] = script_name

        # Update log
        log_entry.status = "completed"
        log_entry.output_data = final_output
        log_entry.completed_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(
            "Playwright script %s completed for run %s (company %s)",
            script_name, run.id, run.company_id,
        )
        return final_output

    except Exception as e:
        from app.services.playwright_scripts.base import PlaywrightScriptError
        screenshot_path = getattr(e, "screenshot_path", None)
        error_msg = str(e)[:500]
        step_hint = getattr(e, "step", None)

        log_entry.status = "failed"
        log_entry.error_message = error_msg
        log_entry.screenshot_path = screenshot_path
        log_entry.completed_at = datetime.now(timezone.utc)
        db.commit()

        logger.error(
            "Playwright script %s failed at step=%s for run %s: %s",
            script_name, step_hint, run.id, error_msg,
        )
        return {
            "type": "playwright_error",
            "error": error_msg,
            "script_name": script_name,
            "step": step_hint,
            "screenshot_path": screenshot_path,
        }


# ── Phase 8b — `call_service_method` action subtype ─────────────────
#
# Parity adapter dispatch. Calls a whitelisted importable Python
# callable by `method_name` + kwargs. The registry is explicit:
# workflow definitions cannot arbitrarily invoke any function; they
# can only call methods this registry exposes.
#
# Adding a new adapter method (for 8c–8f migrations):
#   1. Write the thin adapter function under
#      `app/services/workflows/{agent_name}_adapter.py`.
#   2. Register it in `_SERVICE_METHOD_REGISTRY` below with its
#      allowed kwarg keys.
#   3. Reference it from the workflow definition's step config as
#      `{"action_type": "call_service_method",
#        "method_name": "cash_receipts.run_match_pipeline",
#        "kwargs": {...}}`.
#
# The workflow engine auto-injects `db`, `company_id`, and
# `triggered_by_user_id` kwargs — workflow configs don't need to
# spell those out.


# Map: "dotted.method.name" → (importable callable, allowed kwarg keys).
# Allowed kwargs are a safelist — any kwargs beyond those get dropped
# from the call before dispatch to prevent privilege escalation via
# crafted step configs.
_SERVICE_METHOD_REGISTRY: dict[str, tuple[str, tuple[str, ...]]] = {
    # Cash Receipts Matching (Phase 8b)
    "cash_receipts.run_match_pipeline": (
        "app.services.workflows.cash_receipts_adapter:run_match_pipeline",
        ("dry_run", "trigger_source"),
    ),
    # Month-End Close (Phase 8c) — FULL approval with period lock
    "month_end_close.run_close_pipeline": (
        "app.services.workflows.month_end_close_adapter:run_close_pipeline",
        ("dry_run", "trigger_source", "period_start", "period_end"),
    ),
    # AR Collections (Phase 8c) — SIMPLE approval, per-customer fan-out
    "ar_collections.run_collections_pipeline": (
        "app.services.workflows.ar_collections_adapter:run_collections_pipeline",
        ("dry_run", "trigger_source"),
    ),
    # Expense Categorization (Phase 8c) — SIMPLE approval, per-line
    # review. Trigger migrated from "event" to "scheduled" cron.
    "expense_categorization.run_categorization_pipeline": (
        "app.services.workflows.expense_categorization_adapter:run_categorization_pipeline",
        ("dry_run", "trigger_source"),
    ),
    # FH Aftercare 7-day follow-up (Phase 8d) — triage-only. Staged
    # per-case items; approve sends email + logs VaultItem.
    "aftercare.run_pipeline": (
        "app.services.workflows.aftercare_adapter:run_pipeline",
        ("dry_run", "trigger_source"),
    ),
    # Wilbert catalog auto-fetch (Phase 8d) — triage-gated publish.
    # Stages a pending-review sync_log; approve runs the legacy
    # ingest_from_pdf unchanged.
    "catalog_fetch.run_staged_fetch": (
        "app.services.workflows.catalog_fetch_adapter:run_staged_fetch",
        ("dry_run", "trigger_source"),
    ),
    # Safety Program generation (Phase 8d.1) — AI-generation-with-approval.
    # Wraps the existing run_monthly_generation verbatim; no AgentJob
    # wrapper. Triage queue reads pending_review generations directly.
    "safety_program.run_generation_pipeline": (
        "app.services.workflows.safety_program_adapter:run_generation_pipeline",
        ("dry_run", "trigger_source"),
    ),
}


def _resolve_callable(import_path: str):
    """Import a callable from a 'module:attr' path."""
    module_path, attr = import_path.split(":", 1)
    from importlib import import_module

    mod = import_module(module_path)
    return getattr(mod, attr)


def _handle_call_service_method(
    db: Session,
    config: dict,
    run: WorkflowRun,
    current_company: Company | None,
) -> dict:
    """Dispatch a workflow step to a whitelisted adapter method.

    Config keys:
      method_name    : str  — dotted key in _SERVICE_METHOD_REGISTRY
      kwargs         : dict — forwarded to the callable; filtered by
                              the registry's allowed-kwargs list
      triggered_by   : str  — optional override for audit attribution
                              (defaults to run.triggered_by_user_id)

    Auto-injected kwargs (method gets these regardless of config):
      db, company_id, triggered_by_user_id

    Returns the callable's return value (dict) merged with
    {"method_name", "status": "applied" | "errored"}.
    """
    method_name = config.get("method_name")
    if not method_name:
        return {
            "status": "errored",
            "error": "call_service_method step missing method_name",
        }
    entry = _SERVICE_METHOD_REGISTRY.get(method_name)
    if entry is None:
        return {
            "status": "errored",
            "error": f"method_name {method_name!r} not in registry",
            "method_name": method_name,
        }
    import_path, allowed_kwargs = entry
    raw_kwargs = config.get("kwargs") or {}
    kwargs = {k: v for k, v in raw_kwargs.items() if k in allowed_kwargs}

    company_id = run.company_id if run is not None else None
    if current_company is not None:
        company_id = current_company.id

    triggered_by = config.get("triggered_by") or (
        run.triggered_by_user_id if run is not None else None
    )

    try:
        fn = _resolve_callable(import_path)
        result = fn(
            db,
            company_id=company_id,
            triggered_by_user_id=triggered_by,
            **kwargs,
        )
    except Exception as exc:  # noqa: BLE001 — surface to workflow step
        return {
            "status": "errored",
            "error": str(exc)[:500],
            "method_name": method_name,
        }
    out: dict[str, Any] = {"status": "applied", "method_name": method_name}
    if isinstance(result, dict):
        out.update(result)
    else:
        out["result"] = result
    return out


def _handle_create_record(db: Session, config: dict, run: WorkflowRun) -> dict:
    """Create a record based on config.record_type and config.fields.

    Supports a whitelist of record types. Uses raw SQL inserts to stay
    tolerant of different column sets across environments. Returns
    {id, type} of the created record.
    """
    from sqlalchemy import text as sql_text

    record_type = config.get("record_type")
    fields = config.get("fields") or {}
    company_id = run.company_id
    new_id = str(uuid.uuid4())

    if record_type == "funeral_case":
        # Use the case_service for correctness (creates all satellites)
        from app.services.fh import case_service
        case = case_service.create_case(
            db,
            company_id=company_id,
            director_id=fields.get("director_id") or run.triggered_by_user_id,
        )
        # Apply any remaining field overrides
        for k, v in fields.items():
            if k == "director_id":
                continue
            if hasattr(case, k) and v is not None:
                setattr(case, k, v)
        db.commit()
        db.refresh(case)
        return {"id": case.id, "case_number": case.case_number, "type": "funeral_case"}

    if record_type == "disinterment_order":
        # Table name uses disinterment model if present; otherwise log a vault item
        try:
            # Try direct insert — best-effort
            result = db.execute(
                sql_text(
                    "INSERT INTO disinterment_orders "
                    "(id, company_id, status, created_at, updated_at) "
                    "VALUES (:id, :cid, :status, now(), now()) "
                    "RETURNING id"
                ),
                {"id": new_id, "cid": company_id, "status": fields.get("status", "pending")},
            )
            row = result.fetchone()
            db.commit()
            return {"id": row[0] if row else new_id, "type": "disinterment_order"}
        except Exception:
            db.rollback()
            # Fallback: vault item so the workflow still succeeds
            return _handle_log_vault_item(
                db,
                {
                    "item_type": "event",
                    "event_type": "disinterment_order",
                    "title": "Disinterment order",
                    "metadata": fields,
                },
                run,
            )

    if record_type == "order":
        try:
            result = db.execute(
                sql_text(
                    "INSERT INTO sales_orders "
                    "(id, company_id, order_number, status, created_at, updated_at) "
                    "VALUES (:id, :cid, :num, :status, now(), now()) "
                    "RETURNING id"
                ),
                {
                    "id": new_id,
                    "cid": company_id,
                    "num": f"WF-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{new_id[:8].upper()}",
                    "status": fields.get("status", "pending"),
                },
            )
            row = result.fetchone()
            db.commit()
            return {"id": row[0] if row else new_id, "type": "order"}
        except Exception as e:
            db.rollback()
            return {"status": "error", "error": str(e)[:200], "type": "order"}

    if record_type == "delivery":
        try:
            result = db.execute(
                sql_text(
                    "INSERT INTO deliveries "
                    "(id, company_id, order_id, scheduled_date, status, created_at, updated_at) "
                    "VALUES (:id, :cid, :oid, :date, :status, now(), now()) "
                    "RETURNING id"
                ),
                {
                    "id": new_id,
                    "cid": company_id,
                    "oid": fields.get("order_id"),
                    "date": fields.get("scheduled_date"),
                    "status": fields.get("status", "scheduled"),
                },
            )
            row = result.fetchone()
            db.commit()
            return {"id": row[0] if row else new_id, "type": "delivery"}
        except Exception as e:
            db.rollback()
            return {"status": "error", "error": str(e)[:200], "type": "delivery"}

    if record_type == "purchase_order":
        try:
            po_number = f"WF-PO-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{new_id[:8].upper()}"
            result = db.execute(
                sql_text(
                    "INSERT INTO purchase_orders "
                    "(id, company_id, po_number, status, notes, created_at, updated_at) "
                    "VALUES (:id, :cid, :num, :status, :notes, now(), now()) "
                    "RETURNING id, po_number"
                ),
                {
                    "id": new_id,
                    "cid": company_id,
                    "num": fields.get("po_number", po_number),
                    "status": fields.get("status", "draft"),
                    "notes": fields.get("notes"),
                },
            )
            row = result.fetchone()
            db.commit()
            return {
                "id": row[0] if row else new_id,
                "po_number": row[1] if row else po_number,
                "type": "purchase_order",
            }
        except Exception as e:
            db.rollback()
            return {"status": "error", "error": str(e)[:200], "type": "purchase_order"}

    if record_type == "compliance_item":
        return _handle_log_vault_item(
            db,
            {
                "item_type": "compliance",
                "event_type": fields.get("category", "compliance_item"),
                "title": fields.get("title", "Compliance item"),
                "metadata": fields,
            },
            run,
        )

    return {"status": "unsupported_record_type", "record_type": record_type}


def _handle_update_record(db: Session, config: dict, run: WorkflowRun) -> dict:
    """Best-effort record update via raw SQL."""
    from sqlalchemy import text as sql_text
    record_type = config.get("record_type")
    record_id = config.get("record_id")
    fields = config.get("fields") or {}
    if not record_type or not record_id or not fields:
        return {"status": "missing_params"}

    table = {
        "funeral_case": "funeral_cases",
        "order": "sales_orders",
        "delivery": "deliveries",
        "purchase_order": "purchase_orders",
    }.get(record_type)
    if not table:
        return {"status": "unsupported_record_type", "record_type": record_type}

    set_clauses = ", ".join(f"{k} = :{k}" for k in fields.keys())
    params = {"rid": record_id, **fields}
    try:
        db.execute(
            sql_text(f"UPDATE {table} SET {set_clauses}, updated_at = now() WHERE id = :rid"),
            params,
        )
        db.commit()
        return {"type": "updated", "record_id": record_id, "record_type": record_type}
    except Exception as e:
        db.rollback()
        return {"status": "error", "error": str(e)[:200]}


def _handle_send_notification(db: Session, config: dict, run: WorkflowRun) -> dict:
    """Create a vault item as a lightweight notification surface."""
    return _handle_log_vault_item(
        db,
        {
            "item_type": "notification",
            "event_type": "workflow_notification",
            "title": config.get("title", "Notification"),
            "description": config.get("body"),
            "metadata": {
                "notify_user_id": config.get("notify_user_id"),
                "notify_roles": config.get("notify_roles"),
                "link": config.get("link"),
            },
        },
        run,
    )


def _handle_log_vault_item(db: Session, config: dict, run: WorkflowRun) -> dict:
    """Create a vault_item row. Tolerant of missing columns."""
    from sqlalchemy import text as sql_text

    item_id = str(uuid.uuid4())
    item_type = config.get("item_type", "event")
    event_type = config.get("event_type")
    title = config.get("title", "Workflow event")
    description = config.get("description")
    metadata = config.get("metadata") or {}
    try:
        import json
        db.execute(
            sql_text(
                """
                INSERT INTO vault_items
                  (id, company_id, item_type, event_type, title, description,
                   metadata_json, source, source_entity_id, created_at, updated_at, is_active)
                VALUES
                  (:id, :cid, :itype, :etype, :title, :descr,
                   :meta, 'workflow', :run_id, now(), now(), true)
                """
            ),
            {
                "id": item_id,
                "cid": run.company_id,
                "itype": item_type,
                "etype": event_type,
                "title": title,
                "descr": description,
                "meta": json.dumps(metadata),
                "run_id": run.id,
            },
        )
        db.commit()
        return {"type": "vault_item", "id": item_id, "event_type": event_type}
    except Exception as e:
        db.rollback()
        return {"type": "vault_item", "status": "error", "error": str(e)[:200]}


def _evaluate_condition(config: dict) -> dict:
    """Simple condition eval: {field: X, op: '==', value: Y}."""
    field = config.get("field")
    op = config.get("op", "==")
    value = config.get("value")
    # Caller resolves the field value via variables; config.field can be either
    # a resolved literal or a reference. Support both.
    result = False
    if op == "==":
        result = field == value
    elif op == "!=":
        result = field != value
    elif op == "in":
        result = field in (value or [])
    return {"condition_result": result, "resolved_field": field}


def _complete_run(db: Session, run: WorkflowRun) -> None:
    run.status = "completed"
    run.completed_at = datetime.now(timezone.utc)
    db.commit()


def _fail_run(db: Session, run: WorkflowRun, message: str) -> None:
    run.status = "failed"
    run.error_message = message[:500]
    run.completed_at = datetime.now(timezone.utc)
    db.commit()


def list_runs(
    db: Session, company_id: str, limit: int = 20, status: str | None = None
) -> list[WorkflowRun]:
    q = db.query(WorkflowRun).filter(WorkflowRun.company_id == company_id)
    if status:
        q = q.filter(WorkflowRun.status == status)
    return q.order_by(WorkflowRun.started_at.desc()).limit(limit).all()


# ─────────────────────────────────────────────────────────────────────
# Phase D-1 — generate_document action handler
# ─────────────────────────────────────────────────────────────────────
#
# Routes a workflow step through the Documents layer. Step config shape
# (post-variable-resolution — the caller's `{input.x.y}` references have
# already been substituted with concrete values by resolve_variables):
#
#   {
#     "action_type":   "generate_document",
#     "template_key":  "invoice.professional",   # required
#     "document_type": "invoice",                # required
#     "title":         "Invoice INV-42",         # required
#     "description":   "optional",
#     "context":       {"invoice_number": "INV-42", ...}
#   }
#
# Returns:
#   {
#     "type":           "document_generated",
#     "document_id":    "<uuid>",
#     "storage_key":    "<r2_key>",
#     "pdf_url":        "<presigned_url, 1h TTL>",
#     "version_number": 1
#   }
#
# Downstream steps can reference {output.<step>.document_id},
# {output.<step>.pdf_url}, etc.


# Maps workflow trigger-context entity types to Document specialty FK kwargs.
# Matches the pattern in _execute_ai_prompt for Intelligence linkage.
_ENTITY_TYPE_TO_DOCUMENT_KWARG: dict[str, str] = {
    "funeral_case": "fh_case_id",
    "fh_case": "fh_case_id",
    "disinterment_case": "disinterment_case_id",
    "sales_order": "sales_order_id",
    "invoice": "invoice_id",
    "customer_statement": "customer_statement_id",
    "price_list_version": "price_list_version_id",
    "safety_program_generation": "safety_program_generation_id",
}


def _handle_generate_document(
    db: Session, config: dict, run: WorkflowRun,
) -> dict:
    """Render a document via DocumentRenderer and emit an output dict
    downstream steps can reference.

    Validation errors (missing template_key etc.) raise ValueError,
    which `_execute_step` catches and surfaces as a step failure.
    Render errors (DocumentRenderError) propagate the same way.
    """
    # Import inside the handler so callers that don't use this step type
    # don't pay the import cost at module load.
    from app.services.documents import document_renderer

    template_key = (config or {}).get("template_key")
    document_type = (config or {}).get("document_type")
    title = (config or {}).get("title")
    if not template_key or not document_type or not title:
        raise ValueError(
            "generate_document step requires template_key, document_type, "
            "and title in config"
        )
    context = (config or {}).get("context") or {}
    if not isinstance(context, dict):
        raise ValueError("generate_document config.context must be a dict")
    description = (config or {}).get("description")

    # Workflow trigger context → caller linkage
    trig = run.trigger_context or {}
    entity_type = trig.get("entity_type")
    entity_id = trig.get("entity_id")

    specialty_kwargs: dict[str, str] = {}
    if entity_type and entity_id:
        specialty = _ENTITY_TYPE_TO_DOCUMENT_KWARG.get(entity_type)
        if specialty:
            specialty_kwargs[specialty] = entity_id

    doc = document_renderer.render(
        db,
        template_key=template_key,
        context=context,
        document_type=document_type,
        title=title,
        description=description,
        company_id=run.company_id,
        entity_type=entity_type,
        entity_id=entity_id,
        caller_module=f"workflow_engine.{run.workflow_id}",
        caller_workflow_run_id=run.id,
        **specialty_kwargs,
    )

    presigned = document_renderer.presigned_url(doc, expires_in=3600)

    return {
        "type": "document_generated",
        "document_id": doc.id,
        "storage_key": doc.storage_key,
        "pdf_url": presigned,
        "version_number": 1,
        "document_type": document_type,
    }


# ─────────────────────────────────────────────────────────────────────
# Phase 3d — ai_prompt step type
# ─────────────────────────────────────────────────────────────────────
#
# Routes a workflow step through the managed-prompt Intelligence layer.
# Config shape (post-variable-resolution):
#   {
#     "prompt_key": "scribe.extract_intake",     # required
#     "variables":  {"name": "…", "context": "{input.step_1.body}"},
#     "store_output_as": "result"                # optional — reserved for
#                                                #  future nesting support
#   }
# Output shape (stored on WorkflowRunStep.output_data):
#   - If the prompt returns response_parsed (force_json=true, valid JSON):
#       { <parsed fields>, "_execution_id": "...", "_status": "success" }
#   - Otherwise:
#       { "text": "…", "_execution_id": "...", "_status": "success" }
#
# Downstream steps reference the fields with {output.step_key.field_name}.
# The `_execution_id` is preserved for audit / debug drill-through.

# Maps workflow trigger-context entity types to the Phase 2c-0a
# Intelligence linkage columns. Extend as new linkage columns are added.
_ENTITY_TYPE_TO_LINKAGE_KWARG: dict[str, str] = {
    "funeral_case": "caller_fh_case_id",
    "fh_case": "caller_fh_case_id",
    "agent_job": "caller_agent_job_id",
    "ringcentral_call_log": "caller_ringcentral_call_log_id",
    "call_log": "caller_ringcentral_call_log_id",
    "kb_document": "caller_kb_document_id",
    "price_list_import": "caller_price_list_import_id",
    "accounting_analysis_run": "caller_accounting_analysis_run_id",
}


def _execute_ai_prompt(
    db: Session,
    resolved_config: dict,
    run: WorkflowRun,
    run_step_id: str,
    step_key: str,
) -> dict:
    """Invoke a managed intelligence prompt as a workflow step.

    Raises on missing prompt_key (caught by _execute_step and surfaced as a
    step failure). Execution errors (Anthropic failures, render errors) are
    surfaced by raising so the run is marked failed — this matches the
    behavior of other action steps.
    """
    from app.services.intelligence import intelligence_service

    prompt_key = (resolved_config or {}).get("prompt_key")
    if not prompt_key:
        raise ValueError(
            "ai_prompt step requires a non-empty prompt_key in config",
        )
    variables = (resolved_config or {}).get("variables") or {}
    if not isinstance(variables, dict):
        raise ValueError(
            "ai_prompt step config.variables must be a dict",
        )

    # Workflow trigger context — drive caller linkage. trigger_context is
    # JSONB; callers typically put {entity_type, entity_id, record}.
    trig = run.trigger_context or {}
    entity_type = trig.get("entity_type")
    entity_id = trig.get("entity_id")

    linkage_kwargs: dict[str, str] = {}
    if entity_type and entity_id:
        specialty = _ENTITY_TYPE_TO_LINKAGE_KWARG.get(entity_type)
        if specialty:
            linkage_kwargs[specialty] = entity_id

    # Always thread the workflow_run + run_step ids — these are first-class
    # linkage columns on IntelligenceExecution (from Phase 1). Useful for
    # "show all AI calls made by this workflow run" queries.
    result = intelligence_service.execute(
        db,
        prompt_key=prompt_key,
        variables=variables,
        company_id=run.company_id,
        caller_module=f"workflow_engine.{run.workflow_id}.{step_key}",
        caller_entity_type=entity_type,
        caller_entity_id=entity_id,
        caller_workflow_run_id=run.id,
        caller_workflow_run_step_id=run_step_id,
        **linkage_kwargs,
    )

    if result.status != "success":
        # Surface as a step failure — upstream handler flips run to failed.
        raise RuntimeError(
            f"ai_prompt '{prompt_key}' returned status={result.status}: "
            f"{result.error_message or '(no error message)'}"
        )

    # Shape output so downstream steps can reference fields naturally.
    # - Parsed dict: spread fields at the top level so
    #   {output.step_key.field} resolves.
    # - Plain text: expose under `text`.
    output: dict
    if isinstance(result.response_parsed, dict):
        output = dict(result.response_parsed)
    else:
        output = {"text": result.response_text or ""}

    output["_execution_id"] = result.execution_id
    output["_status"] = result.status
    return output


def validate_ai_prompt_steps(
    db: Session, company_id: str | None, steps: list[dict]
) -> list[str]:
    """Return a list of human-readable error strings for ai_prompt steps.

    Returns empty list if everything checks out. Called from the workflow
    save endpoints so configuration bugs are caught at save time rather
    than at run time.

    Checks:
      1. prompt_key is non-empty and resolves to an active prompt visible
         to this tenant (company_id override or platform-global).
      2. Every `required` variable in the prompt's active version's
         variable_schema is mapped in step config.variables (either a
         literal or a reference string).
      3. Optional variables may be unmapped.
    """
    from app.models.intelligence import (
        IntelligencePrompt,
        IntelligencePromptVersion,
    )

    errors: list[str] = []
    step_keys_by_order = {
        s.get("step_order", i): s.get("step_key", "") for i, s in enumerate(steps)
    }

    for idx, step in enumerate(steps):
        if step.get("step_type") != "ai_prompt":
            continue
        step_key = step.get("step_key") or f"step_{idx}"
        cfg = step.get("config") or {}
        prompt_key = (cfg.get("prompt_key") or "").strip()
        if not prompt_key:
            errors.append(f"Step '{step_key}': prompt_key is required")
            continue

        # Resolve the prompt — tenant override beats platform
        q = db.query(IntelligencePrompt).filter(
            IntelligencePrompt.prompt_key == prompt_key,
            IntelligencePrompt.is_active.is_(True),
        )
        prompt: IntelligencePrompt | None = None
        if company_id:
            prompt = q.filter(IntelligencePrompt.company_id == company_id).first()
        if prompt is None:
            prompt = q.filter(
                IntelligencePrompt.company_id.is_(None)
            ).first()
        if prompt is None:
            errors.append(
                f"Step '{step_key}': prompt_key '{prompt_key}' not found or inactive"
            )
            continue

        active_version = (
            db.query(IntelligencePromptVersion)
            .filter(
                IntelligencePromptVersion.prompt_id == prompt.id,
                IntelligencePromptVersion.status == "active",
            )
            .first()
        )
        if active_version is None:
            errors.append(
                f"Step '{step_key}': prompt '{prompt_key}' has no active version"
            )
            continue

        schema = active_version.variable_schema or {}
        provided = (cfg.get("variables") or {})
        if not isinstance(provided, dict):
            errors.append(
                f"Step '{step_key}': config.variables must be a dict"
            )
            continue

        for var_name, var_spec in schema.items():
            is_required = bool(
                isinstance(var_spec, dict) and var_spec.get("required")
            )
            is_optional = bool(
                isinstance(var_spec, dict) and var_spec.get("optional")
            )
            if is_optional:
                continue
            if is_required and var_name not in provided:
                errors.append(
                    f"Step '{step_key}': missing required variable "
                    f"'{var_name}' for prompt '{prompt_key}'"
                )
        # Round-trip check — variables pointing at {output.X.Y} must
        # point at a step_key that appears earlier in the workflow.
        earlier_keys = {
            step_keys_by_order[k]
            for k in step_keys_by_order
            if isinstance(k, int) and k < step.get("step_order", idx)
        }
        for var_name, raw in provided.items():
            if not isinstance(raw, str):
                continue
            # Extract any {output.step.field} references — validate the step
            for m in VARIABLE_PATTERN.finditer(raw):
                ref = m.group(1).strip()
                if ref.startswith("output."):
                    referenced_step = ref[len("output."):].split(".", 1)[0]
                    if (
                        referenced_step
                        and referenced_step not in earlier_keys
                    ):
                        errors.append(
                            f"Step '{step_key}': variable '{var_name}' "
                            f"references {{output.{referenced_step}.…}} but "
                            f"that step does not appear before this one"
                        )

    return errors


# ═══════════════════════════════════════════════════════════════════════
# Phase D-7 — send_document step type
# ═══════════════════════════════════════════════════════════════════════


def _execute_send_document(
    db: Session,
    resolved_config: dict,
    run: WorkflowRun,
    run_step_id: str,
) -> dict:
    """Invoke DeliveryService as a workflow step.

    Config schema:
        {
            "document_id": "{output.prev.document_id}" | UUID,
            "channel": "email" | "sms",
            "recipient": {
                "type": "email_address" | "phone_number" | ...,
                "value": "...",
                "name": "..."   (optional)
            },
            "subject": "..."             (optional static)
            "template_key": "..."        (optional — renders template)
            "template_context": { ... }  (optional)
            "body": "..."                (alternative to template_key)
            "reply_to": "..."            (optional)
        }

    Output dict:
        {
            "delivery_id": "<uuid>",
            "status": "sent" | "failed" | "rejected",
            "provider_message_id": "..." | null,
            "error_message": "..." | null
        }
    """
    from app.services.delivery import delivery_service

    cfg = resolved_config or {}

    channel = cfg.get("channel")
    if channel not in ("email", "sms"):
        raise ValueError(
            f"send_document requires channel='email' or 'sms' (got {channel!r})"
        )

    recipient = cfg.get("recipient") or {}
    if not recipient.get("type") or not recipient.get("value"):
        raise ValueError(
            "send_document requires recipient.type and recipient.value"
        )

    template_key = cfg.get("template_key")
    body = cfg.get("body")
    if not template_key and not body:
        raise ValueError(
            "send_document requires either template_key or body"
        )

    # Resolve specialty linkage from trigger context (reuses the
    # ai_prompt pattern for consistency)
    trig = run.trigger_context or {}

    params = delivery_service.SendParams(
        company_id=run.company_id,
        channel=channel,
        recipient=delivery_service.RecipientInput(
            type=recipient["type"],
            value=recipient["value"],
            name=recipient.get("name"),
        ),
        document_id=cfg.get("document_id"),
        subject=cfg.get("subject"),
        template_key=template_key,
        template_context=cfg.get("template_context") or {},
        body=body,
        body_html=cfg.get("body_html"),
        reply_to=cfg.get("reply_to"),
        from_name=cfg.get("from_name"),
        caller_module=f"workflow_engine.{run.workflow_id}",
        caller_workflow_run_id=run.id,
        caller_workflow_step_id=run_step_id,
    )

    try:
        delivery = delivery_service.send(db, params)
    except delivery_service.DeliveryError as exc:
        # Programmer-error level — surface as step failure
        raise ValueError(f"send_document rejected: {exc}")

    return {
        "delivery_id": delivery.id,
        "status": delivery.status,
        "provider_message_id": delivery.provider_message_id,
        "error_message": delivery.error_message,
        "channel": delivery.channel,
        "recipient": delivery.recipient_value,
    }
