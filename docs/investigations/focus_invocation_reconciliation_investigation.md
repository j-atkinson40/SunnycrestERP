# Focus-invocation namespace reconciliation + dedupe — Investigation + Phase Plan

**Status:** investigation-only (no code/canon/build/dispatch). HEAD `510d7e8`. Author: Sonnet, 2026-06-02.
**Parent context:** DECISIONS.md `2026-06-02 — Bespoke-namespace divergence + 4-i` (the starting decision: the 2 `invoke_*` types excluded from inline editing, `BespokeNodePane` remnant) + `2026-06-02 — Inline-params phasing model`. The P2b/P3 groundings (`inline_params_investigation.md`, `p3_inspector_retirement_investigation.md` §4) flagged this as the filed-forward arc that removes the remnant.
**Goal as dispatched:** reconcile the namespace divergence so the 2 `invoke_*` types edit inline like the rest (removing `BespokeNodePane`) + dedupe the near-duplicate `generation-focus-invocation` vs `invoke_generation_focus`.

> **Headline finding — the goal is harder than the namespace framing, and the dedupe is sharper.** The divergence is **two problems, not one**: (1) a cheap namespace rename (`focusTemplateName` → `focus_id`), and (2) the **editor SHAPE** (dependent `op_id`-depends-on-`focus_id` dropdowns + a dynamic `kwargs` binding list) which is *why* a bespoke config exists — and which inline tokens / the P3a expand panel cannot fully replace. **Removing `BespokeNodePane` is gated on (2), not (1).** Separately, the dedupe is unambiguous: `generation-focus-invocation` and `invoke_generation_focus` **both declare `extensions.workflowStepType: "invoke_generation_focus"`** — two canvas nodes for one runtime operation; redundant.

---

## 1. The backend contract (the canonical target shape — but a disconnected substrate)

### 1.1 The handlers (cite)
`backend/app/services/workflow_engine.py`:
- **`_handle_invoke_generation_focus`** (`:696-773`) reads `config.get("focus_id")`, `config.get("op_id")`, `config.get("kwargs")` (`:722-724`); requires `focus_id` + `op_id` (errors `missing_dispatch_key` otherwise); calls `dispatch(focus_id, op_id, db=, company_id=, **kwargs)`.
- **`_handle_invoke_review_focus`** (`:776-...`) reads `config.get("review_focus_id")` + `config.get("input_data")` (`:801-802`); requires `review_focus_id`; creates a `WorkflowReviewItem(review_focus_id, input_data, …)`.

### 1.2 What the keys MEAN (cite)
**`focus_id` is a HEADLESS_DISPATCH registry key, NOT a focus-template name.** `dispatch(focus_id, op_id, …)` (`generation_focus/headless_dispatch.py:119-136`) looks `focus_id` up in `HEADLESS_DISPATCH: dict[str, dict[str, _DispatchFn]]` (`:109`), whose one current entry is `"burial_vault_personalization_studio"` (`:110`) with per-`op_id` callables. So `focus_id` = a registered headless-focus id; `op_id` = an operation on it; `kwargs` = arguments to the dispatch callable. This is a different vocabulary from the registry's `focusTemplateName` (a `componentReference` to a `focus-template` registry entry, e.g. `"arrangement-scribe"`). **They are not the same thing semantically** — one indexes the dispatch table, the other names a UI focus-template.

### 1.3 NO backend schema enforces the key names (cite)
The handlers are plain `config.get(...)` reads. A grep of `backend/app/schemas` + `canvas_validator.py` for `focus_id`/`review_focus_id` returns **nothing** — there is no pydantic model, TypedDict, or validator enforcing these config shapes. `canvas_validator.py` validates node *types* (`VALID_NODE_TYPES`) + edge integrity, not config key names. **Implication: a frontend rename suffices for the namespace — nothing backend-side validates the keys.**

