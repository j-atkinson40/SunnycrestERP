# Authoring Assistant — Shell Scoping (Phase 0, read-only)

**HEAD:** `0ca4723` · **Date:** 2026-06-30 · **Status:** scope + build plan. NOT a build.
**Prior:** [moc_authoring_assistant_investigation.md](moc_authoring_assistant_investigation.md)
(the brain ships; canvas is inert-for-runtime; draft-the-canvas decision; validation surface).

Scope: ONLY the **shell** — the persistent, page-aware command bar across MoC/Studio.
Banked decisions: draft-the-canvas (valid+publishes+renders, not runs); synchronous-
ephemeral (no persistent queue); workflows first.

---

## TL;DR — the reframe

**The drafting + review + publish experience for workflows ALREADY EXISTS** — as a
**docked assistant rail** inside the Studio Workflow editor (Builder AI Assistant
1b). `WorkflowAssistantRail` takes NL → calls the brain (`generate_workflow_canvas`)
→ holds a **validated candidate** → previews it on the canvas as "Proposed" →
**Accept** (candidate → draft → autosave) / **Reject**. The `{grounding, emit,
validate, applyProposal}` contract is wired. So "legible review" for workflows is
**mostly built** — it's the editor's rail.

What does NOT exist is the **omnipresent entry point**: the existing rail only lives
*inside the Workflow editor*. The operator's vision — a persistent bar everywhere in
MoC/Studio that routes a drafting request from anywhere — is the real net-new piece.
**The shell is an omnipresent entry-point + router that HANDS OFF to the existing
per-editor rail; it does not rebuild the brain or the review.**

Two consequences reshape the "shell + legible-review are the two builds" framing:
- The **legible-review surface for workflows already exists** (the rail). The two
  real builds are (1) the **omnipresent bar + page-context**, (2) the **handoff
  routing** (bar → editor/rail). A per-artifact rail + any inline review come later.
- The omnipresent bar is **genuinely net-new** — see Unknown 1.

---

## Unknown 1 — Existing command-bar primitive: NET-NEW for the omnipresent shape

Three command-ish surfaces exist; none is the persistent omnipresent authoring bar:

| Surface | Where | Shape | Reusable as the shell? |
|---|---|---|---|
| Tenant `CommandBar` | tenant tree (`components/core/`) | Cmd+K, query→results→**close** | No — wrong tree, atomic-close |
| Admin `AdminCommandBar` | `AdminLayout` (MoC + operational) | Cmd+K, static action registry + an in-modal streaming **chat** (→ `POST /api/platform/admin/chat/message`, a generic Q&A — **not** the authoring brain) | Partial base only — see below |
| `WorkflowAssistantRail` | Studio Workflow editor (via `StudioAssistantSlot`) | the **actual drafting UI** (NL → candidate → canvas preview → accept/reject) | This is the *review* surface to route TO, not the bar |

**The structural blocker — the bar must mount ABOVE the route tree.** The admin app's
top-level `<Routes>` dispatches **sibling** branches that each carry their own layout:
- `/studio/*` → `StudioShell`
- `/visual-editor/*` → `VisualEditorLayout`
- everything else (MoC `/`, `/maps/:vertical`, health, tenants) → `operationalPages`
  wrapped in **`AdminLayout`** (where `AdminCommandBar` mounts).

Navigating MoC → Studio **swaps the matched element**: `AdminLayout` unmounts,
`StudioShell` mounts. So `AdminCommandBar` is **MoC/operational-only today and does
NOT persist into Studio** — and any conversation state in it is lost on the swap. A
truly omnipresent, state-surviving bar must mount **above the top-level `<Routes>`**
(a sibling of `AdminAuthProvider` in `BridgeableAdminApp`), not inside any one layout.

**Verdict:** the persistent omnipresent bar is **net-new**. `AdminCommandBar` is a
partial base (it has Cmd+K + a streaming chat surface) but is mis-mounted (in a
swapping layout), closes-on-action, has no page-context, and its chat routes to a
generic Q&A. Reuse its *visual/keyboard shape*; do not reuse its mount or its routing.

