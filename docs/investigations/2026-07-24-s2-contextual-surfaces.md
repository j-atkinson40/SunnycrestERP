# S-2 Contextual Surfaces (§4.3) — Phase 1 Investigation

2026-07-24 · READ-ONLY · repo @ b66656f7 · no code changed, no push
Governing canon: PLATFORM_ARCHITECTURE §4.3 (floating contextual surfaces), §4.4 (six anti-drift rules), §4.8.2 (pause sensor) · PLATFORM_INTERACTION_MODEL (tablets, composition-reuse) · DESIGN_LANGUAGE (level-3 elevation, brass border, ease-settle) · PLATFORM_QUALITY_BAR · S-1 contract (docs/investigations/2026-07-23-s1-entity-portal.md)

Slice under investigation: the **quote preview** (renders in-flight NL extraction as the real quote artifact, floating beside the palette) + the **price-list reference** surface (summoned because the user is quoting). Deferred S-2 sub-slices: calendar-because-you-mentioned-a-date, answer-backing charts.

---

## Headline

S-2's flagship slice is buildable, and its two scariest questions resolve in our favor:

1. **The render path does NOT force a second, drift-prone renderer.** The documents pipeline already ships an HTML-only, no-persisted-Document, missing-variable-tolerant entry point (`render_preview_html` → `_render_jinja`). A live preview renders the *identical* `quote.standard` Jinja that the final PDF renders, through the *same* Jinja env, differing only by whether the WeasyPrint print-step runs. **Drift is impossible by construction.** No STOP.

2. **Quote pricing IS deterministic** given (product, order-line composition) — the charged unit price is a single scalar with a binary conditional-pricing branch, no random fallback. **But the dispatch's premise is wrong in a way a naive build would trip on: customer identity plays NO role in tier selection, and there are two independent price sources that legitimately disagree.** The preview MUST reuse the order resolver (`order_pricing_service.get_effective_price`), not the command-bar tiered display. That's a build-discipline constraint, not a non-determinism STOP. No STOP — with one honesty requirement (call-office + unresolved-tax render honestly).

The three things that genuinely need building are the *connective tissue*, exactly as canon predicted — but with two corrections to the optimistic framings in prior docs:

- **Correction A (fragmentation):** quote runs through the **workflow overlay** (`NaturalLanguageOverlay` + `/core/command-bar/extract`), not the entity-centric NL path. Attaching a preview does **NOT** require migrating quote off the overlay (no resequence STOP) — it requires an additive **state-lift** (a callback/context so a sibling can read the in-flight extraction without a duplicate `/extract` call).
- **Correction B (host):** the S-1 doc's "S-2 raises the cap to 2–3 and adds non-entity surfaces" undersold the work. S-1 built `CommandBarSurfaceHost` **coupled to `EntityPortalCard` by name** and keyed to `PortalCandidate{entityType, entityId}`. The widget *contract* generalizes to param-keyed surfaces (no change); the *host* needs a bounded, additive generalization (surface-descriptor list + registry dispatch) plus a new action→surfaces summon map that exists nowhere today. Additive, doesn't touch the contract, doesn't break S-1's entity cards.

**No resequencing STOP required.** All three STOP conditions checked and cleared (§ STOP CHECK below).

---

## DELIVERABLE 1 — Build-vs-spec table (per S-2 piece)

