# Pulse consumers — what may go, what must stay, and three claims that were wrong

**Date:** 2026-09-10 · **HEAD:** `7b09f635` · **Read-only — no application source changed.**

The steps 4–5 dispatch flagged consumer enumeration as the risk: *"an unreached
module is the easiest to remove correctly and the hardest to find consumers for
by grep."* This is that enumeration, done before any deletion.

Nothing is inherited from the 2026-09-04 salvage investigation. Every figure was
re-derived at this HEAD.

---

## 0. Headline

**Three survival claims in the dispatch are wrong, and one is wrong in the
dangerous direction.**

| Claim | Reality |
|---|---|
| "IntelligenceStream's payload… in use by the note surface" | The **component** `AnomalyIntelligenceStream`'s only consumer is `PulsePiece`, which is being deleted. `NotePage` imports nothing but React and `apiClient` and renders its own `<Spans>`. |
| "foundation widgets are consumed by the standing set" | The standing set renders plain `label + count` divs and **no widgets at all**. The widgets survive — for a completely different reason. |
| `pulse_signals` "0 rows, dev only" | Now measured in **production**: also 0. Stronger than the salvage claim, and `component_configurations` gives a genuinely enumerated absence. |

**The dangerous one is the second.** The widgets must stay, so the conclusion
holds — but the stated reason is false, and a future session that retires the
note's standing set would read that reason and conclude the widgets are now
free. They are not: they are consumed by Canvas, BottomSheet, StackRail,
CompositionRenderer, PinnedSection, CommandBarSurfaceHost and ParkCanvas.

**One column must not be removed with Pulse**: `users.work_areas` is read by the
**note surface itself**.

---

## 1. The removal set, enumerated

### 1.1 Backend — `services/pulse/` is 10 files, 2,503 LOC

```
  50  __init__.py                294  activity_layer_service.py *
 253  anomaly_intelligence_v1.py 264  anomaly_layer_service.py
 301  composition_cache.py       215  composition_engine.py
 291  operational_layer_service  310  personal_layer_service.py
 431  signal_service.py          194  types.py
```
Plus `api/routes/pulse.py` (349), `models/pulse_signal.py` (88),
`subscribers/pulse_subscriber.py` (85), `alembic/r61_…` (196, keep — history).

**Total in-scope backend: 3,025 LOC**, against the dispatch's ~2,933. The
difference is `pulse_subscriber` (85) and drift.

Production (non-test) importers, enumerated — **five sites only**:
`models/__init__.py:396`, `routes/pulse.py:34-35`, `services/tasks/__init__.py:26`,
`pulse_subscriber.py:61`, and one prose mention in `fragments/platform_defaults.py:276`.

⚠️ **One test consumer the salvage doc did not name:**
`tests/tasks/test_b3_consumer_integration.py` imports
`personal_layer_service._build_tasks_item` at five sites. That is the **task
substrate's** consumer-integration suite reaching into a Pulse internal. It is a
test, not production — but the removal breaks it, and it belongs to a different
arc.

### 1.2 Frontend

Removable, with consumers confined to the set: `PulseSurface` (305),
`PulseLayer` (282), `PulsePiece` (298), `PulseFirstLoginBanner` (101),
`usePulseComposition` (95), `pulse-service` (81),
`utils/renderability` (76), `utils/layer-row-count`, `viewport-fit-constants`,
plus four `PulseSurface.*.test.tsx` files (2,181 LOC of test).

⚠️ **`hooks/useViewportFitMath.ts` is Pulse-only and the salvage doc never named
it.** Chain, verified: `viewport-fit-constants` → `useViewportFitMath` →
`PulseSurface` / `PulseLayer`. Nothing else imports either.

---

## 2. What must stay, with the real reason

### 2.1 `types/pulse.ts` — partially

Two live importers survive: `AnomalyIntelligenceStream.tsx` and
`types/fragments.ts`, both for `IntelligenceStream` + `ReferencedItem`.
`types/fragments.ts` has **zero importers of its own** and exists as a
compile-time assertion (`PAYLOAD_SHAPES_AGREE`) that the two payload shapes
match. The rename must land before the delete, and the blast radius is one file.

### 2.2 `AnomalyIntelligenceStream` — orphaned, not consumed

Its only consumer is `PulsePiece:204`. After the removal it has **zero**. It is
not what the note renders. This is a decision the dispatch did not anticipate:
keep it as the prose renderer the note should arguably be using, or delete it as
unreached. **Surfaced, not decided.**

