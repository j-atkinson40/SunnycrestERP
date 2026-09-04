# Phases 2–3 — one rule, 34 sites, 32 answers and 2 refusals

**Date:** 2026-09-04 · Merged authoring pass. Phases 2 and 3 collapsed at the
probe; this is the single pass they collapsed into.

The rule applied, from DECISIONS 2026-09-04:

> **The subject is what the END TRANSITION acts on.** Not what the anomaly is
> about. What, when done, makes it go away.

It replaced a three-way vocabulary (entity / absence / aggregate) that the probe
had proposed. The replacement was correct and the reason is worth recording:
that vocabulary described **conditions**, not subjects, and a taxonomy of
conditions invites a debate per site. One test applied per site does not.

**Result: 32 of 34 sites answered. 2 refused, and the refusal is a finding.**

---

## 1. What the rule did that the taxonomy could not

Three cases the probe had flagged as hard dissolved on contact.

**`vendors_not_reviewed_for_1099`** was the probe's stated worst case — an
absence *of a review* over an aggregate *of vendors*, so is the subject the tax
year or the vendor set? Asking what CLEARS it: reviewing the vendors for the tax
year. One act, therefore one subject, therefore the tax year. The question only
looked hard while it was being asked about aboutness.

**The single-entity sites stopped being a separate class.** Fixing that row
resolves it, so the row is the subject. They are not a category; they are the
case where the transition's target happens to be a row.

**`expense_no_gl_mapping`** was already ruled — map the category, so the category
is the subject. Under the rule it stops being a special case and becomes the
general rule appearing first.

---

## 2. The one guard that fired, and the one that did not

**TOO COARSE fired five times, and the discriminator is the anomaly TYPE.**

Three `month_end_close` sites — `revenue_outlier`, `low_collection_rate`,
`low_invoice_volume` — all resolve to acts bounded by the same accounting
period. Read carelessly that is three instances collapsing onto one subject with
three different acts, which is exactly what the guard forbids.

It is not, and the reason is structural. The supersede key from DECISIONS
2026-09-01 is `(provenance_kind, provenance_ref_type, provenance_ref_id,
event_kind)` — **`event_kind` is a separate component of the key.** The anomaly
type occupies that slot. So two anomalies of DIFFERENT types over the same
period are already two keys, and sharing a subject is correct rather than
collapsed.

⚠️ **The guard therefore bites on same-type instances only.** That is where it
actually fired, five times:

| site | why the coarse subject was wrong | subject taken |
|---|---|---|
| `budget_line_variance` | one instance per GL account, each its own act | `gl_account_period` = `acct:period` |
| `budget_variance_significant` | one per summary metric | `budget_summary_line` = `metric:period` |
| `yearend_budget_variance` | one per full-year metric | `budget_summary_line` = `metric:year` |
| `yearend_accrual_no_reversal` | one per accrual entry; each needs its own reversal | `journal_entry` = entry id |
| `inventory_large_count_adjustment` | one per count transaction | `inventory_transaction` = txn id |

**GENUINELY AMBIGUOUS never fired.** No site had two competing acts. It came
close once and did not survive scrutiny: `budget_no_prior_year_data` reads as
"backfill the year, OR enter the budget manually," but only the first makes the
warning stop — the second is advice on proceeding despite it. That is a
distinction the rule forces you to make, and it is the right one.

---

## 3. ⚠️ The two refusals are the same shape, and it is not ambiguity

Two sites resist the test, and neither is a Type B with competing resolutions.
They are worse and more interesting: **nothing the operator can do makes them go
away.**

| site | what would clear it |
|---|---|
| `estimated_tax_prep.tax_estimate_rough` | "Less than one full quarter of data available." The quarter fills up. Nobody acts. |
| `prep_1099.w9_tracking_not_implemented` | "W-9 receipt tracking is not yet implemented in Bridgeable." Bridgeable ships the feature. |

One waits on the calendar, one waits on the vendor. Neither has an end
transition, so under the rule neither has a subject — and that is the rule
working, not failing.

⚠️ **These are standing notices wearing an anomaly's shape.** An anomaly is a
thing someone decides about; a notice is a thing someone reads. They sit in the
same queue, they age the same way, and they will never resolve, so they
accumulate exactly the way `expense_no_gl_mapping` did — for a different reason
and with the same result.

**Held without subjects, deliberately, and marked in place at both call sites.**
The arc's own STOP line says inventing a subject is worse than stopping. A
fabricated subject here would key two permanent notices as though they were
resolvable decisions, which is the defect this arc exists to remove.

⚠️ **The ratchet ceiling is 2, not 0, and it must not be driven to 0 by
subjecting these two.** The comment on `MAX_SITES_WITHOUT_SUBJECT` says so.
The real question they raise — whether `agent_anomalies` is the right container
for a non-decision — is a disposition ruling, not this pass's call.

---

## 4. Subject vocabulary as it landed

Eight kinds, none invented for its own sake:

