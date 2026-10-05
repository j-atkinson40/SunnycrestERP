# The vault-name resolver — scope, measured before building

**Read-only. 2026-10-05.** No resolver exists; this measures what one could reach
with the data present, so the arc is scoped from the catalog rather than from an
impression.

## What exists

| | |
|---|---|
| variants | 52 |
| products | 29 |
| families | 24 |
| `platform_product_aliases` | **5 rows, right columns, ZERO readers** outside `app/models/` and the 4 migrations that made it |

⚠️ **The alias table is already load-bearing in the measurement even though
nothing reads it.** Of the phrases that resolve uniquely today, **three do so only
because of an alias row**: `Veteran` → `BV-VTRI`, `SST` → `BV-SSTRI`,
`Basic Gray` → `UV-SAL`. The substrate is right and seeded; it is unwired.

## ⚠️ The headline: this is not a fuzzy-matching problem

**8 of 52 variants cannot be reached uniquely by their own display name**, and
**15 surface forms are ambiguous** — but they are ambiguous for **three distinct
reasons**, each needing a different discriminator:

| cause | example | discriminator |
|---|---|---|
| **FORM** — the same family in burial and urn | `bronze triune` → `BV-BTRI`, `UV-BTRI` | burial vault vs urn vault |
| **SIZE** — the same product in several sizes | `continental` → `BV-CON`, `BV-CON34` | 34″ etc. |
| **LINE** — the same finish across product lines | `cream & gold` → `P300` (regal), `P310` (tribute-urn) | which line |
| *(and tier)* | `triune burial vault` → **5 variants** | the option: Bronze / Copper / SST / … |

A resolver that returned a best match would silently choose one of each pair.
Measured: `P300` precedes `P310`, so pick-first would always sell the Regal.

## What a suffix strip buys, and what it costs

Stripping `" burial vault"` / `" urn vault"` from indexed forms:

```
phrase                     before      after       candidates
'Bronze Triune'            NO MATCH    AMBIG(2)    BV-BTRI, UV-BTRI
'Continental'              NO MATCH    AMBIG(2)    BV-CON, BV-CON34
'Monticello'               NO MATCH    AMBIG(2)    BV-MON, UV-MON
'Monarch'                  NO MATCH    UNIQUE      BV-MRC
'Copper Triune'            NO MATCH    AMBIG(2)    BV-CTRI, UV-CTRI
'Continental 34 inch'      NO MATCH    NO MATCH    —
```

Unique-by-display-name stays **44 of 52**; ambiguous forms go **15 → 31**.

⚠️ **That looks like a regression on one metric and is the right trade.** Before
the strip, the common spoken forms reached *nothing*; after it they reach the
right *candidates*. "No match" is not better than "two candidates" — it is worse,
because two candidates is a question you can ask and no match is a dead end.

`Continental 34 inch` still fails: the catalog spells it `Continental 34"`, so
size normalisation (`34 inch` / `34in` / `34"`) is its own small piece.

## ⚠️ The design this implies — a ruling worth making before any code

**The resolver should return a CANDIDATE SET plus the discriminator that would
narrow it, not a best match.**

```
resolve("Bronze Triune")  -> candidates=[BV-BTRI, UV-BTRI], discriminator=FORM
resolve("Continental")    -> candidates=[BV-CON, BV-CON34], discriminator=SIZE
resolve("Cream & Gold")   -> candidates=[P300, P310],        discriminator=LINE
resolve("Monarch")        -> candidates=[BV-MRC],            resolved
resolve("Bronze Triune Burial Vault") -> candidates=[BV-BTRI], resolved
```

Three reasons, in order of weight:

1. **A capture overlay is exactly the surface for an ambiguity.** "Bronze
   Triune — burial or urn vault?" is one question the operator can ask while the
   caller is still talking. A silent best match throws that away and sells the
   wrong thing.
2. **The context often resolves it without asking.** The capture already knows
   the form from the order; a resolver returning `discriminator=FORM` lets the
   caller filter rather than guess.
3. **It makes the failure mode loud.** Every instance this arc has catalogued had
   a quiet wrong answer where a loud one was available.

## Scope: four pieces, smallest first

1. **Normalisation + the index.** Case, trademark marks, smart quotes, `34 inch`
   → `34"`. Indexes variant display name, SKU, product name, option+product, and
   **alias rows** — the first reader that table will ever have.
2. **Suffix handling**, as measured above.
3. **Candidate sets + discriminator classification** — FORM / SIZE / LINE /
   OPTION, derived from what the candidates differ by rather than hardcoded.
4. **Alias writing** — `source` and `is_confirmed` exist on the table, so a
   confirmed resolution can teach it. ⚠️ Out of scope until 1–3 ship; a
   self-teaching index whose matching is wrong teaches the wrong thing.

## What this unblocks, and what it does not

**Unblocks:** `vault_size`'s removal (ruled redundant, currently the only place
size is captured); the three personalization questions permanently omitted because
`vault_product_id` is always `None` at the call site.

⚠️ **Does NOT unblock RC provisioning.** I have said twice that this resolver
"gates RC provisioning" and that is backwards — the *call overlay* needs RC to be
reachable, and the resolver needs a vault NAME to resolve. They are independent:
six of eight provisioning pieces are absent, beginning with the authorize
endpoint, and none of them is this. Correcting my own claim.

## Method

52 variants, 5 aliases, 24 families read live. Every surface form indexed and
collisions enumerated rather than sampled. Candidate phrases taken from three
sources with ground truth — `FULL_RESULT` in the tests, the call-to-print
prototype, and the 09-22 prototype's `VAULTS` map — rather than invented, so
"no match" means a form someone actually wrote, not one I imagined.
