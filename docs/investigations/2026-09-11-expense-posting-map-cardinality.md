# The posting map's cardinality — a flat mapping is the wrong shape

**Date:** 2026-09-11 · **HEAD:** `c32bda66` · **Read-only. No code changed.**

The preliminary, which the dispatch made blocking. Nothing here is inherited from
it — not the fifteen categories, not the 224 mappings, not the one open anomaly.

---

## 0. The answer

**A flat `(tenant, category) → account` table is the wrong cardinality, and so is
`(tenant, category, discriminator) → account` with any discriminator currently
available.** Three measurements, in increasing order of how much they cost:

1. Categories have **several** legitimate destination accounts on this tenant's
   real chart — not one.
2. For several categories those accounts span **more than one platform account
   type**, so the mapping cannot even nest under the parent.
3. The axes the chart discriminates on — product line, role, function — **do not
   exist as structured data on the thing being posted.** `VendorBillLine` has 11
   columns and none of them is a product line, department or cost centre.

⚠️ **A flat mapping would reproduce, one level finer, the exact defect this arc
already rejected.** STATE records that a parent lookup "would post `payroll` to
MISC. A & S silently and confidently." A category-level mapping posts *every*
salary line to whichever salary account the accountant picked the first time —
equally silently, equally confidently.

---

## 1. Re-derived figures

**15 categories**, by AST over `EXPENSE_CATEGORIES` in
`agents/expense_categorization_agent.py` — `vault_materials`, `direct_labor`,
`delivery_costs`, `other_cogs`, `rent`, `utilities`, `insurance`, `payroll`,
`office_supplies`, `vehicle_expense`, `repairs_maintenance`, `depreciation`,
`professional_fees`, `advertising`, `other_expense`.

⚠️ Not to be confused with `PLATFORM_CATEGORIES`, which is a **dict of 8 account
types over 34 children**. Two vocabularies, one word.

**224 `tenant_gl_mappings` rows**, all on one tenant, distributed across 13
platform categories — `cogs` 47, `expense` 42, `current_liability` 27,
`delivery_cost` 26, `current_asset` 22, `fixed_asset` 20, `revenue` 8,
`long_term_liability` 8, `tax_expense` 7, `equity` 5, `other_income` 5,
`contra_revenue` 5, `other_expense` 2.

---

## 2. One category, many accounts

From the 42 accounts carrying `platform_category='expense'`:

**`payroll`** — 8350 OFFICER SALARIES · 8360 OFFICE SALARIES · 8370
ADMINISTRATIVE SALARIES · 8380 SALES SALARIES & COMMISSIONS · 8400 PAYROLL TAXES
- A & S · 8420 401K MATCH · 8460 UNEMPLOYMENT TAXES · 8860 PAYROLL PREPARATION.

**`insurance`** — 8450 HEALTH INSURANCE - A & S · 8451 OFFICER HEALTH INSURANCE ·
8500 COMP. & DBL INSURANCE - A & S · 8510 OFFICER LIFE INSURANCE · 8730 INSURANCE
EXPENSE.

**`advertising`** — 8580 ADVERTISING · 8590 DISPLAYS: FUNERAL · 8600 PROMOTION &
RESEARCH - PRECAST · 8610 SELLING & PROMOTION-FUNERAL.

**`professional_fees`** — 8850 ACCOUNTING · 8870 PROFESSIONAL FEES · 8900 LEGAL &
COLLECTIONS.

**`office_supplies`** — 8710 SMALL OFFICE EQUIPMENT · 8800 OFFICE SUPPLIES
EXPENSE · 8810 COMPUTER SUPPLIES & MAINT.

⚠️ **Method caveat:** assigning these accounts to categories is *my* reading of
account names, not a mapping the system holds — the whole point is that no such
mapping exists. The claim that survives without judgement is weaker and
sufficient: **the chart draws distinctions the 15-word vocabulary cannot
express.** OFFICER SALARIES and OFFICE SALARIES are different accounts and
`payroll` is one word.

---

## 3. The candidates cross account types

