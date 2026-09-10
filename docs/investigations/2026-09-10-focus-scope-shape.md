# What must a Focus scope round-trip carry?

**Date:** 2026-09-10
**Status:** SHAPE DERIVED FROM CONSUMERS. §2 not built.

The dispatch asked for what existing consumers need rather than a design for
the scheduling case. Enumerated from the five registered fragments' real
`scope` dicts, plus the two other declared consumers.

---

## Every scope shape that exists today

| fragment | scope |
|---|---|
| `anomaly_watchlist` | `anomaly_ids: [...]`, `severity_filter: str\|None`, `include_resolved: bool` |
| `compliance_flags` | `notification_ids: [...]`, `category: str`, `severity_in: [str]` |
| `tasks_due_today` | `task_detail_ids: [...]`, `due_date: "2026-09-10"`, `assignee_user_id: uuid` |
| `collections_outstanding` | `customer_id: uuid`, `queue_id: str` |
| `expense_posting_map` | `platform_category: str` |

Value types present: **id list** (3 of 5), single entity id (2), date (1), enum
string (4), string list (1), boolean (1), explicit null (1).

Plus the two consumers not yet built: the **work log** click-through
("4 sales orders entered" → those four) and the **standing-line Focus-on-click**
ruling.

## The id list is the most common shape and the worst URL

Measured on real emitted instances: an `anomaly_ids` list of **5** costs **355
URL-encoded characters**. UUIDs inflate to roughly 60 chars each once JSON
quoting and percent-encoding are applied.

So roughly **30 ids reaches the practical URL ceiling**, and a user with 40
tasks due today would produce an unshareable link. ⚠️ Those are today's counts
on seeded data, not a bound on the shape.

## But every id list is the EXPANSION of a predicate that is already in the scope

This is the finding, and it changes the scheme rather than sizing it.

- `tasks_due_today` — `task_detail_ids` is exactly what `due_date` +
  `assignee_user_id` select.
- `anomaly_watchlist` — `anomaly_ids` is what `severity_filter` +
  `include_resolved` select.
- `compliance_flags` — `notification_ids` is what `category` + `severity_in`
  select.
- the work log — "those four sales orders" is what
  `(user, day, action=created, entity_type=sales_order)` selects.

**In every case the list is a materialisation of a predicate the scope already
carries.** So the URL can carry the predicate and drop the expansion: shorter,
and it re-derives.

### And that matches a rule the arc already made

DECISIONS 2026-09-04 on settled notes: *anything event-sourced re-derives
as-of; anything that cannot re-derive gets a payload frozen and visibly marked
as a record.* The same distinction applies here:

- **A LIVE entrance carries the predicate.** Re-deriving is correct — the
  scheduling Focus scoped to tomorrow should show tomorrow as it is when opened.
- **A SETTLED entrance carries the expansion.** A record of what happened must
  not re-derive, for the same reason a settled note's spans are frozen: a link
  that quietly shows today's data under yesterday's sentence.

## The consequence to rule on before building

Carrying only the predicate means the fragment contract's `scope` is doing two
jobs today — predicate AND expansion — and only one of them belongs in a URL.
Either:

- **(a)** the URL carries the predicate keys and the core re-derives, and the id
  lists in `scope` stay as a non-navigational payload; or
- **(b)** `scope` splits explicitly into a predicate half and an expansion half,
  so which one an entrance uses is declared rather than inferred by key name.

(b) is the removal-shaped option — it makes "which of these is the URL's job"
unexpressible-by-accident — and it is a change to the fragment contract, which
is why it is reported rather than chosen.

## Not established here

Whether any existing consumer needs a **free query** shape. None of the five
fragments carries one; the dispatch named it as a possible shape and the
enumeration did not find one. Absence over five declarations is not absence over
the space of future fragments.
