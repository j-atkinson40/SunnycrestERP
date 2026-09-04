# Pulse salvage — what is note infrastructure wearing a dashboard's name

**Date:** 2026-09-04 · **HEAD:** `65c39d3b` · **Read-only — no application source changed.**

Answers the seven questions in the 2026-09-04 salvage dispatch. Every claim below
was measured against the repo at that HEAD unless marked **REPORTED**.

**Verdict vocabulary:** SALVAGE (serves the note with modification) · RENAME
(serves it as-is under a truer name) · DELETE (dashboard-specific).

---

## 0. Headline

**The prose fragment already exists in the codebase.** It is called
`IntelligenceStream`, and it carries synthesized prose plus typed entity links.
**The two registers already exist** in the widget surface enum: `spaces_pin`
("Glance-only") and `peek_inline` ("no chrome"). The dashboard-specific
machinery is narrower than the file count suggests — it is concentrated in grid
placement, tetris fitting, and the dismiss affordance.

The single largest correction the dispatch needs: **its Q3 named two backend
files; enumeration finds twelve, totalling ~2,850 LOC.**

---

## 1. Per-component salvage table

| Component | LOC | Verdict | Confidence |
|---|---|---|---|
| `IntelligenceStream` type + `AnomalyIntelligenceStream` | 112 / 132 | **RENAME** → prose fragment | High |
| 10 foundation widgets | — | **SALVAGE** | High |
| `WidgetSurface` enum + variant contract | — | **SALVAGE** | High |
| `PulsePiece` | 298 | **SALVAGE** minus grid + dismiss | High |
| `PulseFirstLoginBanner` | 101 | **SALVAGE** → peek first-run hint | Medium |
| `composition_engine.py` | 215 | **SALVAGE** (ordering/assembly) | Medium |
| 4 layer services | 1,052 | **SALVAGE** as fragment sources | Medium |
| `pulse_signal` + `signal_service.py` | 88 / 431 | **Type B** — see §5 | — |
| `composition_cache.py` | 301 | **SALVAGE**, wrong granularity | High |
| `PulseSurface` / `PulseLayer` | 305 / 282 | **DELETE** (layer/grid orchestration) | High |
| `viewport-fit-constants` + `layer-row-count` | 155 / 120 | **DELETE** (tetris math) | High |
| `utils/renderability.ts` | 76 | **DELETE** | Medium |
| `pulse-widget` ComponentKind | — | **DELETE** — zero instances, see §7 | High |

---

## 2. Q1 — `PulsePiece`

**SALVAGE with surgery.** It is a four-job component: dispatch (widget renderer
vs. intelligence stream), Pattern-2 card chrome, signal collection, and grid
placement.

⚠️ **Correction to a claim made earlier today.** A first read of the props
signature concluded PulsePiece was not grid-aware, since `cols`/`rows` live on
`LayerItem` rather than on the component. That was inference from a signature and
it was wrong. Verified: `PulsePiece.tsx:235-236` sets `gridColumn: span
${item.cols}` and `gridRow: span ${item.rows}`. The grid coupling is real, and it
is two lines.

What survives: the dispatch between a typed-payload renderer and a prose
renderer, which is exactly the note's standing-line-vs-fragment split.

What does not: the card chrome (the note is prose, not bounded cards — see §6),
the grid placement, and the dismiss affordance (§6, contradiction 1).

---

## 3. Q2 — the 10 foundation widgets

**SALVAGE, high confidence. They do not assume a dashboard viewport.**

Enumerated from `frontend/src/components/widgets/foundation/` (10 files,
excluding `register.ts`): Anomalies, Briefing, CalendarConsentPending,
CalendarGlance, CalendarSummary, EmailGlance, OperatorProfile, RecentActivity,
SavedView, Today.

`WidgetSurface` (`components/widgets/types.ts:40-46`) declares **7** surfaces:

```
pulse_grid       — Pulse responsive grid (per-Space)
focus_canvas     — Focus free-form canvas (anchor-positioned)
focus_stack      — Focus stack rail (mobile tier)
spaces_pin       — Spaces sidebar pin (Glance-only)
floating_tablet  — Command bar floating tablet (peek content)
dashboard_grid   — Operations Board / Vault Overview / hub dashboards
peek_inline      — Peek panel content composition (no chrome)
```

Widgets declare `supported_surfaces` + `default_surfaces` and carry per-variant
sizing, with variants `glance | brief | detail | deep`.

**The note's two registers are already expressible in this contract.** A standing
line is `spaces_pin` at Glance. A peek payload is `peek_inline` — already
specified as *no chrome*, which is what a peek over prose requires. Only
`pulse_grid` and `dashboard_grid` are dashboard-shaped, and dropping two enum
values does not disturb the other five.

---

