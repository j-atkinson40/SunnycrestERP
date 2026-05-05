"""Canvas state validator — Phase 4 of the Admin Visual Editor.

Validates the JSONB shape stored on `workflow_templates.canvas_state`
+ `tenant_workflow_forks.canvas_state`.

Schema (locked at Phase 4):

    {
      "version": 1,
      "trigger": {
        "trigger_type": "manual" | "event" | "scheduled" | "time_after_event" | "time_of_day",
        "trigger_config": { ... }                # opaque per trigger_type
      },
      "nodes": [
        {
          "id": "n_<slug>",                       # unique within canvas
          "type": "<node_type>",                  # must be in VALID_NODE_TYPES
          "position": { "x": <number>, "y": <number> },
          "config": { ... },                      # node-type-specific
          "label": "<optional display label>"
        },
        ...
      ],
      "edges": [
        {
          "id": "e_<slug>",                       # unique within canvas
          "source": "<node id>",                  # must reference an existing node
          "target": "<node id>",                  # must reference an existing node
          "condition": "<optional expression>",   # for branching edges
          "label": "<optional display label>"
        },
        ...
      ]
    }

Cycles are forbidden by default. To express iteration, edges may
declare `"is_iteration": true` — those edges are excluded from
the cycle check. Phase 4 doesn't render iteration loops in the
admin canvas; the flag is reserved for Phase 5+.

Validation runs at WRITE time (create_template + update_template +
fork_for_tenant). Resolution at READ time assumes a valid payload.
"""

from __future__ import annotations

from typing import Any, Mapping


class CanvasValidationError(ValueError):
    """The canvas_state payload violates schema rules."""


# ─── Node type vocabulary ────────────────────────────────────────


# Composition primitives that the existing engine recognizes
# (workflow_engine.py step_type + action_type dispatch tables) +
# Phase 1 registry workflow-node names. Authoring at admin scope
# can reference any of these. Engine compatibility check happens
# when a tenant adopts the template (Phase 5+).
VALID_NODE_TYPES: tuple[str, ...] = (
    # Trigger pseudo-node (one per canvas; lives in canvas root,
    # but a `start` node can exist as the entry point)
    "start",
    "end",
    # Step types from workflow_engine.py
    "input",
    "action",
    "ai_prompt",
    "send_document",
    "playwright_action",
    "condition",
    "output",
    "notification",
    # Action types (for action nodes the type can be specialized)
    "create_record",
    "update_record",
    "open_slide_over",
    "show_confirmation",
    "send_notification",
    "send_email",
    "log_vault_item",
    "generate_document",
    "call_service_method",
    # Phase 1 registry workflow-node names (canonical admin
    # vocabulary; these subsume the engine's step types when
    # rendering in the admin canvas)
    "generation-focus-invocation",
    "send-communication",
    # Phase 4 cross-tenant workflow primitives
    "cross_tenant_order",
    "cross_tenant_request",
    "cross_tenant_acknowledgment",
    # Common composition nodes
    "decision",
    "branch",
    "parallel_split",
    "parallel_join",
    "wait",
    "schedule",
)


_REQUIRED_TOP_KEYS = {"nodes", "edges", "version"}


# ─── Validator ───────────────────────────────────────────────────


