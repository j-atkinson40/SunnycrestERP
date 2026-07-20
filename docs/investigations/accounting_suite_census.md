# The Accounting Suite Census — what actually exists

**Date:** 2026-07-20 · **HEAD:** `796572e5` · **Read-only** — the corrected map is the deliverable.
**Method:** four parallel ground-truth sweeps (AP+acceptance · reporting+cash · exceptions+tax+assets
· costing+year-end+catch-all), every claim carrying file:line, wiring checked at every layer:
model → service → route registered (`api/v1.py`) → UI routed (`App.tsx`) → nav-reachable
(`navigation-service.ts` or a hub-card link).

**The operator's belief is confirmed in the large:** much of the suite IS built — AP is complete
end-to-end, statements/JE/reconciliation/aging all real, the four annual agents ship whole.
The census's work is the seams: a large DORMANT register (built-but-unwired — this platform's
signature), a handful of hollow numbers wearing complete clothes, and a short truly-ABSENT list.

**One structural fact colors every "reachable" verdict:** `navigation-service.ts` exposes only
hubs (`/financials`, `/agents`, Vault). Every leaf accounting page depends on a hub-card link.
Where a page is routed but no hub links it, it is effectively invisible — the orphan class below.

---

## 1. THE CLASSIFICATION TABLE (the suite jobs, judged)

### Pay the bills — **COMPLETE** (with two honest asterisks)

| Capability | Class | Evidence |
|---|---|---|
| Vendor bill entry (CRUD, auto-number, PO pre-fill) | COMPLETE | `vendor_bill_service.py:136`; route `vendor_bills.py:89-180` (v1:843); UI `vendor-bills.tsx` @ App:1085; hub tile `financials-hub.tsx:129` |
| Bill approval | COMPLETE | `vendor_bill_service.py:275` (pending/draft→approved, actor+timestamp, audit); perm `ap.approve_bill`. Flat single-tier — no amount thresholds |
| Payment RECORDING (the full loop) | COMPLETE | `vendor_payment_service.py:84` (sum==total, app≤balance, status roll `paid/partial`); UI `vendor-payments.tsx:79` NewPaymentForm with per-bill application rows @ App:1107 |
| Payment SCHEDULING / payment run | **PARTIAL** | Suggested-run endpoint `financials_board.py:413` + Payment Run tab `financials-board.tsx:417` — **view-only**: no PaymentRun model, no execute/batch endpoint; payments enter one-by-one |
| PO + receiving | COMPLETE | `purchase_order_service.py:245-343` (send, receive w/ over-receipt guard, inventory update) |
| "3-way match" | **PARTIAL** | It's a 2-way LINK (PO→bill line pre-fill `vendor_bill_service.py:171-177`; PO→receipt for inventory). NO qty/price variance reconciliation, no hold-on-mismatch anywhere |
| AP aging | COMPLETE | `ap_aging_service.py`; route `ap.py:19` + CSV `:60`; UI `ap-aging.tsx` @ App:1116; hub tile |

*Asterisks:* (1) agent alert deep-links **404** — `agent_service.py:411,424` send users to `/ap/payment-run`
and `/ap/bills?tab=ap-aging`, neither routed; the real tab lives at `/financials/board`. (2) The
Financials hub "Payments" tile points at AR (`/ar/payments`); `/ap/payments` has **no hub tile**
(cross-links only).

### Understand the numbers — **PARTIAL** (P&L real; the rest thinner than its docstring)