## 4. Q3 — the backend, which is six times the size the dispatch assumed

The dispatch named `pulse_signal` model and `routes/pulse.py`. Enumerating
`backend/app/services/pulse/` finds **nine further modules**:

| Module | LOC |
|---|---|
| `signal_service.py` | 431 |
| `personal_layer_service.py` | 310 |
| `composition_cache.py` | 301 |
| `operational_layer_service.py` | 291 |
| `anomaly_layer_service.py` | 264 |
| `anomaly_intelligence_v1.py` | 253 |
| `composition_engine.py` | 215 |
| `types.py` | 194 |
| `activity_layer_service.py` | 187 |
| `__init__.py` | 50 |

**2,496 LOC**, plus `routes/pulse.py` (349) and `pulse_signal.py` (88) = **~2,933
LOC** of backend Pulse. The dispatch's Q3 was a name-scoped list rather than an
enumeration; the directory holds most of the mass.

### Does any of it map to the fragment contract's four declarations?

`IntelligenceStream` (`types/pulse.ts:64-71`) carries `stream_id`, `layer`,
`title`, **`synthesized_text`**, **`referenced_items`**, `priority`. Each
`ReferencedItem` is `{kind, entity_id, label, href}`.

That is the *payload* of a prose fragment: prose, plus typed links that resolve
to entities. `priority` is the urgency ordering the entry requires.

**But it carries none of the four declarations.** Mapping honestly:

| Fragment contract declaration | Present today? |
|---|---|
| (1) permission predicate — who sees it | **No.** No permission field on the stream. |
| (2) condition that brings it into existence | **Partial, and implicit.** Each layer service decides internally; the condition is code, not declared data. |
| (3) what it opens, and with what scope | **Partial.** `href` is a destination; there is no scope carry, so a link opens a generic surface the user then filters — the exact failure the entry names. |
| (4) state transition that ends it | **No.** The only exit is `dismissed`, which the canon prohibits. |

**Verdict:** the payload shape is a rename. The contract is genuinely new work.
`IntelligenceStream` is the fragment's body without its declarations.

---

## 5. Q4 — the subscriber: right stream, wrong granularity, and a count correction

⚠️ **Correction to canon landed today.** The 2026-09-04 fragment entry states the
subscriber "already receives task_created / task_assigned / task_status_changed."
Measured at `pulse_subscriber.py:73-81`, it registers **five** event types — those
three plus **`task_completed` and `task_cancelled`**. The entry is true but
undercounts. DECISIONS is append-only; this is a note for a future entry, not an
edit. The error is mine: I reported three from a docstring excerpt this morning
rather than from the registration call.

**Granularity is wrong for per-fragment regeneration.**
`composition_cache.invalidate_for_user(user_id)` (`composition_cache.py:268`)
"drop[s] **all** cached compositions for a given user across all work_areas
hashes + minute windows." That is whole-surface eviction. Per-fragment
incremental regeneration — which the entry requires, and which is the precondition
for wording stability across refreshes — needs per-fragment keys. Whole-user
eviction re-composes everything, which re-words everything.

**Scope is narrower than the entry implies.** This is the *task* lifecycle
stream. Fragments also need material-change signals from deliveries, invoices,
schedule conflicts, and the inbox. Calling it "the material-change stream
fragments need" overstates a real but partial asset.

**Recommended framing:** adopt the subscriber *pattern* — a registry of typed
lifecycle subscribers — and add fragment-keyed invalidation. The task subscriber
becomes the first of several sources, not the source.

---

## 6. Three findings that contradict the 2026-09-04 entries

### Contradiction 1 — dismiss is shipped, and canon prohibits it

`LayerItem.dismissed`, `DismissSignalRequest`, and PulsePiece's dismiss X
("opacity-30 default → opacity-100 hover, brass on hover") implement exactly the
affordance the deferral entry rules out: *"There is no 'make this go away.'"*

This is a **behavior deletion**, not a rename, and it reaches further than the
button: `signal_service.py` (431 LOC) is substantially built around dismiss and
navigate signals feeding "Tier 2 algorithms." Retiring dismiss without deciding
what replaces it as a ranking input leaves that service without half its inputs.
**Type B — surfaced, not decided.**

### Contradiction 2 — `dwell_time_seconds`

`NavigateSignalRequest` carries `dwell_time_seconds`, computed per piece per
user. The prompts entry says attribution "never carries timing emphasis and is
never aggregated into per-user resolution counts; the moment such a number
exists, someone will look at it."

Component dwell for ranking is not user-performance attribution, so this is not a
direct violation. But the entry's own argument — that the number's existence is
the risk — applies to a per-user timing measure regardless of intent.
**Type B.**

### Contradiction 3 — the intelligence mark is a color