### 1.4 THE TWO-SUBSTRATE SPLIT (the deepest finding)
The engine executes **`WorkflowStep` rows** (the W-1 runtime model): `_execute_step` reads `step.step_type` + `resolved_config.get("action_type")` (`:415`, `:644`), and `action_type == "invoke_generation_focus"` dispatches to the handler (`:686`). This is a **different substrate** from the visual editor's **`WorkflowTemplate.canvas_state`** (nodes/edges), which `VALID_NODE_TYPES` + the registry + the bespoke configs govern. **There is no canvas_state → WorkflowStep compiler** (grep: `canvas_state` lives in `workflow_templates/template_service.py` CRUD + `canvas_validator.py`; `WorkflowStep` lives in the old engine + `workflow_fork.py`; nothing bridges them). So:
- The visual-editor workflow templates (canvas_state, what the Workflow Builder edits) are currently **design-time authoring artifacts that do not execute** via the engine.
- The handlers run for `WorkflowStep` rows created by the R-6.0a headless path (config `action_type: "invoke_generation_focus"`), NOT by canvas nodes.
- The bespoke config writes `focus_id` because it was built (R-6.0b) to **mirror the eventual runtime shape** — the `focus_id`/`op_id`/`kwargs` the handler reads — anticipating a future canvas→runtime compile. So `focus_id` is the **forward-looking canonical target**; `focusTemplateName` (registry/template) is the odd one out that no runtime path consumes.

**Consequence for this arc:** the reconciliation is about making the **visual editor self-consistent + aligned to the canonical runtime shape** — it is not blocked by a live runtime contract (nothing executes canvas focus nodes yet), but the runtime shape (`focus_id`/`op_id`/`kwargs`) is the right target to converge on so the future compile is a no-op.

---

## 2. The frontend declarations — the divergence shape (cite)

| layer | `invoke_generation_focus` | `invoke_review_focus` |
|---|---|---|
| **registry configurableProps** (`workflow-nodes.ts:1042-1080` / `1085-1123`) | `focusTemplateName` (componentReference), `inputBinding` (object), `reviewMode` (enum), `timeoutSeconds` (number) | `focusTemplateName`, `inputBinding`, `routingMode`, … |
| **template slot** (`workflow-node-templates.ts`) | `Invoke generation focus {focusTemplateName}` | `Invoke review focus {focusTemplateName}` |
| **bespoke config WRITES** (`InvokeGenerationFocusConfig.tsx` / `InvokeReviewFocusConfig.tsx`) | `focus_id`, `op_id`, `kwargs` | `review_focus_id`, `input_data_binding`, `reviewer_role`, `decision_actions` |
| **backend handler READS** | `focus_id`, `op_id`, `kwargs` | `review_focus_id`, `input_data` |

**The divergence is precise:** the registry + template are the **odd one out** — they declare/slot `focusTemplateName`, a key **nothing else writes and no handler reads**. The bespoke config + the backend handler agree on `focus_id`/`op_id`/`kwargs` (gen) and `review_focus_id` (review). So `focusTemplateName` is a stranded Phase-1 vocabulary.

