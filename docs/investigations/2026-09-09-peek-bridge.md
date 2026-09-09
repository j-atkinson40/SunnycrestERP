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

### The standing targets — one keyspace, one gap

The five standing targets span **two** registries, not one:

**REVISED 2026-09-09 (rev 2) — the first version of this section was wrong.**

All five standing targets come from one place: `backend/app/services/note/
registry.py`, where `_e()` hard-codes `target_surface="peek"` for every entry.
All five are widget ids in the backend catalog
(`services/widgets/widget_registry.py`, 42 entries). There is one keyspace, not
two.

| Target | In backend catalog | Frontend renderer | `supported_surfaces` |
|---|---|---|---|
| `today` | yes | `widgets/foundation/register.ts:102` | pulse_grid, spaces_pin, dashboard_grid, focus_canvas |
| `vault_schedule` | yes | `widgets/manufacturing/register.ts:63` | pulse_grid, spaces_pin, dashboard_grid, focus_canvas |
| `line_status` | yes | `widgets/manufacturing/register.ts:74` | pulse_grid, dashboard_grid, focus_canvas |
| `scheduling.ancillary-pool` | yes | `dispatch/scheduling-focus/register.ts:84` | focus_canvas, focus_stack, pulse_grid, spaces_pin, dashboard_grid |
| `ar_summary` | **yes** — `widget_registry.py:211` | **none registered** | **`dashboard_grid` only** |

`ar_summary` is a real declared widget titled "Accounts Receivable", category
`financial`, permission `ar.view`, and `operational_layer_service.py:96`
dispatches it as a Pulse piece at variant `brief`. What it lacks is a **frontend
renderer** — so it resolves through `getWidgetRenderer`'s unregistered path to
`MissingWidgetEmptyState`, the honest "Widget unavailable" state that shows the
offending widget_id.

It is also the **only** entry in the `("manufacturing", "accountant")` standing
set (`registry.py:129`). Removing it does not shrink that role's standing set —
it empties it.

The `ar_summary` string in `constants/intelligence-registries.ts:45` is a
**name collision in dead config** — that file has zero importers anywhere in
`frontend/src`.

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

### The chrome table (rev 2)

**What the host supplies today** (`PeekHost.tsx:195–240`): a fixed-position
container with `rounded-lg border bg-card shadow-lg` + ring, a bordered header
(`border-b px-3 py-2`) rendering `display_label` and the entity type as an
eyebrow, an optional close button in click mode, and a `px-3 py-2.5` body.

Note the header reads `data.display_label` and `current.entityType` — both come
from the `/peek` response. A widget path that makes no `/peek` call has neither,
so the host needs a label source regardless of the chrome ruling. The standing
entry already carries one: `_e(entry_id, label, target_key)` — e.g. "Receivables".

**What each widget supplies itself**, at the variant a 360px panel would request:

| Target | Variant selected | Own surface/shadow | Own title | Surface-discriminated? |
|---|---|---|---|---|
| `today` | Glance | **yes** — frosted glass, `shadow-[var(--shadow-widget-tablet)]`, fixed `h-15` | eyebrow only | **yes** — separate `pulse_grid` branch renders `h-full w-full`, no surface |
| `scheduling.ancillary-pool` | Glance | **yes** — same frosted tablet + shadow | eyebrow | **partly** — glance block hard-codes `data-surface="spaces_pin"` |
| `vault_schedule` | Glance | no | `<h3>` | no — glance is surface-agnostic |
| `line_status` | **Brief** (no Glance) | no | `<h3>` | yes — Brief has a `pulse_grid` branch |

**The discriminators**, which decide what a peek host actually receives:

```
AncillaryPoolPin:888   surface === "spaces_pin" || variant_id === "glance"  → Glance
TodayWidget:566        surface === "spaces_pin" || variant_id === "glance"  → Glance
TodayWidget:603        if (surface === "pulse_grid")                        → different Glance chrome
VaultScheduleWidget:984  variant === "glance"                               → Glance
LineStatusWidget:659   props.variant_id ?? "brief"; no Glance branch        → Brief
```

So passing `variant_id="glance"` with an unrecognised surface today yields:
`today` and `scheduling.ancillary-pool` take the **spaces_pin tablet path** —
frosted surface, widget shadow, and a fixed `h-15` — nested inside the host's
own `border bg-card shadow-lg`. Double surface, double shadow, and a fixed
height fighting a 360px panel. `vault_schedule` renders clean. `line_status`
renders Brief.

**This is the wrapper-versus-per-widget answer.** A wrapper alone does not work
for two of four, because those two bring their own surface in the Glance path
and will keep doing so no matter what the host wraps them in. The host cannot
own chrome it does not control.

