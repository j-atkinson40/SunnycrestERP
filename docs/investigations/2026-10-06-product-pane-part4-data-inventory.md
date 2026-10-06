# Product Pane — Part 4: does the data exist?

**2026-10-06. READ-ONLY. No code written.** Origin: James's addendum to the overlay
investigation, against the Product Pane spec (Notion, last edited 2026-10-03).

⚠️ **THE SPEC IS NOT IN THE REPO.** Its section list reached me as dispatch text. Per
CLAUDE.md §11 — *a dispatch may only cite sources the executor can reach* — the section
names below are what I was given, not what I read, and the Notion page should be exported
into `docs/` with a digest before anything is built from it. Everything in the right-hand
columns IS measured, against `bridgeable_dev` at migration head `r199_service_time_and_eta`.

---

## The inventory

Legend: **POPULATED** = exists with data · **EMPTY** = column/table exists, no rows or no
values · **ABSENT** = no such column or table anywhere in the schema.

### Header

| Field | Verdict | Where |
|---|---|---|
| name | **POPULATED** | `products.name` 27/27 · `product_templates.display_name` 29/29 · `product_variant_templates.display_name` 52/52 |
| kind | **POPULATED** | `product_templates.form` 29/29 (`burial_vault` etc.) · `products.category_id` |
| made here / bought in | **EMPTY** | `products.is_manufactured` — **0 of 27 non-null**, by r196's ruling. See below. |
| SKU | **POPULATED** | `products.sku` 27/27 · `product_variant_templates.sku` 52/52 |
| photo | **EMPTY** | `image_url` exists on all three tiers and is **0-populated on every one**: 0/29 templates, 0/52 variants, 0/27 products |

⚠️ The photo column was added with the note *"product pane and catalog browsing all want
the picture. Nullable, no data in this pass."* That pass never happened.

### Right now

| Field | Verdict | Where |
|---|---|---|
| low stock | **EMPTY** | `inventory_items.quantity_on_hand` + `reorder_point`, joined by `product_id` — **1 row in the whole table** |
| pending price change | **EMPTY in practice** | `price_list_versions.status` = 14 `draft`, 1 `active`. ⚠️ See the string-join defect below. |
| none on hand | **EMPTY** | same `inventory_items`, 1 row |

### Price

| Field | Verdict | Where |
|---|---|---|
| current | **POPULATED** | `products.price` 26/27 |
| last changed | **ABSENT** | No per-product price-change timestamp exists. Derivable only by joining `price_list_versions.activated_at` through `price_list_items` — see below. |
| pending | **EMPTY in practice** | draft versions exist; the join does not |
| cost (bought-in) | **EMPTY** | `products.cost_price` 0/27 · `products.wholesale_cost` 0/27 |
| supplier (bought-in) | **ABSENT** | No product→supplier link. `vault_suppliers` exists but nothing joins a product to it; `casket_products.supplier` belongs to a different vertical. |
| margin (bought-in) | **ABSENT** | Derivable as price − cost, and cost is empty |

⚠️ **THE PRICE-HISTORY DEFECT, AND IT IS THE BIGGEST FINDING IN THIS PART.**
`price_list_items` has **no `product_id`**. Its columns are `product_name`,
`product_code`, `standard_price`, `contractor_price`, `homeowner_price`. So every
price-history and pending-price question can only be answered by **matching a product by
name or code string** — 389 items across 15 versions, keyed to products by text. A pane
that claims to show "this product's price history" would be showing the history of rows
whose `product_name` happens to match, which is the `product_name_resolver` problem
appearing in a second place. Nothing about it is visible at the UI layer.

### Specs

| Field | Verdict | Where |
|---|---|---|
| size | **EXISTS, 3 of 52** | `product_variant_templates.inside_/outside_{length,width,height}_in` — 3 populated of 52 |
| weight | **EXISTS, 8 of 29 / 0 of 52** | `product_templates.weight_lb` 8/29 · `product_variant_templates.weight_lb` **0/52** |
| lining | **ABSENT** | **Zero columns matching `lining` anywhere in the schema.** Not a gap in data — the field does not exist. |

### Stock

| Field | Verdict | Where |
|---|---|---|
| on hand | **EMPTY** | `inventory_items`, 1 row |
| in production | **EMPTY** | `production_log_entries.product_id` exists — **0 rows** |
| due out this week | **ABSENT as a product fact** | `deliveries` has 40 rows and 42 columns and **no product column at all**. Reaching a product means `deliveries → sales_orders → sales_order_lines.product_id`, and only **20 of 36** order lines carry a `product_id`. |

