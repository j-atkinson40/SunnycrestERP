# D-11 Investigation — The Quote Unification

**Date:** 2026-07-20 · **HEAD:** `117813dd` (post five-commit S&O deploy, staging green) ·
**Read-only** — the plan is the deliverable.

Two parallel quote/order money systems on ONE table (`quotes`). The structural cause of
half of audit #2's ledger. The field is prepped: one allocator (Session One), one posting
moment (Two), one vocabulary discipline + one converter-hook (Three), one pricing
resolver + one rounding law (Four) — every flank pinned. This investigation maps both
systems whole, works the tax divergence with real numbers, censuses the data, renders
**THE VERDICT**, and shapes the surgery with honest sizing.

---

## 1. THE MAP — both systems, whole

### 1.1 Who creates what

| | **Q- system** (`quote_service.py`) | **QTE- system** (`sales_service.py` quotes block) |
|---|---|---|
| Numbering | `Q-YYYY-NNNN` (shared atomic allocator since S1) | `QTE-YYYY-NNNN` (same allocator, different prefix) |
| Routes | `/order-station/quotes` (POST/GET/PATCH + `/convert`) — 7 call sites in `order_station.py` | `/sales/quotes` (POST/GET/PATCH + `/status` + `/duplicate` + `/convert` + `/pdf` + `/summary` + `/badge-count`) |
| UI face | Order-Station quick-quote slide-over (`order-station.tsx`) | Sales → Quotes page (AR pipeline) |
| Customer | **Walk-in capable** — `customer_name` string, `customer_id` optional | `customer_id` **required** (404 if absent) |
| Distinct fields | `product_line`, `template_id`, `cemetery_id/name`, `permit_*`, `installation_*`, `contact_*`, `deceased_name`, `delivery_charge` | explicit `quote_date`, `expiry_date`, `payment_terms` |
| Non-route callers | NL creation / parse-order (order-station), Playwright demo flows | `email_action_service` (token accept/reject), `duplicate_quote`, badge/summary widgets |

### 1.2 The two tax models — worked divergence

- **Q- model (jurisdiction-resolved):** if `cemetery_id or customer_id` present →
  `tax_service.get_jurisdiction_for_order` (county engine, r8-audited) →
  `compute_tax(subtotal, rate_percentage)` → `tax_rate` stores the **effective fraction**
  (0.0700). Tax base includes delivery (its own line inside subtotal). Exemption-aware
  (`customer.tax_exempt`). Since S4, conditional pricing resolves first.
- **QTE- model (trust-the-caller):** `tax = round_money(subtotal × data.tax_rate)` where
  `tax_rate` is a caller-supplied fraction. **No jurisdiction lookup. No exemption check.**
  The platform's own tax engine is bypassed entirely.

**Identical business inputs, two answers.** Hopkins FH (Cayuga County, 7%), one $1,000
vault + $100 delivery:

| | Q- (Order-Station) | QTE- (Sales) with caller default `tax_rate=0` |
|---|---|---|
| Subtotal | $1,100.00 | $1,100.00 |
| Tax | **$77.00** (resolved 7%) | **$0.00** (caller said so) |
| Total | **$1,177.00** | **$1,100.00** |

