# Production's Wilbert catalog — all 37 rows, for review against what Wilbert sells

**2026-10-02.** Read-only production read via CLAUDE.md §7's `railway run` form, with the
connection-level read-only guard. Credential never printed; target recorded as
`host=shuttle.proxy.rlwy.net port=57253 db=railway`.

**This is the platform's current Wilbert catalog.** It is a developer's transcription, written
in `app/services/catalog_template_seeder.py` and applied to production by the startup hook. It
has never been checked against Wilbert's own catalog.

## §12 declaration — demo inclusion

**0 of 37 rows carry a demo marker.** Searched `id`, `preset`, `category`, `product_name`,
`product_description` and `sku_prefix` for `DEMO`.

⚠️ This declaration is here because it is mandatory, and because the same declaration was
missing from four production reads earlier today — which is how a ruling got built on
`seed_accounting_demo`'s rows. `product_catalog_templates` has no `company_id`, so there is no
tenant scope to state: the population is the whole table.

## Column population — none null, and that is not the interesting part

All ten columns are populated for all 37 rows: `id`, `preset`, `category`, `product_name`,
`product_description`, `sku_prefix`, `default_unit`, `is_manufactured`, `sort_order`,
`created_at`.

⚠️ **So the answer to "which field does the catalog claim to model and not populate" is none —
but the sharper finding is what it has no column for at all.** Every physical fact the
platform/tenant line assigns to the platform is absent as a column:

```
absent: outside dimensions · weight · construction · which personalizations
        the product can physically take · spec source · spec date
        canonical vs alias naming · (price, deliberately — tenant-owned)
```

A spec-provenance field cannot be null here because there is nowhere to put one. The 86″-vs-88″
failure has no column to be wrong in yet.

## ⚠️ One data defect: two rows share `sort_order` 10

```
BV-MON   Monticello Burial Vault        sort_order 10
BV-WBR   Wilbert Bronze Burial Vault    sort_order 10
```

Ordering between them is unspecified, so the catalog renders in an order Postgres chooses. Same
duplicate-ordering pathology CLAUDE.md records for `workflow_steps`, one table over. Burial
Vaults otherwise runs 10–27 with no other collision; Urn Vaults 48–59 and Cemetery Equipment
80–85 are clean.

