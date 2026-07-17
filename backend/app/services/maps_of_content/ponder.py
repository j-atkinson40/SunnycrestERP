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
            if dom == "last" and dow == "*" and month == "*":
                # T-2 (the FH Billing birth): APScheduler's 'last' —
                # end-of-month, cleanly expressible + cleanly taught.
                return f"The last day of each month at {clock}{tz}"
            if dom == "*" and dow.isdigit():
                return f"Every {_WEEKDAYS[int(dow) % 7 - 1 if int(dow) else 6]} at {clock}{tz}"
    except (ValueError, IndexError):
        pass
    return f"On the schedule `{cron}`{tz}"


_ORDINAL_WORDS = {1: "first", 2: "second", 3: "third", 4: "fourth", "last": "last"}


def schedule_trigger_to_prose(config: dict) -> str:
    """A MoC schedule-trigger config → the WHEN beat's own sentence (no
    trailing period). The same grammar the editor's live readback mirrors —
    the user composing a schedule is writing this sentence in reverse."""
    cfg = config or {}
    spec = cfg.get("spec_kind")
    if spec == "cron" and cfg.get("cron"):
        return cron_to_prose(cfg["cron"], cfg.get("timezone"))
    if spec == "time_of_day" and cfg.get("time"):
        try:
            hh, mm = str(cfg["time"]).split(":", 1)
            clock = _clock(int(hh), int(mm))
        except (ValueError, AttributeError):
            return "On a schedule"
        days = cfg.get("days") or []
        if not days or len(days) >= 7:
            return f"Every night at {clock}" if int(hh) >= 20 else f"Every day at {clock}"
        return f"At {clock} on {', '.join(str(d).capitalize() for d in days)}"
    if spec == "ordinal_weekday":
        word = _ORDINAL_WORDS.get(cfg.get("ordinal"))
        weekday_abbrev = str(cfg.get("weekday", ""))
        full = {
            "mon": "Monday", "tue": "Tuesday", "wed": "Wednesday", "thu": "Thursday",
            "fri": "Friday", "sat": "Saturday", "sun": "Sunday",
        }.get(weekday_abbrev)
        try:
            hh, mm = str(cfg.get("time")).split(":", 1)
            clock = _clock(int(hh), int(mm))
        except (ValueError, AttributeError):
            clock = None
        if word and full:
            base = f"The {word} {full} of every month"
            return f"{base} at {clock}" if clock else base
        return "On a monthly schedule"
    if spec == "time_after_event":
        n = cfg.get("offset_days", 0)
        return f"{n} day{'s' if n != 1 else ''} after {cfg.get('field', 'the event')}"
    return "On a schedule"


def _trigger_prose(kind: str, config: dict) -> str:
    """One MoC task trigger → its WHEN sentence (no trailing period)."""
    if kind == "manual":
        return "When you run it — this one waits for a person to start it"
    if kind == "schedule":
        return schedule_trigger_to_prose(config)
    if kind == "event":
        event = str(config.get("event", "an event"))
        base = f"Whenever {event.replace('.', ' ').replace('_', ' ')} occurs"
        conditions = config.get("conditions") or []
        if conditions and isinstance(conditions[0], dict):
            c = conditions[0]
            base += f" (where {c.get('field')} {c.get('operator')} {c.get('value')})"
        return base
    return "On a trigger"


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


