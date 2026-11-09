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

**The stop is enforced, not documented.** `column_mappings/payentry.json` ships with
`verified: false`, and `ColumnMapping.require_verified` RAISES on it — the upload endpoint
returns 422 with the remedy in the message. A guessed mapping that half-matched a real
export would be the worst outcome available: it would read the file, match some columns,
default the rest to zero, and emit dues that are confidently wrong for every member whose
hours fell in an unmatched column. A registered no-op parser would have the same problem
and be invisible at runtime, so the refusal is loud instead.

**To finish it:** obtain a sample, confirm the real header strings, replace the guessed
values, set `verified: true`, and record the sample's md5 in `sample_digest` so a later
format change is detectable. A digest is part of the citation, not a courtesy.

**A second format ships and is verified:** `bridgeable_csv` is this module's OWN canonical
weekly CSV. It is verified because the module *defines* it — the headers are normative
rather than observed. It exists so the upload → calculate → report → approve path is
usable and testable while the Payentry format is unknown. It is **not** a Payentry parser
and must not be offered as one.

### 7.5 `winter_hrs` and `weeks_pay` are stored but are not dues inputs

Neither appears in the `dues_wage` or `dues_hours` formula as specified. `winter_hrs` is
an **hour** column excluded from `dues_hours` while every other hour column is included,
and `weeks_pay` is a **money** column excluded from `dues_wage`.

This may well be intentional — but it is the same shape as the sick-time asymmetry in
§7.2, and it was not called out in the dispatch, so it is recorded here rather than
assumed. Current behaviour is pinned by a characterization test
(`test_payroll_engine_rule_edges.py::test_winter_hours_and_weeks_pay_do_not_move_dues`)
so that a ruling either way produces a failing test that names the change, instead of the
behaviour drifting with nothing to notice.

**Question for the accountant:** should `winter_hrs` be in `dues_hours`? And is
`weeks_pay` a reporting-only column?

### 7.6 Initiation fee on a zero-hours week

The dispatch states `if dues_hours == 0 → dues = 0` before the initiation-fee clause, and
"the employee's first dues week" reads as a week in which dues actually arise. So a member
with no hours is **not** charged the initiation fee and remains due it the following week.
This reading is implemented and pinned by a test; if the fee is owed regardless of hours,
the test fails and says so.

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

## 10. What the golden fixture proves, and what it does not

Stated because "the golden tests pass" otherwise reads as broader coverage than it is. The
goldens were **break-tested against twelve deliberate engine defects**; five fired, and
three did not fire at all until dedicated tests were added:

| Break | Red before | Red after |
|---|---|---|
| cap ignored (`capped = a`) | 14 ✓ | — |
| cap always binds (`capped = b`) | 14 ✓ | — |
| zero-hours guard removed | 7 ✓ | — |
| NULL ot_rate derives 1.0x not 1.5x | 15 ✓ | — |
| `dues_wage` rounded before a/b | 11 ✓ | — |
| **`ROUND_HALF_EVEN` instead of `ROUND_HALF_UP`** | **0 ✗** | 5 ✓ |
| **`vac_hrs` dropped from `dues_hours`** | **0 ✗** | 1 ✓ |
| **sick hours never added to `dues_hours`** | **0 ✗** | 3 ✓ |
| sick wage flag ignored | — | 2 ✓ |
| initiation fee not added | — | 1 ✓ |
| vacation split naive rounding | — | 1 ✓ |
| stonebucks `csr_count == 0` guard removed | — | 1 ✓ |
| float accepted instead of refused | — | 1 ✓ |
| `fmt_exact` reverts to bare `normalize()` | — | 1 ✓ |

⚠️ **The rounding row is the one worth reading.** `ROUND_HALF_UP` is named explicitly in
the dispatch, and no value in the week-44 fixture lands on an exact half-cent — so the
rounding mode could have been wrong in production with all 32 golden assertions green.
That was not predicted; it was found by breaking the thing and watching nothing happen.

## 10a. Out of scope

No UI. Does not run payroll. Does not touch existing accounting, payroll-adjacent
reconciliation, or anomaly code. Does not touch the planned Check integration.

---

## 11. Payroll 4 — the register

Payroll 1–3 read the weekly **hours export**: what we are about to pay. Payroll 4
reads the Payentry **Payroll Register**: the checks actually issued, with their
earnings, taxes and deductions exactly as printed. Measured against one year —
2025-11-09 to 2026-11-09, 262 pages, 1,275 checks, 30 employee ids.

