# Demo data on Sunnycrest's real books — the cleanup list

**2026-10-28.** James's Ruling 2: *"Fairview Burial Services is seed data, not a customer.
Don't type it. Report what references it (orders, entities, anything) and add it to the
demo-data cleanup list alongside SO-2026-0001…0005 and INV-2026-0009. Nothing is deleted
until James runs that cleanup."*

**Nothing in this document has been deleted.** It is an inventory, measured read-only
against production, for James to execute in one step when he chooses.

---

## 1. What "Fairview Burial Services" is

**It is the overpayment and returned-payment test counterparty.** Not an ambiguous name —
`scripts/seed_accounting_demo.py` says so directly:

```python
# line 396
# Bucket 31–60: 1 × 1500.00 → 1500.00 (the overpayment target)
# line 556
("overpayment",  "DEMO2-C004 d-52",  2, Decimal("1750.00"), Decimal("1500.00"), "check"),
# line 560
("to_return",    "DEMO2-C004 d-104", 2, Decimal("1120.00"), Decimal("1120.00"), "check"),
```

`DEMO2-C004` is Fairview. It exists so the accounting demo can exercise a customer who
pays **$1,750 against a $1,500 invoice** (overpayment) and one whose **$1,120 check gets
returned**. Its two invoices are the targets of those two scenarios.

⚠️ **This supersedes what I said on 2026-10-27**, which was that the seed "declares no type
and the name is the only signal". The *type* is still undeclared — that part stands — but
the **purpose** is declared, in the scenario tuples, and I had not read that far. The name
was never the only signal.

## 2. Everything that references Fairview

`customers.id = c7c5eb4d-a457-44df-a5b0-bd44be079d3a`, `account_number = DEMO2-C004`

| referencing | count | detail |
|---|---|---|
| `invoices.customer_id` | **2** | `INV-2026-0004` paid $1,500.00 (2026-06-19) · `INV-2026-0007` paid $1,120.00 (2026-04-28) |
| `invoice_lines` (via those invoices) | **2** | |
| `customer_payments.customer_id` | **2** | ref `DEMO2-PAY-overpayment` $1,750.00 check · ref `DEMO2-PAY-to_return` $1,120.00 check, both 2026-08-08 |
| `customer_payment_applications` (via those payments) | **2** | |
| `sales_orders.customer_id` | 0 | |
| `quotes.customer_id` | 0 | |
| `deliveries.customer_id` | 0 | |
| `company_entities` by name | **0** | ⚠️ which is why Fairview cannot be typed as the funeral home by name — see §5 |

⚠️ **Those two payments have journal entries.** The seed's own header says it *"posts
through services, never direct ORM construction"* precisely so the ledger moves — so
deleting a payment row is not the whole deletion. `customer_payments` carries
`journal_entry_id`, `discount_journal_entry_id` and `returned_at`. **The cleanup has a
general-ledger half**, and it is not in the row list below.

## 3. The named rows

| row | status | date | total | customer |
|---|---|---|---|---|
| `SO-2026-0001` | draft | 2026-10-14 | $1,550.00 | Hopkins · deceased `smith` |
| `SO-2026-0002` | cancelled | 2026-10-16 | $1,705.00 | Hopkins · deceased `demo walker` |
| `SO-2026-0003` | delivered | 2026-10-19 | $1,705.00 | Hopkins · deceased `smith` |
| `SO-2026-0004` | confirmed | 2026-10-19 | $1,705.00 | Riverside · deceased `hart` |
| `SO-2026-0005` | confirmed | 2026-10-26 | $1,405.00 | Hopkins · deceased `smith it` |
| `INV-2026-0009` | draft | 2026-10-23 | $1,705.00 | Hopkins |

These are the **capture arc's** rows — written by dispatches and by James's own walks, not
by the accounting seed. `SO-2026-0003` is `delivered` and `SO-2026-0004`/`0005` are
`confirmed`, so three of the five have moved past draft.

