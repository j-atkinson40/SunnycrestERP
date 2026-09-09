# Peek bridge — investigation

**Date:** 2026-09-09
**Status:** INVESTIGATION ONLY. No code written. Options named, none chosen.
**Dispatch:** Q1–Q4 on bridging the note surface's standing targets to the shipped peek system.

---

## STOP — Q1 fires the stop condition

The dispatch carried: *"Any answer to Q1 that makes a widget renderer a violation
rather than an extension."*

**It is a violation.** Not a fatal one, and not an expensive one under every
option below — but the peek abstraction does assume an entity, and a view-keyed
target does not satisfy that assumption. James's framing was right: this is a
second concept sharing a host, not a sixth renderer.

The rest of this document is the evidence and the sizing. The ruling is James's.

---

## What was verified, and how

Enumerated rather than grepped-where-expected, because the exit-grace miss came
from scoping to one file. Read end-to-end: the frontend dispatch
(`PeekHost.tsx`), the type mirrors (`types/peek.ts`), the client
(`services/peek-service.ts`), the route (`api/routes/peek.py`), the envelope
(`services/peek/types.py`), the dispatcher and two builder **bodies**
(`services/peek/builders.py`), the widget registry
(`components/focus/canvas/widget-renderers.ts`), the Pulse item type
(`types/pulse.ts`), and the latency gate (`tests/test_peek_latency.py`).

---

## Q1 — What does the shipped peek dispatch on?

### The chain

```
PeekTrigger → peek-context → peek-service
  → GET /api/v1/peek/{entity_type}/{entity_id}
  → build_peek()  → PEEK_BUILDERS[entity_type](db, user, entity_id)
  → PeekResponse  → PeekHost: switch (data.entity_type) → renderer
```

Two dispatches, both keyed on `entity_type`, one per side.

### The key, and where each dispatch is written

| Side | Location | Form | Open or closed |
|---|---|---|---|
| Backend | `services/peek/builders.py:383` | `PEEK_BUILDERS.get(entity_type)` dict lookup | **Open** by registration |
| Backend type | `services/peek/types.py` | `PeekEntityType = Literal[...6...]` | **Closed** |
| Frontend type | `types/peek.ts:14` | 6-member string union | **Closed** |
| Frontend | `components/peek/PeekHost.tsx:155` | `switch (data.entity_type)`, 6 cases + `default` | **Closed** |

The `default` arm renders *"Unsupported peek type: {entity_type}"* — so an
unhandled key degrades honestly rather than crashing.

### What a renderer must satisfy

Every builder returns a `PeekResponse` with five fields: `entity_type`,
`entity_id`, `display_label`, `navigate_url`, `peek: dict[str, Any]`. The
envelope types `peek` loosely on purpose, so *"adding a new entity type doesn't
force a union widening"* (`types.py` docstring).

### What the abstraction appears to assume

The envelope alone does **not** require a row. `build_peek` is a plain dict
lookup and never touches the database. Read only the contract, and a widget
target looks like an extension.

The assumption lives one level down, in uniform practice and in the error
taxonomy:

1. **`entity_id` resolves to a tenant-owned row.** All six builders do a
   filtered lookup and raise `EntityNotFound` when it misses. `build_peek`'s own
   docstring: *"builders raise `EntityNotFound` on missing row / tenant miss."*
2. **`saved_view` is the closest existing case, and it is still a row.**
   `_peek_saved_view` resolves `view_id=entity_id` through `get_saved_view` and
   raises `EntityNotFound` on `SavedViewError`. The docstring calls it *"a
   meta-entity"* — but a meta-entity with an id and a record.
3. **`navigate_url` is the "Open full detail →" destination for a record.**
4. **The error taxonomy is row-shaped.** Missing row → `EntityNotFound` → 404.
   For a view-keyed target, "not found" means "unknown key", which is
   `UnknownEntityType` → 400. The 404/400 split does not survive the move.
5. **The type is named `PeekEntityType`,** on both sides.

### The strongest single piece of evidence

`_peek_saved_view` already faced this exact question and ruled against it:

> *"We deliberately do NOT execute the view here — peek must stay fast and
> executing arbitrary saved views blows past the 100ms p50 budget."*

When peek met a view-shaped target, it chose **metadata about the view** over
**the view's data**, explicitly on latency grounds. `/peek` carries a **BLOCKING
CI gate** at p50 < 100 ms, p99 < 300 ms (`tests/test_peek_latency.py:278`).

A widget peek that shows the widget's *content* is precisely what that precedent
refused. A widget peek that shows the widget's *metadata* would honour the
precedent and be useless — a user hovering `vault_schedule` wants the schedule,
not "this widget has 3 filters."

**That is the violation.** Not the key type — the data path and the budget.

### The finding that changes the sizing

There is **already a second, open, view-keyed dispatch in the codebase**:

```ts
getWidgetRenderer(component_key, variant_id)   // components/focus/canvas/widget-renderers.ts
registerWidgetRenderer(widgetType, component)  // 22 call sites (lines, one call each)
```

