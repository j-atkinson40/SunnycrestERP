# P3 — Inspector Retirement: Investigation + Phase Plan

**Status:** investigation-only (no code/canon/build/dispatch). HEAD `da32bf5` (P2b shipped). Author: Sonnet, 2026-06-02.
**Parent map:** `docs/investigations/inline_params_investigation.md` §5–§6 sketched P3; this doc is the full retirement map + phase plan that 8e-style phased dispatches are cut from.
**Operator framing:** retire the node inspector (`NodeConfigForm`) so the card is the sole node-editing surface. Rail end-state = palette (none AND node) + EdgeConditionInspector (edge) + TriggerInspector (background). Edge editing goal = **drag-to-connect** (real canvas edge-drawing), accept P3 splits, drag-to-connect possibly its own sub-arc.

### Locked decisions (operator, 2026-06-02) — the committed map reflects these
- **§4 bespoke fork → (4-i) RESOLVED:** retire-for-31 + a narrow `invoke_*` bespoke pane. P3 delivers without serializing behind the reconciliation arc; the narrow pane disappears when the filed-forward "Focus-invocation namespace reconciliation + dedupe" arc runs. (4-ii rejected.)
- **§2 type/id → RESOLVED: DROP both.** Operator never changes a node's type in place (deletes + re-adds via the palette) and never hand-edits ids. Type-change → delete + re-add (no affordance); id → auto-only (no affordance). **So P3a relocates LABEL only** (inline title edit), not type/id.
- **Phase sequencing (operator-likely):** P3a ∥ P3b are independent; operator will sequence **P3a first** (the hard precondition, lowest risk) → **P3b-1** (draw) → **P3b-2** (canvas delete) → **P3c** (retire + collapse rail).
- **Still open, resolved at their phase grounding:** un-slotted-param home shape (recommended **card expand panel** — confirm at P3a grounding); #4 handle disambiguation (resolved in principle as **origin-based stopPropagation** — confirm at P3b-1 grounding); #8 is_iteration-on-cycle-drop (P3b-1).

---

## 0. What ships today (the retirement target)

`NodeConfigForm.tsx` (214 LOC) owns **five** responsibilities, rendered top-to-bottom (`NodeConfigForm.tsx:67-213`):

1. **Type select** (`:73-84`) — `onPatch({type})` over `VALID_NODE_TYPES` (33 types).
2. **Node id input** (`:94-100`) — `onPatch({id})`.
3. **Label input** (`:110-115`) — `onPatch({label})` (the grow-to-fit title).
4. **Per-type config** (`:122-138`) — dispatch: `invoke_generation_focus` → `InvokeGenerationFocusConfig`; `invoke_review_focus` → `InvokeReviewFocusConfig`; else → `RegistryDrivenConfig`. All emit `onPatch({config: next})`.
5. **Outgoing edges** (`:140-211`) — list + per-edge remove (`onRemoveEdge`) + add-by-target-`<select>` (`onAddEdge`).

The rail dispatch (`WorkflowEditorPage.tsx:1004-1030`) is already a 4-arm selection switch:
- `selectedNode` → `NodeConfigForm`
- `selectedEdge` → `EdgeConditionInspector`
- `selection.kind === "background"` → `TriggerInspector`
- else (none) → `WorkflowNodePalette`

**P1/P2a/P2b already relocated responsibility #4 PARTIALLY** — slotted config params edit inline on the card (`NodeLabelSentence` → popover → `PropControlDispatcher` → `onUpdateNodeConfig` → `handleUpdateNode({config})`). Retirement must relocate the **rest of #4** (un-slotted params, §1 below) + **all of #1/#2/#3/#5**, then flip the node arm of the rail switch from `NodeConfigForm` to `WorkflowNodePalette`.

The mutation substrate is uniform and reusable everywhere: every edit (config, label, type, id, edge add/remove/update, trigger) flows through `setDraftCanvas` → the dirty/auto-save path. No new mutation API is needed for any relocation (`WorkflowEditorPage.tsx:464-522`).

---