### Pills

| Pill | Verdict | Where |
|---|---|---|
| Personalization | **POPULATED** | `Company.settings_json → personalization_availability`, read by `read_availability`; the resolver wiring shipped 2026-10-06 |
| Recent orders | **PARTIAL** | `sales_order_lines.product_id` — **20 of 36** lines linked |
| Price history | **ABSENT** | see the string-join defect |
| …other names | **POPULATED** | `platform_product_aliases` — 5 rows, 5 confirmed |
| …retired names | **ABSENT** | no column, no table |
| …usually ordered with | **ABSENT** | no column, no table |
| …substitute | **EMPTY** | `product_substitution_rules` exists — **0 rows** |
| …lead time | **EXISTS, NOT PER PRODUCT** | `vault_suppliers.lead_time_days`, `vendors.lead_time_days`; no product→supplier link to reach either |
| …truck | **ABSENT** | no column, no table |

### Actions

| Action | Verdict | Where |
|---|---|---|
| Order one | **PARTIAL** | `quick_quote_templates` — 4 rows, keyed by `product_line`, **not per product** |
| Send spec sheet | **ABSENT** | **0** `document_templates` matching `spec`. No template exists to send. |
| Catalog | **POPULATED** | the catalog tiers — 29 templates, 52 variants |

---

## `is_manufactured` is NULL everywhere — what the header shows

Measured: `products.is_manufactured` **0 of 27 non-null**. `product_catalog_templates`
keeps its 25 of 25, which r196 ruled deliberately — those vary per row and are decisions,
not a fill.

**The header must show NOTHING for a NULL, and the chip should be left out of the first
slice entirely.**

Rendering "Bought in" for NULL re-asserts exactly the false claim r196 existed to remove
— a `server_default=false` that made every product claim "we do not make this" without
anyone deciding. Rendering "Made here" is the same error pointing the other way. A third
state ("not recorded") is honest but, since the value is NULL for **all 27 products**,
it would render identically on every product in the pane — a chip that is permanently the
same word is decoration, not information.

So: omit. The chip earns its place the day something populates the column, and the thing
that would populate it is the onboarding answer, not a backfill.

---

## What the first slice leaves — what James will and will not see

**Shows, because it is real:**

- **Header** — name, kind, SKU. *Three of five fields.* No photo, no made-here/bought-in.
- **Price** — current price only.
- **Personalization pill** — the one pill with live data behind it.
- **Other names** — 5 confirmed aliases.
- **Catalog action.**

**Left out, with the reason:**

| Left out | Because |
|---|---|
| photo | 0 populated on all three tiers |
| made here / bought in | NULL everywhere; see above |
| Right now (all three) | `inventory_items` has 1 row |
| Specs | lining ABSENT; size 3/52; variant weight 0/52 |
| Stock (all three) | inventory 1 row, production log 0 rows, deliveries not product-joinable |
| Price history · pending · last changed | no `product_id` on `price_list_items` |
| cost · supplier · margin | cost 0/27, no supplier link, margin derived from both |
| retired names · usually ordered with · truck | do not exist |
| substitute | table exists, 0 rows |
| lead time | exists, unreachable from a product |
| Send spec sheet | no template |

**Borderline, and I would put both in:**

- **Recent orders** — 20 of 36 lines linked. Real for products that have them, empty for
  the rest, and an empty list is an honest answer to "has this been ordered lately?" in a
  way an empty *section* is not.
- **Order one** — works at `product_line` granularity. Useful, and the gap between
  "a line" and "this product" should be visible in the button's wording rather than hidden.

⚠️ **What this means for the slice as a whole: of seven spec sections, two render
substantially (Header, Price), two render one item each (Pills, Actions), and three
render nothing at all (Right now, Specs, Stock).** That is worth James seeing before the
pane is designed around seven sections, because a pane whose top three sections are absent
is a different object from the one the spec describes.

---

## Owed before building

1. **Export the Notion spec into the repo with a digest.** Everything above compares
   measurements against dispatch text.
2. **Rule on the `price_list_items` string join.** It is a product-identity defect, not a
   pane problem, and the pane is where it would first become visible to an operator.
3. **Decide whether `deliveries` should carry a product reference.** "Due out this week"
   is the only Stock line with any prospect of data, and it cannot be reached today.