It is keyed on widget id, populated by side-effect imports at module scope, and
already consumed by six hosts — Canvas, BottomSheet, StackRail,
StackExpandedOverlay, PulsePiece, PinnedSection. Widgets **self-fetch**
(`types/pulse.ts`: payload is *"usually empty for widgets (widgets self-fetch via
useWidgetData)"*), which is exactly why they are not on peek's latency budget.

So the view-keyed concept is not something this arc would invent. It ships. The
build is not "design view-keyed peeks" — it is "decide where the two dispatches
meet."

### The standing targets are not one keyspace

The five standing targets span **two** registries, not one:

| Target | Keyspace | Resolves? |
|---|---|---|
| `today` | widget id — `widgets/foundation/register.ts:102` | yes |
| `vault_schedule` | widget id — `widgets/manufacturing/register.ts:63` | yes |
| `line_status` | widget id — `widgets/manufacturing/register.ts:74` | yes |
| `scheduling.ancillary-pool` | widget id — `dispatch/scheduling-focus/register.ts:84` | yes |
| `ar_summary` | **intelligence-registry key** — `constants/intelligence-registries.ts:45` | **no renderer** |

`ar_summary` is a role-scoped digest key under `full_admin`
(`{key, label, description}`), in a different registry with no widget and no
renderer. Any option below serves at most 4 of 5 targets without additional work.

---

## Q2 — Chrome separability per widget

Already solved, and not by this arc.

`WidgetRendererProps` carries a `surface` discriminator alongside `variant_id`:

```ts
surface?: "focus_canvas" | "focus_stack" | "spaces_pin" | "pulse_grid" | ...
```

Documented intent: *"Renderers may inspect `surface` to adjust internal density."*
Widgets that ignore it *"continue to render their canvas-tier shape"* — so a new
surface value is backward-compatible by construction; unmigrated widgets degrade
to canvas density rather than breaking.

A peek host would add one value (e.g. `"peek_panel"`). Per-widget chrome work is
then opt-in and incremental, one widget at a time, not a blocking prerequisite.

The parity gate already exists: `__tests__/widget-renderer-parity.test.ts`,
added after a real production bug where the backend's canonical
`scheduling.ancillary-pool` paired with a legacy frontend
`funeral-scheduling.ancillary-pool` registration.

**But the surface union is not centrally owned, and has already drifted.**
Measured under `components/widgets/` + `components/dispatch/`: **14 files**
declare their own inline `surface?:` union; **1** imports `WidgetRendererProps`
(counts are files matched, not occurrences). `LineStatusWidgetProps` declares
`dashboard_grid` — a value **not present** in the central union in
`widget-renderers.ts`. So the central declaration is not the single source of
truth today.

Adding a `"peek_panel"` value therefore touches ~14 local declarations, not one.
That cost is identical under Options A, B, and C — it is a property of the widget
layer, not of the bridge. Not verified: how TypeScript assignability currently
tolerates the existing drift at registration
(`REGISTRY.set(widgetType, component)` types the component as
`ComponentType<WidgetRendererProps>`).

---

## Q3 — Legibility at the panel's measured dimensions

**Measured, not assumed:**

- `PANEL_WIDTH = 360` (`PeekHost.tsx:48`) — fixed px, applied inline at line 200.
- `VIEWPORT_PAD = 12` (`PeekHost.tsx:49`).
- **No height constraint exists in `PeekHost.tsx`** — no `max-h-`, no
  `maxHeight`. Panel height is content-driven and currently unbounded in code.

The variant system already addresses small-surface rendering:
`VariantId = "glance" | "brief" | "detail" | "deep"`. The nearest precedent is
`spaces_pin`, which renders **Glance** in a sidebar (`PinnedSection.tsx:573`,
defaulting `?? "glance"`).

So legibility at 360px is a question with an existing answer shape — render
Glance — rather than an open design problem. **But not uniformly.** All four
resolving widgets reference `variant_id`, and three branch on `"glance"`:

| Widget | Glance branch | Behaviour at `variant_id="glance"` |
|---|---|---|
| `today` | yes | renders Glance |
| `vault_schedule` | yes | renders Glance |
| `scheduling.ancillary-pool` | yes | renders Glance |
| `line_status` | **no** | **falls back to Brief** |

`LineStatusWidget` defaults `props.variant_id ?? "brief"` and comments:
*"line_status doesn't declare Glance or Deep variants per §12.10; defensive
fallback ensures any unexpected variant_id renders meaningful content."*

So one of the four would render its Brief shape in a 360px panel. That is a
per-widget density gap, not a blocker — but it means "render Glance" is a
4-target answer with one exception needing either a Glance variant authored or
an accepted Brief-at-360px.

Two remaining caveats:

1. Sidebar width was not measured this session, so "Glance already fits 360px"
   is **unverified**. It needs measuring against the actual pin container.