def _garnish(
    db: Session, workflow: Workflow, company_id: str | None = None
) -> dict | None:
    """Last-run numbers, cheap and honest. Absent → None (never fabricated).
    company_id (P2, the tenant read) scopes to THEIR numbers — a tenant's
    garnish never leaks another tenant's run."""
    if workflow.id == "wf_sys_statement_run":
        from app.models.statement import StatementRun
        srq = db.query(StatementRun)
        if company_id is not None:
            srq = srq.filter(StatementRun.tenant_id == company_id)
        sr = srq.order_by(StatementRun.created_at.desc()).first()
        if sr and (sr.total_customers or 0) > 0:
            return {
                "headline": f"{sr.total_customers} customers",
                "detail": f"{sr.flagged_count or 0} flagged for review",
                "as_of": sr.created_at.isoformat() if sr.created_at else None,
            }
    # Generic: the latest completed run of this workflow.
    rq = db.query(WorkflowRun).filter(
        WorkflowRun.workflow_id == workflow.id,
        WorkflowRun.status == "completed",
    )
    if company_id is not None:
        rq = rq.filter(WorkflowRun.company_id == company_id)
    run = rq.order_by(WorkflowRun.started_at.desc()).first()
    if run and run.started_at:
        return {
            "headline": "Last completed run",
            "detail": None,
            "as_of": run.started_at.isoformat(),
        }
    return None


# ── Artifact previews + audience attribution (Ponder Enrichment) ────────────
# DOCUMENT_REGISTRY: like QUEUE_REGISTRY, an AUTHORED map that mirrors real
# adapter behavior — the accounting adapters render documents by convention
# (statement_pdf_service._resolve_template_key → statement.professional), not
# via step config, so the ref isn't derivable from the canvas. Steps whose
# config DOES carry a template ref (generate_document / send_document) derive
# directly and never consult this map.
DOCUMENT_REGISTRY: dict[tuple[str, str], str] = {
    ("wf_sys_statement_run", "generate_statements"): "statement.professional",
    ("wf_sys_statement_run", "send_statements"): "email.statement",
    ("wf_sys_month_end_close", "statement_run"): "statement.professional",
}


def _document_artifact(db: Session, runtime_id: str | None, node: dict) -> dict | None:
    """A step's document ref → the artifact-preview payload (type+identity).
    The HTML itself renders lazily via the preview endpoint — never at
    script-build time."""
    cfg = node.get("config") or {}
    template_key = cfg.get("template_key") or cfg.get("template")
    if not template_key and runtime_id:
        template_key = DOCUMENT_REGISTRY.get((runtime_id, node.get("id") or ""))
    if not template_key:
        return None
    from app.models.document_template import DocumentTemplate, DocumentTemplateVersion

    tpl = (
        db.query(DocumentTemplate)
        .filter(
            DocumentTemplate.template_key == template_key,
            DocumentTemplate.company_id.is_(None),
            DocumentTemplate.is_active.is_(True),
        )
        .first()
    )
    if tpl is None:
        return None  # a missing preview beats a lying one
    version = None
    if tpl.current_version_id:
        v = db.get(DocumentTemplateVersion, tpl.current_version_id)
        version = v.version_number if v else None
    return {
        "type": "document",
        "template_key": template_key,
        "label": template_key.split(".", 1)[-1].replace("_", " ").title(),
        "document_type": tpl.document_type,
        "version": version,
        "authored_source": (node.get("config") or {}).get("template_key") is None,
    }


def _focus_artifact(db: Session, template_slug: str, vertical: str | None,
                    display_name: str | None = None) -> dict | None:
    """Resolve a focus (pin-honoring, lineage-live) → the miniature payload.
    Unresolvable → None (a missing preview beats a lying one)."""
    from app.services.focus_template_inheritance.resolver import (
        FocusTemplateNotFound, resolve_focus,
    )

    try:
        resolved = resolve_focus(db, template_slug=template_slug, vertical=vertical)
    except FocusTemplateNotFound:
        return None
    rows_schematic = [
        {
            "placements": [
                {"label": (p.get("component") or {}).get("name")
                 or p.get("component_name") or p.get("label") or "widget"}
                for p in (row.get("placements") or [])
            ]
        }
        for row in (resolved.rows or [])
    ]
    chrome_title = None
    if resolved.resolved_chrome:
        chrome_title = resolved.resolved_chrome.get("title")
    return {
        "type": "focus",
        "template_slug": resolved.template_slug,
        "display_name": display_name or resolved.template_slug.replace("-", " ").title(),
        "core_slug": resolved.core_slug,
        "core_version": resolved.core_version,
        "template_version": resolved.template_version,
        "chrome_title": chrome_title,
        "rows": rows_schematic,
    }


