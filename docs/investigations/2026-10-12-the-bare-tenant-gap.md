# Why five live defects survived hundreds of passing tests

Written 2026-10-12, executing the ruling *"Test-fixture gap (the root of all five
live defects): session and pane tests must run against a tenant with the real
catalog, availability and aliases seeded, not a bare tenant."*

---

## ⚠️ THE STATED ROOT CAUSE IS WRONG, AND IT WAS MINE BEFORE IT WAS THE RULING'S

The ruling's premise — and James's relayed wording, *"their fake tenant had no
products, so no vault ever resolved"* — came from me. I wrote it in a commit
message, in STATE.md and in the walk doc, three times, without measuring it.

**Measured, on a tenant consisting of one `companies` row and nothing else:**

| | |
|---|---|
| catalog index, 56 aliases | **reachable** |
| `Continental 34` resolves to one variant | **yes** |
| availability config | **present** (1 entry) |
| personalization permitted set | **`['nameplate_only']`** — it narrows |
| the conflict that produced the HTTP 500 | **arises** |
| cemeteries | **0** |

The catalog (`product_catalog_templates`), the alias table
(`platform_product_aliases`) and the availability config are **platform-level, not
tenant-scoped**. A bare tenant inherits all three. Only the cemeteries are
tenant-scoped, and they are the only thing it lacks.

**So four of the five defects were reachable on a bare tenant the whole time.**

## What actually hid them

Not the tenant. **The inputs.**

No session test ever typed a phrase that resolved a vault to exactly one variant.
The fixtures used `tent only`, `nameplate only`, `years only`, `full setup` — none
of which names a vault — and the one test that did name one used `Continental`,
which is ambiguous and produces a *pick* rather than a resolution. With no single
variant resolved, `permitted_answers` is never consulted and the entire conditional
layer is unreachable regardless of what the tenant has.

This is a worse finding than the one it replaces, because a missing fixture is a
thing you can see in a conftest and a missing *input* is not. Nothing in the test
file announced that every phrase in it stopped short of the same layer.

## The evidence, per defect

The five defects, reintroduced one at a time, against the five new session tests —
run twice, once on the seeded tenant and once on a bare one.

| defect reintroduced | seeded tenant | bare tenant |
|---|---|---|
| 1 `UnpermittedAnswer` raises (the 500) | tests 1, 2 red | tests 1, 2 red |
| 2 the withheld answer is rendered | test 2 red | test 2 red |
| 3 `is_conditional`/`permitted` conflation | test 3 red | test 3 red |
| 4 apostrophes become separators | test 4 red | **no change** |
| 5 the symbol gate loses its context | test 5 red | test 5 red |
| *control, nothing broken* | **all 20 green** | **test 4 red** |

Read the bottom-right cell first. On a bare tenant **test 4 is red before anything
is broken**, because no cemetery exists to match — so it is a saturated signal
there and cannot report defect 4 at all. Its result is identical with the defect
present and absent.

**The fixture was load-bearing for exactly one of the five.** The other four were
closed by writing tests whose input names a vault.

## What was built anyway, and why it is still right

`tests/_seeded_tenant.py`, registered as a pytest plugin in `tests/conftest.py`.
`seeded` hands back the canonical `testco` tenant and **proves four facts on every
use** rather than assuming them: a vault resolves to one variant, the alias table
is loaded (checked with `oversized`, which appears in no product name), availability
narrows a conditional question to a real permitted set, and `St. Mary's Cemetery`
exists to be matched. It **refuses to skip** when `testco` is absent — a skip would
restore exactly the green-run-that-tested-nothing condition this work exists to end.

Keeping it, with the scope stated, because:

- defect 4 genuinely needs it, and cemetery matching is where a whole class of
  director phrasing lives;
- the four assertions are a tripwire on the environment itself, which is the thing
  nobody was checking;
- the platform/tenant split above is not guaranteed to hold — if availability or
  aliases ever become tenant-scoped, every test on a bare tenant goes quietly blind
  again, and this fixture is what would notice.

But it is **not** what closed four of the five, and a reader who believes it is will
under-estimate the real hazard: inputs that stop short of a layer.

## The consequence for how tests get written here

A fixture can be audited by reading a conftest. A missing input cannot be audited at
all — it looks like a test suite with a lot of tests in it.

So the question to ask of a capture test file is not *"what tenant does this run
against"* but **"which layers do these inputs actually reach?"** For this engine
the layers are: vocabulary → party resolution → vault resolution → availability →
conditional applicability → row rendering. The session tests reached the first two
and the last one, and reached nothing in between, for as long as they existed.

## Corrections owed to the record

- `163e73ed`'s commit message says the defects were invisible because "the test
  tenants are BARE — a company, a role, a user, no products — so no vault resolves".
  Wrong. A commit message cannot be edited, so the correction lives here and in
  STATE; this document is the one a reader following that message should land on.
- `tests/_seeded_tenant.py` and `tests/test_whole_text_session.py` both made the
  claim in their first drafts and are corrected in the same commit as this document.
- STATE.md's 2026-10-12 entry is corrected in place with a `[CORRECTED]` marker and
  the original wording preserved.
- ⚠️ `docs/investigations/2026-10-12-typed-capture-round-2-walk.md` does **NOT**
  contain the claim. The first draft of this list said it did — I wrote the list from
  memory of where I had repeated myself rather than by grepping, which is the same
  unmeasured move the whole document is about, made while documenting it. Checked:
  no occurrence.

The five defects were real, were found by running the thing, and are fixed. The
explanation of why the tests missed them was an inference I never checked, offered
confidently, and then received back as a settled premise in a ruling — which is the
shape CLAUDE.md §11 names as *a CAUSE inherited more easily than a count*.
