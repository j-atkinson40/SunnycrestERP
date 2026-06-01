# Inline-params-replace-inspector — Investigation + Phase Plan

**Status:** investigation-only (no code/canon/build/dispatch). HEAD `41cf19e` (right-rail palette pushed). Author: Sonnet, 2026-05-29.
**Operator framing:** maximal both forks — (1) inline params REPLACE the node inspector (card = sole node-editing surface; B-3 RegistryDrivenConfig node-inspector retires); (2) natural-language SENTENCE templates with embedded clickable tokens ("Generate {documentType} for {target}"), click-token → scoped popover. Past single-arc LOC ceiling → map + phase, don't scope one build.

---

## 1. Current node-inspector / config system (what "replace the inspector" must absorb)

### 1.1 NodeConfigForm owns FIVE things — not just config params (THE load-bearing finding)
`NodeConfigForm.tsx:51-214` renders, in order:
1. **Type select** (`:73-84`) — change node.type via `onPatch({type})` over `VALID_NODE_TYPES`.
2. **Node id input** (`:94-100`) — edit node.id via `onPatch({id})`.
3. **Label input** (`:110-115`) — edit node.label via `onPatch({label})` (this is the grow-to-fit label).
4. **Per-type config** (`:122-138`) — dispatch: `invoke_generation_focus` → `InvokeGenerationFocusConfig`; `invoke_review_focus` → `InvokeReviewFocusConfig`; else → `RegistryDrivenConfig`. All emit `onPatch({config: next})`.
5. **Outgoing edges** (`:140-211`) — list + remove (`onRemoveEdge`) + add-by-target-select (`onAddEdge`). STRUCTURAL (edges are canvas data, not node.config).

**Inline sentence-tokens naturally cover only #4 (config params).** Retiring NodeConfigForm therefore requires relocating #1 type, #2 id, #3 label, #5 edges. This is the hidden dependency that makes "retire the inspector" bigger than "inline the params" — it's the gating constraint for the final phase.

### 1.2 Mutation path (inline editors MUST reuse this)
- NodeConfigForm receives `onPatch: (patch: Partial<CanvasNode>) => void` (`:45`).
- In WorkflowEditorPage the mount is `onPatch={(patch) => handleUpdateNode(selectedNode.id, patch)}`.
- Config edits flow as `onPatch({ config: next })` where `next` is the FULL next config object.
- RegistryDrivenConfig's `patch(key,value)` = `onChange({ ...config, [key]: value })` (`RegistryDrivenConfig.tsx:96-98`) — single-key merge into full config, emitted up.
- **Inline-token popover editors reuse exactly this:** a token edit = `handleUpdateNode(nodeId, { config: { ...config, [key]: newValue } })`. Same path, no new mutation API. The scoped-edit guarantee (change one param, nothing else moves) is structurally automatic — it's a single-key merge.

