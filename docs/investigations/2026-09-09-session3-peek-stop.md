# Session 3 STOP — `peek_inline` is declared and unimplemented, and a peek system already ships

**Date:** 2026-09-09 · Read-only against the repo. No code written.
Four STOP lines hit. Stopping before wiring, per §3's own instruction.

---

## 1. ⚠️ `peek_inline` does NOT work as declared

The salvage investigation reported `WidgetSurface` declaring `peek_inline`
("Peek panel content composition, no chrome"). **That is literally true and
functionally misleading.**

Enumerated — every occurrence in `frontend/src`, no bound:

| location | what it is |
|---|---|
| `components/widgets/types.ts` | the enum value + its comment |
| `lib/widget-builder/types/surface-mapping.ts` | the enum value + a mapping set |
| `foundation/RecentActivityWidget.tsx` | **a docstring line.** One occurrence, prose only |
| `lib/plugin-registry/plugin-contracts-snapshot.json` | documentation |

**Nothing dispatches on it.** Widgets *do* branch on `surface` — I found
`surface === "spaces_pin"` in TodayWidget, RecentActivityWidget,
CalendarSummaryWidget and CalendarGlanceWidget, and `surface === "pulse_grid"` in
TodayWidget and AnomaliesWidget. **Zero branch on `peek_inline`.**

⚠️ **So a widget handed `surface="peek_inline"` falls through to its default
return — the full-chrome variant.** The declared meaning is "no chrome"; the
actual behaviour is the opposite. This is the `suppression_key` shape already in
STATE: a declared vocabulary item with three write sites and no consumer.

---

## 2. ⚠️ A peek system ALREADY SHIPS, and this session would be a third convention

`components/peek/` — `PeekHost.tsx`, `PeekTrigger.tsx`, `contexts/peek-context.tsx`,
and **six entity renderers** plus `_shared`. UI/UX arc follow-up 4, April 2026.

Three conflicts with §1 as dispatched:

| dispatched | shipped |
|---|---|
| ~300ms hover entry delay | **`HOVER_DEBOUNCE_MS = 200`** |
| ~150ms exit grace | **none found** — `PeekTrigger` has no mouseleave grace; `PeekHost` handles Escape and focus return |
| long-press on touch, release dismisses | **collapses hover to click** on `matchMedia("(pointer: coarse)")` |

The STOP line says do not invent a third convention silently. **200 vs 300 is a
direct conflict**, and the touch gesture is a *replacement* of shipped behaviour
rather than a gap being filled.

⚠️ The exit grace is the one place the dispatch describes something genuinely
missing. Its diagnosis — *the peek dies while the pointer travels into it* —
appears to be a live defect in the shipped peek, not a hypothetical.

---

## 3. ⚠️ The peek is ENTITY-keyed; the standing set is VIEW-keyed. Zero overlap.

```
PEEK_BUILDERS   : contact, fh_case, invoice, sales_order, saved_view, task
standing targets: ar_summary, line_status, scheduling.ancillary-pool,
                  today, vault_schedule
OVERLAP         : NONE
```

Nothing a standing line points at can render in the existing peek. Wiring them
is not "point the target at the peek that exists" — it needs a payload path that
does not exist yet.

---

## 4. But the payload source DOES exist — all five are widgets

**All five standing `target_key`s are widget ids** in the backend registry's 42
definitions: `ar_summary`, `line_status`, `scheduling.ancillary-pool`, `today`,
`vault_schedule`. The mapping is 1:1 and needs no invention.

⚠️ **I nearly reported the opposite.** My first check was `k in WIDGET_DEFINITIONS`
— and `WIDGET_DEFINITIONS` is a **list of dicts**, not a dict, so it compared each
string against dicts and returned False for all five. It printed "no widget of
that id" five times, which was a check passing for a reason unrelated to what it
claimed. The traceback on an unrelated line is the only reason I looked again.

---

## 5. What the session actually requires

Not larger in direction — the salvage doc pointed the right way — but larger in
work, and it needs rulings this dispatch does not contain:

1. **Implement `peek_inline` in the five widgets**, or build a chrome-stripping
   wrapper. Today the surface value is inert.
2. **Bridge view-keyed targets into a peek path.** Either extend `PEEK_BUILDERS`
   with a widget-backed kind, or give the note surface its own peek host. This is
   an architecture decision, not an implementation detail.
3. **Reconcile the timings against the shipped 200ms** rather than adding a
   second value.
4. **Decide whether touch long-press REPLACES the shipped click-collapse**, on a
   surface whose peek system is shared with the command bar, briefings and
   triage panels — changing it changes those too.

---

## 6. What was NOT done

No peek wired, no invalidation work, no timing constants introduced, no widget
touched. §2 (fragment-keyed invalidation) was not started: it is independent of
this STOP, but starting it would have meant reporting a half-session against a
premise already known to be false.

Read-only throughout. No production access needed or used.
