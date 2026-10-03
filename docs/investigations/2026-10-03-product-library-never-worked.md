# The onboarding product-library route has never worked — 200 days

**2026-10-03.** Measured before 2b-3 Commit 1. Read-only apart from the fix already
landed in `c5a3f911`.

**Three answers, and they compose into one finding: the onboarding
product-selection step has never functioned, and nothing else filled in for it.**

---

## (a) Broken at birth, not drifted into

Both the route and the service signature landed in the **same commit**:

```
e8e86328  2026-03-17  Add tenant onboarding system with guided setup,
                      product library, and import wizard
```

The call was wrong on the day it was written:

```python
# e8e86328, as committed
return tenant_onboarding_service.get_product_library(
    db, company.id, preset=preset, category=category
)

# the service it calls, same commit
def get_product_templates(db, preset=None, category=None)
```

`company.id` binds positionally to `preset`; the keyword re-binds it.
`TypeError: got multiple values for argument 'preset'` — **every call, since
2026-03-17. 200 days.**

⚠️ **This is not a regression anyone introduced.** There is no commit that broke it
and no window in which it worked. The route was never exercised between being
written and being read today.

## (b) The frontend calls it, and swallows the failure into a toast

```
App.tsx:1381                      <Route path="onboarding/product-library" …/>
onboarding-service.ts:71          GET /tenant-onboarding/product-library
product-library.tsx:106           .catch(() => toast.error("Failed to load product library"))
```

So the page **is** reachable, it **does** call the endpoint, and on the 500 it shows
a toast and leaves `templates` as `[]` — an empty product list.

⚠️ **The failure is visible but misattributed.** "Failed to load product library"
reads as a transient network problem. It is a permanent 500, and the phrasing is
what let 200 days pass without anyone chasing it. A message that said *"this
endpoint returned 500"* would have been chased on day one.

⚠️ **And it is an `.catch()` with no state change** — no error banner, no retry, no
distinction between "failed" and "empty". A user who dismisses the toast sees a page
that looks like a catalog with nothing in it, which is a different and plausible
story.

## (c) Nothing populated Sunnycrest. Its production catalog is four demo rows.

Two other paths could have filled the gap. Neither did.

**`sunnycrest_product_seeder`** defines 49 products matching the price list exactly.
Its only caller is `POST /products/seed-sunnycrest` (`products.py:254`) — a manual,
permission-gated endpoint. It is **not** in `run_canonical_seeds.sh`, **not** in
`seed_manifest.py`, and **not** called at startup.

**Production, measured read-only 2026-10-03:** Sunnycrest holds **4 products, all
`DEMO2-*`**, written by `scripts/seed_accounting_demo.py`. So that endpoint has
never been invoked there, and the 49-product seeder has never run.

**Therefore:**

| path | status |
|---|---|
| onboarding product library | 500 since 2026-03-17 |
| `POST /products/seed-sunnycrest` | exists, never invoked in production |
| what Sunnycrest actually has | 4 demo rows from the accounting demo seeder |

⚠️ **The onboarding checklist still lists `add_products` as `must_complete`**
(`onboarding_service.py:234`), and `quick_orders` declares
`depends_on: ["add_products"]` (`:351`). So the checklist has been asking a tenant
to complete a step whose only UI route returns 500 — and gating a later step behind
it.

## What this settles, and what it opens

**Settles Commit 2 entirely.** A route that has returned 500 on every call **has no
clients to break**. No caller has ever received a response containing the old
`category` vocabulary, so there is nothing to preserve: `form` with its six real
values, no deprecation window, no aliasing of the old three. ⚠️ **Safe because the
endpoint never worked — not because a break was judged acceptable.** Those are
different justifications and only the first is available here.

**Opens, and not resolved here:**

- **Has ANY tenant been provisioned through `import_product_templates`?** Still
  unestablished — carried from `2026-10-02-platform-catalog-discrepancies.md` §4 and
  now sharper: its sibling route has never worked, and the POST endpoint it pairs
  with (`product-library/import`) is reachable from the same dead page.
- **What should the `add_products` checklist item mean**, given the step behind it
  has never functioned? A checklist that cannot be satisfied is its own defect.
- **Why Sunnycrest's real catalog was never seeded.** The 49-product seeder matches
  the price list exactly and sits behind a manual endpoint nobody called.

## ⚠️ Method note

This was found by **trying to make the thing work**, not by reasoning about it. The
dispatch that specified validation for this route was written by someone who had put
the can't-fire shape into canon twice that morning, and the validation was specified
for a path that cannot execute. Nothing in reading the code revealed it — the route
is well-formed, the service is well-formed, and the mismatch is only visible when
the two are called together.
