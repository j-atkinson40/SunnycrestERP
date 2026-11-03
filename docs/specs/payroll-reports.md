# Weekly Payroll Reports — specification

**Status:** spec ratified against re-derived golden values. The one open ruling (§7.1) was
**settled 2026-11-03 in favour of `520.44`**; no acceptance criteria remain disputed.
**Date:** 2026-11-03
**Scope:** reporting only. This module does **not** run payroll, does not pay anyone, and
does not touch the planned Check integration.
**Surface:** none. No UI in this dispatch; the surface is prototyped separately.

Replaces the accountant's Excel workbook for weekly union dues reporting. A Payentry
payroll export is imported, fixed rules run over it, and the weekly union dues reports
come out.

---

## 1. Rule set

Rules are versioned per tenant by `effective_date` (`payroll_rule_set`). Defaults:

| Field | Default | Meaning |
|---|---|---|
| `dues_pct` | `0.0145` | percentage-of-wage dues component (`a`) |
| `dues_cap_multiplier` | `0.6461` | average-hourly-rate cap component (`b`) |
| `dues_per_hour` | `0.02` | per-hour dues component (`c`) |
| `initiation_fee` | `10.00` | charged once, on a member's first dues week |
| `vacation_increment` | `0.65` | added to prior-year average hourly rate |
| `vacation_bonus` | `75.00` | flat addition to vacation pay |
| `stonebucks_per_ton` | `11.00` | stonebucks rate per ton, split across CSRs |
| `sick_in_dues_wage` | `false` | whether sick pay enters `dues_wage` |
| `sick_in_dues_hours` | `true` | whether sick hours enter `dues_hours` |
| `remittance_group_by` | `week_end_date` | monthly remittance grouping key |

`sick_in_dues_wage`, `sick_in_dues_hours` and `remittance_group_by` are flags because the
accountant is still confirming whether the workbook's asymmetric treatment of sick time is
intentional. **Defaults reproduce the workbook.** See §7.2, §7.3.

## 2. Money and rounding

All hours and money are `Decimal` (`Numeric`), never `float`.

Rounding is `ROUND_HALF_UP` to 2 decimal places, to match Excel's `ROUND`. Python's
default `ROUND_HALF_EVEN` is wrong here and would disagree with the workbook on exact
half-cents.

`round2` below means `quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)`.

Intermediate values are **not** rounded. `dues_wage` carries full precision into `a` and
`b`; only `a`, `b` and `c` are rounded, and they are rounded before `min()` and before the
sum. Rounding earlier changes answers.

## 3. Dues calculation

```
dues_wage  = (reg + personal + ny_covid + bereavement) * reg_rate
           + (ot + ot2) * ot_rate
           + stonebucks_amt + misc_amt + vac_amt
                                            # sick pay EXCLUDED by default

dues_hours = reg + personal + ny_covid + sick + bereavement + ot + ot2 + vac_hrs
                                            # sick hours INCLUDED by default

if dues_hours == 0:  dues = 0               # short circuit, before any division

a = round2(dues_wage * dues_pct)
b = round2((dues_wage / dues_hours) * dues_cap_multiplier)
c = round2(dues_hours * dues_per_hour)

dues = min(a, b) + c
     + initiation_fee                       # only on the member's first dues week,
                                            # and only if initiation_fee_due
```

The `dues_hours == 0` guard is what makes `b` safe; there is no other division.

`ot_rate` is nullable. **Null means `reg_rate * 1.5`**, derived at calculation time. The
workbook carries typed-in OT rates that are frequently *not* 1.5x — see §6.

### 3.1 Vacation pay

```
vacation_pay = round2(
    ((prior_year_gross / prior_year_hours) + vacation_increment) * vac_hours
    + vacation_bonus
)
```

Optionally split across up to 3 periods by fractions that must sum to exactly 1.

### 3.2 Stonebucks

```
stonebucks_per_day = round2(tons * stonebucks_per_ton / csr_count)
                     0 if csr_count == 0
```

## 4. Data model

Tenant-scoped throughout (`tenant_id` -> `companies.id`). IDs are `String(36)` UUIDs;
timestamps are `DateTime(timezone=True)`, per CLAUDE.md §5.

