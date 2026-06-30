# MoC Authoring Assistant — Phase 0 Investigation (read-only scope)

**HEAD:** `0fc8246` · **Date:** 2026-06-30 · **Status:** scope + phased plan. NOT a build.

The operator wants a persistent, page-aware command-bar assistant across all of
MoC/Studio that drafts artifacts from natural language for **review-then-publish**
(not live direct-authoring). End state: all four artifact types. First capability:
**workflows** (highest-value, most complex; its pattern over-covers the simpler 3).

---

## TL;DR — the two headlines

1. **~40% of "draft workflows" already ships.** A "Builder AI Assistant" is live
   (Phases 1a + 1b): `POST /api/v1/workflow-authoring/generate` (tenant) and
   `POST /api/platform/admin/visual-editor/workflow-authoring/generate` (Studio/
   platform) both call `workflow_authoring.generate_workflow_canvas` →
   `intelligence_service.execute("authoring.workflow_canvas")` → **validator-gated**
   → **returns** a canvas_state (does NOT auto-save). The NL→workflow intelligence,
   the prompt, the model route, the validator gate, and review-then-publish-by-
   return are **done**. **Do not rebuild this.** The remaining work is the
   *omnipresent shell* and the *cross-artifact extension*, not the workflow brain.

2. **A drafted workflow canvas is INERT — it does not run.** There is **no
   canvas→runtime compiler.** `canvas_state` (in `workflow_templates`) is the
   Studio/MoC *design* artifact; the executable runtime is a *separate* model
   (`workflows` + `workflow_steps`) the engine runs via `start_run`/`advance_run`.
   We hit this exact seam in 3a.1/3d (Legacy Order's canvas used `create_task`,
   but execution required hand-built `invoke_review_focus` step rows). **The
   JCF-1 "assert it runs" bar is unmeetable for the canvas the assistant drafts**
   — because that canvas never runs. This is finding #2 below and the load-bearing
   reframe of the whole arc. **STOP point — operator decision required.**

---

## The five load-bearing unknowns

### 1. Draft/publish substrate — PARTIAL (review-then-publish exists by return; no persistent-draft status)

`workflow_templates` columns: `id, scope, vertical, workflow_type, display_name,
description, canvas_state (jsonb), version (int), is_active (bool), timestamps,
created_by, updated_by`.

- **No `draft` vs `published` status column.** Lifecycle = write-side versioning:
  saving deactivates the prior active row + inserts a new `is_active=true` row with
  `version+1`. The active row IS live (the editor + MoC render it). There is no
  "saved but unpublished" state.
- **BUT the safety model is already honored a different way:** the authoring
  endpoint **generates and RETURNS** the canvas_state — it does **not** persist.
  The operator reviews the returned canvas in the Studio Workflow editor and saves
  it via the editor's existing PATCH. So "AI never writes a live artifact directly"
  is already true: generate → review-in-editor → save. **Review-then-publish exists
  as an ephemeral-draft-in-the-editor flow.**
- **What does NOT exist:** a *persistent* draft (a saved-but-unpublished row the
  operator can leave and return to, or a review queue of pending AI drafts). If the
  UX needs that, it's net-new — and the codebase has a clean precedent:
  **accounting analysis** (`tenant_accounting_analysis`, `status pending|confirmed`,
  confidence gating, a `confirm` endpoint that transitions pending→confirmed). URN
  engraving verbal-approval and price-list import follow the same "AI drafts →
  `status=pending` → human confirms → publish" shape.

**Verdict:** the minimal review-then-publish (ephemeral, in-editor) is FREE. A
persistent-draft / review-queue substrate is net-new but well-precedented. **Which
one the operator wants is a UX decision, not a blocker.**

### 2. What the AI produces — CANVAS (inert design), NOT runtime. No compiler. ⛔ STOP

| | `canvas_state` (workflow_templates) | runtime (`workflows` + `workflow_steps`) |
|---|---|---|
| What it is | the visual/design artifact | the executable definition |
| Who reads it | Studio Workflow editor, MoC references | the workflow **engine** (`start_run`/`advance_run`) |
| Authored by | the AI assistant (today) + the editor | `POST /workflows` → `_apply_steps`, the fork, seeds |
| Executes? | **NO** | **YES** |

