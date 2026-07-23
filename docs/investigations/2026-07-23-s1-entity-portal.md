# S-1 Entity Portal (§4.2) — Phase 1 Investigation
2026-07-23 · READ-ONLY · repo @ 90a4feaf · no code changed, no push
Governing canon: DECISIONS 2026-07-23 (park ratification constraint set) · PLATFORM_ARCHITECTURE §4.1–4.4, §4.9 · PLATFORM_INTERACTION_MODEL (tablets, composition-reuse discipline) · Phase-1 arc findings (docs/investigations/2026-07-22-command-bar-spatial-findings.md)

## Headline
S-1 is buildable now, over the entity-model fragmentation, without the CRM unification — because the platform has already built S-1's hard parts twice: **peek builders** are the hydration adapter layer (6 entity types, tenant-scoped, own latency gate) and the **Widget Library contract** (`WidgetRendererProps`: `widgetId / variant_id / surface / config`) is the summonable-surface seam that makes an S-1 Act-shaped card park-able in S-5 without rewrite. The portal is an assembly: new `surface: "command_bar"` host + entity-card widgets at Brief variant + an enriched peek-style hydration endpoint. **No resequencing STOP required.**

---

## JOB 1 — What the resolver gives us

**Per-entity fields returned today: id, entity_type, primary_label (SQL expr), secondary label, url (template), score.** That's it — the UNION ALL selects `id / primary_label / secondary / sim*recency AS score` per `EntityConfig` (resolver.py:82–178, 239–270). **Not enough to populate a portal card** — enough to *recognize* the entity and render the existing result tile.

**`ResultItem` contract** (retrieval.py:65+): `id, type, primary_label, secondary_context, icon, url?, entity_type?, action_id?` — docstring: "enough info for the frontend to render + activate the tile **without a second round-trip**." Two paths:
- **Bump the shape** (embed portal payloads in QueryResponse): coordinated schema change across retrieval.py + adapter + every caller; heavier query work per keystroke (portal data computed for results the user never opens); direct pressure on the query latency gate. Cost: high, and it taxes every query for the rare portal-open.
- **Separate call** (query stays cheap; portal hydrates on selection): zero contract change, zero adapter churn; one extra round-trip on entity-select only. Cost: one ~10–100ms fetch at the moment of intent — exactly the peek pattern that already ships.

