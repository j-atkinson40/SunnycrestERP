# Before the catalog import: r185 confirmed, Monticello answered, and a third catalog

**2026-09-22, 15:50–16:05 UTC.** Read-only. No dry-run built, no write attempted.
**Stopping on a premise, not on a listed STOP line** — the reason is in §4.

---

## 0. r185 is on production and did what it said

Read-only, `SHOW transaction_read_only` = on.

| | |
|---|---|
| alembic head on production | **`r185_personalization_record_v2`** |
| `schema_version` | **2** |
| `answers.nameplate_cover_emblem` | **`cover_emblem_only`** |
| `legacy_v1_options` | `{"vinyl": null, "legacy_print": null, "physical_emblem": {}, "physical_nameplate": null}` — the v1 object verbatim |
| `options` (the v1 key) | gone |
| `vault_product_name` | `Monticello Standard` — untouched, per the ruling |
| `emblem_key` / `name_display` | `patriotic_flag` / `JOHN M. SMITH` — preserved |

Matches `eecba049`'s before-and-after exactly.

⚠️ **The fallback count was NOT read from the deploy log** — I did not retrieve
Railway's deploy output. It is derived instead: the row's `vinyl` is `null`, so
`_vinyl_answer` returns `none` before reaching the fallback, and the counter
cannot have moved. That is an inference from the data, not a reading of the log,
and it is reported as such.

---

## 1. Monticello — the STOP does not fire, and the reason is not the expected one

**A spoken "Monticello" resolves to nothing at all today. There is no
capture→product link to resolve it wrongly.**

`call_extraction_service.create_draft_order_from_extraction` builds a
`SalesOrder` with customer, cemetery, deceased name, scheduled date and service
time — and **no order line and no product id**. `vault_type` is stored as a
string on `ringcentral_call_extractions.vault_type` and never becomes a product
reference. The function resolves `_resolve_customer_id` and
`_resolve_cemetery_id`; there is no `_resolve_product_id`.

So the risk named in the dispatch is real and is not yet reachable: it becomes
live the moment anything resolves `vault_type` to a product, which is work the
capture schema will do.

### The exclusion mechanism exists and is honoured

| | |
|---|---|
| flag | **`Product.is_active`** — Boolean, default True (`models/product.py:33`) |
| the name matcher | `ImportAliasService.match_products` filters `Product.is_active == True` |
| the product picker | `GET /products/` takes `include_inactive: bool = Query(False)` — inactive excluded by default |

Setting the four `DEMO2-*` products inactive would exclude them from both
selection and name matching, non-destructively and reversibly. **No STOP.**

⚠️ **But a flag is not a guarantee across 63 call sites.** Of 63 `query(Product)`
sites under `app/`, 39 do not filter `is_active` within six lines. That count is
a crude heuristic and it mislabelled at least one case — `import_alias_service`
appeared unfiltered at one site while the matcher itself filters correctly. The
honest statement is: the two paths that matter are covered, and the remaining
sites have not been classified one by one. Doing that is its own piece of work.

---

## 2. What the portal has that Sunnycrest's catalog would need

Unchanged from `46b95099` and not re-derived here beyond confirming the file is
the same snapshot: per-vault `hasPersonalization` and `personalizationFields`,
16 burial vaults and 10 urn vaults, no prices, no SKUs, single-tenant.

---

## 3. ⚠️ THERE IS ALREADY A REAL SUNNYCREST CATALOG IN THIS REPO

`backend/app/services/sunnycrest_product_seeder.py`, 339 lines, idempotent by
construction (`_product_exists` guards each insert), with **real prices**:

```
Wilbert Bronze 13452.00 · Bronze Triune 3864.00 · Copper Triune 3457.00
SST Triune 2850.00 · Cameo Rose 2850.00 · Veteran Triune 2850.00
Tribute 2570.00 · Venetian 1934.00 · Continental 1607.00 · Salute 1475.00
Monticello 1405.00 · Monarch 1176.00 · Graveliner 996.00 · Graveliner (SS) 880.00
Continental 34" 2179.00 · Graveliner 34" 1492.00 · Graveliner 38" 2060.00
Loved & Cherished 19"/24"/31" 239.00 / 374.00 / 452.00 · Pine Box (no price)
… plus urn vaults
```

It reaches production only through `POST /api/v1/products/seed-sunnycrest`,
gated on `products.create`. **It has never been run there** — production holds
four `DEMO2-*` products.

This is the unprovisioned-entrance shape again: complete machinery, correct,
reachable, never invoked.

### Why this stops the import as scoped

The dispatch says *"Seed Sunnycrest's real vault catalog and personalization
availability from the ordering portal."* Against this seeder that would create a
**third** definition of the same catalog:

| source | products | prices | per-vault availability |
|---|---|---|---|
| `sunnycrest_product_seeder.py` | yes, with infant and bought-in sizes | **yes** | no |
| the ordering portal | yes, 16 + 10 | **no** | **yes** |
| `PERSONALIZATION_TIERS` | no | no | by tier, platform-wide |

⚠️ **Importing products from the portal would duplicate a catalog the repo
already has, and would lose the prices.** That is the two-copies problem this arc
has spent two commits on — and the portal's print catalog has already
demonstrated what happens when one list is transcribed twice.

**The portal's unique contribution is availability, not products.** The obvious
split — products and prices from the existing seeder, per-vault availability from
the portal — is a different import from the one dispatched, so it is named here
rather than built.

⚠️ **And the three name sets have not been reconciled.** The seeder says
`SST Triune`, `Tribute`, `Graveliner (SS)`, `Pine Box`; the portal says
`Stainless Steel Triune®`, `White Tribute`/`Gray Tribute`, `Concrete Graveliner`,
`Other`. Keying an import on display name across these would mismatch. The
portal ids are stable; the seeder has no ids at all, only names — so **the join
between the two sources is itself undesigned**, and that is the first thing the
real import has to solve.

---

## 4. Why I stopped here

None of the listed STOP lines fired. What stopped me is that Part 2's source is
in question: building a portal→catalog import now would create a third catalog
and discard the prices, and I would be choosing between two sources on James's
behalf.

**Decisions needed before the import is written:**

1. **Products from which source?** The existing seeder (has prices, no ids, no
   availability) or the portal (has ids and availability, no prices) or both.
2. **What joins them?** The seeder's names and the portal's ids do not
   correspond, and three names differ outright.
3. **Should `seed-sunnycrest` simply be run on production?** It is idempotent and
   already written. If it should, that is a production write and James's, and it
   makes the import a much smaller piece — availability only.
4. **DEMO2 exclusion**: `is_active = False` on the four is available and
   sufficient for the two paths that matter. It is still a production write.

Parts 1, 2 and 4 are unstarted. Part 4's dry-run in particular depends on which
Salute row exists after (3) is decided, so producing it now would describe a
product that may not be the one that ends up there.