- The existing assistant drafts **canvas_state** → an inert design artifact.
- **No `canvas_state → workflow_steps` compiler exists** (searched: no
  `compile_canvas`, `materialize`, `canvas_to_steps`, etc.). The two models are
  permanently disconnected today.
- **The runtime has its OWN clean authoring path** that DOES run:
  `POST /workflows` (`create_workflow`) and `PATCH /workflows/{id}`
  (`update_workflow`) both call `_apply_steps(db, wf.id, data.steps)` —
  a list of `{step_type, config}` dicts that the engine executes verbatim.
  (`workflows.py` also has a `generate_workflow` at line 601 worth a look in the
  build phase.)

**The fork this forces (operator decision):**

- **Interpretation A — draft the DESIGN (canvas).** The MoC/Studio artifact IS the
  canvas (the MoC's "Legacy Order" etc. are `workflow_templates`). The assistant
  drafts canvas; "publish" = save the active template; it renders in the editor +
  MoC. **The "does it run" bar does NOT apply** — `workflow_templates` were *always*
  design references, never executables. The honest JCF-1 bar here is "**valid
  canvas + publishes + renders**," and the canvas→runtime gap is a *pre-existing,
  separate* problem the assistant neither introduces nor closes. **This is what the
  existing investment targets and is the lower-risk first capability.**
- **Interpretation B — draft an EXECUTABLE workflow that RUNS.** Then the assistant
  must target the **runtime step list** (`data.steps` → `POST /workflows`) with a
  *new* runtime-targeting prompt, OR a **net-new canvas→runtime compiler** must be
  built. This is the only path where "assert it runs to the endpoint that matters"
  (the 3d lesson) is achievable. It is a materially bigger scope.

**The validator gate does not save you here.** A canvas can pass
`validate_canvas_state` and still be semantically wrong/inert (see #3) — exactly
the `create_task`-vs-`invoke_review_focus` class of bug from 3d, where the canvas
was "valid" but staged into a state nothing read.

### 3. The validation surface — STRUCTURE only, not config/runtime correctness

`canvas_validator.validate_canvas_state` enforces:
- Required top keys: `version`, `nodes`, `edges` (+ optional `trigger`, `containers`).
- `node.type ∈ VALID_NODE_TYPES` — **32 canonical types** (the list the AI must not
  invent against; the authoring prompt **bakes this list in** by importing
  `VALID_NODE_TYPES`).
- Edge reference integrity (sources/targets must be real node ids), node-id
  uniqueness, `position >= 0`.
- **Acyclic** graph (three-color DFS; `is_iteration=true` edges excluded).

It does **NOT** enforce:
- **Per-node `config` completeness/correctness.** `config` is "node-type-specific"
  and **opaque to the validator**. An `invoke_review_focus` node missing
  `review_focus_id`, or a node with the wrong `action_type`, passes validation.

**Implication:** the AI's output spec is "structurally valid canvas." That is a
**necessary but far-from-sufficient** contract — the validator catches invented
node types and broken graphs, but not the semantic/runtime errors that actually
bite (the 3d lesson). Any "it's valid" claim from the assistant must be read as
"structurally valid," never "correct" or "runnable."

**How a human authors a workflow in Studio today:** the Studio Workflow editor
(`/studio/:vertical/workflows`, `WorkflowEditorPage`) — a node-list canvas with a
32-type palette, per-node config forms, client-side `validateCanvasState` before
save, then PATCH to `workflow_templates`. The assistant shortcuts the *palette +
config-form* step by emitting the whole canvas; the human still reviews + saves.

### 4. Existing AI-authoring scaffolding — LIVE and wired (Builder AI Assistant 1a/1b)

- **Prompt:** `authoring.workflow_canvas` (seeded by `seed_workflow_authoring_prompt.py`
  into `intelligence_prompts` + `intelligence_prompt_versions`; platform-global,
  `domain="authoring"`, `model_preference="extraction"` → Sonnet, `force_json`,
  temp 0.3, 8192 tokens). System prompt bakes `VALID_NODE_TYPES` + the canvas schema
  + the validator's hard rules. (The second seed,
  `seed_workflow_ai_prompt_example.py`, is unrelated — it seeds an *example workflow*
  using a step-level `ai_prompt` node calling `scribe.extract_first_call`, not the
  authoring path.)
- **Service:** `workflow_authoring.generate_workflow_canvas` — grounds on
  `existing_workflow_types` + an NL-entity catalog, calls
  `intelligence_service.execute`, gates with `validate_canvas_state`, returns
  `{canvas_state, valid, validation_error, ai_status, ai_execution_id,
  ai_latency_ms, model_used}`. Realm-agnostic (`company_id: str | None`).
- **Routes:** tenant `/api/v1/workflow-authoring/generate` (1a) + platform
  `/api/platform/admin/visual-editor/workflow-authoring/generate` (1b).
- **Intelligence substrate** (the clean way to add the other three artifact types):
  `intelligence_service.execute(prompt_key, variables, company_id, caller_module, …)`
  resolves prompt → renders → routes model → calls Anthropic → parses → logs to
  `intelligence_executions`. Adding a focus/widget/document authoring capability =
  **seed one prompt + one `execute` call + one validator** (the registry/model-route/
  logging infra is all reused). No new intelligence infra needed.

**Conclusion: do not build a parallel workflow brain.** The first capability is
~done at the intelligence layer; the gaps are the shell (#5) and the
publish-target decision (#2).

### 5. Command-bar shell + page context — TWO bars exist; neither is the persistent page-aware assistant

- **Tenant `CommandBar`** (`components/core/CommandBar.tsx`, Cmd+K): query→results→
  **close**. Atomic; every action closes the modal. NL overlays (NLCreationMode,
  NaturalLanguageOverlay) **replace** the results view. **Not a persistent
  conversational/drafting surface** without a structural refactor. (Backend
  `POST /api/v1/command-bar/query` already accepts a `context` of `current_page,
  current_entity_type, current_entity_id, active_space_id`.)
- **Admin `AdminCommandBar`** (`bridgeable-admin/components/AdminCommandBar.tsx`,
  mounted in `AdminLayout`): the right *tree* (wraps MoC + Studio + Health). Has a
  static action registry + an **in-modal streaming chat mode** — but it is **not
  page-aware** (no `useLocation`/`useParams`, no context provider) and **not
  persistent across navigation** (in-modal only).
- **Page context exists in routes but isn't threaded to the bar:**
  `parseStudioPath()` → `{vertical, editor, isLive}` (from `/studio/:vertical/:editor`),
  and `/maps/:vertical` for MoC. `StudioShell` consumes these as props; the
  command bar does not. Wiring = add `useLocation()` + `parseStudioPath()` to the
  admin bar + pass into the query/authoring `context`.

**Conclusion: the omnipresent, page-aware, persistent assistant is the net-new
build.** `AdminCommandBar` is the closest surface to extend, but its query→close
modal shape must be restructured (or a sibling persistent pane added) to host a
drafting conversation; page context must be threaded in.

---

## Phased plan

> Sequencing principle (substrate-consumption / follower-velocity): land the
> *shell* + the *first real consumer* (workflows) together so the shell is proven
> by a real artifact, then the other three follow at velocity (each = one prompt +
> one validator + one publish-target, reusing the shell).

**Phase D0 — the publish-target decision (operator, before any build).** Resolve
#2's fork for workflows:
- **D0-A (recommended first):** assistant drafts the **canvas** (design artifact);
  publish = save the `workflow_template`; JCF-1 bar = **valid + publishes + renders
  in editor/MoC** (NOT "runs"). Lower risk, reuses the live 1a/1b brain, matches
  what MoC artifacts already are. The canvas→runtime inertness is documented as a
  pre-existing, separate gap.
- **D0-B (bigger):** assistant drafts the **runtime step list** (`POST /workflows`
  `_apply_steps`) with a new runtime-targeting prompt, so JCF-1 = **it RUNS**. Or
  build a net-new canvas→runtime compiler. Only take this if "drafted workflows must
  execute" is a hard requirement now.
- This choice reshapes every later phase. **Do not start the shell until it's made.**

**Phase A — the persistent, page-aware shell (net-new; serves all 4 types day one).**
- Extend `AdminCommandBar` (or add a sibling persistent pane in `AdminLayout`/
  `StudioShell`) to host a drafting conversation that survives navigation.
- Thread page context: `useLocation()` + `parseStudioPath()`/MoC `:vertical` →
  `{vertical, editor, openArtifactId}` into the request context.
- The shell is artifact-type-agnostic; it dispatches to a per-type authoring
  capability. Only workflows light up first.

**Phase B — workflow drafting through the shell (consume the live 1a/1b brain).**
- Wire the shell → `workflow-authoring/generate` with page context (vertical +
  workflow_type inferred from the open editor).
- Render the returned canvas as a **review** (the draft), with publish = the
  editor's existing save (D0-A) or `POST /workflows` (D0-B).
- **If a persistent draft / review-queue is wanted:** add the
  `accounting_analysis`-shaped substrate (a `*_drafts` table, `status pending|
  published`, a `publish` endpoint). Flag as net-new.
- **Assembly-test-first (JCF-1, the 3d lesson — assert the endpoint that matters):**
  - D0-A: NL → assistant → a canvas that **passes `validate_canvas_state` AND
    saves AND re-loads in the editor/MoC**. (Explicitly NOT "runs" — state plainly
    that the canvas is inert; that's the separate gap.)
  - D0-B: NL → assistant → `workflow_steps` that **`start_run` actually executes to
    completion** (the real "it runs" bar). Reuse the 3a.1 end-to-end harness shape.
  - Either way: assert against the endpoint that matters, not "JSON was produced."

**Phase C — the other three artifact types (velocity; each reuses the shell).**
- Focus, widget, document: each = seed one `authoring.*` prompt (bake its
  validator's rules) + one `intelligence_service.execute` call + one validator gate
  + the shell's existing review-then-publish. Inventory each one's validation
  surface first (the #3 lesson — the AI's spec is whatever the validator enforces;
  know it exactly or the AI invents).

---

## Net-new substrate flagged

1. **The persistent page-aware shell** (Phase A) — the omnipresent assistant is
   net-new; `AdminCommandBar` is query→close, not a persistent drafting pane.
2. **(Conditional) a persistent-draft / review-queue table** (Phase B) — only if
   review-then-publish must outlive an editor session. Precedent:
   `tenant_accounting_analysis` (pending/confirmed).
3. **(Conditional, D0-B only) a canvas→runtime compiler OR a runtime-targeting
   authoring prompt** — only if drafted workflows must EXECUTE. The runtime has a
   clean authoring endpoint (`_apply_steps`), so a runtime-targeting prompt is the
   cheaper of the two; a general canvas→runtime compiler is a large net-new arc.

## The load-bearing spec (for whoever builds)

The AI's output contract = **`canvas_validator.VALID_NODE_TYPES` (32 types) + the
structural rules in `validate_canvas_state`** (top keys, edge integrity, acyclicity,
id uniqueness, position≥0). The prompt already bakes these. **The validator does NOT
check per-node `config`** — so structural validity ≠ runnable. Treat every "valid"
as "structurally valid."

---

## STOP

Per the Phase-0 stop discipline, both reshaping findings hold and are stated plainly:

- **(a) No draft/publish *status* substrate** — review-then-publish exists only as
  ephemeral in-editor review of a returned canvas. A persistent draft/queue is
  net-new (well-precedented).
- **(b) Canvas does not compile to runtime** — the drafted canvas is INERT; the
  "it runs" bar is unmeetable for canvas. Executable drafts require targeting the
  runtime step list (clean endpoint exists) or a net-new compiler.

These are scope decisions above "add an authoring assistant" — chiefly **D0** (does
a drafted workflow need to *run*, or is a valid *design* the bar?). **No build,
prompt-engineering, or seeding performed.** The plan is the deliverable; the next
move is the operator's D0 call.
