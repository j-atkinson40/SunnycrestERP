# Phase 2b-1 Part 0 — mapping the licensee spec sheet onto the platform catalog

**2026-10-02.** Read-only when written. Establishes the row→product mapping, the
agreement analysis, the figures the parser refuses, and the three personalization
question ids, before r192/r193 wrote anything.

**Six results. Four confirm a prediction; two do not.**

1. **The 31 rows classify exactly as predicted** — 12 / 6 / 10 / 3 — and the
   classification is read off the sheet's own `Type` column, not inferred.
2. **Exactly one product's rows disagree, and it is Loved & Cherished.** The
   product-level spec assumption holds everywhere else.
3. ⚠️ **The md5 in every dispatch is of the PAYLOAD, not the file.** `md5 <file>`
   does not reproduce it, and nothing said so.
4. ⚠️ **`personalization_capability` was `NOT NULL`, so all 21 products asserted
   "takes no personalization"** — a measurement's clothes on something nobody
   measured. Same false assertion as `is_manufactured`, caught before a consumer
   trusted it. ⚠️ **CORRECTED 2026-10-03:** this said `NOT NULL DEFAULT list` and
   blamed the default. The writer was `r188:409`, a hardcoded literal in the
   insert loop — see §5.
5. ⚠️ **The dispatch names four products as having an empty personalization set.
   Eight in-scope products do.** The four are correct and not exhaustive.
6. ⚠️ **My width-exceeds-length check reported zero flagged over 128 comparisons
   — and could not have flagged the one row it existed for.**

---

## 0. The md5 does not reproduce from its own instructions

    expected (every dispatch)                 ab25952750488f826c4738aab9744b18
    md5 of the committed file                 1157ff1cee4778fbc561036976e6a4e1
    md5 of bytes 1347..EOF                    ab25952750488f826c4738aab9744b18  ✓

The commit that landed the sheet prepended a 24-line comment block **before the
UTF-8 BOM** that opens the original upload. So the payload is byte-identical to
what James uploaded — which is what the comment block claims and what matters —
but the whole-file hash differs by exactly the comment block, and the file's own
header quotes the payload hash without saying how to reproduce it.

To check it:

```
tail -c +1347 docs/catalog/2026-10-02-sunnycrest-product-specs.csv | md5
```

`grep -v '^#' … | md5` does **not** work: `grep` appends a trailing newline the
original lacks (its last byte is `,`). This cost one wrong reading before the
offset method was used.

⚠️ **A STOP condition that cannot be evaluated from its own instructions reads as
a failed verification.** The instruction was "verify the md5 before reading it";
following it literally returns a mismatch and halts the pass. Recorded because
the next person to check this sheet will hit the same thing.

## 1. 0a — the mapping, all 31 rows

Line numbers are **payload lines, header = line 1**, matching r189's and r191's
citations. File line = payload line + 24.

Product identity is `(family_slug, form)`, verified unique across all 21 products.

### Manufactured burial vaults — 12 rows → 8 products

| line | sheet name | → product | variant |
|---|---|---|---|
| 2 | `Wilbert Bronze ` | wilbert-bronze / burial_vault | BV-WBR |
| 3 | `Bronze Triune` | **triune / burial_vault** | BV-BTRI |
| 4 | `Copper Triune ` | **triune / burial_vault** | BV-CTRI |
| 5 | `Stainless Steel Triune(SST)` | **triune / burial_vault** | BV-SSTRI |
| 6 | `Veteran` | **triune / burial_vault** | BV-VTRI |
| 7 | `Cameo Rose` | **triune / burial_vault** | BV-CRTRI |
| 8 | `Venetian` | venetian / burial_vault | BV-WVEN, BV-GVEN |
| 9 | `Continental` | continental / burial_vault | BV-CON |
| 10 | `Salute` | salute / burial_vault | BV-SAL |
| 11 | `Monticello` | monticello / burial_vault | BV-MON |
| 12 | `Monarch` | monarch / burial_vault | BV-MRC |
| 13 | `Grave Liner` | graveliner / **grave_liner** | GL-STD, GL-SS |

Line 13's sheet name is still `Grave Liner`; r190 renamed the *product* to
`Graveliner`. The sheet is the source and is left alone.

### Non-manufactured — 6 rows → NO product (out of scope)

