# Workflow Builder — Visual Containers (hierarchy / grouping) — INVESTIGATION

**Date:** 2026-06-04
**HEAD:** `855e132` (focus-invocation reconciliation P3 / E-3 — arc close)
**Type:** Investigation (map the code against a SETTLED design + propose phasing). NOT a grounding-for-build. No code, no canon, no build, no dispatch.
**Thread context:** the third Shortcuts-model canvas thread — completing-rail ✅ + inline-params/inspector-retirement ✅ (closed at `855e132`) → **visual containers** (this map).

---

## 0. The settled design (recorded, NOT re-litigated)

Mapped against — not questioned:

- **Overlay model.** The flat graph (`nodes` + `edges`) STAYS THE TRUTH. A container is an **additive overlay** — NOT a structural tree, NOT a data-model change to nodes/edges, NO runtime change. Need it solves: nested control flow (decision-inside-loop-inside-parallel) tangles the edge graph visually; containers make it scannable.
- **Explicit membership (A1).** A container holds an explicit **member-list of node-ids**. Authoring = select nodes → "group into container" → a container with those members. Bounds **computed** from member positions (the box encloses them). NOT spatial enclosure (no "is this node inside the box by position").
- **Two states.** Default **EXPANDED** (a labeled box drawn AROUND the still-visible members — soft logical grouping) + **COLLAPSED** on demand (members hidden, one labeled box; edges crossing the boundary reroute to the box as a proxy endpoint — the tangle-tidying legibility win). Expand to see/edit innards.
- **New canvas_state collection.** A `containers` collection (`id`, `label`, member node-ids, collapsed-state), rendered as an overlay; the node/edge graph untouched.

---

## 1. MULTI-NODE SELECT — does it exist? (the likely prerequisite)

### Verdict: **DOES NOT EXIST. Phase 0 is real — multi-select must be added first.**

**The selection model is single-target, by construction.** `WorkflowEditorPage` holds a 4-state discriminated union:

- `WorkflowEditorPage.tsx:120-125` — `type WorkflowSelection = { kind:"none" } | { kind:"node"; id:string } | { kind:"edge"; id:string } | { kind:"background" }`. **Each carries at most ONE id.**
- `WorkflowEditorPage.tsx:194-198` — `const [selection, setSelection] = useState<WorkflowSelection>({kind:"none"})`; `selectedNodeId = selection.kind==="node" ? selection.id : null`; `selectedEdgeId` likewise. Single scalars.
- `GraphCanvas.tsx:131-134` — the canvas prop contract is `selectedNodeId: string | null` + `onSelectNode: (id:string|null)=>void`. Single id in, single id out.
- `GraphCanvas.tsx:991` — the node card's `onClick={() => onSelect(node.id)}` REPLACES selection (no accumulation), and `WorkflowEditorPage.tsx:969-971` maps it straight to `setSelection({kind:"node", id})`.

**Confirmed by scan:** a full grep for `multi.?select | selectedNodeIds | selectedIds | marquee | shift.?click | shiftKey | Set<string>…select` across the whole workflow-canvas tree + the page + the lib returned **nothing**. There is no shift+click accumulation, no drag-box marquee, no id-set anywhere. The P3b drag work added single **edge** select; it did not add multi-node select.

### What's the cleanest model to ADD (given the existing raw-pointer gestures)?

Two candidate gestures, and they compose with the existing pointer routing very differently:

**The existing pointer routing on the canvas surface (`GraphCanvas.tsx:351-422`):**
- `handleSurfacePointerDown` (:351) engages a pan gesture **only on a direct background hit** (`if (ev.target !== ev.currentTarget) return`, :356) — node/edge-hit pointer-downs target their own elements and never reach pan.
- The gesture is a 3-state machine in a ref (`idle → pending → panning`, :269-275), promoting to `panning` at the 3px `PAN_DRAG_THRESHOLD` (:382-386).
- A plain background click (sub-3px, no pan) falls through to `onClick → onSelectBackground()` (:517-533) which selects the trigger inspector.

**Candidate A — shift/⌘+click accumulate (RECOMMENDED for Phase 0).**
- Purely additive to the existing node `onClick` (:991): branch on `ev.shiftKey || ev.metaKey` → accumulate into a set instead of replacing.
- **Zero collision** with the pan gesture (pan only engages on background hits; node clicks never reach it).
- Smallest surface: extend the selection union with a multi-node kind (e.g. `{ kind:"nodes"; ids:Set<string> }` or carry `ids:string[]`), branch the node onClick, render a selected-ring per member.
- This is the lowest-friction path and the one the "group selected nodes → container" gesture (Phase 1) actually needs — grouping consumes "the current set of selected nodes."

**Candidate B — drag-box marquee (DEFER — collides with pan).**
- A marquee draws a rubber-band on the **background** and selects enclosed nodes. But the background drag is **already owned by pan** (:351-422). Marquee would have to compete: either modifier-gate it (`shift+drag on background = marquee`, plain drag = pan) or add a canvas mode toggle.
- Modifier-gating is feasible (the pointer-down handler can branch on `ev.shiftKey` to start a marquee-rect ref instead of a pan ref, mirroring the draw-gesture state machine at :290-341), but it's a SECOND background gesture machine — meaningfully more code than Candidate A, and a marquee's "enclosed by rect" is **spatial**, which sits oddly next to the design's **explicit-membership** stance for containers themselves.

