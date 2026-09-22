# The Sunnycrest catalog review sheet

`sunnycrest-catalog-review.xlsx` — built by
`backend/scripts/build_catalog_review_sheet.py`, which reads the seeder's AST.
**Re-run the script rather than editing the generated sheet's left-hand columns**;
the four amber columns are James's and are never written by the generator.

    cd backend && .venv/bin/python scripts/build_catalog_review_sheet.py

63 rows: 55 the seeder would create, 8 on James's list that it lacks.

---

## What happens after the sheet comes back — proposed, not built

The filled sheet becomes the catalog's single definition and the seeder reads it
instead of carrying its own list. What that change involves:

**1. The sheet becomes a source file, not a spreadsheet.** An `.xlsx` is a zip of
XML: it does not diff, it cannot be reviewed in a pull request, and a one-cell
change looks identical to a rewrite. The filled sheet should be converted once to
a **CSV or TOML checked in beside it** — `docs/catalog/sunnycrest-catalog.csv` —
which diffs line by line. The xlsx stays as the thing James edits; the converted
file is what the seeder reads and what review sees.

**2. `sunnycrest_product_seeder.py` loses its literal list.** Today the 55
products are tuples in the module. They become a read of the checked-in file.
⚠️ The seeder's behaviour must not change in the same commit as its data source:
per CLAUDE.md's characterization rule, the move is behaviour-preserving and gets
its own commit, with the existing products asserted identical before and after.

**3. Three columns become real fields.**

| sheet column | where it goes |
|---|---|
| Still sold? | rows marked N are not created — and if one already exists, it is NOT deleted; that is a separate decision |
| Current price | overrides the seeder price where filled |
| Made or bought in | ⚠️ **there is no column for this on `Product` today.** It needs one, or a `product_line` convention. That is a migration and a ruling, not part of the import |

**4. The colour answers unblock the portal mapping.** Four portal vaults cannot
be mapped until they are answered — `white-tribute`/`gray-tribute`,
`white-venetian`/`venetian`, the same urn pair, and `universal-urn`.

⚠️ **CORRECTED 2026-09-22. This paragraph ended:** *"If a colour is 'one product,
a choice', it becomes a **fourth personalization question** alongside legacy
print, nameplate and vinyl — which is the finish question deferred earlier
arriving through the catalog rather than through capture."* **That is wrong, and
wrong in a way that would have damaged the model built this week.**

**Colour is not personalization, whichever way the answer goes.**
Personalization is something ADDED to the vault, and every answer in
`services/personalization/` maps to a job the plant does — fit a nameplate,
apply a print, affix an emblem. That totality is asserted by
`test_every_answer_maps_to_tasks_within_the_canonical_four`. Colour decides
WHICH VAULT is pulled or poured. It has no job in that mapping, and forcing it
in would have made the question layer lie about what personalization is — the
answer set would have held one answer that produces no task, indistinguishable
from the `none` case the totality test exists to keep separate.

If colour is a choice rather than a product, it is a question the call capture
asks **about the product**, next to "which vault" — not a fourth personalization
question. It belongs to the capture schema, not to `questions.py`.

⚠️ The generated sheet was checked and does NOT carry this error: its COLOUR
guidance says only "separate product" or "one product, colour is a choice", with
the price-or-process test. Nothing needed regenerating.

**4a. Made or bought in — ruled yes, and NOT on an existing column.**
⚠️ Two columns look like they already express this and neither does:

| column | what it actually means |
|---|---|
| `Product.source` | **row provenance** — `manual`, `catalog_builder`, `csv_import`, and `seeder` as the seeder writes it. How the RECORD got here, not how the vault is obtained. Overloading it would put two unrelated meanings in one 30-character string |
| `Product.is_direct_ship_product` | a **fulfilment route** — Wilbert ships an urn straight to the funeral home. A bought-in vault still sits in Sunnycrest's yard, so this is close and different |

So the new column is right. The reason it earns one is operational rather than
tidy: **a bought-in vault must never land on the pour schedule or count against
production capacity, and nothing can currently tell the two apart.** It ships
with the seeder change.

**5. What still needs deciding and is not in the sheet.** Whether the seeder's
bought-in sizes should exist at all — `Continental 34"`, `Graveliner 34"`,
`Graveliner 38"` are not on James's list. They appear as ordinary rows; marking
them `N` is how they go away.
