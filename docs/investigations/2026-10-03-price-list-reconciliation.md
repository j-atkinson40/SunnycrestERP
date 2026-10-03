# Reconciling the Feb 1 2026 price list against the platform catalog

**2026-10-03.** Read-only. No migration, no writes. Reconciles
`docs/catalog/2026-02-01-sunnycrest-funeral-price-list.pdf` (md5
`ab3fb519423c09fd766b0a265f288cee`) against the 21 products / 37 variants loaded
by r186–r193.

**Authority (James, 2026-10-03):** *"Do what our price list says."* The price list
is authoritative for catalog **membership** and **organization**. The spec sheet
remains authoritative for **dimensions only**. Where they disagree about whether
something exists or what it is called, the price list wins.

**Six results.**

1. ⚠️ **The spec sheet's six "non-manufactured" rows are NOT the price list's four
   ODD SIZED items.** Different names, different count. 2b-3's product list is dead.
2. ⚠️ **`sunnycrest_product_seeder` already matches the price list exactly** — all
   four ODD SIZED items, at the price list's prices, with SKUs.
3. ⚠️ **Our own catalog contains a one-product-two-names defect**: `UV-VET`
   "Veteran Urn Vault" against every sibling's "… Triune Urn Vault".
4. **Reinforcement needs no schema change.** `product_templates.reinforcement`
   already exists, nullable, and is NULL on all 21.
5. **The r193 Universal/Salute split was already correct.** Size of correction: zero.
6. **Twelve stocked urns and five graveside packages have no catalog counterpart.**

---

## 1. Part 0 — the ORM gap, and its siblings

`variant_template_id` is now declared on `app/models/product.py`. It was added by
**r186** and had no model attribute, so nothing could resolve a tenant product to
its platform definition — the link the whole design turns on.

Every column added by r186–r193, against its model:

| table | db | model | missing from model |
|---|---|---|---|
| `product_families` | 7 | 7 | — |
| `product_templates` | 20 | 20 | — |
| `product_variant_templates` | 19 | 19 | — |
| `platform_product_aliases` | 8 | 8 | — |
| `products` | 40 | 37 | `is_manufactured`, `tax_rate_override_id`, `taxability` |

The four new tables are complete. The three remaining on `products` are left
deliberately: `is_manufactured` is ruled NULL and pending;
`tax_rate_override_id` and `taxability` are from `s3a4b5c6d7e8_add_tax_system`
and predate this arc.

⚠️ **`assert_no_schema_drift` cannot catch this direction and says so.** Its
docstring: *"DB-extra columns/tables are noise, not breakage — ignored."* It is
model→DB only by design, so every column a migration adds and nobody declares is
invisible to it. Closing that blind direction — DB-extra as noise only when on a
named legacy list — is queued, not done here.

## 2. Part 1 — extraction verified against the rendered pages

Text extraction of a designed two-column PDF scrambled two blocks. Both pages
were rasterized at 200 dpi and read; **both scrambles were grouping errors, and
neither changed a value.**

| extraction artifact | what the page shows |
|---|---|
| `'P310P - Pebble Dust\nUniversal Line'` as one left-column block | `Universal Line` is a **left**-column URN VAULTS heading; `P310P - Pebble Dust $118` is a **right**-column Tribute Line urn |
| `'$462\nP363 - Victorian'` | `P363 - Victorian $212` and `P600 - Arlington $462` are separate rows |

No other line item, price or heading disagreed between extraction and page.

