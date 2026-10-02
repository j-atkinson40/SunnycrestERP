# What the product model already supports for a platform catalog

**2026-10-02.** Read-only. No code, no schema proposed. Scopes a platform-defined product
catalog with per-tenant enrollment against what exists.

**The headline is that this is not greenfield and not quite the pattern either.** Three of the
four pieces exist in some form. The one that does not is the one that matters most.

1. **Platform-tier product definitions already exist** — `product_catalog_templates`, no
   `company_id`, keyed by preset. The STOP condition does not fire.
2. ⚠️ **But they are COPIED into tenant rows, not enrolled.** There is no link from a tenant
   product back to its template, so a supplier price increase or a corrected spec cannot
   propagate to anyone already provisioned.
3. **Per-tenant product enablement already exists** — `wilbert_program_enrollments.enabled_product_ids`.
4. **An alias facility already exists** — `product_aliases`, with the exact shape a resolver needs.
5. ⚠️ **"Bronze Triune" vs "Bronze Triune Urn Vault" is settled: TWO SKUs**, by SKU prefix, not
   by inference from four production rows.

---

## 1. `products` — `company_id` is NOT NULL, and the convention is a separate table

```
company_id | character varying | NOT NULL | no default
```

⚠️ **The STOP asked whether a platform-tenant convention exists. It does, and it is not a
nullable tenant.** Platform-tier product definitions live in their own table,
`product_catalog_templates`, which has **no `company_id` column at all**:

```
id · preset · category · product_name · product_description
sku_prefix · default_unit · is_manufactured · sort_order · created_at
```

So the schema already answers the shape question by precedent — and it is a *different*
precedent from the other two instances of this pattern:

| Instance | Platform tier | Tenant tier | Resolution |
|---|---|---|---|
| Themes (`platform_themes`) | `scope` + nullable `vertical`/`tenant_id`, one table | same table | **READ time**, deltas only |
| Component config | same shape | same table | **READ time**, deltas only |
| Capture fields | `PLATFORM_DEFAULT_FIELDS` in code | `TenantCaptureConfig` | **READ time** |
| Personalization | platform question set | `enrollment.personalization_config.availability` | **READ time** |
| **Products** | `product_catalog_templates`, separate table | `products` | ⚠️ **WRITE time, by copy** |

**Products is the odd one out.** Every other instance resolves at read time so a platform
change propagates. Products copies at provision time so a platform change propagates to
nobody.

`products` carries 39 columns. Relevant ones already present: `is_manufactured` (NOT NULL,
default false), `source` (default `'manual'`), `wilbert_sku`, `wholesale_cost`,
`markup_percent`, `is_direct_ship_product`, `product_line`, `has_personalization`,
`personalization_tier`, `price`, `cost_price`. **There is no `template_id`, no
`catalog_template_id`, and no provenance column linking a row to its definition.**

## 2. `catalog_template_seeder.py` — three lists, and the table disagrees with them

```
WILBERT_BURIAL_VAULTS   19 entries   ("name", "SKU", "description")
WILBERT_URN_VAULTS      12 entries
CEMETERY_EQUIPMENT       6 entries
                        37 total, all seeded with preset="manufacturing"
```

⚠️ **THE DEV TABLE DOES NOT CONTAIN THEM.** Population: `product_catalog_templates` in
`bridgeable_dev`, whole table, 25 rows:

```
manufacturing | Burial Vaults       8
manufacturing | Redi-Rock           6
manufacturing | Rosetta Hardscapes  4
manufacturing | Wastewater          7
```

Eight burial vaults against the seeder's nineteen, **no Urn Vaults category at all**, no
Cemetery Equipment, and three categories the seeder never mentions. So either
`seed_wilbert_templates` has not run on this database or something else writes the table.
Its only caller is `app/main.py:274-275`, a startup hook. Not established which; stated as a
discrepancy rather than resolved.

### ⚠️ The Bronze Triune question is settled here, and the answer is two SKUs

```python
WILBERT_BURIAL_VAULTS:  ("Bronze Triune Burial Vault", "BV-BTRI", …)
WILBERT_URN_VAULTS:     ("Bronze Triune Urn Vault",    "UV-BTRI", …)
```

Distinct SKUs under distinct prefixes — `BV-` for burial, `UV-` for urn. Both lists carry the
same pattern for Copper Triune, Stainless Steel Triune, Cameo Rose Triune, Veteran, Salute,
Monticello, Venetian and Graveliner, so it is a systematic naming scheme rather than a
coincidence of two rows.

So the earlier production-derived hypothesis was right and is now evidenced from the catalogue
rather than from four rows: **a vault and an urn vault are different products.** And
`sunnycrest_product_seeder`'s bare `"Bronze Triune"` is a third thing — neither of these, and
not resolvable to one of them without a decision.

