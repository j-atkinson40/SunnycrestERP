# Linking Sunnycrest to the platform catalogue, and giving customers a type

**2026-10-28.** James's two rulings, with his go for both production writes. Mapping
produced read-only first; writes applied, verified by independent read-back, idempotent
on re-run, rollback SQL recorded. Script: `backend/scripts/apply_rulings_2026_10_28.py`
(dry run by default).

---

## Ruling 1 — `products.variant_template_id`

### The mapping, all 10, with the reason

`products.variant_template_id` → `product_variant_templates.id` (52 rows,
`ON DELETE RESTRICT`) → `product_templates` (29, carrying `form` and the dimensions).
Availability is keyed on the **variant**, which is why the variant is the target.

| Sunnycrest product | sku | verdict | reason |
|---|---|---|---|
| **Monticello Burial Vault** | DEMO2-P001 | **WRITTEN** → `8a3c6253` | Exact match on **both** `product_templates.display_name` and `product_variant_templates.display_name`. The catalogue's own `product_name_resolver` returns exactly **one** candidate and agrees. form=`burial_vault`, family=`monticello`, variant sku `BV-MON`, outside 90.5×34.5. |
| Continental Burial Vault | DEMO2-P002 | **NULL — ambiguous** | **Two** variants under one template: `BV-CON` (option "Standard") and `BV-CON34` (option "34 inch"). Both `burial_vault`. The resolver returns 2 candidates and abstains. ⚠️ Their recorded outside dimensions are **identical** (90.5×34.5 for both), so size cannot disambiguate either — which is itself worth a look, since a 34-inch variant differing from standard only in name is suspicious catalogue data. |
| Urn Vault – Standard | DEMO2-P003 | **NULL — no match** | 12 `urn_vault` variants exist; **none** is named "Standard" and no urn-vault template carries a "Standard" option. The options are Monticello / Salute / Triune ×5 colours / Universal ×2 / Venetian ×2 / Graveliner. Picking one would be inventing. |
| Full Equipment | CE-PKG-FULL | **NULL — one-to-many** | The `equipment` form offers Chairs, Cremation Table, Grass Mats, Lowering Device, Tent (Single/Double). "Full Equipment" is a **package of several**, not one variant. A single-id column cannot express it. |
| Lowering Device & Grass | CE-PKG-LDG | **NULL — one-to-many** | Package of two catalogue items (Lowering Device + Grass Mats). |
| Lowering Device Only | CE-PKG-LD | **NULL — judgement, not identity** | There is exactly one `Lowering Device` variant (`CE-LD`), and "Only" is Sunnycrest's package qualifier. Arguable, but it is not a name or sku match — it is me deciding what the qualifier means. |
| Tent Only | CE-PKG-TENT | **NULL — ambiguous** | `Tent` has two options, **Single** (`CE-TS`) and **Double** (`CE-TD`). Nothing in the tenant row says which. |
| Vault Placer | CE-PKG-VP | **NULL — no match** | No equipment variant for a vault placer exists in the catalogue at all. |
| Extra Chairs (Over 8) | CE-CHAIR-EX | **NULL — a pricing rule, not a product** | `Chairs` (`CE-CH`) exists, but "(Over 8)" is a quantity threshold on a charge, not a distinct catalogue item. |
| Graveside Setup Service | DEMO2-P004 | **NULL — no match** | A service. No catalogue counterpart. |

**Written: 1 of 10. Left NULL: 9.** Per the ruling — unambiguous only.

⚠️ **AND LINKING EQUIPMENT WOULD ACHIEVE NOTHING FUNCTIONAL EVEN IF IT MATCHED.**
`variant_template_id` feeds personalization availability, and the personalization
question applies only to `urn_vault` / `burial_vault` forms. Six of the nine NULLs are
equipment. So the backlog is five vault/service rows, not nine.

### ⚠️ Ruling 1's last clause cannot be satisfied, and the reason is not a defect

> "Then show the personalization-clear rule firing on a real Sunnycrest vault."

**Monticello — the one vault now linked — takes no personalization, measured.**