2. The absent height bound is a real gap for widget content specifically. Entity
   peeks are fixed-field and self-limiting; a widget rendering a list is not.
   Any option that puts a widget in this panel needs a height cap and an
   overflow rule that does not exist today. This bites `line_status` hardest,
   since Brief is the taller shape.

---

## Q4 — The 80 ms exit-grace literal (report only; no change made)

**Exact location:** `frontend/src/components/peek/PeekHost.tsx:127` — the
`}, 80);` closing the `window.setTimeout` inside `onLeaveAnchor`, in the
hover-mode dismiss-guard `useEffect` at lines 116–131. Guarded by
`overPanelRef.current`.

**Why it stands out:** its own file already names its constants —
`PANEL_WIDTH` and `VIEWPORT_PAD` at lines 48–49 — and its sibling timing value
is named *and exported* on the other side of the boundary:
`HOVER_DEBOUNCE_MS = 200` (`peek-context.tsx:85`, used at 208, exported at 280).
The 80 is the only unnamed timing value in the peek layer.

**Minimal naming change (not made):** add `const EXIT_GRACE_MS = 80;` beside
`PANEL_WIDTH`/`VIEWPORT_PAD` at line 49 and substitute at line 127. One
declaration, one substitution, no behaviour change, no export — `HOVER_DEBOUNCE_MS`
is exported only because it crosses a module boundary, and this value does not.

---

## Corrections to facts reported earlier in this arc

Per standing discipline, stated rather than quietly fixed:

1. **"All five standing targets are widget ids among 42."** False for
   `ar_summary`, which is an intelligence-registry key with no widget and no
   renderer. Four of five are widget ids. The original claim came from a
   membership test against a registry that did not contain it.
2. **Mid-investigation, I reported "two of the five don't resolve."** Wrong for
   `scheduling.ancillary-pool`, which does resolve — my grep anchored
   `registerWidgetRenderer("key"` to a single line, and that call is written
   across three lines (`register.ts:84–87`). Corrected before any conclusion
   rested on it. One of five does not resolve, not two.
3. **The "42 widget ids" figure is not re-verified here** and should not be
   inherited. Registration happens via side-effect imports at runtime, so a
   static count is a lower bound, not a census. 22 `registerWidgetRenderer`
   call sites were counted — that is **lines matched, one call per line**, from
   a single registry, excluding tests.

---

## Architecture options — named and sized, not chosen

Sizing is relative effort with the driver named, not hours.

### Option A — Seventh peek type (`entity_type: "widget"`)

Widen both type declarations, add `_peek_widget` to `PEEK_BUILDERS`, add a case
and a `WidgetPeekRenderer` to the switch.

- **Cost driver:** the server must produce each widget's summary data inside a
  **blocking p50 < 100 ms gate**, for widgets that today self-fetch on the
  client with no such budget. That is a parallel server-side data path per
  widget, not a renderer.
- **Also:** `entity_id` stops meaning a row; the 404/400 taxonomy misaligns;
  `navigate_url` needs a destination per widget.
- **Serves:** 4 of 5 targets. `ar_summary` needs its own path regardless.
- **Size:** largest. Grows per widget added.
- **Note:** this is the option `_peek_saved_view` already declined on the record.

### Option B — Host-level bridge (widget rendered client-side in the panel)

`PeekHost` branches *before* the fetch: view-keyed targets skip `/peek/...`
entirely, resolve `getWidgetRenderer(key, "glance")`, and render with
`surface: "peek_panel"`. The widget self-fetches inside the panel, as it does on
every other surface.

- **Cost driver:** peek-context must carry a target-kind discriminator; the
  panel needs the height cap and overflow rule Q3 identifies as missing.
- **Avoids:** the latency gate entirely (no new server work on the hot path),
  the row assumption, and the error-taxonomy mismatch.
- **Serves:** 4 of 5. Degrades honestly via `MissingWidgetEmptyState`.
- **Size:** smallest. Makes the "second concept sharing a host" explicit rather
  than disguising it as a seventh entity type.
- **Cost of honesty:** `PeekHost` visibly becomes two things.

### Option C — Two hosts, one trigger

A separate `WidgetPeekHost`; `PeekTrigger` dispatches on target kind. Peek's
entity abstraction stays untouched and uniform.

- **Cost driver:** duplicated positioning, hover-debounce, exit-grace, and
  dismiss logic — or extracting them into a shared primitive first.
- **Size:** medium, and mostly extraction. Cleanest separation; most new surface
  area; two places for hover behaviour to drift.

### Option D — Serve the four, defer `ar_summary`

Not an architecture — a scope cut applicable to A, B, or C. Worth naming because
`ar_summary` is the only target requiring a new renderer *and* a new keyspace
bridge, and it is one of five.

---

## Not verified

- Sidebar/pin container width, so the Glance-fits-360px claim is unconfirmed.
- The total widget census.
- Whether any peek trigger surface today passes a non-entity key.
- How TypeScript assignability tolerates the existing `surface` union drift at
  `REGISTRY.set(widgetType, component)`.