## 3. `wilbert_program_enrollments` — per-tenant product enablement already exists

```
id · company_id · program_code · program_name · is_active
territory_ids · uses_vault_territory · enabled_product_ids ⚠️
metadata · program_type · fulfillment_path
personalization_config · permissions_config · notifications_config
fulfillment_config · payout_config · created_at · updated_at
```

**`enabled_product_ids` (json) is the enrollment field this design needs, already present.**
It is live, not dead: read in 4 files, written through `programs.py:147` and `:195` and
accepted by `onboarding_flow.py:57`.

It also already holds `personalization_config` — the per-licensee availability layer that
DECISIONS 2026-09-22 ruled on. So **the enrollment row is already the per-tenant overlay for
one product-adjacent concern**, which is the strongest argument that products belong there
too rather than in a new table.

What would break if products were added: not established. `enabled_product_ids` holds product
ids, and today those ids are *tenant* product rows, not platform definitions. Pointing it at
platform definitions changes what the ids mean to every existing reader.

## 4. Onboarding provisioning — the copy seam, named

`onboarding_service.import_product_templates(db, tenant_id, items)` at `:1762-1794`, reachable
from `tenant_onboarding.py:202`:

```python
        template = db.query(ProductCatalogTemplate).get(template_id)
        product = Product(
            company_id=tenant_id,
            name=template.product_name,
            description=template.product_description,
            sku=sku or (template.sku_prefix if template.sku_prefix else None),
            price=price,
            unit_of_measure=template.default_unit,
            is_active=True,
        )
```

⚠️ **This is the whole provisioning path and it is a one-way copy.** Six fields move; nothing
records where they came from. After it runs, the tenant product and the platform definition
are unrelated rows.

**Consequences for the two flows named in the dispatch**, both following from the missing link
rather than from anything else:

- A **supplier price increase** cannot find the tenant rows it should reprice.
- A **corrected spec** — 86″ where Wilbert says 88″ — cannot reach a provisioned tenant. The
  driver at the graveside is downstream of exactly this.

⚠️ Note the endpoint calls `tenant_onboarding_service.import_product_templates`, while the
function quoted above is in `onboarding_service`. Two modules, similar names. I read the
latter; whether they are the same function or two implementations is **not established**, and
it matters, because two copy paths would drift.

## 5. Pricing — per tenant, confirmed rather than assumed

`products.price` and `products.cost_price` sit on the tenant-owned row, so price is per tenant
by construction. `product_catalog_templates` carries **no price column** — the platform
defines the product and says nothing about what it costs, which matches the stated practice.

A separate per-customer layer exists (`price_list_items`, `price_list_versions`), so "one price
per product for all customers" is the *products* table's shape and not the whole system's.
Whether any tenant uses the price-list layer to vary price by customer was not measured.

## 6. Make-vs-buy — `is_manufactured` exists

`products.is_manufactured`, boolean, **NOT NULL, default false**. Supported by
`wholesale_cost`, `markup_percent`, `is_direct_ship_product` and `source`.

So the distinction the price-increase flow needs is present on the tenant row. ⚠️ What is
absent is **provenance** — whether the *definition* is platform-owned or tenant-authored.
`is_manufactured` answers "do we make it", not "who defined it", and the price-increase flow
needs the second. `product_catalog_templates.is_manufactured` exists too, so the make-vs-buy
fact is already modelled at both tiers while ownership is modelled at neither.

## 7. Aliases — the facility exists and has the right shape

`product_aliases`:

```
id · company_id · alias_text · alias_text_normalized ⚠️
canonical_product_id · historical_product_id
confidence · source · is_confirmed · created_at
```

`alias_text_normalized → canonical_product_id`, with a confidence score and a confirmation
flag, plus `ImportAliasService` (`app/services/import_alias_service.py`). **This is what a
vault-name resolver would otherwise have had to invent.**

Population: **1 row** in `bridgeable_dev`, all tenants — so the table is essentially unused
and its behaviour under load is unmeasured. It is `company_id`-scoped, meaning aliases are
per tenant today; a platform-level alias ("Bronze Triune" → `BV-BTRI` for everyone) has no
place in it as shaped.

## 8. What this does not establish

- Whether `seed_wilbert_templates` has ever run, or what wrote the 25 dev rows (§2).
- Whether `onboarding_service` and `tenant_onboarding_service` hold one copy path or two (§4).
- What would break if `enabled_product_ids` pointed at platform definitions (§3).
- Whether any tenant uses `price_list_items` to vary price by customer (§5).
- Production's `product_catalog_templates` contents. Dev only was read; the 4 authoritative
  Sunnycrest product rows were measured in the prior investigation, not these templates.