| S-2 piece | Shipped substrate | Gap for S-2 | Verdict |
|---|---|---|---|
| **Extraction** (feeds the preview) | `/core/command-bar/extract` + `NaturalLanguageOverlay` own quote NL end-to-end; `entryIntent:"quote"`, quote labels, `/quoting/{id}` routing all built. 300ms debounce + AbortController in `useNLExtraction` (entity path) and a private debounce in the overlay. | Extraction state is trapped in the overlay's local `useState` — no `onExtraction`/context. A sibling preview can't subscribe without re-POSTing. **Needs a state-lift** (callback prop or shared context). | ⚠️ Built but not subscribable — additive lift |
| **Render** (the artifact) | `render_preview_html(template_key, context, company_id)` → HTML string, no Document, no WeasyPrint (`document_renderer.py:525`). Default Jinja `Undefined` → missing fields render blank, no raise (`:122`, no `undefined=` arg). Seeded `quote.standard` monolithic Jinja template with `{% if %}`-guarded optional fields (`_template_seeds.py:1303-1382`). PDF (`_html_to_pdf`) fully separable. | Only a thin adapter: shape the in-flight extraction → a context dict matching `quote.standard`'s variable names (`lines[]` with `unit_price_formatted`/`line_total_formatted`, `total_formatted`, `customer_name`, `expiry_date`). | ✅ Built — real pipeline, no second renderer |
| **Pricing** (money math) | `order_pricing_service.get_effective_price(product, order_lines, db)` (the ONE resolver both order + quote callers use), `money.round_money`/`line_total` (ROUND_HALF_EVEN), `tax_service.resolve_line_tax` (jurisdiction engine). Deterministic given (product, line composition). | Preview must call the **order resolver**, not the command-bar tiered display (`price_list_items.standard_price` — a different, independently-maintained column). Product-name→Product resolution reuses the NL entity resolver. | ✅ Built + deterministic — with source-discipline constraint |
| **Host** (where it floats) | `CommandBarSurfaceHost` (S-1) enforces §4.3/§4.4 discipline structurally: max-2 slot model, ephemeral (clears on highlight change), null-return when empty, no drag/resize, dies-with-palette. Widget contract `WidgetRendererProps` already carries `surface:"command_bar"`, generic `config`, optional `onPivot`. `EntityPortalCard` is host-agnostic + re-hostable into a Focus (S-3 seam intact). | Host renders `EntityPortalCard` by name (never `getWidgetRenderer`); state vocabulary is entity-id-only; summon is `entity:{type}:{uuid}`-result-only. **Needs additive host generalization** (surface-descriptor list + registry dispatch) + a param/action hydration path (backend endpoint hardcodes `{entity_type}/{entity_id}`). | ⚠️ Contract ready; host + summon need bounded additive extension |
| **Trigger** (when it appears) | Pause sensor (§4.8.2) is **S-4, not built.** Existing proxy: the overlay's extract debounce (post-extraction settle) is a serviceable "the user paused and we have something to show" signal. | Use the debounce-settled extraction as the v1 trigger; keep the trigger behind a seam so S-4's real pause sensor swaps in without touching the surfaces. | ✅ Proxy available — don't hard-couple to it |

---

## DELIVERABLE 2 — The render-path decision (load-bearing, with latency evidence)

**Decision: ONE renderer. The live preview renders through the real document pipeline.**

Evidence trail (all verified against source at b66656f7):

- **Entry point exists and needs nothing new.** `render_preview_html(db, *, template_key, context, company_id)` returns an HTML *string* with "NO persistence, NO delivery, NO PDF stage" (`document_renderer.py:525-537`). It delegates to `_render_non_pdf` → `_render_jinja(body_template, context)` (`:145-167`) — a raw Jinja string + context dict, no DB Document row.
- **Partial data is safe.** The Jinja `Environment` is built with `autoescape=select_autoescape(["html","xml"])` and **no `undefined=` argument** (`document_renderer.py:122`, verified). Default `Undefined` ⇒ a missing top-level variable renders as empty string, `{% if missing %}` is falsy — no raise. `StrictUndefined` is used *only* in the Intelligence prompt path, never in documents. And `quote.standard` additionally `{% if %}`-guards every optional field, so a preview with no total / no customer / no lines degrades to headers + "No line items." rather than erroring.
- **Preview and final PDF cannot drift.** Both render the same `quote.standard` `body_template` through the same env; the only difference is the PDF branch runs `_html_to_pdf` (`document_renderer.py:170-184`, "the ONLY place allowed to instantiate weasyprint.HTML"). Preview skips it; "Generate PDF" runs it on the identical HTML. Zero-drift is a property of the architecture, not of test discipline.
- **Latency: comfortably inside a 300ms debounce.** The composed Jinja is **cached, not recomposed per render** — `block_service._recompose_and_persist` writes composed Jinja back to `document_template_versions.body_template` at *authoring* time; render reads `body_template` directly (`template_loader.py:197`) and never invokes the block composer. And `quote.standard` is hand-authored monolithic Jinja — the composer isn't in the quote path at all. Hot path = one indexed DB read for the version row + `env.from_string(body_template)` (Jinja compile) + `tpl.render(**context)` = pure string assembly, sub-ms-to-low-ms for a one-page quote. To shave even the DB read, load `quote.standard`'s `body_template` once and call `_render_jinja` per keystroke — zero DB on the hot path.

