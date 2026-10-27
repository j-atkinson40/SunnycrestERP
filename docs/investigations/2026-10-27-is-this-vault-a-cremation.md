# "An urn vault marks the order a cremation" — what can actually tell

Measured against **production**, read-only, 2026-10-27, while building guided
capture slice 1. The dispatch's clause 2 says:

> An urn vault marks the order a cremation: the pane shows a "Cremation" chip and
> the equipment question offers the cremation setups from the catalog.

So something has to answer *is this vault an urn vault?* from a captured value
like `"Monticello Burial Vault"` or `"Urn Vault - Standard"`. Four candidates
existed. **Three are unreachable and the fourth is the product's own name.**

## The designed marker exists and nothing reaches it

`product_templates.form` is exactly the right column, with exactly the right
vocabulary:

```
form           rows
urn              8
burial_vault     8
urn_vault        6
equipment        5
grave_liner      1
infant           1
```

The path from a tenant's product to it is declared in full —
`products.variant_template_id` → `product_variant_templates.product_template_id`
→ `product_templates.form` — and every FK in that chain exists.

⚠️ **`products.variant_template_id` IS POPULATED ON 0 OF 39 ROWS.**

```
products.variant_template_id: 0 of 39 rows carry a value
[sunnycrest]  0 of 10 active products reach a form
[testco]      0 of 25 active products reach a form
```

This is CLAUDE.md §11's *complete machinery behind an unprovisioned entrance*,
and it is the second time this column has been the subject: CLAUDE.md already
records that `r186` added `products.variant_template_id` and **declared it
nowhere**, so "the link the whole catalog design resolves through was
unreachable". Declaring it made it expressible. Nothing has since written it.

## The other two candidates

**`products.personalization_tier`** — the comment above it lists `'urn_vault'` as
a value. Measured: **NULL on every active product on both tenants.** Not a
marker, and it is about personalization rather than form in any case.

**`products.sku`** — the platform's catalogue uses a clean scheme (`UV-MON`,
`UV-SAL`, `UV-GL` for urn vaults; `BV-` for burial). Tenant products do not use
it:

```
[sunnycrest]  Urn Vault - Standard        sku=DEMO2-P003
              Monticello Burial Vault     sku=DEMO2-P001
[testco]      Monticello                  sku=MN-001
```

Tenant-local prefixes, unrelated to the platform scheme.

**`product_categories`** — `product_catalog_templates.category` carries
`Burial Vaults` (19), `Urn Vaults` (12), `Cemetery Equipment` (6) at the PLATFORM
tier. Per-tenant, measured:

```
testco      Burial Vaults - Double Reinforced   5
testco      Burial Vaults - Non Reinforced      3
testco      Burial Vaults - Single Reinforced   5
testco      Burial Vaults - Triple Reinforced   1
testco      Graveside Service                   6
testco      Other Charges                       5
sunnycrest  (no rows at all)
```

⚠️ **SUNNYCREST HAS NO PRODUCT CATEGORIES, AND TESTCO HAS NO URN CATEGORY.** So
the per-tenant category layer cannot answer the question on either tenant — on
the one James walks it does not exist, and on the other it has no urn bucket.

## What this slice therefore does

A five-step ladder, each step measured rather than assumed, in
`capture/vault_form.py`:

| # | Step | Reaches, today |
|---|---|---|
| 0 | `product_name_resolver` — the catalogue's own resolver | full platform names |
| 1 | tenant product → `variant_template_id` → `product_templates.form` | **nothing** (0/39) |
| 2 | platform `product_templates.display_name` → `form` | the 6 named urn vaults + 8 burial |
| 3 | platform `product_catalog_templates.product_name` → `category` | 12 urn + 19 burial |
| 4 | the tenant's own product category | testco's 14 vaults |
| 5 | the recorded vault name itself | everything else |

