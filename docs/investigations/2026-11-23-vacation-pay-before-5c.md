# Vacation pay before 5c — what exists, and the four questions the brief has to answer

**Read-only. Nothing was changed.** Measured 2026-11-23 against `ac82c300`.

This is the existence-first pass CLAUDE.md asks for before a build. It was
written because the 5c brief has not arrived and this work is needed either
way: the answers decide what 5c *is*, and two of them are not mine to make.

## The headline

**Vacation pay is computed nowhere in the product.**

The rule is measured, the engine is written and tested against the real
register, and **no code path in `app/` or `scripts/` calls any of it.** That is
CLAUDE.md §11's complete-machinery-behind-an-unprovisioned-entrance for the
fourth time in this arc — after `payroll_status`, the Employee Hours parser and
`PayrollPunch`.

| function | callers in `app/` + `scripts/` | tests |
|---|---|---|
| `compute_vacation_pay` (SUPERSEDED form) | 0 — two of the four hits are a re-export in `__init__.py`, two are comments | 14 |
| `compute_vacation_pay_only` (corrected) | **0** | 5 |
| `compute_vacation_bonus` (corrected) | **0** | 3 |
| `vacation_bonus_for_year` | 0 — re-export and comments only | 16 |
| `vacation_rate` | 0 — same | 6 |
| `vacation_pay_report` | **0** | **0** |

⚠️ `vacation_pay_report` and its `VacationRow` are referenced **nowhere but
their own definitions** — confirmed with a positive control (the grep returns
exactly 1 hit, the `def` line). Its module is live and imported for other
things; the function pair is not.

⚠️ **So the 2026-11-09 correction has never run.** §3.1 records that the
truncated-rate split moved Hunt's week from 975.47 to 975.46 and that the
superseded combined form "remains in `compute_vacation_pay` so weeks already
calculated under it still re-derive their stored figures." **No weeks were
calculated under it** — `service.py::calculate_week` contains zero occurrences
of `vac`. There are no stored vacation figures to preserve, which makes the
back-compat argument for keeping the superseded form weaker than it reads.

## What else is absent

- **No vacation table.** `information_schema` has no `%vacation%` or
  `%entitle%` table. Entitlements — the hours that drive the day tiers — have
  nowhere to live.
- **No writer, no endpoint, no surface, no entrance.** Nothing in
  `app/api/routes/` mentions vacation.
- **The week calculation ignores it.** `vac_hrs` and `vac_amt` are canonical
  line fields on the hours import, and `calculate_week` does not read them.

## What DOES exist, and is good

- **The rulebook keys**: `vacation_increment` (0.65), `vacation_bonus_day_tiers`
  (cumulative $15/$10/$6 for days 1–5/6–10/11–15), and the superseded flat
  `vacation_bonus` kept so old rule-sets still resolve.
- **The rule, measured against the year** (`scripts/check_vacation_bonus.py`):
  13 entitlement groups, 29 bonus lines; tiers reproduce the yearly total in
  12 of 12 checkable groups, cumulative cent placement in 13 of 13.
- ⚠️ **And the spec says the discriminating evidence is one case deep.** 12 of
  the 13 groups cannot tell cumulative from largest-remainder apart. That is
  stated in §11.11 and is worth carrying into 5c rather than re-discovering.

## The four questions the brief has to answer

### 1. Where do `prior_year_gross` and `prior_year_hours` come from? ⚠️ Not mine to decide

`vacation_rate(prior_year_gross, prior_year_hours, …)` is the whole rate. The
spec settles their PROVENANCE for the one case it measured and it is **not the
register**:

> it is **Hunt's row on the accountant's workbook, Vac Calc tab** — the same
> row that computed 900.47 (§11.13, settled 2026-11-10)

Three candidate sources, and they are not equivalent:

| source | available today? | risk |
|---|---|---|
| sum `payroll_checks.printed_total_earnings` / `printed_total_hours` over the prior year | **yes** — both columns exist, with `check_date` | may not equal the workbook's figures; nobody has compared them |
| typed in, as the workbook does | needs a table and a surface | a figure nobody can re-derive |
| imported from the workbook | needs a parser and the file | the file is not in the repo |

**The measurable question, which nobody has asked:** does summing a year of
register checks reproduce 33,062.74 / 1,512.36 for Hunt? If it does, the input
is derivable and 5c needs no entitlement entry for the rate. If it does not,
the difference is the thing to understand before building anything.

⚠️ I did not run that against production. It is read-only and cheap, and it
decides the feature's shape, so it belongs at the top of 5c.

### 2. Where do entitlement HOURS come from?

The day tiers run on entitlement hours ÷ 8. Nothing stores entitlement. Is it
typed per person per year, derived from a union rule, or read off something?

### 3. What is the surface? ⚠️ Prototype first

CLAUDE.md: a new surface gets a clickable prototype reviewed before it is
dispatched. 5a and 5b each arrived with a brief naming the stages, the
entrances and a golden. 5c has none of those yet. Open: is it a Focus, a
report, or a line on the weekly Focus when `vac_hrs` is non-zero?

### 4. Should the rate's truncation become a rulebook key?

§11.13 flags it directly:

> This is **not** a rule-set column … It is therefore not effective-dated: a
> change to it would apply retroactively to every recomputed vacation figure.
> If that matters it should become a rulebook key — the work is a column, a
> migration and a line in the engine.

With no stored vacation figures today (above), this is the cheapest it will
ever be to change.

## What I did not do

No production probe. No code written. No prototype — that is the step the
brief precedes, not follows.
