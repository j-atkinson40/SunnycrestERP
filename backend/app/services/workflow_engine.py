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

        # Load first step for preview
        first_step = (
            db.query(WorkflowStep)
            .filter(WorkflowStep.workflow_id == w.id)
            .order_by(WorkflowStep.step_order)
            .first()
        )
        first_preview = ""
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
    """Provide input for a paused run and continue."""
    run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
    if not run:
        raise ValueError("Run not found")
    if run.status != "awaiting_input":
        raise ValueError(f"Run is not awaiting input (status={run.status})")

    # Save the input under its step_key
    inputs = dict(run.input_data or {})
    for k, v in (step_input or {}).items():
        inputs[k] = v
    run.input_data = inputs

    # Mark the currently-paused input step completed
    if run.current_step_id:
        rs = (
            db.query(WorkflowRunStep)
            .filter(WorkflowRunStep.run_id == run.id, WorkflowRunStep.step_id == run.current_step_id)
            .first()
        )
        if rs:
            rs.status = "completed"
            rs.output_data = step_input

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
        return {"type": "document_generated", "document_type": resolved_config.get("document_type"), "pdf_url": None}

    return {"status": "unknown_action_type", "action_type": action_type}


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