```
Monticello Burial Vault   BV-MON
  personalization_capability = []   spec_source = docs/catalog/2026-10-02-sunnycrest-product-specs.csv
  availability               = []   spec_asof   = 2026-10-02
  -> personalization is NOT ASKED, so there is nothing to clear
```

⚠️ **I EXPECTED THIS TO BE AN UNMEASURED FILL AND IT IS NOT.** All 40 availability rows
were written in one bulk insert (`2026-10-12 12:16:22.439166`, 19 of them empty), which
is the signature CLAUDE.md warns about — so I checked the spec-sheet column against the
availability table across every burial and urn vault: **0 contradictions**, and
Monticello's `[]` carries a `spec_source` and a `spec_asof`. It is Sunnycrest's own spec
sheet saying the Monticello takes none. The rule not firing on it is **correct
behaviour**.

**So the only Sunnycrest vault that can exercise the rule is Continental — the ambiguous
one.** Demonstrated on real production catalogue data (read-only, the name→variant lookup
stood in because the link is deliberately unwritten):

```
Triune / Bronze      permits  legacy_print, nameplate_only, nameplate_and_cover_emblem,
                              cover_emblem_only, lifes_reflections, nameplate_and_lifes_reflections
Continental          permits  nameplate_only
office picked        legacy_print on the Triune, then changed the vault
-> personalization cleared, footer:
   "Legacy Series™ Print cleared: the Continental Burial Vault doesn’t offer it."
```

⚠️ **AND THE AMBIGUITY IS IRRELEVANT TO THIS QUESTION.** Both Continental variants permit
exactly `('nameplate_only',)` — identical. So the capture engine is indifferent between
them; the ambiguity matters for **which physical product Sunnycrest sells** (size, price),
not for personalization.

**The decidable question for James: does Sunnycrest sell the Continental Standard
(`BV-CON`), the Continental 34-inch (`BV-CON34`), or both?** One word links it and the
rule fires through a Sunnycrest product rather than through a stand-in.

One other disagreement, noted not acted on: **`Salute Urn Vault` (`UV-SAL`)** has
spec-sheet capability `[]` while availability offers three answers — availability
permitting something the spec sheet says the product cannot physically take. One case,
and not Sunnycrest's product.

---

## Ruling 2 — `customers.customer_type`

### Before → after

| customer | account | before | after |
|---|---|---|---|
| Hopkins Funeral Home | DEMO2-C001 | `None` | **`funeral_home`** |
| Riverside Memorial Chapel | DEMO2-C003 | `None` | **`funeral_home`** |
| Lakeside Funeral Directors | DEMO2-C005 | `None` | **`funeral_home`** |
| St. Mary's Cemetery | DEMO2-C002 | `None` | **`cemetery`** |
| Fairview Burial Services | DEMO2-C004 | `None` | `None` — see below |

`classification_method = 'manual'` on each write, with the ruling recorded in
`classification_reasoning`. ⚠️ A type with no method is a value whose provenance was
discarded at the moment it was created.

### What "Fairview Burial Services" is, and why it no longer shows

**Demo seed data.** `scripts/seed_accounting_demo.py:_CUSTOMERS` creates all five of
Sunnycrest's customers in one transaction at `2026-08-10 15:00:48`, and that literal
carries only `(name, account_number, receives_monthly_statement)` — it **declares no type
for any of them**. So no repo artifact says what Fairview is, and its name is the only
signal. "Burial Services" is genuinely ambiguous in the trade between a funeral home and
an interment/grave-services vendor, which is the other side of the transaction.

**Why it no longer shows under "Which funeral home?" — two independent reasons now.** It
has zero orders (the fix in `8eef3e71`), and its `customer_type` is not `funeral_home`
(this ruling). Either alone suffices.

⚠️ **Left NULL deliberately.** Typing it `funeral_home` on the strength of its name is the
unmeasured-value defect CLAUDE.md names — a plausible business value written to a row
nobody measured. One word from James settles it; it is a one-line follow-up.

### The two halves of the ruling bind different tables

⚠️ This is the part worth knowing, because it is not visible from either call site alone:

