# `is_manufactured` in production — the default never got overwritten

**2026-10-03.** Read-only production measurement, connection-level guard
(`default_transaction_read_only=on`, confirmed `on` before any data read).
Credentials not printed — `host=shuttle.proxy.rlwy.net port=57253 db=railway`.

Closes the `is_manufactured` set measurement outstanding from the 2026-10-02
dispatches, and confirms against production the defect that
`2026-10-02-platform-catalog-discrepancies.md` §4 predicted from two rows.

**Three results.**

1. **`products.is_manufactured` is `false` for all 33 rows in production, across
   all three tenants. There is not one `true` value anywhere.**
2. **Sunnycrest has 4 products and all 4 are `DEMO2-*`.** Non-demo: zero. The
   retraction in §3 of the discrepancies doc holds — production carries no real
   Sunnycrest product data.
3. ⚠️ **For Sunnycrest the value is correct by accident.** James buys every vault
   Sunnycrest sells and pours none of them, so `false` is right — and nothing
   measured it.

---

## 1. The measurement

```
Sunnycrest company rows: 1
  slug='sunnycrest'  name='Sunnycrest'  id=090e7eeb-3fa4-4268-8d4a-a4602c61196f

PRODUCTS for sunnycrest — total 4 (demo INCLUDED)
  DEMO* sku : 4
  non-DEMO  : 0

  sku            is_manufactured  source     name
  DEMO2-P001               False  manual     Monticello Burial Vault
  DEMO2-P002               False  manual     Continental Burial Vault
  DEMO2-P003               False  manual     Urn Vault - Standard
  DEMO2-P004               False  manual     Graveside Setup Service

  ALL rows       true=0  false=4  null=0  (n=4)
  DEMO only      true=0  false=4  null=0  (n=4)
  non-DEMO only  true=0  false=0  null=0  (n=0)
```

**Whole table, population boundary stated per CLAUDE.md §12:**

```
products, ALL tenants, demo INCLUDED: 33
  f60ef8de-…360956   rows=25   is_manufactured=true: 0
  36fe9f40-…b22079   rows=4    is_manufactured=true: 0
  090e7eeb-…c61196f  rows=4    is_manufactured=true: 0
```

## 2. ⚠️ The column has never been written by anything but its default

`u3v4w5x6y7z8` added `products.is_manufactured` as `nullable=False,
server_default=text("false")` via `op.add_column` on an already-populated table.
Every row in production still reads exactly that default. **33 of 33.**

So the column carries no information. It is not that the data is wrong — it is
that there is no data, wearing a boolean's clothes. This is the uniformity
corollary from DECISIONS 2026-10-03, confirmed empirically rather than argued:

> when a column holds a uniform value across every row of a table, that
> uniformity is a question, not a reassurance.

The question was asked here and the answer is that no writer exists. `source` is
`manual` on all four Sunnycrest rows, and `import_product_templates`
(`onboarding_service.py:1762-1794`) copies six fields and **is not one of them** —
so even the provisioning path that was supposed to populate a tenant catalog
would leave this column at its default.

## 3. ⚠️ Right for the wrong reason, which is the dangerous case

For Sunnycrest, `false` is the correct value. It is a Wilbert **licensee that
buys**: James purchases every vault it sells and pours none. So a reader checking
this column against reality would find it accurate and conclude it works.

**That conclusion would be false, and nothing downstream would contradict it** —
the *Conclusion survives, derivation falsified* shape in CLAUDE.md §11. The value
agrees with the world by coincidence of the default, not by measurement, and the
coincidence is tenant-specific:

- Bridgeable targets ~200 Wilbert licensees, and the network includes licensees
  that **do** pour. For every one of those, the default is wrong on every row,
  and it will be wrong silently at onboarding.
- `product_catalog_templates.is_manufactured` defaults to **`true`** (migration
  `x1y2z3a4b5c6:253`). So the platform tier and the tenant tier disagree by
  default on every product, in opposite directions.

That disagreement is exactly the input §4 of the discrepancies doc predicted
would misfire: a null-if-equal rule comparing tenant `False` against template
`True` reads "DIFFERS → keep" and pins every Wilbert vault as not-manufactured
permanently. **Confirmed against production now rather than inferred from two
rows.**

## 4. What this does not establish

- **Whether any licensee anywhere has a `true` value.** Three tenants exist in
  production and none does. There is no fourth to check.
- **What the correct value is for any tenant other than Sunnycrest.** `false` is
  right for a buying licensee; nothing here measures a pouring one.
- **Whether `is_manufactured` should be a tenant column at all.** The scoping
  document already notes it answers "do we make it" and not "who defined it", and
  the price-increase flow needs the second. Not revisited here.
- **Whether the 25-row tenant (`f60ef8de`) is real or seeded.** Its row count
  matches `seed_staging`'s 25 products exactly, which is suggestive and not
  measured. Stated as a question rather than a finding.