### 1.3 ConfigPropType — 12 union values, RegistryDrivenConfig handles 8
`registry/types.ts:121-133`: `boolean | number | string | enum | tokenReference | componentReference | array | object | tableOfColumns | tableOfRows | listOfParties | conditionalRule` — **12 values.** (The dispatch said "8 ConfigPropTypes" — that's the count RegistryDrivenConfig actively renders; the other 4 — tableOfColumns/tableOfRows/listOfParties/conditionalRule — fall to a fallback and are NOT used by any of the 32 workflow-node registrations.)

RegistryDrivenConfig editors (`RegistryDrivenConfig.tsx:162-298`):
| ConfigPropType | inspector control | inline-popover difficulty |
|---|---|---|
| `enum` (:170) | shadcn Select (bounds = options) | EASY (select-in-popover) |
| `number` (:191) | Input type=number + min/max bounds | EASY |
| `string` (:212) | Input text | EASY |
| `boolean` (:231) | switch/checkbox | EASY (toggle-in-popover, or inline toggle) |
| `object` (:242) | JSON textarea (JsonControl) | HARD (JSON blob — bindings like inputBinding/parameters/fieldBindings) |
| `array` (:247) | list editor (ArrayControl) | HARD (decision.branches) |
| `tokenReference` (:257) | category-scoped token picker | N/A for templates (only the vestigial accentToken) |
| `componentReference` (:274) | component picker (ComponentRefControl) | MEDIUM (focusTemplateName — picker popover) |

Plus the 2 **bespoke** Focus configs (InvokeGenerationFocusConfig / InvokeReviewFocusConfig) — richer than RegistryDrivenConfig; their semantic params are focusTemplateName (componentReference), inputBinding (object), reviewMode/routingMode (enum), timeoutSeconds (number).

---

## 2. The 32 configurableProps — raw data + the semantic/vestigial split

### 2.1 Raw param-count distribution
`3 params: 3 types · 4 params: 27 types · 8 params: 2 types` (generation-focus-invocation, send-communication).

### 2.2 THE KEY RESHAPING: ~3 vestigial VISUAL props per type
EVERY type carries some of: `nodeShape` (A3-inert), `labelPosition` (A3-superseded), `accentToken` (tokenReference, A3-superseded), + the 2 indicator enums on generation-focus-invocation (`successIndicatorStyle`/`failureIndicatorStyle`). These are NOT semantic — they don't belong in a sentence. **Templates interpolate SEMANTIC params only; vestigial-visual props are excluded** (and these are exactly the A3 "full nodeShape removal" file-forward targets — this thread and that cleanup are aligned).

### 2.3 SEMANTIC param table (vestigial visual props struck) — the template raw material
| type | semantic params (type) | semantic count |
|---|---|---|
| start | — | 0 |
| end | terminalStatus:enum | 1 |
| input | inputSchema:object, required:boolean | 2 |
| output | outputBinding:object | 1 |
| wait | waitMode:enum, durationSeconds:number, eventBinding:string | 3 |
| schedule | scheduleMode:enum, cronExpression:string, delaySeconds:number | 3 |
| action | actionType:string, parameters:object | 2 |
| ai_prompt | promptKey:string, model:enum, temperature:number, maxTokens:number | 4 |
| send_document | templateKey:string, recipientBinding:string, deliveryChannel:enum | 3 |
| send_email | templateKey:string, recipientBinding:string, subjectBinding:string, maxRetries:number | 4 |
| send_notification | channel:enum, templateKey:string, recipientBinding:string | 3 |
| send-communication | channel:enum, templateKey:string, recipientBinding:string, maxRetries:number, retryBackoffSeconds:number | 5 |
| notification | message:string, severity:enum, recipientRole:string | 3 |
| show_confirmation | title:string, body:string, confirmLabel:string | 3 |
| open_slide_over | slideOverKey:string, contextBinding:object | 2 |
| playwright_action | scriptKey:string, timeoutSeconds:number, retryOnFailure:boolean | 3 |
| create_record | entityType:string, fieldBindings:object | 2 |
| update_record | entityType:string, recordIdBinding:string, fieldBindings:object | 3 |
| log_vault_item | itemType:string, titleBinding:string, bodyBinding:string | 3 |
| generate_document | templateKey:string, outputFormat:enum, entityBinding:string | 3 |
| call_service_method | serviceMethodKey:string, kwargsBinding:object, timeoutSeconds:number | 3 |
| generation-focus-invocation | focusTemplateName:componentReference, inputBinding:object, reviewMode:enum, timeoutSeconds:number | 4 |
| invoke_generation_focus | focusTemplateName:componentReference, inputBinding:object, reviewMode:enum, timeoutSeconds:number | 4 |
| invoke_review_focus | focusTemplateName:componentReference, inputBinding:object, routingMode:enum | 3 |
| cross_tenant_order | targetTenantBinding:string, orderPayloadBinding:object, acknowledgmentRequired:boolean | 3 |
| cross_tenant_request | targetTenantBinding:string, requestType:string, payloadBinding:object | 3 |
| cross_tenant_acknowledgment | sourceRequestBinding:string, acknowledgmentStatus:enum | 2 |
| condition | expression:string, trueLabel:string, falseLabel:string | 3 |
| decision | branches:array, defaultBranch:string | 2 |
| branch | conditionExpression:string | 1 |
| parallel_split | branchCount:number, waitForAll:boolean | 2 |
| parallel_join | joinPolicy:enum, threshold:number | 2 |

**Semantic distribution: 0 params ×1 (start) · 1 ×3 · 2 ×8 · 3 ×14 · 4 ×4 · 5 ×1.** Max 5, mostly 1-3 → **the sentence model is sane** (no type has an unmanageable semantic param count). The 2 raw-8-param types collapse to 4-5 semantic.

---

## 3. The template engine (net-new)

### 3.1 Format + home
- **Format:** per-type `labelTemplate: string` with `{paramName}` slots referencing semantic configurableProp keys, e.g. `generate_document → "Generate {templateKey} for {entityBinding}"`. Literal prose between slots; slots reference param NAMES (resolved to current values at render).
- **Home:** a parallel vocab file — `lib/visual-editor/workflow-node-templates.ts` (mirrors `workflow-node-palette.ts` / `widget-palette.ts`): `NODE_LABEL_TEMPLATES: Record<string, string>` + a `SEMANTIC_PARAMS` allowlist (or derive semantic = configurableProps − VESTIGIAL_VISUAL set). NOT the registry (keeps registry render-agnostic; B-2 Path-A flat-category lock unaffected), NOT node-families (that's card-render color). Co-locating with the palette vocab keeps "workflow-node display vocab" in one neighborhood.
- **Semantic classifier:** `VESTIGIAL_VISUAL_PARAMS = {nodeShape, labelPosition, accentToken, successIndicatorStyle, failureIndicatorStyle}`; `semanticParams(type) = configurableProps(type) keys − VESTIGIAL_VISUAL_PARAMS`. Templates only slot semantic params; a guard test asserts every `{slot}` in a template references a real semantic param of that type.

### 3.2 Parse / interpolate / render
- **Parse:** split `labelTemplate` on `/{(\w+)}/` into alternating literal + slot segments (pure function, unit-testable — mirror simulate-trace/canvas-layout purity).
- **Interpolate:** for each slot, read current value `config[paramName] ?? schema.default`. **Unset → placeholder token** `[paramLabel]` (humanized param name, dimmed). **Set → value token** (the value, or for enums the chosen option; for componentReference the resolved display name; for object/array a summary like "3 fields" / "2 branches").
- **Render:** literal segments = plain text; slot segments = `<button>`-ish token spans (Phase 2+ clickable). Tokens wrap within the grow-to-fit card (whitespace-normal break-words already in place).

### 3.3 Composition with the existing card
- **node.label vs template:** the template OUTPUT becomes the card's primary text, REPLACING the raw grow-to-fit `node.label` render for typed nodes. BUT node.label is still a real field (operator can name a node). Proposal: render the **template** as the card body; keep node.label as an optional override/title (if set, show it as a heading above the sentence, or the sentence IS the label). **Type-B decision:** does the sentence replace node.label entirely, or coexist (label = optional human name, sentence = param summary)? Lean: sentence is the body; node.label becomes an optional bold title line when non-empty.
- **grow-to-fit:** tokens are inline spans inside the existing wrapping label `<p>` → they wrap + the card grows. No conflict (grow-to-fit measures the rendered height regardless of token content).
- **family icon + selection:** unchanged — icon stays header-left, family tone/stripe stays, selection ring stays (A3 orthogonal channels). The sentence+tokens live in the content column where the label is today.

---

## 4. The popover editors (net-new, per config type)

### 4.1 Mirror primitive
`components/ui/popover.tsx` (base-ui-backed) + existing consumers to mirror: `composition-canvas/ColumnCountPopover.tsx`, `visual-authoring/TokenSwatchPicker.tsx`, `widget-builder/binding-picker/{SavedViewPicker,FieldPathPicker}.tsx`, `visual-editor/CompactPropControl.tsx`. **CompactPropControl is the closest mirror** (a compact per-prop control already in the visual-editor) — investigate whether it can BE the popover body (wrap CompactPropControl in a Popover, reuse its per-type rendering). This would collapse most of the per-config-type editor work into "reuse CompactPropControl inside a Popover."

### 4.2 Per-type popover editor (click token → popover → edit → persist → token updates)
| ConfigPropType | popover body | persist |
|---|---|---|
| string | text Input | `onPatch({config:{...config,[k]:v}})` |
| enum | Select (bounds) | same |
| number | number Input + bounds | same |
| boolean | toggle (or no popover — inline toggle) | same |
| componentReference | picker (mirror SavedViewPicker) | same |
| object | JSON mini-editor (JsonControl in a popover) — or "edit in panel" escape hatch | same |
| array | list editor (ArrayControl in a popover) — or escape hatch | same |

**Scoped-edit guarantee:** structurally automatic — every edit is the single-key merge `{config:{...config,[k]:v}}` through `handleUpdateNode(nodeId, patch)`. Canvas state, other params, selection, edges all untouched (the merge only touches one config key). No new guarantee to build; it falls out of the existing mutation path.

### 4.3 The hard types (object/array) — the real risk
`object` (inputBinding/parameters/fieldBindings/payloadBinding/kwargsBinding/contextBinding) and `array` (decision.branches) don't tokenize as a single inline value. Options: (a) token shows a SUMMARY ("3 fields") + popover holds the full JsonControl/ArrayControl; (b) these params get an "edit in panel" escape hatch (a slim retained editor) rather than full inline — meaning the inspector doesn't FULLY die for complex params. **Type-B decision.** Lean (a): summary-token + popover-hosted existing control (JsonControl/ArrayControl already exist — reuse in a popover).

---

## 5. The retire-inspector path (why it's LAST + its hidden dependency)

Retiring NodeConfigForm requires homes for its 4 non-config responsibilities (§1.1):
- **Label (#3):** inline as the card title (editable token / double-click card title). Smallest.
- **Type (#1):** rare. Options: delete+re-add via palette; OR a small "change type" affordance on the card/peek. Lean: drop in-place type-change (re-add via palette) — but flag operator (is changing a node's type a needed flow?).
- **Id (#2):** rare/advanced. Lean: auto-only (drop manual id edit) — flag.
- **Edges (#5):** the BIG one. Outgoing edges are added/removed in the inspector today. Retiring it needs either (a) canvas drag-to-connect (a real feature — its own arc), or (b) a retained slim edge affordance (a small edges-only panel or an on-card "+edge" control). **This is the gating dependency: the inspector cannot fully retire until edge editing has a non-inspector home.**

**End state (per dispatch, confirmed):** rail = palette (none AND node selection) + EdgeConditionInspector (edge) + TriggerInspector (background). NOT pure-palette — edge.condition and trigger are not node config, so their inspectors stay. Node selection shows the palette (Shortcuts: action library stays open; selected node edited inline on its card).

**No broken-editing window:** every config type must be inline-editable (P2a+P2b complete) AND edges/type/id/label relocated (P3) BEFORE NodeConfigForm is removed.

---

## 6. Phase breakdown (the core deliverable)

Refines the operator straw-man (P1 read-only / P2 editors / P3 retire). Findings force P2 to split and P3 to carry the non-config dependency.

- **P1 — Template engine + 32 templates + READ-ONLY token render.** New `workflow-node-templates.ts` (templates + semantic classifier) + a `NodeLabelSentence` render component (parse/interpolate/render, tokens non-clickable, placeholder for unset) + wire into the card body (replaces raw label render for typed nodes) + grow-to-fit/family/selection composition. **Inspector UNCHANGED (still the editing surface).** Cards now READ as sentences. Pure-function engine + render is unit-testable; jsdom-safe. **~350-480 LOC.** Seam: cards display sentences; all editing still via inspector. **Working at every step.**
- **P2a — Clickable tokens + popover editors for SIMPLE types (string/enum/number/boolean) + mutation wiring.** Click token → Popover (mirror CompactPropControl/ColumnCountPopover) → edit → `handleUpdateNode({config})`. Covers the majority of semantic params. **Inspector still present (fallback for object/array/componentReference + the 2 bespoke).** **~350-480 LOC.** Seam: simple params inline-editable; complex via inspector. Working.
- **P2b — Popover editors for COMPLEX types (object/array/componentReference) + the 2 bespoke Focus configs' semantic params.** Summary-token + popover-hosted JsonControl/ArrayControl/ComponentRefControl (reuse existing controls). After this, EVERY config param is inline-editable → the inspector's config SECTION is redundant. **~350-480 LOC.** Seam: all config inline; inspector config-section dead but inspector still mounted for type/id/label/edges. Working.
- **P3 — Relocate non-config responsibilities + retire NodeConfigForm.** Label → inline card title; type/id → drop-or-minimal-affordance (operator-decided); edges → the gating sub-problem (slim edge affordance vs drag-to-connect). Then node-selection → palette; remove NodeConfigForm; rail = palette(none/node) + edge + background inspectors. **LOC HIGHLY VARIABLE** — if edges get a slim affordance ~300-450; if drag-to-connect is built it's its own arc (P3 sub-phases). Seam: inspector gone, no broken-editing window (gated on P2a+P2b + edge relocation complete).

**Dependencies / reordering:** P1→P2a→P2b is linear (read → simple-edit → complex-edit). P3 depends on ALL of P2 + the edge-relocation decision. **P3's edge sub-problem may itself need an investigation/arc** (drag-to-connect is a non-trivial canvas feature) — flag: P3 is "retire inspector" ONLY if edge editing is solved; otherwise P3 splits into P3a (label/type/id relocation + node-selection→palette, keeping a slim edges affordance) and P3b (edges fully on-canvas, later).

---

## 7. The 32 label templates — DRAFT (operator reviews)

Semantic params only (vestigial visual excluded). `{x}` = clickable token; placeholder `[x]` when unset. ⚠ = phrasing/param-mapping is an operator call.

| type | proposed template | token params |
|---|---|---|
| start | `Start` | — |
| end | `End ({terminalStatus})` | terminalStatus |
| input | `Collect input {inputSchema}` ⚠ (object→summary) | inputSchema |
| output | `Output {outputBinding}` ⚠ | outputBinding |
| wait | `Wait {durationSeconds}s` / `Wait for {eventBinding}` ⚠ (waitMode picks phrasing) | waitMode, durationSeconds, eventBinding |
| schedule | `Schedule: {cronExpression}` / `Delay {delaySeconds}s` ⚠ (scheduleMode picks) | scheduleMode, cronExpression, delaySeconds |
| action | `Run action {actionType}` | actionType, parameters |
| ai_prompt | `Run AI prompt {promptKey} ({model})` | promptKey, model, temperature, maxTokens |
| send_document | `Send {templateKey} to {recipientBinding} via {deliveryChannel}` | templateKey, recipientBinding, deliveryChannel |
| send_email | `Email {templateKey} to {recipientBinding}` | templateKey, recipientBinding, subjectBinding, maxRetries |
| send_notification | `Notify {recipientBinding} via {channel} ({templateKey})` | channel, templateKey, recipientBinding |
| send-communication | `Send {templateKey} to {recipientBinding} via {channel}` | channel, templateKey, recipientBinding, maxRetries, retryBackoffSeconds |
| notification | `Notify {recipientRole}: {message} ({severity})` | message, severity, recipientRole |
| show_confirmation | `Confirm "{title}"` | title, body, confirmLabel |
| open_slide_over | `Open {slideOverKey}` | slideOverKey, contextBinding |
| playwright_action | `Run script {scriptKey}` | scriptKey, timeoutSeconds, retryOnFailure |
| create_record | `Create {entityType}` | entityType, fieldBindings |
| update_record | `Update {entityType} {recordIdBinding}` | entityType, recordIdBinding, fieldBindings |
| log_vault_item | `Log {itemType}: {titleBinding}` | itemType, titleBinding, bodyBinding |
| generate_document | `Generate {templateKey} for {entityBinding} as {outputFormat}` | templateKey, outputFormat, entityBinding |
| call_service_method | `Call {serviceMethodKey}` | serviceMethodKey, kwargsBinding, timeoutSeconds |
| generation-focus-invocation | `Generate via {focusTemplateName}` | focusTemplateName, inputBinding, reviewMode, timeoutSeconds |
| invoke_generation_focus | `Invoke generation focus {focusTemplateName}` | focusTemplateName, inputBinding, reviewMode, timeoutSeconds |
| invoke_review_focus | `Invoke review focus {focusTemplateName}` | focusTemplateName, inputBinding, routingMode |
| cross_tenant_order | `Order from {targetTenantBinding}` | targetTenantBinding, orderPayloadBinding, acknowledgmentRequired |
| cross_tenant_request | `Request {requestType} from {targetTenantBinding}` | targetTenantBinding, requestType, payloadBinding |
| cross_tenant_acknowledgment | `Acknowledge {sourceRequestBinding} ({acknowledgmentStatus})` | sourceRequestBinding, acknowledgmentStatus |
| condition | `If {expression}` | expression, trueLabel, falseLabel |
| decision | `Decide among {branches}` ⚠ (array→summary "N branches") | branches, defaultBranch |
| branch | `Branch if {conditionExpression}` | conditionExpression |
| parallel_split | `Split into {branchCount} branches` | branchCount, waitForAll |
| parallel_join | `Join ({joinPolicy})` | joinPolicy, threshold |

**Phrasing notes:** wait/schedule have mode-dependent phrasing (the enum mode chooses which token shows — a template could be mode-conditional, a small engine feature, OR pick one canonical phrasing — operator call). object/array tokens (inputBinding, fieldBindings, branches, parameters, payloads) render as SUMMARIES ("3 fields"), not raw JSON. Several types have MORE semantic params than the template surfaces (e.g. send_email's subjectBinding/maxRetries) — the template shows the headline params as tokens; the rest are still editable (via a "more" affordance / the popover for the headline token could expose siblings, OR they stay inspector-only until P2b). **Operator decides the headline-vs-all token set per type.**

---

## 8. Type-B decisions surfaced (for Opus/operator resolution)

1. **Template home:** new `workflow-node-templates.ts` vocab file (lean) vs registry field vs node-families neighborhood.
2. **Semantic classifier:** explicit `SEMANTIC_PARAMS` allowlist vs derive (configurableProps − VESTIGIAL_VISUAL). Ties to the A3 nodeShape-removal file-forward (same exclusion set).
3. **node.label vs sentence:** sentence replaces the label render entirely vs coexist (label = optional title line, sentence = body).
4. **Headline vs all tokens:** does every semantic param become a token, or only headline params (with the rest behind a "more"/popover-siblings affordance)? Per-type or global rule?
5. **Popover primitive:** wrap the existing `CompactPropControl` in `ui/popover` (reuse per-type rendering) vs build per-type popover bodies.
6. **object/array tokens:** summary-token + popover-hosted existing control (JsonControl/ArrayControl) vs an "edit in panel" escape hatch (inspector doesn't fully die for complex params).
7. **mode-conditional templates:** wait/schedule phrasing depends on the mode enum — support conditional templates, or pick one canonical phrasing?
8. **The 2 bespoke Focus configs:** inline-tokenize their semantic params (P2b) vs keep them inspector-only (the one exception to full retirement)?
9. **Inspector non-config responsibilities (the P3 gate):** type-change — keep an affordance or drop (re-add via palette)? id — auto-only or keep an affordance? label — inline card-title edit. **Edges — the big one: slim retained edge affordance vs build canvas drag-to-connect (its own arc).**
10. **P3 shape:** single retire-phase (if edges get a slim affordance) vs split P3a (relocate label/type/id + node→palette, slim edges) / P3b (drag-to-connect, later).
11. **Edge/background inspector fate:** confirmed STAY (edge.condition + trigger are not node config). Rail end-state = palette(none/node) + edge-inspector + background-inspector.

---

## Summary
- The sentence model is **feasible**: after excluding ~3 vestigial-visual props/type, semantic param counts are 0-5 (mostly 1-3). Templates drafted for all 32.
- The mutation path (`onPatch({config:{...config,[k]:v}})`) **reuses cleanly**; scoped-edit is automatic.
- The **non-obvious blocker** is that NodeConfigForm owns 4 NON-config things (type/id/label/edges) — "retire the inspector" is gated on relocating those, **especially edges** (drag-to-connect is potentially its own arc). The phase plan front-loads the safe, working-at-every-step work (P1 read-only → P2a simple-edit → P2b complex-edit) and isolates the risky retirement (P3) behind the edge-relocation decision.
- Recommended phases: **P1** (engine + templates + read-only tokens) → **P2a** (simple-type popover editors) → **P2b** (complex/bespoke popover editors) → **P3** (relocate non-config + retire inspector; may split P3a/P3b on edges). Each ~350-480 LOC except P3 (variable; gated).
