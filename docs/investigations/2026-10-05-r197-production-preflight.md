# r197 production preflight — the absent-writer argument, closed with a count

**Read-only. 2026-10-05.** Run before pushing `2905be69` (r197).

## Why this read happened

r197 adds a **nullable column with no default**, which asserts nothing about
existing rows and is therefore safe at any row count. The read was not to
validate the migration.

It was to close an argument I had been making from an **absent writer** rather
than from a measurement: *"RingCentral has no OAuth entrance, therefore no
extraction can exist in production."* That reasoning is the shape CLAUDE.md §11
warns about — a cause inherited across several messages until it reads as
background fact. Zero confirms it. **Non-zero would have meant the overlay has
run in production through an entrance nobody located**, which is a larger finding
than the migration it was gating.

## Result

```
TARGET host=shuttle.proxy.rlwy.net port=57253 db=railway
CONTROL transaction_read_only = on
CONTROL companies = 4            (must be > 0 or every zero below is void)

  ringcentral_call_extractions       0 rows
  ringcentral_call_log               0 rows

  answered_fields already present in production: False   (expect False — r197 unmerged)
```

**Zero, as expected.** The argument from the absent writer is now an argument from
a count.

## And the enumeration found something stronger

The first probe asked for `ringcentral_connections` and reported **TABLE ABSENT**.
⚠️ That name was constructed, so the absence was a *failed lookup* until the real
set was enumerated — the false-absence defect, caught here before it was
reported as a finding.

Enumerated instead:

```
CONTROL total public tables: 496
TABLES MATCHING ringcentral / rc_ / call (2):
   ringcentral_call_extractions     0 rows
   ringcentral_call_log             0 rows
```

And the models declare exactly those two `__tablename__`s and no others.

**So there is no OAuth/token table for RingCentral anywhere — not in production,
not in the models.** That is stronger than "no tenant holds a token": there is
nowhere a token could be stored. The overlay is not merely unreachable for want
of a UI entrance; the persistence an OAuth flow would require does not exist.

Which also means the gate on the conditional-omission work (`vault_product_id`
is permanently `None` at that call site "until RC provisioning") is wider than
"provision the credential" — it includes building the connection storage.

## Verdict

**r197 is safe to merge.** The column it adds is nullable with no default; the
two tables it concerns hold zero rows in production; and the column does not yet
exist there, so the migration is a true forward step rather than a re-run.

## The probe

Both scripts ran under the §7 contract: connection-level
`default_transaction_read_only=on`, asserted before any query; credentials
redacted to host/port/db via `urlparse`; no credential value printed or read.
Token presence would have been read as a boolean only — the `ringcentral_connections`
branch that would have done so never executed, because the table does not exist.

Positive controls, read before the results they vouch for: `transaction_read_only
= on`; `companies = 4` (a connection that cannot see rows returns the same zero as
an empty table); `496` public tables enumerated before filtering.
