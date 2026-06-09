"""Seed the workflow-authoring managed prompt (Builder AI Assistant Phase 1a).

Option A idempotent (matches the Phase 6 / 8b / intake seed canon):
  - no prompt           → create prompt + active v1
  - active version, same content → no-op
  - active version, content differs → deactivate + create v(N+1)
  - multiple versions (admin-customized) → skip with a warning

ALSO ensures the Intelligence model routes exist (seed_model_routes) — the
authoring prompt's model_preference="extraction" must resolve to Sonnet, and
the base intelligence seed is not run on staging deploy (railway-start seeds
staging/fh_demo/dispatch/edge_panel only). Running it here makes the authoring
path self-sufficient for the Claude-API e2e.

The system prompt bakes the STATIC grounding (locked decision: static vocab in
the prompt): the node-type vocab (imported from canvas_validator so it tracks
the canonical set at seed time), the canvas_state schema, and the validator
rules. Dynamic grounding (workflow-types, NL-entities, current canvas_state)
arrives via the user_template variables.

Usage:
    cd backend && source .venv/bin/activate
    DATABASE_URL=postgresql://localhost:5432/bridgeable_dev \
        python -m scripts.seed_workflow_authoring_prompt
Refuses to run if ENVIRONMENT=production has no Intelligence infra (it does in
prod; the prompt is platform-global, safe to seed everywhere).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.intelligence import IntelligencePrompt, IntelligencePromptVersion
from app.services.workflow_authoring.service import AUTHORING_PROMPT_KEY
from app.services.workflow_templates.canvas_validator import VALID_NODE_TYPES

# Reuse the canonical model-route seed so "extraction" (→ Sonnet) resolves.
from scripts.seed_intelligence import seed_model_routes

DISPLAY_NAME = "Workflow Authoring — generate canvas_state"
DOMAIN = "authoring"
MODEL_PREFERENCE = "extraction"  # → claude-sonnet-4-6 (Sonnet, force-JSON route)


def _system_prompt() -> str:
    node_types = "\n".join(f"  - {t}" for t in VALID_NODE_TYPES)
    return f"""You are the Bridgeable Workflow authoring assistant. You translate a \
natural-language description of a business workflow into a valid Bridgeable \
workflow `canvas_state` JSON object. You emit STRUCTURE — nodes, edges, and \
(optionally) container groupings. You do NOT need to produce production-ready \
node configuration; emit config values + data bindings as clearly-labelled \
PLACEHOLDERS for a human to wire afterward.

OUTPUT: a single JSON object — the `canvas_state`. No prose, no markdown fences.

canvas_state SCHEMA:
{{
  "version": 1,
  "trigger": {{ "trigger_type": "manual"|"event"|"scheduled"|"time_after_event"|"time_of_day", "trigger_config": {{}} }},
  "nodes": [
    {{ "id": "n_<slug>", "type": "<node_type>", "label": "<human label>", "position": {{ "x": <number>, "y": <number> }}, "config": {{}} }}
  ],
  "edges": [
    {{ "id": "e_<slug>", "source": "<node id>", "target": "<node id>", "label": "<optional>", "condition": "<optional expr>", "is_iteration": <optional bool> }}
  ],
  "containers": [
    {{ "id": "c_<slug>", "label": "<optional>", "members": [{{ "kind": "node"|"container", "id": "<id>" }}], "collapsed": false }}
  ]
}}
`trigger` and `containers` are OPTIONAL. Omit `containers` unless grouping helps.

VALID node `type` values (use ONLY these):
{node_types}

HARD RULES (the server validator rejects violations — your output MUST satisfy all):
  1. Every node `id` is unique and non-empty (convention: "n_<slug>"). Every edge `id` is unique ("e_<slug>").
  2. Every edge `source` and `target` MUST reference a declared node `id`.
  3. The node/edge graph MUST be ACYCLIC. To express an intentional loop, mark the single back-edge with "is_iteration": true (those edges are excluded from the cycle check) — do not create cycles otherwise.
  4. Every node has a `config` object (may be empty `{{}}` or contain placeholders) and a `position` with numeric x,y. Lay nodes out top-to-bottom following control flow; spread parallel branches horizontally. Use NON-NEGATIVE coordinates (x >= 0, y >= 0).
  5. If you emit `containers`: each `members[].id` with kind "node" MUST reference a declared node; a given node or container is a member of AT MOST ONE container; container nesting MUST be acyclic; `collapsed` is a boolean (default false).
  6. Reachability: ensure a `start` (or trigger entry) flows to the terminal node(s); avoid orphan nodes with no path from the entry.