The same customer quoted from two screens differs by $77 — and the QTE- number is the one
the AR pipeline mails. (`QuoteCreate.tax_rate` literally defaults to `Decimal("0.00")` — `schemas/sales.py:47`;
nothing resolves or validates a caller rate against the jurisdiction engine. The
confident-zero family's cousin, at tax altitude.)

### 1.3 The two status vocabularies

| | draft | sent | accepted | rejected | declined | expired | converted |
|---|---|---|---|---|---|---|---|
| Model comment (`quote.py:40`) | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ |
| QTE- `set_quote_status` | ✓ | ✓ | ✓ | ✓ | — | ✓ | (terminal) |
| Email actions (`email_action_service`) | | ✓ | ✓ | ✓ | — | | |
| Q- `update_quote_status` | — | ✓ | — | — | **✓** | ✓ | (terminal) |
| Q- `list_pending_quotes` filter | ✓ | ✓ | | | (reads "declined" in docstring) | | |

`declined` (Q-) and `rejected` (QTE-) are the same business fact wearing two words. A
Q- quote declined at the order station is invisible to any QTE-side "rejected" filter and
vice versa. **Data census: ZERO rows currently carry either word in any environment** —
the heal is code-only (the D-6 pattern repeats).

### 1.4 The lifecycle divergence (Session Three's deliberately-deferred seam)

- Q- `convert_quote_to_order` → order born **`confirmed`** on INSERT + fires
  `on_order_confirmed` (S3 fix — delivery auto-creates); copies `payment_terms` (S3),
  ship-to/deceased carried; returns dict.
- QTE- `convert_quote_to_order` → order born **`draft`** (pipeline review before
  confirm); PATCH→confirmed later fires the hook; no ship-to carry; returns ORM object.
- S4's parity pin holds money-fields identical across both for identical quotes; the
  status/shape divergence is the seam this arc closes.

### 1.5 Already-entangled faces (evidence the split is illusory)

- The **QTE route's PDF endpoint imports the Q- system's generator**
  (`sales.py:378 → quote_service.generate_quote_pdf`).
- `QUOTE_AUTO_EXPIRY` (`sales_service.expire_stale_quotes`, nightly, healthy post-C-10)
  sweeps the **whole table** — both systems' rows expire under one clock already.
- The S1 allocator, S4 pricing resolver, and S4 rounding law already serve both.

### 1.6 Consumers (who reads quotes, and which system each assumes)

| Consumer | Assumes | Notes |
|---|---|---|
| `order-station.tsx` | Q- dict shape (`_quote_to_dict`) | product-line grouping; S4 added tax fields |
| Sales quotes page | QTE- response schema (`_quote_to_response`) | badge count, summary, duplicate |
| `command_bar_data_search` | neither — raw table | number/customer match; system-agnostic |
| `email_action_service` | QTE- vocabulary (`accepted`/`rejected`) | token approval links |
| `expire_stale_quotes` (scheduler) | table-wide | both systems, one clock — already unified |
| Conversion → AR chain | both (two converters) | post-conversion everything is SalesOrder/Invoice — unified by S1–S4 |
| MoC map/jobs | QUOTE_AUTO_EXPIRY job ref only | the jobs chapter awaits this arc's answer |
| Vault dual-write (V-1f) | Q- only (`_write_quote_vault_item`) | QTE- quotes never reach the Vault timeline — an asymmetry the merge should close |

### 1.7 Beat 8 — the cross-tenant vault-order tax question (mapped, it lives here)

`vault_order_service.accept_vault_order` creates the manufacturer-side SalesOrder with
`tax_amount = 0.00` hardcoded (rounding fixed in S4; the tax question remains). The
correct shape post-unification: the manufacturer's jurisdiction engine resolves with the
FH as customer — **which is usually EXEMPT** (funeral homes resell; resale exemptions are
the industry norm, and `customer.tax_exempt` already models this). So the honest fix is
not "compute tax" but "resolve through the engine, which usually yields $0 *for the
documented reason* (exemption) rather than $0 by hardcode." Business confirmation
needed: does Sunnycrest collect resale certificates from its FHs (tax_exempt=True per
customer), or charge tax to uncertified accounts? **One operator/business answer, then a
2-line change inside U-1's unified tax path.**

---

## 2. THE DATA CENSUS

| Env | System | Rows | Money | Character |
|---|---|---|---|---|
| dev | Q- | 8 | $4,900.50 | ALL in `v1fg-*` test-residue tenants |
| dev | QTE- | 8 | $22,302 (2× mirrored sets) | `default` + `testco` — seed/test class |
| staging | Q- | **0** | — | — |
| staging | QTE- | 4 | $11,151 | testco seed class (2 expired / 1 draft / 1 converted) |
| **staging** | **sunnycrest (real)** | **0** | **$0** | **Sunnycrest has NEVER written a quote row in either system** |

**No census surprise — the inverse of one:** the migration-risk class is EMPTY. No real
money sits in `quotes` anywhere. Every row in both environments is synthetic. Statuses in
the wild: draft/sent/expired/converted only — zero `declined`, zero `accepted`, zero
`rejected`. The data-migration portion of this surgery is therefore **near-nil**: no
recompute-vs-carry dilemma has any rows to bite (policy stated anyway in §4.2 for
discipline), no vocabulary rows to map, no renumbering (r138's per-tenant unique already
spans both prefixes).

---

## 3. THE VERDICT (before shapes, per the dispatch)

**The audit's parallel-systems read is CONFIRMED in substance, with one refinement.**

These are **one business function built twice** — "a priced offer that may become an
order" — not two functions sharing a table. The evidence: same table, same lines model,
same conversion target, same expiry clock (already shared), same PDF generator (already
shared), same allocator/pricing/rounding (shared since the flank sessions). What
genuinely differs is the **face**: the Order-Station face is operational intake
(walk-in-capable, product-line-scoped, permit/cemetery/delivery fields, converts straight
to a confirmed order) and the Sales face is pipeline formality (customer-required,
payment terms, accept/reject ceremony, converts to a reviewable draft).

**Therefore: neither a pure merge (delete one) nor a split (two tables). The honest shape
is SHARED CORE, TWO FACES** — one money path, one tax model, one vocabulary, one
converter (with the draft-vs-confirmed flow as a *parameter*, not a fork), one serializer
core; both UIs remain as entry faces over it. The face differences are real and worth
keeping; the duplicated *core* is the defect.

---

## 4. THE SHAPES (per the verdict)

### 4.1 The keepers (argued from the flank sessions' laws)

| Concern | Keeper | Argument |
|---|---|---|
| **Tax model** | **Q-'s jurisdiction-resolved** (`tax_service` engine), with an explicit `tax_override` input for edge cases | The platform owns a county-jurisdiction engine (r8, audited clean); trusting a caller-typed fraction is the confident-zero class S1 killed at line level, recurring at tax level. Exemption-awareness rides free. The QTE face's rate field becomes an *override with a stated reason*, not the default path. |
| **Vocabulary** | `draft, sent, accepted, rejected, expired, converted` (the model comment's own set) | `rejected` already owned by 3 consumers (model, set_quote_status, email actions) vs `declined`'s 1; zero data rows either way; the D-6 precedent (canonical constant exported, comparisons rewired, writers normalize). |
| **Numbering** | **`Q-` going forward**; existing `QTE-` rows keep their numbers forever | Numbers are history, not identity; r138's unique index spans both. No renumbering migration — a renumber would break printed/emailed references for zero benefit. |
| **Converter** | ONE function, `target_status: "draft" \| "confirmed"` parameter | S3 closed the hook bypass and S4 pinned money parity; the remaining divergence is a flow choice the route declares. Confirmed target fires `on_order_confirmed` (already true); draft target fires it later on PATCH (already true). |
| **Serializer** | One core dict (S4's honest `_quote_to_dict` superset), faces select their view | Ends the two-shapes problem; the Vault dual-write asymmetry (§1.6) closes by moving the dual-write into the shared create core. |

### 4.2 The data migration (the highest-care class — stated even though near-empty)

- **Recompute-vs-carry: CARRY.** Historical quote rows keep their stored
  subtotal/tax/total verbatim — stored history is never silently rewritten (the S4 drift
  census discipline). The census says zero real rows exist, but the policy is stated so
  the migration is safe even against rows created between now and then.
- **Vocabulary mapping:** `UPDATE quotes SET status='rejected' WHERE status='declined'`
  — censused zero rows today; idempotent, reversible (r139 if any rows exist at ship
  time; skippable no-op otherwise — flag: **migration r139 conditional**).
- **Numbering:** none. **Schema:** none required — the unification is service-layer;
  no column adds, no drops. (Optional later hygiene: a CHECK on the status set.)
- **Post-merge proof:** re-run the S4 drift census (all-zeros expected) + the full S1–S4
  pin suite — the merge must not move a single stored cent.

### 4.3 The phases (each independently shippable)

| Phase | Content | Pins | Size |
|---|---|---|---|
| **U-1 — One money core** | Extract `quote_core.py` (or fold into quote_service): one `create_quote_core(lines, tax_policy, …)` used by BOTH creators; QTE path routes through jurisdiction tax with explicit-override; Beat 8's vault-order tax resolves through the same path once the exemption answer lands | S4 conditional/rounding pins re-run against both faces + new QTE-tax pin (the $77 worked example becomes a test) | ~1 session |
| **U-2 — One lifecycle** | `QUOTE_STATUSES` canonical set exported (D-6 pattern); `declined`→`rejected` everywhere; one `transition_quote_status` function; email actions + both PATCH routes converge on it; conditional r139 | both-spellings pins; transition-matrix pin (converted is terminal, etc.) | ~0.5 session |
| **U-3 — One converter** | Single `convert_quote_to_order(…, target_status)`; both routes call it; ship-to/payment-terms/deceased carry for both; return shape unified | S4 parity pin upgraded from money-fields to FULL-shape (minus the declared status param) | ~0.5 session |
| **U-4 — Faces + map landing** | One serializer core with face views; Vault dual-write moves into the core (QTE quotes join the timeline); UI convergence pass (order-station + sales quotes read one shape); **the jobs chapter documents THE quote system** — "Enter an order"'s nine audit-written beats land; Sales & Orders goes map-ready | vitest on both faces; Playwright walk of both entry paths | ~1 session |

**The honest number: 3 sessions** (U-1 alone; U-2+U-3 pair naturally; U-4 alone). Matches
the audit's ARC estimate of 2–3. The near-empty data census is the gift that keeps it at
the low end — no migration rehearsals, no remediation gates.

### 4.4 What this arc does NOT touch (scope fences)

- The **SalesOrder/Invoice** side — already unified by S1–S4 (allocator, posting,
  rounding, vocabulary); this arc is quotes-only.
- **D-13** (NL sales-order wire-or-retire) — independent decide; U-4 can absorb the
  "wire" option if the word arrives before it ships.
- **D-14** (seed truthfulness) — rides U-4 naturally (the seed authors quotes through
  the unified core, giving the map demo real quote→order lineage) but ships separately
  if U-4 runs long.
- The `default` tenant's mirrored QTE rows (dev oddity) — residue class, dies with the
  generalized dev-residue purge session already on the board.

---

## 5. THE DECISION SET (the operator's words)

1. **Verdict:** endorse **shared-core-two-faces** (recommended) — or argue for full
   face-merge / split.
2. **Tax keeper:** jurisdiction-resolved with explicit override (recommended per §4.1).
3. **Prefix forward:** `Q-` for all new quotes from U-1 on (recommended); QTE- history
   stands.
4. **Beat 8 business answer:** do FHs carry resale certificates (tax_exempt per
   customer), or does Sunnycrest charge uncertified accounts? (Determines whether the
   vault-order tax fix is "resolve→exempt→$0 documented" or "resolve→charge".)
5. **Phasing:** approve U-1 → U-2+U-3 → U-4 (recommended), or reorder.

**Migrations flagged:** one conditional (r139 vocabulary no-op unless rows appear);
zero schema changes; zero renumbering.

---

*Every invariant the four flank sessions pinned survives by construction: the merge
routes MORE traffic through the already-pinned paths, never around them. The pins are
the safety rail the surgery walks on — 34 S&O pins green before U-1's first edit, 34+
green after every phase.*
