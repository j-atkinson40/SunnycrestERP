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
   ⚠️ **BOTH HALVES SUPERSEDED 2026-10-03.** `r194` makes it a constraint, and R2
   makes the three rows VARIANTS, which need no family/form key. The collision is
   now unexpressible rather than avoided. See the Revision section.
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

---

# Revision, 2026-10-03 — rulings applied, counts re-derived

Supersedes §3a, §3d and §5 above. Earlier text left in place; read this for the
live version.

## R1. `UV-VET`'s SKU never changes — closed, not deferred

**RULED:** the SKU stays `UV-VET` **permanently**. Only `display_name` changes, to
`Veteran Triune Urn Vault`.

**The cosmetic inconsistency with `UV-BTRI`/`UV-CTRI`/`UV-SSTRI`/`UV-CRTRI` is
DELIBERATE and is not to be re-opened.** A SKU is an identifier: it is unambiguous,
it is referenced in `r188:262`, in `r189`'s and `r191`'s docstrings, in two
investigation documents and in `catalog_template_seeder.py:49`, and renaming it for
consistency is churn with real blast radius and no user-visible benefit.

Recorded here rather than deferred because a deferred decision comes back. ⚠️ If
you are reading this because `UV-VET` looks wrong next to its siblings: it is
wrong, it is known, and it stays.

## R2. ⚠️ Odd sizes are VARIANTS, not products — supersedes §3d

The `(family_slug, form)` collision in §3d **dissolves**: a variant does not need a
family/form key of its own.

| price list item | becomes a variant of | basis |
|---|---|---|
| `Continental 34"` | `continental` / `burial_vault` | **inferred** — see falsifier below |
| `Graveliner 34"` | `graveliner` / `grave_liner` | **inferred** — same |
| `Graveliner 38"` | `graveliner` / `grave_liner` | **inferred** — same |

**Precedent:** `Loved & Cherished` is one product with three sizes at three
different prices ($239 / $374 / $452). Price is already variant-capable, so
`Continental 34"` at $2,179 against `Continental` at $1,607 is not an obstacle.

### ⚠️ The inference moved somewhere more honest, and this is the point

The earlier reading assigned these rows NULL reinforcement *because the price list
states no tier for them*. As variants **they do not carry the attribute at all** —
reinforcement lives on the product, and `Continental` is `Single Reinforced` on the
page, measured.

So the claim is no longer *"Continental 34" is Single Reinforced"* — which the
document does not say — but *"Continental 34" is a Continental"*, which is the
real question and is genuinely an inference.

**FALSIFIER:** a source showing the odd size is built differently from its parent —
a different wall thickness, a different reinforcement, a different mold line. The
price list's `ODD SIZED` grouping is weak contrary evidence: it organizes them away
from their parents. Nothing resolves it, and nothing needs to until something reads
a dimension.

### ⚠️ One wrinkle the ruling creates, flagged not resolved

`option_label` is a single string, and these products would then carry **two axes
in one field**:

```
graveliner / grave_liner    GL-STD  "Standard"        ← grade axis
                            GL-SS   "Social Service"  ← grade axis
                            NEW     "34 inch"         ← size axis
                            NEW     "38 inch"         ← size axis

continental / burial_vault  BV-CON  "Continental"     ← not an axis value at all
                            NEW     "34 inch"         ← size axis
```

`Loved & Cherished` is clean because every variant is a size (`19 inch`, `24 inch`,
`31 inch`). These are not. ⚠️ `BV-CON`'s existing `option_label` is `Continental` —
the product's own name, not a value on any axis — so adding `34 inch` beside it
makes the field mean two different things in one product.

Three options, all **decided**:

1. **Accept the mixing.** `option_label` becomes "whatever distinguishes this
   variant", which is what it already is for `Tent` (`Single`/`Double`).
2. **Normalise the base label** — `BV-CON`'s `option_label` becomes `Standard`,
   matching `GL-STD`. One row changed, and the axis reads consistently.
   **Recommended.**
3. **Add an axis column** to `product_variant_templates`. Largest change; defers
   nothing else.

Needs a ruling before Migration B writes these three rows.

## R3. Reinforcement — re-derived, and the count is UNCHANGED

The ruling notes the 7 explicit NULLs need re-deriving because the odd sizes leave
the set. **Re-derived: they were never in it.** §3b's table covers the **21 products
that exist today**, and the odd sizes were not among them — they were proposed as
new products in §3d, and are now variants, so they never touched this set in either
reading.

**14 measured tiers + 7 NULL stands.** The 7 break down as 2 where the source
withholds a tier (`universal` / urn_vault has its own group with no reinforcement
word; `loved-and-cherished` has its own block) and 5 where the concept does not
apply (the equipment products).

## R4. James's answers — and they resolve oppositely

Both items were absent from the price list and looked identical on the page. They
are not the same fact.

