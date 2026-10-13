# What Approve would write — order capture through approval

**Date:** 2026-10-13
**Dispatch:** order capture: finish it (part A build, part B investigate)
**Status:** read-only investigation. Nothing in B was built.

Every claim below carries `file:line` or a named production query. Production reads
went through a connection-level read-only guard
(`default_transaction_read_only=on`); credentials were never printed.

---

## 0. Two premises in the dispatch are wrong, and both change the work

### 0.1 James's St. Mary's miss was not a matching failure — his tenant has no cemeteries

The dispatch says "while 'St. Mary's Cemetery' exists on the tenant". Measured on
production:

| tenant | `company_entities` | `cemeteries` |
|---|---|---|
| sunnycrest | 3 | **0** |
| hopkins-fh | 0 | 0 |
| st-marys | 0 | 0 |
| testco | 20 | 3 |

`sunnycrest`'s three `company_entities` rows are `Hopkins Funeral Home`,
`Riverside Memorial Chapel`, and **`St. Mary's Cemetery`**. So the cemetery exists
as a **company entity** — the table `resolve_funeral_home` reads
(`app/services/party_resolver.py:238`) — and **not** as a `cemeteries` row, the only
table `resolve_cemetery` reads (`app/services/party_resolver.py:255`).

The capture session row proves it was that tenant and that sentence:

    tenant='sunnycrest'  status='capturing'  created=2026-10-13 15:23:06+00
    full_text="order for hopkins monticello going to St. Mary's"

15:23 UTC = 11:23 ET, one minute before the walk note. There was nothing for any
pattern to match, so no widening of the matcher would have helped.

**This is a decision, not a fix** — see Q1 in §6.

### 0.2 The "9 fields with no home" list is wrong in both directions

The dispatch names nine: personalization, legacy_series, legacy_print_name,
lifes_reflections_symbol, service_date, cemetery_city, nameplate_date_format,
date_of_birth, date_of_death.

Measured against the real schema, **two captured fields it does not list also have
no home** — `burial_date` and `grave_location` — and **two it does list already
have one**: `personalization` (→ `order_personalization_tasks`, FK'd to
`sales_orders.id`) and `service_date` (→ `sales_orders.scheduled_date`, whose own
comment reads "The service/delivery date for this order",
`app/models/sales_order.py:88-89`). Full mapping in §4.

---

## 1. B1 — the prototype's summary stage and Approve

File: `docs/prototypes/2026-10-01-opas-overlay.html`. The stage is `review`
(`:389`). Quoting the behaviours:

**Entering review** (`:541-542`). Typing `that's everything|done|review( it)?|looks
good|ready` checks required fields first:

> `const req=SCHEMAS[cur.type].fields.filter(f=>f[2]&&cur.values[f[0]]==null);`
> `if(req.length){cur.flagged=true;…out.push({t:'Still needed: '+req.map(f=>f[1].toLowerCase()).join(', '),cls:'miss'});return}`
> `cur.stage='review';…out.push({t:'Ready for your approval'});`

So **review is gated on completeness** — you cannot reach it with a required field
missing; the bar answers "Still needed: …" instead.

**What review shows** (`:389-404`):

1. Header (`:402`): `Review`, then `<b>N</b> captured`, then a pill reading
   **`0 missing`** — hardcoded, because review is unreachable while anything is
   missing.
2. Title block (`:390`): the decedent's name, subtitled
   `Sales order · <funeral home name>`.
3. A field grid of **seven** rows via `sf(k,label)` (`:391`): Funeral home (with
   `v.customer.person` as a second line), Vault, Personalization, Delivery,
   Cemetery, Cemetery equipment. **Each row carries its own `edit` button**
   (`data-act="editfield"`).
4. Line items (`:179`, built at `:393-395`): the vault at `VAULTS[v.vault]`
   (`:270`), then one line per personalization extra at `EXTRAS[e]` (`:271`), then
   a **Total**.
5. A **Notes textarea**, order-only (`:401`), placeholder
   *"Anything dispatch or the office should know"*.
