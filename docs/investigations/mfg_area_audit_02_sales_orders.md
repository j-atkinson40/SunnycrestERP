# MFG Area Audit #2 — Sales & Orders (the four-list ledger + the jobs skeleton)

**Date:** 2026-07-18 · **HEAD:** `a6d20089` · **Read-only — the ledger is the deliverable.**
**Drawn boundaries honored:** quotes + pricing live HERE (incl. QUOTE_AUTO_EXPIRY); the
accounting seam is where an accepted order becomes an invoice (the handoff audited, not
the invoice); payment collection is accounting's (done).

**Scale note (per the STOP discipline):** this ledger is **comparable to or larger than
audit #1's**. The structural root of most of it is one fact — **there are TWO parallel
quote/order-money systems on the same tables** (the Order-Station path in
`quote_service.py` and the AR path in `sales_service.py`, with five more creation paths
orbiting them, each doing its own math). The operator sequences; the audit proposes the
cheap class-killers first and the unification as its own arc.

---

## THE OPENERS

### Opener 1 — The fires strip (Pull Bank Transactions)
**The machine works; the coffee moment is still ahead.** As of the audit (Jul 18, 20:04
EDT) the strip carries its first LIVE fires — but they belong to **16 `d3-*` test-residue
companies** (timezone UTC) whose 22:30 struck at 18:33 EDT: each fired exactly-once,
`trigger_source=moc_task_schedule`, live (not dry), with the honest `ingested: 0` ("No
bank connections"). Sunnycrest + testco sit on America/New_York — **the real first fire
is tonight 22:30 EDT**, followed by 06:30 tomorrow. Verdict: provenance ✓, exactly-once ✓,
honesty ✓ — and the standing **dev test-residue cleanup item just gained a live
consequence** (16 dead companies riding every vertical_default fan-out, forever, until
cleaned — see D-10).

### Opener 2 — QUOTE_AUTO_EXPIRY's post-heal life
**Working, and correct.** `expire_stale_quotes` (`sales_service.py:492-515`): only
`draft`/`sent` flip; `accepted`/`converted` untouched; expiry-null skipped; `modified_at`
stamped; commit only when work happened. Dev data: **zero** overdue-but-unexpired quotes
(`sent`/`draft` past expiry = 0 rows); 4 quotes properly `expired` with past dates
(Jun 23–Jul 8). The job that started the C-10 saga is quietly healthy.

### C-10-healed columns — deeper truth (the dispatch's List-2 rider)
The heal restored **structure** correctly (r124/r125/r126; drift gate clean) and app-created
quotes populate the healed columns (`product_line` set at `quote_service.py:266`). But on
dev the SEED fills only `customer_name` (24/24); **`product_line` is 100% NULL (0/24)**,
`delivery_charge`/`installation_*`/`contact_*` likewise — so the Order-Station UI's
product-line grouping (`order-station.tsx:1467`) renders seeded quotes into a blank
bucket. **Verdict: schema true, data seeded-hollow — a seed gap, not a heal fault.**
Money columns themselves are coherent (0 line_total mismatches; 0 orders where
subtotal ≠ Σ lines) — the $0 incoherence that exists comes from the zero-money creation
beats (List 1 #6), not the heal.

---

## LIST 1 — SILENTLY WRONG (severity-first; money math hand-checked)

### 1.1 🚩 Delivery charge DOUBLE-COUNTED on Order-Station quotes (the worst number)
`quote_service.py`: delivery is added into `subtotal` at `:238` AND added again in the
tax branch at `:320` (`total = subtotal + tax_amount + delivery_charge` — subtotal
already contains delivery). **Hand-worked:** $1,000 lines + $100 delivery, 7% tax →
charged **$1,277.00**; correct is $1,177.00. **The customer is overcharged the full
delivery amount on every Order-Station quote that resolves a tax jurisdiction**
(cemetery_id or customer_id present). The non-tax branch (`:250`) is correct — the bug is
*conditional*, the worst shape. The wrong total then **copies verbatim onto the
SalesOrder** at conversion (Beat 2→4) and from there verbatim onto the invoice (the seam
carries faithfully — a statement that lies earlier in the pipeline, exactly as the
dispatch predicted). Secondary: tax is computed on a delivery-inclusive subtotal
(policy-dependent; compounds the double-add).

### 1.2 🚩 The customer AR balance is posted TWICE in the standard flow
`create_invoice_from_order` bumps `customer.current_balance += invoice.total`
**unconditionally at creation, drafts included** (`sales_service.py:755-757`); approval
bumps it **again** (`draft_invoice_service.py:612-613`, and `approve_all_no_exceptions`
`:669-672` — whose docstring claims approval is where posting happens). The standard
end-of-day flow (18:00 draft → morning approve) double-counts every invoice. **Masked,
not fixed**, by the nightly `run_ar_balance_reconciliation` sweeper
(`proactive_agents.py:441-514`, 02:00) which recomputes and silently overwrites — and
whose alert copy misattributes the drift to "failed transactions, import edge cases, or
manual adjustments," never naming the real cause. The balance lies from approval until
the next sweep. (Dev shows 0 drift right now — because the sweeper already laundered it;
5 `auto_generated` drafts are queued to double-post on approval.)

### 1.3 🚩 `completed` orders leak out of the invoice net
The 18:00 batch filter is `["confirmed","processing","shipped","delivered"]`
(`draft_invoice_service.py:199`) — **`completed` absent**. Dev: **3 past-due completed
funeral orders (~$9,942) that will never auto-invoice** (SO-2026-0008/-0009/-0010).
Compounded by 1.7's per-order swallow: a failed invoice creation is logged and forgotten.

### 1.4 🚩 Order-Station "create order" can silently create NOTHING but still return 201
`order_station.py:489-490`: the entire mode="order" quote→order conversion is wrapped in
`except Exception: pass`. If conversion fails, the user is told the order was created;
only a quote exists. Money adjacent (an order book that lies by omission).

### 1.5 Conditional pricing NEVER applies to quotes
`get_effective_price`/`recalculate_order_line_prices` are called ONLY from
`create_sales_order` (`sales_service.py:613-615`). Both quote paths take caller-supplied
prices verbatim — a `has_conditional_pricing`/`is_call_office` product quotes at whatever
was typed (or $0 per 1.6), then REPRICES at order conversion. Quote and order can state
different prices for the same goods, silently. (Structural cause: pricing forked outside
the sales money path — List 4.)

### 1.6 The confident-zero family (money defaults)
- `quote_service.py:220` — missing `unit_price` in a line dict → **$0.00 line**, silent.
- Beats 7/8/9 (call-extraction `call_extraction_service.py:247`, vault cross-tenant
  `vault_order_service.py`, legacy-studio `legacy_studio.py:355`) create orders with
  **zero/derived-zero money** — 27 of dev's 61 orders are $0/zero-line from these paths.
- `bundle_pricing_service.py:122` — NULL conditional-charge price → $0 silently; `:37,48`
  same for bundles.
- `quote_service.py:321-322` — the ENTIRE tax computation is try/except→warning: a tax
  lookup failure ships the quote **untaxed**, silently.
- `order_pricing_service` vault detection (`has_vault_on_order` `:21-44`): a vault product
  missing category/variant AND absent from the hardcoded `VAULT_PRODUCT_LINES` set
  resolves "no vault" → charges the **higher standalone price** silently (a
  data-quality-gated overcharge).

### 1.7 Unrounded money & rounding drift
- `order_pricing_service.py:96` — `line.line_total = price * qty` **without
  `.quantize(.01)`**; the unrounded values are then SUMMED into `order.subtotal/total`
  (`:102`) before the DB truncates per-line — in-memory totals can disagree with persisted
  lines by cents.
- `vault_order_service.py:249,251,266` — same class (no quantize) + `tax_amount`
  hard-zeroed on cross-tenant orders.

### 1.8 One action, two truths: convert-quote diverges by route
AR route (`sales.py:323` → `sales_service.convert_quote_to_order:242`) → order
**`draft`**. Order-Station route (`order_station.py:546` →
`quote_service.convert_quote_to_order:361` — a *different function*) → order
**`confirmed` on INSERT**, which **bypasses `on_order_confirmed`** (the hook only fires
via `update_sales_order`, `sales_service.py:686`) — so Order-Station and vault
cross-tenant orders (Beat 8) are born confirmed but **never auto-spawn a delivery**. The
tenant flag `auto_create_delivery_from_order` silently doesn't apply to two of the three
confirm paths.

### 1.9 Number generation (collision + convention breaks)
- Both quote `_next_number` impls (`sales_service.py:38-61`, `quote_service.py:131-151`):
  non-atomic max-scan, **no unique constraint** — concurrent creates collide; lexical
  `ORDER BY number DESC` breaks past 9999 (string max stays "9999" → 10000 forever →
  duplicates).
- `vault_order_service.py:225-233` — numbering by `count(*)+1` (collides after any gap).
- `legacy_studio.py:358` — `SO-LEGACY-{uuid}` breaks the `SO-YYYY-####` convention every
  reader assumes (invisible to `_next_number`'s LIKE scan and year-parsers).
- Two quote systems, two number LINEAGES on one table: `Q-YYYY-NNNN` (Order Station) vs
  `QTE-YYYY-NNNN` (AR).

### 1.10 The `cancelled` spelling landmine
`_auto_complete_order_on_payment` guard checks `("cancelled", "completed")`
(`sales_service.py:1125`) — double-L — while the codebase's value is `"canceled"`
(`:656,702`). Currently masked only because nothing ever writes canceled (List 3.1); the
moment cancellation ships, paid-then-canceled orders would auto-complete.

---

## LIST 2 — BROKEN LOUD

- **Beat 7 crashes on unknown customers**: `call_extraction_service.py:290` returns
  `None` → `customer_id nullable=False` → IntegrityError at `:262 db.flush()` → 500.
  Also passes `service_time` as an isoformat **string** into a `Time` column (`:258`).
- **NL sales-order creation is a dead capability**: declared as an `EntityType`
  (`nl_creation/types.py:29`) with a resolver (`entity_resolver.py:82`) but **no
  materialization code exists** — "new sales order for Hopkins…" resolves entities and
  creates nothing. (The command-bar `wf_create_order` action is pure navigation.)
- The two convert-quote functions coexisting under one name (see 1.8) is loud-adjacent:
  reading code cannot tell which fires without tracing the route.

---

## LIST 3 — MISSING (models imply, no surface serves)

1. **Orders cannot be canceled.** `canceled` is guarded against (`sales_service.py:656,702`)
   and filtered on, but NO endpoint/service writes it. The guards are dead-defensive.
2. **`processing` and `shipped` are dead filter values** — read in 8+ places
   (`internal.py:121`, `briefing_service.py:842/937/1540`, `draft_invoice_service.py:199`,
   `location_service.py:264`…) but written nowhere. Dev distribution: delivered 31,
   confirmed 24, completed 4, draft 2 — zero processing/shipped ever. Briefings and the
   invoice batch filter on statuses that cannot occur.
3. **`spring_burial` is an undocumented orphan status** — written
   (`spring_burial_service.py:143`), absent from the model's enum comment, read by no
   sales filter: a parked spring-burial order silently drops out of briefings, location
   counts, and the invoice batch until returned to confirmed.
4. **Partial fulfillment modeled, unimplemented**: `SalesOrderLine.quantity_shipped`
   written nowhere, serialized nowhere; the seam always bills 100% of ordered qty.
5. **SavedOrder never materializes**: templates are recorded
   (`saved_order_service.py:138`) but no "create order FROM saved order" path exists.
6. **No discount fields anywhere** on Quote/QuoteLine/SalesOrderLine — if line/order
   discounts are expected, the schema itself is missing them.
7. **The AR API can't see fulfillment truth**: `SalesOrderResponse` (`schemas/sales.py:151`)
   omits ~15 written columns (cemetery_id, order_type, scheduled_date, inventory warnings,
   spring-burial fields, driver exceptions, delivered_at/driver_confirmed, completed_at,
   location_id…). Set by real paths, invisible to the sales UI.
8. **Quote serializer gaps**: `_quote_to_dict` (`quote_service.py:539-573`) omits
   `payment_terms`, `tax_rate`, `tax_amount` (computed + stored, never returned).
9. **Manual invoice endpoint lacks guards** (seam rider): `POST /orders/{id}/invoice` has
   no already-invoiced check and accepts `draft` orders (`sales_service.py:697-706`).
10. **Seeds don't tell the routes' story**: 61/61 dev orders have `quote_id NULL` (the
    quote→order story unseeded); 27/61 are zero-line/$0 (the Beat 7/8/9 shapes); seeded
    quotes have `product_line` 100% NULL (the C-10 rider above).
11. **No customer-PO field exists on SalesOrder** — "PO crosses the seam" is structurally
    impossible today.

---

## LIST 4 — MISFILED (the drawn boundaries)

1. **Order-Station money math lives in `quote_service.py`**, not the shared sales
   helpers — the fork that produced 1.1/1.5/1.6. (The unification target.)
2. **Payment events mutate order state inside sales**: `_auto_complete_order_on_payment`
   (`sales_service.py:1115-1129`) — an invoice-payment listener completing orders;
   payment belongs to accounting, order lifecycle to sales — the coupling point should be
   an explicit seam, not a swallowed try/except.
3. **AR posting lives in the seam files**: balance mutation at creation
   (`sales_service.py:755`) and approval (`draft_invoice_service.py:612,669`) is AR-ledger
   work (and is the 1.2 double-post); the seam should hand off, accounting should post —
   once.
4. **Delivery writes order status directly** (`delivery_service.py:604`,
   `draft_invoice_service.py:258`) — fulfillment reaching into the sales record rather
   than through a transition function (which is also why hooks get bypassed — 1.8).
5. **Two tax models**: Order Station resolves jurisdiction via `tax_service`; AR trusts a
   caller-supplied flat `tax_rate`. One platform, two tax truths for the same tenant.
6. **Quote status vocabularies diverge**: Path A writes `declined`
   (`quote_service.py:477`), Path B and the model say `rejected` — filters keyed on
   `rejected` miss Order-Station declines.

---

## THE SEAM (audited as the boundary, per the drawn line)

**Amount fidelity: SOUND.** All four order→invoice paths funnel through ONE chokepoint
(`create_invoice_from_order`, `sales_service.py:697-774`) that carries totals AND lines
**verbatim** (no recomputation, matching Numeric types, no rounding surface). Dev
reconciliation: 29 linked invoices, **0 total mismatches, 0 duplicate invoices**. The
crossing itself tells the truth — the lies are on its flanks (1.2, 1.3, the manual
guard, the silent field-drops: ship-to, cemetery, order_type, service dates/locations,
delivery attribution all vanish at the crossing).

---

## THE JOBS SKELETON (the reframe-native chapter)

| JOB (as humans name it) | automations (existing) | human-work surfaces | notes |
|---|---|---|---|
| **Quote a customer** | Quote Auto-Expiry (nightly 23:40 — **not yet on the map**: an APScheduler job with no catalog row; mirror candidate) | Order-Station quick quote · Sales quotes + templates · duplicate | The two-systems fork lives inside this job; unification is its healing |
| **Enter an order** | none live (NL creation dead — List 2) | THE FLAGSHIP: the order form · Order Station · from-quote (×2 routes) | **The operator's named capability-ponder example — its beat list is READY** (below) |
| **Keep the order book honest** | draft_invoice_generator (18:00 — also not on the map; mirror candidate) · [missing: cancellation, spring-burial return visibility] | orders list · order station · briefing counts (currently filtering dead statuses) | The status-vocabulary heal (D-6) is this job's spine |
| **Get paid** | → points ACROSS the accounting seam to **Customer billing & statements** + **Bank reconciliation** (both already jobs there) | the seam's approval review | The job card here should REF the accounting jobs, not duplicate them |

**Job-shaped vs automation-shaped**: the sales-relevant nightly jobs
(QUOTE_AUTO_EXPIRY, draft_invoice_generator) are **invisible to the map today** — the
same shape the six accounting mirrors had pre-T-2. They are the area's first
mirror-then-adopt candidates when the Sales & Orders map chapter builds.

**THE FLAGSHIP — "sales order entry" capability-ponder beat list (ready):**
1. The AR order form (the reference math) · 2. The Order-Station funeral form
(quote→auto-convert) · 3. Convert a quote (AR route) · 4. Convert a quote (Order-Station
route) · 5. The command bar ("new sales order" → the form) · 6. Natural language (today:
honest never-face — declared, not yet wired) · 7. From a phone call (Call Intelligence
draft) · 8. From a connected funeral home (vault cross-tenant) · 9. From Legacy Studio
(proof-driven). Each beat's honesty caveat = its List-1/2 entry above; the ponder ships
when the pricing paths are healed enough to teach without asterisks.

---

## THE D-LIST (numbered, sized, fix-vs-delete, recommended order)

**Cheap class-killers first; the silent-zeros as real sessions; the unification as an arc.**

| # | Fix | Size | Mark |
|---|---|---|---|
| D-1 | **Delivery double-count** (`quote_service.py:320`): stop re-adding `delivery_charge`; decide tax-base policy (delivery taxed or not) explicitly; pin with the hand-worked example; **check historical quotes/orders for the overcharge** (a data census rides the fix) | S (fix) + S (census) | FIX NOW |
| D-2 | **Double AR-post**: pick ONE posting moment (approval, per the docstring's own claim), delete the other; fix the sweeper's alert copy to name what it finds; pin the single-post | M | FIX (real session) |
| D-3 | **`completed` into the batch filter** + decide the backfill for the 3 stranded orders; surface (not swallow) per-order invoice failures (`draft_invoice_service.py:307,416`) | S | FIX NOW |
| D-4 | **Order-Station convert swallow** → raise + honest response (no 201-with-no-order) | S | FIX NOW |
| D-5 | **Manual invoice guards**: already-invoiced check + refuse `draft` | S | FIX NOW |
| D-6 | **Status vocabulary heal**: retire dead `processing`/`shipped` from filters (or implement them deliberately); document/route `spring_burial`; unify `declined`→`rejected`; fix the `cancelled` spelling; THEN ship cancellation (List 3.1) as the missing verb | M | FIX (session) |
| D-7 | **Confirm-on-INSERT hook bypass**: route all confirms through one transition fn so `on_order_confirmed` fires (Beats 4/8) | M | FIX (session) |
| D-8 | **Numbering**: unique constraint per tenant + retry-on-conflict; kill count(*)+1; decide the SO-LEGACY convention | M | FIX (session) |
| D-9 | **Zero-money creation paths**: Beat 7 (customer-required crash + no lines), Beat 8 (quantize + tax), Beat 9 (numbering + money) — each small, batchable | M | FIX (batch session) |
| D-10 | **d3-\* test-residue purge** (16 dead companies riding every fan-out — the opener's finding; the standing board item) | S | DELETE NOW |
| D-11 | **THE QUOTE UNIFICATION** (the structural root): one money path, one tax path, one converter, one number lineage, conditional pricing applied at QUOTE time — absorbs the leftovers of D-1/1.5/1.6/List-4.1/4.5/4.6 | **ARC** (2–3 sessions) | THE CAMPAIGN |
| D-12 | Serializer honesty (List 3.7/3.8) — surface what's written | S–M | FIX (rides D-11 or alone) |
| D-13 | NL sales-order: wire it or retire the declaration (honest never-face until then) | M | DECIDE |
| D-14 | Seed truthfulness: quote→order lineage + product_line + lined orders in seeds | S | FIX (rides any) |

**Recommended sequence:** D-1+D-3+D-4+D-5+D-10 as ONE cheap class-killer session (all
small, all silent-wrong or leak-class) → D-2 (the AR double-post, its own session with
the sweeper honesty) → D-6+D-7 (the lifecycle session) → D-8+D-9 (the creation-paths
session) → **D-11 the unification arc** (with D-12/D-14 riding) → the Sales & Orders map
chapter (jobs + the flagship capability ponder) lands on healed ground.

---

*Everything above is file:line-cited from HEAD `a6d20089` with dev-DB evidence
(postgresql read-only). No code was changed. The severity findings (1.1–1.4) were
surfaced to the operator immediately during the audit, per discipline.*
