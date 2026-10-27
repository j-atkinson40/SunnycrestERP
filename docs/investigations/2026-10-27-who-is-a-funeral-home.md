# "Which funeral home?" — what the data can and cannot tell

James, 2026-10-27: *"St. Mary's Cemetery and 'Fairview Burial Services' appear under
'Which funeral home?' That's the customer-type fix still waiting on your rulings block.
Paste that block if you haven't. 'Fairview Burial Services' isn't a name I recognize; it
may be a test record."*

⚠️ **NO `customer_type` RULING HAS REACHED ME.** I raised the gap at the end of the
slice-1 report and nothing has come back on it, so there was no block to apply. This
records what was measured, what was fixed without a ruling, and exactly what the ruling
would change.

## What "Fairview Burial Services" is: seed data

Measured on production, read-only. All five of Sunnycrest's customers:

```
name                        account      type  orders(all/live)  invoices  created
Hopkins Funeral Home        DEMO2-C001   NULL  4 / 3             2         2026-08-10 15:00:48.565257
St. Mary's Cemetery         DEMO2-C002   NULL  0 / 0             1         2026-08-10 15:00:48.565280
Riverside Memorial Chapel   DEMO2-C003   NULL  1 / 1             2         2026-08-10 15:00:48.565289
Fairview Burial Services    DEMO2-C004   NULL  0 / 0             2         2026-08-10 15:00:48.565297
Lakeside Funeral Directors  DEMO2-C005   NULL  0 / 0             2         2026-08-10 15:00:48.565304
```

Every one shares the `DEMO2-C00N` account prefix, was created inside **one transaction**
(the timestamps differ by microseconds) and carries the same `created_by`. The source is
`backend/scripts/seed_accounting_demo.py:293`:

```python
_CUSTOMERS = [
    ("Hopkins Funeral Home", "DEMO2-C001", True),
    ("St. Mary's Cemetery", "DEMO2-C002", True),
    ("Riverside Memorial Chapel", "DEMO2-C003", False),
    ("Fairview Burial Services", "DEMO2-C004", False),
    ("Lakeside Funeral Directors", "DEMO2-C005", False),
]
```

**So: a seed row, not a real Sunnycrest customer and not a test leftover.** Deliberate
demo substrate — and that script's own docstring says *"Its first execution will be
against production"*, so it is meant to be there. ⚠️ **AND SO ARE THE OTHER FOUR,
INCLUDING HOPKINS.** The orders against Hopkins are real (they come from the capture
walks); the customer ROW is seeded.

## ⚠️ Nothing in the data distinguishes a funeral home from a cemetery

`customers.customer_type` is **NULL on all five**. There is no other candidate:
`company_entities` rows exist with no address and every flag False, and `contacts` holds
zero rows for the tenant (both measured for the Customer Pane on 2026-10-24).

So the question "is this customer a funeral home?" is **not answerable from the data
today**, by any column.

## What was fixed without a ruling: offer only customers who have ORDERED

The pills now rank `funeral_home` from order history alone and no longer pad the list
from every active customer. That pad was mine and the dispatch never asked for it —
clause 3 of the slice-1 dispatch says *"this customer's usual first… then the tenant's
most ordered"*, and a customer with zero orders is not among the tenant's most ordered.

Result on production: **Hopkins (3 live orders) and Riverside (1)** — the two real
funeral homes. St. Mary's, Fairview and Lakeside each have none and drop out.

⚠️ **THIS IS NOT THE `customer_type` FIX AND MUST NOT BE MISTAKEN FOR IT.** Order
history is a different discriminator that happens to give the right answer on this
tenant. It is right for a reason unrelated to what a customer IS.

⚠️ **AND IT HAS A STATED COST.** A genuinely new funeral home has no orders either, so
it is not offered until its first order is typed. That is survivable — a name typed in
full always works, and pills are an accelerator rather than the only route — and it is
exactly the case a ruling would fix. `test_a_customer_with_no_orders_is_not_offered_even_if_it_is_the_only_one`
pins the trade so it is visible rather than discovered.

⚠️ **I DID NOT REACH FOR A NAME RULE** — excluding anything containing "Cemetery" —
because that is the shape James ruled out for the "Smith It" defect on 2026-10-26: *"fix
it in the name rules (not a one-word stoplist)"*. A customer called "Fairview Burial
Services" would survive such a rule anyway, and a funeral home called "Cemetery Road
Funeral Home" would not.

## What a ruling would decide

1. **Does `customer_type` get populated, and by whom?** Five rows on Sunnycrest. It is a
   production write on seeded data, so it is James's call rather than a backfill I
   should run.
2. **Is a cemetery a legitimate answer to this question?** A cemetery buying a vault is a
   real transaction in this business. It may be that the FIELD is misnamed — it stores
   the customer, and the schema calls it `funeral_home` — rather than the data being
   wrong. If so the question's wording is what changes, not the pill list.
3. **Should a never-ordered customer be offered at all?** Today: no. A new funeral home's
   first order is typed in full, which works, and the pills fill in afterwards.