6. Actions (`:404`): a primary button labelled by `sc.verb` — for orders,
   **`Approve and create sales order`** (`:289`) — and a link
   **`Back to capture`**.

**Inline field editing** (`:489`): the value becomes `contentEditable`; on blur it
is written to `w.edits[k]`. ⚠️ `w.edits` is a **separate store from `w.values`** and
is read only by the review renderer's `val()` (`:390`) — the prototype never merges
edits back, so what Approve consumes is unspecified there. That is a real gap the
prototype leaves to us, not a behaviour to copy.

**What Approve does** (`:493`):

> `if(a==='approve'){ w.stage='done';`
> `if(w.type==='order'){w.result='Created SO-2026-0425 for '+w.values.customer.name;w.ref='SO-2026-0425'}`
> `… paint(w);show([{t:w.result}]);input.focus(); }`

It sets stage `done`, fabricates a **hardcoded** order number `SO-2026-0425`, and
echoes one line in the bar. The prototype writes nothing and specifies no status, no
invoice, and no delivery. **Also reachable by typing** `approve|create it|send
it|yes|go` (`:543`) and by **⌘Enter** while in review (`:90049` region, keydown
handler).

**The prototype's field set is 7; ours is 20.** Its `order` schema (`:289-290`) is
`customer, decedent, vault, extras, date, cemetery, equip`. It has no burial date,
service time, ETA, grave location, service location, dates of birth/death, nameplate
date format, legacy series/print, or symbol. So the prototype's grid cannot be
copied row-for-row.

---

## 2. B2 — what exists today for creating a sales order

**Model** `app/models/sales_order.py`.
`SalesOrder` (`:32`), table `sales_orders`, 49 columns.
`SalesOrderLine` (`:181`), table `sales_order_lines`, 12 columns.
⚠️ Audit timestamps are `created_at` / `modified_at` — **not** `updated_at`
(`:152-160`, and CLAUDE.md §5 names `sales_orders` explicitly).

**Statuses.** Declared only as a comment on the column (`:50-52`):
`draft, confirmed, processing, delivered, completed, cancelled` — a `String(20)`
with `default="draft"` and **no CHECK constraint and no enum**. Canonical cancel
spelling is `"cancelled"`, double-L, with `CANCEL_SPELLINGS` accepting `"canceled"`
on the way in (`:26-29`). Other strings appear in queries that nothing declares:
`"shipped"` (`draft_invoice_service.py:227`).

**Endpoints** (`app/api/routes/sales.py`):

| endpoint | line | permission |
|---|---|---|
| `POST /api/v1/sales/orders` | `:427` | `ar.create_order` |
| `GET /api/v1/sales/orders` | `:410` | `ar.view` |
| `GET /api/v1/sales/orders/{id}` | `:440` | `ar.view` |
| `PATCH /api/v1/sales/orders/{id}` | `:451` | `ar.update_order` |
| `POST /api/v1/sales/orders/{id}/invoice` | `:465` | `ar.create_invoice` |

All sit behind `require_module("sales")`.

**`create_sales_order`** (`app/services/sales_service.py:537`), in order:

1. `_get_customer_or_404` — **requires a `customers` row** (`:541`).
2. `_compute_totals`, `_next_number(…, "SO")` (`:543-544`).
3. Inserts the order with **`status="draft"` hardcoded** (`:551`).
4. Inserts each line (`:567-578`).
5. `recalculate_order_line_prices` — try/except, warn-only (`:582-586`).
6. `apply_placer_to_order_lines` + `set_order_confirmation_method` — try/except
   (`:589-599`). ⚠️ **The first of these ADDS LINES** the caller did not ask for
   (funeral-home placer preferences).
7. `_check_credit_on_order` — soft warning, does not block (`:602`).
8. `_check_inventory_on_order` — soft flag, does not block (`:605`).
9. `audit_service.log_action(… "created", "sales_order" …)` (`:607`).
10. `db.commit()`.

**Nothing in creation invoices, posts to a ledger, emails, or creates a delivery.**