Matched on account name across all 224 rows, so the search was not confined to
one type:

```
VEHICLE   6 accounts   types: delivery_cost, expense
  delivery_cost  7940 VEHICLE MAINTENANCE- PRECAST
  delivery_cost  7950 VEHICLE MAINTENANCE-VAULT
  delivery_cost  8050 INSURANCE - VEHICLE
  delivery_cost  8200 VEHICLE/TRAILER RENTAL
  delivery_cost  8250 VEHICLE LEASE
  expense        8970 OFFICER VEHICLE LEASE

RENT      5 accounts   types: cogs, delivery_cost, expense
MAINT     4 accounts   types: cogs, delivery_cost, expense
DEPREC    2 accounts   types: cogs, delivery_cost
UTIL      1 account    type:  cogs          ← and NOT `expense`
```

Two consequences. A `vehicle_expense` mapping nested under its parent type is
impossible, because its candidates sit under two parents. And `utilities`
resolves to an account whose platform category is **`cogs`**, so even the
category-to-type correspondence is not reliable.

---

## 4. The discriminator does not exist on the bill line

`VendorBillLine`, enumerated — **11 columns**:

`id` · `bill_id` · `po_line_id` · `description` · `quantity` · `unit_cost` ·
`amount` · `expense_category` · `sort_order` · `created_at` · `deleted_at`

No product line. No department. No cost centre. The only discriminating content
is `description` (free text) and, through `bill_id`, the vendor.

But the chart discriminates on at least three axes:

- **product line** — PRECAST vs VAULT vs FUNERAL (7940/7950, 8590/8600/8610)
- **role** — OFFICER vs staff (8350/8360, 8450/8451, 8250/8970)
- **function** — MFG vs DELIVERY vs A & S (6950 vs 7940, 7000 vs 8100)

⚠️ **Vendor is the only structured discriminator available, and it does not
separate the cases that matter.** One payroll provider bills officer and office
salaries alike. A `(tenant, category, vendor) → account` table resolves fuel and
fails salaries.

⚠️ **The distinctions live in prose.** Which is precisely why a human reading the
bill line CAN make the call and a table cannot — and why writing the answer as a
reusable row is the part that breaks.

---

## 5. What this means for the dispatch

**§2's triage framing survives and is strengthened.** The decision genuinely
needs the bill in front of it, because the category under-determines the account
and the deciding context is unstructured. Per-occurrence is right.

**§1's storage shape does not survive.** "Resolving it writes the mapping" needs
to say what a mapping IS. If it is `(tenant, category) → account`, the second
occurrence of `vehicle_expense` — the PRECAST one, when the first was the OFFICER
LEASE — gets the wrong account with no signal. That is the silent-and-confident
failure the arc rejected, at a finer grain.

**The options, not chosen here:**

- **Per-occurrence only.** The triage item resolves *this line* to an account and
  writes no reusable mapping. Honest, and every line stays manual forever.
- **Suggest, never resolve.** Store `(tenant, category) → account` as a
  *default the accountant confirms per line*, never as an auto-post. Keeps the
  learning, keeps the human in the loop, and the stored row is advisory — which
  is what "the accountant's decision is the only source" implies anyway.
- **Add the discriminator to the bill line.** Product line exists as a platform
  concept; it is not on `VendorBillLine`. That is a schema change and a data
  question (who sets it, and from what).

⚠️ **STOP, per the dispatch's first line.** The cardinality is wrong, and the
rest of the dispatch assumes it is not.

---

## 6. Method notes

- The 15 and the 34 were taken by AST, after `PLATFORM_CATEGORIES` turned out to
  be a dict of parents rather than the flat list the name suggests.
- Account searches ran across all 224 rows rather than within
  `platform_category='expense'`, which is how the type-spanning was found. Had I
  scoped to `expense` first — the obvious framing — `vehicle_expense` would have
  shown ONE candidate and the answer would have been "flat is fine."
- One statement per connection throughout.
- Production read through a connection-level read-only guard; credentials
  redacted to host and database.
