# 2b-3 Part 0 — repointing the four consumers. Map only, no code.

**2026-10-03.** Read-only. The first phase today where behaviour actually changes:
everything since r186 has been additive and nothing reads the new catalog.

**Five results, and two of them change the plan.**

1. ⚠️ **One of the four is not a consumer.** `catalog_template_seeder` is a
   **WRITER**, and it must be repointed **LAST**, not first — it is what populates
   the table the other three still read.
2. ⚠️ **All three real consumers want VARIANTS, not products.** The old 37 flat rows
   ARE variants. Repointing any of them to `product_templates` would silently
   collapse 37 sellable things into 21 kinds.
3. **The mapping is 1:1 and total.** All 37 old `sku_prefix` values match a new
   variant `sku` exactly. **0 absent, 0 ambiguous.**
4. ⚠️ **`price_list_analysis_service` classifies by STRING-MATCHING product names**,
   and the new catalog has a `form` column that answers the same question directly.
   The new rows break the string match.
5. **No consumer branches on `is_manufactured`.** r196 introduces no third case.

---

## 1. The four, as they actually are

| # | site | kind | reachable from | risk |
|---|---|---|---|---|
| 1 | `price_list_analysis_service.py:749` | reader | `price_list_import.py:50` (live) | **lowest** |
| 2 | `onboarding_service.py:1752` `get_product_templates` | reader | `tenant_onboarding.py:181` (live) | medium |
| 3 | `onboarding_service.py:1762` `import_product_templates` | reader → **writes tenant rows** | `tenant_onboarding.py:202` (live) | **highest** |
| 4 | `catalog_template_seeder.py:81-120` | ⚠️ **WRITER** | `main.py:275`, gated on `PLATFORM_ADMIN_*` | — |

⚠️ **#2 IS reachable.** An earlier note recorded `get_product_templates` as
re-exported but uncalled. It is called — `tenant_onboarding.py:181` defines a route
handler of the same name that delegates to it. The grep that missed it excluded the
re-export lines and so excluded the route too.

## 2. Consumer by consumer

### 1. `price_list_analysis_service.analyze_price_list`

**(a) Reads.** `ProductCatalogTemplate` filtered `preset == "manufacturing"`,
`.all()` → **list** of ORM objects. Uses four columns: `id`, `product_name`,
`category`, `sku_prefix`.

**(b) Does.** Formats them into a newline-joined string `catalog_ref` and puts it
in an LLM prompt. The model returns `items[].match.template_name` /
`template_id`. **The consequence is the quality of a Claude match**, which a human
then reviews — the output lands in the price-list import tables, never directly in
`products`.

⚠️ **Then it post-processes** (`:400-445`) to fix urn-vs-burial confusion, building
its lookups by **string-matching the product name**:

```python
if "urn vault" in name_lower:   base = name_lower.replace(" urn vault", "")
elif "burial vault" in name_lower:  burial_template_ids.add(t.id)
```

**(c) Changes.** The prompt would carry **52 variants instead of 37 rows**, and the
string classifier meets names it cannot classify:

| new name | old classifier says | truth |
|---|---|---|
| `Country Bouquet`, `Jewel`, `Arlington`, `Regal Line`… | neither | **urns** — a form that did not exist |
| `Wilbert Bronze` | neither | burial vault |
| `Graveliner`, `Graveliner (Social Service)` | neither | grave liner |
| `Loved & Cherished 19"` | neither | infant |

Under the old 37 these were classified by accident, because every burial vault name
ended in "Burial Vault". **That accident is gone.**

⚠️ **The fix is not a better string match — it is `t.form`.** The new catalog
carries the classification as a column (`burial_vault`, `urn_vault`, `grave_liner`,
`infant`, `equipment`, `urn`). The entire `:400-445` pass becomes a column read.

⚠️ **`WILBERT_VARIATIONS` (`:88-100`) is a hand-written alias list in a prompt
string** — "Monticello: MON, Monti…". That is exactly what `platform_product_aliases`
(r189/r191) exists to hold. Not in scope for the repoint; recorded because the
repoint is when someone will notice it.

**(d) Wants: VARIANTS.** It matches price-list line items, and a line item is a
sellable thing. Products would offer "Triune Burial Vault" where the price list says
"Bronze Triune".

### 2. `onboarding_service.get_product_templates`

**(a) Reads.** Optional `preset` / `category` filters, `.order_by(sort_order).all()`
→ **list** of ORM objects, returned whole.

**(b) Does.** Serves the product-library list a tenant admin browses during
onboarding and ticks to import. **The consequence is what a new licensee is
offered.**