| Capability | Class | Evidence |
|---|---|---|
| Income statement / P&L (live view) | COMPLETE* | `financial_report_service.py:35`; route `reports.py:33`; UI `reports.tsx` @ App:1101, hub card `financials-hub.tsx:167` |
| AR/AP aging, sales-by-customer, invoice register | COMPLETE* | `reports.py:47-71` + `reports.tsx:23-31` |
| Tax summary report | **HOLLOW** | `financial_report_service.py:206-210` returns hardcoded empty (`jurisdictions:[], total_tax:0`). Route + UI tab render zeros forever |
| **The "13 report types" claim** | **FALSE** | Docstring `financial_report_service.py:1`; only **6** generators exist |
| Balance sheet | ABSENT | No generator; only LLM-commentary branch (`report_intelligence_service.py:39`) + tax-package "requires CPA input" (`tax_package_agent.py:400`) |
| Trial balance | ABSENT | Only a preflight check STRING (`report_intelligence_service.py:338`) |
| General ledger view | ABSENT | `journal_entries.py:432 /gl-accounts` lists the COA; no ledger/transaction view |
| Journal entries (post, reverse, AI parse) | COMPLETE* | Route-resident logic `journal_entries.py:72-266`; UI `journal-entries.tsx` 3 tabs @ App:1099; templates/periods tabs largely read-only (create handlers unverified) |
| Chart of accounts management | **PARTIAL** | Read-only COA list feeds the JE form; `FinancialAccount` CRUD exists API-only (`reconciliation.py:95,124`); **`/settings/accounts` is a DEAD LINK** (board `financials-board.tsx:1325` + two `run_health_check` action_urls → no such route) |
| Monthly statements (generate→approve→send) | COMPLETE* | `statement_generation_service.py:99-155` (safety refusal: "wrong money number worse than no statement"); routes `statements.py:64-359` incl. send-all + received-statement inbox; UI `statements.tsx` @ /ar/statements |
| Bank reconciliation (the workflow) | COMPLETE* | `reconciliation.py:146-636` (start, populate-from-feed [Plaid], CSV, matching, actions, confirm); UI embedded WHOLLY in `ReconciliationZone` (`financials-board.tsx:1084-1355`) — no standalone page; account provisioning DORMANT (API-only + the dead link above) |
| The Financials Board | COMPLETE*, registry decorative | 7 hard-coded zones (`financials-board.tsx:134-153`); **`FinancialsBoardRegistry.getZones()` is never called** — only `getAllSettingsItems()`; `AuditReadinessZone` renders with NO registry entry (so no settings toggle) |

### Watch the cash — **the census's biggest finding: the substrate arrived; the surface didn't**

| Capability | Class | Evidence |
|---|---|---|
| Cash-flow "forecast" | **PARTIAL** | `financials_board.py:452` → CashFlowZone: a 5-week AR-due minus AP-due timing net. **Contains no actual cash** — no opening balance, no bank data |
| Financial health score (incl. cash-position component) | **DORMANT** | `financial_health_service.py:39-181` (5 components, daily), routes `financial_health.py:19-66` (v1:672) — **zero frontend consumers** (grep-proven) |
| Report intelligence (commentary/trends/forecasts) | **DORMANT** | Registered v1:652 — zero frontend consumers |
| **Plaid bank balances** | **DORMANT — the headline** | `bank_accounts.current_balance/available_balance` captured at link (`plaid/service.py:188-213`) but (a) **stripped from `item_summary` (:218) and the frontend type (`plaid-service.ts:12-20`)**, (b) **never refreshed on sync** (`plaid/sync.py` has zero balance writes), (c) shown in NO UI anywhere. Real cash-on-hand sits in the DB invisible |
| Bank transaction feed | PARTIAL | Powers reconciliation populate-from-feed + the uncategorized-fix list (`BankCategoriesSettings.tsx` @ App:825) — no browsing/ledger view, no cash surface |
| balance_reduction_advisor | PARTIAL | Emits behavioral insights (`proactive_agents.py:135-165`); `finance_charge_warnings` counter never increments (dead) |
| uncleared_check_monitor | **STUB-DISCARD** | `proactive_agents.py:350-372` counts stale outstanding checks, returns `{"flagged": N}`, writes NOTHING — fires nightly, output discarded |

### Handle the exceptions — **the thinnest suite job**