**Why no second renderer is even tempting:** the thing people reach a lightweight second renderer *for* (skip PDF cost) is already the default HTML branch here. WeasyPrint is the separable print step, not the renderer. There is no latency motive to fork.

**Build note:** the adapter's whole job on the render side is producing a context dict whose keys match `quote.standard`'s variables (`lines[]` of `{description, quantity, unit_price_formatted, line_total_formatted}`, plus `subtotal`/`tax`/`total_formatted`, `customer_name`, `expiry_date`). Those `*_formatted` fields are pre-rendered currency strings — the pricing math (Deliverable 3) produces them.

---

## DELIVERABLE 3 — The tier-resolution answer (correctness-critical)

**Answer: quote pricing is DETERMINISTIC. There is no non-determinism STOP. But the dispatch's mental model — "how is the tier chosen for Hopkins?" — has no answer, because customer identity does not select a price tier.** Two corrections a build must respect, both verified against source:

### Correction 1 — the customer never selects a price tier
The tri-tier columns `standard_price` / `contractor_price` / `homeowner_price` live **only** on `price_list_items` — the *publication* artifact rendered into PDF price lists and returned by the command-bar "what's our price" answer. They are **never auto-selected by customer type** at order/quote time. Grep-confirmed empty across `order_pricing_service.py`, `quote_service.py`, `sales_service.py`, `order_station.py`, `sales.py`. "Hopkins" (a funeral home) does not map to a tier. There is no customer→tier mapping to be non-deterministic about — the ambiguity the dispatch feared simply doesn't exist in this direction.

### Correction 2 — two price sources exist and can legitimately disagree
- **Order/quote charge** (the truth): `order_pricing_service.get_effective_price(product, order_lines, db)` → `product.price`, or `product.price_without_our_product` when `has_conditional_pricing` and no vault on order, or `None` when `is_call_office` (`order_pricing_service.py:47-63`, verified).
- **Command-bar price display**: `price_list_items.standard_price` from the active `PriceListVersion` (`command_bar_data_search.py`) — a *different column*, maintained independently, and it does **not** multiply by quantity.

**A preview wired to the command-bar tiered lookup would show a number the order does not charge.** The preview MUST reuse `get_effective_price`.

### What determinism looks like for "3 Monticellos for Hopkins"
`monticello` ∈ `VAULT_PRODUCT_LINES` (`order_pricing_service.py:15`, verified). A vault is a *qualifier*, not a conditionally-priced item — it has `has_conditional_pricing = False`, so `get_effective_price` returns the single scalar `product.price`. Line total = `round_money(3 × product.price)` (ROUND_HALF_EVEN, per-line; `money.py:23-28`, verified). Deterministic, reproducible, standable-behind.

### The exact money math the preview must mirror (hand-provable inputs)
| Input | Source (verified) |
|---|---|
| product → unit price | `get_effective_price` → `product.price` / `product.price_without_our_product` / `None` (call-office). NOT `price_list_items.*`, NOT `product_price_tiers` (quantity-break tiers exist but are never applied at order time). |
| tier-selection input | order-line composition only (`has_vault_on_order`). **Customer: not an input to price.** |
| quantity | caller-supplied whole number |
| line_total | `round_money(qty × unit_price)`, ROUND_HALF_EVEN, per line |
| subtotal | Σ per-line-rounded totals |
| tax rate | override → product-exempt → job cert → customer blanket cert → jurisdiction engine (`cemetery.county` > customer-zip→county) → unresolved. `customer.tax_exempt` flag *without* a valid certificate ⇒ still TAXABLE, gap surfaced. |
| tax_amount | `round_money(taxable_subtotal × rate/100)` |
| total | `subtotal + tax_amount` (not re-rounded; both already at the cent) |
| discounts | none automatic in the standard product path; conditional with-vault pricing is the only automatic price movement; `quote_service` adds a `delivery_charge` line. |