def _focus_beats(db: Session, task: MoCTaskCatalog) -> list[dict[str, Any]]:
    """The task's attached focuses → focus beats with a miniature payload
    derived from the RESOLVED composition (pin-honoring, lineage-live) —
    never a generic picture. Unresolvable → skipped (missing beats lying)."""
    from app.services.focus_template_inheritance.resolver import (
        FocusTemplateNotFound, resolve_focus,
    )
    from app.models.focus_template import FocusTemplate

    beats: list[dict[str, Any]] = []
    for join in task.focuses:
        tpl = db.get(FocusTemplate, join.focus_template_id)
        if tpl is None:
            # stale id — rebind by nothing here; the MoC resolver's rebind
            # happens at card level. Skip honestly.
            continue
        try:
            resolved = resolve_focus(
                db, template_slug=tpl.template_slug, vertical=tpl.vertical
            )
        except FocusTemplateNotFound:
            continue
        rows_schematic = [
            {
                "placements": [
                    {"label": (p.get("component") or {}).get("name")
                     or p.get("component_name") or p.get("label") or "widget"}
                    for p in (row.get("placements") or [])
                ]
            }
            for row in (resolved.rows or [])
        ]
        chrome_title = None
        if resolved.resolved_chrome:
            chrome_title = resolved.resolved_chrome.get("title")
        beats.append({
            "kind": "focus",
            "key": f"focus:{resolved.template_slug}",
            "derived": (
                f"The work happens in {tpl.display_name} — "
                f"this task opens it ready to go."
            ),
            "artifact": {
                "type": "focus",
                "template_slug": resolved.template_slug,
                "display_name": tpl.display_name,
                "core_slug": resolved.core_slug,
                "core_version": resolved.core_version,
                "template_version": resolved.template_version,
                "chrome_title": chrome_title,
                "rows": rows_schematic,
            },
        })
    return beats


def _audience_for_queue(
    db: Session, queue_id: str, company_id: str | None = None
) -> dict | None:
    """Queue → who can act on it, from the REAL config (queue permissions +
    the action palette's required_permission). Plus a capped live count —
    company-scoped on the tenant read (P2): THEIR people, not the platform's
    user census."""
    from app.services.triage.registry import _PLATFORM_CONFIGS
    from app.services.triage import platform_defaults  # noqa: F401 — ensure registered

    cfg = _PLATFORM_CONFIGS.get(queue_id)
    if cfg is None:
        return None
    perm = None
    for action in getattr(cfg, "action_palette", []) or []:
        if getattr(action, "required_permission", None):
            perm = action.required_permission
            break
    if perm is None:
        perms = getattr(cfg, "permissions", None) or []
        perm = perms[0] if perms else None
    if perm is None:
        return None
    # Capped live count — users whose role grants the permission. Capped at
    # 500 so the garnish never becomes a heavy scan (dev has fixture noise).
    from sqlalchemy import text as _sql

    company_clause = " AND u.company_id = :cid" if company_id is not None else ""
    params: dict = {"perm": perm}
    if company_id is not None:
        params["cid"] = company_id
    n = db.execute(_sql(
        "SELECT count(*) FROM ("
        " SELECT u.id FROM users u"
        " JOIN role_permissions rp ON rp.role_id = u.role_id"
        f" WHERE rp.permission_key = :perm AND u.is_active = true{company_clause}"
        " LIMIT 501) x"
    ), params).scalar() or 0
    return {
        "text": f"anyone with the {perm} permission",
        "permission": perm,
        "count": min(n, 500),
        "count_capped": n > 500,
    }


def _user_name_map(db: Session, user_ids: list) -> dict[str, str]:
    """User ids → {id: display name}. An id that doesn't resolve is simply
    ABSENT (a missing name beats a guessed one)."""
    ids = [str(u) for u in user_ids if u]
    if not ids:
        return {}
    from app.models.user import User

    rows = db.query(User).filter(User.id.in_(ids)).all()
    return {u.id: f"{u.first_name} {u.last_name}".strip() or u.email for u in rows}


