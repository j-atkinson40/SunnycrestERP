# S-3b Edit-Canvas Quote Core (§5.2) — Phase 1 Investigation

2026-07-24 · READ-ONLY · repo @ 3e2fd9c9 · no code changed, no push
Governing canon: PLATFORM_ARCHITECTURE §5.1–5.4 (Focus + core modes + pins), §5.6 (exit/re-entry), §5.7 (layout state — widget geometry, three-tier), §5.14 (bounded-decision), §5.15 (impl foundation) · CLAUDE.md "Focus Composition Layer" + "Focus Canvas tier-renderer pointer-events contract" · DESIGN_LANGUAGE · PLATFORM_QUALITY_BAR · S-1/S-2/S-3a findings.

S-3b: the EDITABLE edit-canvas quote core that replaces S-3a's display-only core. Directors add/remove/reprice/reorder line items and watch the total move. The first editable Focus core.

---

## Headline — all three STOPs CLEARED; S-3b is buildable

- **Externalized state (one-way-door STOP): CLEARED.** The `AncillaryPoolPin` pattern proves stateful-yet-re-hostable: a feature context (`createContext<T | null>(null)`) with a paired `useX()` (throws) / `useXOptional()` (null-safe) hook. The null-safe hook keeps the **park door open** — a parked quote widget with no provider degrades to read-only, it does not break. Internal `useState` under `coreComponent` would close the door; the context pattern does not.
- **Pointer-events tier contract (silent-breakage STOP): CLEARED — and it doesn't even apply to the core.** The core region is naturally `pointer-events: auto`; the `pointer-events: none` layer is the Canvas (pins), a *sibling on top* that passes events through. The core is mounted once for all tiers (never collapses). `SchedulingKanbanCore` — drag-drop + clicks + a dialog — is the working proof. Followable by replication.
- **Re-pricing / drift (mis-price STOP): CLEARED.** The shipped S-2 `/command-bar/quote-preview` endpoint prices an **arbitrary** edited line set through the **same** `render_preview_html("quote.standard")` path (drift guard holds), multi-line math is correct (per-line `get_effective_price`, sum-of-rounded-lines subtotal, tax on the multi-line subtotal), and refusal-under-ambiguity is **line-source-agnostic** (a typed "Bronze" refuses exactly like an extracted one). No second renderer, no other pricing path.

**S-3b builds the EDITING SURFACE, not pricing.** The bounded net-new work: a `QuoteFocus` draft context (mutable store), the editable line-item core, two *additive* backend response fields (structured per-line breakdown + optional per-line override), and the SAVE materialization (reuse `create_quote`). LOC floor ≈ **1,700** (Deliverable 5).

---

## DELIVERABLE 1 — The draft-store externalization shape (load-bearing)

Copy `SchedulingFocusContext` (`contexts/scheduling-focus-context.tsx`) verbatim in shape:

```ts
// contexts/quote-focus-context.tsx  (net-new)
interface QuoteDraftLine { productRef: string; productId?: string; quantity: number
                           unitPriceOverride?: number /* S-5a, optional */ }
interface QuoteFocusContextValue {
  customer: { id?: string; name: string } | null
  lines: QuoteDraftLine[]
  addLine: (line: QuoteDraftLine) => void
  removeLine: (index: number) => void
  updateLine: (index: number, patch: Partial<QuoteDraftLine>) => void
  reorderLine?: (from: number, to: number) => void   // follow-on
}
const QuoteFocusContext = createContext<QuoteFocusContextValue | null>(null)  // null = "outside provider"
export function useQuoteFocus(): QuoteFocusContextValue { /* throws if null — strict */ }
export function useQuoteFocusOptional(): QuoteFocusContextValue | null { return useContext(QuoteFocusContext) }
```