## Unknown 2 — Page-context wiring: vertical+editor are route-derivable; the OPEN ARTIFACT is editor-local

- **MoC:** `/maps/:vertical` → `useParams().vertical`. The bar reads "I'm on the
  manufacturing MoC" from the route.
- **Studio:** `parseStudioPath()` (`lib/studio-routes.ts`) → `{vertical, editor}` from
  `/studio/:vertical/:editor`. The bar reads "I'm in the manufacturing Workflows
  editor." (`STUDIO_EDITOR_KEYS` = themes/focuses/widgets/documents/workflows/…)
- **NOT route-derivable: which specific artifact is open.** The Workflow editor holds
  the open template in **component-local state** (`WorkflowEditorPage` `activeTemplate`,
  `useState`); it is not in the URL and not in a shared context. The only bridge is the
  **`StudioAssistantSlot`** — the editor pushes its rail (bound to its `activeTemplate`)
  into the shell slot, *within the editor*. Outside the editor, "which workflow is
  open" is unknown.

**Implication for routing:**
- **Fresh draft** ("make a billing workflow") needs only **vertical + editor-kind**
  (route-derivable). Enough to route to the brain / the right editor.
- **Edit-existing** (passing `current_canvas_state`) needs the open artifact — which
  lives in the editor. So edit-existing only works **from inside the editor** (where
  the rail already does it), or requires the editor to publish its open-artifact state
  to a shared context (net-new wiring). For the omnipresent bar's first light,
  fresh-draft-then-hand-off-to-editor sidesteps this.

**Verdict:** page-awareness (vertical + editor-kind) is **available from existing
route state** — the bar derives it itself via `useLocation()` + `parseStudioPath()` /
`useParams()` (no context provider exists to read, but none is needed for vertical+
editor). The deeper "which artifact is open" is editor-local and only bridged inside
the editor via the slot.

---

## Lighter maps (for the build plan)

**How a request reaches the brain.** No reusable intent/routing layer applies here —
`AdminCommandBar`'s `rankActions` is a static admin-action registry; its chat is a
generic Q&A endpoint. The authoring bar needs its **own** request→brain path:
classify "make a billing workflow" as a *workflow-draft intent* → resolve
(vertical from context, workflow_type from the request) → **hand off to the Workflow
editor + its rail** (recommended; reuses the candidate-review), or call
`workflow-authoring/generate` directly + show an inline review (duplicates the rail).
Recommend the hand-off: navigate to `/studio/<vertical>/workflows` with the NL in
route state; `WorkflowAssistantRail` consumes it and runs its existing generate→
review→accept flow. (Small wiring: the rail must accept an initial NL.)

**Where the bar persists across navigation.** MoC, Studio, and visual-editor are
sibling top-level route branches with swapping layouts (Unknown 1). A persistent
element therefore **must mount above the top-level `<Routes>`** in `BridgeableAdminApp`
(alongside `AdminAuthProvider`) to survive MoC↔Studio↔editor navigation with its
state intact. A per-layout mount (AdminLayout / StudioShell) cannot be omnipresent.

**The minimal first-light.** The bar appears across MoC + Studio (above-Routes mount),
derives page-context (vertical + editor from the route), and routes a workflow-draft
request to the brain by handing off to the Workflow editor's existing rail — which
returns the validated candidate for review. No new review surface, no new brain.

---

## Phased plan

**Shell-1 — the omnipresent, page-aware bar (net-new; serves all 4 types day one).**
- Mount a persistent bar + provider **above the top-level `<Routes>`** in
  `BridgeableAdminApp` so it survives MoC↔Studio↔visual-editor navigation.
- Derive page-context inside the bar: `useLocation()` + `parseStudioPath()` (Studio)
  / `useParams().vertical` (MoC) → `{surface, vertical, editorKind}`.
- Cmd+K open; reuse `AdminCommandBar`'s visual/keyboard shape but NOT its mount.
- Artifact-agnostic dispatch; only the workflow intent lights up. **No brain call yet
  — this phase is the omnipresent, context-reading shell.**
