# Backend Health Triage — Phase 0: Failure Catalog (read-only)

**Date:** 2026-06-26 · **HEAD:** `c89a039` · **Read-only** — no code, no migration, no commit.
**Source of truth:** local source + `bridgeable_dev` schema (at-head: `r111_moc_pages` = heads). Staging logs are the symptom source; local source/schema is ground truth.
**Method:** confirmed each of the six sampled failures against source/schema, then swept for the rest. Every claim witnessed; the dispatch's hypotheses verified both directions (two were refuted — see #1↔#3 and #4).

---

## HEADLINE — two findings that most change the plan

1. **THE "SCHEMA DRIFT" (item 3) IS NOT A SCHEMA ARC. It is "staging didn't migrate" — operational, not modeling.** Witnessed: the ORM matches the local at-head schema **exactly** — zero tables missing, zero columns the ORM expects that the DB lacks (full `Base.metadata` vs `information_schema` diff). And `quotes.customer_name` IS in the at-head DB. So there is **no model-vs-migration drift anywhere**; *all* staging schema drift = **staging's DB is behind the migration chain**. The fix is not writing migrations (they're correct and apply cleanly); it is getting staging's `alembic upgrade head` to actually complete. **This DE-escalates the arc** the dispatch feared item 3 would inflate. Root cause lives behind staging's `alembic current` + deploy logs (Railway access — same domain as the open slow-boot/deploy-failure finding); strongly suggests the deploy chain isn't reaching head (failed migration, multiple-heads refusal, or aborted deploy).

2. **THE FAILURE SURFACE IS LARGER THAN SIX — chiefly dead imports.** The "two dead modules" are actually **12 non-existent modules across ~18 import sites**, all orphans of the documented model renames (orders→sales_orders, bills→vendor_bills, payments→customer_payments). All are in-function (lazy) imports → each is a *contained* failure for its endpoint/agent, not a module-load crash. Triage should be **phased**, not one pass.

**And two dispatch hypotheses are REFUTED by source (the epistemic note paying off):**
- **#1 is NOT a boot crash and does NOT connect to #3.** The `created_by="system"` invoice insert is in `draft_invoice_service` (called by the *scheduled* `draft_invoice_generator` job, in-process post-startup), not in the `railway-start.sh` migration/seed chain. No seed calls it. So it cannot abort the deploy or leave staging behind. It is a recurring *scheduled-job* failure, independent of the migration problem.
- **#4 is NOT reproduced from source.** The canonical AR-aging path is `date.today() - invoice.due_date` (date−date, type-correct). The reported `date - datetime` error is not present in the obvious path; it needs the staging traceback to pin (likely data-specific or a different caller). Lower severity than catalogued.

---

## THE SIX SAMPLED FAILURES — confirmed / corrected (witnessed)

### #1 — draft_invoice_generator: `created_by="system"` → FK violation. **CONFIRMED (mechanism); reclassified (not boot).**
- `app/services/draft_invoice_service.py:269` and `:375` call `sales_service.create_invoice_from_order(db, tenant_id, "system", order.id)` — the 3rd arg becomes `invoices.created_by`.
- Witnessed: `invoices.created_by` is an **FK → users**; there is **no `users` row `id='system'`** → INSERT FK-violates. The job fails every run.
- **Class size: contained.** Only these 2 sites pass a bare `"system"` actor (grep of `[,(] 'system' [,)]` across `app/` = these two). Not a platform-wide pattern.
- **Trigger:** the `draft_invoice_generator` scheduled job (`scheduler.py:213`), NOT the boot/seed chain (no seed calls the draft path). So it does NOT abort deploys / cause #3.
- **Fix:** seed a real `system`/platform actor `users` row, OR pass a real actor / `None` (column is nullable). No migration. **Verify on fix:** reproduce by running `draft_invoice_generator` against a tenant with eligible orders.

