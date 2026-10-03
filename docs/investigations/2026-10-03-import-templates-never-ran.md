# Has `import_product_templates` ever run? No — in either environment

**2026-10-03.** Read-only, both environments, guard confirmed `on`. Measured before
2b-3 Commit 3 so that commit can be graded correctly.

**Answer: no trace, anywhere. Commit 3 is a COLD PATH** — new code, not a change to
live behaviour.

---

## 1. ⚠️ The obvious signal is uninformative, and reporting it as zero would mislead

`products.variant_template_id IS NOT NULL` is **0** in both environments — and that
answers nothing.

The column was added by **r186 (2026-10-02)** and had no ORM attribute until
**r196 (2026-10-03)**. `import_product_templates` copies six fields and this is not
one of them. **It is NULL everywhere by construction**, so a zero is guaranteed
whether the path ran a thousand times or never.

Recorded because "0 rows with `variant_template_id`" is exactly the kind of true,
precise, well-formed number that would have closed this question with a wrong
answer.

## 2. The real fingerprint: what the function actually writes

```python
Product(name=template.product_name,
        sku=sku or template.sku_prefix,
        unit_of_measure=template.default_unit, …)
```

So the trace is a product whose **name equals a template's `product_name`**, and —
when the request supplied no sku — whose **sku equals the `sku_prefix`**.

| environment | products | templates | name matches | sku matches prefix |
|---|---|---|---|---|
| dev | 27 | 25 | **0** | 0 |
| production | 33 | 37 | 4 | **0** |

⚠️ **All four production matches have a known non-onboarding writer**, and the sku
is the discriminator — not one of them carries the prefix `import_product_templates`
would have written:

| product | sku | prefix | actual writer |
|---|---|---|---|
| `Monticello Burial Vault` | `DEMO2-P001` | `BV-MON` | `seed_accounting_demo.py:312` |
| `Continental Burial Vault` | `DEMO2-P002` | `BV-CON` | `seed_accounting_demo.py:313` |
| `Graveliner` | `GL-001` | `GL-STD` | `seed_staging.py:764` |
| `Graveliner` | `GL-001` | `GL-STD` | `seed_staging.py:764` |

**A name match alone is weak** — two seeders happen to use catalog names. The sku is
what separates "copied from a template" from "named like one", and it separates all
four.

⚠️ **POSITIVE CONTROL, because 0 and 4-explained are both reassuring answers.** A
self-join of `product_catalog_templates` on `product_name` returns **25 (dev) / 37
(production)** — so the join column and collation can match. The detector can see.

## 3. The independent signal agrees

`onboarding_checklist_items` where `item_key = 'add_products'`:

```
dev          2 rows,  0 marked complete
production   2 rows,  0 marked complete
```

**No tenant has ever completed the add-products onboarding step** — in either
environment. Exactly consistent with `GET /product-library` having returned 500 since
2026-03-17.

## 4. Consequence for Commit 3

`import_product_templates` has never provisioned a tenant. So repointing it is
**writing new code**, not migrating live behaviour:

- No existing `products` rows were created by it, so none need reconciling.
- No regression surface — there is no prior behaviour to preserve.
- It should be graded as new code: tested on its own terms, not diffed against what
  it used to do.

⚠️ **That lowers the risk and RAISES the bar.** A cold path has no production
evidence to check against, so it is correct only insofar as its tests say so. The
"highest risk" label from the consumer map was right about blast radius and wrong
about what makes it hard.

## 5. And the frontend's grouping is already dynamic

Reported for Commit 2 rather than assumed.

`product-library.tsx:22` builds its groups from the data
(`groups[t.category].push(t)`) and renders one collapsible section per key. **Six
forms need no new grouping concept** — the page already adapts to whatever arrives.

⚠️ **But `CATEGORY_ORDER` at `:34` is hardcoded to DEV's vocabulary:**

```js
const CATEGORY_ORDER = ["Burial Vaults", "Wastewater", "Redi-Rock", "Rosetta Hardscapes"];
```

Those are the `x1y2z3a4b5c6` migration's categories. **Production's are `Burial
Vaults`, `Urn Vaults`, `Cemetery Equipment`** — so two of production's three are
already unknown to this list and fall to `indexOf === -1`, sorting alphabetically
after the known ones. The ordering has been half-wrong in production all along, and
nobody saw it because the page never loaded.

The degradation is graceful (unknown keys sort last, no crash), so six forms will
render correctly but in an order nobody chose. **That list needs updating in Commit 2
— as a deliberate ordering decision, not a silent inheritance.**

## 6. What this does not establish

- **Whether any tenant completed `add_products` by another route** — manual product
  entry or CSV import would not set that checklist item either, so "0 complete" is
  consistent with a tenant having products and never touching the step.
- **Whether the two `Graveliner`/`GL-001` rows are in a real tenant.** They sit in
  companies `36fe9f40…` and `f60ef8de…`, which are not Sunnycrest; whether those are
  real or seeded was not measured here.
