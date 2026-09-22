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
`white-venetian`/`venetian`, the same urn pair, and `universal-urn`. If a colour
is "one product, a choice", it becomes a **fourth personalization question**
alongside legacy print, nameplate and vinyl — which is the finish question
deferred earlier arriving through the catalog rather than through capture.

**5. What still needs deciding and is not in the sheet.** Whether the seeder's
bought-in sizes should exist at all — `Continental 34"`, `Graveliner 34"`,
`Graveliner 38"` are not on James's list. They appear as ordinary rows; marking
them `N` is how they go away.