**And `surface` is not a styling token that "lives in one place."** It is a
DB-backed capability declaration: `widget_definitions.supported_surfaces` is a
JSONB column (`models/widget_definition.py:113`), validated by
`variant_target_compatible_with_supported_surfaces`
(`services/widget_definitions/validators.py:38`), filtered on by
`GET /widgets` (`routes/widgets.py:84` — *"Returns widgets that declare
`surface` in their supported_surfaces"*), and mirrored by a frontend invariant
test (`default_surfaces ⊆ supported_surfaces`). All 42 catalog entries declare
it; 29 are `["dashboard_grid"]` and 7 are `["spaces_pin", "pulse_grid"]`.

Adding a surface value therefore touches the catalog rows, the validator, the
filter endpoint, and ~14 local frontend unions — but it also *buys* the thing
those layers provide: a widget can declare whether it is willing to render in a
peek panel, and `ar_summary` (`["dashboard_grid"]` only) would correctly decline.

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

1. **"All five standing targets are widget ids among 42."** This was
   reported false in rev 1. **Rev 1 was itself wrong, and rev 2 restores the
   original claim.** All five ARE widget ids in the backend catalog, including
   `ar_summary` (`widget_registry.py:211`). Rev 1 matched the string in
   `constants/intelligence-registries.ts` — a name collision in a file with zero
   importers — and concluded a second keyspace that does not exist. The real
   defect is narrower and different: `ar_summary` has **no frontend renderer**,
   and its catalog entry declares `supported_surfaces: ["dashboard_grid"]` only.
   A wrong cause was reported for a real symptom.
2. **Mid-investigation, I reported "two of the five don't resolve."** Wrong for
   `scheduling.ancillary-pool`, which does resolve — my grep anchored
   `registerWidgetRenderer("key"` to a single line, and that call is written
   across three lines (`register.ts:84–87`). Corrected before any conclusion
   rested on it. One of five does not resolve, not two.
3. **The "42" figure — two different numbers were being conflated.**
   - **42 is exact**, and enumerable: `"widget_id":` keys in
     `services/widgets/widget_registry.py`, a static list in one file. Parsed by
     line-range, 42 records, all 42 carrying `supported_surfaces`.
   - **22 is a lower bound**: `registerWidgetRenderer` call sites (lines
     matched, one call per line, excluding tests). Registration is by
     side-effect import, so no static count of the *frontend* registry is
     complete.

   The enumeration problem applies only to the frontend registry. The backend
   catalog is the SOT and is countable. **The gap between them is the defect
   surface** — up to 20 declared widgets with no renderer, of which `ar_summary`
   is one.

4. **A constructed-scope miss, caught in flight.** A regex parse of the catalog
   used `\{[^{}]*"widget_id"[^{}]*\}`, which cannot match blocks containing
   nested dicts. It returned 29 of 42 and reported four standing targets as
   "NOT IN CATALOG". That is a miss on a constructed scope, not an absence.
   Re-parsed by line ranges before anything rested on it.

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
- **Serves:** 4 of 5 targets. `ar_summary` needs a renderer regardless.
- **Size:** largest. Grows per widget added.
- **RULED OUT 2026-09-09.** James: overturning the `_peek_saved_view` budget
  precedent to make a widget peek work would be reversing a correct earlier
  ruling because it has become inconvenient. **No widget content goes through
  `/peek`.**

### Option B — Host-level bridge (widget rendered client-side in the panel)

`PeekHost` branches *before* the fetch: view-keyed targets skip `/peek/...`
entirely, resolve `getWidgetRenderer(key, "glance")`, and render with
`surface: "peek_panel"`. The widget self-fetches inside the panel, as it does on
every other surface.

- **Cost driver:** peek-context must carry a target-kind discriminator; the
  panel needs the height cap and overflow rule Q3 identifies as missing.
- **Avoids:** the latency gate entirely (no new server work on the hot path),
  the row assumption, and the error-taxonomy mismatch.
- **Serves:** 4 of 5. `ar_summary` degrades honestly via
  `MissingWidgetEmptyState` — which is what it already does in Pulse today.
- **Size:** smallest. Makes the "second concept sharing a host" explicit rather
  than disguising it as a seventh entity type.
- **Cost of honesty:** `PeekHost` visibly becomes two things.
- **SELECTED 2026-09-09** as the direction. The budget is honoured because there
  is no request to be slow. Two dispatches meeting at a host, not one absorbing
  the other. Chrome sub-ruling (wrapper vs per-widget) still open — see the
  chrome table under Q2.

### Option C — Two hosts, one trigger

A separate `WidgetPeekHost`; `PeekTrigger` dispatches on target kind. Peek's
entity abstraction stays untouched and uniform.

- **Cost driver:** duplicated positioning, hover-debounce, exit-grace, and
  dismiss logic — or extracting them into a shared primitive first.
- **Size:** medium, and mostly extraction. Cleanest separation; most new surface
  area; two places for hover behaviour to drift.

### Option D — Serve the four, resolve `ar_summary` separately

Not an architecture — a scope cut applicable to A, B, or C. Revised in rev 2:
`ar_summary` needs **a frontend renderer**, not a keyspace bridge. Three sub-options:

- **D1 — build the renderer.** It is a declared widget with a catalog entry,
  a title, and a permission. Its `supported_surfaces` would need widening.
- **D2 — remove it from the standing set.** This **empties** the
  `("manufacturing", "accountant")` standing set; it is that role's only entry.
- **D3 — repoint the entry** at a target that has a renderer. Changes what the
  accountant's standing line means, which is a content decision, not a build one.

---

## Not verified

- Sidebar/pin container width, so the Glance-fits-360px claim is unconfirmed.
- The total widget census.
- Whether any peek trigger surface today passes a non-entity key.
- How TypeScript assignability tolerates the existing `surface` union drift at
  `REGISTRY.set(widgetType, component)`.
