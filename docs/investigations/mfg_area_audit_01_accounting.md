# Manufacturing Area Audit #1 — ACCOUNTING (read-only reconciliation ledger)

**Date:** 2026-07-09 · **HEAD:** `7348faf3` (r123, staging deployed same SHA) · **Read-only** — no code, no migration, no Planning writes.
**Pattern-establisher:** this doc doubles as the template for areas #2..N. §T at the bottom is the reusable structure; everything above it is the Accounting instance.
**Method:** every works/broken claim witnessed from source or `bridgeable_dev` (at r123) — never memory. The standing-rot catalog (`backend_health_triage_investigation.md`, 2026-06-26 + addendum) was re-verified item-by-item against **current** source; several entries have moved since it was written. Local uvicorn log checked (clean — fresh process, nightly agents haven't fired locally; code is the witness for scheduled-job rot).

---

## HEADLINE — three things that most change the picture

1. **The worst accounting rot is not a crash — it's silently wrong numbers.** The canonical statement-generation path (used by month-end close, the statement run workflow, and the statements API) computes `payments_total = 0` on **every statement** because a swallowed dead import (`app.models.payment`) makes the payments query throw and the `except` returns `Decimal(0)`. Every customer statement the platform has generated **omits all payments and overstates the closing balance**. Same class, two more places: AP aging always returns an empty vendor list, and the GL expense rollup silently drops all vendor bills from financial reports. These generate "successfully" — no error, no log, wrong output. (C-1, C-3, C-4 below.)
2. **The dead-import surface shrank from ~18 sites to 8 since the June catalog** — the clean repoints happened (widget_data inventory/safety, statements.py, command-bar, ops-board, gl_mapping, financials_board, plus the Phase-1 trio). **Everything left is the hard tail**: STALE-logic sites needing query rework against the renamed models, and DEAD paths needing a delete-or-model decision. 7 of the 8 remaining sites are accounting. This audit sizes each.
3. **The seed-omission class is real and cross-environment.** `seed_default_workflows` upserts only keys present in the seed dicts — omitted keys are never corrected. Two live consequences: `wf_sys_cash_receipts` has `scope='tenant'` (model default; born after the r36 backfill, r38 didn't cover it) so a Tier-1 platform workflow is misfiled in the three-tab builder in **every environment**; and the three migrated agents (`month_end_close`, `ar_collections`, `expense_categorization`) still carry stale `agent_registry_key` in any DB seeded before Phase 8c — display-only impact (badge + read-only view instead of the builder), but it makes migrated workflows look unmigrated.

---

## A. EXISTS AND MAPPED — the accounting slice of the manufacturing map today

Witnessed from `moc_pages.slug='manufacturing-map'` (dev, r123):

| Map row | Card | Backing artifact | Runtime health |
|---|---|---|---|
| AR Collections | workflows (mirror) | `wf_sys_ar_collections` (core, scheduled cron 0 23 * * *) | Works (8c migration; triage `ar_collections_triage` is canonical path) |
| Expense Categorization | workflows (mirror) | `wf_sys_expense_categorization` (core, scheduled */15) | Works (8c; `expense_categorization_triage`) |
| Month-End Close | workflows (mirror) | `wf_sys_month_end_close` (core, manual) | Runs, but **statements it triggers are wrong** — see C-1 |
| Monthly Statement Run | workflows (mirror) | `wf_sys_statement_run` (core, scheduled) | Runs, but **wrong numbers** — C-1 |
| Accounts Receivable | widgets | `widget_definitions.ar_summary` (financial, system) | Works |
| Standard Quote | documents | `document_templates.quote.standard` | Works — **boundary item Q1** (is quoting "Accounting"?) |
| Funeral Home Billing | task catalog (type=Accounting, End of Month) | **none** — no `workflow_template_id`, no triggers | Descriptive stub. It names the flagship business motion (monthly consolidated billing) but points at nothing |

Also mapped-adjacent: the four migrated accounting **triage queues** (`cash_receipts_matching_triage`, `month_end_close_triage`, `ar_collections_triage`, `expense_categorization_triage`) are the canonical human-approval surfaces for the mapped workflows — but triage queues are **not a MoC card type** (builders today: workflows / focuses / widgets / documents). See D-5.

## B. EXISTS BUT UNMAPPED

**B-1 — Cash Receipts Matching workflow.** `wf_sys_cash_receipts` (Tier 1, nightly 23:30, the 8b reconnaissance migration + its triage queue) is not in the mirror backfill's `_CORE` list and has no map row. It is a peer of the four mapped accounting workflows in every respect. Likely origin: the original mirror-triage dedup pass predated close attention to it. **Cheapest fix:** add to `_CORE` in `seed_moc_backfill_workflow_mirrors.py` (self-deploys) — but note its scope defect first (C-5).

**B-2 — Create Invoice + Send Statement (vertical, tier 2, manual).** Both exist as vertical workflows; both were excluded by the original manufacturing mirror triage (not in `_MANUFACTURING`). If that was dedup-against-Monthly-Statement-Run reasoning it half-holds for Send Statement, but Create Invoice is a distinct manual intent with no map presence. Revisit deliberately rather than assume the old triage verdict.

**B-3 — Revenue widget.** `widget_definitions.revenue_summary` (financial, system) — the only other financial widget in the composable substrate; unmapped while its sibling `ar_summary` is mapped.

**B-4 — Accounting document templates (9 unmapped).** `invoice.{clean_minimal,modern,professional}`, `statement.{clean_minimal,modern,professional}`, `email.statement`, `email.collections`, `email.approval_gate_review`. The map carries exactly one document (Standard Quote). If documents belong on the map at all (the FH stamp said yes), the invoice/statement families are the accounting area's most-used documents.

**B-5 — The unmigrated agent eight (Phase 8f never ran).** `unbilled_orders`, `estimated_tax_prep`, `inventory_reconciliation`, `budget_vs_actual`, `prep_1099`, `year_end_close`, `tax_package`, `annual_budget` — all registered in `AgentRunner.AGENT_REGISTRY`, none has a workflow row, a triage queue, or a map presence. Their only surface is the legacy `/agents` dashboard. These are invisible from the MoC by construction (the map surfaces workflows, and they aren't workflows yet).

**B-6 — The scheduler shadow-fleet.** Accounting-relevant scheduled jobs with no workflow row and no map representation: `ar_aging_monitor`, `collections_sequence`, `ap_upcoming_payments`, `draft_invoice_generator`, `ar_balance_reconciliation`, `quote_auto_expiry`, `missing_entry_detector`, `balance_reduction_advisor`, `tax_filing_prep`, `uncleared_check_monitor`, `financial_health_score`, `discount_expiry_monitor`, `payment_pattern_enrichment`. These fire nightly against every tenant and are invisible everywhere except stderr. (This is the same runtime-health gap the June catalog flagged as P3 — the map is now a natural surfacing candidate: a "scheduled monitors" card kind, or migrate-to-workflow one at a time per the 8b template.)

## C. EXISTS BUT BROKEN — witnessed from current source, sized

Ranked by user-visible damage. "Witnessed" = the exact file:line read this session at HEAD `7348faf3`.

**C-1 — Statement generation silently zeroes payments. SILENT-WRONG, flagship path. [size: 1 session]**
`app/services/statement_generation_service.py:56,106` — `from app.models.payment import Payment` inside `try/except`; module doesn't exist; `payments_total = Decimal(0)` / post-cutoff flag silently skipped. Callers witnessed: `month_end_close_agent.py:595`, `invoice_statement_adapter.py:62` (the wf_sys_statement_run path), `statements.py:216`, `approval_gate.py:280` — i.e., **the canonical path**. Not a repoint: `customer_payments` has no `amount` column (June catalog, re-confirmed) — the query needs rework against `CustomerPayment` + `customer_payment_applications` (application-level amounts). Fix must also decide semantics: payments *received* in period vs payments *applied to this customer's invoices* in period. One session including a parity test that seeds a payment and asserts a nonzero `payments_total`.

**C-2 — AP Upcoming Payments crashes every nightly fire. [size: 0.5 session after a rewrite-vs-retire call]**
`app/services/agent_service.py:333` — `from app.models.bill import Bill` **unwrapped** at the top of `run_ap_upcoming_payments` → `ModuleNotFoundError` every 23:10 fire, per-tenant, caught+logged by `_run_per_tenant`. STALE class: `VendorBill` uses `company_id` (not `tenant_id`) and statuses `paid/approved` (not `open/partial/overdue`) — a repoint alone would return wrong sets. **Domain call for the operator:** rewrite against VendorBill's real schema, or retire the job (AP alerts may be superseded by the vendor-bill views). Half a session once decided.

**C-3 — Financial reports silently exclude all vendor bills. SILENT-WRONG. [size: shares C-2's schema mapping — 1 session for both `financial_report_service` sites]**
`app/services/financial_report_service.py:109` (AP aging report → always `{"vendors": [], ...}`) and `:340` (`_sum_by_gl_type` → expense totals silently omit bill lines). Both wrapped, both dead (`app.models.bill`). Consequence: AP aging is an empty report; expense-side report rollups understate expenses by the entire vendor-bill volume. Rework against VendorBill (same field mapping as C-2 — do together).

**C-4 — Bank reconciliation can never match payments. SILENT feature-void. [size: 1 session incl. one domain call]**
`app/api/routes/reconciliation.py:272` (payment → `payments = []`) and `:282` (bill_payment → `bill_payments = []`, and **no BillPayment model exists** — DEAD path per the June classification, re-confirmed). Every reconciliation run silently has zero platform payment records to match against — the matching feature is a no-op for both directions of cash. Customer side: rework to `CustomerPayment` (exists; `company_id` present). Vendor side: decide — model vendor-bill payments, or drop that matching leg explicitly.

**C-5 — `wf_sys_cash_receipts` scope='tenant'. Cross-environment misfile. [size: hours]**
Witnessed: seed dicts in `app/data/default_workflows.py` contain **zero** `"scope"` keys (and zero `"agent_registry_key"` keys); `Workflow.scope` defaults `'tenant'`; the row was created post-r36 so no backfill ever corrected it; dev shows it as the only `wf_sys_*` not core/vertical. A Tier-1 platform workflow files under the wrong tab in the three-tab builder everywhere. Fix: add explicit `scope` to the Tier-1/2/3 seed dicts (or derive from tier in `seed_workflows.py`) + the existing upsert corrects rows on next deploy. Same patch should set `agent_registry_key: None` explicitly for the migrated three (C-6).

**C-6 — Stale `agent_registry_key` on the migrated three. [size: folded into C-5]**
Dev (and any env seeded pre-8c) still has keys on `wf_sys_month_end_close` / `ar_collections` / `expense_categorization` because the seed omits the field. Consumers witnessed: display-only (`workflows.py:69` badge) + fork-clears — execution does NOT dispatch on it, so impact is the misleading "Built-in implementation" badge + read-only click-through blocking the builder editor for three workflows that are in fact editable.

**C-7 — `seed_quotes` + `seed_saved_orders` crash on every deploy. [size: hours]**
`scripts/seed_quotes.py:112`, `scripts/seed_saved_orders.py:66` — `CompanyModule.module_key` / `.is_enabled`; the model has `module` / `enabled` → AttributeError at query build. Both run in the canonical seed runner's **warn-and-continue** tier, so every staging deploy logs a warning and their content has never seeded via the runner. Two-line fix + the seed-idempotency CI gate would have caught it if `scripts/seed_*.py` changes trigger it (they do — the gate exists; these predate it or slipped in a non-triggering commit — worth confirming the gate actually runs them).

**C-8 — AR `customer.current_balance` write-path gap. [size: 1 session, investigation-led]**
June catalog #6, still open: `ar_balance_reconciliation` (works) keeps auto-correcting stale denormalized balances — some AR write path doesn't maintain `current_balance`. Root cause never pinned. The monitor is the safety net masking it nightly.

**C-9 — AR aging `date − datetime` — still unpinned. [carry, needs staging traceback]**
Re-confirmed this session: canonical path (`agent_service.py:86,101,197`) is date−date, type-correct. Not reproducible from source; needs the operator's staging traceback pull to locate the actual caller. Do not size until pinned.

**C-10 — `quote_auto_expiry` / `quotes.customer_name` — PRESUMED RESOLVED, verify.**
`quotes.customer_name` exists in the at-head schema (witnessed dev, and the model at `quote.py:35`); the staging UndefinedColumn was the staging-behind-migrations condition, and staging now deploys at r123 with fail-loud migrations. Expect the error gone; confirm on the next staging log pull before closing.

## D. MISSING — proposed Planning items (PROPOSALS ONLY — nothing written to the Planning space)

The audit proposes; the operator curates into `manufacturing-map → Planning`. Suggested rows, in the priority the evidence supports:

| # | kind | proposed title | why / evidence | size |
|---|---|---|---|---|
| D-1 | workflow | **Fix statement payments (silent-zero) — C-1** | Flagship statements are numerically wrong today | 1 session |
| D-2 | workflow | **Vendor-bill rework: AP agent + financial reports — C-2+C-3** | One shared VendorBill field-mapping fixes a nightly crash + two silent-wrong reports; needs the rewrite-vs-retire call on the AP agent | 1 session |
| D-3 | workflow | **Reconciliation payment matching rework — C-4** | Matching is a no-op; customer leg is mechanical, vendor leg needs a model decision | 1 session |
| D-4 | feature | **Seed-omission patch: explicit scope + agent_registry_key in workflow seeds — C-5+C-6+C-7** | Cross-environment misfiles + two always-failing seeds; smallest arc on the list | hours |
| D-5 | feature | **Triage queues as a MoC card type** | The four accounting approval surfaces are invisible from the map; queues are where the human work actually happens | 1 session |
| D-6 | workflow | **Migrate the agent-eight (Phase 8f) — or explicitly retire some** | 8 accounting agents invisible outside the legacy dashboard; the 8b/8c template makes each ~1 session; triage which are September-relevant (unbilled_orders yes; 1099/year-end probably not) | 1 session each |
| D-7 | feature | **Scheduler shadow-fleet surfacing** | 13 accounting monitors fire nightly with zero visibility (the June P3 infra gap, now with a natural home: the map) | 1 session (scope first) |
| D-8 | task | **Wire the "Funeral Home Billing" task stub** | The one type=Accounting catalog task points at nothing; wire to wf_sys_statement_run mirror (or the D-1-fixed pipeline) + an End-of-Month schedule trigger | hours |
| D-9 | feature | **AR current_balance root cause — C-8** | Stop the nightly auto-correct masking | 1 session |

## BOUNDARY QUESTIONS — surfaced, not decided

**Q1 — Quotes/pricing: Accounting or Sales?** The map's only document today is Standard Quote, and `quote_auto_expiry` is in the accounting-ish scheduler fleet — but quotes are pre-revenue sales motion (quote → sales order → invoice). If area #2/#3 is "Sales & Orders," quotes/pricing/price-lists likely belong there, and this audit's quote items (C-10, Standard Quote row) transfer with it.
**Q2 — Payment processing vs payment accounting.** Stripe is configured-not-wired; POS/charge-account is a future add-on phase. Is "taking payments" in the Accounting area (it writes `customer_payments`) or its own future area? Affects where D-3's vendor-payment modeling decision lands.
**Q3 — Statement delivery.** Statement *generation* is Accounting; statement *delivery* rides the D-7 documents/delivery abstraction (`email.statement`) shared with every other communication. Map the delivery templates here (B-4) or in a Documents/Communications area?
**Q4 — Cross-tenant billing.** `cross_tenant_statement_service` (licensee-transfer billing chains) touches accounting but is architecturally cross-tenant network. Own area, or accounting?

## MoC-SLICE DELTA (summary of A vs B)

Mapped: 4 workflows + 1 widget + 1 document + 1 stub task. Unmapped but existing: 1 peer workflow (+2 excluded vertical ones), 1 widget, 9 documents, 4 triage queues (no card type), 8 agents, 13 scheduled jobs. **The map currently shows roughly the top quarter of the accounting area, and none of its approval surfaces.** The mapped quarter is the right quarter (the migrated, workflow-shaped core) — the gap is systematic, not random: everything not yet workflow-shaped is invisible.

---

## §T — TEMPLATE FOR AREAS #2..N (the reusable structure)

Per-area audit = one read-only session producing `docs/investigations/mfg_area_audit_NN_<area>.md`:

1. **Recon inputs (in order):** standing-rot catalog re-verified against current source (never trust prior status — items move) → local log check (note freshness limits) → dev-DB artifact inventory (workflows/mirrors, task catalog+triggers, triage queues, widget_definitions, document_templates, scheduled jobs, agents/services specific to the area) → the map's current rows for the area.
2. **Four lists:** A exists-and-mapped (with runtime-health column) · B exists-but-unmapped (with cheapest-mapping note) · C exists-but-broken (file:line witnessed at HEAD, ranked by user-visible damage, **silent-wrong outranks crash**, each sized hours/session/arc, repoint-vs-rework-vs-delete classified) · D missing (Planning-item proposals as a table: kind/title/evidence/size — never written to the Planning space by the auditor).
3. **Boundary questions:** surfaced with the evidence that raises them; not decided.
4. **Delta summary:** one paragraph — what fraction of the area the map shows, and whether the gap is systematic.
5. **Discipline:** every claim witnessed; "presumed resolved" is a status (with its verification step named); prior catalogs are leads, not facts; treat "may not exist / best-effort" comments around imports as smells (June addendum's masking-comment lesson); the audit PROPOSES Planning items, the operator curates them in.

## PROPOSED AREA SEQUENCE (#2..N)

Ordered by September-demo weight × observed rot density:

2. **Sales & Orders** (quotes → sales orders → invoicing handoff; absorbs Q1; `delivery_intelligence_service` order-import rot; Create Invoice/Send Statement mapping call)
3. **Production & Scheduling** (dispatch kanban, pours, scheduling board; `widget_data.py:496` production_log crash lives here)
4. **Delivery & Dispatch** (driver portal, routes, delivery confirmations; demo-visible)
5. **Safety & Compliance** (safety program gen already migrated; toolbox `inspection_record` dead path; OSHA/NPCA)
6. **Inventory** (inventory reconciliation agent unmigrated; receiving)
7. **CRM & Cross-Tenant** (company entities, funeral-home network, cross-tenant billing — absorbs Q4)
8. **Documents & Communications** (template families, delivery abstraction, email intake — absorbs Q3)

Extensions (Urn Sales etc.) audit within their host area or as a trailing #9 if signal warrants.

---

**STOP.** Read-only. No Planning items written (D-table is proposals). No code touched. Committed for operator review; the operator's moves from here: curate D-1..D-9 into the Planning section, answer Q1–Q4, pull the C-9 staging traceback + C-10 log confirmation when convenient, and point at the top Planning item to dispatch.