- **The provider holds the MUTABLE draft** (`lines` + `add/remove/update/reorder`), **seeded from S-3a's `currentFocus.params.extraction`** on mount. This is the exact transform: S-3a's read-only in-memory pass-through (`QuoteFocusWithAccessories.tsx:48-55`) becomes a mutable store — **without moving to internal core `useState`**.
- **Core/context boundary** (per the `SchedulingFocus` precedent): the *shared draft* (lines, mutations) lives in the context — both the editable core AND the preview/price-list pins read it; the editable core also *writes* it. Private UI state (which row is mid-edit, focus ring) stays local `useState` in the core (fine — it's not shared and not the draft).
- **The pins read the draft from the context**, not from static config. The S-2 `surface.quote-preview` + `surface.price-list-reference` widgets stay registered widgets; their `config` is derived from the live context each render (the S-2 `configFrom` pattern, now sourced from `useQuoteFocusOptional()`). An edit → context mutation → pin config change → the widget's existing 200ms debounce → `/quote-preview` re-fetch. **Re-pricing debounce is inherited from the S-2 widget — nothing new to build.**
- **Provider mount (a v1 simplification):** `SchedulingFocus`'s provider is lifted to `Focus.tsx` (`FocusDataProviderForFocusId`) *because its pin lives in the Canvas sibling subtree*. S-3a's `QuoteFocusWithAccessories` renders core + pins as **direct children in one subtree** — so for S-3b v1 the `QuoteFocusProvider` can live **inside `QuoteFocusWithAccessories`** (simpler, no `Focus.tsx` edit). It must lift to `Focus.tsx` only if a quote pin later moves to the Canvas rail.

### Re-host / park (STOP #1) — door stays open
`useQuoteFocusOptional()` returns `null` outside the provider → a parked quote widget (S-5, `WidgetChrome`, no provider) degrades to a read-only render, exactly as the parked `AncillaryPoolPin` fetches read-only endpoint data (`useAncillaryPool.ts:222-238`). **The provider is not mandatory for park** — it only *upgrades* to interactive. The one-way door only appears if the editable core uses the *throwing* hook or internal `useState`; the optional-context pattern avoids it. **Named for the build: the editable core + pins MUST consume via `useQuoteFocusOptional()` and render a graceful read-only/empty state when null** — S-3a already does this for the dropped-params case (`data-quote-focus-state="empty"`).

---

## DELIVERABLE 2 — Persistence / data-write Type B (James's call)

S-3a's draft is in-memory, dropped on reload (correct for the ephemeral handoff). S-3b is the *edit* surface — does an edit session survive reload? Three options, honest costs:

| Option | Survives reload? | Write footprint | New infra | Notes |
|---|---|---|---|---|
| **(a) In-memory only** (S-3a today) | No | **Zero** | **Zero** | The draft lives in `currentFocus.params` / the context; lost on reload. A bounded editing session is an unsaved document — you build it then save/discard. §5.14-consistent; the §5.6 return pill gives a 15s fast-return. |
| **(b) `focus_sessions`-adjacent JSONB** (no Document) | Yes | 1 row, no Quote | **1 migration + model field + new/extended endpoint + service + FE wiring** | `layout_state` is contractually widget geometry (`focus_session.py:54`) and is auto-seeded/overwritten by the tenant-default layout cascade — stashing draft content there races the resolver. Needs a *new* `draft_state` column + write endpoint. No quote number, not in the Quoting Hub. |
| **(c) Draft `Quote` Document on first edit** | Yes | `Quote` + `QuoteLine` rows | **Early-create wiring + net-new line-edit endpoint + relax/gate the missing-price guard** | Reuses `create_quote` + the existing `status="draft"` default (`quote.py:23`), BUT: `create_quote` *requires* a `unit_price` per line (`quote_service.py:188`), consumes a QTE-#### number immediately, surfaces in the Quoting Hub pipeline from first edit, and — critically — `update_quote` today edits only status/expiry/terms/notes, **not line items**, so add/remove/reprice `QuoteLine` is a net-new endpoint regardless. |

**Materialization belongs at SAVE regardless** (`quote_service.create_quote` → `POST /order-station/quotes`, or `sales_service.create_quote` → `POST /sales/quotes`). **Investigator's read: (a) in-memory for the edit session + materialize on explicit SAVE.** It's the smallest write footprint, keeps the S-1→S-3a "no data until commit" principle intact, and a bounded editing session losing an unsaved draft on reload is honest. (b)/(c) buy reload-resilience at real cost that v1 doesn't obviously need — revisit if "resume a half-built quote on another device" becomes a requirement. **This is a Type B — surfaced with costs, not decided.**

### §5.14 + does S-3b build SAVE?
The nameable decision: *"what goes in this quote and at what price — commit on send/save, or discard."* **S-3b MUST build SAVE** — an edit surface with no terminal commit isn't a bounded decision (it'd be "done looking around" → the anti-pattern). Save materializes via the existing `create_quote` (all lines must be resolved + priced — ambiguous/unresolved lines gate the save, a natural guard). Discard = backdrop dismiss (in-memory, no write). Send (email) is a later concern; SAVE (materialize) is the S-3b terminal action.