| Capability | Class | Evidence |
|---|---|---|
| Invoice voiding | COMPLETE | `sales_service.py:965` (+S2 draft-honesty); route `sales.py:540`; button `invoice-detail.tsx:251` |
| Payment voiding | COMPLETE | route `sales.py:642`; button `customer-payments.tsx:479` |
| Credit memos | **ABSENT** | Two prose mentions only (`agent_service.py:3`, `proactive_agents.py:126`); no model/service/route/UI |
| AR write-off | **PARTIAL (status, no verb)** | `invoice.py:40` enum value + badge (`invoices.tsx:67`); nothing sets it — hand-edit only. (The shipped "write-offs" UI is INVENTORY shrinkage — `write-offs.tsx` @ App:1136, itself nav-orphaned) |
| Refunds / credit disbursement | **PARTIAL** | Overpayment auto-credits `customer.credit_balance` (`sales_service.py:~1327`); **nothing ever disburses or applies it** — the money accumulates silently on the customer record |
| Short-pay | PARTIAL | Alert-only (`sales_service.py:1012`); no resolution workflow |
| Finance-charge forgiveness | **DORMANT — a whole engine** | `finance_charge_service.py` run/calculate/review/approve/approve-all/forgive/post + settings (`finance_charges.py:104` etc., v1:527) — **zero frontend anywhere**. Complete backend workflow no user can reach |

### Sales tax accumulation/filing — **infrastructure yes, filing no**

| Capability | Class | Evidence |
|---|---|---|
| Jurisdictions/rates/exemptions mgmt | COMPLETE | `tax.py` routes (v1:719); `tax-settings.tsx` 3 tabs @ App:1100; exemptions live on Customer (`customer.py:97`) |
| Resolution engine | COMPLETE | `tax_service.py` — U-1's one resolution serves quotes; order/invoice resolve-line endpoints exist |
| **Accumulation into filing periods** | **ABSENT (labeled stub)** | `proactive_agents.py:227-268` `run_tax_filing_prep` computes only WHICH period is due; explicit `# For now, return the prep structure` (:262); no tax_period model; even the stub's endpoint (`proactive_agents.py:58`) has no frontend consumer. And the report that should feed it (`get_tax_summary`) is the hardcoded-zero stub above. **No sales-tax return can be produced** |
| estimated_tax_prep agent | COMPLETE (different tax) | Federal quarterly INCOME-tax estimates (`estimated_tax_prep_agent.py:53-116`) via /agents dashboard — not sales-tax |

### Fixed assets & depreciation — **ABSENT**

No asset register, no depreciation engine anywhere. Depreciation exists as: a year-end AUDIT of
manually-posted JEs (`year_end_close_agent.py:287-365` — flags missing/irregular), a checklist
string (`proactive_agents.py:389`), and a tax-package punt ("requires CPA input",
`tax_package_agent.py:400`). The `equipment` model is employee/operational tracking — no cost
basis, no GL linkage; do not conflate.

### Costing / margin — **the numbers wear complete clothes and are hollow underneath**

| Capability | Class | Evidence |
|---|---|---|
| Product cost fields | COMPLETE (data) | `product.py:29-30,83` (`price`, `cost_price`, `wholesale_cost`) — stored, imported, displayed |
| BOM material-cost rollup | **PARTIAL (nav-orphan)** | `bom_service.py:375-423` (Σ component cost×qty×waste); routes v1:431; UI `/bom` @ App:1155 — **no nav entry, no inbound link from any reachable page**: URL-only |
| Margin (anywhere) | **ABSENT** | `order_pricing_service.py` + `price_list_analysis_service.py` (1,032 lines): zero cost/margin references |
| **Gross margin on the P&L** | **STRUCTURALLY FICTITIOUS** | `financial_report_service.py:53-54` computes `gross_margin_percent`, but `_sum_by_gl_type(...,"cogs")` returns `[]` BY DESIGN ("no COGS dimension exists in the model", `:354-357`) → **reported gross margin ≈ 100% always**, and `report_intelligence` + `budget_vs_actual_agent` surface the hollow number |
| Inventory valuation / COGS | **PARTIAL** | No cost column on `inventory_item`/`inventory_transaction`; the ONLY valuation is the year-end agent's ephemeral `qty × Product.cost_price` (`year_end_close_agent.py:531-586`) |

### Year-end / 1099 / W-9 / exports — **COMPLETE, with one self-declared gap**

