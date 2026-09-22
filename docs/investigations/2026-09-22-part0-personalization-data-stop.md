# Part 0 STOP — personalization order data exists on production

**2026-09-22, read at 14:08–14:10 UTC.** Read-only at the connection level
(`SHOW transaction_read_only` → `on` before every probe); no credential value
printed, requested or written. **No code was written. Parts 1–3 were not started.**

---

## The count

| table | rows | with personalization |
|---|---|---|
| `case_merchandise` | **3** | **1** (`vault_personalization` non-null) |
| `order_personalization_tasks` | 0 | — |
| `legacy_proofs` | 0 | — |
| `order_personalization_photos` | 0 | — |

The dispatch's condition is unconditional — *"If either is non-zero, STOP"* — and
one is non-zero. Stopping.

⚠️ **The preliminary's claim was wrong, and this is why the dispatch asked.**
`2026-09-22-capture-schema-preliminary.md` inferred "nothing is stored" from
counts of *neighbouring* tables — `legacy_proofs`, `wilbert_program_enrollments`,
`configurable_item_registry`, all genuinely 0. It never counted
`case_merchandise`, because that table was not part of the availability question.
The inference was reasonable and the conclusion was false.

---

## What the row is

**The seeded Hopkins demo case.** Not customer data.

| | |
|---|---|
| case | **`FC-2026-0001`**, status `active`, created 2026-05-06 23:46:58 UTC |
| tenant | `hopkins-fh` — the canonical synthetic funeral-home dev tenant |
| vault manufacturer on the case | `090e7eeb…` = `sunnycrest` |
| orphaned? | **no** — 0 orphans against the correct parent |

CLAUDE.md §7 describes `seed_fh_demo` as creating *"demo case FC-2026-0001 (John
Michael Smith, veteran)"*, and the blob's `name_display` is `JOHN M. SMITH` with
`emblem_key: patriotic_flag`. All three `case_merchandise` rows belong to
`hopkins-fh`.

⚠️ It is still **on production**, and removing it is a destructive production
write. That is James's, not mine.

### The blob, verbatim

```json
{"font": "uppercase",
 "options": {"vinyl": null, "legacy_print": null,
             "physical_emblem": {}, "physical_nameplate": null},
 "emblem_key": "patriotic_flag",
 "name_display": "JOHN M. SMITH",
 "template_type": "burial_vault_personalization_studio",
 "nameplate_text": null,
 "schema_version": 1,
 "vault_product_id": null,
 "vault_product_name": "Monticello Standard",
 "birth_date_display": "March 3, 1942",
 "death_date_display": "April 9, 2026",
 "family_approval_status": "approved"}
```

**It is keyed by the canonical four**, and it carries `schema_version: 1` — so
there is already a declared version to migrate from, which makes the migration
cheaper than it would otherwise be.

---

## ⚠️ And the one row in existence is the case the new STOP was written to protect

This is the part worth ruling on rather than just cleaning up.

`physical_emblem` is `{}` — present — while `physical_nameplate` is `null`. **The
single row of personalization data that exists anywhere is an emblem with no
nameplate.** Under the Part 1 model that is `nameplate_cover_emblem =
cover_emblem_only`, which the dispatch says only Salute permits.

Two things follow:

1. The mapping is not hypothetical. `{physical_emblem: {}, physical_nameplate:
   null}` → `cover_emblem_only` is a real transformation with a real row.
2. ⚠️ `vault_product_name` is **`"Monticello Standard"`** — and the portal records
   Monticello® as `hasPersonalization: false`. The row is an emblem-only
   personalization on a vault that, per the source of truth, offers none. Whether
   that is demo data being careless or a naming mismatch (`"Monticello Standard"`
   is not a portal vault id, and `vault_product_id` is **null**) is not
   established here.

So the single existing row is an example the proposed availability model would
classify as impossible. That is a useful test case and a bad thing to migrate
silently.

---

## ⚠️ Two instrument errors I made, and what actually caught them

**I claimed the row was orphaned. It is not.** I queried `fh_cases`, got 0
matches, and read that as "the parent is gone." The foreign key is
`case_merchandise.case_id → funeral_cases.id ON DELETE CASCADE` — a different
table. `fh_cases` exists and holds **0 rows**, so *every* row is "missing" from
it, and a `NOT EXISTS` against it returns 3 for any input.

⚠️ **My "second method" was the same assumption re-expressed.** I re-derived the
orphan count with `NOT EXISTS`, which felt independent and shared the one thing
that was wrong — the table name. What caught it was reading the FK catalogue,
which is a different kind of question, not a different phrasing of the same one.
Against the correct parent the orphan count is **0**.

**And I guessed column names twice after enumerating them.** I printed the
`funeral_cases` columns that exist, then wrote a query naming
`deceased_first_name`, which does not exist on that table. The fix was to build
the projection *from* the catalogue rather than reading the catalogue and then
typing from memory — enumerating and then not using the enumeration is its own
failure mode.

---

## What this leaves — named, not chosen

- **(a) Delete the row and proceed as greenfield.** It is demo data on the
  synthetic tenant. Cheapest, and it discards the only real example of the
  emblem-only case. A destructive production write.
- **(b) Migrate it.** One row, `schema_version: 1` already declared, mapping is
  `{physical_emblem: {}} → cover_emblem_only`. Proves the migration path on the
  one row that exists before there are more.
- **(c) Leave it and version the reader.** The new model reads `schema_version`
  and interprets v1 blobs in place. No write to production at all, and the cost
  is a permanent compatibility branch for a demo row.
- **(d) Re-seed instead.** `seed_fh_demo` produced it; the demo could be
  regenerated in the new shape once the model exists, making the question moot —
  but that is still a production write today.

**Independently of which:** the Monticello-with-an-emblem contradiction should be
ruled on, because if demo seed data disagrees with the availability model, the
first thing the new reader does on production is reject its own demo.