⚠️ **STEP 0 WAS ADDED AFTER I HAD WRITTEN THE OTHER FOUR, and it is the half of
this finding worth keeping.** The platform already answers this question:
`resolve_schema` takes a `vault_form` argument, and `typed_extraction` already
fills it from `resolve(index, phrase).candidates[0].form`. I was one commit from
shipping a second detector beside an existing one — two answers to one question,
which is the shape this codebase keeps finding and paying for. Measuring the
existing resolver against my ladder is what surfaced it.

⚠️ **AND THE EXISTING CALLER IS STRICTER THAN IT NEEDS TO BE.** It takes a form
only when the phrase resolves to ONE variant, warranted as: *"An ambiguous set can
span forms ('Graveliner' spans grave_liner and urn_vault), so a form read off
candidates[0] would be whichever the sort put first."* That is right about
SPANNING sets and too strict about AGREEING ones. Measured: `Continental Burial
Vault` returns **two** candidates — the 34-inch and the standard, differing only
by size — and **both are `burial_vault`**. Abstaining there discards an answer the
catalogue is unanimous about.

Step 0 therefore asks for UNANIMITY rather than uniqueness. `Graveliner` (5
candidates across two forms) still abstains, which is the case the original
warrant protected. ⚠️ `typed_extraction`'s own call is left alone: there a form
decides which personalization questions APPLY, and loosening it is a separate
ruling with a different blast radius.

⚠️ **STEP 4 EXISTS BECAUSE A PROBE FOUND THE LADDER SILENT ON TESTCO** — the
tenant this dispatch names for verifying the urn path. Testco's vaults are bare
family names (`Monticello`, `Continental`, `Salute`, `Venetian`, `Monarch`,
`Tribute`): they match no platform product name and contain no "vault" word, so
20 of 25 returned nothing. Testco files them under `Burial Vaults - Single
Reinforced` and the like, which is an answer about testco's own product. A bare
family name is genuinely ambiguous at the PLATFORM tier — `monticello` has two
templates, one burial and one urn — which is why this step reads the tenant's
category rather than the family.

⚠️ **STEP 1 IS FIRST EVEN THOUGH IT ANSWERS NOTHING**, deliberately. It is the
designed path; the moment a tenant's products are linked it becomes the
authoritative answer and the lower steps stop being consulted. Putting it last,
or leaving it out because it is currently dead, would mean the correct answer
arriving and being overruled by a name match.

⚠️ **AND STEP 4 IS THE ONE THAT CARRIES SUNNYCREST TODAY.** `Urn Vault -
Standard` matches no platform row — the platform's twelve urn vaults are named
`Monticello Urn Vault`, `Salute Urn Vault`, `Universal Urn Vault (Cream &
Gold)` and so on, and none of them is `Urn Vault - Standard`. So on the tenant
James walks, the only thing that says the order is a cremation is the two words
in the product's own name.

That is a weak basis and it is stated as one. It is NOT a one-word stoplist of
the kind ruled out for the "Smith It" defect — it reads the product's own
recorded name, which is where a product's category genuinely lives when nothing
else records it — but it will mis-answer the first vault whose name does not say
what it is.

## ⚠️ The one-line fix, which is James's call and not mine

Populate `products.variant_template_id`. It makes step 1 live, makes steps 2-4
dead code that never runs, and fixes the same gap for everything else that wants
to know a product's form — pricing, personalization availability, the catalogue
panes. `platform_product_aliases.variant_template_id` and
`platform_personalization_availability.variant_template_id` already point at the
same place, so the join is the designed one and not a new idea.

It is not in this slice because the dispatch is read-only on the catalogue and
because a backfill across 39 production rows is a write that deserves its own
ruling. Reported rather than done.


## ⚠️ The urn path cannot be verified end to end on testco

The dispatch asks for *"the urn path end to end on testco"*. Measured: **every one
of testco's 14 vaults is `burial_vault`.** Testco has no urn vault, in its
products or in its categories, so there is no value a director could pick there
that would make the order a cremation.