### #2 — dead imports. **CONFIRMED, and 6× larger than sampled.**
12 non-existent `app/models/*` modules imported (all in-function → contained):
| Module (missing) | Site(s) | Likely correct target |
|---|---|---|
| `bill` (Bill) | `agent_service.py:333` (run_ap_upcoming_payments), `financial_report_service.py:109,340` | `vendor_bill.VendorBill` |
| `reconciliation` (ReconciliationAdjustment) | `proactive_agents.py:352` (run_uncleared_check_monitor) | reconciliation model (renamed) |
| `payment` (Payment) | `reconciliation.py:272`, `financials_board.py:75`, `statement_generation_service.py:56,106` | `customer_payment.CustomerPayment` |
| `bill_payment` (BillPayment) | `reconciliation.py:282` | vendor-bill-payment model |
| `order` (Order) | `delivery_intelligence_service.py:156` | `sales_order.SalesOrder` |
| `inventory` (InventoryItem) | `widget_data.py:534`, `command_bar_data_search.py:652` (`# type: ignore`!) | `inventory_item.InventoryItem` |
| `production_log` (ProductionLogEntry) | `widget_data.py:496` | renamed model |
| `safety` (SafetyIncident, SafetyInspection) | `widget_data.py:644` | safety models (split) |
| `statement_run` (StatementRunItem) | `statements.py:169` | `statement` model |
| `gl_mapping` (TenantGLMapping) | `early_payment_discount_service.py:264` | renamed model |
| `inspection_record` (InspectionRecord) | `toolbox_suggestion_service.py:163` | renamed model |
| `agent_alert` (AgentAlert) | `operations_board_service.py:448` | renamed model |
- **Impact:** each path 500s/errors only when exercised. Two are *scheduled agents* that fail every run: `ap_upcoming_payments` (bill) + `uncleared_check_monitor` (reconciliation). The rest are endpoints/widgets/services (financials board, statements, widget data, command-bar search, etc.) that error on demand.
- **Fix:** repoint each import to the renamed module/symbol; verify the symbol exists at the target. No migration. (The `# type: ignore` at `command_bar_data_search.py:652` is a smell — it was suppressing the type error on a dead import.)

### #3 — `quotes.customer_name` "schema drift". **CONFIRMED present locally → staging is BEHIND (not model drift).** See HEADLINE #1. Full ORM-vs-DB diff = zero drift. Operational fix (staging migration application), not a schema arc. **Sizes the arc DOWN.**

### #4 — AR aging `date - datetime`. **NOT REPRODUCED from source.**
- `agent_service.py:86` `now = date.today()`; `:101` `(now - inv.due_date).days`; `:197` `(date.today() - invoice.due_date).days` — `due_date` is a DATE column → date−date, type-correct. No `due_datetime` arithmetic in the agents.
- **Verdict:** the obvious path is correct; the logged error is data-specific or a different caller. **Needs the staging traceback line to pin.** Lower severity than sampled (not a blanket type bug).

### #5 — approval email `'User' has no attribute 'role'`. **CONFIRMED, single site.**
- `app/services/agents/approval_gate.py:80`: `if admin.role and admin.role.slug in ("admin","accounting")`. `admin` is a `User`; the `User` model has **`role_id` + a `role_obj` relationship**, **no `.role`** → `AttributeError` every time the approval gate emails admins (the every-15-min log spam).
- **Not a class:** the only other `.role` on a user-ish var is `deps.py:344` `platform_user.role` — and `PlatformUser` **does** have a `role: Mapped[str]` column (`platform_user.py:24`), so that one is VALID. #5 is one site.
- **Fix:** `admin.role` → `admin.role_obj` (2 references on the one line). No migration.

### #6 — AR balance drift `stored=0.00 vs calculated=4350.00`. **The monitor is WORKING — real data-integrity finding.**
- `proactive_agents.py:438` `run_ar_balance_reconciliation`: `calculated` = open-invoice total (`:457`); `stored` = `customer.current_balance` (`:468`); logs the drift (`:473`); **auto-corrects `customer.current_balance = calculated` (`:480`)** + raises an alert (`:490`).
- **Verdict:** not a monitor bug — it correctly detected that a customer's denormalized `current_balance` was stale (0) vs $4,350 of open invoices, fixed it, and alerted. **Escalate the ROOT CAUSE:** some AR write path creates/updates invoices without maintaining `customer.current_balance`. That's the real finding (a denormalization-maintenance gap); the monitor is the safety net, not the bug.

---

## THE BROADER SURFACE (what the window didn't show)

**Scheduled agents (`scheduler.py` `JOB_REGISTRY`, ~17 jobs).** Confirmed states:
- `draft_invoice_generator` → **#1** (system FK, fails every run).
- `ap_upcoming_payments` → **dead `bill` import** (fails every run).
- `uncleared_check_monitor` → **dead `reconciliation` import** (fails every run).
- `ar_balance_reconciliation` → **#6** (works; surfaces real drift).
- `ar_aging_monitor` → #4 (source type-correct; logged error unpinned).
- Collections/approval flow → **#5** (User.role in the approval email).
- **Not yet individually static-checked (recommend in fix-phase):** `network_readiness`, `discount_expiry_monitor`, `payment_pattern_enrichment`, `reorder_suggestion`, `receiving_discrepancy_monitor`, `balance_reduction_advisor`, `missing_entry_detector`, `tax_filing_prep`, `financial_health_score`, `cross_system_synthesis`, `network_snapshot`. The dead-import sweep (12 modules) covers their import-failure risk; a per-agent run against `bridgeable_dev` would confirm query/schema health (none surfaced new dead `app.models.*` imports beyond the 12).