def _resolve_user_names(db: Session, user_ids: list) -> list[str]:
    """User ids → display names, input order, unresolvable skipped."""
    by_id = _user_name_map(db, user_ids)
    return [by_id[str(u)] for u in user_ids if u and str(u) in by_id]


def _audience_for_step(db: Session, node: dict) -> dict | None:
    """Notify-shaped steps → their honest audience: roles named in config
    plus SPECIFIC PEOPLE (user_multi_select params — the fringe cases roles
    don't cover), names resolved live. Nothing honest in the config → None
    (never guess)."""
    cfg = node.get("config") or {}
    roles = cfg.get("roles") or cfg.get("notify_roles")
    user_ids = cfg.get("user_ids") or cfg.get("notify_user_ids")

    parts: list[str] = []
    if isinstance(roles, list) and roles:
        pretty = ", ".join(str(r).replace("_", " ") for r in roles)
        parts.append(f"the {pretty} role" + ("s" if len(roles) > 1 else ""))
    if isinstance(user_ids, list) and user_ids:
        names = _resolve_user_names(db, user_ids)
        if names:
            shown = ", ".join(names[:3])
            if len(names) > 3:
                shown += f" +{len(names) - 3} more"
            parts.append(shown)
    if not parts:
        return None
    return {"text": " + ".join(parts)}


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


# ── The schedule-authority discriminator (Transfer T-0) ─────────────────────
# WHO makes this task fire? Discriminated by AUTHORITY, never by task-ness:
#   "runtime_scheduler" — the task mirrors a runtime workflow that carries a
#       LIVE runtime schedule (scheduled / time_of_day / time_after_event).
#       The runtime scheduler is the firing truth; a composed MoC schedule
#       would be display-only — so the composer BLOCKS (blocked-with-reason
#       beats allowed-with-caveat) and the WHEN beat reads the RUNTIME
#       config, until the T-1/T-2 adopt transfers the clock.
#   "moc" — everything else: compiled tasks (the sweep + is_live govern —
#       the composer IS write-authoritative), authored drafts, and mirrors
#       of MANUAL runtime workflows (no competing schedule exists; composed
#       triggers are honest dry-run previews).
_RUNTIME_SCHEDULE_TYPES = ("scheduled", "time_of_day", "time_after_event")


def schedule_authority(runtime: Workflow | None) -> str:
    if (
        runtime is not None
        and runtime.is_active
        and runtime.trigger_type in _RUNTIME_SCHEDULE_TYPES
        # Transfer T-1: an adopted (retired) schedule no longer competes —
        # authority moved to the MoC trigger; the badge/block lift and the
        # §6 guard narrows, by this one condition.
        and runtime.schedule_retired_at is None
    ):
        return "runtime_scheduler"
    return "moc"


class PonderError(ValueError):
    pass


# ── The fires strip (P3 — the monitoring leg) ────────────────────────────────


def recent_fires(
    db: Session, *, runtime_workflow_id: str, company_id: str, limit: int = 8
) -> list[dict]:
    """What did this machine actually DO lately — THIS tenant's recent runs
    of the task's runtime workflow (mirror fires re-point to the same id, so
    one query covers scheduler fires AND sweep fires). A ledger, not a
    dashboard: when, dry-run/live (honest — read from the run's own marker),
    outcome, event provenance where event-fired, and the H1 review item for
    a FAILED fire (the deep link the frontend renders for roles that can
    follow it). Empty list = hasn't run — the strip says so plainly, never
    a fabricated history."""
    from app.models.workflow_review_item import WorkflowReviewItem

    runs = (
        db.query(WorkflowRun)
        .filter(
            WorkflowRun.workflow_id == runtime_workflow_id,
            WorkflowRun.company_id == company_id,
        )
        .order_by(WorkflowRun.started_at.desc())
        .limit(limit)
        .all()
    )
    if not runs:
        return []
    failed_ids = [r.id for r in runs if r.status == "failed"]
    review_by_run: dict[str, str] = {}
    if failed_ids:
        rows = (
            db.query(WorkflowReviewItem.run_id, WorkflowReviewItem.id)
            .filter(
                WorkflowReviewItem.run_id.in_(failed_ids),
                WorkflowReviewItem.company_id == company_id,
            )
            .all()
        )
        review_by_run = {run_id: item_id for run_id, item_id in rows}
    out = []
    for r in runs:
        ctx = r.trigger_context or {}
        out.append({
            "run_id": r.id,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "status": r.status,
            "is_dry_run": bool((r.output_data or {}).get("__dry_run__")),
            "source": r.trigger_source,
            "event_key": ctx.get("event_key"),
            "review_item_id": review_by_run.get(r.id),
        })
    return out


