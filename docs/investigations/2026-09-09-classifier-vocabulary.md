# The classifier's 14 "unmappable" categories — not absence, mismatch, or drift

**Date:** 2026-09-09 · **Read-only** against production. No code written, no
writes.

The question was whether the fourteen categories are unmappable because the
mappings do not exist, or because the vocabularies genuinely differ. **It is
neither**, and the distinction matters because the obvious fix is harmful.

⚠️ **Counts here are over `tenant_gl_mappings`, not `agent_anomalies`, so the
five seeded demo rows do not enter any figure below.** Stated because the
standing rule says every `agent_anomalies` count must declare them and silence
would be ambiguous.

---

## 1. The vocabularies do not differ. They are two LEVELS of one vocabulary.

`AccountingAnalysisService.PLATFORM_CATEGORIES` is a **parent → children** dict:

```
cogs           → vault_materials, direct_labor, other_cogs
delivery_cost  → delivery_costs
expense        → rent, utilities, insurance, payroll, office_supplies,
                 vehicle_expense, repairs_maintenance, depreciation,
                 professional_fees, advertising
other_expense  → interest_expense, penalties
```

The classifier's `EXPENSE_CATEGORIES` is the flattened list of **children** (plus
`other_expense`, which is a parent). `tenant_gl_mappings.platform_category`
stores **parents**. The agent queries child-level values against a parent-level
column, so every lookup misses.

**`resolve_platform_category()` already exists** and resolves child → parent.
Run against all fifteen, **fifteen of fifteen resolve**, to four parents — `cogs`,
`delivery_cost`, `expense`, `other_expense` — **and this tenant has all four
mapped.** Genuinely absent mappings: **zero**.

⚠️ **`delivery_costs` vs `delivery_cost` is not drift.** It is child versus
parent, distinct by design in the dict. I reported it as a near-miss typo
yesterday; that was wrong.

**`other_expense` is the single overlap** because it is simultaneously a child in
`EXPENSE_CATEGORIES` and a parent in the dict. That is the whole reason exactly
one of fifteen worked, and it is a coincidence of construction rather than a
signal.

---

## 2. ⚠️ STOP — correcting the level would be WORSE than the current behaviour

The tenant's mappings resolve like this:

```
cogs          → 7503 CREDIT CARD FEES PROCESSED
delivery_cost → 8255 EQUIPMENT LEASE
expense       → 9000 MISC. A & S
other_expense → 9250 PENALTIES
```

So a "fix" that resolved to the parent would post `vault_materials` to CREDIT
CARD FEES, `delivery_costs` to EQUIPMENT LEASE, and `payroll` to MISC. A & S —
**silently, with confidence, into the ledger.** Today the agent refuses to post
and raises an anomaly. That is strictly better.

⚠️ **And even those four accounts are arbitrary.** The table holds **224 rows for
this tenant, one per ACCOUNT**, and the accounts-per-type distribution is:

| platform_category | accounts | | platform_category | accounts |
|---|---:|---|---|---:|
| `cogs` | 47 | | `fixed_asset` | 20 |
| `expense` | 42 | | `revenue` | 8 |
| `current_liability` | 27 | | `long_term_liability` | 8 |
| `delivery_cost` | 26 | | `tax_expense` | 7 |
| `current_asset` | 22 | | `equity`, `other_income`, `contra_revenue` | 5 each |
| | | | `other_expense` | 2 |

The single account shown per parent in §2's first block was **whichever row my
query happened to keep last** out of 42. There is no "the" expense account.

---

## 3. The actual shape: the table answers the INVERSE question

**`tenant_gl_mappings` maps ACCOUNT → TYPE.** It is the output of COA analysis:
*"account 8350 OFFICER SALARIES is an `expense` account."*

**The classifier needs TYPE → ACCOUNT**: *"this line is `payroll`; which account
does it post to?"*

Those are inverse relationships, and the inverse is **one-to-many** — 42 accounts
carry `expense`. **The table does not contain the fact the classifier needs, and
no amount of resolving levels will produce it.**

Two different questions have been sharing one column name and one table.

---

## 4. ⚠️ Therefore `expense_no_gl_mapping` IS A TRUE FINDING

> Category `vehicle_expense` has no GL account mapping for this tenant. Add a
> mapping in Settings → GL Accounts before this can post.

**That statement is correct.** There is no fact in the system saying which
account `vehicle_expense` posts to. The agent declines to post and says why,
which is the right behaviour for a system that cannot know the answer.

The 1,825 rows were a **duplication** defect, and that is fixed. The **finding**
was never wrong. Yesterday's framing — that this is "the actual cause of the
largest anomaly population" and belongs at the top of the fix list — is right
about the cause and wrong about the remedy: there is no bug here to repair.

---

## 5. What it actually is: an unbuilt surface, not a broken one

Someone must decide, per tenant, **which account each of the fifteen categories
posts to**. That decision does not exist anywhere today:

- no `type → account` table
- the anomaly points at "Settings → GL Accounts", which is the COA analysis
  surface and answers the other direction

So this is a **build plus a data task**, not a repair — and the build is a
decision about where per-category posting targets live, which is James's.

⚠️ Until it exists, the correct behaviour is exactly what happens now. **Nothing
should be done to make these anomalies stop appearing**, and in particular the
one open `expense_no_gl_mapping` row left after the dedup should not be read as
residue.

---

## 6. Method notes

- Resolution checked by executing `resolve_platform_category` over all fifteen,
  not by reading the dict.
- Per-category verdict computed per row against production, not per type.
- The accounts-per-type distribution is the measurement that overturned the
  level-fix; without it the parent lookup looks like a one-line repair.
- No writes; read-only connection guard throughout.
