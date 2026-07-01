"""Canvas → runtime compiler (Canvas↔Runtime Bridge T-2.0, MECHANISM 2).

Turns a `workflow_templates.canvas_state` (the inert design layer) into runnable
`workflows` + `workflow_steps` rows the existing engine executes — the FORWARD
direction, the (partial) inverse of the backfill's runtime→canvas transform.

SCOPE — THE LINEAR SUBSET ONLY (operator decision, T-2.0). The canvas node
vocabulary is richer than the runtime step model: the runtime walks one current
step at a time (`next_step_id` / `condition_true|false_step_id`), with no
representation for `parallel_split`/`parallel_join`/`branch`(n-way)/`wait`/
`schedule`, and no canonical canvas true/false edge convention for `condition`/
`decision` (deferred to T-2.0b once a convention + fixture exist). So this
compiler:
  - COMPILES a LINEAR canvas (a single chain: start → n1 → … → end, every node
    with ≤1 outgoing edge), and
  - REJECTS anything else LOUDLY with a node-specific error (never a silent
    partial-compile that drops a branch — dropping a node would execute a
    DIFFERENT workflow than authored, the worst failure).

SAFETY: the compiled workflow's `trigger_type` is FORCED to "manual" (never the
canvas's trigger) so a compiled row is inert to the scheduler — the bridge
invokes it directly; it must not fire itself. No engine dry-run yet (T-2.0b);
execution is gated in `execution_bridge.execute_template`.

Compile-on-demand: persists real `workflows`+`workflow_steps` rows (the engine
reads steps from the DB). Row accumulation + a compiled-workflow cache are a
T-2.0b concern; T-2.0 callers are test-only + clean up.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from app.models.workflow import Workflow, WorkflowStep

# Pseudo-nodes: graph markers, not steps.
_PSEUDO_NODE_TYPES = frozenset({"start", "end"})

# Node types with NO runtime representation yet — reject loudly (T-2.0b/later).
# `condition`/`decision` are here because the canvas has no canonical true/false
# edge convention to compile a branch against (deferred to T-2.0b).
_UNSUPPORTED_NODE_TYPES = frozenset({
    "condition", "decision", "branch",
    "parallel_split", "parallel_join",
    "wait", "schedule",
    "cross_tenant_order", "cross_tenant_request", "cross_tenant_acknowledgment",
})

# Node types that ARE a runtime step_type directly.
_ENGINE_STEP_TYPES = frozenset({
    "input", "action", "output", "notification",
    "ai_prompt", "send_document", "playwright_action",
})

# Node types that are an action_type specialization → step_type="action" with
# action_type nested into config (the authoring style where the action IS the
# node type, e.g. node.type="call_service_method").
_ACTION_TYPE_NODE_NAMES = frozenset({
    "create_record", "update_record", "call_service_method",
    "invoke_generation_focus", "invoke_review_focus",
    "notify_via_contact_preference", "log_vault_item", "generate_document",
    "send_email", "send_notification", "open_slide_over", "show_confirmation",
    "create_task", "wait_for_task_completion", "route_on_task_outcome",
    "send-communication",
    # Canvas↔Runtime Bridge T-2.1b-WITNESS — the benign marker action (writes a
    # moc_witness_marker row; real but harmless). Lets a canvas author a compiled
    # task whose only effect is a witness marker.
    "record_marker",
})


class CanvasCompileError(ValueError):
    """A canvas that cannot be compiled to runtime steps — raised LOUDLY, never a
    silent partial-compile. (out-of-subset node / non-linear graph / bad shape)."""


def _node_to_step(node_type: str, config: dict) -> tuple[str, dict]:
    """(node.type, node.config) → (step_type, step_config). Action-type node
    names nest into an action step; engine step types pass through."""
    if node_type in _ENGINE_STEP_TYPES:
        return node_type, dict(config)
    if node_type in _ACTION_TYPE_NODE_NAMES:
        # step_type=action, action_type carried in config (don't clobber an
        # action_type already present).
        return "action", {"action_type": node_type, **config}
    raise CanvasCompileError(
        f"canvas node type {node_type!r} is not a known runtime step or action "
        f"type — cannot compile"
    )


def _ordered_linear_chain(nodes: list[dict], edges: list[dict]) -> list[dict]:
    """Validate the canvas is a single LINEAR chain and return the real
    (non-pseudo) nodes in execution order. Rejects forks, out-of-subset nodes,
    cycles, and disconnected graphs LOUDLY."""
    if not nodes:
        raise CanvasCompileError("canvas has no nodes — nothing to compile")

    by_id: dict[str, dict] = {}
    for n in nodes:
        nid = n.get("id")
        if not nid:
            raise CanvasCompileError("a canvas node is missing its id")
        if nid in by_id:
            raise CanvasCompileError(f"duplicate canvas node id {nid!r}")
        by_id[nid] = n

    # Reject out-of-subset node types up front with a node-specific message.
    for n in nodes:
        nt = n.get("type")
        if nt in _UNSUPPORTED_NODE_TYPES:
            raise CanvasCompileError(
                f"canvas node {n.get('id')!r} is type {nt!r}, which has no runtime "
                f"representation yet — T-2.0 compiles the LINEAR subset only "
                f"(branching/parallel/wait/conditional land in a later phase). "
                f"Refusing to compile a partial workflow."
            )

    # Adjacency + linear (no-fork) enforcement.
    out: dict[str, list[str]] = defaultdict(list)
    indeg: dict[str, int] = {nid: 0 for nid in by_id}
    for e in edges:
        src, tgt = e.get("source"), e.get("target")
        if src not in by_id or tgt not in by_id:
            raise CanvasCompileError(f"edge references unknown node ({src!r} → {tgt!r})")
        out[src].append(tgt)
        indeg[tgt] += 1
    for nid, targets in out.items():
        if len(targets) > 1:
            raise CanvasCompileError(
                f"canvas node {nid!r} has {len(targets)} outgoing edges — T-2.0 "
                f"compiles LINEAR canvases only (no branching / fan-out). "
                f"Refusing to compile."
            )

    # Entry = the `start` node, else the unique node with no incoming edge.
    starts = [n["id"] for n in nodes if n.get("type") == "start"]
    if len(starts) > 1:
        raise CanvasCompileError("canvas has multiple start nodes")
    if starts:
        entry = starts[0]
    else:
        roots = [nid for nid, d in indeg.items() if d == 0]
        if len(roots) != 1:
            raise CanvasCompileError(
                f"canvas is not a single chain — expected one entry node, found "
                f"{len(roots)}"
            )
        entry = roots[0]

    # Walk the single chain, collecting real nodes in order.
    chain: list[dict] = []
    visited: set[str] = set()
    cur: str | None = entry
    while cur is not None:
        if cur in visited:
            raise CanvasCompileError(f"canvas has a cycle at node {cur!r}")
        visited.add(cur)
        node = by_id[cur]
        if node.get("type") not in _PSEUDO_NODE_TYPES:
            chain.append(node)
        targets = out.get(cur, [])
        cur = targets[0] if targets else None

    if len(visited) != len(nodes):
        raise CanvasCompileError(
            f"canvas is not a single connected chain — {len(nodes) - len(visited)} "
            f"node(s) unreachable from the entry. Refusing to compile."
        )
    if not chain:
        raise CanvasCompileError("canvas has no executable steps (only start/end)")
    return chain


def compile_canvas_to_workflow(
    db: Session,
    *,
    canvas_state: dict[str, Any],
    company_id: str,
    name: str,
    source_template_id: str | None = None,
    actor_user_id: str | None = None,
) -> Workflow:
    """Compile a LINEAR canvas → a runnable Workflow + WorkflowStep rows. Rejects
    out-of-subset canvases with CanvasCompileError. Caller commits.

    The compiled workflow's trigger_type is forced to "manual" (scheduler-inert).
    step_key = node.id (preserves the engine's `{output.<step_key>...}` variable
    refs); config is carried verbatim (template vars resolve at run time)."""
    if not isinstance(canvas_state, dict):
        raise CanvasCompileError("canvas_state must be an object")
    nodes = canvas_state.get("nodes") or []
    edges = canvas_state.get("edges") or []

    chain = _ordered_linear_chain(nodes, edges)

    wf = Workflow(
        id=str(uuid.uuid4()),
        company_id=company_id,
        name=name,
        description=(
            f"Compiled on-demand from workflow_template {source_template_id} "
            f"(Canvas↔Runtime Bridge T-2.0). Runtime snapshot — the template "
            f"canvas is the source of truth."
        ),
        # FORCED manual: the bridge invokes this directly; it must NOT be
        # scheduler-visible (never carry the canvas's scheduled/time_of_day
        # trigger).
        trigger_type="manual",
        scope="tenant",
        tier=4,
        is_active=True,
        created_by_user_id=actor_user_id,
    )
    db.add(wf)
    db.flush()

    # Pre-generate step ids so next_step_id can link forward.
    step_ids = {node["id"]: str(uuid.uuid4()) for node in chain}
    for i, node in enumerate(chain):
        step_type, step_config = _node_to_step(node.get("type"), node.get("config") or {})
        next_node = chain[i + 1] if i + 1 < len(chain) else None
        db.add(WorkflowStep(
            id=step_ids[node["id"]],
            workflow_id=wf.id,
            step_order=i + 1,
            step_key=node["id"],
            step_type=step_type,
            config=step_config,
            display_name=node.get("label"),
            next_step_id=step_ids[next_node["id"]] if next_node else None,
        ))
    db.flush()
    return wf