The register never enters the repository. It carries names, pay rates, child
support and garnishment lines; it is read in place and only parsed rows are kept.

### 11.1 What the register contains

| | codes | count |
|---|---|---|
| earnings | `Reg` `OT` `Sal` `PTO` `Vac` `Sick` `VacBonus` `Comm` `HealthInsS` `Bonus` `Hol` `Ber` `Winter` | 13 |
| deductions | `Union` `MedicalPT` `401k` `Kloan` `HSAEEInd` `CellReimb` `CafMed` `ChSup1` `Roth401K` `Garn` `Med2Reim` `BootReim` `GasReim` | 13 |

`Union` is the only deduction that affects dues. 629 `Union` lines across 18 of
the 30 employee ids. 105 deduction lines are **negative** — reimbursements
(`CellReimb` 88, `Med2Reim` 8, `BootReim` 6, `GasReim` 2, `MedicalPT` 1) — and
are stored negative; `abs()` would overstate the deduction total by twice the
amount and break the agreement with the printed total that validates the parse.

`ChSup1` and `Garn` are **sensitive**: line-level only, payroll area only, never
summarised in a note, report or Opas text outside that area (James, 2026-11-09).
Enforced structurally by `tests/test_sensitive_deduction_codes.py`, which
requires every module that can reach a check line to be named with a reason.

### 11.2 Dues from actual pay lines — 553 of 629

The dues code map was **measured**, not chosen: candidate maps were scored
against the 629 real `Union` deductions, which are the answer key.

| | codes |
|---|---|
| dues **wage** | `Reg` `OT` `PTO` `Ber` `Vac` `VacBonus` `Hol` |
| dues **hours** | `Reg` `OT` `PTO` `Ber` `Vac` `Hol` |
| neither | `Sal` `Sick` `Comm` `Bonus` `HealthInsS` `Winter` |

Each exclusion is a measurement. Adding `Comm`, `Bonus`, `HealthInsS` and
`Winter` **lowers** the match count from 553 to 552. `VacBonus` is in the wage
and not the hours because all 29 of its lines are flat amounts with no hours.
`Vac` alone changes nothing (535); `Vac`+`VacBonus` takes 535 → 552; `Hol` → 553.

The 76 disagreements, by shape:

| count | shape |
|---|---|
| 34 | off by up to 1.00 |
| 22 | off by 1.00 to 5.00 |
| 10 | within 2 cents |
| 6 | actual exactly 10.00 higher — an initiation fee |
| 2 | no dues-bearing earnings on the check at all |
| 2 | off by more than 5.00 |

The two largest buckets are small, signed in both directions and spread across
17 of the 18 members. That is the shape of dues computed from a **different
week's** figures: the accountant works from the hours export and types the
result into Payentry, so a timing offset would look like this. Recorded as the
leading hypothesis only — it has not been tested against an hours export for
the same weeks, and doing so is the obvious next measurement.

### 11.3 §7.2 SETTLED — sick is out of both

The accountant answered on 2026-11-03: sick is excluded from dues wage **and**
dues hours. `sick_in_dues_hours` becomes `False`, reversing the shipped default.

The register adds a fact that makes this cheap to accept: of the 76 missing
checks, **none carries a `Sick` line at all**. Including sick hours could not
turn a single miss into a match, so no evidence in a year of registers argues
against the accountant's answer. `scripts/check_register_dues.py` re-asks the
question on every run and reports rather than acts.

### 11.4 §7.5 — the register barely speaks to `winter_hrs`

`Winter` appears on **2** earning lines in the whole year, and neither is on a
check that carries union dues. Excluding it is what the measured map does, but
2 lines is not evidence. §7.5 stays open and still needs the accountant.

### 11.5 The initiation fee is a people fact, not an inference

Six checks show an actual dues figure exactly 10.00 above the computed one — the
fee. Only **2 of those 6** are that member's first `Union` check in the
register's window, so "first check seen" would charge four established members a
fee they had already paid and would miss members whose membership began before
whatever range happened to be uploaded. Whether a member has paid an initiation
fee belongs in the people facts of Phase 4. `dues_for_check` therefore takes
`apply_initiation_fee` from its caller and never infers it.

### 11.6 Two notes on reading the PDF, kept because both were silent faults