| item | ruling | basis |
|---|---|---|
| `Vault Placer` | price **$0.00** is CORRECT. No additional cost. | **measured** — James, 2026-10-03. The seeder's `0.00` (`:241`) is a real price, not a placeholder. |
| `CE-CT` Cremation Table | the product **EXISTS**. Keep it. It is simply not on the February 2026 price list. | **measured** — James, 2026-10-03. ⚠️ Its price is **NULL — not established, and NOT $0.00.** He said it exists, not that it is free. |

⚠️ **This pair is the distinction worth keeping.** Two items, both absent from the
price list, resolving in opposite directions: one is *priced at zero*, the other has
*no established price*. Had either been defaulted — to `0.00` for tidiness, or to
"absent therefore delete" — the difference would have been erased and nothing
downstream would have contradicted it.

Same line as `Pine Box`'s "Call Office" versus not-priced, and the same line as
`personalization_capability`'s `[]` versus NULL. **Third instance this arc**, now in
three different columns.

`CE-CT` is therefore **not** a membership gap and must not be deleted as one. Set
(c) resolves completely: six package components plus one product that exists and
is not currently listed.

## R5. Revised row counts for Migration B

```
changed    1    UV-VET display_name -> "Veteran Triune Urn Vault"
                (sku unchanged, permanently — R1)
updated   21    reinforcement: 14 measured tiers + 7 NULL  (unchanged — R3)
added      8    urn products        (new `urn` form)
added     12    urn variants
added      3    odd-size VARIANTS   (0 new products — R2)
                Continental 34" -> continental/burial_vault
                Graveliner 34"  -> graveliner/grave_liner
                Graveliner 38"  -> graveliner/grave_liner
changed    1    BV-CON option_label "Continental" -> "Standard"  [IF R2 option 2]
```

**Was:** 2 odd-sized products + 3 variants, and a blocker on `(family_slug, form)`.
**Now:** 0 products, 3 variants, no collision — and `r194` has made the collision
impossible rather than merely avoided.

⚠️ **Blocked on R2's option ruling** (the two-axes-in-one-field question) before the
three odd-size variants can be written. Everything else in Migration B is ruled.

---

# Rulings applied, 2026-10-03 — `option_label` and `BV-CON`. Built in r195.

## R6. `option_label` stays ONE axis — RULED

Graveliner carries `Standard`, `Social Service`, `34 inch`, `38 inch` as a **flat
heterogeneous list**. Basis: **decided**.

⚠️ **It looks like a grade axis crossed with a size axis ONLY IF THE CROSS-PRODUCT
EXISTS, AND IT DOES NOT.** There is no Graveliner SS at 34" on the price list, in
`sunnycrest_product_seeder`, or in anything James has said. Two axes would create
**six slots to hold four real things**, and the two empties would then need a
reason to be empty that nobody has.

The axis is *"which graveliner"* — not "size" and not "grade".

**FALSIFIER, recorded:** any source offering a crossed configuration — Graveliner
SS in 34" or 38", or similar. That is the day it becomes two axes. It is not today,
and building for it now is the same move as mapping shells to products before
anything needs dimensions.

⚠️ **The falsifier is test-enforced, not merely written down.**
`test_price_list_catalog_r195.py::test_graveliner_carries_a_flat_heterogeneous_axis`
asserts the label set by **equality**, so a crossed configuration appearing fails
the suite — which is exactly when this ruling should be revisited rather than
worked around. Break-tested: inserting `GL-SS34` "Social Service 34 inch" turned
it red.

## R7. `BV-CON`'s `option_label` becomes `Standard` — RULED

Basis: **decided**, explicitly not measured. The price list says `Continental`, not
`Continental Standard`.

`Continental` as an option label is **degenerate** — it restates the product rather
than naming a value on any axis. That is invisible while there is one variant and
wrong the moment `34 inch` joins it. Parallel to `GL-STD` **by our choice**, not by
the source.

## R8. What r195 actually built

```
form `urn` added to ck_product_templates_form
8 families, 8 products, 12 variants      the stocked urns, ownership wilbert (inferred)
3 variants                               BV-CON34, GL-34, GL-38 on existing parents
1 display_name                           UV-VET -> "Veteran Triune Urn Vault" (sku unchanged)
1 option_label                           BV-CON "Continental" -> "Standard"
14 reinforcement tiers                   measured; 7 products stay NULL
```

Catalog is now **29 products / 52 variants**, reproduced identically from empty on
a scratch database.

⚠️ **No price was written for anything**, because `product_templates` has no price
column. James's two rulings — `Vault Placer` at **$0.00** (measured, correct) and
`CE-CT` at **NULL** (exists, price not established, NOT zero) — are recorded here
and had nothing to write. `test_no_price_column_exists_to_have_defaulted` pins the
reason they could not have been confused at this tier.

⚠️ **`CE-CT` is not deleted and is test-pinned.** Absence from a price list is not
absence from the world.