### 2.3 Foundation widgets — consumed, but not by the note

10 widgets registered via `register.ts` into the **canvas widget-renderer
registry**. Real consumers: `Canvas`, `BottomSheet`, `StackRail`,
`StackExpandedOverlay`, `CompositionRenderer` (Focus accessories),
`PinnedSection` (space pins), `CommandBarSurfaceHost`, `ParkCanvas`, and the
visual-editor registry. **None of them is the note.**

### 2.4 ⚠️ `users.work_areas` — read by the note surface

`r61` is named `user_work_areas_pulse_signals` and creates **a `work_areas`
column on `users`** plus the `pulse_signals` **table**. Only the table goes.

The column has non-Pulse consumers: `operator_profile_service`,
`routes/operator_profile`, `OperatorOnboardingFlow.tsx`, and — decisively —
`services/note/registry.py:56` and `note/types.py:23`, where the standing-set
registry resolves per work-area.

⚠️ **My own error, recorded:** I probed for a table called `user_work_areas`,
constructing the name from the migration's filename. It has never existed. That
is "a scope taken from a filename", in the probe written to check someone else's
claim.

### 2.5 The peek layer

Independent. No peek module imports any Pulse module; peek renders widgets
through `getWidgetRenderer`, which is the canvas registry, not Pulse.

---

## 3. `pulse_subscriber` — safe to remove, established by enumeration

`EVENT_TYPES` is **7** events. `register_subscriber`'s `event_types` **defaults
to all seven**, so `audit_writer`, which passes none, subscribes to everything.

| event | subscribers now | after removing `pulse_invalidator` |
|---|---|---|
| task_created | 4 | 3 |
| task_assigned | 4 | 3 |
| task_status_changed | 3 | 2 |
| task_completed | 7 | 6 |
| task_cancelled | 7 | 6 |
| task_blocked | 1 | 1 |
| task_unblocked | 1 | 1 |

**No event is orphaned. The STOP does not fire.**

⚠️ Two method notes. My first pass extracted event names with a regex requiring a
dot (`"[a-z_]+\.[a-z_]+"`); task events have none, so it reported **zero events
for every subscriber** — a constructed pattern returning a clean, false table.
And the AST pass that replaced it initially showed `audit_writer` with `[]`
events, which is the *implicit all-seven* default rather than an absence. Both
would have understated the coverage that makes this removal safe.

`services/tasks/__init__.py:5` says "7 events, 6 subscribers". There are **8**.
Stale docstring, unrelated to this work, recorded rather than fixed.

---

## 4. The CHECK constraint — production, read-only

Probed through a connection-level `default_transaction_read_only=on` guard;
credentials redacted to host/port/db.

| | dev | production |
|---|---|---|
| `component_configurations` WHERE kind='pulse-widget' | 0 | **0** |
| distinct kinds present | **(table empty)** | **['widget']** |
| `component_class_configurations` WHERE class='pulse-widget' | 0 | 0 |
| distinct classes present | (table empty) | (table empty) |
| `pulse_signals` | 0 | **0** |

⚠️ **Dev proves nothing here and the salvage doc's "0 rows" leaned on it.** Both
config tables are entirely empty in dev, so "zero pulse-widget rows" is
trivially true. Production is the informative measurement: the table **is**
populated, and an enumeration of its distinct kinds returns `['widget']` alone.
That is an absence established by enumeration rather than by a filtered count.

`component_class_configurations` is empty in production too, so its half of the
constraint drop is safe but unevidenced in the same way — stated rather than
implied.

⚠️ **A failed statement aborts the transaction, and every later query in it
returns `InternalError` — which reads exactly like a real zero.** The first
version of this probe hit that: `user_work_areas` did not exist, and both
enumerations after it came back empty for that reason rather than from the data.
Each query now runs on its own connection.

---

## 5. Owed before the removal commit

1. **A ruling on `AnomalyIntelligenceStream`** (§2.2) — orphaned by the removal.
2. **`tests/tasks/test_b3_consumer_integration.py`** (§1.1) reaches into
   `personal_layer_service`; the task substrate's suite needs its own fixture.
3. The `types/fragments.ts` rename lands before `types/pulse.ts` is touched.
4. `ON DELETE` behaviour on both CHECK-constraint tables, per the `r177`
   precedent, before either constraint is dropped.