### The two honesty requirements (not STOPs — design constraints)
1. **`is_call_office` products** return `None` — there is no reproducible price. The preview must render "price on request" for those lines, never a fabricated number.
2. **Tax is frequently unresolved mid-type** — a live preview usually has no cemetery and maybe no resolved customer, so the jurisdiction engine can't fire. The honest preview shows **subtotal confidently and tax as "calculated at order"** until jurisdiction resolves (matches §4.8 "show what you know," and `resolve_line_tax` already returns a clean `resolved=False` / `0.00` state to key off). Floating a confident grand-total before tax resolves would be a QUALITY_BAR lie.

---

## DELIVERABLE 4 — Type B calls for James (fragmentation + render-path + pricing first)

**#1 — Extraction attachment: state-lift, NOT migration (the fragmentation call).**
Quote uses the workflow overlay (`NaturalLanguageOverlay` + `/core/command-bar/extract`), not the entity-centric NL path (`sales_order`/`quote` are deliberately absent from `entity_registry._ENTITY_CONFIGS`; the docstring says so). **This is NOT the migration STOP** — the preview attaches to the overlay path as-is. The choice is *how the sibling reads the in-flight extraction*:
- (a) **Add an `onExtraction(fields)` / `onFields` callback prop to `NaturalLanguageOverlay`** — smallest change, the overlay stays the owner, the host lifts the fields to feed the preview. ~1 prop + a `useEffect`.
- (b) **Hoist extraction into a shared context** both overlay and preview subscribe to — cleaner for S-3/S-4 but touches the overlay's internals more.
- **Investigator's read: (a) for S-2**, revisit (b) if S-4's pause sensor wants the stream too. Either way the preview consumes the overlay's `FieldMap` shape via `/core/command-bar/extract` — NOT the entity-path `FieldExtraction[]` shape. Naming this now prevents wiring the preview to the wrong extract endpoint.