## The 37 rows

    === Burial Vaults ===
      sku        product_name                         unit   mfg  ord  description
      BV-BTRI    Bronze Triune Burial Vault           each   True 11   Bronze Triune three-piece protective vault
      BV-CON     Continental Burial Vault             each   True 20   Continental reinforced concrete vault
      BV-CRTRI   Cameo Rose Triune Burial Vault       each   True 14   Cameo Rose Triune three-piece protective vault
      BV-CTRI    Copper Triune Burial Vault           each   True 12   Copper Triune three-piece protective vault
      BV-GTRIB   Gray Tribute Burial Vault            each   True 17   Gray Tribute entry-level vault
      BV-GVEN    Gold Venetian Burial Vault           each   True 19   Gold finish Venetian air-sealed vault
      BV-MON     Monticello Burial Vault              each   True 10   Monticello reinforced concrete burial vault
      BV-MRC     Monarch Burial Vault                 each   True 22   Monarch reinforced concrete vault
      BV-SAL     Salute Burial Vault                  each   True 21   Salute reinforced concrete vault
      BV-SSTRI   Stainless Steel Triune Burial Vault  each   True 13   Stainless steel Triune three-piece protective 
      BV-VTRI    Veteran Triune Burial Vault          each   True 15   Military tribute Triune vault
      BV-WBR     Wilbert Bronze Burial Vault          each   True 10   Premium bronze-finished Wilbert vault
      BV-WTRIB   White Tribute Burial Vault           each   True 16   White Tribute entry-level vault
      BV-WVEN    White Venetian Burial Vault          each   True 18   White finish Venetian air-sealed vault
      GL-SS      Graveliner (Social Service)          each   True 24   Social service concrete grave liner
      GL-STD     Graveliner                           each   True 23   Standard concrete grave liner
      LC-19      Loved & Cherished 19"                each   True 25   Infant/child vault 19 inch
      LC-24      Loved & Cherished 24"                each   True 26   Infant/child vault 24 inch
      LC-31      Loved & Cherished 31"                each   True 27   Infant/child vault 31 inch
    
    === Cemetery Equipment ===
      sku        product_name                         unit   mfg  ord  description
      CE-CH      Graveside Chairs                     each   False85   Graveside chairs rental per set
      CE-CT      Cremation Table                      each   False81   Cremation table rental per service
      CE-GM      Grass Mats                           each   False84   Artificial turf/grass mats rental per service
      CE-LD      Lowering Device                      each   False80   Lowering device rental per service
      CE-TD      Cemetery Tent - Double               each   False83   Double tent (seats ~100) rental per service
      CE-TS      Cemetery Tent - Single               each   False82   Single tent (seats ~50) rental per service
    
    === Urn Vaults ===
      sku        product_name                         unit   mfg  ord  description
      UV-BTRI    Bronze Triune Urn Vault              each   True 48   Bronze Triune urn vault
      UV-CRTRI   Cameo Rose Triune Urn Vault          each   True 51   Cameo Rose Triune urn vault
      UV-CTRI    Copper Triune Urn Vault              each   True 49   Copper Triune urn vault
      UV-GL      Graveliner Urn Vault                 each   True 59   Graveliner urn vault
      UV-GVEN    Gold Venetian Urn Vault              each   True 55   Gold Venetian urn vault
      UV-MON     Monticello Urn Vault                 each   True 58   Monticello urn vault
      UV-SAL     Salute Urn Vault                     each   True 56   Salute urn vault
      UV-SSTRI   Stainless Steel Triune Urn Vault     each   True 50   Stainless Steel Triune urn vault
      UV-UCG     Universal Urn Vault (Cream & Gold)   each   True 52   Universal urn vault cream and gold finish
      UV-UWS     Universal Urn Vault (White & Silver) each   True 53   Universal urn vault white and silver finish
      UV-VET     Veteran Urn Vault                    each   True 57   Veteran military tribute urn vault
      UV-WVEN    White Venetian Urn Vault             each   True 54   White Venetian urn vault

## What to check against Wilbert's catalog

Ordered by how wrong each would be if wrong:

1. **Granularity.** This models Triune as six finishes × two forms (burial, urn). Dev's table
   models it as one product. One of those matches Wilbert; neither is verified.
2. **`is_manufactured`** is `True` for every vault and urn vault, `False` for all six Cemetery
   Equipment rows. That asserts Sunnycrest manufactures every Wilbert-branded vault, which is a
   claim about the licensee relationship rather than about the product.
3. **The names.** `Wilbert Bronze Burial Vault` and `Bronze Triune Burial Vault` are adjacent
   and differently shaped; `Graveliner` has no `BV-`/`GL-` consistency with its own
   Social Service sibling. These read as one person's transcription, not a catalogue.
4. **Coverage.** 19 burial vaults, 12 urn vaults, 6 equipment. Nothing for precast, Redi-Rock,
   Rosetta or wastewater — which dev's table does carry, and which Sunnycrest sells.
5. **`LC-19` / `LC-24` / `LC-31`** carry inch sizes in the name, the only rows that encode a
   physical fact — and they encode it in a string because there is no dimension column.

## What this does not establish

- Whether any of these names, SKUs or groupings match Wilbert's own catalog. That is the xlsx
  pass.
- Whether the `x1y2z3a4b5c6` migration's 25 rows ever existed in production. None of its three
  distinctive categories is present now.
- Why `sort_order` 10 is duplicated — seeder authoring error or an upsert artifact.