```
the PILLS      rank from order facts, look names up in `customers`
the TYPED path party_resolver.resolve_funeral_home -> `company_entities`,
               which deliberately filters on NO role flag
```

So the type filter went on the pills only. The typed path is untouched, which is what
keeps the ruling's second clause true — **a cemetery typed by name is still accepted as
the customer**, verified by test and by production read (`"St. Mary's Cemetery"` resolves
to a candidate).

⚠️ **`company_entities` holds only 3 of the 5** (Hopkins, Riverside, St. Mary's). **Lakeside
and Fairview are not in it at all**, so they cannot be typed as the funeral home by name
today. Pre-existing, not caused by this change, and worth a separate look.

### ⚠️ The filter applies only where the tenant has typed something — and my first comment about that was false

A bare `WHERE customer_type = 'funeral_home'` offers **zero** funeral homes on an
unclassified licensee, turning "nobody has typed these yet" into "none of these is a
funeral home". So the filter is gated on the tenant having typed *anything*.

⚠️ **I wrote that gate with the justification "Sunnycrest is the only typed tenant". That
was false, and a test control caught it on the first run.** `seed_staging.py` has been
setting `customer_type = 'funeral_home'` on `FH-001`…`FH-005` all along. Measured on dev:
testco is **261 customers, 5 typed funeral_home, 256 NULL** (`Fixture …` / `Cert
Fixture …` litter). The real shape is **partial** typing, which is the case the gate has
to be right about — and it is: testco's pills now offer its four most-ordered typed homes
and exclude all 256 untyped fixture rows.

**Stated cost of the strict reading** (which is what "funeral homes **only**" asks for): on
a partially typed tenant, a real funeral home that has orders but has not been typed drops
out of the pills until someone types it. Measured, nobody is in that position today.

### ⚠️ No pad, deliberately — and it keeps your walk exact

"Pills offer funeral homes **only**" is a restriction, not an instruction to add zero-order
funeral homes. **Lakeside is typed `funeral_home` and has 0 orders, so it does not appear** —
which is why the walk still shows exactly Hopkins and Riverside. The last time this branch
padded from the customer table it was a pad no dispatch asked for, and that is what put
St. Mary's under "Which funeral home?" in the screenshot. The type column now makes
padding a one-line change if James wants it; this is not that change.

---

## The walk, read-only on production, post-rulings

```
STEP 1  "Which funeral home?"   ⌥1 Hopkins Funeral Home   ⌥2 Riverside Memorial Chapel
STEP 2  Monticello Burial Vault -> form=burial_vault via=name_resolver cremation=False
        equipment: Full Equipment / Lowering Device & Grass / Tent Only / Lowering Device Only
STEP 3  Urn Vault - Standard    -> form=urn_vault via=recorded_name cremation=True
        chip "Cremation"
        equipment now: Tent Only / Extra Chairs (Over 8) / None
        equipment cleared; footer:
          "Full Equipment cleared: an urn vault means a cremation setup."
```

⚠️ **Step 3 works through `recorded_name`, the LAST rung of the form ladder, not the
link.** `Urn Vault – Standard` matches no catalogue template, so its form is read from its
own name. The cremation path has never depended on `variant_template_id` — which is why
the walk was already sound before today's write and stays sound with 9 of 10 still NULL.

Rollback for every write is in the script's output and reproduced here:

```sql
UPDATE products  SET variant_template_id = NULL WHERE company_id = '090e7eeb-…' AND sku = 'DEMO2-P001';
UPDATE customers SET customer_type = NULL, classification_method = NULL WHERE company_id = '090e7eeb-…' AND account_number = 'DEMO2-C001';
UPDATE customers SET customer_type = NULL, classification_method = NULL WHERE company_id = '090e7eeb-…' AND account_number = 'DEMO2-C003';
UPDATE customers SET customer_type = NULL, classification_method = NULL WHERE company_id = '090e7eeb-…' AND account_number = 'DEMO2-C005';
UPDATE customers SET customer_type = NULL, classification_method = NULL WHERE company_id = '090e7eeb-…' AND account_number = 'DEMO2-C002';
```
