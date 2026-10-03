# r195 pre-flight: does production hold the state the migration expects?

**2026-10-03.** Read-only against production, connection-level guard confirmed `on`
before any read, credentials never printed (`host`/`port`/`db` only). Run before
pushing `6f14311e`.

**Why this was run rather than reasoned about.** `r194` was validated against
production by COUNT — 21 rows, 21 distinct keys. That is the right check for a
uniqueness constraint and the wrong one for `r195`, which carries postconditions
asserting specific CONTENT. Nothing had established that production's 21 rows were
the *same* 21 as the reference's.

⚠️ **Equal cardinality standing in for an equal set is the substitution this arc
caught three times on 2026-10-02 alone. This is the instance that writes to a live
system.** The reproduction-from-empty evidence is strong about what `r186→r195`
produces from nothing; production did not come from nothing.

⚠️ **And r195's postconditions are demonstrably load-bearing**, which is what makes
a content mismatch expensive: during break-testing they REFUSED to apply onto a
catalog whose `CE-CT` had been deleted, rolling the migration back. That is the
behaviour you want — and against production it would be a failed migration
mid-deploy rather than on a laptop.

---

## 1. The comparison had to be against r193/r194, not against dev

⚠️ Dev was already at `r195` (29 products / 52 variants). Comparing it to production
would have measured **the migration**, not production's fitness to receive it. The
reference is a database built from empty to exactly the head production is on.

```
reference   local, built from empty       head r194_product_template_natural_key
production  shuttle.proxy.rlwy.net        head r194_product_template_natural_key
```

ⓘ Production was found at **r194, not r193** — the `dfd23c1f` push had deployed and
the unique constraint was already live there. The reference was upgraded to match
rather than the difference being reasoned away.

## 2. Symmetric difference by CONTENT: zero

Column lists built from `information_schema`, not from memory, so a column added
later joins the comparison automatically. `id`, `created_at`, `updated_at` and
`product_template_id` excluded as environment-specific. Variants carry their
parent's NATURAL key rather than its surrogate id, so the comparison does not
depend on `uuid5` reproducing identically.

| section | reference | production | symmetric difference |
|---|---|---|---|
| families | 16 | 16 | **0** |
| products | 21 | 21 | **0** |
| variants | 37 | 37 | **0** |

74 rows compared across 17 product columns and 15 variant columns.

### ⚠️ The comparator was break-tested, because zero is the reassuring answer

Perturbing a single field in the reference copy — twice, in different tables — was
detected and the differing field named:

```
BV-CON option_label  'Standard' vs 'Continental'       -> difference 2
wilbert-bronze reinforcement  'Triple' vs None         -> difference 2
```

A comparator reporting 0 and a comparator that cannot see are the same output.

## 3. Twelve preconditions, by value

Every state `r195`'s UPDATEs and postconditions depend on:

| # | check | production |
|---|---|---|
| 1 | `BV-CON.option_label` is the pre-rename value | `'Continental'` ✓ |
| 2 | `UV-VET.display_name` is the pre-rename value | `'Veteran Urn Vault'` ✓ |
| 3 | `CE-CT` exists | 1 ✓ |
| 4 | all 14 reinforcement targets exist | 14/14 ✓ |
| 5 | all 14 currently hold NULL | all NULL ✓ |
| 6 | NO product anywhere already has a tier | none ✓ |
| 7 | no product already on form `urn` | 0 ✓ |
| 8 | none of the 8 new family slugs exist | none ✓ |
| 9 | none of the 15 new SKUs exist | none ✓ |
| 10 | `continental/burial_vault` resolves to exactly one row | 1 ✓ |
| 11 | `graveliner/grave_liner` resolves to exactly one row | 1 ✓ |
| 12 | `r194`'s unique constraint is live | 1 ✓ |

**12 run, 12 passed, 0 failed.**

Checks 10 and 11 matter specifically: `r195` resolves those two parents with
`scalar_one()`, which raises on 0 **or** 2+ rows. `r194` makes the 2+ case
impossible; these confirm the 0 case does not apply either.

## 4. Verdict

**Safe to deploy.** Production holds exactly the state `r195` expects as input, by
content and not by count.

## 5. What this does not establish

- **That the deploy will succeed** — only that the migration's preconditions hold
  at the moment of reading. A deploy is a separate event and its head is read from
  `alembic_version` afterwards, not from a log line.
- **Anything about tenant `products` rows.** This is the platform tier. Sunnycrest's
  own product rows are untouched by `r195` and were not read here.
- **That the catalog is correct** — only that two environments agree about it.
