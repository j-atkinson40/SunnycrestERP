# The two discrepancies, resolved — and a ruling of mine retracted

**2026-10-02.** Read-only. No migration written or proposed. Resolves the two open items from
`1b7de2c8` and, in doing so, **retracts the catalog ruling I committed in `84efb8a0` the same
morning.**

**Four results.**

1. **Dev and production have entirely different template tables.** Dev's 25 rows come from a
   migration; production's 37 come from the seeder. Both populations are real; neither is the
   other's subset.
2. **One copy path, not two.** `tenant_onboarding_service` re-exports the single definition.
3. ⚠️ **MY RULING IN `84efb8a0` IS VOID.** Sunnycrest's 4 production products are demo seed
   rows, so the invoice lines that gave them "billing provenance" are demo rows referencing
   demo rows.
4. ⚠️ **The null-if-equal migration rule has a flaw independent of that**, and it would misfire
   on `is_manufactured` for every row.

---

## 1. The 25-vs-37 discrepancy — two writers, two environments

**The dev rows have an identifiable writer.** `alembic/versions/x1y2z3a4b5c6_add_onboarding_tables.py:362`:

```python
    op.bulk_insert(product_catalog_templates, seed_data)
```

25 rows, matching dev's 25 exactly. The STOP condition does not fire.

**The seeder has never run on dev, and the reason is a gate on something unrelated.**
`seed_wilbert_templates`' only caller is `app/main.py:274-275` — inside `seed_platform_admin()`,
whose entire body is guarded by:

```python
@app.on_event("startup")
def seed_platform_admin():
    if settings.PLATFORM_ADMIN_EMAIL and settings.PLATFORM_ADMIN_PASSWORD:
```

Both are unset in the dev environment (measured, presence only). So on dev the product catalog
templates are gated on **platform-admin credentials being configured** — a condition with no
relationship to products.

**Production, measured:**

```
templates TOTAL (whole table)          37
  Burial Vaults                        19
  Urn Vaults                           12
  Cemetery Equipment                    6
```

Exactly `catalog_template_seeder.py`'s three lists (19 + 12 + 6). So **the seeder is the live
convention in production**, and the migration's 25 are not there.

| | dev | production |
|---|---|---|
| rows | 25 | 37 |
| writer | `x1y2z3a4b5c6` migration | `catalog_template_seeder` via the startup hook |
| categories | Burial Vaults 8 · Redi-Rock 6 · Rosetta 4 · Wastewater 7 | Burial Vaults 19 · Urn Vaults 12 · Cemetery Equipment 6 |
| Urn Vaults | **absent** | 12 |
| Redi-Rock / Rosetta / Wastewater | present | **absent** |

⚠️ **Neither is a subset of the other, and they disagree on granularity.** Dev models Triune as
one product (`Wilbert Triune Burial Vault`, `BV-TRI`) and urn vaults as one
(`Concrete Urn Vault`, `UV-STD`). Production models six Triune finishes × two forms. A design
validated against dev would be validated against a convention production does not use.

**So the live convention for the migration's null-if-equal rule is production's 37**, and
`1b7de2c8`'s dev-based reading of it was measuring the wrong table. That correction is the
reason this question mattered.

### Bronze Triune, now confirmed in production

Production carries both as distinct platform rows:

```
[Burial Vaults] Bronze Triune Burial Vault   BV-BTRI
[Urn Vaults   ] Bronze Triune Urn Vault      UV-BTRI
```

Two SKUs — established against the live table rather than against a seeder that had never run.
The naming is still a developer's, not Wilbert's; what the xlsx pass is for.

## 2. One copy path

`grep -rn "def import_product_templates" app/` returns **one** definition,
`onboarding_service.py:1762`. The route calls it on `tenant_onboarding_service`, which
re-exports it at `tenant_onboarding_service.py:8-18` with `# noqa: F401`. Resolved at runtime:

```
attribute present: True
defined in: app.services.onboarding_service
```

**No drift risk.** A change to that function changes the only copy path.

## 3. ⚠️ Retraction: the catalog ruling in `84efb8a0` is void