**`update_sales_order`** (`:620`): refuses `completed`/`cancelled` (`:623-627`);
writes only `status, required_date, shipped_date, notes, deceased_name,
service_location, service_location_other, service_time, eta` (`:635-640`); then —

> `if new_status == "confirmed": order_integration_service.on_order_confirmed(db, order)` (`:663-665`)

---

## 3. B3 — side effects, and which ones an Approve would set off

Each row is "what triggers it" → "would an Approve from capture set it off?"

### 3.1 Delivery auto-creation
`order_integration_service.on_order_confirmed` (`:23`). Trigger: a status
transition **to `confirmed`** via `update_sales_order` (`sales_service.py:665`) or
quote acceptance (`quote_service.py:474`). Gated on
`settings.auto_create_delivery_from_order` (`:32-33`); inserts a `Delivery` with
`status="pending"` and **commits** (`:59-73`).

**Production:** `auto_create_delivery_from_order` is **False on sunnycrest,
hopkins-fh and st-marys**; **True on testco**.
→ **Would fire on testco if Approve sets `confirmed`. Would not on sunnycrest.**

### 3.2 The 18:00 end-of-day invoice batch — the one that matters
`scheduler.py:708-712` registers `job_draft_invoice_generator` on
`CronTrigger(hour=18, minute=0)`, per tenant (`:356-358`) →
`draft_invoice_service.generate_draft_invoices` (`:181`).

Gate: `invoice_generation_mode != "end_of_day"` returns immediately (`:191-195`).
Selection (`:217-241`):

- `status IN ("confirmed","processing","shipped","delivered","completed")` — **`draft` is excluded**
- `scheduled_date <= today` **OR** (`scheduled_date IS NULL` AND `required_date <= today`)
- `order_type == "funeral" OR order_type IS NULL` — **NULL is in the net**
- not already invoiced

Then, with `require_driver_status_updates = False`, `_generate_auto_confirm_mode`
(`:291`) **mutates the order**:

> `order.status = "delivered"; order.delivered_at = now; order.delivery_auto_confirmed = True` (`:306-309`)

and creates an invoice via `create_invoice_from_order`, stamped
`status="draft"`, `requires_review=True`, `review_due_date=tomorrow`,
`auto_generated=True`, `generation_reason="end_of_day_batch"` (`:316-330`), plus
`log_activity` / `create_alert` agent writes (`:346`, `:398`).

**Production settings, measured:**

| tenant | invoice_generation_mode | require_driver | auto_create_delivery |
|---|---|---|---|
| sunnycrest | **end_of_day** | False | False |
| hopkins-fh | end_of_day | False | False |
| st-marys | end_of_day | False | False |
| testco | end_of_day | **False** | True |

**This is live, not theoretical.** On production: 12 invoices carry
`generation_reason='end_of_day_batch'` (all `draft`, all on testco) and **5 testco
orders have `delivery_auto_confirmed = true`** — the batch has already rewritten
real orders' status to `delivered`.

→ **An Approve that sets `confirmed` with a `scheduled_date` of today or earlier
would, that same evening, have the order marked `delivered` and a draft invoice
created. No human step is involved.** This is the single most important finding in
B3.

### 3.3 AR posting and the ledger
`sales_service.post_invoice_to_ar` (`:672`) is the only place
`customer.current_balance` moves, and it calls
`ar_invoice_posting.post_invoice` (`:719-721`), which writes a journal entry with
`entry_type="invoice"` (`ar_invoice_posting.py:98`, `:257`).