**The verified price list — 54 items.** Burial Vaults: Wilbert Bronze $13,452
(Triple); Bronze Triune $3,864, Copper Triune $3,457, SST Triune $2,850, Cameo
Rose $2,850, Veteran Triune $2,850 (Double); Tribute $2,570, Venetian $1,934,
Continental $1,607, Salute $1,475, Monticello $1,405 (Single); Monarch $1,176,
Graveliner $996, Graveliner(SS) $880 (Non). Odd Sized: Continental 34" $2,179,
Graveliner 34" $1,492, Graveliner 38" $2,060, Pine Box "Call Office". Loved &
Cherished: 19" $239, 24" $374, 31" $452. Urn Vaults: Bronze Triune $855, Copper
Triune $835, SST Triune $822, Cameo Rose $822, Veteran Triune $822 (Double);
Venetian $616, Monticello $493 (Single); Salute $436, Graveliner $284 (Non);
Universal Line Cream & Gold $510, White & Silver $510. Urns We Stock: P445 $151,
P440 $142, P440A $142, P440B $142, P363 $212, P600 $462; Regal Line P300 $124,
P300WS $110, P300P $113; Tribute Line P310 $135, P310WS $111, P310P $118.
Graveside Service (with/without our product): Full Equipment $300/$600, Lowering
Device & Grass $185/$487, Lowering Device Only $140/$487, Tent Only $225/$557,
Extra Chairs (over 8) $5/$8. Other Charges: Sunday & Holiday $550, Saturday
Spring Burial $200, Late Arrival per ½ hr $75, Legacy Rush Fee $100, Late Notice
$250.

⚠️ **Read off the page, not inferred:** `Lowering Device & Grass` and `Lowering
Device Only` carry the **same** without-our-product price, $487. That is what the
document says. Flagged as a possible source typo; not corrected.

## 3. Part 2 — the three sets

**Matched on NAME *and* FORM.** ⚠️ **Price is not an available second signal**: the
platform tier has no price column at all (price lives on the tenant `products`
row), so the dispatch's offered signal does not exist here. Spec presence is
reported as a third signal where r193 loaded one. Every alias used is **declared**
with its justification — no fuzzy matching.

**Detector break-tested.** Forbidding a known match (`UV-MON`, then `BV-CON`) from
matching while leaving it in the catalog moved it into set (c) and its price-list
counterpart into set (b), 27/27/7 → 26/28/8 both times.

### Set (a) — on both: 27 price-list items

All burial vaults, all urn vaults, all three Loved & Cherished sizes, and both
Universal finishes match. Four required a declared alias: `SST Triune` →
Stainless Steel, `Graveliner(SS)` → Social Service, `Cream & Gold`/`White &
Silver` → the Universal finishes, and the three L&C sizes.

⚠️ **Three price-list items are one-to-two against the catalog**, which is a real
disagreement rather than a matching failure:

| price list | catalog | note |
|---|---|---|
| `Tribute` $2,570 | `BV-WTRIB` White + `BV-GTRIB` Gray | one price, two finishes |
| `Venetian` $1,934 | `BV-WVEN` White + `BV-GVEN` Gold | one price, two finishes |
| `Venetian` $616 (urn) | `UV-WVEN` White + `UV-GVEN` Gold | one price, two finishes |

The price list does not split these by finish. Either the finishes are not
separately orderable, or the price list omits a distinction it charges the same
for. **Not resolved here.**

### Set (b) — price list only: 27 items

- **Odd Sized (4):** Continental 34", Graveliner 34", Graveliner 38", Pine Box
- **Urns We Stock (12):** the P-numbered items — no `urn` form exists
- **Graveside Service (5):** the packages, as packages
- **Other Charges (5):** fee lines
- ⚠️ **`Veteran Triune` (urn vault, $822)** — see §4; a false negative, not a gap

### Set (c) — catalog only: 7 variants

```
CE-CH   Graveside Chairs          CE-CT   Cremation Table
CE-GM   Grass Mats                CE-LD   Lowering Device
CE-TD   Cemetery Tent - Double    CE-TS   Cemetery Tent - Single
UV-VET  Veteran Urn Vault
```

Six are the equipment components, which the price list sells only inside packages
(§6c). **`CE-CT` Cremation Table appears nowhere on the price list at all** — not
as an item, not as a package component.

## 4. ⚠️ Our own catalog has a one-product-two-names defect

`UV-VET` fell into set (c) and `Veteran Triune` into set (b). **They are the same
product.** Price list: Veteran Triune, Double Reinforced urn vault, $822 — the
same tier and price as Cameo Rose and SST Triune.

The catalog is internally inconsistent. Every other Triune urn variant is named
and SKU'd as a Triune:

