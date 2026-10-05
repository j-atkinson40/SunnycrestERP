# Checklist gating, and `GET /debug-init`

**Read-only. Nothing fixed. 2026-10-05.** Two questions asked before the import
repair, both answered by enumeration rather than assumption.

---

# 1. `GET /debug-init` — the four questions

| question | answer |
|---|---|
| what does it do | calls `initialize_checklist(db, company.id, preset)` — creates the checklist, its items and its scenarios |
| auth-gated | yes, but **less than the real route** (see below) |
| does it write | **yes, and it commits** — `db.commit()` at `onboarding_service.py:1411` |
| does it bind | yes, correctly |

Added **2026-03-19 — two days after `e8e86328`** — in a commit titled *"Add
debug-init endpoint to diagnose onboarding checklist creation failure"*. It is a
debugging artifact from the week the onboarding system shipped, left mounted on
the live tenant router for 200 days. **No frontend caller. No test.**

Four properties beyond the four questions, in the order they matter:

**(a) It is a `GET` that commits.** Any crawler, prefetch, link preview, or
browser history replay performs the write. `initialize_checklist` is idempotent —
it returns an existing checklist unmodified — so the blast radius is bounded to
*creating a checklist for a tenant that does not have one*. That is not nothing:
it is a 28-item checklist plus scenarios, created by a GET.

**(b) It is a privilege downgrade on an operation that already exists.** The real
route is `POST /checklist/initialize` with `Depends(require_admin)`. `debug-init`
does the same work behind `Depends(get_current_user)` — **any authenticated
tenant user**, not just an admin. The admin gate on the real route is bypassable
by anyone who knows the debug path.

**(c) It returns a traceback to the client.** `traceback.format_exc()[-1500:]` —
1500 characters of internal file paths, SQL, and schema detail, to any
authenticated tenant user.

**(d) It returns 200 on error.** By design — the docstring says *"return any
errors as 200"*. So no monitor, gate, client, or log-level alert can ever observe
it failing. It is a permanently green endpoint, which is the one property on this
list that would survive every check we have.

⚠️ **This is a different kind of thing from the other 13.** Those are features
that were written and never ran. This one works, and works slightly too well.

---

# 2. Checklist gating — confirmed, not assumed

**Answer: the critical path is NOT wider than the import repair. No
`must_complete` item routes through any of the 14 dead routes.**

But the confirmation turned up one thing that *is* acceptance-relevant, and it is
not a dead route at all. **It is in the function 2b-3 Commit 3 wrote.**

## The catalogue

28 items, not the 25 CLAUDE.md §9 lists; **16 `must_complete`**, not 14. (§9's
table is stale — reported, not corrected, since canon edits need authorisation.)

Every item is `action_type: navigate` to a frontend page. So gating is: the user
lands on a page, does the work, and a `check_completion` trigger fires — or the
page calls the generic complete route.

## Where the `must_complete` items actually go

| item(s) | page | backend | verdict |
|---|---|---|---|
| `data_migration`, `import_order_history`, `review_customer_types` | `/onboarding/import` → `UnifiedImportPage` | `/api/v1/onboarding/import/*` (`unified_import`) | ✓ **clean** — 21 routes, 51 edges bound, 0 failures |
| `add_products` | `/products` | triggers at `price_list_import.py:513`, `unified_import_service.py:1094` | ✓ reachable — **but not via the product library** |
| `configure_cross_tenant` | `/onboarding/network-preferences` | `/cross-tenant-preferences` | ✓ binds (added after `e8e86328`) |
| `setup_scheduling_board` | `/onboarding/scheduling` | `/scheduling-board/*` | ✓ binds (added after) |
| `company_branding`, `setup_quick_orders` | own pages | generic complete route, called inline | ✓ binds |
| the other 8 | own pages | triggers in `tax.py`, `charge_terms.py`, `vault_supplier.py`, `cemetery_directory.py`, `accounting_connection.py`, `onboarding_hooks.py` | ✓ reachable |

**The import wizard the three import items use is a different, working
implementation.** `unified_import` (21 routes) superseded the `tenant_onboarding`
import routes and nobody retired the dead ones. That is why 200 days of
onboarding did not surface them.

Scenario items *do* route through the dead `POST /scenarios/{k}/advance` — but
`run_vault_scenario` and `run_production_log_scenario` are `should_complete` and
`run_month_end_scenario` is `optional`. **None is `must_complete`.**

## ⚠️ The finding that changes the import repair

**`import_product_templates` fires no completion trigger, and the product library
page never calls the complete route.**

```
product-library.tsx:254   const result = await onboardingService.importProductTemplates(...)
product-library.tsx:256   navigate("/products")          ← and that is the whole handler
```

Parsed from `import_product_templates`: `check_completion` is **not** among its
calls. So a licensee who uses the product library — the path 2b-3 built — imports
products successfully and **the `add_products` item stays open**. And
`setup_quick_orders` declares `depends_on: ["add_products"]`, so quick orders
never unlock.

That is the acceptance bar verbatim: *the library loads, a selection imports, the
checklist item completes, and `quick_orders` unlocks.* Repairing the route's
schema and arity delivers the first two. **The third needs the trigger**, which
is why this is going into the import repair rather than a follow-up.

## Two adjacent defects, reported not fixed

**`on_product_created` has zero real callers.** Its only reference imports it and
then does nothing with it:

```python
# production_log_service.py:143-148
    # Fire onboarding hook
    try:
        from app.services.onboarding_hooks import on_product_created
        # Check completion for production log scenario if applicable
    except Exception:
        pass
```

The comment says "Fire onboarding hook". No fire. The hook body is correct and
unreachable — complete machinery behind an unprovisioned entrance. `add_products`
survives only because two other call sites exist; nothing creating a *product*
completes it. Neither `products.py` nor `product_service.py` fires any hook.

**The generic `completeChecklistItem` helper 404s on the wrong prefix.**
`onboarding-service.ts:33` posts to `/onboarding/checklist/items/${itemKey}/complete`;
the route lives at `/tenant-onboarding/checklist/items/{item_key}/complete`, and
`onboarding.py` has no `checklist/items` path at all. The two pages that *do*
complete items (`historical-order-import.tsx:581`, `quick-orders.tsx:482`) inline
the correct path and bypass the helper — which is why the helper's breakage never
surfaced. **This is the sixth wrong-prefix frontend call**, after the five in the
sweep.

---

## Method notes

- **An instrument reported `0 failures` on a control of `0`.** The first
  `unified_import` audit resolved 0 service aliases, inspected 0 edges, and
  reported 0 failures — which reads as "clean". That router imports its services
  *inside handler bodies* and calls them by **bare name**, a shape the walker only
  looked for as `module.attr`. Rewritten to resolve function-local `ImportFrom`:
  51 edges, genuinely 0 failures. *"Zero findings" and "nothing inspected" are
  the same sentence* — second instance in two sessions.
- **I nearly reported that `add_products` can never complete.** The hook is dead
  and the library fires nothing, and the inference from there felt safe. It is
  wrong: two other call sites exist. Enumerating every `check_completion` site
  and its key argument caught it. A causal claim built on two true observations.
- **An `awk` range over `initialize_checklist` returned one line.** A near-empty
  result is not an answer; re-done with `ast`, the function is 85 lines and
  commits at the end.
- All greps here use quoted `--include='*.ts'`.