**Two sub-divergences within the divergence:**
- **Gen:** registry/template say `focusTemplateName`; config + handler say `focus_id` (+ `op_id` + `kwargs`, which the registry doesn't declare at all). The config is a *3-key dependent shape*, not a single renameable token.
- **Review:** `review_focus_id` already matches config↔handler. But the config writes `input_data_binding` (a `{prefix.path}` template string) while the handler reads `input_data` (a resolved dict) — a binding-vs-resolved divergence; plus `reviewer_role`/`decision_actions` are authoring-layer hints the config round-trips for future R-6.x (per its header) that the handler doesn't read.

### 2.1 Why the configs are bespoke — the SHAPE, not just the namespace (the reframe)
`InvokeGenerationFocusConfig` is bespoke because: `op_id`'s valid options **depend on the selected `focus_id`** (the `HEADLESS_FOCUS_CATALOG` per-focus ops list), and `kwargs` is a **dynamic list of source-binding rows** (key + source-type + path). A generic `PropControlDispatcher` enum cannot do dependent options; a generic object control can't do the binding-row UX. `InvokeReviewFocusConfig` similarly has a source-type+path binding builder + a decision-actions checklist. **So even after a namespace rename, these would still need a richer-than-token editor.** The 4-i decision framed the exclusion as "phantom-key (namespace) divergence" — accurate as far as it went, but the *fuller* reason these resist inline editing is the dependent-options + dynamic-list **shape**.

---

## 3. The seed / migration surface (cite)

- **Only `generation-focus-invocation` is seeded** — `seed_workflow_templates_phase4.py:217-228` (the `funeral_cascade` `n_generate_obituary_draft` node), config `{focusTemplateName: "arrangement-scribe", extraction_template: "obituary", reviewMode: "review-by-default"}`. **`invoke_generation_focus` and `invoke_review_focus` are NOT seeded** anywhere.
- **No live tenant data:** the visual-editor workflow templates are platform/vertical-default seeds (the canon dev tenants); there is no canvas→runtime execution, so no production workflow *runs* depend on these canvas configs. The migration surface is **the seed file + the canon dev tenants**, not live tenant operational data.
- **A latent data bug to note:** the seeded `generation-focus-invocation` value `focusTemplateName: "arrangement-scribe"` is itself **semantically wrong against the runtime** — `"arrangement-scribe"` is a focus-template name, but the handler needs a `HEADLESS_DISPATCH` `focus_id` (e.g. `"burial_vault_personalization_studio"`) + an `op_id`. So even today's one seeded focus node would not execute correctly if compiled. The dedupe/reconciliation is the moment to fix it.

**Implication for R-1:** because `invoke_*` are **not seeded**, renaming their registry props (`focusTemplateName` → `focus_id`/`op_id`) is **zero data migration** — the bespoke config already writes `focus_id`/`op_id`/`kwargs`, so a rename just aligns the (currently-stranded) registry/template declarations to what the config + handler already use. The only migration is the **dedupe's** seed fix (the 1 `generation-focus-invocation` node).

---

## 4. The reconciliation options (surface all; do not pick)

The namespace half. Note throughout: the editor-shape half (§2.1) is a separate gate on "remove BespokeNodePane" regardless of which namespace option is chosen.

- **(R-1) Frontend → backend (rename the registry/template to the runtime shape).** Change `invoke_*` registry `configurableProps` + the template slot from `focusTemplateName` → `focus_id` (+ declare `op_id`, `kwargs` to match). Frontend-only; backend + (the absent) `invoke_*` seeds already use `focus_id` → **no backend change, no data migration**. After it, the registry/template/config/handler all speak `focus_id`. **COST:** the template token would reference `focus_id` — but the template *label* can stay human ("Invoke generation focus {focus_id}" reads fine, or the token can render the resolved focus display-name while the key is `focus_id`, the same way `componentReference` tokens already resolve to a display name). **Smallest, lowest-risk — recommended for the namespace half**, confirmed by §1.3 (no backend schema) + §3 (invoke_* not seeded).
- **(R-2) Backend → frontend (rename the handlers to read `focusTemplateName`).** Change `_handle_invoke_*` + migrate the seed + any data. **COST:** backend change + the runtime would then read a UI-template name where it needs a dispatch id — *semantically wrong* (§1.2: `focus_id` indexes `HEADLESS_DISPATCH`, `focusTemplateName` is a UI focus-template). Rejected on semantics, not just cost: the backend key is the *correct* vocabulary.
- **(R-3) Mapping layer (config writes `focusTemplateName`, a translator → `focus_id`).** **COST:** permanent indirection + the focusTemplateName→focus_id mapping has no natural source (a focus-template name is not a dispatch id). Worst option; rejected.

**For all three:** none of them *alone* makes the 2 types inline-editable — that's the §2.1 editor-shape gate. R-1 makes the bespoke config write the keys the registry declares (self-consistency + the inline path *could* then target them), but the dependent-options/kwargs UX still needs a home.

### 4.1 The editor-shape options (the real "remove BespokeNodePane" fork)
- **(E-1) Keep `BespokeNodePane`, reframe it as shape-bespoke (not namespace-bespoke).** After R-1 the pane writes the right keys; it stays because `op_id`-depends-on-`focus_id` + `kwargs`-list genuinely need bespoke UI. The DECISIONS 4-i entry's rationale shifts from "phantom-key" to "dependent-options shape." `BESPOKE_NAMESPACE_TYPES` is renamed/repurposed (e.g. `BESPOKE_SHAPE_TYPES`). **This does NOT remove the remnant — it legitimizes it.** Smallest; honest; but doesn't meet the dispatched goal of removing the pane.
- **(E-2) Build dependent-enum + binding-list capability into the inline editors.** Extend `PropControlDispatcher` / the P3a expand panel with a dependent-enum control (options keyed off another field) + a binding-row-list control. Then the 2 types edit inline via the expand panel; `BespokeNodePane` retires. **Largest; net-new editor substrate; the genuine path to the dispatched goal.**
- **(E-3) Host the bespoke config INSIDE the expand panel.** Instead of a rail pane, render `InvokeGenerationFocusConfig`/`InvokeReviewFocusConfig` in the card's P3a expand panel (the card stays the surface; the rail still shows the palette). Removes the *rail* remnant without rebuilding the editor — the bespoke config moves onto the card. Middle option; keeps the bespoke UI but eliminates the rail-pane exception (the rail becomes uniformly palette for all node-selection). **Plausible sweet spot** — meets "the card is the sole node-editing surface" without an editor rebuild.

---

## 5. The dedupe (the second question — verdict: REDUNDANT, gen only)

### 5.1 The evidence
- `generation-focus-invocation` (hyphenated, Phase-1) — registry `workflow-nodes.ts:21`, `extensions.workflowStepType: "invoke_generation_focus"` (`:102`); dispatches to `RegistryDrivenConfig` (edits inline cleanly via `focusTemplateName`); **IS seeded** (§3); but its `focusTemplateName` value doesn't match the runtime `focus_id`/`op_id` shape.
- `invoke_generation_focus` (R-6.0b) — registry `:1042`, `extensions.workflowStepType: "invoke_generation_focus"` (`:1079`); dispatches to the **bespoke** `InvokeGenerationFocusConfig` (writes `focus_id`/`op_id`/`kwargs`, the runtime shape); excluded from inline (4-i); **NOT seeded**.

**Both declare `workflowStepType: "invoke_generation_focus"`** — i.e. the visual-editor→runtime mapping points BOTH canvas nodes at the SAME runtime action_type. They are **two canvas-authoring representations of one runtime operation** — the Phase-1 placeholder (`generation-focus-invocation`, inline-editable but wrong-namespace + non-runtime-shaped) and the R-6.0b real one (`invoke_generation_focus`, runtime-shaped but bespoke-edited). **Verdict: redundant.**

### 5.2 Which wins
**`invoke_generation_focus` is the keeper** — it carries the correct runtime namespace (`focus_id`/`op_id`/`kwargs`) + the shape-appropriate editor. `generation-focus-invocation` is the vestigial Phase-1 node and should **retire**, with its **1 seed node migrated** to `invoke_generation_focus` + a real `focus_id`/`op_id` (fixing the §3 latent value bug — `"arrangement-scribe"` → a real `HEADLESS_DISPATCH` id + op, or the node re-pointed/removed if obituary-draft isn't a registered headless op). Retiring it means removing it from `VALID_NODE_TYPES` (frontend + backend mirror) + the registry + the template + migrating the seed.
- **≥3-prop rule interaction:** retiring `generation-focus-invocation` is a *node removal*, gated by the same ≥3-configurableProps rule (DECISIONS 2026-05-19 + the 2026-06-02 cross-ref) only if removal would drop a *surviving* type below 3 — not applicable here (we remove the whole type, not its props). No conflict.

### 5.3 Review side — standalone, no dedupe
`invoke_review_focus` has **no hyphenated twin** (`canvas-validator.ts:45` has only `invoke_review_focus`; no `review-focus-invocation`). So the review type needs **namespace/shape reconciliation only** (its `review_focus_id` already matches; resolve `input_data_binding` vs `input_data` + the `reviewer_role`/`decision_actions` authoring-hints), not a dedupe.

---

## 6. Phase plan (the deliverable)

Dependency-ordered; each phase leaves the builder working.

```
Phase 1 (namespace, frontend-only, cheap)  ─┐
                                             ├─→ Phase 3 (editor-shape: remove/relocate the pane)
Phase 2 (dedupe: retire gen-focus-invocation + migrate the 1 seed)  ─┘
```

- **Phase 1 — Namespace reconciliation (R-1), frontend-only.** Rename `invoke_*` registry `configurableProps` + template slots `focusTemplateName` → `focus_id` (declare `op_id`/`kwargs`); align the review keys. No backend change (§1.3), no `invoke_*` data migration (§3). The bespoke configs already write these keys → after this they're self-consistent with the registry. **Small.** Seam: registry/template/config all speak the runtime vocabulary; pane still present. **Frontend-only — no backend grounding needed.**
- **Phase 2 — Dedupe: retire `generation-focus-invocation`.** Remove it from `VALID_NODE_TYPES` (frontend `canvas-validator.ts` + backend `canvas_validator.py` mirror — *this phase touches the backend validator*), the registry, the template; **migrate the 1 seed node** (`funeral_cascade` `n_generate_obituary_draft`) to `invoke_generation_focus` + a correct `focus_id`/`op_id` (or remove/re-point it if no headless op fits "obituary draft"). **Small-medium; backend-touching** (the validator mirror + the seed) → wants a light backend-grounding for the validator change + the seed migration. Seam: one canonical generation-focus node.
- **Phase 3 — Editor-shape (remove/relocate `BespokeNodePane`).** The §4.1 fork: **E-3 (host the bespoke config in the P3a expand panel)** is the recommended sweet spot — removes the rail-pane exception (rail = uniformly palette for node-selection, finishing P3c's intent) without rebuilding the editor; OR **E-2 (dependent-enum + binding-list inline controls)** if true token-level inline editing is wanted (larger, net-new editor substrate). Ungate the 2 types from `BESPOKE_NAMESPACE_TYPES`. **Variable size by option.** Seam: `BespokeNodePane` gone (E-2/E-3) or reframed as shape-bespoke (E-1). **This is the phase that meets the dispatched "remove the remnant" goal; its size depends on the E-fork.**

**Note:** Phase 1 + 2 are the cheap, clearly-scoped half. Phase 3 is where the real cost lives (the editor-shape problem the 4-i framing under-stated). The arc could legitimately ship Phase 1+2 (self-consistent + deduped) and treat Phase 3 (the pane removal) as its own follow-up once the E-fork is decided — the dispatched goal ("remove the remnant") is genuinely Phase 3, and it is not cheap.

---

## 7. Type-B decisions surfaced (for Opus/operator resolution)

1. **Namespace shape:** R-1 (frontend→backend rename, recommended — cheap, no migration, backend key is canonical) vs R-2 (backend→frontend, rejected on semantics) vs R-3 (mapping, rejected).
2. **Template token display:** can the token show a human/resolved label while the key is `focus_id` (like `componentReference` tokens already resolve to a display name), or does the sentence read "{focus_id}"? (Cosmetic; affects whether R-1's token is glanceable.)
3. **The editor-shape fork (the real one):** E-1 (keep the pane, reframe 4-i as shape-bespoke — does NOT remove the remnant) vs E-2 (build dependent-enum + binding-list inline controls — largest, true inline) vs E-3 (host the bespoke config in the P3a expand panel — removes the rail-pane exception without an editor rebuild, recommended sweet spot).
4. **Dedupe verdict:** confirmed **redundant** (both → `workflowStepType: "invoke_generation_focus"`); keeper = `invoke_generation_focus`; retire `generation-focus-invocation`. (Surface only if the operator wants to instead keep the hyphenated one as the inline-editable face — but it carries the wrong runtime namespace, so the recommendation is firm.)
5. **Seed migration of the 1 `generation-focus-invocation` node:** migrate to `invoke_generation_focus` + a real `focus_id`/`op_id` — but **which** `focus_id`/`op_id`? "Obituary draft" may have no registered `HEADLESS_DISPATCH` op (the only entry is `burial_vault_personalization_studio`). Options: re-point to an existing op, register a new headless op, or remove the node from the seed. (Needs a domain call.)
6. **Phase order / scope:** ship Phase 1+2 (namespace + dedupe, cheap) as the arc and treat Phase 3 (pane removal) as a gated follow-up once the E-fork is chosen — vs. one arc through Phase 3.
7. **Review-side `input_data_binding` vs `input_data`:** resolve the binding-string-vs-resolved-dict divergence + decide the fate of the `reviewer_role`/`decision_actions` authoring-hints (kept for future R-6.x per the config header, or dropped).

---

## Summary
- **Backend contract:** handlers read `focus_id`/`op_id`/`kwargs` (gen) + `review_focus_id`/`input_data` (review); **no pydantic schema** enforces the keys (so a frontend rename suffices); `focus_id` is a `HEADLESS_DISPATCH` id, not a focus-template name. **And canvas_state does not execute** — it's a separate substrate from the `WorkflowStep` runtime; the `focus_id` shape is the forward-looking canonical target the bespoke config already mirrors.
- **Divergence:** the registry + template (`focusTemplateName`) are the odd one out; the bespoke config + handler agree on `focus_id`/`op_id`/`kwargs`. **R-1 (rename frontend → the runtime shape) is the smallest, no-migration namespace fix** (invoke_* aren't seeded; no backend schema).
- **But "remove BespokeNodePane" is gated on the editor SHAPE** (dependent `op_id`/`kwargs` UX), not just the namespace — the 4-i framing under-stated this. The §4.1 E-fork (E-3 host-in-expand-panel recommended) is the real cost.
- **Dedupe = redundant, gen only:** `generation-focus-invocation` + `invoke_generation_focus` both map to `workflowStepType: "invoke_generation_focus"`; keep `invoke_generation_focus` (correct runtime namespace), retire the hyphenated Phase-1 node, migrate the 1 seed node (and fix its semantically-wrong `focusTemplateName: "arrangement-scribe"` value). Review type is standalone (no twin).
- **Phases:** 1 (namespace R-1, frontend-only, cheap) ∥ 2 (dedupe + seed migration, backend-validator-touching) → 3 (editor-shape pane removal, the real cost, E-fork-dependent). 1+2 are a clean cheap arc; 3 meets the dispatched remnant-removal goal and is not cheap.