The only urn vault anywhere in production is **sunnycrest's `Urn Vault -
Standard`**, which is why the urn path is verified there instead and why that
verification rests on step 5.

Not worked around — seeding an urn vault into testco is a production write, and
the dispatch is read-only on the catalogue. Reported so the gap is James's to
close rather than mine to paper over.

---

## What the production walk verified, and two gaps it exposed

Run read-only against production on both tenants, 2026-10-27, after the build.

### The urn path, end to end on sunnycrest — WORKS

With no vault chosen, the equipment question reads:

```
cemetery_equipment   What equipment?
                     hint: Chairs come with every setup except the device alone.
                     ⌥1 Full Equipment  ⌥2 Lowering Device & Grass  ⌥3 Tent Only  ⌥4 Lowering Device Only
```

With `Urn Vault - Standard` chosen (`cremation=True`, `via=recorded_name`):

```
cemetery_equipment   What cremation setup?
                     hint: It’s an urn vault, so these are the cremation setups.
                     ⌥1 Tent Only  ⌥2 Extra Chairs (Over 8)  ⌥3 None
```

The sentence changes, the hint changes, and the four burial packages drop to the three
that apply. The vault pill itself carries `· cremation`.

### ⚠️ GAP 1 — "Vault Placer" was offered as a vault, and the probe is what found it

The catalogue fallback matched `lower(name) LIKE '%vault%'`, which is true of a piece of
graveside equipment. On sunnycrest it appeared at **⌥4 under "Which vault?"**. Fixed by
asking `form_of` instead of the name: a vault pill must have a form in `VAULT_FORMS`.

⚠️ **NEITHER REVIEW NOR THE SUITE FOUND THIS.** 33 tests were green, the break harness
was 24-for-24, and the defect was in the one place neither looked — what the query
returns against real rows. It is the §11 shape where a check has full contact with the
code and no contact with the world.

### ⚠️ GAP 2 — a cemetery is offered under "Which funeral home?", and no column can say otherwise

Sunnycrest's five customers, measured:

```
Hopkins Funeral Home         type=None  orders=3
Riverside Memorial Chapel    type=None  orders=1
Fairview Burial Services     type=None  orders=0
Lakeside Funeral Directors   type=None  orders=0
St. Mary's Cemetery          type=None  orders=0
```

`customers.customer_type` is **NULL on every one**, so there is no field that
distinguishes a funeral home from a cemetery. The pills rank by order history, so
Hopkins and Riverside come first; the remaining two slots are filled from the active
customer list, and `St. Mary's Cemetery` lands in one of them.

**Not fixed, deliberately.** The available fixes are a name rule ("exclude anything
containing 'Cemetery'") or a product decision about which customers may answer this
question. The first is the shape James ruled out for the "Smith It" defect; the second
is his call. ⚠️ And a cemetery buying a vault is a real transaction in this business —
it may be that the field is misnamed rather than the data wrong.

The remedy is data: populate `customers.customer_type`.

### ⚠️ GAP 3 — testco's equipment question offers only "None"

```
[testco] cemetery_equipment   What equipment?
                              ⌥1 None
```

`_tenant_equipment` keeps only packages the tenant can bill, and billing needs the
product name to match `EQUIPMENT_PRODUCT_NAMES` through
`approval._product_by_exact_name` — which is exact. Testco's equipment products are
named `Full Equipment (with product)`, `Tent Only (without)`, `Lowering Device & Grass
(with)` and so on, and none matches.

**This is the pills telling the truth.** Testco genuinely cannot bill "Full Equipment":
`assess` would report a blocker. Offering it anyway would be the door promising what it
cannot do (2026-10-26). Sunnycrest, whose products are named as the platform names
them, offers all four.

Reported rather than fixed because the fix is either renaming testco's products or
loosening the billing match — both writes, neither in this slice's scope.