**Runtime-health gap (the durable infra finding).** None of these surface anywhere: scheduled-job failures are caught per-job and logged to stderr (`_run_per_tenant` swallows + logs), CI is green (it doesn't run the agents), and there's no startup self-test or agent-failure health signal. So a job can fail on every fire for months invisibly (exactly what happened). **Recommendation (scope, don't build here):** (a) each scheduled job records success/failure + last-run to a surfaced table or `/api/health`-adjacent endpoint; (b) a startup self-test that imports every agent + dry-checks its core query against the live schema, failing loud on a dead import or missing column; (c) cross-reference the open staging slow-boot/deploy-failure finding (same Railway domain as #3). Re-auth `railway login` so #3's staging-side diagnosis can be done from the CLI.

---

## SEVERITY-RANKED FIX PLAN (triage phases)

**P0 — service-down / query-corrupting (do first):**
- **#3 staging-behind migrations** — operational, NOT a migration to write. Diagnose staging's `alembic current` + deploy logs (Railway); get `alembic upgrade head` to complete on staging. Likely entangled with the slow-boot/deploy-failure infra item — fix together. *No migration authored; this is a deploy fix.*
- **#1 draft_invoice "system" FK** — seed a `system` actor `users` row (or pass a real/`None` actor at the 2 call sites). Stops the draft-invoice job crashing every run. *No migration (data seed or code).* 

**P1 — contained failures (each path errors when run):**
- **#2 dead imports (12 modules / ~18 sites)** — repoint each to the renamed module/symbol; verify each target exists. Prioritize the 2 scheduled agents (`ap_upcoming_payments`, `uncleared_check_monitor`) — they fail every fire. *No migration.* Phaseable by service.

**P2 — loud but non-fatal:**
- **#5 approval_gate `admin.role` → `admin.role_obj`** (1 line, 2 refs). Stops the every-15-min log spam + lets approval emails send. *No migration.*
- **#6 AR `current_balance` drift** — the monitor works; investigate + fix the *write path* that leaves `current_balance` stale (the root cause), separately. *Likely no migration; a service-logic fix.*
- **#4 AR aging date error** — pull the staging traceback to pin the exact caller (source's canonical path is type-correct); fix once located. *Probably no migration.*

**P3 — durable infra (recommendation, separate small arc):** agent-failure surfacing + startup self-test (above). This is what made all of the above invisible; without it, the next regression hides the same way.

**Migration count for the whole triage: likely ZERO.** The schema is consistent (ORM = at-head). Every fix above is code, a data seed (the `system` user), or operational (staging migration application) — not schema authoring. That is the single most plan-shaping fact: **this is a code/deploy triage, not a schema arc.**

---

**STOP.** Read-only; not committed (operator reviews; fixes dispatch as ranked phases). Scope honesty: #1/#2/#3/#5/#6 confirmed with witnessed source+schema queries (FK introspection, full ORM-vs-DB column diff, import-site enumeration, monitor-logic read). #4 explicitly NOT reproduced — flagged needs-traceback rather than asserted. The two facts only staging access can add — *why* staging is behind (#3) and the #4 traceback — are named as the operator's Railway-side pulls; neither changes the catalog's shape (the schema is provably consistent; the failure set is code/deploy, not schema).

---

## ADDENDUM (2026-06-26) — Phase 1 fixes + COMPLETE dead-import classification

**Phase 1 shipped the three VERIFIED-CLEAN fixes** (held for review): P0 draft-invoice `"system"`→`None` (nullable attribution, matching create_vault_order); P1 `uncleared_check_monitor` import repoint (`reconciliation`→`financial_account.ReconciliationAdjustment`, fields verified); P2 `approval_gate` `admin.role`→`admin.role_obj`. Each witnessed (the agent *runs*, the invoice *persists* with NULL actor, `role_obj` resolves). No migrations.

**Then the per-site classification (read-only) — "12 dead imports" is THREE different problems.** Verify-first (scope-col + field-existence + wrap-status per site) splits the remaining sites:

### CLEAN REPOINT (model renamed/moved; every field the site uses exists on the target) — safe, mechanical
| Site | Symbol → target | Crashes? | Note |
|---|---|---|---|
| `proactive_agents.py:352` | reconciliation → `financial_account.ReconciliationAdjustment` | (was crash) | **DONE in Phase 1** |
| `widget_data.py:534` | inventory → `inventory_item.InventoryItem` | **CRASH** (unwrapped) | company_id/is_active/quantity_on_hand all present |
| `widget_data.py:644` | safety → `SafetyIncident` | **CRASH** | company_id/status present |
| `statements.py:169` | statement_run → `statement.StatementRunItem` | **CRASH** | statement_run_id present |
| `command_bar_data_search.py:652` | inventory → InventoryItem | swallowed | `# type: ignore` smell; clean target |
| `operations_board_service.py:448` | agent_alert → `agent.AgentAlert` | swallowed | import-name only |
| `early_payment_discount_service.py:264` | gl_mapping → TenantGLMapping (`tenant_gl_mappings`) | swallowed | tenant_id/platform_category — confirm at repoint |
| `financials_board.py:75` | payment → `customer_payment.CustomerPayment` | swallowed | uses only company_id/payment_date (both present) |

### STALE LOGIC (target exists but the site queries fields it LACKS — the `bill` trap) — needs query REWORK, not a repoint
| Site | Symbol → plausible target | Mismatch (witnessed) |
|---|---|---|
| `agent_service.py:333` (run_ap_upcoming_payments) | bill → VendorBill | `Bill.tenant_id` (VendorBill=company_id); status `open/partial/overdue` (actual: `paid/approved`) |
| `financial_report_service.py:109,340` | bill → VendorBill | `Bill.tenant_id` (company_id) |
| `reconciliation.py:272` | payment → CustomerPayment | `Payment.tenant_id` (customer_payments lacks tenant_id) |
| `statement_generation_service.py:56,106` | payment → CustomerPayment | `Payment.amount` (customer_payments has no `amount` column) |
| `delivery_intelligence_service.py:156` | order → SalesOrder | `Order.order_area` + `Order.scheduled_delivery_date` (sales_orders lacks both) |
| `widget_data.py:496` | production_log → ProductionLogEntry | **CRASH** + `ProductionLogEntry.company_id` (table has `tenant_id`, not company_id) |

### DEAD PATH (no valid target model exists) — needs DELETE (or feature decision), not a repoint
| Site | Symbol | Finding |
|---|---|---|
| `reconciliation.py:282` | bill_payment → BillPayment | **No model exists** (no `*BillPayment`); `try/except`-swallowed → silently dead |
| `toolbox_suggestion_service.py:163` | inspection_record → InspectionRecord | **No model exists** (only `QCInspection`/`SafetyInspection`, different); swallowed |

### THE PATTERN behind P1 (capture): **the dead imports are a map of half-finished migrations.**
Each STALE site is a model that was *replaced* (bill→VendorBill, payment→CustomerPayment, order→SalesOrder) where the rename swept the model but left consumers stranded against the *old* schema — and `try/except` swallowed the failure so nothing surfaced it. This predicts where else to look (any consumer of a renamed financial model) and is exactly what the P3 runtime-health surfacing would have caught the day the rename landed. The DEAD paths (bill_payment, inspection_record) are models that were *removed*, leaving swallowed import attempts that silently no-op a feature.

**Sub-pattern — masking comments (the camouflage layer).** The renames didn't just orphan imports; they left behind comments that actively *misdescribed* the orphans as defensive code. `command_bar_data_search.py:650` carried `# Try InventoryItem model — may not exist in all environments` + a bare `# type: ignore` on the dead import — a dead import dressed up as an environment-robustness guard, so it read as *intentional* rather than *broken*. This is the same family as the `try/except`-swallowed sites: a failure wearing the costume of a handled edge case. The cost is that the next reader re-infers a robustness that was never real and leaves the dead path alone. **Fix discipline (applied in P2):** kill the masking comment along with the repoint — the corrected comment should state what the model actually is, so the camouflage doesn't regenerate. When auditing for the remaining stale/dead sites, treat "may not exist / optional / best-effort" comments around a model import as a *smell*, not a reassurance — verify the model against the current schema rather than trusting the comment.

### Recommended next dispatch (fully scoped):
- **Clean repoints (7 remaining):** mechanical; prioritize the 3 **crashing endpoints** (`widget_data.py:534`/`:644`, `statements.py:169` — they 500 on hit). Verify each field at repoint (the mapping is right per this table, but confirm at the edit).
- **Stale rework (6 sites):** DOMAIN CALLS — is `run_ap_upcoming_payments` worth rewriting against VendorBill's real schema, or is AP-upcoming a dead feature? Same for the payment/order/production_log queries. Each needs a rewrite-vs-delete decision.
- **Dead delete (2 sites):** remove the swallowed dead imports (bill_payment reconciliation, inspection_record signal), or decide the feature is wanted and model it.