def user_can_follow_reviews(db: Session, user) -> bool:
    """Can this tenant user follow a failed fire into Decision Triage? Read
    from the QUEUE'S OWN config (workflow_review_triage permissions) — empty
    permissions = any authenticated tenant user (today's honest answer);
    if the queue later gains a permission, this mapping follows it."""
    from app.services.triage import platform_defaults  # noqa: F401 — ensure registered
    from app.services.triage.registry import _PLATFORM_CONFIGS

    cfg = _PLATFORM_CONFIGS.get("workflow_review_triage")
    if cfg is None:
        return False
    perms = list(getattr(cfg, "permissions", None) or [])
    if not perms:
        return True
    from sqlalchemy import text as _sql

    n = db.execute(_sql(
        "SELECT count(*) FROM role_permissions WHERE role_id = :rid "
        "AND permission_key = ANY(:perms)"
    ), {"rid": user.role_id, "perms": perms}).scalar() or 0
    return n > 0


# ── The document-preview render (one path, both realms — P2) ────────────────
# Mirrors the Studio Documents editor's default sample shape; a version's own
# sample_context (when authored) overlays this.
PREVIEW_SAMPLE_CONTEXT = {
    "company_name": "Sunnycrest Precast",
    "company_logo_url": "",
    "document_title": "Preview",
    "document_date": "2026-06-01",
    "customer_name": "Hopkins Funeral Home",
    "customer_address": "123 Genesee St, Auburn, NY",
    "invoice_number": "INV-2026-0147",
    "statement_number": "ST-2026-06",
    "period_start": "2026-06-01",
    "period_end": "2026-06-30",
    "previous_balance": "$1,250.00",
    "new_charges": "$3,400.00",
    "payments_received": "$1,250.00",
    "balance_due": "$3,400.00",
    "items": [
        {"description": "Monticello vault", "quantity": 1,
         "unit_price": "$1,700.00", "line_total": "$1,700.00"},
        {"description": "Graveside setup", "quantity": 1,
         "unit_price": "$1,700.00", "line_total": "$1,700.00"},
    ],
    "subtotal": "$3,400.00", "tax": "$0.00", "total": "$3,400.00",
}


def render_document_preview(db: Session, template_key: str) -> dict[str, str]:
    """Lazy live-render of a PLATFORM template's real body for the ponder's
    document beat — resolved at request time, never cached stale. Raises
    PonderError (not-found / render failure); the route layers map it. The
    ONE preview path — the admin + tenant routers both delegate here."""
    from app.models.document_template import DocumentTemplate, DocumentTemplateVersion
    from app.services.documents import document_renderer

    tpl = (
        db.query(DocumentTemplate)
        .filter(
            DocumentTemplate.template_key == template_key,
            DocumentTemplate.company_id.is_(None),
            DocumentTemplate.is_active.is_(True),
        )
        .first()
    )
    if tpl is None:
        raise PonderError("Template not found")
    context = dict(PREVIEW_SAMPLE_CONTEXT)
    if tpl.current_version_id:
        v = db.get(DocumentTemplateVersion, tpl.current_version_id)
        if v is not None and isinstance(v.sample_context, dict):
            context.update(v.sample_context)
    try:
        html = document_renderer.render_preview_html(
            db, template_key=template_key, context=context
        )
    except Exception as e:
        raise PonderError(f"Preview render failed: {e}")
    return {"template_key": template_key, "html": html}