| line | sheet name |
|---|---|
| 14 | `Monticello 34"` |
| 15 | `Large 34"` |
| 16 | `Large 36"` |
| 17 | `Large 40"` |
| 18 | `Youth MT` |
| 19 | `Youth GL` |

No `product_template` exists for any of these. Phase 2b-3 adds them. r193 names
all six in `_OUT_OF_SCOPE` and asserts it skipped exactly six, so the skip is
auditable rather than a silent filter.

### Urn vaults — 10 rows → 6 products

| line | sheet name | → product | variant |
|---|---|---|---|
| 20 | `Bronze Triune Urn Vault` | **triune / urn_vault** | UV-BTRI |
| 21 | `Copper Triune Urn Vault` | **triune / urn_vault** | UV-CTRI |
| 22 | `Stainless Steel Triune (SST) Urn Vault` | **triune / urn_vault** | UV-SSTRI |
| 23 | `Veteran Urn Vault` | **triune / urn_vault** | UV-VET |
| 24 | `Cameo Rose Urn Vault` | **triune / urn_vault** | UV-CRTRI |
| 25 | `Venetian Urn Vault` | venetian / urn_vault | UV-WVEN, UV-GVEN |
| 26 | `Monticello Urn Vault` | monticello / urn_vault | UV-MON |
| 27 | `Universal Urn Vault (P400WS)` | universal / urn_vault | UV-UWS, **UV-UCG** |
| 28 | `Basic Gray Urn Vault (P410)` | **salute / urn_vault** | UV-SAL |
| 29 | `Graveliner Urn Vault` | graveliner / urn_vault | UV-GL |

**Both ruled mappings verified rather than assumed.**