## 4. ⚠️ The population is much larger than the dispatch names, and that is the finding

**Every customer on Sunnycrest's production books is seed data**, and so are eight of the
nine invoices.

| | |
|---|---|
| customers | **5 of 5** seeded — `DEMO2-C001`…`C005` |
| invoices | **8 of 9** seeded — `INV-2026-0001`…`0008`; only `0009` is the arc's |
| products | **4 of 11** seeded — `DEMO2-P001`…`P004` |
| sales orders | 0 of 5 seeded — all five are the arc's |

```
DEMO2-C001  'Hopkins Funeral Home'         funeral_home  invoices=2 payments=1 orders=4
DEMO2-C002  "St. Mary's Cemetery"          cemetery      invoices=1 payments=1 orders=0
DEMO2-C003  'Riverside Memorial Chapel'    funeral_home  invoices=2 payments=2 orders=1
DEMO2-C004  'Fairview Burial Services'     (none)        invoices=2 payments=2 orders=0
DEMO2-C005  'Lakeside Funeral Directors'   funeral_home  invoices=2 payments=1 orders=0
```

⚠️ **SO "CLEAR THE DEMO DATA" CANNOT BE EXECUTED AS WRITTEN, AND THIS IS THE DECISION
JAMES NEEDS TO MAKE BEFORE RUNNING ANYTHING.** Hopkins and Riverside are seed rows. They
are also:

- the two funeral homes the guided-capture pills offer,
- the customers on all five `SO-2026-000N` orders,
- the counterparties James types in every walk (`"order for hopkins"`),
- and now typed `funeral_home` by his own Ruling 2 of this morning.

Deleting them takes the walk and the orders with them. **Three options, his call:**

1. **Promote** — keep Hopkins, Riverside and St. Mary's as real customers (re-key off the
   `DEMO2-` account numbers), delete only Fairview and Lakeside plus the seeded invoices
   and payments. Smallest blast radius; leaves the capture arc's orders standing.
2. **Clear and re-enter** — delete all five customers and everything referencing them,
   then enter Sunnycrest's actual funeral-home customers. Cleanest books; the capture
   arc loses its fixtures and the walk needs new counterparties first.
3. **Clear the accounting demo only** — delete the seeded invoices, payments and journal
   entries but keep all five customers. Fixes the books; leaves five fictional customers.

⚠️ **I am not choosing.** The scope of "all the demo data" is a business decision about
whose names belong on Sunnycrest's books.

## 5. Adjacent, pre-existing, not caused by any ruling

- **`company_entities` holds only 3 of the 5 customers** (Hopkins, Riverside, St. Mary's).
  Lakeside and Fairview are absent, so neither can be resolved as the funeral home by
  name — `resolve_funeral_home` reads `company_entities`, not `customers`.
- **`Vault Placer` is priced $0.00.** Every other Sunnycrest product matches the
  February 2026 price list exactly; this one has no price list entry and no price.
- **`products.has_personalization` is `False` on both Continentals** while the catalogue
  permits `nameplate_only` on both. Nothing in the capture or personalization path reads
  that column (grepped), so the disagreement is inert — but it is a disagreement.

## 6. ⚠️ If and when it runs: the FK hazard is documented and real

`tests/_cleanup.py::purge_companies_by_slug` is **not** a safe basis for this. Measured
2026-09-23 and recorded in CLAUDE.md: it deletes from **72** tables while **327** tables
reference a purged table without `ON DELETE CASCADE`, **77** of which hold rows — and the
purge *raises partway* on `quotes.customer_id`. A partial delete that raises mid-way
leaves the books in a state nobody designed.

So the cleanup wants a **per-row** deletion script with its own measured order, dry-run
first, rollback recorded — the same shape as `scripts/apply_rulings_2026_10_28*.py` — not
a tenant purge. **That script does not exist yet and is not written here**, because the
option in §4 decides what it deletes.
