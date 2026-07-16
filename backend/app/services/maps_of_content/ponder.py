"""The Ponder — derive the staged walkthrough script from truth (P0+P1).

Per ponder_investigation.md: given a task-catalog row, build the ordered
BEAT list the overlay renders — every beat derived live from the platform's
own state, never baked:

  when       — the trigger config → human-legible prose
  step/pause — the mirror canvas nodes in edge order (pause = input/approval)
  downstream — the workflow→queue registry + H1's REAL failure routing
  garnish    — last-run numbers where cheaply readable (omitted, never faked)

CAPTION MERGE: the task row's `ponder` JSONB (r127) overlays authored text
per beat, keyed by stable beat keys (node slugs — the C-2.1.2 slug-is-
identity pattern). A missing/orphaned caption degrades to the DERIVED text:
plainer, never stale. Orphans are reported for the editor's reclaim list.

THE MIRROR-DRIFT CHECK (P0 — the schema-gate's sibling, pointed at
pedagogy): a mirror teaches its runtime source's story; if the runtime shape
changes under the mirror (step count/order/type), the ponder would silently
teach the old story. Divergence logs a NAMED warning + rides the script
payload — warn, not fail: a stale ponder is a P0-priority content bug, not
an outage.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.moc_task_catalog import MoCTaskCatalog
from app.models.workflow import Workflow, WorkflowRun, WorkflowStep
from app.models.workflow_template import WorkflowTemplate

logger = logging.getLogger(__name__)


# ── P0: the workflow→queue registry (the 5 authored entries) ────────────────
# The one place the derived story needs a human-maintained map: the runtime
# workflow → its BUSINESS-exception triage queue is convention (adapter code),
# not a queryable link. Authored here, read by the downstream beat.
QUEUE_REGISTRY: dict[str, dict[str, str]] = {
    "wf_sys_statement_run": {
        "queue_id": "month_end_close_triage",
        "queue_label": "Month-End Close review",
        "note": "Flagged statements are reviewed before anything sends.",
    },
    "wf_sys_month_end_close": {
        "queue_id": "month_end_close_triage",
        "queue_label": "Month-End Close review",
        "note": "Anomalies the checks surface wait for your decision.",
    },
    "wf_sys_ar_collections": {
        "queue_id": "ar_collections_triage",
        "queue_label": "AR Collections review",
        "note": "Each drafted reminder waits for a person to send or skip.",
    },
    "wf_sys_expense_categorization": {
        "queue_id": "expense_categorization_triage",
        "queue_label": "Expense Categorization review",
        "note": "Uncertain categorizations queue for a quick confirm.",
    },
    "wf_sys_cash_receipts": {
        "queue_id": "cash_receipts_matching_triage",
        "queue_label": "Cash Receipts review",
        "note": "Payments that can't be confidently matched wait here.",
    },
}

# H1 is live: run failures land in Decision Triage (workflow_review_triage)
# and surface in the morning briefing's queue counts. This beat is TRUE.
_FAILURE_BEAT_TEXT = (
    "And if a run ever fails, it lands in Decision Triage — deduplicated, "
    "with the error and a link to the run — and shows up in your morning "
    "briefing's counts."
)

_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_MONTHS = ["", "January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"]


def _ordinal(n: int) -> str:
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def _clock(hh: int, mm: int) -> str:
    ampm = "AM" if hh < 12 else "PM"
    h12 = hh % 12 or 12
    return f"{h12}:{mm:02d} {ampm}"


def cron_to_prose(cron: str, timezone_name: str | None = None) -> str:
    """A deliberately small cron renderer for the shapes the platform uses.
    Unrecognized shapes fall back to showing the cron honestly."""
    tz = " (tenant-local)" if timezone_name else ""
    parts = cron.split()
    if len(parts) != 5:
        return f"On the schedule `{cron}`{tz}"
    minute, hour, dom, month, dow = parts
    try:
        if minute.startswith("*/") and hour == "*" and dom == "*" and dow == "*":
            return f"Every {int(minute[2:])} minutes"
        if minute.isdigit() and hour.isdigit():
            clock = _clock(int(hour), int(minute))
            if dom == "*" and dow == "*":
                return f"Every night at {clock}{tz}" if int(hour) >= 20 else f"Every day at {clock}{tz}"
            if dom.isdigit() and dow == "*":
                day = _ordinal(int(dom))
                if month == "*":
                    return f"The {day} of each month at {clock}{tz}"
                return f"Every {_MONTHS[int(month)]} {day} at {clock}{tz}"
            if dom == "*" and dow.isdigit():
                return f"Every {_WEEKDAYS[int(dow) % 7 - 1 if int(dow) else 6]} at {clock}{tz}"
    except (ValueError, IndexError):
        pass
    return f"On the schedule `{cron}`{tz}"


def _when_text(workflow: Workflow) -> str:
    cfg = workflow.trigger_config or {}
    t = workflow.trigger_type
    if t == "manual":
        return "When you run it — this one waits for a person to start it."
    if t == "scheduled" and cfg.get("cron"):
        return cron_to_prose(cfg["cron"], cfg.get("timezone")) + "."
    if t == "time_of_day" and cfg.get("time"):
        hh, mm = str(cfg["time"]).split(":")
        days = cfg.get("days") or []
        clock = _clock(int(hh), int(mm))
        if len(days) >= 7 or not days:
            return f"Every night at {clock}." if int(hh) >= 20 else f"Every day at {clock}."
        return f"At {clock} on {', '.join(d.capitalize() for d in days)}."
    if t == "event" and cfg.get("event"):
        return f"Whenever {cfg['event'].replace('.', ' ').replace('_', ' ')} occurs."
    return f"Trigger: {t or 'unspecified'}."


def _ordered_nodes(canvas: dict) -> list[dict]:
    """Walk the canvas edges from the root (a node with no incoming edge).
    Linear-subset walk — branches beyond the marked treatment would surface
    here (the STOP condition); the accounting mirrors are linear."""
    nodes = {n["id"]: n for n in canvas.get("nodes", [])}
    edges = canvas.get("edges", [])
    targets = {e["target"] for e in edges}
    nexts = {e["source"]: e["target"] for e in edges}
    roots = [nid for nid in nodes if nid not in targets]
    if not roots:
        return list(nodes.values())
    ordered, seen, cur = [], set(), roots[0]
    while cur and cur in nodes and cur not in seen:
        ordered.append(nodes[cur])
        seen.add(cur)
        cur = nexts.get(cur)
    # Any disconnected leftovers append in declaration order (honest, visible).
    ordered += [n for nid, n in nodes.items() if nid not in seen]
    return ordered


def check_mirror_drift(
    template: WorkflowTemplate, runtime_steps: list[WorkflowStep]
) -> list[str]:
    """The pedagogy drift check: the mirror's nodes vs the runtime's steps —
    count, order (by step_key), and type. Returns named divergences."""
    canvas = template.canvas_state or {}
    nodes = _ordered_nodes(canvas)
    drift: list[str] = []
    if len(nodes) != len(runtime_steps):
        drift.append(
            f"step count: mirror has {len(nodes)}, runtime has {len(runtime_steps)}"
        )
    for node, step in zip(nodes, sorted(runtime_steps, key=lambda s: s.step_order)):
        if node["id"] != step.step_key:
            drift.append(f"order/key: mirror '{node['id']}' vs runtime '{step.step_key}'")
        elif node.get("type") != step.step_type:
            drift.append(
                f"type on '{step.step_key}': mirror '{node.get('type')}' "
                f"vs runtime '{step.step_type}'"
            )
    return drift


def _garnish(db: Session, workflow: Workflow) -> dict | None:
    """Last-run numbers, cheap and honest. Absent → None (never fabricated)."""
    if workflow.id == "wf_sys_statement_run":
        from app.models.statement import StatementRun
        sr = (
            db.query(StatementRun)
            .order_by(StatementRun.created_at.desc())
            .first()
        )
        if sr and (sr.total_customers or 0) > 0:
            return {
                "headline": f"{sr.total_customers} customers",
                "detail": f"{sr.flagged_count or 0} flagged for review",
                "as_of": sr.created_at.isoformat() if sr.created_at else None,
            }
    # Generic: the latest completed run of this workflow.
    run = (
        db.query(WorkflowRun)
        .filter(
            WorkflowRun.workflow_id == workflow.id,
            WorkflowRun.status == "completed",
        )
        .order_by(WorkflowRun.started_at.desc())
        .first()
    )
    if run and run.started_at:
        return {
            "headline": "Last completed run",
            "detail": None,
            "as_of": run.started_at.isoformat(),
        }
    return None


# ── The motif grammar (Ponder Polish Set 3) ─────────────────────────────────
# Beat semantics → a scene HINT the overlay's motif library renders. Chosen
# from step type + config words — never hand-illustrated per workflow. A step
# the grammar can't place gets NO motif (the typographic treatment): a
# missing visual beats a lying one.

import re as _re

_MOTIF_ENTITIES = (
    "order", "invoice", "statement", "customer", "payment", "case",
    "document", "certificate", "delivery", "bill", "proof", "expense",
    "receipt", "anomaly", "report", "reminder", "pour", "vault",
)
_CREATE_VERBS = ("generate", "create", "draft", "produce", "compose")
_SEND_VERBS = ("send", "email", "notify", "dispatch", "deliver")


def _entities_in(text: str) -> list[str]:
    words = _re.findall(r"[a-z]+", text)
    seen: list[str] = []
    for w in words:
        singular = w[:-1] if w.endswith("s") else w
        if singular in _MOTIF_ENTITIES and singular not in seen:
            seen.append(singular)
    return seen


def motif_for_step(node: dict) -> dict | None:
    """The step-beat grammar. Returns {'kind': ..., ...} or None."""
    cfg = node.get("config") or {}
    ntype = node.get("type")
    if ntype in ("condition", "decision", "branch"):
        return {"kind": "branch"}
    if ntype == "input":
        return {"kind": "pause"}
    text = " ".join(
        str(x) for x in (
            node.get("id"), node.get("label"),
            cfg.get("description"), cfg.get("action_type"), cfg.get("record_type"),
        ) if x
    ).lower().replace("_", " ")
    words = set(_re.findall(r"[a-z]+", text))
    entities = _entities_in(text)
    action_type = cfg.get("action_type") or ""

    if words & set(_SEND_VERBS) or action_type in ("send_communication", "send_document", "notification"):
        return {"kind": "send", "entity": entities[0] if entities else None}

    if words & set(_CREATE_VERBS) or action_type in ("create_record", "generate_document"):
        # "generate X from Y" → a TRANSFORM (Y becomes X); else a CREATE.
        if " from " in text and len(entities) >= 2:
            before, _, after = text.partition(" from ")
            to_e = _entities_in(before) or entities[:1]
            from_e = _entities_in(after)
            if to_e and from_e and to_e[0] != from_e[0]:
                return {"kind": "transform", "from": from_e[0], "to": to_e[0]}
        return {"kind": "create", "entity": entities[0] if entities else None}

    return None  # the grammar can't place it — typographic, never a wrong scene


class PonderError(ValueError):
    pass


def build_ponder_script(db: Session, task_id: str) -> dict[str, Any]:
    task = db.get(MoCTaskCatalog, task_id)
    if task is None or not task.is_active:
        raise PonderError("Task not found")
    if not task.workflow_template_id:
        raise PonderError("This task has no workflow to ponder")
    template = db.get(WorkflowTemplate, task.workflow_template_id)
    if template is None:
        raise PonderError("The task's workflow template is gone")

    runtime: Workflow | None = None
    runtime_steps: list[WorkflowStep] = []
    drift: list[str] = []
    if template.mirrored_from_workflow_id:
        runtime = db.get(Workflow, template.mirrored_from_workflow_id)
        if runtime is not None:
            runtime_steps = (
                db.query(WorkflowStep)
                .filter(WorkflowStep.workflow_id == runtime.id)
                .order_by(WorkflowStep.step_order)
                .all()
            )
            drift = check_mirror_drift(template, runtime_steps)
            if drift:
                logger.warning(
                    "PONDER MIRROR DRIFT — template %s (%s) diverges from its "
                    "runtime source %s: %s. The walkthrough may teach an old "
                    "story; re-run the mirror pass.",
                    template.id, template.workflow_type, runtime.id,
                    "; ".join(drift),
                )

    captions: dict[str, str] = {}
    if isinstance(task.ponder, dict):
        captions = dict(task.ponder.get("captions") or {})

    beats: list[dict[str, Any]] = []

    def _beat(key: str, kind: str, derived: str, **extra) -> None:
        authored = captions.get(key)
        beats.append({
            "key": key,
            "kind": kind,
            "text": authored or derived,
            "derived_text": derived,
            "authored": bool(authored),
            **extra,
        })

    # WHEN
    if runtime is not None:
        _when_motif = None
        if runtime.trigger_type in ("scheduled", "time_of_day"):
            _when_motif = {"kind": "clock"}
        elif runtime.trigger_type == "event":
            _when_motif = {"kind": "signal"}
        _beat("when", "when", _when_text(runtime), motif=_when_motif)

    # STEPS / PAUSES from the mirror canvas
    for node in _ordered_nodes(template.canvas_state or {}):
        cfg = node.get("config") or {}
        derived = (
            cfg.get("description") or cfg.get("prompt")
            or node.get("label") or node["id"]
        )
        label = (node.get("label") or node["id"]).replace("_", " ")
        if node.get("type") == "input":
            _beat(
                f"pause:{node['id']}", "pause", derived,
                label=label, node_type=node.get("type"),
                motif={"kind": "pause"},
            )
        else:
            _beat(
                f"step:{node['id']}", "step", derived,
                label=label, node_type=node.get("type") or "action",
                motif=motif_for_step(node),
            )

    # DOWNSTREAM — the business-exception queue (registry) + H1's failure truth
    reg = QUEUE_REGISTRY.get(runtime.id) if runtime is not None else None
    if reg:
        _beat(
            "downstream:queue", "downstream", reg["note"],
            queue_id=reg["queue_id"], queue_label=reg["queue_label"],
            motif={"kind": "queue", "label": reg["queue_label"]},
        )
    _beat(
        "downstream:failure", "downstream", _FAILURE_BEAT_TEXT,
        queue_id="workflow_review_triage", queue_label="Decision Triage",
        motif={"kind": "failure", "label": "Decision Triage"},
    )

    # GARNISH
    garnish = _garnish(db, runtime) if runtime is not None else None
    if garnish:
        detail = f" — {garnish['detail']}" if garnish.get("detail") else ""
        as_of = ""
        if garnish.get("as_of"):
            as_of = f" (as of {garnish['as_of'][:10]})"
        _beat(
            "garnish", "garnish",
            f"{garnish['headline']}{detail}{as_of}",
            **garnish,
        )

    live_keys = {b["key"] for b in beats}
    orphaned = sorted(k for k in captions if k not in live_keys)

    return {
        "task_id": task.id,
        "task_name": task.name,
        "workflow_name": runtime.name if runtime else template.workflow_type,
        "beats": beats,
        "orphaned_captions": {k: captions[k] for k in orphaned},
        "mirror_drift": drift,
    }


def save_caption(
    db: Session, task_id: str, beat_key: str, text: str | None
) -> dict[str, str]:
    """Set (or clear, text=None) one authored caption. Returns the block."""
    task = db.get(MoCTaskCatalog, task_id)
    if task is None:
        raise PonderError("Task not found")
    block = dict(task.ponder or {})
    captions = dict(block.get("captions") or {})
    if text is None or not text.strip():
        captions.pop(beat_key, None)
    else:
        captions[beat_key] = text.strip()
    block["captions"] = captions
    task.ponder = block  # reassign — JSONB change detection
    db.commit()
    return captions