## 1. CONFIG PARAMS — the un-slotted-param gap (the headline P3a finding)

P1/P2a/P2b made **slotted** params editable. But the 32 templates were authored as **headline summaries** (parent §7) — they slot only the 1–3 most salient params per type. Every **un-slotted semantic param edits ONLY in the inspector today.** Retiring the inspector strands them unless they get an inline home.

### 1.1 Full enumeration — un-slotted semantic params per type

Derived from `NODE_LABEL_TEMPLATES` (slots) vs the registry's semantic params (configurableProps − VESTIGIAL_VISUAL set, per parent §2.3). "Un-slotted" = a real, editable semantic param with **no inline surface**.

| type | slotted (inline today) | UN-SLOTTED (inspector-only) | propType of un-slotted |
|---|---|---|---|
| start | — | — | — |
| end | terminalStatus | — | — |
| input | — | inputSchema, required | object, boolean |
| output | — | outputBinding | object |
| wait | durationSeconds | waitMode, eventBinding | enum, string |
| schedule | scheduleMode | cronExpression, delaySeconds | string, number |
| action | actionType | parameters | object |
| ai_prompt | promptKey, model | temperature, maxTokens | number, number |
| send_document | templateKey, recipientBinding, deliveryChannel | — | — |
| send_email | templateKey, recipientBinding | subjectBinding, maxRetries | string, number |
| send_notification | recipientBinding, channel | templateKey | string |
| send-communication | templateKey, recipientBinding, channel | maxRetries, retryBackoffSeconds | number, number |
| notification | recipientRole, message | severity | enum |
| show_confirmation | title | body, confirmLabel | string, string |
| open_slide_over | slideOverKey | contextBinding | object |
| playwright_action | scriptKey | timeoutSeconds, retryOnFailure | number, boolean |
| create_record | entityType | fieldBindings | object |
| update_record | entityType, recordIdBinding | fieldBindings | object |
| log_vault_item | itemType, titleBinding | bodyBinding | string |
| generate_document | templateKey, outputFormat, entityBinding | — | — |
| call_service_method | serviceMethodKey | kwargsBinding, timeoutSeconds | object, number |
| generation-focus-invocation | focusTemplateName | inputBinding, reviewMode, timeoutSeconds | object, enum, number |
| invoke_generation_focus | *(bespoke — §4)* | *(bespoke — focus_id/op_id/kwargs)* | — |
| invoke_review_focus | *(bespoke — §4)* | *(bespoke — review_focus_id/…)* | — |
| cross_tenant_order | targetTenantBinding | orderPayloadBinding, acknowledgmentRequired | object, boolean |
| cross_tenant_request | requestType, targetTenantBinding | payloadBinding | object |
| cross_tenant_acknowledgment | sourceRequestBinding, acknowledgmentStatus | — | — |
| condition | expression | trueLabel, falseLabel | string, string |
| decision | branches | defaultBranch | string |
| branch | conditionExpression | — | — |
| parallel_split | branchCount | waitForAll | boolean |
| parallel_join | joinPolicy | threshold | number |

**Scale of the gap:** ~24 of the 33 types have ≥1 un-slotted semantic param. Only **6** types are fully covered inline today (start, end, send_document, generate_document, branch, cross_tenant_acknowledgment). **So "show all params" is NOT optional polish — it is a hard precondition for retirement.** Without it, retiring the inspector silently removes the only editor for ~40 distinct params.

**Note — the un-slotted set is mostly simple + object, all dispatcher-handled.** Every un-slotted propType above is one of `{string, enum, number, boolean, object}` — all already rendered by `PropControlDispatcher` (P2a + P2b). No new control bodies are needed; the un-slotted-param home is a *surfacing* problem, not a *control* problem. This is the single most important de-risking finding in §1.

### 1.2 The decision — how un-slotted params get an inline home (Type-B)