- **`payroll_report_employee`** — `tenant_id`, `payentry_file_number`, `display_name`,
  `dept`, `is_union_member`, `union_join_date`, `initiation_fee_due`, `active`
- **`payroll_rate`** — `employee_id`, `reg_rate`, `ot_rate` (**nullable**; null =
  `reg_rate * 1.5`), `effective_date`
- **`payroll_rule_set`** — `tenant_id`, `effective_date`, + the fields in §1
- **`payroll_week`** — `tenant_id`, `week_number`, `week_end_date`, `check_date`
  (= `week_end_date + 5 days`), `source_file_hash`, `status`
  (`imported` / `calculated` / `approved`), `imported_at`, `approved_by`, `approved_at`
- **`payroll_week_line`** — `week_id`, `employee_id`, `reg_hrs`, `ny_covid_hrs`, `ot_hrs`,
  `ot2_hrs`, `personal_hrs`, `sick_hrs`, `bereavement_hrs`, `winter_hrs`, `vac_hrs`,
  `stonebucks_amt`, `misc_amt`, `vac_amt`, `weeks_pay`, + `raw` JSON holding the original
  import row verbatim
- **`payroll_week_result`** — `week_id`, `employee_id`, `report_key`, `values` JSON,
  `rule_set_id`, `rate_ids` — so every number traces back to the inputs and the rule
  version that produced it

`ot_rate` is nullable **as a semantic**, not merely as a convenience: null records "this
rate was never established separately" and is distinguishable from a measured value, per
CLAUDE.md §5 *"a migration must leave 'not established' distinguishable from a measured
value"*.

## 5. Calculation engine

Pure functions. **No DB access, no session, no ORM imports.** `Decimal` throughout. The
engine takes line values + a rule set + resolved rates and returns results; persistence is
the caller's job. This is what makes the golden tests hand-provable without a database.

## 6. Golden fixture — week 44, w/e 2026-10-31

Anonymized ids. Real names are deliberately absent from fixtures. Rates are the workbook's
own typed-in OT rates.