| Capability | Class | Evidence |
|---|---|---|
| 1099 prep agent | COMPLETE | `prep_1099_agent.py:52-517` — $600 threshold, tax-ID masking, gap flags, CPA-ready HTML artifact; /agents dashboard (nav :152) |
| Year-end close agent | COMPLETE | Inherits month-end's 8 steps + 5 year-end (`year_end_close_agent.py:60-66`) |
| Tax package agent | COMPLETE | Read-only capstone compiling approved agent outputs into a CPA packet (`tax_package_agent.py:14-66`) |
| Annual budget agent | COMPLETE | `annual_budget_agent.py:35-66`; output consumed by budget-vs-actual as the formal budget source |
| W-9 collection | **ABSENT — self-declared** | The 1099 agent SHIPS the admission: anomaly `w9_tracking_not_implemented`, "Recommend maintaining W-9s in your CPA's system" (`prep_1099_agent.py:317-324`). Vendor has `tax_id` + `is_1099_vendor` only |
| Sage CSV export | COMPLETE (nav-orphan) | Provider substrate + `sage-exports.tsx` @ App:1140 — reachable only via an onboarding page link |
| QBO | DECOMMISSIONED, residue | Factory 410s correctly; stale: `tenant_module_service.py:449` still advertises the module, 2 extension blurbs, `category_catalog.py:261-282` imports a deleted provider behind try/except |
| Period locks | COMPLETE | Model+service+routes (`agents.py:456-490`) + `AccountingPeriodsTab` @ /vault/accounting/periods |

### Payment ACCEPTANCE (money in by card/ACH) — **ABSENT; Stripe is a ghost**

- Config keys exist (`config.py:35-37`), Stripe ID columns exist on plans/subscriptions/events —
  **zero `import stripe`, zero SDK calls, zero webhook routes** in the entire backend
  (`platform_incidents.py:41`: "Future: wire to Stripe webhook handler").
- No pay-invoice link, no portal payment, no ACH intake anywhere. `customer-payments.tsx` RECORDS
  manually-received money; nothing accepts it.
- `billing_service.py` is PLATFORM subscription bookkeeping (Bridgeable→tenants), wired for manual
  create/cancel — money movement dormant. Note the name collision: the tenant "Billing" page
  (`pages/billing/billing-page.tsx`) is AR invoices/statements, unrelated.

---

## 2. THE DORMANT REGISTER (built-but-unwired — the best news, prominently)

Ranked by leverage; each needs WIRING, not building:

| # | Dormant capability | What exists | The missing wire | Size |
|---|---|---|---|---|
| 1 | **Plaid cash position** | Live bank balances captured in `bank_accounts.current_balance/available_balance`; categorized transaction feed | Add balances to `item_summary` + frontend type; refresh balances on sync; a cash-position card (board zone / map glance); feed the opening balance into the cash-flow forecast | **cheap-assembly** (~½ session) — the highest-leverage unwired capability in the platform |
| 2 | **Finance-charge engine** | Full run/calculate/review/approve/forgive/post workflow, routed (v1:527) | A UI surface (a Financials-hub page or a triage queue — the 8b–8d pattern fits perfectly) | cheap-assembly (~1 session) |
| 3 | **Financial health score** | 5-component daily score incl. cash position, routed (v1:672) | One widget/zone consumer | cheap-assembly (small) |
| 4 | **Report intelligence** | Commentary/trends/forecasts/preflight, routed (v1:652) | A consumer on the reports page | cheap-assembly (small); note its audit-package TODO remains a stub inside |
| 5 | **BOM costing** | Complete cost rollup + UI, routed | One nav/hub link | trivial |
| 6 | **FinancialAccount provisioning** | CRUD via reconciliation routes | The `/settings/accounts` page the dead links already point at | cheap-assembly (small) |
| 7 | **Sage exports / write-offs / transfers pages** | Routed, working | Hub/nav links (`/inventory/sage-exports`, `/inventory/write-offs`, `/transfers`) | trivial |
| 8 | **uncleared_check_monitor** | Correct stale-check count, fires nightly | Write an insight/notification instead of discarding the return | trivial |

---

## 3. TRULY ABSENT (a real build each — sized honestly)

