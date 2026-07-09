# D-1 — Statement Payments Rework: Phase 0 findings (payment-model semantics)

**Date:** 2026-07-09 · **Base:** `14f7c70c` · Per `mfg_area_audit_01_accounting.md` C-1.

## 1. Where the money lives

- **`CustomerPayment`** (`customer_payments`): `total_amount` = the check amount; `payment_date` (timestamptz); `customer_id` + `company_id` direct; **soft-delete via `deleted_at`** (must be filtered — the dead code never did).
- **`CustomerPaymentApplication`** (`customer_payment_applications`): `amount_applied` per invoice; one payment → many invoices (full or partial). **Applications carry NO date of their own** — the payment's `payment_date` governs.
- **Unapplied credit** exists implicitly: `total_amount − Σ amount_applied`.
- Write path (`sales_service` record-payment): creates payment + applications, bumps `Invoice.amount_paid`, flips status paid/partial. So `Invoice.amount_paid`/`status` are **as-of-now** denormalizations.

## 2. The honest period query (ambiguity resolved from the models)

“Payments in this period for this customer” = **Σ `CustomerPayment.total_amount` where `payment_date` falls in the period** (`deleted_at IS NULL`). Application-date attribution is not even representable (no date on applications), and the payment-date reading is what a customer expects: the check they sent this month appears on this month’s statement, regardless of which invoices it settled. A payment received this period applied to a prior-period invoice **shows as a period payment** — and stays consistent because of §3.

## 3. The double-count hazard the audit didn’t list (fixed with C-1)

The old opening balance was `Σ (total − amount_paid)` over pre-period invoices with **current** status/`amount_paid` — a point-in-time-now number. Once `payments_total` is real, an in-period payment applied to a pre-period invoice would be counted twice (opening already shrunk by it, then subtracted again) — e.g. a $1,000 May invoice paid June 15 would produce a spurious −$1,000 June closing. Fix: **opening reconstructed as-of-period-start**:

```
opening = Σ Invoice.total          (invoice_date < period_start, status not excluded)
        − Σ amount_applied         (joined: invoice as above AND payment_date < period_start, payment not deleted)
```

Consistency proof: `closing = opening + invoices_total − payments_total` = Σ invoice totals (≤ end) − Σ applications from payments dated < end − unapplied in-period credit = true outstanding as of period end, net of open credits. Hand-verified in the assembly test.

## 4. Decisions taken in the rework

- **Excluded invoice statuses** = `draft`, `void`, `write_off` — for BOTH opening and in-period charges. (Old in-period query had NO status filter: draft invoices inflated `new_charges`. Behavior change, deliberate: drafts/voids/write-offs never belong on a customer statement.)
- **Boundary honesty**: `invoice_date`/`payment_date` are timestamps; period bounds are dates. Old `<= period_end` excluded intraday period-end activity; old post-cutoff flag `> period_end` mis-flagged a same-day-as-cutoff payment as “after cutoff.” Rework compares end-exclusive (`< period_end + 1 day`) everywhere.
- **Loud failure**: no `try/except → Decimal(0)` anywhere in the money math. Module-level imports of the real models. If statement math raises, `generate_statement_run` rolls back (no statement rows), records a `status="failed"` `StatementRun` row (the vocabulary already exists — approval_gate checks `status not in ("draft","failed")`), and **re-raises**. A wrong money number is worse than no statement.
- **Regeneration**: `uq_statement_run_period` means wrong statements do NOT regenerate naturally — the first (wrong) run owns the period forever. Rework: generation **supersedes** an existing same-period run that is still pre-send (`draft`/`in_review`/`failed`, `sent_count = 0`) — deleting it and its items — and **refuses loudly** (clear error, not a raw unique violation) if the period’s run is `approved`/`sending`/`sent`. One post-fix run therefore replaces any stale wrong-numbered draft; rehearsal re-runs work.

## 5. Sibling scan (same service, same pass)

Exactly **2** `try/except → default` blocks in `statement_generation_service.py` — the payments sum (`:55`) and the post-cutoff flag (`:105`). Both are the dead-payment sites; both fixed in this pass. Nothing else in the file confidently defaults. Remaining deliberate stub: `credits_total: 0` (no credit-memo model exists; unapplied payment credits already reduce closing via §2/§3 math) — left as-is, flagged.

## 6. Callers (all four inherit the service fix)

- `statements.py` API + `invoice_statement_adapter` (wf_sys_statement_run): propagate the raise → 500 / WorkflowRun failed. ✔ loud.
- `month_end_close_agent` step 5: calls `calculate_statement_data` directly for pre-approval analysis → a raise fails the agent step → AgentJob failed. ✔ loud.
- `approval_gate._trigger_statement_run`: catches exceptions, records `statement_run_error` in the job payload, continues the approval. That is a **swallow-with-record**, not a silent-zero — the failure is operator-visible in the job report. No caller depends on wrong numbers; no STOP condition met.

## 7. Stale artifacts

Statements are never seeded (only `seed_full_year_e2e` *deletes* them); wrong rows come from live generation. Dev: 5 `customer_statements`, all `payments_received = 0.00`. Staging carries similar residue from rehearsals/agent runs. §4’s supersede-on-regenerate is the handling: the first post-fix run for a period replaces the stale pre-fix draft. **Operator note:** any staging period whose run is already `sent`/`approved` would refuse regeneration — none expected (demo tenants don’t send), but if Act III’s period is occupied by an approved run, delete it once on staging.

## 8. D-3 pattern credit

`sum_customer_payments_in_period` + the applications⋈payments⋈invoices join in `_opening_balance_as_of` are the canonical `CustomerPayment` read patterns. D-3 (reconciliation matching rework) reuses exactly this read (payments by `company_id` + `payment_date` window + `deleted_at IS NULL`, amounts from `total_amount`).