**A code glued to its description must be split by character position, not by a
known-code prefix.** When a code fills its column the renderer emits no space,
so `extract_words` returns `MedicalPTMedical` as one token. Splitting against a
list of known codes is circular — the list is what the parse is meant to
discover. Worse, it fails *quietly* when the wrong prefix is also a real code:
the first version read every `VacBonus` line as `Vac`, because `Vac` is a
legitimate prefix of it. No unknown code was reported, 29 vacation-bonus lines
were counted as vacation pay, and nothing disagreed. The description column
starts at a fixed x in every band, so the characters themselves say where the
code ends.

**A person's name is only what sits above the `Emp Id` row.** Reading the whole
left-hand band also reads the page footer on the last block of each page — 256
pages of it — which turned 30 employees into 72 distinct "people". One display
name per employee id is resolved by frequency, and any id with a second
candidate is **reported, never merged**: a real name change is possible and only
a person can tell it from a parse fault. Measured after the fix: 30 ids, 30
names, 0 ambiguous.

### 11.7 Phase 4 — people facts, proposed not written

The register is the only record of which employee ids were paid, what names
were printed beside them, which had dues taken, and when a member was charged
an initiation fee. `payroll_report_employees` already carried every one of
those fields except the last, so the register **populates** them.

One column is new: `initiation_fee_paid_date`. It is not a second copy of
`initiation_fee_due` — that one is forward-looking ("charge a fee next time
dues arise"), this one is historical ("a fee was charged, on this date").

Reconciliation returns **proposals**, never writes: `fill` (the roster has
nothing), `agree`, or `conflict`. Only `fill` is applied, and only on request.
`is_union_member` fills **upward only** — a dues line proves membership, its
absence disproves nothing, because a member on leave or between entitlements
has no dues line to show.

Measured: 30 employee ids, 18 with membership proved, 0 ambiguous names, 6 with
an initiation fee observed (one date each, no conflicts).

### 11.8 Phase 6 — the R-115, beside the existing remittance report

| report_key | source | says |
|---|---|---|
| `monthly_dues_remittance` | hours export | dues the rules **imply** |
| `union_remittance_r115` | register | dues actually **deducted** |

Both are kept (James, 2026-11-09). They disagree on 76 of 629 checks, which is
why: the form filed with the union must state what was taken, and the other
report is how you learn whether what was taken was right.

The R-115 is **always grouped by check date** and that is not a setting — a
register has a check date and carries no week-end date, so the alternative is
unavailable rather than unselected. `monthly_dues_remittance` keeps its setting
because its source has both dates.

Status flow `draft -> submitted -> filed`, with one step back from `submitted`.
`filed` is **terminal**, enforced by having no entry in `R115_TRANSITIONS`
rather than by a branch — a terminal state guarded by an `if` can be bypassed
by whoever adds the next `elif`. A correction is a **new form** that supersedes
the old one, which keeps its own stored table: the stored rows are the record of
what was sent, not a cache of a query, because recomputing a filed month gives a
different answer as soon as an overlapping register is imported.

October 2026 local check (`scripts/check_r115_october.py`), by check date:
five check dates — Oct 1, 8, 15, 22, 29, exactly as the ruling named — 61 check
rows, 13 members, 2,731.14 hours, **979.73** dues.

### 11.9 OPEN — `vacation_bonus` tiers are DISPUTED, and Phase 5 waits on them

Phase 5 (vacation pay) is **not built**, because the figure it would compute
with is not agreed. See the `disputed` provenance on `vacation_bonus` and
§11.10.

The register also shows that vacation pay and the vacation bonus are **two
separate earning lines** (`Vac` and `VacBonus`), each rounded to the cent on its
own — not one combined amount. The current formula in §3.1 adds the bonus inside
a single `round2(...)`, which is a different computation and can differ by a
cent. This is the shape of the correction already noted for the spec
(975.47 -> 900.46 + 75.00 = 975.46).

### 11.10 The measured vacation bonus

Paid as a **total per vacation entitlement**, in equal instalments alongside
each vacation week:

| entitlement | total | as paid |
|---|---|---|
| one week (40 h) | 75.00 | once |
| one week (48 h) | 85.00 | once |
| two weeks | 125.00 | 62.50 x2, or 125.00 once |
| three weeks | 155.00 | 51.67 / 51.66 / 51.67 |
| four weeks | 155.00 | 38.75 x4 |

One week at 75.00 and three weeks at 155.00 agree with the dispatch. A **second
week does not**: the registers say the two-week total is 125.00, not
75.00 + 30.00 = 105.00. The 48-hour week at 85.00 is a shape the dispatch does
not describe, suggesting the bonus may be a function of vacation **hours**
rather than whole weeks. Four weeks paying the same as three suggests 155.00 is
a ceiling.
