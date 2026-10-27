# The personalization clear never ran

**2026-10-27.** Read-only measurement plus a four-break test. Found while writing a
production *retest* probe for James's guided-capture FIXES — not by any test.

## What was broken

James's slice-1 dispatch, clause 4:

> Changing an answer clears what no longer fits (urn after burial clears equipment; **a
> vault without that personalization clears it**) and says why in one line in the pane
> footer.

The first half works. The second half had **never executed once**, from the day it
shipped, and two independent defects were each sufficient to stop it:

| # | defect | raises |
|---|---|---|
| 1 | `resolve_availability_config` imported from `personalization.availability` — it lives in `personalization.**enrollment**` | `ImportError` |
| 2 | `resolve_schema(db, company_id=…, values=…)` against a signature that is keyword-only over `(vault_product_id, personalization_config, vault_form, tenant_config, platform_fields, answers)` — it takes no session, no `company_id`, no `values` | `TypeError` |

Both sat inside one `try:` whose handler was `except Exception:`. So both read, at
runtime, as *"this tenant has no availability configured"* — the condition the handler
was actually written for. Two defects, one silence, and the silence was indistinguishable
from correct behaviour.

## How 60 green tests and a 48/48 break harness missed it

⚠️ **Four tests covered clause 4. All four tested the equipment half.** The
personalization half had no test at all:

```
test_the_clearing_reports_the_keys_it_removed          urn vault  -> equipment clears
test_a_burial_to_burial_change_clears_NOTHING          burial->burial, no clear
test_changing_something_OTHER_than_the_vault_...       guard is on the changed field
test_an_equipment_answer_that_fits_a_cremation_...     tent_only survives
```

⚠️ **AND THE BREAK HARNESS COULD NOT HAVE CAUGHT IT.** Breaking a path that no test
exercises turns nothing red. A break test proves a check *can* fire; it is blind to a
check that does not exist. The gap was an absence, and §11's remedy — break it and watch
it go red — has no purchase on an absence.

The three follow-up tests that *do* touch personalization go through a local
`_resolved_with()` helper which passes `personalization_config` **directly** to
`resolve_schema`. So they exercise the narrowing, correctly, and never touch either of
the two lines that were wrong.

## How it was actually found

A production retest probe was written to confirm the shipped slice-1 behaviour, and it
copied `from app.services.personalization.availability import resolve_availability_config`
out of `clears.py`. The probe has no `except`, so it raised where `clears.py` was quiet.

⚠️ The defect was surfaced by **re-using the bad line in a context that could not swallow
it**. That is luck, not method — and it is the second time this arc that a production
probe has found something 60 green tests held.

## The fix, in three parts

1. **Right module.** `personalization.enrollment`.
2. **Right call shape** — `typed_extraction`'s, which was the working precedent all
   along. The vault arrives here as a *name*, and availability is keyed by
   `variant_template_id`, so the name goes through the catalogue's own resolver first.
3. **The structural part, which matters more than either.** The imports moved to module
   scope, so a wrong name is now an `ImportError` *at import*, which every test in the
   package trips immediately. And the handler narrowed from `except Exception` to
   `except SQLAlchemyError`, so *"the config table is unreachable"* still fails open while
   *"this code is wrong"* fails loudly. Removal, not recognition: the silent form is no
   longer expressible.

The `# pragma: no cover` came off the handler. ⚠️ It had been load-bearing in the wrong
direction — telling the coverage tool not to care that the fail-open branch never ran
under test, while in production it was the *only* branch that ever ran.

## Five tests, four breaks

```
BREAK 1  wrong import module        -> all 5 red (ImportError at module scope)
BREAK 2  wrong resolve_schema call  -> 3 red (REACHES / does_not_offer / DOES_offer)
BREAK 3  bare `except Exception`    -> 1 red (PROGRAMMING_error_is_NOT_swallowed)
BREAK 4  drop the permitted guard   -> 1 red (DOES_offer — the discriminator)
CONTROL  restored                   -> 5 pass
```

The first new test asserts only that the branch **runs** — a call count, not an outcome.
⚠️ That is deliberate: *"no exception raised"* was true for the entire period the rule did
nothing, because the exception was caught. A non-zero call count is the one reading the
broken version could not produce.

## ⚠️ It is correct now and still inert on production

The rule reads `permitted_answers`, which is filled from availability keyed by
`variant_template_id`. Measured read-only against production this afternoon:

| sunnycrest | |
|---|---|
| products | 10 |
| …carrying `variant_template_id` | **0** |
| availability variants | 40 |
| …narrowing personalization | 4 |
| products whose **name** resolves to a variant | 1 |
| …to a **narrowing** variant, i.e. the rule can fire | **0** |

testco (dev) is the same shape: 25 products, 2 resolve to a variant, 4 variants narrow
personalization, **0** products reach a narrowing one. This is why the positive test has
to craft the licensee config — the case cannot be built from seeded data in either
environment.

⚠️ **So James will not see this rule fire on his walk, and that is not a new defect.** It
is the `variant_template_id` backfill, already open, now with a concrete consequence
attached: until the catalogue link is populated, *"a vault without that personalization
clears it"* has nothing to read.

⚠️ **And re-deriving caught an arithmetic defect in my own STATE entry — a narrower
fault than I first wrote, so stated narrowly.** That entry reads *"populated on 0 OF 39
PRODUCTION ROWS. Both tenants, 0 of 10 and 0 of 25."* The **breakdown is correct** and
today's read reproduces the sunnycrest half exactly (0 of 10). The **headline disagrees
with it**: 10 + 25 = 35, not 39. So this is not an inherited figure measured against the
wrong population — it is a total that was never derived from the two numbers printed
beside it, in the same sentence, where the discrepancy was checkable by addition.

⚠️ Which is the shape worth keeping rather than the size of the error. A wrong total sitting
next to its own correct parts is invisible precisely because the parts look measured — and
they were. Nobody adds up a sentence they have already read.

## Sibling audit

The wrong import was unique to `clears.py`. Of the four other `except Exception` sites in
files I wrote this slice, none is hiding anything:

- `vault_form.py:183, :351, :441` — all three wrap `product_name_resolver` imports that
  are **correct**, and the path is proven live by measurement rather than by reading:
  `form_of` returns `via=name_resolver` on real testco products, which only happens if the
  `try` completed.
- `session_service.py:1123` (the cremation chip) — correct import, and it
  `logger.warning(..., exc_info=True)`. **Logging is the distinguishing property.**
  `clears.py` was the only one that swallowed without a trace.

Not audited: `why.py:284`, `session_service.py:1277`, `session_service.py:1576`,
`rule_draft.py:99`. These predate this slice and I did not read them — stating that
rather than implying a clean sweep.
