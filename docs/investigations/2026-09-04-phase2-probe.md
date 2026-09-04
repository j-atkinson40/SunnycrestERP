# Phase 2 probe — the sibling does not answer, and the reason reframes the arc

**Date:** 2026-09-04 · **Read-only.** No sites edited. Phase 2 held.

The probe was `year_end_close`: 7 lacking against 1 covered, chosen as the
hardest sibling case on the reasoning that if one covered site answers seven,
siblings answer nearly everywhere.

**It answers one of seven.** And the six it fails to answer are all the same
shape, which turns out to be the arc's actual finding.

---

## 1. The probe's result

`year_end_close`'s single covered site establishes
`entity_type="inventory_item"`, `entity_id=item.id`.

| lacking site | is it an inventory item? |
|---|---|
| `yearend_inventory_value_zero` | yes — the sibling answers it |
| `yearend_budget_variance` | no |
| `yearend_no_depreciation` | no |
| `yearend_depreciation_irregular` | no |
| `yearend_accrual_no_reversal` | no |
| `yearend_no_accruals` | no |
| `yearend_retained_earnings_unavailable` | no |

**1 of 7.** Phase 2's premise — that a covered sibling establishes the agent's
subject vocabulary — does not hold here.

---

## 2. ⚠️ Why, and this is the finding

The 34 lacking sites are **not sites someone forgot to fill in.** They are sites
where an entity reference is the wrong shape for the subject. Two kinds:

**ABSENCE anomalies — the subject is a thing that does not exist.** Nine across
the seven partially-covered agents: `yearend_no_depreciation`,
`yearend_no_accruals`, `yearend_accrual_no_reversal`,
`yearend_retained_earnings_unavailable`, `yearend_inventory_value_zero`,
`vendors_not_reviewed_for_1099`, `missing_tax_ids_summary`,
`w9_tracking_not_implemented`, `expense_no_gl_mapping`.

You cannot pass `entity_id` for a depreciation entry that was never made. The
anomaly is precisely that the row is absent.

**AGGREGATE anomalies — the subject is a population or a period.**
`revenue_outlier`, `low_collection_rate`, `low_invoice_volume`,
`high_unmatched_ratio`, `unbilled_backlog_growing`, `budget_variance_significant`,
`budget_projects_loss`.

### The four zero-coverage agents confirm it

They are at zero because they write **nothing but** absence and aggregate
anomalies:

```
tax_package         missing_year_end_close · missing_1099_prep ·
                    months_not_closed · missing_tax_estimates
estimated_tax_prep  no_posted_ledger_activity · tax_estimate_rough ·
                    no_tax_rates_configured · no_tax_payment_tracking
budget_vs_actual    budget_no_comparison_basis · budget_variance_significant ·
                    budget_line_variance
annual_budget       budget_no_prior_year_data · budget_projects_loss
```

Not an oversight in four agents. **Four agents whose anomalies are not about
rows.** And every covered site across all twelve agents is single-entity —
invoice, customer, payment, vendor, order, inventory_item, vendor_bill_line. The
pattern is exact: entity-shaped anomalies got entity ids; non-entity-shaped ones
did not.

---

## 3. This is not a blocker — it is a vocabulary decision

⚠️ **`entity_type` and `entity_id` are `String` columns. They do not have to
reference a table row.** Nothing in the schema requires it; the convention that
they do is a convention.

So a subject can be `("expense_category", "Utilities")` or
`("tax_year", "2026")` or `("period", "2026-08")` — and the operator's own
category ruling already requires exactly this. **An expense category is not a
row in a table.** The ruling was right and it was already asking for a non-row
subject; nobody noticed because the one case looked like a special case.

It is also consistent with IDENTITY as landed, which says a composite is fine
when the subject genuinely is one, and which `tasks_due_today` already uses with
`subject_kind="user_day"`.

**So shape 2 survives.** What changes is what phases 2–3 actually do: not "fill
in the missing ids" but "decide what the non-row subjects are, and name their
kinds." That is authoring, not mechanical work, and it is the same batch
question for far more sites than phase 3 anticipated.

---

## 4. ⚠️ STOP — phases 2 and 3 merge, and the estimate moves

Per the arc's STOP line — *any call site whose subject differs from what its
siblings pass* — six of seven in the probe differ, so phase 2's premise fails at
its own opening measurement, exactly as the probe was designed to detect.

**Phases 2 and 3 collapse into one authoring phase**, because the same question
now covers most of the 34 rather than 14 of them. The estimate moves to **6**,
which the arc predicted as the phase-3-goes-wide case, and it moves **before the
session was committed rather than during it** — which is what the probe was for.

### The batch the operator needs to rule on

Three subject kinds appear to cover everything, offered as a starting vocabulary
rather than a recommendation:

1. **Entity** — an existing row. Already in use at all 30 covered sites.
2. **Absence** — the thing that should exist. Subject is what it *would have
   been about*: a period, a tax year, a category, a vendor.
3. **Aggregate** — a population over a scope. Subject is the scope itself:
   tenant + period, usually.

⚠️ The genuinely hard ones are where 2 and 3 overlap.
`vendors_not_reviewed_for_1099` is an absence *of a review* over an aggregate *of
vendors* — is the subject the tax year, or the vendor set? Answering that once,
for the batch, is what keeps the answers consistent; answering it per-site is how
four framings appear.

---

## 5. What is NOT in question

The ratchet from phase 1 holds regardless of how the vocabulary resolves — it
counts sites without a subject, and every one of these will acquire one. The
consolidation holds. Item 5 holds. Nothing in phase 1 depended on the subjects
being rows.

---

## 6. Method notes

- The probe was run before any site was edited, which is the whole point of
  choosing the hardest case as the opening measurement.
- Absence classification is by anomaly-type name (`no_`, `missing`,
  `unavailable`, `not_`, `zero`) and is a **heuristic on the name, not on the
  code**. `yearend_inventory_value_zero` may be about a real item with a zero
  value rather than an absence; verify per-site during the authoring phase.
  The four zero-coverage agents' classification does not rest on the heuristic —
  their types are absences on reading.
- No production access needed or used for this probe; it is entirely a source
  question.
