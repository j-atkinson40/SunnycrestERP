# S-3 Focus Escalation (§4.5 / §5) — Phase 1 Investigation

2026-07-24 · READ-ONLY · repo @ d313da1b · no code changed, no push
Governing canon: PLATFORM_ARCHITECTURE §4.5 (recognition-and-escalation), §5.1–5.4 (Focus primitive + core modes + pins), §5.14 (bounded-decision discipline), §5.15 (implementation foundation — Focus IS a base-ui Dialog; **Command Bar and Focus are mutually exclusive**) · PLATFORM_INTERACTION_MODEL · DESIGN_LANGUAGE · PLATFORM_QUALITY_BAR · S-1 findings (2026-07-23-s1-entity-portal.md) · S-2 findings (2026-07-24-s2-contextual-surfaces.md)

Two connective pieces under investigation: (1) the command bar detecting a deliberative quote and offering "open in Focus," and (2) the handoff — the S-2 quote-preview surface becoming the quote Focus's core. §5.2 assigns quote-building to an **edit-canvas** core.

---

## Headline

The hypothesis is **confirmed on every point**, and it forces one loud call:

- **The Focus shell + composition layer are shipped and production-wired** — base-ui Dialog shell (`Focus.tsx`), `useFocus().open(id, {params})` via `?focus=` URL, registry + `mode-dispatcher`, Canvas/pins/`WidgetChrome`/3-tier cascade, backend `focus_sessions` layout persistence. Two real cores exist: **kanban** (`SchedulingKanbanCore`, 1,720 LOC) and **triage-queue** (`TriageQueueCore`).
- **The edit-canvas core does NOT exist.** `editCanvas` is scaffolded end-to-end (in the `CoreMode` union, wired through the dispatcher, a Focus may register a specialized `coreComponent`), but `EditCanvasCore` is a **disabled placeholder** whose own header says *"Real canvas behavior … lands with the first real edit-canvas Focus … what Quote Building Focus (Phase B) will use"* (`cores/EditCanvasCore.tsx:1-11`). A quote-building core is **net-new**.
- **The handoff is a read-only→editable BUILD, not a re-parent.** The S-2 preview is a display-only widget (`WidgetRendererProps`, iframe `srcDoc`); an edit-canvas core is a different contract (`coreComponent<{focusId, config}>`) and is editable by definition. You don't transform the preview into the core — you **build a new editable line-item core and reuse the S-2 preview + price-list as display PINS around it.**

**→ LOUD STOP #1 (scope/sequencing, James's call): the edit-canvas core is net-new AND a real line-item quote editor is large enough that S-3 should SPLIT.** S-3a = escalation wiring + a *display-core* quote Focus (reuse the shipped S-2 preview + price-list as the Focus content; non-editable "review before send") — proves the escalation + handoff seam at ~600 LOC. S-3b = the full edit-canvas line-item editor core (~2k LOC + backend). See Deliverable 5.

The other two STOPs are **cleared** (good news): escalation does **not** require materializing a persisted Document (the core can hold the same in-memory draft the preview held — materialize only on save), and making the surface an editable core does **not** provably break S-5 re-hostability (the display widget survives as a distinct registration; the editable core can even stay re-hostable via the `AncillaryPoolPin` precedent).

---

## DELIVERABLE 1 — Core-modes build-vs-spec table (§5.2)

`MODE_RENDERERS` (`components/focus/cores/mode-dispatcher.tsx:36-42`) maps each `CoreMode` → a component; a registered Focus's `coreComponent` overrides the generic stub.

| §5.2 core mode | Built? | Component (file) | Evidence |
|---|---|---|---|
| **kanban** | ✅ real | `SchedulingKanbanCore.tsx` (1,720 LOC) via `funeral-scheduling`'s `coreComponent` | real @dnd-kit drag-drop, ~15 `useState`, finalize/QuickEdit. Generic `cores/KanbanCore.tsx` is a placeholder. |
| **triage-queue** | ✅ real | `cores/TriageQueueCore.tsx` | wraps the shipped Phase-5 `TriageWorkspace variant="focus"` scoped by `config.queueId` (`decision-triage` is the one real instance). |
| **EDIT CANVAS** | ❌ **stub only** | `cores/EditCanvasCore.tsx` | **disabled placeholder** — faux toolbar (all buttons `disabled`) + "Canvas placeholder"; header: "Real canvas behavior … lands with the first real edit-canvas Focus … Quote Building Focus (Phase B)." **No editable content, no line-item editor, no save/discard, no data binding.** |
| single-record | ❌ stub only | `cores/SingleRecordCore.tsx` | hardcoded "placeholder value" rows |
| matrix | ❌ stub only | `cores/MatrixCore.tsx` | static 4×4 em-dash table |