def validate_canvas_state(canvas_state: Mapping[str, Any]) -> None:
    """Raise `CanvasValidationError` if the payload is malformed."""
    if not isinstance(canvas_state, dict):
        raise CanvasValidationError(
            "canvas_state must be a mapping (got "
            f"{type(canvas_state).__name__})"
        )

    # Empty {} is permitted — it represents an empty workflow draft
    # (admin author hasn't added any nodes yet). Treated equivalent
    # to {"nodes": [], "edges": [], "version": 1}.
    if len(canvas_state) == 0:
        return

    missing = _REQUIRED_TOP_KEYS - set(canvas_state.keys())
    if missing:
        raise CanvasValidationError(
            f"canvas_state missing required keys: {sorted(missing)}"
        )

    version = canvas_state["version"]
    if not isinstance(version, int) or version < 1:
        raise CanvasValidationError(
            f"canvas_state.version must be a positive integer, got {version!r}"
        )

    nodes = canvas_state["nodes"]
    edges = canvas_state["edges"]
    if not isinstance(nodes, list):
        raise CanvasValidationError("canvas_state.nodes must be a list")
    if not isinstance(edges, list):
        raise CanvasValidationError("canvas_state.edges must be a list")

    # ── Per-node validation + id uniqueness ──────────────────
    seen_node_ids: set[str] = set()
    for idx, node in enumerate(nodes):
        if not isinstance(node, dict):
            raise CanvasValidationError(
                f"nodes[{idx}] must be a mapping"
            )
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id:
            raise CanvasValidationError(
                f"nodes[{idx}].id must be a non-empty string"
            )
        if node_id in seen_node_ids:
            raise CanvasValidationError(
                f"nodes[{idx}].id duplicates an earlier node: {node_id!r}"
            )
        seen_node_ids.add(node_id)

        node_type = node.get("type")
        if not isinstance(node_type, str) or not node_type:
            raise CanvasValidationError(
                f"nodes[{idx}].type must be a non-empty string"
            )
        if node_type not in VALID_NODE_TYPES:
            raise CanvasValidationError(
                f"nodes[{idx}].type {node_type!r} not in canonical "
                f"VALID_NODE_TYPES set ({len(VALID_NODE_TYPES)} types). "
                f"If this is a new canonical type, add it to "
                f"`canvas_validator.VALID_NODE_TYPES` first."
            )

        position = node.get("position", {})
        if not isinstance(position, dict):
            raise CanvasValidationError(
                f"nodes[{idx}].position must be a mapping"
            )

        config = node.get("config", {})
        if not isinstance(config, dict):
            raise CanvasValidationError(
                f"nodes[{idx}].config must be a mapping"
            )

    # ── Per-edge validation + id uniqueness + ref integrity ──
    seen_edge_ids: set[str] = set()
    for idx, edge in enumerate(edges):
        if not isinstance(edge, dict):
            raise CanvasValidationError(
                f"edges[{idx}] must be a mapping"
            )
        edge_id = edge.get("id")
        if not isinstance(edge_id, str) or not edge_id:
            raise CanvasValidationError(
                f"edges[{idx}].id must be a non-empty string"
            )
        if edge_id in seen_edge_ids:
            raise CanvasValidationError(
                f"edges[{idx}].id duplicates an earlier edge: {edge_id!r}"
            )
        seen_edge_ids.add(edge_id)

        source = edge.get("source")
        target = edge.get("target")
        if not isinstance(source, str) or source not in seen_node_ids:
            raise CanvasValidationError(
                f"edges[{idx}].source {source!r} doesn't reference a "
                f"declared node id"
            )
        if not isinstance(target, str) or target not in seen_node_ids:
            raise CanvasValidationError(
                f"edges[{idx}].target {target!r} doesn't reference a "
                f"declared node id"
            )

    # ── Cycle check (excluding edges flagged as iteration) ──
    _detect_cycles(nodes, edges)


def _detect_cycles(nodes: list, edges: list) -> None:
    """DFS-based cycle detector. Edges with `is_iteration=true`
    are excluded so future iteration loops don't trip the check
    (Phase 4 doesn't render them but the schema reserves the flag).
    """
    # Build adjacency excluding iteration edges
    adj: dict[str, list[str]] = {}
    for node in nodes:
        adj.setdefault(node["id"], [])
    for edge in edges:
        if edge.get("is_iteration") is True:
            continue
        adj.setdefault(edge["source"], []).append(edge["target"])

    # DFS with three-color marking
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {nid: WHITE for nid in adj}

    def visit(nid: str, path: list[str]) -> None:
        if color.get(nid) == GRAY:
            cycle = " → ".join([*path, nid])
            raise CanvasValidationError(
                f"canvas_state contains a cycle: {cycle}. To express "
                f"iteration explicitly, mark the back-edge with "
                f"is_iteration=true."
            )
        if color.get(nid) == BLACK:
            return
        color[nid] = GRAY
        for neighbor in adj.get(nid, []):
            visit(neighbor, [*path, nid])
        color[nid] = BLACK

    for nid in list(color.keys()):
        if color[nid] == WHITE:
            visit(nid, [])