| Capability | Why it's a build | Size |
|---|---|---|
| Credit memos | New model + AR math (posting interacts with the S2 chokepoint) + UI | ~1–1.5 sessions |
| AR write-off verb + credit disbursement/application | Verb + guards + balance math through the one posting law; credit-application UI | ~1 session (pairs naturally with credit memos) |
| Sales-tax accumulation/filing | Period model + accumulator over computed tax + jurisdiction report (replaces both stubs: `get_tax_summary` + `tax_filing_prep`) | ~1–1.5 sessions; U-1's resolver makes the input honest now |
| COGS dimension (real gross margin) | The structural one: cost capture at order/invoice line level (or GL COGS postings), inventory cost — the P&L's fiction dies only with a modeled dimension | **real arc** (2+ sessions); decide policy first (standard cost from `Product.cost_price` vs perpetual) |
| Balance sheet / trial balance / GL view | Needs a real GL posting spine (JEs exist; invoices/payments don't post to GL) — same root as COGS | **real arc**; honest note: today's "books" are subledgers + JEs, not a double-entry ledger |
| Fixed assets & depreciation | Register + schedules + JE generation | ~1–2 sessions, low urgency (year-end agent already audits the manual path) |
| W-9 tracking | Small model + vendor UI + 1099-agent integration (it already flags the gap) | ~½ session |
| Payment acceptance (Stripe) | Real integration arc: SDK, webhook, pay-links/portal, AR application through the posting chokepoint | **real arc** (2–3 sessions) |
| Payment-run execution (batch AP pay) | PaymentRun model + execute endpoint over existing vendor-payment machinery + the view-only tab gains its verb | ~1 session |
| 3-way match (real) | Variance rules + hold states over existing PO/receipt/bill links | ~1 session |

---

## 4. THE BROKEN-THINGS REGISTER (small, factual, cheap)

- Agent alert deep-links 404: `/ap/payment-run`, `/ap/bills?tab=ap-aging` (`agent_service.py:411,424`).
- Dead link `/settings/accounts` from the board (`financials-board.tsx:1325`) + two health-check action_urls.
- Hub "Payments" tile mislabels (points to AR; AP payments has no tile).
- `get_tax_summary` renders zeros forever behind a real-looking report tab.
- Gross margin ≈100% fiction on the P&L (flagged above — worth a UI honesty note until COGS lands).
- QBO residue: module catalog entry, 2 extension blurbs, ghost import in `category_catalog.py`.
- Nav item labeled "API Keys" points at `/admin/accounting` (`navigation-service.ts:345-350`).
- `FinancialsBoardRegistry` is decorative (`getZones()` never called); AuditReadinessZone has no settings toggle.
- `balance_reduction_advisor`'s `finance_charge_warnings` counter never increments.

---

## 5. THE CORRECTED SUITE MAP (one paragraph per job — what the operator actually has)

- **Pay the bills** — YOURS TODAY, end to end. Missing only: batch payment execution, real 3-way match. Fix the 404 deep-links cheaply.
- **Understand the numbers** — P&L/agings/register/statements/JE/reconciliation are real. Balance sheet, trial balance, GL are NOT (no GL spine). The tax report is a stub. Two intelligence layers are built and dark.
- **Watch the cash** — the substrate landed with Plaid; the surface is one cheap session away (balances → card → forecast opening balance). Today's "cash flow" is AR/AP timing only.
- **Handle the exceptions** — void works; everything else is status-without-verb, alert-without-workflow, or absent. The finance-charge engine is complete and invisible.
- **Sales tax** — resolution is excellent (U-1); accumulation/filing does not exist despite two stubs pretending.
- **Fixed assets** — absent; the year-end agent audits the manual practice honestly.
- **Costing/margin** — data fields exist, BOM rolls up material cost (unreachable), and the P&L's gross margin is fictitious until a COGS dimension is modeled.
- **Year-end** — the four annual agents are genuinely done and reachable; W-9 is the self-declared gap.
- **Payment acceptance** — absent; Stripe is columns without code.

*The operator curates from this reality. The dormant register is the cheap season; the GL/COGS
root is the one real arc hiding under two different symptoms (no balance sheet + fictitious margin
are the same missing spine).*