**(c) Changes.** 37 → 52 entries. ⚠️ **`category` has no counterpart.** The new
catalog has `family_slug` (16 families) and `form` (6 values); the old `category`
was 3 values — "Burial Vaults", "Urn Vaults", "Cemetery Equipment". `form` is the
closest and is **not the same partition**: it splits `grave_liner`, `infant` and
`urn` out of what used to be two buckets.

⚠️ **AND `category` IS A PUBLIC QUERY PARAMETER, not an internal filter.** Verified:

```python
@router.get("/product-library")
def get_product_library(
    preset: str | None = Query(None),
    category: str | None = Query(None),   # ← exposed
```

So changing its vocabulary is an **API contract change**, not a refactor. A client
passing `?category=Burial Vaults` gets an empty list rather than an error — the
filter simply matches nothing. **Silent, not loud**, which is the worst form.
Whatever step 2 does with `category` has to be decided rather than inherited:
translate the three old values, accept both vocabularies for a window, or change
the parameter and version the endpoint.

**(d) Wants: VARIANTS**, grouped by product for display. A licensee picks "Bronze
Triune Burial Vault", not "Triune Burial Vault".

### 3. `onboarding_service.import_product_templates`

**(a) Reads.** `db.query(ProductCatalogTemplate).get(template_id)` — one row per
requested id. Uses `product_name`, `product_description`, `sku_prefix`,
`default_unit`.

**(b) Does.** ⚠️ **CREATES `Product` ROWS IN THE TENANT'S CATALOG.** Six fields
copied; `is_active=True`; `price` from the request. **This is the highest-consequence
of the four — it writes persistent tenant data on the path a new licensee walks.**

**(c) Changes.** `template_id` becomes a **variant** id. ⚠️ **And this is where
`variant_template_id` finally earns its declaration**: the new `Product` row should
carry `variant_template_id=<variant.id>`, which is the link r186 added and nothing
could set because the column had no ORM attribute until r196.

The copied fields move tier: `product_name` → the **variant's** `display_name`
(the exact source name, e.g. `Bronze Triune Burial Vault`); `product_description`
→ ⚠️ lives on **both** tiers in the new catalog and the product's is usually NULL —
decide which, and NULL-on-the-variant should fall through to the product rather
than writing NULL.

⚠️ **AND DO NOT COPY `is_manufactured`.** It is not copied today (the six-field list
omits it) and it must stay omitted. Copying the template's value would convert the
onboarding **pre-fill** into an **answer** silently — reinstating exactly the defect
r196 removed, this time with a provenance trail making it look measured. The
acceptance is the measurement; the pre-fill is not.

**(d) Wants: VARIANTS.** It creates one product row per selected sellable thing.

### 4. `catalog_template_seeder.seed_wilbert_templates` — ⚠️ a WRITER

**(a) Reads.** Only `existing` — a set of `product_name` values, for idempotency.

**(b) Does.** **Inserts up to 37 rows into `product_catalog_templates`** on startup,
gated on `PLATFORM_ADMIN_EMAIL` **and** `PLATFORM_ADMIN_PASSWORD` being set. That
gate is why it has never run on dev, and why dev holds 25 migration-sourced rows
while production holds these 37.

**(c) Changes.** The new catalog is populated by **migrations** (r188, r195) —
versioned, reproducible from empty, and already applied to production. So this
seeder has no counterpart to be repointed to: its job is done by the migration
chain. **The change is deletion, not repointing.**

⚠️ **AND IT MUST GO LAST.** It is what populates the table consumers 1–3 still read.
Deleting it before they are repointed leaves any fresh environment with an empty
`product_catalog_templates` and three consumers reading nothing.

**(d) Wants: neither.** It is not a consumer.

## 3. The mapping — 37 old rows, matched on SKU

**Second signal: `sku_prefix` → `sku`, not name.** The name match is corroboration.

**Result: 37 of 37 `mapped`. 0 `absent`. 0 `ambiguous`.**

Every old `sku_prefix` is a new variant `sku` exactly. That is not luck — r188 built
the variants from this same source — but it was verified rather than assumed.

