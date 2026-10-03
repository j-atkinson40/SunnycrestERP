# Price list → catalog: the proposed row set for the next migration

**2026-10-03.** No migration written. This is the map; the load comes after it is
ruled on — the `ca78a64a` pattern that worked for the spec sheet.

Source: `docs/catalog/2026-02-01-sunnycrest-funeral-price-list.pdf`, md5
`ab3fb519423c09fd766b0a265f288cee`, pinned by
`backend/tests/test_price_list_provenance.py`.

**Four things to read before the tables.**

1. ⚠️ **The dispatch's "missing products" list is wrong on two of five.**
2. ⚠️ **No source in this repository establishes ownership.** Every tier is
   `decided`, except the urns which are `inferred`.
3. ⚠️ **`(family_slug, form)` is NOT a database constraint**, and three proposed
   rows collide on it.
4. The price list is **not a product list** — it carries products, services and
   fees on one page, and only the first become catalog rows.

---

## 0. Basis vocabulary

Every row below carries one:

| basis | meaning |
|---|---|
| **measured** | a source states it. The source and its line are cited. |
| **decided** | our product decision. No source establishes it. |
| **inferred** | reasoning from a pattern. The pattern is stated, and so is what would falsify it. |

## 1. ⚠️ Scope correction — three products are missing, not five

The dispatch lists the platform-tier gaps as *Wilbert Bronze, Graveliner (SS),
Continental 34", Graveliner 34", Graveliner 38"*. **Two of those are already in
the platform catalog and matched in set (a):**

| dispatch says missing | actually | evidence |
|---|---|---|
| `Wilbert Bronze` | **present** as `BV-WBR` "Wilbert Bronze Burial Vault" | set (a), matched on name + form |
| `Graveliner (SS)` | **present** as `GL-SS` "Graveliner (Social Service)" | set (a), matched via the declared `(SS)` → Social Service alias |

Adding either would create a duplicate. The genuine platform-tier gaps among
price-list **products** are **three**: `Continental 34"`, `Graveliner 34"`,
`Graveliner 38"` — plus the twelve urns, which need a new form.

## 2. ⚠️ No source in this repository establishes ownership

Both of Sunnycrest's documents are **tenant-tier facts**:

- `sunnycrest_product_seeder.py` is a tenant fixture. Everything in it sits at
  tenant tier **by construction**, including `Wilbert Bronze` and `Tribute`, which
  nobody would call tenant-owned. **It is not cited as ownership evidence anywhere
  in this map.**
- The **price list** says what Sunnycrest offers. Offering is not authorship.
- The **spec sheet** is Sunnycrest's own licensee spec sheet. Same.

So `wilbert` / `licensee_common` / `tenant` cannot be *read* from anything here.
James has ruled the policy — *build the Wilbert catalog the way we want it,
configure per tenant at onboarding, licensees rename and add their own* — which
makes ownership a **decision**, and this map records it as one.

⚠️ **The consequence worth stating:** when the first other licensee's catalog
contradicts an assignment below, that is a **signal**, not a surprise. A row marked
`decided` has no evidence behind it to be surprised by.

## 3. IN SCOPE — proposed rows

### 3a. `UV-VET` rename — 1 row changed, 0 added

| field | from | to | basis |
|---|---|---|---|
| `display_name` | `Veteran Urn Vault` | `Veteran Triune Urn Vault` | **measured** — price list p2 "Veteran Triune" (Double Reinforced urn vaults); `sunnycrest_product_seeder.py:173` "Veteran Triune Urn Vault". Two sources agree. |
| `option_label` | `Veteran` | *(unchanged)* | **measured** — siblings use the bare finish/model: Bronze, Copper, Stainless Steel, Cameo Rose. |
| `sku` | `UV-VET` | `UV-VTRI` | ⚠️ **decided** — no source names our SKUs. Proposed only for consistency with `UV-BTRI`/`UV-CTRI`/`UV-SSTRI`/`UV-CRTRI` and with `BV-VTRI` on the burial side. |

⚠️ **The SKU change is the risky half and is separable.** `UV-VET` is referenced in
`r188:262` (which created it), in `r189`'s and `r191`'s docstrings as a worked
example, in two investigation documents, and in
**`catalog_template_seeder.py:49`** — which writes the *old* `product_catalog_templates`
table that Phase 3 drops. The display-name fix needs none of that touched. **Recommend
renaming the display name now and deciding the SKU separately**, since one is
correcting a defect and the other is tidying.

### 3b. `reinforcement` populated — 21 rows, data only

Column exists (`r186`, nullable, NULL on all 21). ⚠️ **Key on the column, never on
label text:** `option_label` already contains `Single` and `Double` as **Tent**
variant values.