```
UV-BTRI   Bronze Triune Urn Vault
UV-CTRI   Copper Triune Urn Vault
UV-SSTRI  Stainless Steel Triune Urn Vault
UV-CRTRI  Cameo Rose Triune Urn Vault
UV-VET    Veteran Urn Vault          ← no "Triune", and UV-VET not UV-VTRI
```

Three sources, two namings: the **price list** says "Veteran Triune", the **spec
sheet** (line 23) says "Veteran Urn Vault", the **catalog** says "Veteran Urn
Vault" / `UV-VET`. The burial side has it right — `BV-VTRI` "Veteran Triune
Burial Vault" — so the inconsistency is on the urn side only.

**This is exactly the hazard `platform_product_aliases` exists for, and it is
inside our own catalog rather than between sources.** The matcher surfaced it by
refusing to match on name shape alone; a name-keyed matcher would have merged or
dropped it silently. Needs a ruling: rename to `UV-VTRI` / "Veteran Triune Urn
Vault", or keep and alias.

## 5. ⚠️ The spec sheet's six are not the price list's four

The dispatch expected `Monticello 34"`, `Large 34"`, `Youth MT`, `Youth GL` in set
(c). **They cannot be** — they are spec-sheet rows that r193 deliberately never
loaded, so they are in no catalog set. Side by side:

| spec sheet (lines 14–19) | inside | outside | price list ODD SIZED |
|---|---|---|---|
| Monticello 34" | 90 × 34 × 28 | 95 × 39 | — |
| Large 34" | 90 × 34 × 28 | 94 × 39 | — |
| Large 36" | 90 × 36 × 28 | 94 × 40 | — |
| Large 40" | 94 × 40 × 32 | 98 × 44 | — |
| Youth MT | 68 × 24 × 21 | 72 × 28 | — |
| Youth GL | 61 × 22 × 21 | 63 × 25 | — |
| — | | | Continental 34" $2,179 |
| — | | | Graveliner 34" $1,492 |
| — | | | Graveliner 38" $2,060 |
| — | | | Pine Box "Call Office" |

**Not one name appears in both columns.** The price list has a 38"; the spec sheet
has 36" and 40" and no 38". Youth MT and Youth GL have no price-list counterpart.

### ⚠️ But the TENANT seeder already matches the price list exactly

`app/services/sunnycrest_product_seeder.py:134-144`:

```python
('Continental 34"', cat_burial, Decimal("2179.00"), {"wilbert_sku": "BV-CON34", ...
('Graveliner 34"',  cat_burial, Decimal("1492.00"), {"wilbert_sku": "BV-GL34", ...
('Graveliner 38"',  cat_burial, Decimal("2060.00"), {"wilbert_sku": "BV-GL38", ...
("Pine Box",        cat_burial, None,               {"wilbert_sku": "BV-PB", ...
```

All four, at the price list's exact prices, with SKUs. `Continental` at
`$1,607.00` matches too. **The tenant seeder is aligned to the Feb 2026 price
list; the platform catalog and the spec sheet are not.**

**A hypothesis, recorded as a hypothesis and NOT acted on.** The spec sheet may
record SHELLS while the price list names PRODUCTS: `Monticello 34"` (outside 95)
and `Large 34"` (outside 94) are two shells at one inside size, and a reinforced
product has a larger outside than a non-reinforced one — which would pair
`Monticello 34"` → `Continental 34"` ($2,179, Single Reinforced) and `Large 34"`
→ `Graveliner 34"` ($1,492, Non Reinforced). It is coherent and it is **name-shape
reasoning with an arithmetic gloss**, which is the move that produced both review
sheet false negatives. ⚠️ It also leaves `Graveliner 38"` with no spec row and
`Large 36"`, `Large 40"`, `Youth MT`, `Youth GL` with no product. **Needs James.**

## 6. Part 3 — reported, not built

### a. Reinforcement tier — no schema change needed

`product_templates.reinforcement` **already exists** (r186, `varchar`, nullable)
and is **NULL on all 21 rows**. The ruling — a nullable product ATTRIBUTE, not a
variant axis — is already what the schema expresses. Only data is missing.

Nothing uses reinforcement as a variant axis. ⚠️ One name collision to avoid: the
`option_label` values already include `Single` and `Double`, but those are the
**Tent** variants (`CE-TS`, `CE-TD`), not reinforcement tiers. A matcher keyed on
those words would collide.