- *Assembly test (real wiring):* from a MoC route AND a Studio route, the bar is
  present and reports the correct `{vertical, editorKind}` (assert context, both
  surfaces, across a navigation that previously unmounted the bar).

**Shell-2 — route a workflow-draft request to the existing brain+rail (synchronous,
ephemeral).**
- Intent: detect a workflow-draft request; resolve vertical (context) + workflow_type
  (request).
- Hand off: navigate to `/studio/<vertical>/workflows` with the NL in route state;
  `WorkflowAssistantRail` consumes it and runs generate→candidate→canvas-preview→
  accept/reject (the existing 1b flow; the ephemeral review = the rail's candidate).
- (Wiring: the rail accepts an initial NL + auto-runs `onGenerate` once.)
- *Assembly test (JCF-1, draft-the-canvas bar — the prior-doc lesson, NOT "runs"):*
  a NL request through the bar → the brain returns a **valid** canvas
  (`validate_canvas_state` passes) → it lands as the editor's reviewable candidate.
  Assert the candidate is real + valid + previews; **state plainly the canvas is
  inert-for-runtime** (the separate gap).

**Later phases (own builds, after the shell):**
- **Per-artifact rails** (focus/widget/document): each = a brain prompt (prior doc
  Phase C) + an editor rail filling the `StudioAssistantSlot` (the extraction seam the
  slot context already anticipates: "Consumer #2 hoists/parameterizes"). The shell
  routes to each.
- **Inline review in the bar** (only if requests must resolve WITHOUT navigating to an
  editor — e.g. drafting from MoC and reviewing in-place). If hand-off-to-editor is
  accepted, this is optional. Scope separately.
- **Edit-existing from outside the editor** (publishing the open-artifact to a shared
  context) — deferred; fresh-draft + hand-off covers first light.

---

## Net-new substrate flagged

1. **The above-Routes persistent bar mount** (Shell-1) — the omnipresent shell is
   net-new; no existing bar mounts where it must, and the layout trees swap on nav.
2. **The bar's own intent→brain routing** (Shell-2) — no reusable intent layer; the
   generic admin chat is unrelated. Small, but net-new.
3. **The rail's "accept an initial NL" wiring** (Shell-2) — minor, to enable hand-off.
4. **(Later) per-artifact rails + the slot's extraction-seam generalization** — the
   `StudioAssistantSlot` is deliberately single-rail today; a second consumer hoists it.

## What does NOT need building (reuse, do not rebuild)

- The **workflow brain** (`generate_workflow_canvas`, validator-gated) — ships.
- The **workflow drafting + legible review + publish** — ships as `WorkflowAssistantRail`
  (candidate → canvas preview → accept/reject → draft → autosave). The shell routes to it.
- **Page-context source** — existing route state (`parseStudioPath` / `useParams`); the
  bar reads it directly, no provider to build.

---

## STOP

Per the stop discipline, the reshaping findings, plainly:

- **No reusable omnipresent command-bar primitive exists.** The shell is a net-new
  frontend build — specifically an **above-the-top-level-`<Routes>` mount**, because
  MoC/Studio/visual-editor are sibling layout branches that swap (and unmount the
  current `AdminCommandBar`) on navigation. This is the bigger-than-"mount+extend"
  surface the dispatch asked to flag.
- **Page-context (vertical + editor-kind) is readable from existing route state** —
  the bar derives it itself; no context-provider build needed for first light. The
  deeper "which artifact is open" is editor-local (only bridged inside the editor via
  the existing `StudioAssistantSlot`), which is why first light is fresh-draft +
  hand-off-to-editor.
- **The drafting + review already exists** (the 1b rail). The shell's job is the
  omnipresent entry point + routing/hand-off — materially smaller than "build a
  command bar AND a review surface."

No build, prompt-engineering, or seeding performed. The plan is the deliverable; the
next move is the operator's go/no-go on Shell-1 (the above-Routes omnipresent bar).