**All measured** from the price list's group headings unless noted.

| product (family / form) | reinforcement | basis |
|---|---|---|
| `wilbert-bronze` / burial_vault | `Triple` | measured — p1 "Triple Reinforced" |
| `triune` / burial_vault | `Double` | measured — p1; all five variants sit in that group |
| `tribute` / burial_vault | `Single` | measured — p1 |
| `venetian` / burial_vault | `Single` | measured — p1 |
| `continental` / burial_vault | `Single` | measured — p1 |
| `salute` / burial_vault | `Single` | measured — p1 |
| `monticello` / burial_vault | `Single` | measured — p1 |
| `monarch` / burial_vault | `Non` | measured — p1 "Non Reinforced" |
| `graveliner` / grave_liner | `Non` | measured — p1; both Graveliner and Graveliner(SS) are in that group |
| `triune` / urn_vault | `Double` | measured — p2 |
| `venetian` / urn_vault | `Single` | measured — p2 |
| `monticello` / urn_vault | `Single` | measured — p2 |
| `salute` / urn_vault | `Non` | measured — p2 |
| `graveliner` / urn_vault | `Non` | measured — p2 |
| `universal` / urn_vault | **NULL** | measured — p2 gives it its own `Universal Line` group carrying **no reinforcement word**. NULL is the finding, not an omission. |
| `loved-and-cherished` / infant | **NULL** | measured — p1 gives it its own block with no tier |
| the 5 `equipment` products | **NULL** | **decided** — reinforcement does not apply to a tent or a lowering device |

14 products take a tier; 7 take NULL, 2 of them because the source withholds it and
5 because the concept does not apply.

### 3c. Urns — a new form, 8 products, 12 variants

⚠️ `form` today is `burial_vault`, `equipment`, `grave_liner`, `infant`,
`urn_vault`. **There is no `urn`.** Per the ruling they do not fold into
`urn_vault` — an urn is not a vault.

**Ownership: `wilbert`, basis `inferred`.** The pattern: `P445`, `P440`, `P440A`,
`P440B`, `P363`, `P600`, `P300`, `P310` share the **P-number scheme** with
`P400WS` and `P410` on the spec sheet, and those two were already ruled Wilbert
products. A tenant does not mint P-numbers. **What would falsify it:** Sunnycrest
buying these from a non-Wilbert supplier who also uses P-numbers. Not resolvable
from either document. Stocking and price remain Sunnycrest's.

| family / form | product | variants (sku · option_label) | basis |
|---|---|---|---|
| `country-bouquet` / urn | Country Bouquet | `P445` · Country Bouquet | measured (p2) |
| `jewel` / urn | Jewel | `P440` · Jewel | measured (p2) |
| `moon-stone` / urn | Moon Stone | `P440A` · Moon Stone | measured (p2) |
| `sedona` / urn | Sedona | `P440B` · Sedona | measured (p2) |
| `victorian` / urn | Victorian | `P363` · Victorian | measured (p2) |
| `arlington` / urn | Arlington | `P600` · Arlington | measured (p2) |
| `regal` / urn | Regal Line | `P300` · Cream & Gold; `P300WS` · White & Silver; `P300P` · Pebble Dust | measured (p2 "Regal Line") |
| `tribute-urn` / urn | Tribute Line | `P310` · Cream & Gold; `P310WS` · White & Silver; `P310P` · Pebble Dust | measured (p2 "Tribute Line") |

⚠️ **`tribute-urn`, not `tribute`** — `decided`. The family slug `tribute` is taken
by the Tribute **burial vault**. The price list calls this group "Tribute Line";
the slug is ours. Grouping the six ungrouped urns as one product per urn is also
`decided` — the price list gives them no line name, so one-product-one-variant is a
choice, not a reading.

⚠️ **Three option labels collide across forms**: `Cream & Gold`, `White & Silver`
and `Pebble Dust` appear on both the Regal/Tribute urns and the `universal`
**urn vault**. Form is the only thing separating them. A name-keyed resolver
merges them; the alias table must stay form-aware.

### 3d. The three genuinely missing products — ⚠️ BLOCKED on a key collision

| price list item | price | proposed | basis |
|---|---|---|---|
| `Continental 34"` | $2,179 | its own product, **not a variant of Continental** | **measured** — p1 puts it in the `ODD SIZED` group, *away from* `Continental` under Single Reinforced. The price list is authoritative for organization, and it organizes them apart. |
| `Graveliner 34"` | $1,492 | its own product | measured — same |
| `Graveliner 38"` | $2,060 | its own product | measured — same |

