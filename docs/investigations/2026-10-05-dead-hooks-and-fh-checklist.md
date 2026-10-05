# The dead hooks, and the funeral_home checklist

**Read-only. Nothing fixed. 2026-10-05.** One measurement, asked of the 6
remaining dead hooks. It answered that question and surfaced a larger one.

---

## ⚠️ REPORT-IMMEDIATELY: funeral_home onboarding cannot be completed

**3 of its 6 `must_complete` items have no reachable completion path.** Same
class as `add_employees`, three at once, in a vertical nobody had mapped.

| item | sort | action_target | only trigger |
|---|---|---|---|
| `review_ftc_compliance` | 2 | `/funeral-home/compliance` | **none of any kind** |
| `link_vault_supplier` | 3 | `/admin/settings` | `on_manufacturer_linked` — a **dead hook** |
| `add_directors` | 4 | `/admin/users` | **none of any kind** |

No frontend page completes any of the three, and all three `action_target`s are
**generic admin pages** rather than onboarding pages — so unlike the
manufacturing items, there is no dedicated page whose success handler would
naturally call the complete route. `review_ftc_compliance` and `add_directors`
have no trigger of any kind: not a route, not a hook, not a frontend call.

**Manufacturing, by contrast, is now fully clear** — all 16 `must_complete`
items have a reachable path, after the import repair and the prefix fix.

⚠️ **AND THIS IS THE THIRD TIME TODAY THE SAME SUBSTITUTION PRODUCED A WRONG
SCOPE.** I reported "the critical path is not wider" — true of the 13 dead
routes, which was not what was asked. I then classified two hooks "redundant via
the generic complete route" — true of the route existing, which is not a path.
Both times I answered for the population I had measured rather than the thing in
question. This finding exists because the third version of the question —
*every* must_complete item, in *every* preset, against paths that something
actually calls — was finally the right one.

The manufacturing preset was the one I was working in. Nothing about the
measurement said it was a sample.

---

## The hooks: 7 dead, 1 must be repaired, 6 are deletable

A hook is dead when nothing calls it. 7 of the 12 in `onboarding_hooks.py` are.
The decision rule: does its item have a reachable path *by anything else*?

### REPAIR — not deletable (the `add_employees` class)

| hook | item | why |
|---|---|---|
| `on_manufacturer_linked` | `link_vault_supplier` (FH, must_complete) | **its item's only trigger.** Deleting it removes the last mechanism; wiring it is the repair. |

### DELETE — the hook completes nothing even if fired

Their item keys exist in **no preset**, so the `check_completion` call inside
them could never match a row:

| hook | item it checks | status of that key |
|---|---|---|
| `on_customer_created` | `add_first_customer` | in no preset |
| `on_price_list_updated` | `add_price_list` | in no preset |
| `on_scenario_completed` | — | **checks no key at all** |

### DELETE — redundant, the item already completes by a live path

| hook | item | the live path |
|---|---|---|
| `on_employee_created` | `add_employees` | frontend `completeChecklistItem("add_employees")` — reachable since the prefix fix |
| `on_integration_connected` | `connect_accounting` | `accounting_connection.py:474` |
| `on_product_created` | `add_products` | `tenant_onboarding.py:280` (the import route), `price_list_import.py:513`, `unified_import_service.py:1094` |

**Recommendation: delete all six.** A dead hook is a trap — the next reader takes
it for the mechanism and wires it alongside the live one, producing two
completion calls on a live write path. Annotating keeps the trap and adds a sign
next to it.

⚠️ **`on_employee_created` is only redundant BECAUSE of today's prefix fix.**
Before `fd410c43` it was the sole trigger for `add_employees` and belonged in the
repair column. Its classification changed within the session, which is the
argument for re-deriving this table rather than citing it later.

---

## What is NOT a defect

**Auto-completion as UX** — the checklist ticking itself when the user performs
the real action, instead of a page having to call the complete route — is a
product question. Five of the twelve hooks are wired exactly that way and work.
If that is wanted generally, it is one commit wiring the survivors deliberately,
with a break test each, not six repairs. It is not what any of the above asks
for.

---

## Method

- **A path counts only if something CALLS it.** Non-hook `check_completion` call
  sites in `app/`, plus hooks that have a real caller, plus frontend completions
  naming the key. The generic complete route is not a path on its own.
- **A real call is distinguished from a bare import.** `on_product_created` is
  imported at `production_log_service.py:145` under a comment reading "Fire
  onboarding hook" and never invoked.
- Frontend completions enumerated with quoted globs; exactly 6 keys are
  explicitly completed and there are no dynamic call sites other than the helper
  definition itself, so the set is closed.
- Controls reported before every result: 12 hooks parsed, 5 live, 15 non-hook
  keys, 6 frontend keys, 40 preset item keys across two presets.