Tiers to assign, from the price list: Triple (Wilbert Bronze), Double (the five
Triunes, both forms), Single (Tribute, Venetian, Continental, Salute, Monticello
burial; Venetian, Monticello urn), Non (Monarch, Graveliner, Graveliner SS;
Salute, Graveliner urn). The Odd Sized block carries no tier → **NULL, not a
guess**. `Universal Line` is its own group and carries no reinforcement word
either → NULL.

### b. Urns as a new form

Twelve P-numbered items in three groups: six ungrouped (P445 Country Bouquet,
P440 Jewel, P440A Moon Stone, P440B Sedona, P363 Victorian, P600 Arlington), Regal
Line (P300, P300WS, P300P), Tribute Line (P310, P310WS, P310P).

`form` today is `burial_vault`, `equipment`, `grave_liner`, `infant`, `urn_vault`.
**There is no `urn`.** Per the ruling they do not fold into `urn_vault` — an urn is
not a vault. Needs a new form value, a family per line, and 12 variants.

⚠️ Note the `Tribute Line` name collides with the `Tribute` burial vault, and
`Cream & Gold` / `White & Silver` collide with the Universal urn-vault finishes.
Form is what separates them; a name-keyed resolver merges them.

### c. Graveside service is sold as packages, the catalog has components

| package | with our product | without |
|---|---|---|
| Full Equipment | $300 | $600 |
| Lowering Device & Grass | $185 | $487 |
| Lowering Device Only | $140 | $487 |
| Tent Only | $225 | $557 |
| Extra Chairs (over 8) | $5 | $8 |

The catalog has `CE-LD`, `CE-GM`, `CE-TS`/`CE-TD`, `CE-CH` as separate equipment
products. **A package is not a product and the dual pricing is not a product
attribute** — the same package is two prices depending on whether Sunnycrest's
vault is in the ground, which is a property of the ORDER, not of the item.
Modelling this needs a ruling; nothing in the catalog expresses it today.

`CE-CT` Cremation Table is on neither side of the price list.

### d. "Call Office" as a price

`Pine Box` has no numeric price. The tenant seeder already encodes this as
`None` (`sunnycrest_product_seeder.py:143`), so the absence round-trips today as
NULL. ⚠️ But NULL price and "price on application" are different facts, and the
same not-established-vs-measured distinction applies: a NULL price could equally
mean nobody has set one. If "Call Office" is to be displayed as such it needs its
own representation, not an absent number.

## 7. ⚠️ The SUPERSEDED item — r193 was already right

**r193 built Universal and Salute urn vaults as TWO products. Size of the
correction: zero.**

```
salute    / urn_vault  "Salute Urn Vault"     wilbert  13 x 10¼ x 10  UV-SAL/Salute
universal / urn_vault  "Universal Urn Vault"  wilbert  13 x 10¼ x 10  UV-UWS/White & Silver
                                                                      UV-UCG/Cream & Gold
```

The price list confirms the split and supplies what the spec sheet could not: they
sit in **different groups at different prices** — Salute under `Non Reinforced`
at $436, Universal under its own `Universal Line` at $510 for both finishes.

⚠️ One thing the price list does NOT resolve: both products carry **identical
dimensions** (13 × 10¼ × 10), because spec-sheet lines 27 and 28 are identical.
Same shell, different tier and price. Consistent, but worth knowing the dimensions
cannot distinguish them.

## 8. What this does not establish

- **Whether the spec sheet's six non-manufactured rows correspond to the price
  list's four odd-sized items.** §5's hypothesis is name-shape reasoning and is
  not acted on.
- **Whether Tribute/Venetian finishes are separately orderable.** One price, two
  catalog variants, in three places.
- **Whether `Lowering Device & Grass` and `Lowering Device Only` really share a
  $487 without-product price**, or the document has a typo.
- **What `Graveliner(SS)` means commercially.** `GL-SS` carries option_label
  "Social Service"; whether that is a real grade was already open from r188.
- **Whether the 25-row production tenant is real or seeded.** Out of scope.