def build_ponder_script(
    db: Session, task_id: str, company_id: str | None = None
) -> dict[str, Any]:
    """The staged walkthrough script. company_id (P2, the tenant read)
    scopes everything numeric-or-personal to THEIR tenancy: effective params
    (their overrides in the chain), audience counts (their people), garnish
    (their fires). None = the platform-admin read, unchanged."""
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

    # Tenant Ponder-Editor P1 — SYMMETRY: the derivation reads the SAME
    # effective param values fire time merges (one resolution path — see
    # services/workflows/step_params.py). Beats below derive from node config
    # WITH live overlays applied, and step beats carry their declared params
    # so the editor renders fields for exactly what the platform declared.
    params_by_step: dict[str, list[dict]] = {}
    live_by_step: dict[str, dict[str, Any]] = {}
    if runtime is not None:
        from app.services.workflows.step_params import describe_step_params

        for p in describe_step_params(db, runtime.id, company_id):
            if p["param_type"] == "user_multi_select":
                # The editor's chips need names, resolved with the same
                # honesty as the audience line (unresolvable → absent).
                ids = p["effective_value"] if isinstance(p["effective_value"], list) else []
                p = {**p, "value_labels": _user_name_map(db, ids)}
            params_by_step.setdefault(p["step_key"], []).append(p)
            if p["live"] and p["is_configurable"]:
                live_by_step.setdefault(p["step_key"], {})[p["param_key"]] = (
                    p["effective_value"]
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

    # WHEN — the task's OWN triggers first (the T-1b collection the ponder's
    # trigger editor writes; editing the beat edits these rows and the beat
    # re-derives). Tasks with no declared triggers fall back to the runtime
    # workflow's trigger config (still editable — an edit ADDS a task trigger).
    from app.services.maps_of_content import triggers as triggers_svc

    task_triggers = triggers_svc.list_triggers(db, task_catalog_id=task.id)
    active_triggers = [t for t in task_triggers if t.is_active]
    trigger_payloads = [
        {
            "id": t.id, "kind": t.kind, "config": t.config, "label": t.label,
            "is_active": t.is_active, "is_live": t.is_live,
            "summary": triggers_svc.summarize_trigger(t.kind, t.config),
        }
        for t in task_triggers
    ]
    authority = schedule_authority(runtime)
    is_owned_fork = task.scope == "tenant_override" and company_id is not None
    if authority == "runtime_scheduler" and not is_owned_fork:
        # T-0 HONESTY: the runtime scheduler is the firing truth — the beat
        # teaches ITS schedule, sourced from the authority that makes it
        # happen, regardless of any composed MoC trigger. The composer is
        # blocked (editable=False + managed_by); triggers still ride the
        # payload so nothing is hidden.
        _when_motif = {"kind": "clock"}
        _beat(
            "when", "when", _when_text(runtime), motif=_when_motif,
            triggers=trigger_payloads, editable=False,
            managed_by="standard_scheduler",
        )
    elif active_triggers:
        sentences = []
        for t in active_triggers:
            sentences.append(_trigger_prose(t.kind, t.config or {}))
        derived_when = ". ".join(sentences) + "."
        kinds = {t.kind for t in active_triggers}
        _when_motif = None
        if "schedule" in kinds:
            _when_motif = {"kind": "clock"}
        elif "event" in kinds:
            _when_motif = {"kind": "signal"}
        _beat(
            "when", "when", derived_when, motif=_when_motif,
            triggers=trigger_payloads, editable=True,
        )
    elif runtime is not None:
        _when_motif = None
        if runtime.trigger_type in ("scheduled", "time_of_day"):
            _when_motif = {"kind": "clock"}
        elif runtime.trigger_type == "event":
            _when_motif = {"kind": "signal"}
        _beat(
            "when", "when", _when_text(runtime), motif=_when_motif,
            triggers=trigger_payloads, editable=True,
        )

    # STEPS / PAUSES from the mirror canvas
    for node in _ordered_nodes(template.canvas_state or {}):
        # SYMMETRY: derive from the node config WITH live param overlays
        # merged — the beat shows what the fire would do, by construction.
        overlay = live_by_step.get(node["id"]) or {}
        cfg = {**(node.get("config") or {}), **overlay}
        node = {**node, "config": cfg}
        derived = (
            cfg.get("description") or cfg.get("prompt")
            or node.get("label") or node["id"]
        )
        label = (node.get("label") or node["id"]).replace("_", " ")
        if node.get("type") == "input":
            # The pause's audience = whoever can act on the workflow's
            # review queue (the registry link → the queue's real config).
            pause_audience = None
            if runtime is not None and runtime.id in QUEUE_REGISTRY:
                pause_audience = _audience_for_queue(
                    db, QUEUE_REGISTRY[runtime.id]["queue_id"], company_id
                )
            _beat(
                f"pause:{node['id']}", "pause", derived,
                label=label, node_type=node.get("type"),
                motif={"kind": "pause"},
                audience=pause_audience,
            )
        else:
            _beat(
                f"step:{node['id']}", "step", derived,
                label=label, node_type=node.get("type") or "action",
                motif=motif_for_step(node),
                artifact=_document_artifact(db, runtime.id if runtime else None, node),
                audience=_audience_for_step(db, node),
                # The declared params — the editing grammar's fields. Empty
                # list omitted to keep un-parameterized beats lean.
                **({"params": params_by_step[node["id"]], "editable": True}
                   if params_by_step.get(node["id"]) else {}),
            )

    # FOCUS beats — the task's attached focuses, resolved live (pin-honoring)
    for fb in _focus_beats(db, task):
        _beat(fb["key"], "focus", fb["derived"], artifact=fb["artifact"])

    # DOWNSTREAM — the business-exception queue (registry) + H1's failure truth
    reg = QUEUE_REGISTRY.get(runtime.id) if runtime is not None else None
    if reg:
        _beat(
            "downstream:queue", "downstream", reg["note"],
            queue_id=reg["queue_id"], queue_label=reg["queue_label"],
            motif={"kind": "queue", "label": reg["queue_label"]},
            audience=_audience_for_queue(db, reg["queue_id"], company_id),
        )
    _beat(
        "downstream:failure", "downstream", _FAILURE_BEAT_TEXT,
        queue_id="workflow_review_triage", queue_label="Decision Triage",
        motif={"kind": "failure", "label": "Decision Triage"},
        # The queue's bound Focus (the frontend registry binds decision-triage
        # → workflow_review_triage) — the beat SHOWS where failures land. The
        # template is vertical-scoped; resolve in the task's vertical.
        artifact=_focus_artifact(db, "decision-triage", task.vertical, "Decision Triage"),
    )

    # GARNISH
    garnish = _garnish(db, runtime, company_id) if runtime is not None else None
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
        # Tenant Ponder-Editor P1 — the editors' gravity + context:
        # is_live gates the confirm-with-evidence (a live task's next fire
        # uses edited settings); vertical scopes the event-catalog picker;
        # workflow_id is the param editors' write target.
        "is_live": any(t.is_live for t in task_triggers),
        # T-0 — WHO makes this task fire (the composer + badges key on it).
        "schedule_authority": authority,
        # P3 — the fires strip (the tenant read only: THEIR history; the
        # platform read keeps its garnish). Empty list = hasn't run yet.
        "fires": (
            recent_fires(db, runtime_workflow_id=runtime.id, company_id=company_id)
            if company_id is not None and runtime is not None
            else None
        ),
        "task_scope": task.scope,
        "owned": task.scope == "tenant_override" and task.tenant_id == company_id
        if company_id is not None else True,
        "vertical": task.vertical,
        "workflow_id": runtime.id if runtime else None,
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
