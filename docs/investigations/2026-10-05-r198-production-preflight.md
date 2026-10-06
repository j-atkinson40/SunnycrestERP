# r198 production preflight

**Read-only. 2026-10-05.** Run before pushing `e2d5a8e0`.

## Which instrument, and why not the other one

r198 is **additive**: one nullable column, no default, no row touched. It asserts
nothing about existing rows.

So a **content comparison** — the r195 shape, where loaded data had to be checked
against its source — would be answering a question this migration does not raise.
It would also invite the stronger failure: a clean-looking diff over an empty
table reads as agreement, which is the empty-control defect.

This is the **r197 shape**. What can go wrong with an additive migration is narrow
and checkable **by value**, and all three were checked:

| | result | why it matters |
|---|---|---|
| 1. does `vault_resolution` already exist | **absent** | `env.py` monkey-patches `op.add_column` idempotent, so an existing column would make the migration a no-op wearing a step's clothes |
| 2. production's head, from `alembic_version` | **`r197_capture_answered_fields`** — matches r198's `down_revision` | a mismatch means the chain is wrong |
| 3. row count of the altered table | **0** | if non-zero, every claim this arc made about the capture path never having run is false |

Controls read before the results: `transaction_read_only = on`, `companies = 4`
(a connection that cannot see rows returns the same zero as an empty table).

**Zero rows CLOSES the argument-from-absent-writer** rather than merely failing to
contradict it — the same distinction the r197 preflight drew, and the reason this
read is worth the trip even though the migration is safe at any count.

Also confirmed, because r198's own positive control asserts it:
`answered_fields` and `missing_fields` are both present and `jsonb`.

## Verdict

**Safe to merge.** Additive, nullable, no default; chain matches; the table it
alters is empty in production.

## Note

Production's head being `r197` confirms that r197 itself deployed — the first
observation this arc has of a capture migration reaching production, since
nothing in the capture path has ever run there.