- **(1-i) Card "show all params / expand" affordance.** A disclosure on the card (e.g. a "⋯ N more" chevron under the sentence) expands a compact list of the un-slotted params as additional editable rows — each reusing `PropControlDispatcher` exactly like the popover tokens. *Implication:* one mechanism covers all ~24 types uniformly; the card grows (grow-to-fit already measures height, so this composes); the expand state is per-node ephemeral UI (not persisted). The expanded rows are NOT sentence tokens — they're a labeled `param: control` mini-form scoped to the card. **Recommended** — it's the smallest uniform home and the dispatcher already renders every needed control.
- **(1-ii) Per-param "more" popover off the card.** A single "⋯" opens one popover hosting all un-slotted params. *Implication:* keeps the card visually minimal; but a popover hosting 3 controls (e.g. generation-focus-invocation's inputBinding+reviewMode+timeoutSeconds) is essentially a mini-inspector-in-a-popover — at which point it's closer to "the inspector didn't die, it moved into a popover." Reasonable, but blurs the retirement.
- **(1-iii) Some params stay inspector-only → inspector partially survives.** Declare object-plumbing params (the bindings) "advanced," keep a slim inspector for them. *Implication:* the inspector does NOT fully retire — contradicts the operator's stated goal. Only choose if (1-i) proves to strain a specific param type (none identified — all un-slotted types are dispatcher-handled).

The §1.1 finding (all un-slotted propTypes are dispatcher-handled simple+object) means **(1-i) is low-risk**: the expand panel is a list of `PropControlDispatcher` instances keyed on the un-slotted param names, persisting via the same `onUpdateNodeConfig` whole-key merge. The only genuinely large surface is an object param's JSON textarea (`inputBinding`, `fieldBindings`, etc.) — but those render the same `ObjectControl` already shipped in P2b, and real seeded data is small (1–2 keys, per the P2b grounding).

---

## 2. LABEL / TYPE / ID

> **RESOLVED (operator, 2026-06-02):** DROP both in-place type-change and manual id-edit. P3a relocates **LABEL only** (§2.1). Type → delete + re-add via palette (2-ii-a). Id → auto-only (2-iii-a). §2.2/§2.3 options retained below for rationale; the recommended option is the locked choice.

### 2.1 Label (`node.label`) — smallest, clear mechanism
The optional bold title above the sentence (`GraphCanvas.tsx:784-791`). Relocate to **inline card-title edit**: double-click the title (or a click-to-edit affordance) → inline `<input>` → `onUpdateNodeConfig`-sibling `handleUpdateNode(id, {label})`. The mutation path already exists (`handleUpdateNode` takes `Partial<CanvasNode>`, so `{label}` works verbatim). When `node.label` is empty, the title line isn't rendered today — the editor needs an "add a name" affordance (e.g. a faint "name this node" placeholder on hover/selection). Smallest of the five relocations; no new substrate.

### 2.2 Type (`node.type`) — surface whether it's a needed flow
Today: a `<select>` over `VALID_NODE_TYPES` (`:73-84`). Changing a node's type in place is **rare and semantically fraught** — the config shape is type-specific (an `ai_prompt`'s `{promptKey, model, …}` is meaningless on a `wait` node), so an in-place type change orphans the old config. Options:
- **(2-ii-a) Drop in-place type change** — to change a node's type, delete it + re-add from the palette (the palette is always present in the rail). *Implication:* zero new affordance; the orphaned-config problem disappears (a fresh palette-add starts clean). **Recommended** unless the operator reports actually changing types in place.
- **(2-ii-b) Keep a small on-card/peek "change type" affordance** — a type pill on the card opens a type picker. *Implication:* must decide config-carry-over semantics (clear config? attempt to map shared keys?) — non-trivial. Only build if type-change is a real workflow.

**Surface to operator:** *do you ever change a node's type in practice, or always delete + re-add?* The answer collapses this to (2-ii-a) (almost certainly).