| old row (`sku_prefix` · `product_name`) | new variant | new product | form |
|---|---|---|---|
| `BV-WBR` Wilbert Bronze Burial Vault | `BV-WBR` | Wilbert Bronze | burial_vault |
| `BV-BTRI` Bronze Triune Burial Vault | `BV-BTRI` | **Triune Burial Vault** | burial_vault |
| `BV-CTRI` Copper Triune Burial Vault | `BV-CTRI` | **Triune Burial Vault** | burial_vault |
| `BV-SSTRI` Stainless Steel Triune Burial Vault | `BV-SSTRI` | **Triune Burial Vault** | burial_vault |
| `BV-CRTRI` Cameo Rose Triune Burial Vault | `BV-CRTRI` | **Triune Burial Vault** | burial_vault |
| `BV-VTRI` Veteran Triune Burial Vault | `BV-VTRI` | **Triune Burial Vault** | burial_vault |
| `BV-WTRIB` White Tribute Burial Vault | `BV-WTRIB` | **Tribute Burial Vault** | burial_vault |
| `BV-GTRIB` Gray Tribute Burial Vault | `BV-GTRIB` | **Tribute Burial Vault** | burial_vault |
| `BV-WVEN` White Venetian Burial Vault | `BV-WVEN` | **Venetian Burial Vault** | burial_vault |
| `BV-GVEN` Gold Venetian Burial Vault | `BV-GVEN` | **Venetian Burial Vault** | burial_vault |
| `BV-CON` Continental Burial Vault | `BV-CON` | Continental Burial Vault | burial_vault |
| `BV-MON` Monticello Burial Vault | `BV-MON` | Monticello Burial Vault | burial_vault |
| `BV-SAL` Salute Burial Vault | `BV-SAL` | Salute Burial Vault | burial_vault |
| `BV-MRC` Monarch Burial Vault | `BV-MRC` | Monarch Burial Vault | burial_vault |
| `GL-STD` Graveliner | `GL-STD` | **Graveliner** | ⚠️ grave_liner |
| `GL-SS` Graveliner (Social Service) | `GL-SS` | **Graveliner** | ⚠️ grave_liner |
| `LC-19` Loved & Cherished 19" | `LC-19` | **Loved & Cherished** | ⚠️ infant |
| `LC-24` Loved & Cherished 24" | `LC-24` | **Loved & Cherished** | ⚠️ infant |
| `LC-31` Loved & Cherished 31" | `LC-31` | **Loved & Cherished** | ⚠️ infant |
| `UV-BTRI` Bronze Triune Urn Vault | `UV-BTRI` | **Triune Urn Vault** | urn_vault |
| `UV-CTRI` Copper Triune Urn Vault | `UV-CTRI` | **Triune Urn Vault** | urn_vault |
| `UV-SSTRI` Stainless Steel Triune Urn Vault | `UV-SSTRI` | **Triune Urn Vault** | urn_vault |
| `UV-CRTRI` Cameo Rose Triune Urn Vault | `UV-CRTRI` | **Triune Urn Vault** | urn_vault |
| `UV-VET` Veteran Urn Vault | `UV-VET` | **Triune Urn Vault** | urn_vault |
| `UV-UCG` Universal Urn Vault (Cream & Gold) | `UV-UCG` | **Universal Urn Vault** | urn_vault |
| `UV-UWS` Universal Urn Vault (White & Silver) | `UV-UWS` | **Universal Urn Vault** | urn_vault |
| `UV-WVEN` White Venetian Urn Vault | `UV-WVEN` | **Venetian Urn Vault** | urn_vault |
| `UV-GVEN` Gold Venetian Urn Vault | `UV-GVEN` | **Venetian Urn Vault** | urn_vault |
| `UV-SAL` Salute Urn Vault | `UV-SAL` | Salute Urn Vault | urn_vault |
| `UV-MON` Monticello Urn Vault | `UV-MON` | Monticello Urn Vault | urn_vault |
| `UV-GL` Graveliner Urn Vault | `UV-GL` | Graveliner Urn Vault | urn_vault |
| `CE-LD` Lowering Device | `CE-LD` | Lowering Device | equipment |
| `CE-CT` Cremation Table | `CE-CT` | Cremation Table | equipment |
| `CE-TS` Cemetery Tent - Single | `CE-TS` | **Tent** | equipment |
| `CE-TD` Cemetery Tent - Double | `CE-TD` | **Tent** | equipment |
| `CE-GM` Grass Mats | `CE-GM` | Grass Mats | equipment |
| `CE-CH` Graveside Chairs | `CE-CH` | Graveside Chairs | equipment |

**Bold** = several old rows collapse onto one product. Nine products take more than
one; twelve take exactly one. **21 products receive the 37 rows** — which is the
whole argument for (d): a consumer repointed to products sees 21 where it saw 37.

### One name drift, and it is deliberate

| sku | old `product_name` | new variant `display_name` |
|---|---|---|
| `UV-VET` | `Veteran Urn Vault` | **`Veteran Triune Urn Vault`** |

r195's ruled rename — the price list and the tenant seeder both say "Veteran
Triune"; the old table and the spec sheet were the outliers. ⚠️ **The SKU is
unchanged and permanent**, so any consumer keyed on `sku_prefix` is unaffected and
only a consumer keyed on the NAME would see this.

