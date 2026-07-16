# D-2 — Vendor-Bill Rework: Phase 0 findings (payables semantics)

**Date:** 2026-07-16 · **Base:** `1e2a7b7e` · Per `mfg_area_audit_01_accounting.md` D-2 (C-3).

## 1. The fork resolves: a REAL payables substrate exists

- **`VendorBill`** (`vendor_bills`): `bill_date` + `due_date` (both NOT NULL — aging-from-due-date is the model's own answer, no ambiguity), `total`, **`amount_paid`** (+ `balance_remaining` property) — partials are first-class; statuses `draft|pending|approved|paid|partial|void`; soft-delete `deleted_at`; vendor FK.
- **`VendorBillLine`**: `amount` + **`expense_category`** — the real category dimension (the same one the expense-categorization agent writes). Line sums may be less than `bill.total` (tax lives on the bill).
- **`VendorPayment` + `VendorPaymentApplication`**: the AP mirror of customer payments; `amount_paid` is the maintained denormalization.
- **A real AP aging service already exists**: `ap_aging_service.get_ap_aging` — due-date buckets (current/1-30/31-60/61-90/90+), `balance_remaining` (partials handled), statuses `pending|approved|partial`, soft-deletes excluded. The dead `financial_report_service.get_ap_aging_report` is a **duplicate dead surface** over the same question.

**No STOP:** substrate exists; aging semantics are forced by the model (age from `due_date`; a bill due exactly as-of is `current` — days_past ≤ 0).

## 2. The fix shapes

- **AP aging report → DELEGATE to the real service** (zero duplication, the D-1 adapter spirit): `get_ap_aging_report` keeps its response contract verbatim (`vendors[{…days_1_30…}]`, `totals`, `as_of_date`, `vendor_count` — its consumers are the /reports route + the audit-package bundle) and maps from `get_ap_aging`'s rows. `as_of: date` → midnight-UTC datetime for deterministic day counts.
- **Expense rollup → real lines, real categories**: `_sum_by_gl_type("expense")` sums `VendorBillLine.amount` grouped by `expense_category` (uncategorized → "General Expenses"), bills filtered `status ∉ (draft, void)`, `deleted_at IS NULL`, `bill_date` in period end-exclusive (the D-1 boundary discipline). The tax/uncategorized remainder (`Σ bill.total − Σ lines`) lands as an honestly-labeled remainder row so **the rollup ties to bill totals exactly** — the independent cross-check property.
- **The dead 0.6 COGS heuristic is REMOVED, not preserved**: it never executed (the swallow fired first — cogs was ALWAYS `[]` in observed behavior), so removal changes nothing observed while deleting a fabricated ratio. COGS returns `[]` honestly until a real COGS dimension exists — flagged as a known P&L limitation, not invented.
- **Both swallows KILLED**: module-level imports of the real models; a report that cannot compute raises (route 500s — loud). `_log_run` continues to record successful runs.

## 3. Sibling scan (STOP check: more than the audit counted — surfaced)

`financial_report_service.py` carries **six** try/except blocks, not the audit's two:
- Lines 109 + 340: the two money-math silent-zeros — **fixed in this session** (the D-2 scope).
- Lines 220/237/251/264: `run_health_check`'s four per-check swallows — **a different, defensible class**: advisory audit findings where one broken check shouldn't kill the rest (best-effort is the intended semantic). NOT money math; NOT reworked. Flag-level fix applied: each swallow now logs a WARNING (a permanently-broken check becomes visible instead of silently absent). Full rework deferred.

## 4. Callers + stale artifacts

- Callers: `routes/reports.py` (the AP-aging endpoint + the report-bundle builder) and the income statement (report 1) via `_sum_by_gl_type` (P&L cogs+expenses; comparison-period paths too). The pre-fix P&L overstated profit by ALL vendor-bill expenses.
- Persisted artifacts: `_log_run` stores run METADATA only (params + row_count) — report outputs are never persisted, so there are no stale wrong-numbered artifacts to supersede. Dead-era `ReportRun` rows (row_count 0) are honest history.
- The AP agent (`agent_service.run_ap_upcoming_payments`, the nightly ModuleNotFoundError) remains **out of D-2's scope by dispatch** — its rewrite-vs-retire is still the operator's open call (audit C-2).
