# Piece 1 — are the four phantom fields real?

**Report only. Nothing added, nothing deleted. 2026-10-05.**

This gates Piece 3. The question is whether retiring the two hardcoded client
lists would delete duplication or delete requirements.

## Answer: one real requirement, not four

| field | verdict | what it actually is |
|---|---|---|
| `service_location` | **(a) REAL — the template is missing it** | a real `sales_orders` column with no capture equivalent |
| `service_time` | **(b) already captured, under another name** | the template's `burial_time` is written into `sales_orders.service_time` |
| `service_date` | **(b) already captured, under another name** | the template's `burial_date` is written into `sales_orders.scheduled_date` |
| `special_instructions` | **(b) dead UI — but the concept exists under two other names** | `extraction.special_requests` and `sales_orders.notes` |

**So Piece 3 must add exactly one field to the template first: `service_location`
(with its companion `service_location_other`).** Retiring the lists then removes
duplication only.

---

## The evidence, per field

### All four are permanently unrenderable

Compared the client's `CallExtraction` interface against the server model:
**12 client-declared fields, 25 server columns, and these four are the only
client fields with no server column.** `ReviewCard`'s guard is
`if (field?.value)`, so all four entries are dead branches — the API cannot
source them.

That settles *why nothing broke*. It does not settle whether they are
requirements, which is the rest of this report.

### `service_location` — REAL, and the strongest case of the four

- **Column exists**: `sales_orders.service_location` `String(20)`, with the
  in-model comment enumerating `'church', 'funeral_home', 'graveside', 'other'`,
  plus a companion `service_location_other` `String(100)` for the free-text case.
- **The model says when it is set**: *"Service details — set during order entry,
  shown on scheduling board"* (`sales_order.py:121`).
- **The scheduling Focus reads it** — `SchedulingKanbanCore.tsx`, plus
  `DeliveryCard.tsx`, `QuickEditDialog.tsx`, `TodaysServicesWidget.tsx`,
  `funeral-scheduling.tsx`, `morning-briefing-card.tsx`.
- **Capture has no equivalent.** No template field, and
  `create_draft_order_from_extraction` never sets it — an order created from a
  call has `service_location = NULL`.
- **It is a genuine domain fact, not a restatement of another field.** The
  adjacent `eta` column's comment — *"Estimated cemetery arrival (procession
  ETA); null for graveside"* — only makes sense if the service happens somewhere
  other than the grave. Where the service is held is independent of the cemetery
  and of the burial time.

⚠️ It is `nullable=True` on the model and `str | None = None` on both sales
schemas, so it is **not currently enforced** anywhere. "Real requirement" here
means *a real field of the object that capture should ask for*, not *a column
with a NOT NULL constraint*. Whether it is `required=True` in the template is a
separate decision and I am not making it.

### `service_time` and `service_date` — already captured, misnamed

`create_draft_order_from_extraction` writes:

```python
scheduled_date = extraction.burial_date      # ← the template's burial_date
service_time   = extraction.burial_time      # ← the template's burial_time
```

The codebase already treats these as the same field under two names. There is
nothing to add; adding `service_date`/`service_time` to the template would create
a **second** field for a value already captured, which is the drift this whole
exercise exists to remove.

⚠️ **But the naming mismatch is a real finding in its own right, and it bears on
the rename.** The capture template says `burial_*`; the object says
`scheduled_date` / `service_time`. One of those names is wrong, and the mapping
lives in a hand-written adapter whose own docstring warns that
*"three of the eight names differ and getting one wrong fails silently"*. That
adapter is already carrying three such mismatches; these are a fourth and fifth.

### `special_instructions` — dead UI, over a real concept with three names

- The client declares `special_instructions`.
- The extraction model stores **`special_requests`**, populated from the model's
  output (`result.get("special_requests")`).
- The order stores **`notes`**, set from `call_summary` — *not* from
  `special_requests`.

So the concept is captured, stored, and then **not carried into the order**, and
the client reads a fourth name that exists nowhere. I rule this **(b)** for
Piece 3's purposes — retiring the UI entry deletes nothing, because nothing ever
populated it. The orphaned `special_requests` → `notes` gap is a separate,
smaller finding and I am not folding it in.

---

## Adjacent finding, because it changes what the rename means

Asked where each of the 11 template fields lands on `sales_orders`:

| template field | lands as |
|---|---|
| `deceased_name` | `deceased_name` |
| `cemetery` | `cemetery_id` (resolved by name) |
| `burial_date` | `scheduled_date` |
| `burial_time` | `service_time` |
| `funeral_home` | `customer_id`, resolved via `master_company_id` |
| `vault`, `vault_size` | order **lines** — and `create_draft_order_from_extraction` creates an order **with no line items** |
| `grave_location` | **nothing writes it** |
| `legacy_print`, `nameplate_cover_emblem`, `lifes_reflections` | **nothing writes any of them** |

So **four of eleven template fields have no destination at all**, and the two
that identify the product are captured but never turned into lines. ⚠️ This does
not contradict the `funeral_order` → `sales_order` ruling — one object type with
tenant-varying fields is right — but it means the rename makes the template *name*
the object before the template *reaches* it. Worth knowing when Piece 3 lands, and
it is the real content of the "capture ends in the finished object" canon entry
that nothing yet satisfies.

---

## Premise note

The dispatch asked whether *"the sales order pane prototype"* shows these fields.
**No such artifact exists** — nothing matching `sales.?order.?pane`
(case-insensitive) in any `.md`, `.ts` or `.tsx` outside `node_modules`. The
evidence above substitutes the scheduling Focus core and the order model, which
are the surfaces that do exist.

## Where I looked

`frontend/src/contexts/call-context.tsx` (the client type) ·
`backend/app/models/ringcentral_call_extraction.py` (25 columns) ·
`backend/app/models/sales_order.py` (58 columns) ·
`backend/app/schemas/sales.py` ·
`backend/app/services/call_extraction_service.py`
(`_captured_from_result`, `create_draft_order_from_extraction`) ·
`frontend/src/components/dispatch/scheduling-focus/SchedulingKanbanCore.tsx` ·
plus a repo-wide reader enumeration for each of the four names.

Controls reported at each step: 12 client fields vs 25 server columns (both
non-empty, or the comparison is vacuous); 58 `sales_orders` columns; 11 template
fields.