### 15 variants exist that no old row names

`BV-CON34`, `GL-34`, `GL-38` (odd sizes, r195) and the twelve stocked urns `P300`,
`P300P`, `P300WS`, `P310`, `P310P`, `P310WS`, `P363`, `P440`, `P440A`, `P440B`,
`P445`, `P600` (r195).

**These are additions, not mismatches** — every one appears on the Feb 1 2026 price
list and none existed in the old table. Each repointed consumer **newly sees** them:
the price-list prompt gains twelve urns it could previously never match, and the
onboarding library gains fifteen things a licensee can select.

## 4. `is_manufactured` — no consumer branches on it

| file | occurrences | what |
|---|---|---|
| `price_list_analysis_service.py` | 0 | — |
| `onboarding_service.py` | 0 | ⚠️ `import_product_templates` does **not** copy it, and must continue not to |
| `catalog_template_seeder.py` | 3 | **writes** it: `True`/`True`/`False` per category |

**r196 introduces no third case for any consumer.** The only code that touches the
column writes it, and that file is being deleted rather than repointed.

## 5. Order — reassessed after reading all four

**`price_list_analysis_service` is still the right first step, and now for a reason
I could not have given before reading the others.**

It is the only one of the four whose output is a **prompt**. A bad repoint degrades
match quality, which surfaces in a human review step that already exists, and writes
nothing to `products`. The other two readers either show a list a licensee chooses
from or create persistent tenant rows.

Proposed order, one consumer per commit:

1. **`price_list_analysis_service`** — prompt only; replace the string classifier
   with `t.form` in the same commit, since the repoint breaks it.
2. **`get_product_templates`** — read-only list; resolve the `category` filter,
   which has no counterpart.
3. **`import_product_templates`** — writes tenant rows; sets `variant_template_id`.
4. **`catalog_template_seeder`** — ⚠️ **delete, LAST.** It populates the table 1–3
   read until they are repointed and green.

⚠️ **`product_catalog_templates` is NOT dropped.** That is Phase 3, after all four
are done and green.

## 6. What this does not establish

- **Whether any tenant has ever been provisioned through
  `import_product_templates`.** Still unestablished, carried from
  `2026-10-02-platform-catalog-discrepancies.md` §4. It decides whether step 3 has
  live data behind it or is a cold path.
- **What `category` should become.** `form` is the closest and is a different
  partition; a caller passing `category="Burial Vaults"` has no exact successor.
- **Whether the price-list prompt gets better or worse with 52 entries.** More
  candidates could improve recall or dilute matching. Measurable after step 1, not
  before.

---

# Ruling, 2026-10-03 — unit of measure is a precast-vertical concern

Commit 2 removed the `per <unit>` display because the new catalog has no unit
column and the old `default_unit` was not uniform. **The row that made it
non-uniform has now been identified, and it settles the question.**

## The measurement

```
dev        Burial Vaults        each  8
           Redi-Rock            each  6
           Wastewater           each  7
           Rosetta Hardscapes   each  3
           Rosetta Hardscapes   sqft  1   ← `Rosetta Pavers` / `RH-PAV`

production Burial Vaults        each 19
           Urn Vaults           each 12
           Cemetery Equipment   each  6
           rows whose unit is NOT 'each': 0
```

**The single exception in either environment is `Rosetta Pavers`, a hardscape
paver sold by the square foot** — from the Rosetta vertical, which is deferred
until the funeral side is live.

## The ruling

**Unit of measure is a PRECAST-VERTICAL concern. Every funeral-side product is
sold `each`. The column gets added when that vertical lands — not now, and not as
a hardcoded default.**

Production carries 37 funeral rows and **zero** of them is anything but `each`, so
nothing in the funeral catalog needs the field today. A paver is the one shape that
does, and pavers are not shipping.

⚠️ **The removal stands either way, and this ruling is why it was a REMOVAL rather
than a default.** Rendering a hardcoded `"each"` would have been a guess wearing the
old field's clothes — correct for 37 of 37 production rows and wrong the first time
a paver appears, with nothing to distinguish "measured as each" from "we assumed".
That is the `is_manufactured` defect exactly: a plausible value filling a column
nobody measured. The blank is the honest state until the vertical that needs the
field arrives with it.

⚠️ **AND IT WAS CONFIRMED RATHER THAN INHERITED.** The hypothesis — "the sqft row is
probably a hardscape item" — was supplied and was correct, and was still checked
against both databases before being recorded. A ruling resting on a plausible guess
about a single row is the shape this arc has spent the day catching.