`AnomalyIntelligenceStream` signals "composed by intelligence" with a "1px
aged-brass divider" at the top edge. The text-states entry rules that no color
carries the measured/inferred distinction.

These differ in granularity: the brass thread marks a whole block as composed;
the entry requires per-phrase distinction *within* prose. So the existing mark is
not the thing the entry prohibits — but it occupies the same visual role and will
read as the inference mark to a user. **Type B**, and the aesthetics arc owns it.

---

## 7. Q7 — `pulse-widget` is a kind with no instances

**15 occurrences across 12 files.** CHECK constraint text appears in
`r81_component_configurations.py:112` and three times in
`r83_component_class_configurations.py` (`:41`, `:134`, `:186`).

Measured against `bridgeable_dev`:

```
component_configurations   WHERE component_kind='pulse-widget'   → 0 rows
component_class_configurations WHERE component_class='pulse-widget' → 0 rows
pulse_signals                                                     → 0 rows
```

And **zero** registrations declare `type: "pulse-widget"` in
`lib/visual-editor/registry/registrations/`.

**Verdict: DELETE.** The kind was declared in the ComponentKind enum, wired
through the Studio inspector, edit-mode context, preview-data icon map, registry
debug page, and both backend constraint lists — and nothing was ever registered
as one. Retirement is **one migration altering two CHECK constraints, with no
data migration**, plus removal from 10 non-migration files.

⚠️ `pulse_signals` at 0 rows is **measured on dev only**. It means the signal
machinery has recorded nothing here; it is not evidence the write path is
unreachable, and it should not be reported as such. Staging and production were
not queried.

---

## 8. Q5 / Q6 — surface orchestration and the `/home` assumption

**Q5.** `PulseSurface` (305) and `PulseLayer` (282) orchestrate four named layers
into a responsive grid; `viewport-fit-constants` (155) and `layer-row-count`
(120) are tetris fitting — how many rows a layer occupies given column count and
per-item `cols`/`rows`. All four are **DELETE**: the note has no layers and no
grid. `PulseSurface.test.tsx` (890) tests grid composition and goes with them.

`PulseFirstLoginBanner` (101) is **SALVAGE**, and usefully: the peek entry names
discoverability as the known risk of release-dismisses and a first-run hint as
the mitigation. A shipped first-login banner component is that mitigation's
chassis.

**Q6.** Six files assume `/home`:
`root-redirect.tsx:43` (`<Navigate to="/home" replace />`), `HomePage.tsx:24`
(`return <PulseSurface />` — the mount), `App.tsx`, `lib/runtime-host/page-contexts.ts`,
`lib/runtime-host/TenantRouteTree.tsx`, and
`lib/visual-editor/registry/registrations/buttons.ts`.

The swap is contained: `HomePage` is a 24-line wrapper whose entire body is the
Pulse mount. Pointing `/home` at the note surface is a one-line change in one
file; the other five reference the route, not the surface.

---

## 9. Session estimate

**Salvage-heavy reading — 4 sessions after the contract sub-arc.** Holds if
`IntelligenceStream` renames to the fragment payload, the four layer services
become fragment sources behind the new contract, widgets render at `peek_inline`
and `spaces_pin` unchanged, and `composition_engine` survives as the ordering
pass. Work is then: fragment-keyed invalidation, prose composition over the
renamed payload, the peek layer, settling + deferral, owner/backup routing.

**Rebuild-heavy reading — 6 to 7 sessions.** Holds if the four declarations force
the layer services to be rewritten rather than wrapped, since none of them
declares permission, scope-carry, or an end transition today, and retrofitting
declarations into 1,052 LOC of layer services that compute their conditions
inline may cost more than writing sources against the contract.

**The discriminator is answerable in the contract sub-arc and should be measured
there, not estimated now:** take one layer service — `anomaly_layer_service.py`
(264 LOC) is the smallest with a real condition — and express its output as a
declared fragment. If it wraps, the estimate is 4. If it has to be rewritten,
it is 6+. One session's work decides the other five.

The dispatch's own no-interim ruling helps here: with no coexistence requirement,
salvage can be aggressive. Nothing has to keep working while the swap happens.

---

## 10. Method notes

- **The dispatch's Q3 undercounted by naming files rather than enumerating a
  directory.** Two named; twelve exist. This is the constructed-name shape at
  dispatch altitude rather than at query altitude — the brief inherited a file
  list from a prior report instead of re-deriving it.
- **One inference retracted mid-investigation.** PulsePiece's grid coupling was
  read out of a props signature and concluded absent; it is present at
  `:235-236`. Signatures are not implementations.
- **Counts are occurrences, not lines,** where stated (`pulse-widget`: 15
  occurrences / 12 files, via `grep -o | wc -l`).
- **Zero-row measurements are dev-only** and are labelled as such in §7.