**Latency gate** (test_command_bar_latency.py): BLOCKING; measures `/command-bar/query` only — 50 sequential mixed-shape queries against a ~20-row tenant; p50<100/p99<300. Inline assembly of orders + financial standing (multi-table joins + AR aggregation per fuzzy match) inside that endpoint would multiply per-query work and put the gate at genuine risk; and the gate would then mis-measure (portal assembly cost hidden inside query samples). **This forces the hydration Type B call (#2 below).** Precedent: the Peek arc already made this exact call — `GET /api/v1/peek/{entity_type}/{entity_id}` with its own BLOCKING gate (p50<100/p99<300; measured 3.7/7.4ms dev).

## JOB 2 — The entity-model problem

**The 4 parallel contact models** (docs/DEBT.md §"CRM parallel contact models unification"):
| Model | Key | Used by |
|---|---|---|
| `Contact` (CRM canonical-ish) | `master_company_id → CompanyEntity` | Vault CRM (`/vault/crm/*`), command-bar resolver, peek `contact` builder, NL-creation resolver |
| `CustomerContact` | `customer_id` | AR/customers surfaces |
| `VendorContact` | `vendor_id` | AP/purchasing surfaces |
| `FHCaseContact` | `fh_case_id` (+ portal-invite fields no other model has) | FH cases, family portal |
Same physical person can be four rows. Unification = Vault audit Option B: CompanyEntity→VaultItem + Contact canonical + migrate three tables + all call sites — **audit-estimated 6–8 weeks**, threshold "after V-1h + one stable release."

**Adapter-over-fragmentation vs unify-first:**
- **Adapter (build over it)** — *proven feasible in-repo*: peek's `PEEK_BUILDERS` and triage's `_RELATED_ENTITY_BUILDERS` are exactly this shape (per-entity ~30-line builders querying whatever models that entity needs, dispatched by entity_type). The portal's "customer card" builder joins CompanyEntity + Contact + SalesOrder + Invoice in one builder function. Cost: the builder embeds fragmentation knowledge (a "customer's contacts" means Contact-by-master_company_id ∪ CustomerContact-by-customer_id if we want completeness — or, honest v1: Contact only, matching what Vault CRM shows); when Option B lands, builder internals swap with zero surface change. ~400 LOC, S-1-sized.
- **Unify first** — clean single contact model under the card, no dual-source logic ever written. Cost: **6–8 weeks before S-1 starts**, blowing up the ratified S-1→S-5 sequence and the park pull-forward rationale; and the unification was explicitly deferred with a threshold that hasn't been re-evaluated.
- Honest middle truth: the adapter does NOT paint us into a corner — the portal surface contract (Job 4) is entity-type-keyed and model-agnostic; unification is an internals swap later.

**Rich portal today vs near-empty card** (resolver's 7 types × available substrate):
| Entity | Portal richness today | Substrate |
|---|---|---|
| contact / company (customer) | **Rich** — the §4.2 headline card | peek contact builder (contact + CompanyEntity), sales_orders, invoices/AR aging, RingCentral call logs |
| fh_case | **Rich** | peek builder + case tables + events |
| sales_order | **Rich** | peek builder + lines + delivery + invoice links |
| invoice | **Rich** | peek builder + payments + customer |
| task | Moderate | peek builder + provenance |
| product | Moderate (new builder needed) | inventory, price_list_items, recent order lines |
| document | Thin (title/type/date + open) — acceptable, honest card | D-1 presigned preview |

## JOB 3 — Vault views + permissions

**Reuse exists — the Widget Library, not bespoke components.** Three registries already in play: the in-memory visual-editor metadata registry (authoring), the **canvas widget-renderer registry** (`registerWidgetRenderer(type, component)` — runtime dispatch), and the Spaces/Pulse pin surfaces consuming the same components at variants. INTERACTION_MODEL states the pattern outright: *"a customer peek renders the Customer Card Widget at Brief variant inside the peek panel chrome … three summon mechanisms, one materialization unit."* Portal cards should be **entity-card widgets** registered in both registry layers (CLAUDE.md two-layer rule), rendered at **Brief** variant in the portal host. What reuse requires: (a) authoring the entity-card widget components (they don't exist yet — peek renderers are close cousins but peek-chrome-coupled), (b) adding a `surface` value for the command-bar host, (c) registering in both layers.

**Permission gating today:** command-bar registry gates entries via permission/module/extension filters "mirroring VaultServiceDescriptor semantics" (same pipeline the Vault hub uses — e.g. `customers.view`, `admin`); resolver/peek enforce **tenant isolation** (company_id filters) but peek builders do **NOT per-section permission-gate** today. §4.2's "financial standing (if user has permission)" therefore needs a per-card-section gate at the hydration-builder level — `user_has_permission(user, db, "…")` per section, omitted-section-quietly semantics (the Phase-8a Settings-space precedent: live permission check at assembly time). This is additive to the builder pattern, not a new mechanism.

## JOB 4 — THE SUMMONABLE-SURFACE CONTRACT (load-bearing output)

**The seam already exists: `WidgetRendererProps`.** Shipped contract (widget-renderers.ts):
```ts
{ widgetId: string; variant_id?: VariantId /* Glance|Brief|Detail|Deep */;
  surface?: "focus_canvas" | "focus_stack" | "spaces_pin"; config?: … }
```
plus the registry rules: identity-only props, **widgets self-fetch data** (feature-owned context/fetch — registry never pipes data), one component per widget with an internal variant switch.

**Proposal — an entity-portal card IS a widget from day one:**
1. **Component**: `EntityCardWidget` per entity type (or one dispatcher + per-type renderers), registered via `registerWidgetRenderer("entity-card.<type>", …)` + visual-editor metadata registration. Internal variant switch; **Brief** is the portal default (canon: "default command bar peek variant").
2. **Config**: `{ entity_type, entity_id }` rides the shipped `config` prop (the W-3b plumbing exists — saved_view widget precedent requires config to render, same shape).
3. **Data**: self-fetched from the portal hydration endpoint (Job 1's second call). No data through hosts — this is what makes the card host-agnostic.
4. **Surface**: add `"command_bar"` to the `surface` union (additive optional prop — non-breaking; widgets that ignore it render canonical shape, per the migration-window rule already in the file).
5. **Hosts own everything spatial.** S-1's Act host renders cards floating near the palette: **no drag, no resize, no persistence, max 2–3** (§4.3 verbatim) — those constraints live in the HOST, not the card. S-3 hands the same component to a Focus as anchored core (host = Focus core slot). S-5 parks it by wrapping the SAME component in **WidgetChrome** (drag/resize/@dnd-kit — the ONE drag system) with session-scoped `{anchor, offsetX, offsetY, width, height}` state and the three-tier cascade — all of which already exists and already consumes this exact props contract.
6. **Pivots/actions**: card-level affordances (call/note/pivot chips) are part of the card component; pivot-click emits an `onPivot(entity_type, entity_id)` callback the HOST interprets (Act host: replace/add card; Focus host: open peek or re-anchor). One optional callback prop addition — name it in S-1 so S-2..S-5 never touch the contract.

**Why this is the no-rework seam**: the Act-discipline (ephemeral, non-draggable) and the park behavior (draggable, session-persistent) are *host* properties. The card never knows which host it's in beyond the `surface` discriminator it may use for density. S-5 requires zero card changes — it builds the parking host.

## JOB 5 — Where it hangs + what's in the way

- **CommandBar.tsx render pipeline (honest)**: one modal, one return; `NLCreationMode` swaps IN PLACE of the results list when create-with-content is detected (line ~1040); otherwise ranked `results.slice(0, 7)` tile list (line ~1214). **Mode-swap precedent exists** (NL creation). Portal attachment is a Type B call (#4): (a) third in-palette mode swap (entity-select → portal replaces list — consistent with NL precedent, but §4.3 says surfaces "float near the command bar (below or beside)"), or (b) adjacent floating panel(s) beside the palette with the list retained — closer to canon's picture and to what S-2 needs anyway. Either way S-1 should extract the future host as its own component (`CommandBarSurfaceHost`) rather than growing the 1,392-LOC file.
- **Naming drift confirmed**: frontend registry is `src/services/actions/registry.ts` (+ manufacturing/funeral_home/types); CLAUDE.md says `actionRegistry.ts`. Fix in passing during S-1 docs touch; not fixed now.
- **RingCentral**: a REAL integration — inbound webhook telephony (`/webhook`, ringing/answered/ended events), SSE stream (`/events`), call logs, transcription + after-call intelligence pipeline, per-tenant resolution. **Outbound click-to-call (RingOut) is NOT built** — no make-call endpoint exists. Click-to-call on the contact card = small new backend endpoint on a live integration + graceful `tel:` fallback when RC unconfigured (Type B #5 scope call).
- **Already partially built §4.2 elements**: peek renderers (CasePeek/InvoicePeek/SalesOrderPeek/TaskPeek/ContactPeek + `_shared` label/value + StatusBadge) are proto-card UI; peek/triage builders are proto-hydration; recents/affinity ranking already personalizes entity surfacing; disambiguation rows exist as the plain result list (keyboard-numbered §4.6 treatment not built).

## DELIVERABLE 1 — Build-vs-spec table (§4.2)

| §4.2 element | Status |
|---|---|
| Type a name → entity recognized | ✅ Built (resolver, 7 types, pg_trgm + recency + boosts) |
| Entity card composition per type | ❌ Not built (closest: peek renderers, peek-chrome-coupled, Brief-ish) |
| Contact card | ❌ (ContactPeek is the seed) |
| Click-to-call | ❌ outbound; ✅ RC integration substrate (inbound/SSE/logs) |
| Text / email / note affordances | ❌ (delivery abstraction + notes tables exist as substrate) |
| Recent/open orders panel | ❌ (data trivially available; peek sales_order builder as seed) |
| Financial standing (permission-gated) | ❌ (AR data exists; per-section permission gate is NEW at builder level) |
| Relational pivots (navigate-through-entities) | ❌ (peek's related_entities panel + navigate_url are seeds; in-context pivot = new) |
| Permission-respecting via Vault views | ⚠️ Mechanism exists (registry filter pipeline); not wired to any card |
| "Invokes into your current context, not navigates" (§4.9) | ❌ — the whole point of S-1; today every result navigates |

## DELIVERABLE 3 — Type B calls for James

**#1 — Entity-model path (the big one).** (a) Adapter-over-fragmentation now (peek-builder pattern, ~400 LOC, customer card reads CompanyEntity+Contact and shows what Vault CRM shows; CustomerContact/VendorContact/FHCaseContact rows invisible to v1 portal) vs (b) CRM unification first (6–8 weeks, resequences the ratified arc) vs (c) adapter now + unification unchanged on its own threshold. **Investigator's read: (c).** The adapter is the shipped house pattern (peek, triage, NL-resolver all do it); the portal contract is model-agnostic so unification later is an internals swap. The honest cost of (c): v1 "customer" cards can miss contacts that live only in the three parallel tables — say so in the card's design rather than pretending completeness.

**#2 — Hydration path.** (a) Inline in `/command-bar/query` (bump ResultItem) vs (b) second-call hydration on entity-select. **Read: (b), specifically EXTEND THE PEEK SUBSTRATE** — either generalize `GET /peek/{type}/{id}` with a `?depth=portal` or add `GET /api/v1/command-bar/portal/{type}/{id}` reusing/enriching PEEK_BUILDERS. Keeps the query gate untouched, inherits the proven builder pattern, and gets its own BLOCKING gate (mirror the peek gate; portal budget suggestion p50<150/p99<400 given richer assembly). The one UX cost — a fetch on select — is the same one peek already made invisible.

**#3 — Card = widget from day one** (the Job 4 contract) vs bespoke portal components now, widget-ify at S-5. **Read: widget from day one.** The contract already exists (`WidgetRendererProps` + variant switch + self-fetch + registry); bespoke-now means a guaranteed S-5 rewrite and violates the composition-reuse discipline INTERACTION_MODEL names. Cost of widget-first: two-layer registration ceremony + `surface: "command_bar"` addition (additive, non-breaking).

**#4 — Where the portal renders.** (a) In-palette mode swap (NL precedent) vs (b) floating panel(s) beside the palette (§4.3's literal picture, and the host S-2 needs). **Read: (b)** — build `CommandBarSurfaceHost` as a sibling of the palette overlay in S-1 with max-1-card; S-2 raises the cap to 2–3 and adds non-entity surfaces. Same host later gains the park affordance (S-5) — the host is where Act-discipline lives, so it must be its own component either way.

**#5 — Click-to-call scope.** (a) Full RingOut endpoint on the live RC integration vs (b) `tel:`/copy affordance v1, RingOut later. **Read: (b) in S-1** — outbound dialing is its own small integration arc (auth scopes, device selection, error surfaces); the card's affordance contract is identical either way, so nothing is lost by deferring the transport.

**#6 — Disambiguation (§4.6).** The keyboard-numbered candidate cards are spec-only; S-1 could ship portal-on-top-result-only and defer §4.6, or include it since entity-select is the trigger moment. **Read: defer to S-2/S-4** unless the ~800ms pick moment proves essential during S-1's build — the plain ranked list already disambiguates functionally.

## DELIVERABLE 4 — LOC floor (S-1 only; floor, not ceiling)

| Work | LOC floor |
|---|---|
| Portal hydration endpoint + enriched/new builders (customer, product; pivots + permission-gated financial section) + tests | ~450 |
| Entity-card widget components (~6 types, Brief variant, shared chrome/label primitives reusing peek `_shared`) | ~700 |
| `CommandBarSurfaceHost` (Act-discipline host) + CommandBar wiring + adapter touch | ~300 |
| Contract additions (surface value, config type, onPivot) + two-layer registrations | ~150 |
| Latency gate (portal endpoint) + vitest for host/cards | ~250 |
| **Floor total** | **≈ 1,850** |

Excludes: §4.6 disambiguation, RingOut transport, S-2 surfaces, any park machinery.

— Read-only confirmed: no code or schema changes, no Type B decided, no push. This file is the sole write. —