```
accounting_period       period-bounded acts        7 sites
fiscal_year             year-bounded acts         10 sites
tax_year                1099 / tax-payment acts    4 sites
budget_summary_line     metric:period              2 sites
gl_account_period       account:period             1 site
expense_category        the category               1 site
tax_rate_configuration  the tenant's tax settings  1 site
row subjects            inventory_item, inventory_transaction,
                        statement_run, journal_entry
```

**`_period_subject_id()` was consolidated onto `BaseAgent`.** It returns
`period_start:period_end`.

> ⚠️ **[CORRECTED 2026-09-04] TWO ERRORS IN THE PARAGRAPH THIS REPLACES.**
> Original wording: *"...rather than open-coded at six sites. It returns
> `period_start:period_end` and **raises** when the job has no period rather
> than returning a placeholder — a blank subject is indistinguishable from a
> legitimately absent one, which is the absent-signal shape.
> `AgentRunner.create_job` requires both dates, so it can only fire on a job
> created some other way, and that is worth hearing about."*
>
> **(1) Not six sites — 7 take the period as their subject kind, and the id
> helper is called at 9**, the extra two inside the `budget_summary_line` and
> `gl_account_period` composites. Six was a recollection, not a count, in a
> document about not inheriting figures.
>
> **(2) THE RAISE WAS A LIVE REGRESSION.** The reasoning was sound and the
> conclusion wrong, because "some other way" is the common way. Measured against
> production: `month_end_close`'s ONLY job there has a null period, as does 1 of
> 172 `cash_receipts_matching` jobs, and four job types are 100% null. It would
> have aborted the step at its next run — **removal before the callers comply,
> inside the fix for exactly that mistake.** Now returns `tenant_books` / tenant
> id, which is the honest reading (a job naming no period has no period-bounded
> act) and still supersedes. See `2026-09-04-anomaly-subject-phase4.md` §5.

⚠️ It is deliberately NOT the job id. A run-scoped subject is what IDENTITY
refuses by name, and it is the mechanism behind the 1,825 duplicates.

---

## 5. Two things found in passing

**`tax_package` constructs an anomaly type name.** Line 284:
`anomaly_type=f"tax_package_missing_{agent_type}"`. This is the constructed-name
shape, and it is directly relevant to **phase 4** — the three unlocated types
(`uncategorized_expense`, `invoice_severely_overdue`, `invoice_overdue`) were
reported as a failed literal lookup precisely because a writer building its type
name evades a literal search. Here is a writer that does exactly that,
confirming the mechanism is present in this codebase rather than hypothetical.
It does not produce those three names, so it is not the answer — it is evidence
that phase 4's method (enumerate writers, do not search harder) is the right one.

**`base_agent._make_anomaly`'s docstring carried the wrong figure.** It said
"45 of 75 call sites," the pre-correction numbers. The correction had landed in
the audit, the arc scope, and the ratchet, and this fourth copy was missed —
a fourth document carrying the description rather than the population. Corrected
in place with the original noted.

---

## 6. Method notes

- Every site read individually with surrounding context before assignment. No
  site was assigned from its type name.
- The ratchet was **break-tested after lowering**: removing one `entity_id` turned
  both `test_the_ratchet_may_only_shrink` and `test_the_ceiling_is_not_stale`
  red and named the site. A ceiling lowered without that check is a ceiling that
  might already be loose.
- Site count re-measured, not inherited: 64 call sites, 62 with a subject, 2
  without.

---

## 7. ⚠️ A measurement error I made during this pass, and what it uncovered

I ran a broader command than the gate — the whole `tests/` tree — and then
checked whether any failure touched the agents by grepping an output I had piped
through `tail -30`. The "zero mentions" I read back was a property of the
truncation, not of the run. **Enumeration defeated by presentation, CLAUDE.md
§11, committed while holding the entry.** Re-run untruncated, the answer happened
to be the same, which is luck rather than vindication.

Measured properly:

| | |
|---|---:|
| test files in `backend/tests/` | 426 |
| files in the gate manifest (`tests/ci_gate.txt`) | 164 |
| whole-tree result | 6,279 passed · 45 failed · 137 errors |
| distinct failing files | 28 |
| failing files that are IN the gate | **1** |
| failures referencing agents / `_make_anomaly` / `entity_id` | **0** |

**The gate is clean at 2,281 passed / 0 failed, identical to the pre-pass
baseline.** Nothing here is caused by this pass.

⚠️ **The one gate-manifest file among the 28 is `test_payment_posting_ar2.py`,
and it is order-coupled, not broken.** It passes 20/20 in isolation and 20/20
inside the gate; it errors 20/20 under the whole-tree run. The first error in
that run is `httpcore.ConnectError: [Errno 61] Connection refused` — tests that
require a live server — so the broad-tree red is a mix of environment-dependent
suites and the shared-DB order coupling that R-7-δ already canonised.

**The observation worth keeping is the ratio, and it is a magnitude claim of the
kind §11 warns about.** The gate covers 164 of 426 files. The other 262 are not
"passing" — they are unmeasured, and 182 red results live in there. Every
"backend gate green" in this arc's commits, mine included, is a statement about
38% of the test files. That is not wrong, and it is narrower than the phrase
sounds. Establishing which of the 262 are genuinely broken versus merely
environment-dependent is its own piece of work and is not this arc's.