Re-derived independently from the rules in §3 before any implementation existed, so the
expected values are not inherited from the code under test (CLAUDE.md §11 *"Money math is
hand-proven"*, *"Figures in dispatches are never inherited"*).

| id | reg | pers | ot | reg_rate | ot_rate | dues_wage | dues_hours | a | b | c | dues | binds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E01 | 40    | — | 7     | 30.00 | 45.000 | 1515.00000 | 47.00 | 21.97 | 20.83 | 0.94 | **21.77** | b |
| E02 | 40    | — | 12.8  | 24.54 | 35.835 | 1440.28800 | 52.80 | 20.88 | 17.62 | 1.06 | **18.68** | b |
| E03 | 40    | — | 7.9   | 24.39 | 36.585 | 1264.62150 | 47.90 | 18.34 | 17.06 | 0.96 | **18.02** | b |
| E04 | 40    | — | 2     | 24.39 | 36.585 | 1048.77000 | 42.00 | 15.21 | 16.13 | 0.84 | **16.05** | a |
| E05 | 36    | 4 | 7.68  | 24.44 | 35.685 | 1251.66080 | 47.68 | 18.15 | 16.96 | 0.95 | **17.91** | b |
| E06 | 40    | — | 7.43  | 24.39 | 36.585 | 1247.42655 | 47.43 | 18.09 | 16.99 | 0.95 | **17.94** | b |
| E07 | 32    | — | 6.68  | 22.34 | 32.535 |  932.21380 | 38.68 | 13.52 | 15.57 | 0.77 | **14.29** | a |
| E08 | 40    | — | 5.83  | 22.34 | 32.535 | 1083.27905 | 45.83 | 15.71 | 15.27 | 0.92 | **16.19** | b |
| E09 | 0     | — | 0     | 22.34 | 32.535 |    0.00000 |  0.00 |  n/a  |  n/a  | n/a  |  **0.00** | zero |
| E10 | 31.57 | — | 0.08  | 22.34 | 32.535 |  707.87660 | 31.65 | 10.26 | 14.45 | 0.63 | **10.89** | a |
| E11 | 32    | — | 4.9   | 22.34 | 32.535 |  874.30150 | 36.90 | 12.68 | 15.31 | 0.74 | **13.42** | a |
| E12 | 40    | — | 1.37  | 22.34 | 32.535 |  938.17295 | 41.37 | 13.60 | 14.65 | 0.83 | **14.43** | a |
| E13 | 40    | — | 1.2   | 22.34 | 32.535 |  932.64200 | 41.20 | 13.52 | 14.63 | 0.82 | **14.34** | a |

All 13 per-member `dues_wage`, `dues_hours` and `dues` values reproduce exactly.

**Totals**

| | derived (all 13 rows) | dispatch states | |
|---|---|---|---|
| total dues | `193.93` | `193.93` | match |
| total wage | `13236.25275` -> round2 `13236.25` | `13236.25` | match |
| total hours | `520.44` | `479.24` | **dispatch figure was wrong — ruled `520.44`, see §7.1** |

**Vacation.** prior gross `33062.74`, prior hours `1512.36`, 40 vac hrs, increment `0.65`,
bonus `75`:

```
33062.74 / 1512.36 = 21.86168637096987489751117459
          + 0.65   = 22.51168637096987489751117459
          x 40     = 900.4674548387949959004469836
          + 75     = 975.4674548387949959004469836
          round2   = 975.47          -> matches
```

### 6.1 Null-OT comparison (second golden)

With `ot_rate = NULL` (derived as `reg_rate * 1.5`), dues rise for exactly eight members.
The predicted set and the derived set agree, and every delta is positive:

| id | reg_rate | typed ot | 1.5x | dues (typed) | dues (1.5x) | delta |
|---|---|---|---|---|---|---|
| E02 | 24.54 | 35.835 | 36.810 | 18.68 | 18.84 | +0.16 |
| E05 | 24.44 | 35.685 | 36.660 | 17.91 | 18.01 | +0.10 |
| E07 | 22.34 | 32.535 | 33.510 | 14.29 | 14.38 | +0.09 |
| E08 | 22.34 | 32.535 | 33.510 | 16.19 | 16.27 | +0.08 |
| E10 | 22.34 | 32.535 | 33.510 | 10.89 | 10.90 | +0.01 |
| E11 | 22.34 | 32.535 | 33.510 | 13.42 | 13.49 | +0.07 |
| E12 | 22.34 | 32.535 | 33.510 | 14.43 | 14.45 | +0.02 |
| E13 | 22.34 | 32.535 | 33.510 | 14.34 | 14.36 | +0.02 |
| | | | **total** | **193.93** | **194.48** | **+0.55** |

E01, E03, E04, E06 are unchanged because their typed OT rate already equals `reg_rate *
1.5` exactly (`30 -> 45`, `24.39 -> 36.585`). E09 is unchanged at zero.

### 6.2 What this fixture does and does not exercise

Stated because "the golden tests pass" otherwise reads as broader coverage than it is
(CLAUDE.md §11 *"a gate reports its denominator"*).

**Genuinely discriminated.** `min(a, b)` is exercised in **both** directions — the cap `b`
binds on 6 rows (E01, E02, E03, E05, E06, E08) and the percentage `a` binds on 6 rows
(E04, E07, E10, E11, E12, E13). The `dues_hours == 0` short circuit is exercised by E09.
Neither branch is coverage by accident.

**Zero contact.** Eight of the thirteen line inputs are identically zero in every golden
row: `ny_covid_hrs`, `sick_hrs`, `bereavement_hrs`, `ot2_hrs`, `vac_hrs`,
`stonebucks_amt`, `misc_amt`, `vac_amt`. Only `reg_hrs`, `personal_hrs` (E05 alone) and
`ot_hrs` carry nonzero values. The initiation fee is not exercised. The 3-period vacation
split is not exercised.

**Consequence — the sick flags cannot be tested by this fixture at all.** Because
`sick_hrs = 0` on all 13 rows, flipping either `sick_in_dues_wage` or
`sick_in_dues_hours` leaves every golden value unchanged. A test asserting those flags
against this fixture would be green without contact (CLAUDE.md §11 green-without-evidence
shape 6) and would stay green if the flags were wired backwards or not wired at all.

**Therefore the sick flags, the initiation fee, the vacation split, and each of the eight
zero-contact inputs get their own dedicated tests with nonzero values, hand-computed
separately.** They are not covered by week 44 and must not be reported as if they were.

## 7. Open rulings

### 7.1 SETTLED 2026-11-03 — total dues_hours is `520.44`

The dispatch states `total hours 479.24`. Summing `dues_hours` over all 13 rows gives
**`520.44`**. The difference is **`41.20`**, which is exactly E13's `dues_hours`.

`479.24` is the running total through **E12** — the sum of the first twelve rows:

```
after E01: 47        after E06: 284.81     after E11: 437.87
after E02: 99.8      after E07: 323.49     after E12: 479.24   <-- stated total
after E03: 147.7     after E08: 369.32     after E13: 520.44   <-- all 13 rows
after E04: 189.7     after E09: 369.32
after E05: 237.38    after E10: 400.97
```

This is not a rounding question and not a rule question. The stated hours total has a
**different population** than the other two totals in the same report:

- total dues `193.93` = all 13 rows (12 rows would give `179.59`)
- total wage `13236.25` = all 13 rows (12 rows would give `12303.61`)
- total hours `479.24` = 12 rows

It also contradicts the dispatch's own rule for this report, *"all rows included in every
total"*.

The shape is consistent with a SUM range in the workbook covering one column one row short
— which is the class of defect this module exists to remove.

**RULING (2026-11-03): `520.44` is correct. `479.24` was a workbook bug**, and the
workbook's week-44 hours total was understated by `41.20`. The golden test asserts
`520.44`.

The formula was not adjusted to reach either figure — the mismatch was reported first and
ruled on before any test was written, per the dispatch's STOP condition. The rejected
reading (b) would have required an unstated rule excluding E13 from the hours total alone
while counting it in both the dues and wage totals; no such rule exists.

⚠️ **This is the first known defect the module corrects relative to the workbook it
replaces.** Recorded here because the discrepancy is evidence about the workbook, not
about this module, and the accountant will see a week-44 hours total that differs from
their own records by `41.20`. That difference is expected and correct.

### 7.2 Is the workbook's sick-time asymmetry intentional?

Sick pay is excluded from `dues_wage` while sick hours are included in `dues_hours`. Shipped
as two independent rule-set flags with defaults reproducing the workbook. Accountant
confirming. Note §6.2: the week-44 fixture cannot validate either flag.

### 7.3 Monthly remittance grouping — `week_end_date` or `check_date`?

Shipped as a rule-set setting, default `week_end_date`, pending confirmation. The two
differ by 5 days, so a week ending near a month boundary lands in different months under
each. Week 44 (w/e 2026-10-31, check date 2026-11-05) is exactly such a week: it groups to
**October** under `week_end_date` and **November** under `check_date`.

### 7.4 Payentry export format — sample needed

The parser is a pluggable interface plus a column-mapping config. The real Payentry parser
is **not** written; per the dispatch, build stops before it pending a sample export. The
sample lives outside the repo and must never be committed.

## 8. Reports

Each returns structured data and supports CSV export.

| report_key | Shape |
|---|---|
| `weekly_dues_detail` | per member: `dues_wage`, `dues_hours`, `a`, `b`, `c`, `dues`, + totals (all rows in every total — see §7.1) |
| `employee_dues_deduction` | name + dues for the week, + total |
| `monthly_dues_remittance` | per member sum for a calendar month, grouped per §7.3 |
| `vacation_pay` | per employee for a year |

### 8.1 Validation flags

- zero hours with pay
- missing rate
- `ot_rate != 1.5 * reg_rate` (**warn only** — this is the normal case in the workbook; 9
  of the 13 week-44 members are in this state, so it is advisory, never an error)
- employee present in the export but not configured
- configured member missing from the export

## 9. API

FastAPI, accountant/admin role only:

- upload export -> create week
- recalculate week
- get reports
- approve week (locks it)

Recalculating an approved week is **refused**. Approval is terminal for calculation.

## 10. Out of scope

No UI. Does not run payroll. Does not touch existing accounting, payroll-adjacent
reconciliation, or anomaly code. Does not touch the planned Check integration.