---

## DELIVERABLE 3 — Re-pricing reuse + the multi-line money-math cases to hand-prove

**Reuse confirmed, all four load-bearing checks green** (`quote_preview.py`):
- Arbitrary edited lines priced identically (the `DraftLine` has no provenance flag — "extraction" is a docstring, not a code path).
- Multi-line math correct across *different* products: per-line `get_effective_price`, `subtotal = Σ round_money(qty×unit)`, `total = subtotal + tax` on the multi-line `tax_lines` — matches `create_quote` exactly.
- Refusal line-source-agnostic (`resolve_product` per line, no origin param; edited "Bronze" → `ambiguous`).
- Drift guard holds: `render_preview_html("quote.standard")` — same `body_template` as the final PDF; one render call, no edit-mode renderer.

**Two additive backend changes (the sizing gap, NOT a new pricing path):**
1. **Structured per-line breakdown on the response (load-bearing).** Today the response is `html` + scalar summary + `ambiguous_products` — the per-line `line_contexts` (`{description, quantity, unit_price_formatted, line_total_formatted}`) is computed then discarded into the HTML. An editable UI cannot scrape HTML for rows — it needs, per line: **resolved `product_id`** (to key the row), name, numeric `unit_price`, `quantity`, `line_total`, and `status` (resolved / ambiguous+candidates / unresolved / call-office). Add a `lines: [...]` field to `QuotePreviewResult` + `QuotePreviewResponseBody`, sourced from the pricing loop. Additive; the pricing/render paths don't change.
2. **Optional per-line `unit_price` override (S-5a).** Today pricing is always catalog `get_effective_price`. A director re-pricing a line off-catalog needs a `unit_price` field on `_PreviewLineBody`/`DraftLine` + a guarded bypass (use the override when present). Small; v1-or-follow-on (Type B #3).

**Money-math cases to HAND-PROVE at build** (fresh — S-2 only proved single-line):
- **Two different products:** Monticello $1,405 ×2 ($2,810.00) + Continental $1,607 ×1 ($1,607.00) → **subtotal $4,417.00** (sum of rounded lines).
- **Add/remove/qty-edit:** add a 3rd line → subtotal grows by that line total; remove → shrinks; change qty 2→3 → line + subtotal update.
- **Ambiguous edited line:** type "Bronze" → `ambiguous`, NOT priced, excluded from subtotal (no fabricated total).
- **Per-line override (if S-5a v1):** override $1,200 on a $1,405 line ×2 → line $2,400.00 (override × qty), subtotal reflects it, not the catalog price.
- **Save parity:** the SAVE (`create_quote`) materializes byte-identical figures to the preview subtotal/total (the S-2 drift discipline, extended to the created row).

---

## DELIVERABLE 4 — Minimum editable-core UI + pointer-events conformance

### Minimum scope (a real editable quote — do NOT gold-plate)
- **Line rows:** product name · qty (editable number) · unit price (catalog, or editable if S-5a) · line total. Per-row remove.
- **Add line:** a product-search input reusing `resolve_product` + refusal — a typed ambiguous product surfaces "which: A, B?" (the S-2 honesty family), a typed unknown surfaces "couldn't find."
- **Live totals:** subtotal / tax ("calculated at order" until resolved) / total, from the re-priced preview.
- **Live document preview:** the S-2 `surface.quote-preview` widget as a pin, re-rendering the `quote.standard` document as edits land (the drift-safe result view).
- **Price-list reference pin:** the S-2 `surface.price-list-reference`.
- **SAVE** (→ `create_quote`) + discard (backdrop dismiss).
- **Follow-on (flag, NOT v1):** drag-to-reorder rows, per-line price override (if deferred), send-email.

### Registration + pointer-events conformance (STOP #2 cleared)
- **Registers exactly like `SchedulingKanbanCore`:** a `coreComponent` on the `registerFocus({ id:"quote-building", mode:"editCanvas", coreComponent })` entry — S-3a already registers `quote-building` with `mode:"editCanvas"` and a display `coreComponent`; S-3b **swaps that `coreComponent`** for the editable editor. The id, mode, escalation seam, and params contract stay unchanged.
- **Pointer-events: FOLLOWABLE.** Keep the core container at **default pointer-events** (plain `flex h-full w-full`, no `pointer-events-none` — exactly S-3a's `QuoteFocusWithAccessories.tsx:84`). Put the editable controls in the **core region** (inside the Popup), NOT as Canvas pins. Accessory rails stay `<aside>` siblings inside the wrapper (default-auto). The Canvas (`pointer-events:none`) sits on top and passes events through; keyboard works via the base-ui Dialog focus trap. `SchedulingKanbanCore` proves it end to end. **Named STOP would only occur if editable controls were placed in Canvas pins — don't.**

---

## DELIVERABLE 5 — Type B calls (persistence first) + LOC floor

**#1 — Persistence** (Deliverable 2): (a) in-memory + save-materializes vs (b) focus_sessions-adjacent vs (c) draft-Document-on-edit. **Read: (a).** Smallest footprint; preserves no-data-until-commit; reload-loss acceptable for a bounded session.

**#2 — SAVE scope:** S-3b builds SAVE (materialize via `create_quote`) — **yes**, §5.14 needs a terminal commit. Send-email is a later concern.

**#3 — Per-line price override:** v1 vs follow-on. **Read: v1 if the demo needs off-catalog re-pricing; else follow-on** — it's a small additive backend field but adds a guarded pricing branch to hand-prove.

**#4 — Drag-to-reorder rows:** **follow-on** — not minimum for a real editable quote; adds @dnd-kit gesture surface. (Reorder is §5.2 "edit canvas" flavor but polish.)

**#5 — Provider mount site:** in `QuoteFocusWithAccessories` (v1, simpler) vs lifted to `Focus.tsx`. **Read: in the wrapper for v1** (core + pins share one subtree); lift only if a pin moves to the Canvas rail.

### LOC floor (≈ 1,700)
| Work | LOC floor |
|---|---|
| Backend: structured per-line breakdown on `QuotePreviewResult`/response + route mapping | ~90 |
| Backend: SAVE adapter (draft → `create_quote` inputs) + endpoint reuse + all-lines-resolved gate; (+ per-line override if #3 v1) | ~140 |
| Backend tests: multi-line money-math hand-proof (Deliverable 3 cases) + ambiguous-edited-line + save-parity | ~280 |
| FE: `QuoteFocusContext` + provider (seed from params) + `useQuoteFocus`/`useQuoteFocusOptional` | ~150 |
| FE: `QuoteEditCanvasCore` — editable rows, add-line (resolver+refusal), remove, qty edit, live totals, SAVE | ~600 |
| FE: wire preview + price-list pins to the context (config from live draft); register the editable core swap | ~120 |
| FE vitest: context mutations, core rows add/remove/reprice, refusal-on-typed-ambiguous, pointer-events conformance, save wiring | ~320 |
| **Floor total** | **≈ 1,700** |

Roughly the S-3 findings' S-3b estimate (~1,500–2,500). Editable-editor UI is the bulk; the pricing path is reused untouched.

---

## STOP CHECK (all three dispatch STOPs, explicitly)

- **STOP if the only way to make the core editable is internal `useState` under `coreComponent`** → **CLEARED.** The `QuoteFocusContext` externalized-store pattern (copied from `SchedulingFocusContext`) makes the draft mutable *and* re-hostable; the optional hook keeps the S-5 park door open. Internal `useState` is the wrong build, not the only build.
- **STOP if the editable core can't follow the pointer-events tier contract** → **CLEARED.** The contract doesn't apply to the core — the core region is default-`auto` beneath the `pointer-events:none` Canvas sibling; the core mounts once for all tiers and never collapses. `SchedulingKanbanCore` proves an interactive core works. The only risk (controls in Canvas pins) is avoidable — keep controls in the core region.
- **STOP if re-pricing an edited quote needs a second renderer or a non-S-2 pricing path** → **CLEARED.** The shipped `/quote-preview` prices arbitrary edited multi-line sets through the same `quote.standard` render (drift guard holds) with line-source-agnostic refusal. The only backend work is two additive response-side fields (structured per-line data + optional override) — no new renderer, no new pricing path.

---

— Read-only confirmed: no code, no schema, no test, no doc besides this file changed; no Type B decided; nothing pushed. This file is the sole write. —
