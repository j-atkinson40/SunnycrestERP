# D-3 — Reconciliation Rework (+ C-2 rider): Phase 0 findings

**Date:** 2026-07-16 · **Base:** `125ceeba` · Per `mfg_area_audit_01_accounting.md` D-3 + C-2 (operator's call: REWRITE).

## 1. Both forks resolve from model reality — no STOP

- **Bank-side substrate EXISTS and is complete**: `ReconciliationRun` (statement date/balances/counts/status) + `ReconciliationTransaction` (statement lines with `amount`, `transaction_date`, `transaction_type` credit/debit, `reference_number`, and DURABLE match state: `match_status`, `match_confidence`, `matched_record_type/id`, reviewer stamps) + `ReconciliationAdjustment`. The CSV import + column-mapping + review flow are all real. Only the **candidate loading** was dead.
- **The vendor-payment "open decision" closes before it opens**: `VendorPayment` (+`VendorPaymentApplication`) already exists — `total_amount`, `payment_date`, `reference_number`, `deleted_at` — the symmetric twin of CustomerPayment. The audit's missing `BillPayment` was only the dead NAME. Option (b) is already built; no migration, no deferral.
- **The vendor list was never wired in at all**: pre-fix, `bill_payments` was loaded (dead) and then NEVER USED by the matching loop — only customer payments entered the amount lookup. The vendor side wasn't just broken; it was absent.

## 2. The fix shapes

- **Candidate loading against the real models, LOUD**: `CustomerPayment` + `VendorPayment`, soft-deletes excluded, `payment_date ≤ statement_date` (end-inclusive at day granularity), `≥ period_start` when the run carries one (it's nullable — filter only when present, never invent a window).
- **Direction-honest pools** (what the data carries, not an invented heuristic): a `credit` statement line (deposit) matches customer payments; a `debit` (withdrawal) matches vendor payments; an untyped line consults both. `transaction_type` is a real column the importer already writes.
- **The matching algorithm itself is UNTOUCHED** (pattern recognition → exact-amount + ≤5-day proximity with confidence tiers → reference match). It was never the bug.
- **Two date−datetime landmines defused (the C-9 class, pre-empted)**: payment/bill dates are timestamptz; statement dates are DATE. A naive repoint would have crashed at `(txn.transaction_date − payment_date).days` and `(bill.due_date − today).days`. Both normalized to `.date()` at the comparison.
- **C-2 rider — full field mapping** (the agent's purpose maps 1:1; no STOP): `Bill.tenant_id→VendorBill.company_id` · statuses `open/partial/overdue → pending/approved/partial` (overdue is not a status; it's `due_date` past — the agent's own day-math already says so) · `bill_number→number` · `balance_due→balance_remaining` · `vendor.vendor_name / vendor_name_raw → resolve_vendor_name(bill.vendor)` (the ap_aging resolver, consistency). Alert shapes preserved verbatim (overdue / due-in-3 / 14-day digest / Monday payment-run suggestion). The job-level try/except STAYS — that's the agent framework's loud-record contract (`_complete_job(error)`), not a silent-zero.

## 3. Sibling scan — the audit's count holds

`routes/reconciliation.py` has three try/excepts: the two dead-import swallows (fixed here) + the per-row CSV-parse skip at import time, which already logs each skipped row — the defensible best-effort class, untouched. No STOP.