### 2.3 Id (`node.id`) — surface drop-vs-keep
Today: a free-text `<input>` (`:94-100`). Node ids are referenced by edges (`edge.source`/`edge.target`) and by parameter bindings (`{output.<nodeId>.…}` in configs). **Editing an id in place is dangerous** — it silently breaks every edge + binding that references the old id (the validator would then reject the dangling edge refs at `canvas-validator.ts:158-167`). Options:
- **(2-iii-a) Auto-only — drop manual id edit.** Ids are generated at node-add (the palette's `handleAddNode` already assigns `n_<…>`). *Implication:* removes a footgun; ids become opaque (consistent with the Shortcuts "hide the n_ id" treatment the card already applies). **Recommended.**
- **(2-iii-b) Keep an affordance** with cascade-rename (rewrite all referencing edges + bindings on id change). *Implication:* real work (binding-string rewriting is a parse/replace across all configs) for a rare advanced flow. Not worth it unless requested.

**Surface to operator:** *is manual id editing ever used?* Almost certainly drop (2-iii-a).

---

## 3. EDGES — drag-to-connect (the big gate)

### 3.1 Current edge model (cite)
- **Storage:** `canvas_state.edges: Array<{id, source, target, condition?, label?, is_iteration?}>` (`canvas-validator.ts:143-168`; `workflow-templates-service` CanvasEdge).
- **Render:** SVG cubic-bezier per edge (`GraphCanvas.tsx:447-535`) via `computeEdgePath` (`canvas-layout.ts:212-230`) — departs **source bottom-center** (`sx=x+w/2, sy=y+height`), arrives **target top-center** (`tx=x+w/2, ty=y`). Arrowhead marker; `is_iteration` edges dashed + accent-stroked. SVG layer is `pointer-events:none`; each edge's transparent **12px hit-stroke** re-enables `pointer-events:stroke` for click selection (B-5, `:509-522`).
- **Create (today):** inspector `<select>` of candidate targets + "Edge" button → `onAddEdge(source, target)` → `handleAddEdge` appends `{id, source, target}` (no condition) (`WorkflowEditorPage.tsx:478-491`). Candidate targets exclude self + already-connected (`NodeConfigForm.tsx:61-65`).
- **Remove (today):** per-edge trash in the inspector list → `handleRemoveEdge(edgeId)` filters (`:493-500`). **B-5 edge SELECTION exists** (click the hit-stroke → `onSelectEdge` → EdgeConditionInspector), but there is **no delete-from-canvas** yet — deletion is inspector-only.
- **Validate:** `validateCanvasState` runs reference-integrity (every edge.source/target must be a declared node) + **three-color-DFS cycle detection** excluding `is_iteration=true` edges (`canvas-validator.ts:170-212`). Already wired as the inline validation banner (`GraphCanvas.tsx:361-368`). Backend mirror at `canvas_validator.py`.

### 3.2 What drag-to-connect requires vs what the substrate already gives

| requirement | substrate today | net-new for P3b |
|---|---|---|
| **anchor points** edges attach to | fixed: source bottom-center, target top-center (`computeEdgePath`) | render visible **connection handles** at those anchors (a small dot at card bottom = source out-handle; card top = target in-handle) |
| **transform-correct dragging** | pan+zoom is `translate+scale` on the surface; nodes drag via dnd-kit under that transform | the drag-preview edge must compute cursor position in **canvas coords** (un-project the screen point through `view.panX/panY/zoom`) — the un-projection math is the inverse of the existing `transform` |
| **a drag interaction** (down on out-handle → preview edge follows cursor → up on a target node/in-handle → create) | none (node-body drag is node-move; nothing on handles) | the full pointer gesture: start on handle, track a "pending edge" preview path, hit-test the drop target, commit |
| **edge validation on drop** | `validateCanvasState` (cycle + ref-integrity) already runs | call it on the **candidate** canvas (current + the new edge); reject (or offer `is_iteration`) if it throws a cycle; reject self-edges + duplicates (the candidate-target filter logic from `NodeConfigForm.tsx:61-65` becomes the drop-validity check) |
| **edge deletion on canvas** | edge SELECTION (B-5) exists; no delete | a delete affordance on the **selected** edge (Del key when an edge is selected, or a small × at the edge midpoint) → `handleRemoveEdge` (exists) |
| **edge condition/label edit** | EdgeConditionInspector (B-5) — **stays, see §5** | — (creation ≠ condition-editing; orthogonal) |

So a meaningful fraction is already present: the edge render, the cycle/ref validator, edge selection, the remove handler, and the pan/zoom transform whose inverse we need. **Net-new is concentrated in: (a) connection handles, (b) the drag gesture + preview-edge + drop hit-test + coord un-projection, (c) wiring delete to selected-edge.**

### 3.3 The core interaction-design question: handle-drag vs body-drag disambiguation

The canvas already binds **node-body drag** to node-move via dnd-kit `useDraggable` (the whole card is the drag handle — `GraphCanvas.tsx` comment §"the node card is the drag handle"; 3px PointerSensor). Drag-to-connect introduces a **second** drag meaning on the same node. They must disambiguate by **where the drag starts**:
- drag starts on the **card body** → move the node (existing dnd-kit `useDraggable`).
- drag starts on a **connection handle** (the small anchor dot) → draw an edge (new gesture).

Two viable disambiguation mechanisms (Type-B):
- **(3-iii-a) Handles are separate elements that stop dnd-kit.** The out-handle dot is a sibling element with its own `onPointerDown` that `stopPropagation`s (so dnd-kit's draggable on the card body doesn't engage) + starts the edge-draw gesture. *Mirrors the proven P2a token pattern* — the clickable token already `stopPropagation`s onPointerDown so a token click doesn't start a node drag (`NodeLabelSentence.tsx:74,87-88`). **The exact same guard works for handles.** Recommended — it reuses a proven disambiguation.
- **(3-iii-b) A modifier or mode toggle** (e.g. hold a key, or an "connect mode" toggle) switches body-drag to edge-draw. *Implication:* a mode is heavier UX; only if handles prove too fiddly at small zoom.

The pan/zoom gesture is already disambiguated from both (it only engages on a **direct surface** pointer-down, `target === currentTarget` — `GraphCanvas.tsx:242`), so handles + node-body + background are three already-separable pointer origins. Adding edge-draw as a fourth (handle-origin) composes with the existing three-way split.

**Why dnd-kit is NOT the right tool for the edge gesture:** dnd-kit models *position translation* of a dragged element (it gave us node-move + the FF widget canvas). An edge-draw is not translating an element — it's a transient preview path from a fixed anchor to a moving cursor, ending in a hit-test. This is the same lesson as DECISIONS 2026-05-21 ("@dnd-kit transform model is position-only; dimensional/rotational/skew gestures require state-mediated rendering"). **Edge-draw is a state-mediated pointer gesture** (like pan), NOT a dnd-kit draggable — implement it with raw `onPointerDown/Move/Up` on the handle + a `pendingEdge` state slot rendering a preview path, exactly as pan was implemented (`GraphCanvas.tsx:237-308`). This is a load-bearing architectural call: do not try to express edge-draw as a dnd-kit draggable.

### 3.4 Size — drag-to-connect is its own sub-arc, plausibly split

This is comparable to or larger than pan+zoom. Proposed internal split (each a working seam):
- **P3b-1 — Connection handles + edge-draw gesture + preview + drop-create + validation.** The core: render handles, the state-mediated draw gesture (coord un-projection through the view transform), preview path, drop hit-test, `validateCanvasState` on the candidate, commit via `handleAddEdge`. Largest piece. ~400–550 LOC + Playwright (the gesture is pointer-under-transform, jsdom-weak — same Playwright-deferred posture as pan+zoom; the pure pieces — un-projection math, drop-validity predicate — are vitest-covered).
- **P3b-2 — Canvas edge deletion.** Wire Del-key / midpoint-× on the selected edge → `handleRemoveEdge`. Small (~80–150 LOC); depends on B-5 selection (present). Could fold into P3b-1 if small enough, but cleaner as its own seam since it's independent of the draw gesture.

`is_iteration` handling: when a drop would create a cycle, the validator throws. The drop handler can either reject, or **offer to mark the new edge `is_iteration=true`** (the validator excludes those from cycle detection). Surfacing that choice is a small UX addition inside P3b-1.

---

## 4. THE 2 BESPOKE `invoke_*` TYPES — the retirement dependency

`invoke_generation_focus` + `invoke_review_focus` author a **different config namespace** than their template slots (P2b finding): bespoke configs write `config.focus_id`/`config.review_focus_id`/`kwargs`/`decision_actions`/…, while the template slots `{focusTemplateName}` (a key the bespoke path never writes). P2b **excluded** them from inline editing (`BESPOKE_NAMESPACE_TYPES`). Their config is editable **only** via `InvokeGenerationFocusConfig`/`InvokeReviewFocusConfig` in the inspector today.

**So full inspector retirement has a hard dependency here.** Two paths (**(4-i) RESOLVED — operator, 2026-06-02; (4-ii) rejected**):

- **(4-i) — LOCKED. Retire-for-31, keep a narrow bespoke inspector for these 2 types.** The rail's node arm shows the palette for all types EXCEPT `invoke_*`, which still show their bespoke config. *Implication:* `NodeConfigForm` shrinks to a 2-type bespoke shell (drops type/id/label/edges/RegistryDrivenConfig — those relocate); the inspector doesn't fully die but becomes a tiny `invoke_*`-only pane. The card is the sole editing surface for 31 of 33 types; 2 types keep a pane. Honest + shippable without the reconciliation arc. The filed-forward "Focus-invocation namespace reconciliation + dedupe" arc *removes this last pane* when it runs.
- **(4-ii) — REJECTED. Run the reconciliation arc FIRST.** Would make `invoke_*` edit inline before P3c, but **serializes P3 behind a separate backend-contract-grounded arc**. Rejected to avoid the serialization; the cleaner end-state arrives later via the filed-forward arc instead.

---

## 5. THE RAIL END-STATE

The rail dispatch (`WorkflowEditorPage.tsx:1004-1030`) becomes:

| selection | today | after P3 |
|---|---|---|
| **node** | `NodeConfigForm` | **`WorkflowNodePalette`** (edits happen on the card) — *except* `invoke_*` under (4-i) → narrow bespoke pane |
| **edge** | `EdgeConditionInspector` | `EdgeConditionInspector` **(unchanged)** |
| **background** | `TriggerInspector` | `TriggerInspector` **(unchanged)** |
| **none** | `WorkflowNodePalette` | `WorkflowNodePalette` **(unchanged)** |

So the rail is **not** pure-palette: edge.condition + trigger are not node config, their inspectors stay. The node arm collapses into the none arm (both show the palette). Net change to the switch: one branch (`selectedNode ? NodeConfigForm`) becomes `selectedNode && !isBespoke ? <bespoke> : <palette>`, and `NodeConfigForm` is deleted.

**Edge CREATION (drag-to-connect, §3) vs edge CONDITION-editing (EdgeConditionInspector) are distinct concerns and both persist:**
- creating an edge = the §3 canvas gesture → `handleAddEdge`.
- editing an existing edge's condition/label = select the edge → `EdgeConditionInspector` → `handleUpdateEdge` (unchanged).
They never conflict — one is a canvas drag, the other a rail panel on selection.

---

## 6. PHASE BREAKDOWN (core deliverable)

Discipline (same as P1→P2): **the inspector stays fully functional until each replacement is proven.** Nothing is removed until its inline replacement ships + is tested. Working-at-every-step.

### Dependency order
```
P3a (un-slotted home + label)  ─┐
                                 ├─→ P3c (remove NodeConfigForm + collapse rail)
P3b (drag-to-connect: P3b-1 + P3b-2)  ─┘   ↑ gated on §4 = (4-i) LOCKED → narrow invoke_* pane
```
P3a and P3b are **independent** (config/identity relocation vs edge relocation). **Operator-locked sequencing:** P3a **first** (the hard precondition, lowest risk) → P3b-1 → P3b-2 → P3c. P3c depends on BOTH being complete; the §4 bespoke decision is RESOLVED (4-i), so P3c ships retire-for-31 with the narrow `invoke_*` pane (no wait on the reconciliation arc).

### Phases

**P3a — un-slotted-param inline home + label relocation.** [config + identity, additive]
- Card "show all params" expand (1-i): a disclosure rendering the un-slotted semantic params as `PropControlDispatcher` rows, persisting via the existing `onUpdateNodeConfig` whole-key merge. Reuses every shipped control (the un-slotted set is all dispatcher-handled — §1.1).
- Inline label edit (2.1): click-to-edit card title → `handleUpdateNode({label})`.
- Type + id: **DROPPED (locked §2)** — no affordance built. P3a documents "delete + re-add via palette to change type; ids are auto-only." This removes scaffolding intent from P3c, not P3a (P3a just doesn't add type/id inline homes; the inspector's type/id inputs are deleted in P3c).
- **Stays working:** inspector untouched — it's still the full editor; P3a adds the inline homes alongside. **Seam:** every config param + label now editable on the card; inspector redundant for config+label but still mounted. **Gates:** vitest (expand renders un-slotted params per type; each persists via whole-key merge; label edit persists), tsc, build, full-suite streak. **LOC:** ~300–430 (label-only relocation trims the upper end vs the original type/id-inclusive estimate).

**P3b-1 — drag-to-connect (handles + gesture + preview + drop-create + validation).** [edges, the big one]
- Connection handles at the existing anchors; state-mediated edge-draw gesture (raw pointer + `pendingEdge`, NOT dnd-kit — §3.3); coord un-projection through the view transform; preview path; drop hit-test; `validateCanvasState` on the candidate (cycle → reject or offer `is_iteration`); commit via existing `handleAddEdge`. Handle pointer-down `stopPropagation`s to not trigger node-body drag (the proven P2a token guard).
- **Stays working:** the inspector's edge `<select>` add still works in parallel (two ways to add an edge during the seam). **Seam:** edges can be drawn on canvas; inspector edge-add redundant but present. **Gates:** vitest (un-projection math; drop-validity predicate; is_iteration offer logic), Playwright-deferred (the pointer-under-transform gesture, same posture as pan+zoom), tsc/build/streak. **LOC:** ~400–550. *This is the largest phase — if it overruns, split the `is_iteration`-offer + handle-affordance polish into a P3b-1b.*

**P3b-2 — canvas edge deletion.** [edges, small]
- Del-key / midpoint-× on the **selected** edge (B-5 selection exists) → existing `handleRemoveEdge`. **Stays working:** inspector edge-remove still present in parallel. **Seam:** edges fully manageable on canvas. **Gates:** vitest (selected-edge delete → handleRemoveEdge), tsc/build/streak. **LOC:** ~80–150. *Could fold into P3b-1 if the budget allows; kept separate for a clean seam.*

**P3c — remove `NodeConfigForm` + collapse the rail.** [the retirement; gated]
- Flip the rail node arm: `selectedNode && !BESPOKE → WorkflowNodePalette` (same as none); under (4-i), `invoke_*` → a narrow retained bespoke pane (the shrunk `NodeConfigForm` reduced to its `invoke_*` dispatch only, or a new tiny `BespokeFocusConfigPane`). Delete the type/id/label/RegistryDrivenConfig/edge-list scaffolding from `NodeConfigForm`.
- Remove the now-redundant inspector edge-add/remove `<select>`/list (relocated to canvas in P3b).
- **Precondition (no broken-editing window):** P3a (all config+label inline) + P3b-1/P3b-2 (edges on canvas) complete + tested, AND the §4 bespoke decision made. **Stays working:** every edit has a proven non-inspector home before removal. **Seam:** inspector gone; rail = palette(none/node) + edge + background (+ narrow bespoke pane under 4-i). **Gates:** the existing NodeConfigForm/WorkflowEditorPage test suites updated (node selection now shows palette), all neighbor suites green, tsc/build/streak. **LOC:** ~200–350 (mostly deletion + the rail-arm flip + the narrow bespoke pane).

### Is P3b too big as one phase?
Yes — split into P3b-1 (draw) + P3b-2 (delete) as above; P3b-1 itself may shed an `is_iteration`/polish P3b-1b if it overruns the ceiling. The draw gesture is the irreducible core.

### Does the bespoke question force the reconciliation arc before P3c?
**No, under (4-i)** — P3c ships retire-for-31 with a narrow `invoke_*` pane; the reconciliation arc later removes that last pane. **Yes, under (4-ii)** — P3c waits on reconciliation. Recommend (4-i) to avoid serializing P3 behind a separate backend-grounded arc.

---

## 7. TYPE-B DECISIONS

**RESOLVED (operator, 2026-06-02):** #2, #3, #6, #7 (sequencing). **Open, resolved at phase grounding:** #1, #4, #5, #8.

1. **Un-slotted-param home (§1.2):** card expand (1-i, **recommended**) vs more-popover (1-ii) vs inspector-partially-survives (1-iii). → *open; confirm at P3a grounding.*
2. **Type-change flow (§2.2):** ✅ **RESOLVED — DROP in-place change** (2-ii-a; delete + re-add via palette). Operator never changes type in place.
3. **Id edit (§2.3):** ✅ **RESOLVED — auto-only, DROP manual edit** (2-iii-a). Operator never hand-edits ids.
4. **Drag-to-connect disambiguation (§3.3):** separate handle elements that stopPropagation (3-iii-a, **recommended — resolved in principle (origin-based)**; confirm mechanics at P3b-1 grounding) vs a modifier/mode toggle (3-iii-b).
5. **Edge-draw implementation (§3.3):** state-mediated raw-pointer gesture (like pan), NOT a dnd-kit draggable (architectural, **recommended** per DECISIONS 2026-05-21). → *confirm at P3b-1 grounding.*
6. **Bespoke `invoke_*` handling (§4):** ✅ **RESOLVED — (4-i) retire-for-31 + narrow bespoke pane.** (4-ii reconciliation-first rejected.) The reconciliation arc later removes the last pane.
7. **Phase split + dependency order (§6):** ✅ **RESOLVED — P3a first → P3b-1 → P3b-2 → P3c** (P3a ∥ P3b independent; operator sequences P3a first). P3c gated on both + (4-i, locked).
8. **is_iteration on cycle-drop (§3.4):** when a drawn edge would create a cycle, reject outright vs offer to mark it `is_iteration=true`. → *open; resolved at P3b-1 grounding.*

---

## Summary
- **The headline gap:** ~24 of 33 node types have un-slotted semantic params that edit ONLY in the inspector today (full enumeration §1.1). "Show all params" is a hard precondition for retirement, not polish — **but** every un-slotted propType is already dispatcher-handled (simple + object), so it's a surfacing problem, not a control problem (low-risk, (1-i)).
- **Label/type/id:** ✅ locked — label → inline title edit (small, P3a); type + id → **dropped** (delete+re-add via palette / auto-only). P3a relocates label only.
- **Drag-to-connect:** the edge render, cycle/ref validator, edge selection, remove handler, and the pan/zoom transform (whose inverse we need) already exist. Net-new = connection handles + a **state-mediated raw-pointer draw gesture** (NOT dnd-kit — it's position-only) + drop hit-test/validation + canvas delete. Its own sub-arc, split P3b-1 (draw) + P3b-2 (delete). Disambiguation from node-body-drag reuses the proven P2a stopPropagation guard.
- **Bespoke `invoke_*`:** ✅ locked (4-i) — retire-for-31 + a narrow bespoke pane so P3 doesn't serialize behind the filed-forward reconciliation arc, which later removes the last pane.
- **Rail end-state:** node arm → palette (collapses into the none arm; `invoke_*` → narrow bespoke pane); edge + background inspectors unchanged; `NodeConfigForm` deleted. Edge CREATION (canvas drag) and edge CONDITION-editing (EdgeConditionInspector) are distinct and both persist.
- **Phases:** ✅ sequencing locked — **P3a (un-slotted home + label) first** → P3b-1 (draw) → P3b-2 (canvas delete) → P3c (remove inspector + collapse rail; gated on both + (4-i)). Each leaves the builder working; the inspector is removed only after every edit has a proven inline home.