**Recommendation (Type-B, flag — don't decide here):** Phase 0 ships **Candidate A (shift/⌘+click accumulate)** as the prerequisite. Marquee is a follow-on nicety, gated behind the pan-vs-marquee modifier decision, and is NOT required for containers to work (grouping needs a node-set; shift+click produces one).

---

## 2. HOW CONTAINERS SLOT INTO canvas_state (the additive data)

### canvas_state shape today

`CanvasState` (`workflow-templates-service.ts:49-54`):
```ts
interface CanvasState { version: number; trigger?: CanvasTrigger; nodes: CanvasNode[]; edges: CanvasEdge[] }
```
- `CanvasNode` (:19-25): `{ id; type; label?; position:{x,y}; config }`.
- `CanvasEdge` (:28-35): `{ id; source; target; label?; condition?; is_iteration? }`.
- Persistence: `canvas_state` is **JSONB**, `nullable=False`, `default=dict`, on BOTH `workflow_templates` (`backend/app/models/workflow_template.py:61`) and `tenant_workflow_forks` (`:148`).

### Adding a `containers` collection: how it composes

**It's a clean additive field. Confirmed — no migration, no required-key change, existing payloads stay valid.**

1. **Type (frontend):** add optional `containers?: WorkflowContainer[]` to `CanvasState` (:49-54), with `interface WorkflowContainer { id:string; label?:string; member_ids:string[]; collapsed:boolean }`. Optional → every existing draft (no containers) is unchanged.

2. **Persistence:** JSONB on both tables → **no Alembic migration**. An additive key serializes into the existing column. Empty/absent `containers` is the universal back-compat state. (Matches the precedent: `is_iteration?` on edges and `trigger?` on the canvas were both additive-into-JSONB.)

3. **Validators — additive, both sides:**
   - `_REQUIRED_TOP_KEYS = {"nodes","edges","version"}` — backend `canvas_validator.py:109`, frontend `canvas-validator.ts:76`. `containers` is **NOT** required → omitting it stays valid (the empty-`{}` and missing-key paths at `canvas_validator.py:126-133` / `canvas-validator.ts:72-82` are untouched).
   - Adding container validation is cheap because both validators **already build `seen_node_ids`** while walking nodes (`canvas_validator.py:149/164`; `canvas-validator.ts:102/117`) — the exact set a `member_ids → real node` reference check needs. Mirror the edge-reference check (`canvas_validator.py:211-220` / `canvas-validator.ts:157-166`) for members.
   - The two validators MUST stay in lockstep (the file headers both assert it; cross-reference tests verify — `canvas-validator.ts:4-9`). Any container rule lands in BOTH files in the same commit.

4. **registry_snapshot — N/A (confirmed).** `registry_snapshot.py` mirrors **component prop schemas** for `component_configurations` write validation. Containers are not registry component types (they're canvas-overlay metadata, not a `workflow-node` registration), so the snapshot is untouched. No `VALID_NODE_TYPES` change either (`canvas_validator.py:62-106` / `canvas-validator.ts:18-55`) — a container is not a node type.

### Validation questions to surface (Type-B — flag for the build, don't decide)

- **Member-ref integrity** (cheap, recommended baseline): every `member_ids[i]` must reference a declared node id (reuse `seen_node_ids`). Orphan member = reject (or silently drop? — mirror the orphaned-override precedent in component_configurations, which drops + warns).
- **Container-id uniqueness** (mirror node/edge id-uniqueness checks).
- **A node in ≤1 container, or many?** The design implies disjoint logical groups; recommend **≤1** as the baseline invariant (a node belongs to at most one container). Flag.
- **Empty member-list** — allowed (a freshly-created empty container) or rejected? Recommend allowed (parallels the empty-`{}` canvas being valid).
- **collapsed default** — `false` (expanded is the default state per the design).

### Container NESTING (data-model-affecting — flag)

The design's motivating case — "decision-inside-loop-inside-parallel" — is **nested control flow**, which makes **nested containers** plausibly wanted. The member-list model's nesting support hinges on one decision:

- **Flat (nodes-only members)** — `member_ids` reference only node ids. Simplest; both validators' `seen_node_ids` check works as-is. A container cannot contain a container.
- **Nestable (member can be a container id)** — `member_ids` may reference EITHER a node id OR a container id. This needs a discriminator (member is `{kind:"node"|"container", id}`) OR a separate `parent_container_id?` field on the container record, plus: nesting cycle-detection (a container can't transitively contain itself), bounds-of-a-container-that-contains-a-collapsed-container, and rerouting across two boundary levels.

**Recommendation (Type-B, flag):** Phase 1 ships **flat (nodes-only members)** — it satisfies the scannability win for a single grouping level and keeps the data model + validators trivial. **Nesting is a follow-on (proposed Phase 3)** because it materially complicates both the data model AND the Phase 2 rerouting (box-inside-box). Confirm scope at build time.

### Observation — `collapsed` is PERSISTED authored state (diverges from the view-state pattern)

The design puts `collapsed:bool` in the container record **inside canvas_state**, so collapse/expand round-trips and a collapse fires a save (`isDirty` compares `JSON.stringify(persistedCanvas) !== JSON.stringify(draftCanvas)`, `WorkflowEditorPage.tsx:309` → autosave at :393-409). This is a deliberate departure from the established "view state is never persisted" pattern — the trace-overlay toggle (`GraphCanvas.tsx:214`), pan/zoom (`:252`), and per-node expand (`:917`) are all ephemeral. Per the settled design, collapse is an authored choice (it persists), unlike pan/zoom. Worth naming so it's intentional, not accidental.

---

## 3. THE COLLAPSE EDGE-REROUTING (the meaty rendering — how big?)

### How edges render today

The edge layer is an SVG, `pointer-events:none`, absolutely positioned inside the transform surface (`GraphCanvas.tsx:539-724`). Per edge (`:561-689`):
- Resolve `source`/`target` nodes by id (`:562-564`); skip if either is missing.
- Source anchor is **height-aware**: `sourceHeight = heights.get(source.id) ?? NODE_HEIGHT` (:570), fed to `computeEdgePath` (:571-575).
- `computeEdgePath` (`canvas-layout.ts:221-239`): anchors at source **bottom-center** (`sx = source.x + nodeWidth/2`, `sy = source.y + nodeHeight`, :228-229) → target **top-center** (`tx = target.x + nodeWidth/2`, `ty = target.y`, :230-231), cubic-bezier with vertical control offset.
- `computeEdgeMidpoint` (`:247-259`) for the label + the P3b-2 delete-×.
- `computeEdgePreviewPath` (`:331-344`) already proves a **bare-point endpoint** variant (cursor, not a node box) — it does NOT add `nodeWidth/2` to the endpoint because the endpoint isn't a box.

### How collapse-rerouting would work, and what it costs

**The bezier path-drawing REUSES; the anchor computation + the rerouting LOGIC is substantial new code. Honest size: MEDIUM-LARGE — the largest single piece of the thread.**

When a container is collapsed, its member nodes are hidden and the container renders as one box. Each edge must be classified relative to the collapsed member-set `M`:

1. **Interior** (`source ∈ M && target ∈ M`) → **hidden entirely** (both endpoints are inside the collapsed box). New: filter these out of the edge `.map`.
2. **Crossing-out** (`source ∈ M && target ∉ M`) → re-anchor the SOURCE to the **container box boundary**; target unchanged.
3. **Crossing-in** (`source ∉ M && target ∈ M`) → re-anchor the TARGET to the box boundary; source unchanged.
4. **External** (`source ∉ M && target ∉ M`) → unchanged.

Why this is real work, not a parameter tweak:
- **Anchor generalization.** `computeEdgePath` hardcodes the anchor to a NODE box of `NODE_WIDTH × nodeHeight` (`:228-231`). A container box is a **different-sized box** at computed bounds. Either generalize the helper to "anchor on a box of arbitrary `(x,y,w,h)`" (new param shape) or add a new `computeEdgePathToBox` helper. The `computeEdgePreviewPath` bare-point variant shows the codebase's pattern for "endpoint isn't a standard node," but a container is a box (needs a boundary point), not a point — so it's a THIRD anchor mode.
- **Proxy port model (Type-B — flag).** When multiple edges cross the same boundary, do they all converge on **one proxy port** (e.g. box bottom-center, simplest, but visually stacks arrows), or each route to a **distinct point on the box edge** (nearest-boundary-point per edge, cleaner but needs a boundary-intersection computation), or **side-bucketed** (top edge for incoming, bottom for outgoing)? This choice drives how much geometry is net-new.
- **Box↔box routing.** When **two** containers are collapsed and an edge crosses between them (both endpoints hidden, in different boxes), the edge must route box-boundary → box-boundary. With nesting (if ever in scope) this compounds. Even flat-only, the multi-container-collapsed case must be handled (route from box A's boundary to box B's boundary).
- **Midpoint + delete-× + label** (`:576-686`) all key off the path's anchors → they follow the re-anchoring automatically once the anchor function is generalized (no separate work, but they must be verified against the new anchors).
- **Hit-testing.** A collapsed container box becomes a click target (select it; expand it). The node hit-test (`nodeAtPoint`, `canvas-layout.ts:358-377`) is node-only today; a parallel container hit-test (or the box being a real clickable DOM element, like the node card) is needed.

**Size verdict:** the **path geometry reuses** the existing bezier (good — no new curve math), but (a) edge-classification against the collapsed set, (b) box-boundary anchor computation in ≥1 new mode, (c) the proxy-port decision, (d) hiding interior edges, (e) box↔box for multi-collapse, and (f) the collapsed box as a render+hit+expand surface together make **Phase 2 the heaviest phase** of the thread. The P3b edge work gives a strong foundation (anchors are already parameterized on `Point` + height-aware), but collapse-rerouting is genuinely new rendering, not an extension of a knob.

---

## 4. RENDERING THE CONTAINER (the overlay)

### Where it slots in the layer stack

The transform surface div (`GraphCanvas.tsx:496-755`) stacks, in DOM/paint order: the **SVG edge layer** (`:539-724`, `pointer-events:none`, `inset-0`) → the **node layer** (`:727-754`, absolutely-positioned cards). A container box slots:
- **Expanded:** a styled `<div>` positioned at computed bounds, painted **BEHIND** the nodes (a labeled frame around them). Insert it as a sibling **before** the node `.map` (around `:725`, after the SVG) so nodes paint on top of the frame. It's `pointer-events:auto` only on its label/chrome (so the enclosed nodes stay clickable through the frame's interior — mirror the SVG's selective pointer-events approach at `:540`/`:623`).
- **Collapsed:** the same box, now opaque, **replacing** the (hidden) members — painted in the node layer's z-band, behaving like a node card (selectable, expandable).

### Computed bounds — the reactive machinery ALREADY EXISTS

- `bbox(nodes, NODE_WIDTH, heightOf)` (`canvas-layout.ts:270-305`) computes min/max-X/Y over a node set using the **measured** `heightOf` resolver. A container's expanded bounds = **`bbox(memberNodes, NODE_WIDTH, heightOf)` + padding** — a direct reuse over the member subset (call it with the filtered member list instead of all nodes).
- Heights are measured per-node via ResizeObserver into a `Map` (`GraphCanvas.tsx:230-242`, reported from each `GraphCanvasNode` at `:886-899`); `heightOf` reads it (`:239-242`). Member moves flow `onMoveNode → handleUpdateNode → setDraftCanvas → re-render` (`:519-524`, `:464-476`), so the bounds **recompute reactively** when any member moves — exactly the grow-to-fit reactivity the design wants. No new machinery; reuse `bbox` + `heightOf` + the measured `heights` Map.

### Pan/zoom — composes for free

The container box is a child of the transform surface div, which carries `transform: translate(panX,panY) scale(zoom)` (`GraphCanvas.tsx:496-509`). Everything inside transforms together (the comment at `:500-507` states the invariant: edges SVG + node DOM transform as one). A container box added as a sibling child **transforms automatically** — same pan/zoom/zoom-to-cursor behavior as nodes and edges, zero extra wiring. (The floating controls — trace toggle `:761`, zoom controls `:782` — are deliberately OUTSIDE the transform target; the container box is INSIDE it, which is correct.)

---

## 5. THE PHASING (the deliverable)

Each phase leaves the builder fully working. Frontend-only except a small backend validator add in Phase 1.

### Phase 0 — Multi-node select (the prerequisite)
- **Why:** containers' "group selected nodes" gesture needs a node-SET; none exists today (§1).
- **Touches:** `WorkflowEditorPage.tsx` selection union (:120-125 — add a multi-node kind carrying `ids`, or carry `ids:string[]` alongside the single-node kind) + the GraphCanvas node `onClick` (`:991` — branch on `ev.shiftKey/metaKey` to accumulate vs replace) + a selected-ring per member (reuse the existing `data-selected`/outline channel at `:1040-1042`). Keyboard a11y: Space-toggle within the dnd KeyboardSensor is out of scope; click is the gesture.
- **Model:** shift/⌘+click accumulate (Candidate A). Marquee deferred (collides with pan, §1).
- **Frontend-only.** **Size: SMALL-MEDIUM.** Single-click selection is byte-identical to today; multi-select is purely additive.

### Phase 1 — Containers as EXPANDED labeled regions (the additive, cheaper half)
- **Scope:** the `containers` canvas_state field (§2) + validators (member-ref integrity, id-uniqueness, ≤1-container invariant) + the "group selected nodes → container" gesture (consumes the Phase 0 set) + render the labeled box around members (`bbox` over the member subset, §4) + label inline-edit (reuse the node-title inline-edit idiom at `GraphCanvas.tsx:1086-1134`) + ungroup. **NO collapse yet** (the field carries `collapsed:false`; nothing reads it in Phase 1).
- **Touches:** `workflow-templates-service.ts` (type, :49-54) · `canvas-validator.ts` + `canvas_validator.py` (member rules, lockstep) · `GraphCanvas.tsx` (render the expanded frame behind nodes; group/ungroup affordance) · `WorkflowEditorPage.tsx` (a `handleCreateContainer(memberIds)` / `handleUpdateContainer` / `handleRemoveContainer` mutating `setDraftCanvas`, mirroring the edge handlers at :484-513).
- **Frontend + a SMALL backend validator add.** **No migration** (JSONB). **Size: MEDIUM.** Leaves builder working (a canvas with no containers renders exactly as today).

### Phase 2 — Collapse / expand + edge-rerouting (the meaty half)
- **Scope:** read `collapsed`; hide member nodes + interior edges; reroute crossing edges to the container box boundary (the proxy endpoint); the collapsed box as a select/expand surface (§3). The hardest rendering of the thread.
- **Touches:** `canvas-layout.ts` (generalize the anchor / add `computeEdgePathToBox`; an edge-classification helper against the collapsed member-set; a container hit-test parallel to `nodeAtPoint`) · `GraphCanvas.tsx` (edge `.map` filters interior, re-anchors crossing; collapsed-box render + collapse/expand toggle + hit). Pure helpers stay unit-testable (the canvas-layout precedent at `:308-313`).
- **Frontend-only** (no schema — `collapsed` already in the Phase 1 field). **Size: LARGE.** Leaves builder working (default `collapsed:false` = Phase 1's expanded behavior; collapse is opt-in).

### Phase 3 (proposed follow-on) — Nested containers
- **In scope or follow-on? FLAG (Type-B).** The motivating "decision-inside-loop-inside-parallel" case argues for it, but nesting affects the **data model** (member can be a container id → discriminator or `parent_container_id`), the validators (nesting cycle-detection), and Phase 2's rerouting (box-inside-box, two boundary levels). Recommend deferring to a dedicated phase AFTER Phase 1+2 prove the flat model. Phases 1+2 ship **flat (nodes-only members)**.

---

## 6. TYPE-B DECISIONS surfaced (NOT resolved — for the Opus build dispatch)

1. **Multi-select model (Phase 0):** shift/⌘+click accumulate (recommended) vs + drag-box marquee (collides with the background-pan gesture; needs a modifier-gate or mode). Marquee can be a follow-on.
2. **Member-ref integrity on orphan:** reject (HTTP 400, mirror edge-ref) vs silently drop + warn (mirror component_configurations orphaned-override). Recommend reject for write-time, since the editor controls membership.
3. **A node in ≤1 container, or many?** Recommend ≤1 (disjoint logical groups). Affects the validator invariant.
4. **Container nesting — in scope or Phase 3?** Affects the member-list data model (flat node-ids vs nestable discriminator). Recommend flat for Phases 1+2; nesting as Phase 3.
5. **Collapse proxy-port model (Phase 2):** one proxy port (simplest, arrows stack) vs distinct nearest-boundary points per edge (cleaner, needs boundary-intersection geometry) vs side-bucketed (incoming top / outgoing bottom). Drives Phase 2's net-new geometry.
6. **collapsed is persisted authored state** (per the settled design) — diverges from the ephemeral view-state pattern (trace toggle, pan/zoom, per-node expand). Confirm intentional (it means collapse/expand fires an autosave).
7. **Empty member-list container** — allowed (recommend, parallels empty-`{}` canvas) or rejected.
8. **Phase order** — the proposed 0 → 1 → 2 (→ 3 nested) sequence; confirm or adjust.

---

## Appendix — file:line index (the map's evidence)

| Concern | File:line |
|---|---|
| Selection union (single-id, 4-state) | `WorkflowEditorPage.tsx:120-125`, `:194-198` |
| Node click → replace selection | `GraphCanvas.tsx:991`; page map `WorkflowEditorPage.tsx:969-971` |
| Canvas prop contract (single id) | `GraphCanvas.tsx:131-134` |
| Background-pan gesture machine | `GraphCanvas.tsx:269-275`, `:351-422` |
| Background click → trigger select | `GraphCanvas.tsx:517-533` |
| `CanvasState` / `CanvasNode` / `CanvasEdge` types | `workflow-templates-service.ts:19-54` |
| `canvas_state` JSONB column (both tables) | `backend/app/models/workflow_template.py:61`, `:148` |
| Required top-keys (containers NOT required) | `canvas_validator.py:109`; `canvas-validator.ts:76` |
| `seen_node_ids` (reuse for member-ref) | `canvas_validator.py:149/164`; `canvas-validator.ts:102/117` |
| Edge-ref integrity (mirror for members) | `canvas_validator.py:211-220`; `canvas-validator.ts:157-166` |
| `VALID_NODE_TYPES` (no change — container isn't a node) | `canvas_validator.py:62-106`; `canvas-validator.ts:18-55` |
| Edge render loop | `GraphCanvas.tsx:561-689` |
| `computeEdgePath` (box-anchor, hardcoded NODE dims) | `canvas-layout.ts:221-239` |
| `computeEdgeMidpoint` | `canvas-layout.ts:247-259` |
| `computeEdgePreviewPath` (bare-point endpoint precedent) | `canvas-layout.ts:331-344` |
| `nodeAtPoint` hit-test (node-only) | `canvas-layout.ts:358-377` |
| `bbox` (reuse for container bounds) | `canvas-layout.ts:270-305` |
| Measured heights Map + `heightOf` | `GraphCanvas.tsx:230-242`; reporter `:886-899` |
| Transform surface (pan/zoom — container transforms with it) | `GraphCanvas.tsx:496-509` |
| Node layer (paint order) | `GraphCanvas.tsx:727-754` |
| Node-title inline-edit idiom (reuse for label) | `GraphCanvas.tsx:1086-1134` |
| Edge mutation handlers (mirror for container CRUD) | `WorkflowEditorPage.tsx:484-513` |
| `isDirty` autosave (collapse fires a save) | `WorkflowEditorPage.tsx:309`, `:393-409` |
| GraphCanvas is the SOLE canvas renderer; page is sole mount | grep: only `GraphCanvas.tsx` + `WorkflowEditorPage.tsx` |
| WorkflowsTab uses NodeConfigForm (panel, no canvas) → untouched | CLAUDE.md §4 + `WorkflowEditorPage.tsx:40-49` |

**No code. No canon. No build. No dispatch.** Map only.

---

# Phase 2 — collapse / expand + edge-rerouting (the LARGE phase) — INVESTIGATION

**Date:** 2026-06-04 · **HEAD:** `628972d` (P1 shipped — expanded labeled containers live). Appended to the committed investigation; **uncommitted until P2a lands.** No code, no canon, no build.

**Proxy-port model LOCKED: side-bucketed** — crossing-IN edges route to the box TOP-center, crossing-OUT to the box BOTTOM-center (matching `computeEdgePath`'s source-bottom→target-top convention; the collapsed box anchors like a big node). **Flat only** (P1/P2 produce only `kind:"node"` members; nesting/box-inside-box is P3).

## P2.1 — The edge classifier (the core logic)

A pure helper consumed by the edge `.map` (`GraphCanvas.tsx:593`). Given `edges` + the collapsed-membership lookup, classify each edge into five cases:

| Case | Condition | Render |
|---|---|---|
| **interior** | source ∈ M and target ∈ M, **same** collapsed container | **hidden** (both endpoints inside the box) |
| **box↔box** | source ∈ M and target ∈ M, **different** collapsed containers | route boxA-**bottom** → boxB-**top** (both endpoints re-anchored) |
| **crossing-out** | source ∈ M (collapsed), target ∉ any collapsed | route boxA-**bottom** → target node-**top** (existing node anchor) |
| **crossing-in** | source ∉ any collapsed, target ∈ M (collapsed) | route source node-**bottom** → boxB-**top** |
| **external** | neither endpoint in a collapsed container | **unchanged** (P1 path) |

where **M = the set of node-ids that are `kind:"node"` members of a COLLAPSED container.** (An expanded container hides nothing → its members render normally → their edges are external.)

**The member→container lookup.** `buildCollapsedMembership(containers): Map<nodeId, containerId>` — iterate `containers.filter(c => c.collapsed)`, map each `kind:"node"` member id → its container id. Built in `GraphCanvas` render as a `useMemo` over `canvas.containers` (the collapsed subset). Reactivity: a `collapsed` toggle → `handleUpdateContainer` → `setDraftCanvas` → re-render → the memo rebuilds → reclassify. The classifier reads `membership.get(edge.source)` / `.get(edge.target)` — same container id on both ⇒ interior; both present + different ⇒ box↔box; one present ⇒ crossing; neither ⇒ external.

**Cases the classifier must handle (enumerated):**
- Member with only interior edges → those hide; the member vanishes with the box. Fine.
- Container with **no** crossing edges (fully self-contained) → collapses to a box with no external edges. Fine.
- Member of collapsed-A ↔ member of collapsed-B → **box↔box** (NOT interior — different containers).
- Member of collapsed-A ↔ member of an **expanded** container → the expanded member is a visible node → **crossing** (node anchor on the expanded side; box anchor on the collapsed side).
- Self-loop on a member (source===target, same collapsed container) → interior → hidden.
- A node that is a member of NO container → never in M → its edges are external/crossing depending on the OTHER endpoint.

## P2.2 — The anchor generalization (side-bucketed) — does `computeEdgePath` generalize?

**Partially — the bezier CURVE reuses; the per-endpoint ANCHOR resolution is the new pure helper.** `computeEdgePath` (`canvas-layout.ts:221-239`) computes BOTH anchors from a SINGLE `nodeWidth`/`nodeHeight` pair: `sx = source.x + nodeWidth/2; sy = source.y + nodeHeight` (source bottom-center), `tx = target.x + nodeWidth/2; ty = target.y` (target top-center). A crossing edge has **mismatched per-endpoint dims** (one end a node `NODE_WIDTH×heightOf`, the other a box `boxW×boxH`), so the single-dims signature does NOT cover it.

**Clean generalization (the P2a deliverable):** extract the curve core + a per-endpoint anchor resolver:
- `bezierBetween(sourcePt: Point, targetPt: Point): string` — the existing control-point math from `computeEdgePath:234-238` (`ctrl = max(40, |dy|/2)`, the cubic `M…C…`), lifted to operate on two already-resolved points. `computeEdgePath` becomes a thin caller (resolve node anchors → `bezierBetween`); `computeEdgePreviewPath` (`canvas-layout.ts:331-344`, already a bare-point variant) folds onto the same core. So the codebase's three bezier variants (node-target, point-target, box-target) unify on one core.
- `boxAnchor(bounds: {x,y,w,h}, side: "top"|"bottom"): Point` — `top` → `(x + w/2, y)`; `bottom` → `(x + w/2, y + h)`. This is EXACTLY the node top/bottom-center math at box dims — confirming the lean: **same top/bottom-center geometry, different box.** No new curve math.

A crossing-out edge: `bezierBetween(boxAnchor(boxBounds,"bottom"), nodeTopCenter(target))`. A box↔box edge: `bezierBetween(boxAnchor(boxA,"bottom"), boxAnchor(boxB,"top"))`. The arrow marker + the midpoint helper (`computeEdgeMidpoint:247-259`, used for labels + the P3b-2 delete-×) follow the new anchors once they read the resolved endpoints.

## P2.3 — The COLLAPSED BOX POSITION + SIZE (the real open question)

When **expanded**, bounds = `bbox(memberNodes, NODE_WIDTH, heightOf)` + 18px padding (`GraphCanvas.tsx:775` — P1). When **collapsed**, members are hidden → `bbox(members)` is the wrong SIZE (occupying the full member footprint defeats the tangle-tidying purpose). The collapsed box needs a definite compact `(x,y,w,h)` for the side-bucketed anchor.

**Options (Type-B — surface, lean stated):**
- **POSITION (a, lean):** the members' bbox **top-left** (`{x: b.minX, y: b.minY}`) — computed from the still-present member positions (members exist in `canvas_state`, just unrendered), so collapse shrinks the region toward its top-left corner. No schema change; deterministic; stable while collapsed (hidden members can't move).
- POSITION (b): members' **centroid** (collapse toward center). Computed; the box overlaps where members were.
- POSITION (c): a **stored** `position?: {x,y}` on `WorkflowContainer` (set at first collapse; draggable thereafter). Makes the collapsed box a first-class movable card — but adds a field + "set on first collapse" logic + drag handling.
- **SIZE (a, lean):** a **fixed** collapsed-card size — a dedicated `COLLAPSED_CONTAINER_WIDTH/HEIGHT` (≈ a node card, perhaps a touch wider to fit the label + a member count). Predictable; the anchor math has a definite box.
- SIZE (b): label-hugging (variable). More layout work; little benefit.

**Lean for P2: computed position (members' bbox top-left) + fixed size — NO schema change.** Trade: the collapsed box is **not independently draggable** (it's pinned to the members' bbox top-left); making it draggable needs the stored `position` (option c) — **deferred refinement**, flagged. This gives `boxAnchor` a definite box without a schema migration and keeps `collapsed` the only P2 state read.

## P2.4 — The collapsed box as a surface (render + hit + expand)

- **Render — branch `GraphCanvasContainer` on `collapsed` (one component, two modes).** Expanded → the current P1 behind-nodes labeled frame (`pointer-events:none` body, chrome auto — `GraphCanvas.tsx:1372+`). Collapsed → an **opaque card** at the P2.3 collapsed bounds, `pointer-events:auto`, **z-index in the node band** (so it paints among the cards it replaces). The container layer (`:758-790`) renders BEFORE the node layer (`:792-793`), but z-index (not DOM order) governs paint within the transform surface — a collapsed box with node-band z-index reads as on-top. **The node `.map` (`:793`) must SKIP hidden members** (filter out any node in M) so the collapsed box visually replaces them. Keeping ALL container rendering in `GraphCanvasContainer` (branched) is cleaner than promoting collapsed boxes into the node layer.
- **Hit-testing — DOM card, NO `nodeAtPoint` change.** The collapsed box is a real DOM element with its own `onClick` (like the node card), so clicks are handled in the DOM — `nodeAtPoint` (`canvas-layout.ts:358-377`) stays node-only. **BUT a real interaction to fix in P2b:** `nodeAtPoint` iterates ALL `canvas.nodes` (incl. hidden members); `dropDecision` (`canvas-layout.ts:416-438`, drag-to-connect) could therefore resolve a DROP onto a HIDDEN member while a container is collapsed. **P2b must exclude hidden members from the drop hit-test** (pass only-visible nodes, or filter M out before `nodeAtPoint`). Flagged — it's the one place collapse touches an existing gesture.
- **Collapse/expand toggle.** Expanded chrome gets a **collapse** button (alongside label + ungroup); the collapsed card gets an **expand** button. Both call `handleUpdateContainer(id, { collapsed: !collapsed })` → `setDraftCanvas` → persists + autosaves (P1 established `collapsed` as authored state). Maps cleanly onto the existing P1 `handleUpdateContainer`.
- **Container selection (Type-B).** P1 does label-edit + ungroup **inline on the box chrome** — no selection needed. P2 can keep that (expand/collapse/ungroup/label all chrome buttons) → **no new selection kind**, consistent with P1, and P2 doesn't touch the selection union again. The alternative — a new `{ kind:"container"; id }` (6th union kind) — buys a container rail panel + a selection ring, at the cost of touching the union (`WorkflowEditorPage.tsx:120-130`) + the rail dispatch. **Lean: keep interactions inline-on-box for P2; defer `{kind:"container"}` unless a container rail is wanted.**

## P2.5 — Composition + reactivity

- **`collapsed` is authored/persisted** (P1 shipped the field; it's in `canvas_state`). Toggling → `handleUpdateContainer` → `setDraftCanvas` → re-render + autosave (`WorkflowEditorPage.tsx:309/393-409` dirty+autosave). The membership map + edge classification + box render are `useMemo`'d on `canvas.containers`/`canvas.edges` → recompute on the toggle.
- **Surface bbox / pan bounds:** keep counting ALL nodes (incl. hidden members) toward the surface-sizing `bbox` so collapse doesn't shrink the scroll surface or jump pan. Minor — flag.
- **grow-to-fit:** the collapsed box is **fixed size** → it doesn't depend on the measured-heights `Map`; hidden members stop re-measuring (not rendered) but their stale heights are harmless (the collapsed box position uses member bbox top-left, position-based not height-based). The collapsed box does not report a measured height (it's not a node).
- **pan/zoom:** the collapsed box + rerouted edges are children of the transform surface (`GraphCanvas.tsx` surface div) → transform-composed for free, like everything.
- **Transition (Type-B, polish):** expanded↔collapsed as an instant swap (lean) vs an animated shrink/grow — deferred polish, not required for P2.

## P2.6 — P2 internal phasing (mirrors the P3b-1a/1b de-risk)

**P2a — pure helpers (de-risked first, consumed by nothing; mirrors P3b-1a `canvas-layout` pure functions).**
- `buildCollapsedMembership(containers): Map<nodeId, containerId>`
- `classifyEdge(edge, membership): { kind: "interior"|"crossing-in"|"crossing-out"|"external"|"box-box"; sourceContainerId?; targetContainerId? }`
- `bezierBetween(sourcePt, targetPt)` (extract `computeEdgePath`'s curve core; fold in `computeEdgePreviewPath`) + `boxAnchor(bounds, "top"|"bottom")`
- `collapsedBoxBounds(container, members, heightOf): {x,y,w,h}` (members' bbox top-left + fixed size)
- All unit-testable in `canvas-layout.test.ts` with no DOM (the Q-40 JSDOM-weakness pattern). **Size: SMALL-MEDIUM.** Consumed by nothing → builder unaffected.

**P2b — rendering (consumes P2a; mirrors P3b-1b).**
- node `.map` filters hidden members; edge `.map` consumes `classifyEdge` (hide interior; reroute crossing/box↔box via `bezierBetween`+`boxAnchor`; external unchanged).
- `GraphCanvasContainer` branches on `collapsed` (expanded frame ↔ collapsed opaque card + expand button); collapse button on the expanded chrome.
- the drop-hit-test-excludes-hidden-members fix (P2.4).
- **Size: LARGE.** Behind the `collapsed` flag → default-false = P1 behavior, so the builder stays working throughout.

**2a/2b confirmed.** The collapsed-box surface + the edge-rerouting are visually interdependent (rerouting targets the box), so they belong in one rendering phase (P2b); splitting them would show half a feature. If P2b proves too large mid-build, the natural seam is collapsed-box-render-+-toggle FIRST (members hide, box shows, edges temporarily hidden), THEN edge-rerouting — but lean: one P2b.

## P2.7 — Type-B decisions surfaced (NOT resolved)

1. **Collapsed box position + size** (§P2.3): computed members'-bbox-top-left + fixed size (lean, no schema) vs stored `position` (draggable, +field). Draggability-when-collapsed deferred.
2. **Multiple crossing edges per side** (§P2.2 sub-question): all-in at top-center / all-out at bottom-center (lean, simplest) vs spread along the box edge (a pure `N→N points` refinement). P2b polish — center first.
3. **Container-selection kind** (§P2.4): keep interactions inline-on-box, no new union kind (lean, consistent with P1) vs add `{kind:"container"}` for a container rail + ring.
4. **Expand/collapse transition** (§P2.5): instant (lean) vs animated. Polish.
5. **P2a/2b split** (§P2.6): confirmed; the in-build fallback seam noted.

## Appendix — Phase 2 file:line index

| Concern | File:line |
|---|---|
| Edge render loop (consumes the classifier) | `GraphCanvas.tsx:593` |
| `computeEdgePath` (curve core to extract + node anchors) | `canvas-layout.ts:221-239` |
| `computeEdgePreviewPath` (bare-point variant — folds onto `bezierBetween`) | `canvas-layout.ts:331-344` |
| `computeEdgeMidpoint` (follows the new anchors) | `canvas-layout.ts:247-259` |
| `nodeAtPoint` (node-only; stays — but drop hit-test must exclude hidden) | `canvas-layout.ts:358-377` |
| `dropDecision` (drag-to-connect; exclude-hidden-members fix) | `canvas-layout.ts:416-438` |
| `bbox` (expanded bounds; surface sizing counts all nodes) | `canvas-layout.ts:270-305` |
| Container render layer (`canvas.containers?.map`; `const b = bbox(memberNodes…)`) | `GraphCanvas.tsx:758-790`, `:775` |
| Node layer (must filter hidden members) | `GraphCanvas.tsx:792-793` |
| `GraphCanvasContainer` (branch on `collapsed`; add collapse/expand chrome) | `GraphCanvas.tsx:1372+` |
| Container chrome (label + ungroup; add collapse toggle) | `GraphCanvas.tsx:1435-1480` |
| `handleUpdateContainer` (collapse toggle → setDraftCanvas → persist) | `WorkflowEditorPage.tsx` (P1 container CRUD) |
| Selection union (Type-B: add `{kind:"container"}` or not) | `WorkflowEditorPage.tsx:120-130` |
| `isDirty` autosave (collapse persists) | `WorkflowEditorPage.tsx:309`, `:393-409` |

**No code. No canon. No build. No dispatch.** Phase 2 map only — uncommitted until P2a.