CONFIG + BINDINGS = PLACEHOLDERS: for config values and data bindings, emit a \
short placeholder the author can replace, e.g. {{ "template_key": "TODO:choose-template" }} \
or a binding like "{{{{binding: deceased_name}}}}". Prefer entity/field names from \
the provided NL-entity catalog when a binding is obviously implied. Do not invent \
config keys you are unsure of — a minimal valid config beats a wrong one.

Return ONLY the JSON canvas_state."""


_USER_TEMPLATE = """Author a workflow for vertical "{{vertical}}", workflow_type "{{workflow_type}}".

REQUEST:
{{nl_request}}

Existing workflow types (for naming + context):
{{existing_workflow_types}}

NL-entity catalog (entity types + fields — use for sensible binding placeholders):
{{nl_entities}}

Current canvas_state to EDIT (if generating fresh, this says "none"):
{{current_canvas_state}}

Emit the complete canvas_state JSON now."""

_VARIABLE_SCHEMA = {
    "type": "object",
    "properties": {
        "nl_request": {"type": "string"},
        "vertical": {"type": "string"},
        "workflow_type": {"type": "string"},
        "existing_workflow_types": {"type": "string"},
        "nl_entities": {"type": "string"},
        "current_canvas_state": {"type": "string"},
    },
    "required": [
        "nl_request",
        "vertical",
        "workflow_type",
        "existing_workflow_types",
        "nl_entities",
        "current_canvas_state",
    ],
}


def seed_authoring_prompt(db: Session) -> str:
    """Option A idempotent seed. Returns one of: created / noop / v2 / skip."""
    system_prompt = _system_prompt()

    prompt = (
        db.query(IntelligencePrompt)
        .filter(
            IntelligencePrompt.company_id.is_(None),
            IntelligencePrompt.prompt_key == AUTHORING_PROMPT_KEY,
        )
        .first()
    )
    if prompt is None:
        prompt = IntelligencePrompt(
            company_id=None,
            prompt_key=AUTHORING_PROMPT_KEY,
            display_name=DISPLAY_NAME,
            description="NL → a valid workflow canvas_state (Builder AI Assistant 1a).",
            domain=DOMAIN,
        )
        db.add(prompt)
        db.flush()

    versions = (
        db.query(IntelligencePromptVersion)
        .filter(IntelligencePromptVersion.prompt_id == prompt.id)
        .all()
    )
    active = [v for v in versions if v.status == "active"]

    def _new_version(version_number: int) -> IntelligencePromptVersion:
        return IntelligencePromptVersion(
            prompt_id=prompt.id,
            version_number=version_number,
            system_prompt=system_prompt,
            user_template=_USER_TEMPLATE,
            variable_schema=_VARIABLE_SCHEMA,
            response_schema=None,  # the canvas_validator is the real gate
            model_preference=MODEL_PREFERENCE,
            temperature=0.3,
            max_tokens=8192,  # a whole multi-branch canvas_state needs headroom
            force_json=True,
            supports_streaming=False,
            supports_tool_use=False,
            status="active",
            changelog="Builder AI Assistant Phase 1a — workflow-authoring generation.",
            activated_at=datetime.now(timezone.utc),
        )

    if not versions:
        db.add(_new_version(1))
        db.commit()
        return "created"

    if len(active) > 1:
        db.rollback()
        return "skip"  # admin-customized; don't clobber

    current = active[0] if active else None
    if current is not None and (
        current.system_prompt == system_prompt
        and current.user_template == _USER_TEMPLATE
        and current.model_preference == MODEL_PREFERENCE
        and current.force_json is True
    ):
        return "noop"

    # Content differs (or no active among existing) → deactivate + new version.
    if current is not None:
        current.status = "archived"
    next_n = max((v.version_number for v in versions), default=0) + 1
    db.add(_new_version(next_n))
    db.commit()
    return "v2"


def main() -> None:
    db = SessionLocal()
    try:
        routes_n = seed_model_routes(db)
        result = seed_authoring_prompt(db)
        print(f"[seed_workflow_authoring_prompt] model_routes ensured ({routes_n}); prompt: {result}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