All 4 Sunnycrest product rows carry a `DEMO%` sku, and `scripts/seed_accounting_demo.py:312-315`
defines exactly those four, with exactly those skus and prices:

```python
    ("Monticello Burial Vault",  "DEMO2-P001", Decimal("1250.00")),
    ("Continental Burial Vault", "DEMO2-P002", Decimal("1850.00")),
    ("Urn Vault - Standard",     "DEMO2-P003", Decimal("425.00")),
    ("Graveside Setup Service",  "DEMO2-P004", Decimal("300.00")),
```

`MARKER = "DEMO2"`, and the file's docstring states every seeded row carries it. Its customers
are demo as well — `DEMO2-C001`..`C005` are Hopkins, St Mary's, Riverside, Fairview, Lakeside.
Production's `Urn Vault - Standard` price reads 425.00 and `Graveside Setup Service` 300.00,
matching the seeder exactly.

**So the 8 invoices and 12 invoice lines are demo rows referencing demo rows.**

The reasoning I committed was: 7 of 12 invoice lines reference all 4 products → they have
billing provenance → the products table is authoritative. **Every step is true and the
conclusion is false**, because the population was synthetic. I checked that the rows were
REFERENCED and never that they were REAL.

⚠️ **Canon already named this.** CLAUDE.md §12 records this seeder by name as a known writer of
demo rows into production and requires that *"every count over that table states whether it
includes them."* I ran four production reads and stated it in none of them. The rule was
written for exactly this table and exactly this mistake.

**Corrected state:** production holds no real Sunnycrest product data and no real billing data.
That is the outcome named as the alternative — nothing is authoritative yet, and extending the
catalog is a genuine product decision rather than a reconciliation.

## 4. ⚠️ The null-if-equal rule would misfire, independent of the demo problem

Per-field, for the two Sunnycrest rows that match a production template by name:

| field | product | template | rule's verdict |
|---|---|---|---|
| `name` | `Continental Burial Vault` | same | EQUAL → null |
| `unit_of_measure` | `each` | `each` | EQUAL → null |
| `sku` | `DEMO2-P002` | `BV-CON` | DIFFERS → keep |
| `description` | `None` | `Continental reinforced concrete vault` | DIFFERS → keep |
| `is_manufactured` | `False` | `True` | DIFFERS → keep |

Identical shape for `Monticello Burial Vault`. `Graveside Setup Service` and
`Urn Vault - Standard` match no template by name at all.

⚠️ **"DIFFERS" conflates three different things, and only one is an override.**
`import_product_templates` copies six fields — name, description, sku, price,
unit_of_measure, is_active. It **does not copy `is_manufactured`**. So:

- `is_manufactured=False` against a template's `True` is the **column default**
  (NOT NULL, default false), never a decision. The rule would read it as a deliberate override
  and pin every Wilbert vault as not-manufactured, permanently, against the platform's own
  definition.
- `description=None` against a populated template is an **absent value**, not an override.
  Reading through would gain the description; keeping it preserves a blank.
- `sku` genuinely differs, but these particular values are demo artifacts.

**So the rule needs a third category — unset — distinct from equal and from differing.** The
natural discriminator is whether the copy path ever wrote the field: a field the copy function
does not touch cannot carry an override, so it should null regardless of value. That is
measurable from the six-field list rather than from the data.

⚠️ And the rule's input cannot be validated on Sunnycrest at all, because all four rows are
demo. A real validation needs a tenant provisioned through
`import_product_templates`; whether any tenant anywhere was is **not established**.

## 5. What this does not establish

- Whether the `x1y2z3a4b5c6` migration ever ran against production, or whether its 25 rows were
  removed. Production holds 37 and none of its categories; both are consistent with either.
- Whether any tenant in any environment was provisioned through `import_product_templates`.
- Whether production's 37 match Wilbert's own catalog, in names or in granularity. The names are
  a developer's; the xlsx pass is the check.
- Whether Sunnycrest has real products anywhere outside the demo set. Four production reads
  found none.