**Production Focus types registered: exactly two** — `funeral-scheduling` (kanban) + `decision-triage` (triage). No quote Focus, no `arrangement_scribe`. `editCanvas` is in the `CoreMode` union (`focus-registry.ts:35`) and a Focus can register `coreComponent?: ComponentType<{focusId, config}>` (`:206`), so the scaffolding is ready — **only the operational core component is missing.**

---

## DELIVERABLE 2 — The handoff decision (load-bearing)

### The handoff is NOT a re-host of the same widget — it's build-a-core + reuse-preview-as-pin.

Two hard facts force this:

1. **Command Bar and Focus are mutually exclusive** (§5.15, verified: `Focus`/`ReturnPill` mount above `CommandBarProvider` in `App.tsx:498`; the bar's Cmd+K + render are gated on `useFocus().isOpen`). So escalation **closes the command bar and opens the Focus** — there is no live surface to "re-parent." The handoff is a *state pass*, not a DOM move.

2. **Two different contracts.** The re-hostable widget is `WidgetRendererProps = {widgetId, variant_id?, surface?, onPivot?, config?}` (dispatched via `getWidgetRenderer`). A Focus **core** is `coreComponent<{focusId, config: FocusConfig}>` — a *different shape*, registered via `registerFocus`, mounted by name. The one production core (`SchedulingKanbanCore`) satisfies `{focusId, config}`, holds ~15 `useState`, and is **not** a `getWidgetRenderer` widget — operational cores are a separate, Focus-mounted class.

### So what an edit-canvas quote core actually is
**A structured line-item editor** — not "the `quote.standard` render made editable." Add/remove/reprice lines, product search + resolve (reusing the S-2 `resolve_product` fuzzy-with-refusal path), live re-price via the shipped `/command-bar/quote-preview` endpoint on each edit, customer + terms, save/send/discard. The **S-2 `surface.quote-preview` widget is reused verbatim as a display PIN** that shows the live-rendered document beside the editor (it already renders any draft via `render_preview_html`), and `surface.price-list-reference` is a second pin. The read-only→editable transform is: *the preview stays read-only and becomes a pin; a new editable core is built next to it.*

### What state the handoff carries — and does it create data?
- **Carries:** the S-2 `ExtractionContext` (`{entryIntent, customer, lines, rawInput}`) → passed via `useFocus().open("quote-focus", { params: ctx })` (`focus-context.tsx:125`) → seeds the core's initial draft. The extraction that fed the preview seeds the editor.
- **Creates data? NO — not required, and shouldn't.** Opening a Focus writes a `focus_sessions` row (JSONB **layout state**, best-effort, `POST /focus/{type}/open`) — *not* quote content. The quote draft lives in the core's in-flight state exactly as it lived in the preview; a `Document`/`Quote` materializes only on **"Create Quote / Save."** This preserves the S-2 principle that the preview never creates data. **STOP #2 cleared** — escalation does not require materializing a Document. (It *is* a nameable decision — Type B #2 — but the architecture supports draft-in-memory, so it's a choice, not a forced write.)

### Re-hostability reality check (S-1/S-2 claim vs the editable requirement)
The S-1/S-2 "re-hostable into a Focus" claim **holds for the display widget** — `surface.quote-preview` flows through `getWidgetRenderer` in the command-bar host, the Focus canvas/composition renderer, and `WidgetChrome` (park), all passing the same `WidgetRendererProps` (verified: all three dispatch via `getWidgetRenderer`, no host bypasses it). The **editable core is a different contract** and is naturally Focus-only — but that is **not** a failure of the contract, it's the Act/Decide difference made concrete: the *display* surface is re-hostable; the *decision* core is a core. **STOP #3 cleared** (see Deliverable 4).

---

## DELIVERABLE 3 — Escalation trigger + the §5.14 nameable decision

### Escalation is greenfield
No recognize-and-offer exists anywhere; the only CommandBar↔Focus link is the suppression gate. `useFocus().open(id, {params})` is ready — the bar just needs to call it (the `open_focus` button dispatch already wraps `focus.open`).

### The trigger signal — recommend EXPLICIT, user-clicked (v1)
§4.5's decision-shaped signals (open-ended / multiple items / comparison / long-refine) **don't cleanly auto-fire for a quote**: a quote has a specific entity (customer + product), and — critically — **the "multiple product lines" signal is undetectable today.** `ExtractionContext.lines` is typed `QuoteDraftLine[]` but `normalizeExtraction` does a single `push` from the one `ask_product` field (`NaturalLanguageOverlay.tsx:87-102`), so the array never holds >1 line. "User kept building / is comparing options" cannot be detected until the extractor is extended to emit multiple lines.

**Recommendation:** the v1 trigger is an **explicit "Build this quote out →" affordance**, offered whenever `entryIntent === "quote"` (+ a resolved customer or a priced line), user-clicked. §4.5's escalation is *user-initiated by design* ("want me to open a Focus on it?" → one-click), so an explicit offer is faithful, not a shortcut. Auto-escalation on a real "kept building" signal (multi-line) is deferred to when the extractor supports multiple lines. **Best seam:** an interpretation-style chip in the overlay's intent-badge row (`NaturalLanguageOverlay.tsx:503-546`, the shipped "wrong type?" pattern) — always-visible incl. mobile; its `onClick` calls `useFocus().open(...)` instead of a state reset. (A suppressible `CONTEXTUAL_SURFACES` entry is the desktop-side-column alternative, but it's `lg`-only.)

### The §5.14 nameable decision (anti-pattern guard — PASSES)
> **The quote Focus closes: "what goes in this quote and at what price — commit on send/save, or discard."**
> Exit: on send / save / discard. Not "when done looking around."

This is a bounded, nameable decision with a clean exit — it passes §5.14. It is emphatically *not* a dashboard-with-delusions: there is one artifact (the quote), a finite set of edits, and a terminal action. Hold the line confirmed.

---

## DELIVERABLE 4 — Contract + forward-wiring (S-5 park)

### Pins: the price-list surface CAN be a Focus pin — static free, live needs wiring
**Correction to the CLAUDE.md note:** the r84 `focus_compositions`/`composition_service` layer was **greenfield-replaced in r96** with a three-tier chain `focus_cores → focus_templates(placements/12-col grid) → focus_compositions(per-tenant delta)`. Placements carry **static `prop_overrides`** (a frozen dict); the runtime renderer (`CompositionRenderer.renderRuntimePlacement`) passes `config = prop_overrides` verbatim via `getWidgetRenderer`.

- **Static pin — zero new infra:** place `surface.price-list-reference` with `prop_overrides: {products, customerId}`; it self-fetches. But `products` is *frozen* in the composition JSONB — it won't track the core's draft.
- **Live-config pin (products track the draft) — needs new wiring.** The composition schema has **no `configFrom` equivalent** (S-2's live per-render derivation). The closest seam, `FocusContextBridge` + `useOperationalProps`, is *not* wired into the default dispatch and the S-2 widgets read `config`, not operational props.
- **The clean path for v1 (recommended): bypass the composition-placement layer entirely.** Follow the `SchedulingFocusWithAccessories` precedent — a `QuoteFocusWithAccessories` wrapper mounts the edit-canvas core **in code** and renders the price-list + preview widgets **directly**, passing live-derived `config` from the core's draft each render (exactly the `surfacesForIntent`/`configFrom` pattern, now inside the wrapper). This gets live pins with no composition-layer change. (Note: the scheduling template seeds **zero** accessory placements today — `rows: []` — so the composition-authored accessory path isn't even populated in production yet; hand-composition is the shipped-precedent path.)

### S-5 park forward-compat — NOT broken (STOP #3 cleared)
The re-host seam lives at the widget-registry boundary, and all three hosts (command-bar Act host, Focus canvas/`WidgetChrome`, composition renderer) dispatch via `getWidgetRenderer` with identical `WidgetRendererProps`. Two facts keep the door open:
1. **The display widgets are distinct registrations that survive untouched.** Building the editable core doesn't touch `surface.quote-preview` / `surface.price-list-reference` — S-5 parks *those* unchanged.
2. **Even the editable component can stay re-hostable** via the `AncillaryPoolPin` precedent (registered as a `getWidgetRenderer` widget, stateful, but externalizes its store to a feature-owned optional context — `useSchedulingFocusOptional`; config-in for identity, `null`-safe when the host doesn't provide the store).

So the editable transform is **one-way only if you choose to make it so** (internal mutable state under `coreComponent`, mounted by name — the kanban pattern). v1 can ship the core Focus-only (simplest) *without* closing S-5, because S-5 parks display surfaces, not the decision core. **Flag:** if a future arc wants to park the *editable* quote core itself, build it with externalized draft state from the start (AncillaryPoolPin pattern) — cheap if done at inception, a refactor if retrofitted.

---

## DELIVERABLE 5 — LOC floor, split into (a) escalation and (b) the edit-canvas core

Deliberately separated because (b) is large — this is the split recommendation made concrete.

### S-3a — escalation wiring + display-core quote Focus (~600 LOC floor)
| Work | LOC floor |
|---|---|
| Escalation affordance (chip in the overlay intent-badge row) + `entryIntent==="quote"` guard + `useFocus().open("quote-focus", {params: ctx})` | ~120 |
| `quote-focus` registration (`registerFocus`, mode, `coreComponent`) + params→draft seeding | ~80 |
| `QuoteFocusWithAccessories` wrapper: mounts a **display core** (reuse `surface.quote-preview` at full size, non-editable) + price-list pin, live-derived `config` from the seeded draft (the `surfacesForIntent`/`configFrom` pattern inside the wrapper) | ~250 |
| vitest (escalation offer render/guard, open wiring, wrapper composition) | ~150 |
| **S-3a floor** | **≈ 600** |

S-3a ships the *whole seam* — escalation → Focus opens → preview + price-list as the Focus's anchored content, seeded from the extraction — with **no new editable core**. It proves the handoff and escalation end-to-end and is demo-ready ("open the quote in a Focus to review before sending").

### S-3b — the edit-canvas line-item core (~1,500–2,500+ LOC floor)
| Work | LOC floor |
|---|---|
| `QuoteEditCanvasCore` — line-item editor: add/remove/reprice rows, product search+resolve (reuse `resolve_product`), qty, customer/terms, live re-price via `/quote-preview` on edit, save/send/discard | ~1,000–1,600 |
| Backend: draft persistence (if drafts persist across sessions) + materialize `Quote`/`Document` on save (reuse `quote_service.create_quote`) | ~300–500 |
| Parity/money tests (edit → re-price matches the order resolver; save materializes the same figures) + vitest for the editor | ~350 |
| **S-3b floor** | **≈ 1,500–2,500** |

The gap between (a) and (b) is the justification for the split: (a) is a wiring arc; (b) is a real editor + its money-math discipline.

---

## Type B calls for James (handoff-size + trigger-signal first)

**#1 — SPLIT S-3? (the load-bearing sequencing call).** (a) S-3a now (escalation + display-core quote Focus, ~600 LOC, proves the seam), S-3b later (the ~2k-LOC edit-canvas editor); vs (b) one large S-3 building the full editable core up front. **Investigator's read: SPLIT.** S-3a delivers the escalation + handoff architecture and a demoable quote Focus without gating on a from-scratch editor; S-3b is a self-contained editor arc with its own money-math parity gates. This also de-risks — the seam is proven before the big build.

**#2 — Does escalation create a draft Document, or hold in-memory?** (a) in-memory draft (materialize `Quote`/`Document` only on save — preserves the S-2 never-creates-data principle) vs (b) create a draft Document on open (persists across devices/sessions immediately). **Read: (a)** for S-3a/S-3b v1 — the `focus_sessions` row already gives session continuity for *layout*; the quote *content* stays in-flight until save, matching the preview. Revisit (b) only if "resume this half-built quote on another device" becomes a requirement.

**#3 — Trigger signal.** (a) explicit user-clicked "Build this out →" whenever `entryIntent==="quote"` vs (b) auto-escalate on a "kept building" heuristic. **Read: (a)** — (b)'s multi-line signal is undetectable today (single-line extraction); §4.5 escalation is user-initiated anyway. Extending the extractor to emit multiple lines (enabling auto-escalation + multi-product quotes) is its own downstream call, not S-3's.

**#4 — Pins: static or live.** (a) live-config pins via a `QuoteFocusWithAccessories` wrapper that derives pin `config` from the core draft each render (no composition-layer change) vs (b) static composition-authored placements (frozen products) vs (c) build the live-config seam into the composition layer (`configFrom` for placements). **Read: (a)** for v1 — the wrapper precedent (`SchedulingFocusWithAccessories`) is shipped and gives live pins immediately; (c) is a general composition-layer enhancement worth its own arc, not a S-3 dependency.

**#5 — Editable core re-hostable, or Focus-only.** (a) Focus-only core (kanban pattern, simplest) — S-5 still parks the display widgets vs (b) build the editable core re-hostable from inception (AncillaryPoolPin externalized-state pattern). **Read: (a) for v1**, but *name the choice at S-3b build time* — externalizing the draft store is cheap at inception and preserves the option to park the editable core later; retrofitting is a rewrite.

---

## STOP CHECK (all three dispatch STOPs, explicitly)

- **STOP if no edit-canvas core exists AND building one is large enough that S-3 should split** → **TRIPPED, surfaced loudly.** No edit-canvas core exists (net-new); a real line-item editor is ~1.5–2.5k LOC. **Recommend split: S-3a (escalation + display-core, ~600) / S-3b (edit-canvas core, ~2k).** James's sequencing call.
- **STOP if the handoff requires materializing a persisted Document on escalation** → **CLEARED.** It does not — opening the Focus writes only a `focus_sessions` layout row; the quote draft stays in-memory (like the preview), materializing on save. It's a nameable choice (Type B #2), not a forced write.
- **STOP if making the surface an editable core provably breaks S-5 re-hostability** → **CLEARED.** It does not — the display widgets survive as distinct registrations (S-5 parks those), and even the editable core can stay re-hostable via the AncillaryPoolPin precedent. One-way only if built the internal-mutable-state way, which is a build choice, not a forced consequence.

---

— Read-only confirmed: no code, no schema, no test, no doc besides this file changed; no Type B decided; nothing pushed. This file is the sole write. —
