# ⚠️ Annotation on `sunnycrest-catalog-review.xlsx` — two false negatives

**2026-10-02.** The spreadsheet is left exactly as committed in `b0596829`
(2026-09-22). This file records what was later found to be wrong in it, and why.

**If you are reading that sheet to decide what the platform catalog is missing, read
this first.** Two of its rows report a product as absent when the product is present
under a different name, and one class of its rows is measuring a different thing
than the heading suggests.

---

## 1. It measured the TENANT seeder, not the platform catalog

Its `In seeder?` column compares against **`app/services/sunnycrest_product_seeder.py`** —
Sunnycrest's own tenant fixture — not against `catalog_template_seeder.py` or the
platform `product_catalog_templates`.

Established by its SKU scheme, which belongs to exactly one of the two:

| SKU | `sunnycrest_product_seeder` | `catalog_template_seeder` |
|---|---|---|
| `BV-CR`, `BV-VTR`, `BV-GL`, `BV-GLSS`, `BV-GL34`, `BV-GL38`, `UV-CR`, `UV-VTR` | **all 8 present** | 0 present |

The platform catalog uses a different scheme entirely — `BV-CRTRI`, `BV-VTRI`,
`GL-STD`, `GL-SS`.

**Consequence.** `Graveliner 34"` / `BV-GL34` and `Graveliner 38"` / `BV-GL38` are
TENANT products. Their absence from the platform catalog's 37 templates is expected
and is **not** a platform gap. A reader counting platform gaps from this sheet would
over-count by two.

## 2. ⚠️ `Basic Gray (P410)` — "NOT IN SEEDER" is a FALSE NEGATIVE

The product is present, as **`Salute Urn Vault` / `UV-SAL`**
(`sunnycrest_product_seeder.py:182-183`, price 436.00).

Wilbert sells it as one listing, **"Basic Gray/Salute Urn Vault"**. Our spec sheet
calls it `Basic Gray Urn Vault (P410)`; the seeder and the platform catalog call it
`Salute Urn Vault`. Confirmed one product by the owner on 2026-10-02.

The sheet looked for one half of a compound name, found the other half under a
different row, and reported a gap.

## 3. ⚠️ `Universal (P400WS)` — ALSO a FALSE NEGATIVE

The product is present, as **`White & Silver Urn Vault` / `UV-WS`**, `product_line`
`Universal` (`sunnycrest_product_seeder.py:191-192`, price 510.00).

`P400`**`WS`** ↔ `UV-`**`WS`** ↔ "White & Silver". The seeder names the finish where
the spec sheet names the model, so the row matched nothing.

⚠️ **This one was not noticed when the first false negative was.** It was found only
by reading the neighbouring rows rather than stopping at the row that had been
flagged. Worth knowing about this sheet: the defect is systematic, so a third
instance is more likely than not among rows nobody has checked.

## 4. The cause, stated plainly

**A gap analysis reports a product missing when the same product appears under a
second name.** Both rows have that cause. Nothing about the sheet's method was
careless — it compared names, and the names genuinely differ across sources.

Three sources we own name the same products differently: the platform catalog, this
tenant seeder, and `docs/catalog/2026-10-02-sunnycrest-product-specs.csv`. Wilbert's
consumer store is a fourth. **This is exactly what `platform_product_aliases`
(migration `r189`) exists to prevent, and it happened twice in our own repository
before that table existed.**

The corroboration runs the other way too, and it is the reason the `UV-SAL`
correction is trustworthy: `sunnycrest_product_seeder.py:182-193` already treats
Salute, Cream & Gold and White & Silver as three distinct products, and it predates
every conclusion reached on 2026-10-02. Today's reading agrees with what was already
in the repository rather than replacing it with a fresh guess.

## 5. What is still sound in the sheet

Everything that is a question rather than a comparison. Its four amber columns —
`STILL SOLD?`, `CURRENT PRICE`, `MADE or BOUGHT IN`, `COLOUR` — are unanswered
prompts for the owner and are unaffected by any of the above. Its per-row prices and
`Portal vault id(s)` are read from the tenant seeder and are accurate to it.

Only the `In seeder?` column's negatives are suspect, and only where a product may
carry a second name.