**#2 — Render path: one renderer, server-side HTML (the load-bearing call).**
(a) `render_preview_html` server-side, endpoint returns HTML string the widget mounts, vs (b) return a priced context dict + a frontend renderer. **Read: (a)** — the preview MUST be the real Jinja template (that's the whole no-drift guarantee); a frontend renderer would be exactly the second, drift-prone renderer the STOP forbids. The widget self-fetches HTML and mounts it in a sandboxed container (per the widget self-fetch rule). One new endpoint, its own BLOCKING latency gate (mirror the peek/portal gate; suggest p50<150/p99<400 given pricing + Jinja assembly).

**#3 — Pricing source: reuse the order resolver, render call-office/unresolved-tax honestly.**
(a) `order_pricing_service.get_effective_price` + `money` + `tax_service.resolve_line_tax` (the exact order-creation math) vs (b) the command-bar tiered display. **Read: (a), unambiguously** — (b) shows a number the order doesn't charge. The preview-pricing function is a thin reuse of shipped services; its correctness is hand-provable against Deliverable 3's input table. Ship a parity test: *preview total == the total the order-creation path would compute for the same lines.*

**#4 — Host generalization (correction to the S-1 "trivial cap raise" framing).**
The host is coupled to `EntityPortalCard` + entity-id candidates. To float a param-keyed preview + reference pair:
(a) **Generalize `CommandBarSurfaceHost`** to accept a `surfaces: SurfaceDescriptor[]` (entity-card OR param-widget), dispatch each via `getWidgetRenderer` instead of the hardcoded card, raise the cap to 2–3 — discipline stays in the host (§4.4 enforced structurally for whatever it renders). vs (b) a parallel second host for non-entity surfaces. **Read: (a)** — one Act host is the §4.3 canon ("a *family* with the command bar"); a second host fragments the discipline. Bounded, additive, doesn't touch `WidgetRendererProps`, doesn't break S-1's entity cards. This is also where S-5's park affordance later attaches, so the host must be the single Act host regardless.

**#5 — The summon map (the S-4 seam).**
"A quote-in-flight shows a quote preview + price-list reference" is declared **nowhere today** — no `contextual_surfaces` slot exists in the action registry, and the backend portal endpoint hardcodes `{entity_type}/{entity_id}`. Least-invasive home:
(a) a small **`CONTEXTUAL_SURFACES` map** keyed by in-flight interpretation (`intent:"quote"` → `["quote_preview","price_list_reference"]`), consulted by the host, vs (b) extend `entity_registry`/action registry with a per-action `contextual_surfaces` field. **Read: (a) a new small map for S-2** — quote's summon key is an *interpretation* (workflow-overlay intent), not an entity id or a registered action, so it doesn't fit either existing registry cleanly. Keep the map tiny and behind the same seam as the trigger (#6) so S-4 can repoint it at the real interpretation-chip/pause signal.

**#6 — Trigger timing (don't hard-couple to a mechanism S-4 replaces).**
§4.8.2's pause sensor (500–700ms adaptive inter-keystroke) is S-4, unbuilt. (a) Use the overlay's post-extraction debounce settle as the v1 "pause" proxy vs (b) pull minimal pause detection forward into S-2. **Read: (a)** — the extract debounce already fires after the user stops typing and yields something to show; wrapping the trigger in a `useContextualSurfaceTrigger` seam lets S-4 swap the real pause sensor in with zero surface changes. Do not build pause detection in S-2; do isolate the trigger call so S-4 isn't a rewrite.

---

## DELIVERABLE 5 — LOC floor (flagship slice only: preview + price-list reference)

Floor, not ceiling. Excludes: calendar/chart sub-slices, S-3 Focus re-host, S-4 pause sensor, S-5 park machinery.

| Work | LOC floor |
|---|---|
| Backend preview-pricing + render endpoint: product resolution (reuse NL resolver) → `get_effective_price` per line → `money.line_total` → `resolve_line_tax` → context dict → `render_preview_html`; call-office + unresolved-tax honest states | ~220 |
| Backend price-list-reference hydration: tiered rows for mentioned products (reuse `command_bar_data_search`) + optional recent-order pattern for resolved customer | ~120 |
| BLOCKING latency gate + pricing-parity test (preview total == order total) + partial-data render tests | ~230 |
| `QuotePreviewWidget` (WidgetRendererProps, `config:{draft_params}`, self-fetch HTML, Brief variant, sandboxed mount) | ~180 |
| `PriceListReferenceWidget` (WidgetRendererProps, `config:{products, customer_id?}`, self-fetch, Brief variant) | ~150 |
| Host generalization: `SurfaceDescriptor[]` + `getWidgetRenderer` dispatch + cap 2–3 (discipline preserved) | ~150 |
| Extraction state-lift (`onExtraction` on `NaturalLanguageOverlay`) + summon `CONTEXTUAL_SURFACES` map + trigger seam + CommandBar wiring | ~200 |
| Two-layer widget registrations (runtime + visual-editor metadata) for both widgets | ~70 |
| vitest: host discipline (max-2–3, ephemeral, no-drag), both widgets, trigger seam | ~230 |
| **Floor total** | **≈ 1,550** |

Roughly S-1-sized (~1,850), lighter because the render + pricing + host substrate is reused rather than built.

---

## STOP CHECK (all three dispatch STOPs, explicitly)

- **STOP if the preview can only render via a second renderer that provably drifts** → **CLEARED.** One renderer; preview and final PDF are the same `quote.standard` Jinja through the same env; WeasyPrint is the only difference and it's a separable print step. Drift is architecturally impossible.
- **STOP if quote tier resolution is non-deterministic** → **CLEARED.** Unit price is a single deterministic scalar (binary conditional branch, no random fallback); customer identity isn't even an input to price. The only non-reproducible case is `is_call_office` ("price on request"), which the preview renders honestly rather than guessing. Correctness constraint (not a STOP): reuse `get_effective_price`, not the command-bar tiered display; show tax as "calculated at order" until jurisdiction resolves.
- **STOP if attaching the preview requires migrating quote off the workflow overlay** → **CLEARED.** Quote *stays* on the workflow overlay; attachment is an additive state-lift (a callback prop), not a migration. No resequence.

Two honest corrections to prior optimistic framings, neither a STOP: (A) quote is on the workflow overlay, not the entity path — attach via state-lift; (B) the S-1 host is entity-coupled — S-2 must additively generalize it (surface-descriptor list + registry dispatch + summon map), which the "raise the cap to 2–3" note undersold.

---

— Read-only confirmed: no code, no schema, no test, no doc besides this file changed; no Type B decided; nothing pushed. This file is the sole write. —

---

## ADDENDUM (ratified) — CONTEXTUAL_SURFACES + trigger seam shapes

Ratified after Phase 1, folded into the Phase 2 build. The interpretation
signal S-2 keys on **exists at extraction time today** and is **not** the §4.8
interpretation chip (which is S-4): it is `entry_intent: "order" | "quote"`,
computed by the backend `detect_entry_intent(input_text)` regex
(`command_bar_extract_service.py:64`, on the `/core/command-bar/extract`
response `:560`) and surfaced into `NaturalLanguageOverlay` state
(`:214`). Because quote is click-to-activate, the intent is already committed by
the time surfaces would appear — exactly what §4.3 attaches to. So S-2 is
decoupled from S-4 on keying: **the map keys on the intent string; who produces
the string lives behind the seam.**

### CONTEXTUAL_SURFACES (keyed on committed intent)

```ts
interface ContextualSurfaceDecl {
  kind: string
  widgetId: string // registry id → host dispatches via getWidgetRenderer
  // PURE derivation of widget config from the lifted extraction.
  // Return null to SUPPRESS this surface for the current fields.
  configFrom: (ctx: ExtractionContext) => Record<string, unknown> | null
}

const CONTEXTUAL_SURFACES: Record<string, ContextualSurfaceDecl[]> = {
  quote: [
    { kind: "quote_preview", widgetId: "surface.quote-preview",
      // materializes once there's a customer or a line; nothing flashes on empty
      configFrom: (ctx) => ctx.customer || ctx.lines.length > 0
        ? { customer: ctx.customer, lines: ctx.lines } : null },
    { kind: "price_list_reference", widgetId: "surface.price-list-reference",
      // suppressed until a product resolves — no empty shell
      configFrom: (ctx) => ctx.lines.length > 0
        ? { products: ctx.lines.map((l) => l.productRef), customerId: ctx.customer?.id ?? null }
        : null },
  ],
}
```

`ExtractionContext = { entryIntent, customer: {id?,name}|null, lines: {productRef,productId?,quantity}[], rawInput }` — the normalized read of the overlay's `FieldMap` (`ask_customer`/`ask_product`/`ask_quantity`), lifted via `onExtraction`.

### useContextualSurfaceTrigger (carries rhythm, not just "fire")

```ts
interface SurfaceTriggerSignal {
  reason: "extraction_settled" | "pause" | "manual" // v1 settled; S-4 pause
  msSinceLastKeystroke: number | null // best-effort now; rich under S-4
  cursorMoved: boolean                // §4.8.2 softer pause signal
  inputText: string
}
interface ContextualSurfaceTrigger {
  active: boolean                     // host reads: show surfaces now?
  signal: SurfaceTriggerSignal | null
  dismiss: () => void                 // resume-typing / action-complete (S-4)
}
function useContextualSurfaceTrigger(opts: {
  context: ExtractionContext | null
  minVisibleMs?: number               // §4.8.2 ~1s min-visibility, owned by the seam
}): ContextualSurfaceTrigger
```

v1 emits `reason:"extraction_settled"` with best-effort rhythm; S-4's pause
sensor swaps the **implementation** to emit `reason:"pause"` with a real
adaptive threshold + rhythm through the **identical** return shape — the host
and surfaces never change.

— Phase 2 built exactly these shapes; see STATE.md 2026-07-24. —
