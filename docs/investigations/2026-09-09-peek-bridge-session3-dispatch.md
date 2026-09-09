# Session 3 — peek bridge build dispatch (for review, not built)

**Date:** 2026-09-09
**Status:** DRAFT FOR REVIEW. Nothing built.
**Predecessor:** `2026-09-09-peek-bridge.md` (rev 3)

Rulings this implements: Option B (host-level bridge, no `/peek` call for widget
targets); the surface value is the existing `peek_inline`; variant is **Brief**;
panel gains a height cap with scroll; the 80 ms literal gets a name; the
vocabulary consolidation and `ar_summary` are queued, not built.

---

## ⚠️ One ruling meets an obstacle — needs a decision before step 2

The ruling was *"Session 3 implements the existing value; nothing new gets added
to any union."* The first clause is buildable. The second cannot hold literally.

`peek_inline` exists in the **canonical** enum (`components/widgets/types.ts:39`)
and in the **backend** catalog. It is **absent from the runtime prop union**,
`WidgetRendererProps.surface` in `widget-renderers.ts` — which is the union that
every dispatch site actually passes through. It is also absent from the four
target widgets' own local unions.

So passing `surface="peek_inline"` from `PeekHost` requires adding the value to
**5 unions**: the runtime prop union + `TodayWidget`, `VaultScheduleWidget`,
`LineStatusWidget`, `AncillaryPoolPin`.

No new value is invented — every edit adds a value that already exists in the
canonical enum. **Drift decreases**: the runtime union moves toward canonical
rather than away. And none of the four queued consolidation questions
(`command_bar`/`park`, `dashboard_grid`, the `surface?: string` files, the
duplicate `WidgetSurface`) are touched or answered.

### The alternative, and why it is worse

Pass **only** `variant_id="brief"` and no `surface`. Zero union edits; honours
the ruling literally. Verified against the four dispatchers — all four do return
Brief with no surface passed.

But `AncillaryPoolPin`'s Brief (line 490) renders its own frosted tablet —
`bg-surface-elevated/85`, `backdrop-blur-sm`,
`shadow-[var(--shadow-widget-tablet)]`, `--widget-tablet-transform` — and
hard-codes `data-surface="pulse_grid"`. The host cannot strip chrome it does not
control. So that target would show a double surface and double shadow inside the
panel, and `peek_inline` would remain unimplemented — we would have renamed the
ruling rather than built it.

**Recommendation: take the 5 union additions.** Flagged rather than absorbed.

---

## Steps

### 1. Backend — declare the surface (no migration)

Add `"peek_inline"` to `supported_surfaces` for the four standing targets in
`services/widgets/widget_registry.py`: `today`, `vault_schedule`, `line_status`,
`scheduling.ancillary-pool`.

`seed_widget_definitions` (called at `main.py:310` on startup) **upserts** —
its docstring lists `supported_surfaces` among the system-owned columns refreshed
on existing rows. Verified by reading the body, not the signature. No migration.

Do **not** touch `default_surfaces` — the frontend invariant test asserts
`default_surfaces ⊆ supported_surfaces`, and adding to defaults would change
where these widgets render by default.

`ar_summary` is deliberately left at `["dashboard_grid"]`. It declines the panel,
which is the mechanism working.

### 2. Frontend types — add the existing value to 5 unions

`peek_inline` into `WidgetRendererProps.surface` and the four target widgets'
local unions. Blocked on the decision above.

### 3. Per-widget Brief branches — the work is not uniform

Measured per widget; three of four need real work, one is likely clean:

| Widget | What Brief does today | Work |
|---|---|---|
| `scheduling.ancillary-pool` | frosted tablet + widget shadow + tablet transform + `h-full`; hard-codes `data-surface="pulse_grid"` | `peek_inline` branch dropping tablet chrome + transform; stop hard-coding the surface attribute |
| `today` | `TodayBriefVariant` receives **only `_editMode`** — `surface` is not threaded to it at all (`TodayWidget.tsx:574`) | thread `surface` through the wrapper, then branch |
| `line_status` | Brief has a `pulse_grid` branch (232–233); no own surface/shadow found | add `peek_inline` branch or confirm the default path is correct unchanged |
| `vault_schedule` | no own surface/shadow found; variant-only dispatch | likely no change — **verify before asserting** |

All four declare a `brief` variant in the catalog; `today`, `vault_schedule` and
`line_status` default to it, `scheduling.ancillary-pool` declares it and defaults
to `detail`.

### 4. `PeekHost` — the bridge

A target-kind discriminator ahead of the fetch. Widget targets make **no
`/peek` call at all** — the budget is honoured because there is no request.
Resolve `getWidgetRenderer(target_key, "brief")`, render with
`surface="peek_inline"`.

The host header currently reads `data.display_label` and `data.entity_type` from
the peek response, which a widget target never fetches. The standing entry
already carries the label — `_e(entry_id, label, target_key)` in
`note/registry.py` — e.g. "Receivables", "Schedule". Header text comes from there.

Unregistered keys already degrade honestly to `MissingWidgetEmptyState`.

### 5. Panel height cap + scroll

`PeekHost` has no height constraint today. Entity peeks are fixed-field and
never hit it; Brief renders lists. Add a max height with `overflow-y: auto` on
the body, not the panel, so the header stays put. Required by
`AncillaryPoolPin`'s `h-full`, which needs a bounded parent.

Cap value to be chosen against the rendered result, not picked in advance.

### 6. Name the 80 ms literal

`const EXIT_GRACE_MS = 80;` beside `PANEL_WIDTH`/`VIEWPORT_PAD`
(`PeekHost.tsx:48–49`), substituted at line 127. No export — unlike
`HOVER_DEBOUNCE_MS`, it does not cross a module boundary. No behaviour change.

### 7. `TargetSurface` cross-reference comments

A comment at each declaration naming the other. No rename.
- `types/fragments.ts:28` — `"peek" | "focus" | "window"` (note arc)
- `lib/widget-builder/types/composition-blob.ts:49` — authoring surfaces

---

## Verification

- **Positive control required.** The bridge asserts widget targets make no
  `/peek` request. An assertion that depends on absence needs a control that
  reproduces the failure it catches: a test that fails when the branch is
  removed, plus proof the break actually applied.
- Existing gates that must stay green: `test_peek_latency.py` (should be
  untouched — no new server path), `widget-renderer-parity.test.ts`, the
  `default_surfaces ⊆ supported_surfaces` invariant, `renderers.test.tsx`.
- Gate numbers will state their denominator.

## Queued, not built

1. **`ar_summary` — D1.** Build the renderer; `supported_surfaces` gains
   `peek_inline` when it does. Until then it shows `MissingWidgetEmptyState`,
   which is honest and useless, and acceptable with no users.
2. **Surface vocabulary consolidation** — its own arc, four rulings in it:
   are `command_bar`/`park` canonical? does `dashboard_grid` enter the runtime
   union? do the four `surface?: string` files take the union (narrowing can
   fail to compile)? does the duplicate `WidgetSurface` in
   `surface-mapping.ts` collapse into the canonical one?