- **Line 28 → UV-SAL.** Wilbert sells one listing as "Basic Gray/Salute Urn
  Vault". `sunnycrest_product_seeder.py:182-183` already carries `Salute Urn
  Vault` / `UV-SAL` at 436.00 and predates every 2026-10-02 conclusion, so
  today's reading agrees with what was already in the repository rather than
  replacing it with a guess. Recorded in
  `docs/catalog/sunnycrest-catalog-review-ANNOTATION.md` §2 as a false negative.
- **Line 27 → the universal PRODUCT.** The sheet names a MODEL (`P400`**WS**)
  where our catalog names a FINISH. ⚠️ So `UV-UCG` (Cream & Gold) correctly has
  **no row of its own** and reads through to the product. That is the
  product-level model working, not a gap — stated explicitly, and pinned by a
  test, so it is not later read as missing data.

### Loved & Cherished — 3 rows → 1 product, at the VARIANT tier

| line | sheet name | → variant |
|---|---|---|
| 30 | `Loved & Cherished  31` | LC-31 |
| 31 | `Loved & Cherished  24` | LC-24 |
| 32 | `Loved & Cherished 19` | LC-19 |

### Unmappable rows: none. Products with no row: six.

Every one of the 25 in-scope rows maps to exactly one product. The 6
non-manufactured rows map to nothing *because the product does not exist yet*,
which is a scope boundary rather than a failed mapping.

**Six products have no row in the sheet, exactly as predicted:**

    tribute / burial_vault          Tribute Burial Vault
    chairs / equipment              Chairs
    cremation-table / equipment     Cremation Table
    grass-mats / equipment          Grass Mats
    lowering-device / equipment     Lowering Device
    tent / equipment                Tent

## 2. 0b — agreement, for every product with more than one row

**Only three products have more than one CSV row.** Every other product has
exactly one, so "do its rows agree" does not arise for them.

| product | rows | dimensions | weight | verdict |
|---|---|---|---|---|
| triune / burial_vault | 3,4,5,6,7 | `86 × 30 × 25½` / `91¼ × 35¼` on all five | 3000 on all five | **AGREE** |
| triune / urn_vault | 20,21,22,23,24 | `12½ × 12½ × 13¾` / `14-5/16 × 14-5/16` on all five | absent on all five | **AGREE** |
| loved-and-cherished / infant | 30,31,32 | all six dimensions differ | absent on all three | ⚠️ **DISAGREE** |

**The prediction holds exactly: one disagreement, and it is Loved & Cherished.**
The STOP does not fire.

    LC-31   31-1/8 × 10-5/8 × 12-1/4    out 36-1/4 × 15-3/8 × 14
    LC-24   23-5/16 × 9-1/8 × 10-1/8    out 26 × 11-13/16 × 11-1/4
    LC-19   18 3/8 × 8 × 7              out 20 1/16 × 9 ¾ × 8 3/4

Model is a **size** axis there; everywhere else a variant is a **finish**, and a
finish does not change the object's size.

⚠️ Lines 21 and 22 carry a double space (`12½ × 12½  × 13¾`). That is a
whitespace difference, not a value difference, and whitespace is collapsed before
comparison. Stated so the "AGREE" verdict is not read as having ignored it.

## 3. 0c — what the parser refuses, and what it only appears to accept

The parser attempted **173** figures across the 31 rows: **172 parsed, 1
refused**, 44 cells blank. Every one of the 172 is **sixteenths-exact**, which
confirms the sheet's stated convention rather than assuming it.

### The one refusal

    line 29  Graveliner Urn Vault  OUT = " 151/2 x 18 x 13"
             component 1: `151/2`

`151/2` has **no separator** between a possible whole number and a fraction, so
it reads as either `15½` or `151/2` and nothing in the sheet decides which. The
parser raises rather than returning 15.5. ⚠️ A column later read as a clearance
measurement by a driver with a vault on a truck is the wrong place for a parser's
judgment call.

The rule that catches it, stated so it generalises: a bare `a/b` with no
separator is accepted only while **proper** (`1/2` is a half). `151/2` is
improper, which is the signature of a missing separator. `31-1/8` and `18 3/8`
have separators and are unambiguous.

### Its two companions are discarded with it

Line 29's **outside width is 18" against an inside width of 12"** — a growth of
+6.00". Measured across all ten urn-vault rows:

    +1.8125"   lines 20-26  (seven rows)
    +3.0000"   lines 27-28  (two rows)
    +6.0000"   line 29      ← 2.0x the next largest, 3.3x its own class

So the triple is suspect for a second, independent reason, and all three outside
figures for line 29 are left NULL. **Its inside triple parses cleanly and is
loaded** — this is a refusal of one reading, not of the row.

### ⚠️ The check that should have caught the width could not have

A width-exceeds-length comparison over all 31 rows **made 128 comparisons and
flagged 0**. It needs both length and width; line 29's length is the unparseable
value, so the comparison was **skipped for the one row it existed for**.

`0 flagged` is also what a check that never ran returns. The positive control
(128 comparisons made, non-zero) proves the instrument was alive — and the
instrument being alive is not the same as it having looked at the case in
question. See CLAUDE.md §11, "A control that cannot distinguish itself from a
failure is not a control". The width is evidenced above by the growth
measurement, which needs no length.

### Absences that are the sheet's design, not parse failures

- **Outside height is absent for 25 of 31 rows.** The column is headed
  `OUT (inches) LxW` and carries two components for 25 rows, three for six
  (lines 27-32). ⚠️ The header is wrong for those six rows; the data is what is
  read, and the discrepancy is recorded rather than resolved.

  ⚠️ **It lands on only 2 products** — universal/UV and salute/UV — **plus the 3
  L&C variants.** This paragraph first said 5 products. Of the six
  three-component rows, three are L&C *variants* rather than products and one
  (line 29) has its whole triple refused, leaving two. Nothing stale in the
  wording pointed at it; it was caught by counting the stored rows. Recorded
  because it is the same shape as r188's "four family slugs" claim — a figure
  with no stale identifier beside it, catchable only by arithmetic.
- **Weight is absent for 19 of 31 rows** — every urn vault (10), every Loved &
  Cherished (3), every non-manufactured vault (6). Present for all 12
  manufactured burial vaults. A lift rating and a truck load depend on that
  number, so it stays NULL rather than being taken from a sibling.

### Cosmetic irregularities, parsed and not normalised in the source

Trailing spaces in product names (lines 2, 4), a leading space in line 29's
outside cell, double spaces inside lines 21, 22, 27, 28, and a double space in
`Loved & Cherished  31` / `  24` where `19` has one. Line 32 mixes a unicode `¾`
and an ASCII `3/4` within one cell. All parse; none is rewritten in the CSV.

## 4. 0d — the three personalization question ids, from the declaration site

Read from `backend/app/services/personalization/questions.py` rather than
confirmed against the dispatch. `QUESTIONS` is a **3-tuple** and there is no
fourth id anywhere:

| id | `display_label` in code | CSV label |
|---|---|---|
| `legacy_print` | `Legacy Series™ Print` | `Legacy` |
| `nameplate_cover_emblem` | `Nameplate & Cover Emblem` | `Nameplate + Emblem` |
| `lifes_reflections` | `Life's Reflections® Vinyl` | `Life's Reflections` |

**Exactly as named in the dispatch. The STOP does not fire.** Stored in the
declaration's order, so a reader comparing a stored list against the canonical
enumeration sees the same sequence. r193 asserts every id it writes is in that
set.

⚠️ The first grep for these returned **zero matches for all three** — zsh
glob-expanded an unquoted `--include=*.py` and the command never ran. A positive
control on a string known to be present is what surfaced it. A false absence here
would have fired a STOP on a condition that was in fact satisfied.

## 5. ⚠️ `personalization_capability` could not express "unknown"

r186 declared it `JSON NOT NULL`. All 21 products therefore read `[]`, and under
the semantics the column exists for:

    []     the product physically takes NO personalization   — a FINDING
    NULL   nobody has established what it takes              — an ABSENCE

**a NOT NULL column cannot express the second, so the first was being asserted 21
times by default**, including for Tribute and the five equipment products that
the sheet says nothing whatever about.

⚠️ **This is the `is_manufactured` defect, one table over and caught before it
shipped.** `2026-10-02-platform-catalog-discrepancies.md` §4 records a rule that
would have read `is_manufactured=False` — a NOT NULL column default — as a
deliberate tenant override and pinned every Wilbert vault as not-manufactured
permanently. Same column shape, same mechanism. The only reason this one was
caught is that someone asked what `[]` was asserting before writing a consumer
that trusts it.

**Part 1 therefore includes a change Part 1 did not name**: drop the NOT NULL,
drop the default, reset all 21 to NULL. Part 3's requirement — *"Every product
WITHOUT a CSV row has NULL specs and NULL personalization_capability"* — is
unsatisfiable without it, so the change is forced rather than chosen. It is also
pure expansion: widening nullability cannot break a reader compiled against the
narrower type, so a rolling deploy is safe in either order.

Zero consumers exist today (`grep -rni personalization_capability` over `backend`
and `frontend` returns nothing outside the model and the migrations), so the
reset destroys no information — there was none to destroy.

## 6. ⚠️ Eight in-scope products have an empty personalization set, not four

The dispatch names *"Monticello, Monarch, Grave Liner and the Monticello urn
vault"*. All four are correct. **The list is not exhaustive.** Read off the
sheet's own cells:

| capability | products | lines |
|---|---|---|
| all three questions | wilbert-bronze, triune/BV, venetian/BV, triune/UV, venetian/UV | 2, 3-7, 8, 20-24, 25 |
| `nameplate_cover_emblem` only | continental, salute/BV | 9, 10 |
| **empty set** | monticello/BV, monarch, graveliner/GL, monticello/UV, **universal/UV**, **salute/UV**, **graveliner/UV**, **loved-and-cherished** | 11, 12, 13, 26, 27, 28, 29, 30-32 |
| **unknown (no row)** | tribute, chairs, cremation-table, grass-mats, lowering-device, tent | — |

5 + 2 + 8 = 15 covered, + 6 unknown = 21. The four extra empties are the two
ruled urn-vault mappings, the Graveliner urn vault, and Loved & Cherished.

## 7. What this does not establish

- **Whether any empty cell means "takes none" or "not filled in".** The sheet
  gives one blank for both. r193 stores `[]` — the finding — because the sheet is
  the authority the dispatch names, but a blank cell is weaker evidence than a
  populated one and nothing here distinguishes them.
- **Whether line 29's `151/2` is 15½.** It is left NULL. Resolving it needs a
  re-read off the source, which is James's.
- **Whether line 29's width is 18.** It is left NULL on the strength of the
  growth measurement, which says the figure is anomalous, not what it should be.
- **Monticello 34" (line 14) vs Large 34" (line 15).** Both 90 × 34 × 28 inside,
  differing only in outside length (95 vs 94). Whether these are two products or
  one named twice is 2b-3's question; both are out of scope here.
- **Whether `GL-SS` is a real grade**, carried forward unresolved from r188.
- **Any weight for any urn vault, L&C, or non-manufactured vault.** 19 rows,
  absent at source.
