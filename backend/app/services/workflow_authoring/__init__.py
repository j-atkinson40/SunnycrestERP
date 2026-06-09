"""Workflow authoring — Builder AI Assistant Phase 1a (backend generation).

Natural-language → a valid workflow `canvas_state`, gated by the EXISTING
server-side `validate_canvas_state`. The pilot consumer for a shared
builder-authoring assistant primitive (extraction deferred to consumer #2).

Design (settled in the Phase 0 scoping investigation + the 1a dispatch):
  - EMISSION = whole-config JSON. The model emits a complete `canvas_state`;
    the existing validator + edit pipeline already consume a whole config, so
    no ops-as-tools / reducer extraction.
  - MODEL CALL = reuse `intelligence_service.execute()` (managed prompt,
    tenant-scoping, logging, cost, force-JSON) routed to Sonnet via the prompt's
    `model_preference` ("extraction" → claude-sonnet-4-6) + model-router
    fallback. (The substrate's Sonnet is claude-sonnet-4-6, not the AIService
    id; the route is the substrate-idiomatic selection.)
  - GROUNDING = static node-type vocab + the canvas_state schema + the validator
    rules baked into the seeded prompt (`scripts/seed_workflow_authoring_prompt`)
    + the existing workflow-types (via `list_active_workflow_types`) + the
    NL-entities dump (`serialize_nl_entities`) for legible placeholder bindings.
    The component-registry dump + node-config-prop grounding + the Vault
    binding catalog are deferred (their consumers — widget/focus authoring,
    config-QUALITY tuning — don't exist yet).
  - PROOF SCOPE = valid STRUCTURE (the validator's whole scope: ids, edge
    integrity, acyclicity, container ≤1-parent/no-cycle), NOT node-config
    quality. Bindings/config emit as placeholders for the author (or 1b's
    review loop + a later config-prop grounding) to refine.
"""

from app.services.workflow_authoring.service import (
    generate_workflow_canvas,
    list_active_workflow_types,
    serialize_nl_entities,
)

__all__ = [
    "generate_workflow_canvas",
    "list_active_workflow_types",
    "serialize_nl_entities",
]
