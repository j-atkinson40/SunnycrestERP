# What it would take for "change the vault to continental" to work

Report only, by ruling: *"Report only, don't build: what it would take for 'change the
vault to continental' on a confirmed order to work… James will rule on scope."*
(James, 2026-10-26, item 3.)

Measured against HEAD, not recalled. Every claim below names the file it came from.

## The short version

Four of the five pieces exist. The missing one is the **route from Opas's words to the
write**, and the expensive one is a **pricing ruling** that is a business decision rather
than a derivation.

| Piece | State | Where |
|---|---|---|
| A write path that edits a confirmed order | **EXISTS** | `sales_service.update_sales_order` |
| A transition gate so an edit cannot skip a status | **EXISTS** | `sales_order_transitions` |
| A period lock so a closed month cannot be edited | **EXISTS** | `PeriodLockService` |
| A history entry | **EXISTS, BUT BLIND** — see below | `audit_service.log_action` |
| Re-pricing a replaced line | **NEEDS A RULING** | `capture/approval.py` |
| Opas's language reaching any of it | **DOES NOT EXIST** | — |
| The "why?" question on that change | **DOES NOT EXIST** for a non-capture edit | `capture/why.py` |

## 1. The write path already permits this

`sales_service.update_sales_order` refuses only `completed` and `cancelled`:

```python
if order.status in ("completed", STATUS_CANCELLED):
    raise HTTPException(400, f"Cannot modify order in '{order.status}' status")
```

A **confirmed** order is editable today, through the office's own UI, with the transition
gate and the period lock both in force. So "Opas can't change orders" is a fact about
Opas, not about the platform — which makes this smaller than it looks.

⚠️ **AND IT IS WHY THE REFUSAL NAMES UNDO CONFIRM RATHER THAN SAYING "IMPOSSIBLE".** The
office has a way to do this; the bar does not reach it.

## 2. The history entry exists and would not say what changed

`update_sales_order` calls `audit_service.log_action` **without `changes`**. Measured and
already recorded in `order_list/detail.py:287`: production holds `created` rows carrying a
`changes` JSON and **`updated` rows with `changes` NULL**, which is why the Sales Order
Pane's history tab renders `detail_absent` — a row that says *something happened* and
cannot say what.

So the history piece is not "add logging". It is **pass the field diff that the edit
already computes**. Cheap, and worth doing whether or not Opas ever edits anything,
because the office's own edits are equally blind today.

## 3. Re-pricing is a ruling, not a derivation

Lines are built at approve time in `capture/approval.py` from
`_product_by_exact_name(db, tenant, name).price`. Replacing a vault means dropping one
line and building another — and **which price applies is a business decision nobody has
made**:

- the price **today**, when the change is made; or
- the price **the order was taken at**, which is what the funeral home was quoted.

`price_list_versions` exists and is versioned, so both are answerable. ⚠️ They differ the
moment a price list is activated between the order and the edit, and on a monthly
statement the difference is visible to the customer. This is the piece that needs James
rather than an engineer.

Two more that fall out of it:

- **An invoiced order.** `undo_confirm_blocker` already refuses undo once an invoice
  exists; an edit would need the same refusal, or a credit note, which is a bigger thing.
- **Equipment and ancillary lines.** A vault change can imply a different lowering device
  or vault placer. `approval.py` derives those at capture time from the whole text; an
  edit that changed only the vault would leave them untouched and silently inconsistent.

## 4. Opas's language reaching it — the actual missing piece

Three sub-pieces, none of them large on its own:

1. **An intent.** `asks_to_edit` (added 2026-10-26) already recognises the shape —
   `<verb> … to <target>` — but only to refuse it. It does not say WHICH order or WHICH
   field.
2. **A target.** "the vault" is a field name; "this order" is the pane in front. The host
   already resolves "the cemetery" and "the customer" against the front order
   (`handleContext`), so the mechanism exists and would extend.
3. ⚠️ **A SHAPE FOR THE DOOR TO RETURN, WHICH IS THE PART TO BE CAREFUL ABOUT.** The
   door's returnable shapes are exactly `question` and `picks`, both reads — that is the
   audit from item 1, now pinned by
   `test_THE_AUDIT_the_doors_shapes_are_reads_and_nothing_else`. Teaching it to return an
   ACTING shape is the change that let a label promise an edit in the first place, one
   level up. If an edit intent is ever added, the rules should own it end to end and the
   model should stay out: "change X to Y" is a deterministic phrase, and nothing is
   gained by asking a model to interpret it.

## 5. The "why?" question on that change

The dispatch says this kind of change "is exactly what 'why?' should ask about too", and
it is — but the current detector cannot see it.

`capture/why.changes()` compares `capture_sessions.opas_proposed` against
`capture_sessions.values`. **An edit to a confirmed order has no capture session**, so
there is no `opas_proposed` to compare and no session for the answer to hang on
(`capture_sessions.decision_id` is the link the whole flow uses).

What would make it work, and it is less than it sounds:

- The edit path computes a **before/after field diff** anyway — it needs one for the
  history entry in §2. That diff is the same shape `why.Change` already carries
  (`field_id`, `was`, `now`).
- `why.changes()` would take that diff directly rather than reading it off a session, and
  `ask_payload` would key on the ORDER rather than on `sales_order_id` being set.
- The decision row would be written by the edit rather than by `record_capture_open`.

⚠️ **AND THE SOURCE WOULD BE A NEW ONE.** Today a change is `extraction`, `prefill` or
`default` — all of them things OPAS proposed. An edit after approve is a change to a
value **the person already approved once**, which is a different event and should say so:
the rule drafted from it means "we got this wrong after the fact", not "Opas misread you".

## Scope options, cheapest first

1. **Leave it refused** (today's state). The office uses Undo confirm, which works and is
   now named in the refusal. Cost: nothing. ⚠️ It is also the honest state while the
   pricing ruling is open.
2. **"the vault" → Undo confirm, then re-capture.** Opas offers the undo as a button in
   the reply line instead of a sentence; the office presses it and retypes. No new write
   path, no pricing question, because the order goes back through capture and is priced
   exactly as a new one. ⚠️ **It loses the order number and the history continuity**,
   which may be the deciding objection.
3. **A real field edit through `update_sales_order`.** Needs: the pricing ruling, the
   diff-carrying history entry, an invoiced-order refusal, the ancillary-line question,
   and the "why?" extension above. This is the full version and the pricing ruling gates
   it.

**My recommendation, for what it is worth: option 2, then §2's history fix on its own
merits.** Option 2 answers what James reached for — "I want this order to be a
Continental" — without opening the pricing question, and re-capture re-derives the
equipment lines rather than leaving them stale. Option 3 is the right end state and
should wait for a price ruling rather than acquire one by default.