Trigger: the **draft→issued** transition only — a status PATCH out of draft, the
review-queue approval, emailing a draft (`sales.py:1122-1125`), or born-real finance
charges. `create_invoice_from_order` explicitly does **not** post: *"NO AR POST
HERE (audit #2 D-2): the invoice is a DRAFT"*.

**The dispatch's claim is confirmed.** On production all **15** `journal_entries`
rows are `entry_type='reconciliation'`, status `draft`. **Zero** `entry_type='invoice'`
rows; zero entries whose description matches `Invoice %`. `post_invoice` has never
run on production.

→ **Would not fire from Approve**, even via the batch — the batch leaves the invoice
`draft`.

### 3.4 Email
`draft_invoice_service._try_send_invoice_email` (`:38`) generates a PDF and calls
`email_service.send_invoice_email` (`:72`). Called from exactly two places:
`approve_invoice` (`:700`) and `approve_all_no_exceptions` (`:755`) — both
**human actions on the invoice review queue**. The 18:00 batch does not call it.
A separate manual path exists at `sales.py:1122`.

→ **Would not fire from Approve.** An email requires a person to approve the
invoice afterwards.

### 3.5 Invoice on delivery completion
`on_delivery_completed` (`order_integration_service.py:85`) auto-invoices only when
mode is `"immediate"` (`:104-105`); `end_of_day` and `manual` return. Callers:
`deliveries.py:657`, `delivery_notification_service.py:164`.

→ **Would not fire** — every production tenant is `end_of_day`, and no delivery
exists for a capture order anyway.

### 3.6 Agent writes
`agent_anomalies` holds **2,440** rows on production; the batch writes alerts and
activity (`draft_invoice_service.py:346`, `:398`). Anomalies are also how
`post_invoice` reports an unconfigured account rather than raising
(`sales_service.py:697-699`).

→ **Only reached via the batch**, i.e. only if Approve sets a batch-eligible status.

### 3.7 Pricing and auto-added lines
`recalculate_order_line_prices` (`order_pricing_service.py:104`) and
`apply_placer_to_order_lines` both run **inside `create_sales_order`** and both are
wrapped in try/except that only logs (`sales_service.py:582`, `:589`).

→ **Would fire on any Approve that calls `create_sales_order`.** Lines may be added
and prices rewritten, and a failure is a log line, not an error.

---

## 4. B4 — where each of the 20 captured fields would land

Authoritative field list: `PLATFORM_DEFAULT_FIELDS`,
`app/services/capture/schema.py:459`.

| # | captured field | lands where | status |
|---|---|---|---|
| 1 | `vault` | a `sales_order_lines` row | needs a product id — §5 |
| 2 | `funeral_home` | `sales_orders.customer_id` | name-matches an existing `customers` row on sunnycrest — Q2 |
| 3 | `deceased_name` | `sales_orders.deceased_name` | exists (`:131`) |
| 4 | `cemetery` | `sales_orders.cemetery_id` | exists (`:83`) |
| 5 | `cemetery_city` | — | derivable from `cemetery_id`; no column needed |
| 6 | `burial_date` | — | **NO HOME** (not in the dispatch's list) |
| 7 | `service_date` | `sales_orders.scheduled_date` | exists (`:88`), comment says exactly this |
| 8 | `service_time` | `sales_orders.service_time` | exists (`:127`) |
| 9 | `grave_location` | — | **NO HOME** (not in the dispatch's list) |
| 10 | `service_location` | `sales_orders.service_location` | exists (`:123`) |
| 11 | `service_location_other` | `sales_orders.service_location_other` | exists (`:125`) |
| 12 | `eta` | `sales_orders.eta` | exists (`:128`) |
| 13 | `date_of_birth` | — | **NO HOME** |
| 14 | `date_of_death` | — | **NO HOME** |
| 15 | `nameplate_date_format` | `order_personalization_tasks.inscription_dates`? | **no format column** — see below |
| 16 | `legacy_series` | `order_personalization_tasks.is_custom_legacy` | exists (`:34`) — boolean, two options map |
| 17 | `legacy_print_name` | `order_personalization_tasks.print_name` | exists (`:31`) |
| 18 | `lifes_reflections_symbol` | `order_personalization_tasks.symbol` | exists (`:33`) |
| 19 | `cemetery_equipment` | a `sales_order_lines` row | no tenant product — §5 |
| 20 | `personalization` | `order_personalization_tasks.task_type` | exists (`:20`) |

### The personalization home is `order_personalization_tasks`, not `case_merchandise`

`app/models/order_personalization_task.py:12`, table
`order_personalization_tasks`, with **`order_id` → FK `sales_orders.id`**
(`:17`) and `order_line_id` (`:19`, String, no FK). Its `task_type` vocabulary is
`physical_nameplate, physical_emblem, vinyl, legacy_print` (`:20-26`) — which is the
same substrate vocabulary the capture's `personalization` field uses. It already
carries `print_name`, `symbol`, `is_custom_legacy`, `inscription_name`,
`inscription_dates`, `inscription_additional`, plus proof fields
(`proof_url`, `tif_url`, `default_layout`, `approved_layout`).

⚠️ **`case_merchandise`, which the dispatch names, is not reachable from a sales
order.** It is keyed by `case_id` and belongs to the funeral-case model
(`app/models/funeral_case.py`); there is no `sales_order_id` on it and no
`case_id` on `sales_orders`. Its `vault_personalization` column is for the
funeral-home vertical's case, a different object. `personalization_records` and
`order_personalization_task` (singular) **do not exist as tables**.

⚠️ **`sales_order_lines.personalization_data` (JSONB) also exists** (`:216`) and is
a second candidate for per-line personalization. Two homes for one fact is the
condition CLAUDE.md §5 warns about — see Q3.

### What the Personalization Focus reads
`order_personalization_tasks` is the table the personalization task flow is built
on (`task_type`, `status`, `completed_by`, `proof_url`, `approved_layout`). Writing
capture's personalization there is the mapping that matches how the Focus will read
it; writing it to `sales_order_lines.personalization_data` would not be visible to
that flow.

### `nameplate_date_format` has the closest precedent elsewhere
`case_merchandise` has `monument_dates_format` — but as above, that table is not
reachable from a sales order. `order_personalization_tasks` has
`inscription_dates` (the rendered text) and **no format column**. So the format is
genuinely homeless; it is also exactly the kind of field that belongs with the task
rather than the order.

### Summary of what has no home
**Six fields**, not nine: `burial_date`, `grave_location`, `date_of_birth`,
`date_of_death`, `nameplate_date_format`, and `cemetery_city` (needed only if the
typed town must be kept when it differs from the record).

---

## 5. B5 — line items and price

**How a line is built.** `SalesOrderLine` needs `description` (NOT NULL) and takes
`product_id` (nullable FK to `products`), `quantity`, `unit_price`, `line_total`
(`app/models/sales_order.py:181-216`). A line **can** be written with
`product_id=NULL` and a description — nothing forbids it.

**Where a price would come from.** `order_pricing_service` returns
`product.price`, or `product.price_without_our_product` for the standalone case
(`:51-63`). So pricing needs a **tenant `products` row**.

**The variant link is empty, as the dispatch says — and it is empty everywhere.**
Measured on production: `products` with a non-null `variant_template_id` —
**0 of 4 on sunnycrest, 0 of 4 on st-marys, 0 of 25 on testco**. The capture
resolves a vault through the platform catalog
(`product_name_resolver.build_index`, 207 indexed phrases) and returns a
`variant_template_id` and a `display_name`. There is **no join** from that to a
tenant product.

**But a name match does reach a priced product on sunnycrest.** Its four products:

| product | price | sku |
|---|---|---|
| Monticello Burial Vault | $1,250.00 | DEMO2-P001 |
| Continental Burial Vault | $1,850.00 | DEMO2-P002 |
| Urn Vault - Standard | $425.00 | DEMO2-P003 |
| Graveside Setup Service | $300.00 | DEMO2-P004 |

The capture's `display_name` for the two vaults James demos is exactly
`"Monticello Burial Vault"` and `"Continental Burial Vault"` — **string-identical**
to the product names. So a name match works for those two today.

It does **not** work for anything else: the capture's `"Monticello Urn Vault"` has
no sunnycrest product (`"Urn Vault - Standard"` is a different string), and
**none of the seven equipment packages** — `full_equipment`,
`lowering_device_and_grass`, `tent_only`, `lowering_device_only`, `vault_placer`,
`extra_chairs`, `none` (`schema.py:389`) — corresponds to any tenant product name.

**So, stated exactly:** Approve can put a **vault line** on the order with a real
`product_id` and a real `unit_price` **when the captured vault's display name
matches a tenant product name** — true for Monticello and Continental burial vaults
on sunnycrest, false otherwise. For **cemetery equipment it cannot**: there is no
product, so the only options are a description-only line at `unit_price = 0.00`, or
no line at all. See Q4.

⚠️ And whatever Approve writes, `create_sales_order` will then run
`recalculate_order_line_prices` and `apply_placer_to_order_lines` over it (§3.7), so
the lines Approve writes are not necessarily the lines that end up stored.

---

## 6. B6 — the smallest Approve, and the decisions that are James's

### The proposal

**What it writes.** One `sales_orders` row plus its lines and personalization tasks,
through a new capture-owned service — **not** through
`sales_service.create_sales_order`, because that path hardcodes `status="draft"`
(fine) but also runs placer auto-add and price recalc over our lines (§3.7) and
requires a `customers` row (Q2).

- `status = "draft"` — **the safe terminal state.** `draft` is excluded from the
  18:00 batch's status filter (`draft_invoice_service.py:226-228`) and
  `create_invoice_from_order` refuses a draft outright: *"Order {number} is still a
  draft — confirm it before invoicing"* (`sales_service.py:739-743`). Nothing
  automatic can touch a draft.
- `order_type = "funeral"` — explicit rather than NULL. NULL is inside the batch's
  net (`:240`), so leaving it NULL means the order's safety rests only on `status`.
  Two independent reasons to be skipped is better than one.
- **`scheduled_date` left NULL** for now, or set only if James wants it: with
  `status` draft it is inert, but it is the other half of the batch's selection and
  the field most likely to be set by a later edit.
- Columns that already exist: `deceased_name`, `cemetery_id`, `service_time`,
  `service_location`, `service_location_other`, `eta`, `notes`.
- Lines: one vault line (product-matched where possible, §5); equipment per Q4.
- `order_personalization_tasks` rows for the personalization answers, carrying
  `print_name`, `symbol`, `is_custom_legacy`.
- `audit_service.log_action(… "created", "sales_order" …)`, matching the existing
  path.

**What it must NOT trigger, and the exact reason:**

| must not | why it cannot |
|---|---|
| the 18:00 batch marking the order `delivered` + drafting an invoice | `status="draft"` is outside its filter; `order_type="funeral"` is a second guard |
| `on_order_confirmed` → delivery row | only fires on a transition **to `confirmed`**; and `auto_create_delivery_from_order` is False on sunnycrest |
| `post_invoice_to_ar` → AR balance + journal entry | only on draft→issued of an **invoice**; no invoice is created |
| any email | only from `approve_invoice` / `approve_all_no_exceptions`, both human actions on an invoice |
| placer auto-add lines / price recalc rewriting our lines | by not routing through `create_sales_order` |

**The migration it needs.** One, additive, all columns nullable — the six homeless
fields. Candidate shape (pending Q3/Q5):

- `sales_orders.burial_date` (Date)
- `sales_orders.grave_location` (String)
- `sales_orders.date_of_birth` (Date), `sales_orders.date_of_death` (Date)
- `order_personalization_tasks.nameplate_date_format` (String(10))
- `sales_orders.cemetery_city_typed` (String) — only if Q5 says keep it

Every one nullable with **no server default and no model-side `default=`**: these
columns would be added to populated tables (`sales_orders` holds 37 rows on
production), and a non-null value would assert something about rows nobody measured
(CLAUDE.md §5).

⚠️ **Part A was explicitly "no migration expected; stop if one is needed" and it
needed none.** This one is part B's proposal, for James to approve before it is
written.

**What James will see afterwards.** The order appears at **`/ar/orders`**
(`frontend/src/App.tsx:1046`, `SalesOrdersPage`) and opens at `/ar/orders/:id`
(`:1050`). Drafts are listed — the status filter offers "Draft"
(`src/pages/sales-orders.tsx:191`) and nothing excludes them by default. It will be
the **first sales order sunnycrest has ever had** (production: 0 rows).

### The decisions that are James's

**Q1. St. Mary's is a company entity, not a cemetery. Which do you want?**

`company_entities` carries `is_customer` / `is_vendor` / `is_cemetery` flags, so
"read the entities and filter to cemeteries" looked like a no-data-write option.
Measured, it is not: **all three sunnycrest entities have `is_cemetery = False`** —
including `St. Mary's Cemetery` — and so are `is_customer` and `is_vendor`. The demo
rows were created with no flags set at all. On testco, by contrast, 4 entities are
flagged `is_cemetery` against 3 `cemeteries` rows (`Oakwood Memorial` is flagged but
has no cemetery row), so that tenant holds both representations and they do not quite
agree.

- (a) Add `St. Mary's Cemetery` as a `cemeteries` row on sunnycrest. One row, a
  production data write, **no code change** — the capture resolves it immediately.
- (b) Set `is_cemetery = True` on the entity **and** teach `resolve_cemetery` to read
  flagged entities. A data write *and* a code change, and it inherits testco's
  disagreement between the two representations.
- (c) Leave it; demo the cemetery on testco.

**Recommendation: (a).** It is the smallest change, it needs no new code, and it
makes "the tenant has a cemetery" mean the thing the resolver already checks. ⚠️ Note
that (b) was my first instinct and the flag measurement killed it — without checking,
"filter on `is_cemetery`" reads like the obviously correct answer.

**Q2. The funeral home resolves against `company_entities`, but a sales order needs
a `customers` row — and the bridge is a name match.** `customer_id` is NOT NULL
(`app/models/sales_order.py:42`) and `create_sales_order` 404s without the row
(`sales_service.py:541`).

Measured: **sunnycrest has 5 `customers` rows**, and they include
`Hopkins Funeral Home`, `Riverside Memorial Chapel` and `St. Mary's Cemetery` —
string-identical to the entity names the capture resolves. So **the row James needs
already exists**, and a name match from the resolved funeral home to `customers`
works today for Hopkins. `customers.master_company_id` is NULL on all five, so there
is no FK path; the name is the only join.

This is no longer blocking. What remains is the fallback: when the resolved funeral
home has **no** matching customer — (a) Approve creates one, (b) Approve refuses and
names what is missing, (c) onboarding links the tables properly. **Recommendation:
(b)** for the smallest Approve — creating a customer as a side effect of approving an
order is a second write nobody asked for, and the office should know the record is
missing.

**Q3. Personalization: `order_personalization_tasks` or
`sales_order_lines.personalization_data`?** Both exist. The task table is FK'd to
the order and is what the personalization flow reads; the JSONB column is per-line
and nothing reads it that I found. **Recommendation: the task table**, and leave the
JSONB column alone rather than writing both.

**Q4. Cemetery equipment has no tenant product and no price.** (a) A
description-only line at $0.00, visible on the order and obviously unpriced. (b) No
line; keep it only as a captured field until products exist. (c) Create the seven
equipment products first. **Recommendation: (b)** for the smallest Approve — a $0.00
line on a real sales order is a number that can be mistaken for a price.

**Q5. Keep the typed cemetery town when it differs from the record?** The capture
captures `cemetery_city` and raises a conflict pick when it disagrees. Once
`cemetery_id` is set, the record's city is authoritative. Keep the typed value as
evidence, or drop it?

**Q6. Should Approve be reversible?** `update_sales_order` refuses to modify
`completed`/`cancelled` orders but a `draft` is freely editable, so "unapprove"
could mean reopening the capture session, or cancelling the order, or nothing.

---

## 7. What I did not do

- Built nothing in part B; no migration was written.
- Did not trace the `require_driver_status_updates = True` branch
  (`draft_invoice_service.py:423`) in detail, because no production tenant has it
  set.
- Did not read the `Delivery` model's own downstream hooks; no delivery would be
  created by the proposed Approve.