Ownership: `licensee_common`, basis **decided** for all three — consistent with the
standing assignment of `Graveliner` and its odd sizes. ⚠️ `Continental 34"` is the
weakest of the three: `Continental` itself is assigned `wilbert`, so an oversize
Continental sitting at `licensee_common` is an assertion that the oversize is
licensee-made while the standard is Wilbert's. **Nothing establishes that.**

#### ⚠️ The blocker: `(family_slug, form)` cannot express these rows

`Continental 34"` wants `(continental, burial_vault)` — **already taken** by
"Continental Burial Vault". Same for the two Graveliners against
`(graveliner, grave_liner)`.

**And the key is not enforced.** `product_templates` has only `id` as PRIMARY KEY
and a plain, **non-unique** index on `family_slug`. So the database would accept a
duplicate silently.

⚠️ **That matters beyond this migration.** `r193` resolves products with
`{(family_slug, form): id}` built from a query — a Python dict. A duplicate key
would be **silently collapsed, last row wins**, leaving one product permanently
unreachable with no error. The natural key everything relies on is a convention
the schema does not hold anyone to.

Three ways out, all `decided`, none measured:

1. **Distinct families** — `continental-34`, `graveliner-34`, `graveliner-38`.
   Cheapest; makes the family slug carry a size, which no other family does.
2. **One odd-sized family per base product** — `continental-odd` (1 variant),
   `graveliner-odd` (2 variants: 34", 38"). Keeps size on the variant axis where
   `Loved & Cherished` already puts it. **Recommended.**
3. **Relax the key** — add a discriminator. Largest change, and the one that makes
   the unenforced convention worse.

**Recommend option 2, and separately add a unique constraint on
`(family_slug, form)`** so the convention the code relies on is one the database
holds. That constraint is a migration of its own and should not ride inside the
data load.

## 4. OUT OF SCOPE — where they would go, nothing built

### 4a. Graveside service packages — services, not products

| package | with our product | without |
|---|---|---|
| Full Equipment | $300 | $600 |
| Lowering Device & Grass | $185 | $487 |
| Lowering Device Only | $140 | $487 |
| Tent Only | $225 | $557 |
| Extra Chairs (over 8) | $5 | $8 |

Services composed of equipment products. The components already exist at platform
tier (`CE-LD`, `CE-GM`, `CE-TS`/`CE-TD`, `CE-CH`) — **which is why six of the seven
set-(c) items resolve cleanly: they are products, and the packages are services made
of them.**

⚠️ The dual pricing is a property of the **order**, not of the item: the same
package is two prices depending on whether Sunnycrest's vault is in the ground.
Nothing in the catalog expresses that, and a `price` column could not.

⚠️ Also recorded, unresolved and from the document itself: `Lowering Device & Grass`
and `Lowering Device Only` carry the **same** $487 without-our-product price while
their with-product prices differ ($185 vs $140). Possible source typo. With James.

### 4b. Fee lines — billing rules, not products

`Sunday & Holiday` $550, `Saturday Spring Burial` $200, `Late Arrival per ½ hr`
$75, `Legacy Rush Fee` $100, `Late Notice` $250.

*"Do what our price list says"* governs what Sunnycrest **offers**. It does not make
a late fee a product.

### 4c. `Pine Box` — "Call Office" is a pricing mode we do not model

⚠️ `None` and *price on application* are different facts, the same
not-established-versus-measured distinction this arc has now hit three times. The
tenant seeder stores `None` (`:143`), which round-trips as *no price set*. If the
catalog is to say "Call Office" it needs its own representation.

### 4d. Spec-sheet-only names — ruled, not products

`Monticello 34"`, `Large 34"`, `Large 36"`, `Large 40"`, `Youth MT`, `Youth GL`.
Not on the price list; the price list is authoritative for membership. They stay
recorded as unmatched dimension rows. The shells-vs-products hypothesis is written
up in `docs/investigations/2026-10-03-price-list-reconciliation.md` §13, with the
note that it should be answered by measuring a vault rather than by re-reading
either document.

## 5. Flagged, not resolved — with James

| item | where | question |
|---|---|---|
| `Vault Placer` | `sunnycrest_product_seeder.py:241`, **$0.00**, absent from the price list | included with something, or a leftover? |
| `CE-CT` Cremation Table | platform catalog only — on **neither** the price list nor the tenant seeder | does Sunnycrest have one? Keeping it is a guess; removing it is also a guess. |

## 6. Row count, if everything in §3 is approved

```
changed      1    UV-VET display_name  (+1 more if the sku change is approved)
updated     21    reinforcement — 14 tiers, 7 explicit NULL
added        8    urn products        (new form)
added       12    urn variants
added        2    odd-sized products  (option 2 above)
added        3    odd-sized variants
```

⚠️ **Blocked until §3d is ruled**, and the unique constraint on
`(family_slug, form)` should land as its own migration **before** any row that
would collide on it.
