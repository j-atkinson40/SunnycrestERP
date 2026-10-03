# r196 pre-flight — and why the instrument differs from r195's

**2026-10-03.** Read-only against production, guard confirmed `on`, credentials not
printed. Run before pushing r196.

⚠️ **r195 was pre-flighted by SYMMETRIC DIFFERENCE because it asserted specific
CONTENT. r196 asserts PRESERVATION, so it is content-agnostic and a set comparison
is the wrong check.** What matters is not that production's rows match a reference —
they legitimately do not — but that r196's preconditions hold against whatever is
there.

## 1. The environments differ by design, and that is fine here

```
                              dev                     production
product_catalog_templates     25 rows (15 t / 10 f)   37 rows (31 t / 6 f)
  written by                  x1y2z3a4b5c6 migration  catalog_template_seeder
products                      27 rows, all false      33 rows, all false
  head                        r196 (local)            r195
```

The 25-vs-37 split is the long-standing divergence recorded in
`2026-10-02-platform-catalog-discrepancies.md` §1: the seeder has never run on dev
because it is gated on `PLATFORM_ADMIN_*`. Neither population is the other's subset.

⚠️ **A symmetric-difference check would report dozens of differences and all of
them would be expected.** Running it anyway and then explaining the output away is
how a check stops being one.

## 2. Production's values confirm the ruling independently

Production's 31 `true` / 6 `false` matches `catalog_template_seeder` exactly:

```
WILBERT_BURIAL_VAULTS  19  is_manufactured=True   (:87)
WILBERT_URN_VAULTS     12  is_manufactured=True   (:103)   -> 31 true
CEMETERY_EQUIPMENT      6  is_manufactured=False  (:119)   ->  6 false
```

**So the preserve-don't-null ruling is evidenced in production, not only in dev.**
Those 37 rows carry a real per-category decision — vaults are poured, cemetery
equipment is bought — and nulling them would destroy it to satisfy a rule aimed at
uniform fills.

## 3. Preconditions, by value

| check | production | r196 needs |
|---|---|---|
| `products.is_manufactured` nullable | `NO` | will be altered to YES ✓ |
| `products` default | `false` | will be dropped ✓ |
| `products` rows | 33, all `false` | UPDATE nulls 33; `rowcount == n_before` holds ✓ |
| `product_catalog_templates` nullable | `YES` | already correct — no alter needed ✓ |
| `product_catalog_templates` default | `true` | will be dropped ✓ |
| `product_catalog_templates` rows | 37 | untouched; `after == before` holds ✓ |
| values vary | 31 t / 6 f | `test_the_values_actually_vary` passes ✓ |

**Verdict: safe to deploy.**

## 4. ⚠️ One hazard this exercise surfaced, about break-testing

A break test set every `product_catalog_templates` row to `true` on dev, and **r196's
own downgrade could not restore it** — because r196 deliberately does not own those
rows. The round trip completed and left the damage in place.

Restored from the authoritative source rather than guessed: `x1y2z3a4b5c6` writes
`True` for Burial Vaults and Wastewater, `False` for Redi-Rock and Rosetta
Hardscapes, which reproduces dev's 15/10 exactly.

**The general shape: a break test against data owned by an EARLIER migration cannot
be undone by the current one's downgrade.** Check who owns the rows before breaking
them, and know the restore path first. The round trip is not a universal undo —
it only reverses what the migration under test actually wrote.

## 5. What this does not establish

- That the deploy will succeed. The head is read from `alembic_version` afterwards.
- Anything about whether any licensee actually pours. That is the question
  onboarding will ask; this migration only stops the schema answering it by default.
