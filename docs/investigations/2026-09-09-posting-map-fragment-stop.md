# Posting-map fragment — the subject holds, the CONDITION produces 15 permanent prompts

**Date:** 2026-09-09 · **Read-only.** No fragment declared, no code written.
Session 2 stopped at its first deliverable, before four more fragments were built
on the same assumption.

---

## 1. The subject IS the category. The dispatch's assumption survives.

Applying the arc's rule — *what, when done, makes it go away* — to a candidate
subject of "the tenant's posting map as a whole": filling `payroll` and filling
`rent` are **separate decisions with separate answers**, so one subject holding
both trips the TOO COARSE guard. Per-category is the level at which one act
resolves one instance.

Checked for the opposite error too. Nothing finer exists — a category needs one
account, not several — and no single act resolves multiple categories, because
each is a distinct choice about a distinct account.

**Subject: `expense_category` / the platform category.** Which is the same
subject kind the anomaly-subject arc landed for `expense_no_gl_mapping`, so the
two agree rather than merely coexisting.

---

## 2. ⚠️ But the CONDITION as dispatched is permanently true and unresolvable

> *"The tenant has classifier categories with no GL account to post to."*

Measured, that is true of **15 of 15** categories, for every tenant, **and will
remain true indefinitely** — because the surface that would record a
type → account decision does not exist. Enumerated, not assumed: the only table
matching `%gl_map%` / `%posting%` / `%category_account%` is
`tenant_gl_mappings`, which answers account → type.

Prompts render whenever their condition holds (§1 of the dispatch, correctly —
a pending decision is always worth saying). So this condition emits **15 prompts
on day one, every day, none of which can be resolved by any act available to the
operator.**

⚠️ **That is the `w9_tracking_not_implemented` shape**, which this arc already
ruled on: no operator act means no end transition, and the anomaly-subject arc
held two such sites open rather than inventing subjects for them. Fifteen
permanent unresolvable prompts is the precise failure the note surface exists to
prevent, arriving through its first prompt.

---

## 3. What the data actually says — every bound declared

| measurement | `WHERE` | result |
|---|---|---|
| classifier vocabulary | read from source, not inherited | **15** |
| distinct categories ever assigned | `vendor_bill_lines.expense_category IS NOT NULL`, no LIMIT | **1** — and it is `nonexistent_category`, on 2 lines |
| vendor bill lines, total | none | **10** (2 categorized) |
| open `expense_no_gl_mapping` | `resolved=false AND superseded_at IS NULL` | **1** |
| type → account surfaces | `information_schema`, three name patterns | **0** |
| child values in `tenant_gl_mappings` | across all tenants | **1** (`other_expense`, both a child and a parent) |

⚠️ **Counts over `agent_anomalies` include the five seeded demo rows; none of the
five is `expense_no_gl_mapping`.**

⚠️ **The one open row carries `entity_type = NULL, entity_id = NULL`** — it was
written 2026-08-31, before phases 2–3 gave that site a subject. It names
`vehicle_expense` in prose only. So a condition reading subjects off existing
anomalies would find nothing to key on.

**And `expense_categorization` runs `dry_run=False` 11,298 times** yet production
holds ten bill lines, two categorized, with a category that is not in the
vocabulary. **There is essentially no expense data here.** A fragment ranging
over configuration completeness would be the only thing in the note that ever
spoke.

---

## 4. The grounded alternative — same subject, different condition

Condition: **a bill line the classifier categorized cannot post, because its
category has no account.** Grounded in blocked work rather than in configuration
completeness.

- **Subject unchanged**: the platform category.
- **Instances today: zero.** Correct, and the composition gate's own thesis — a
  quiet day produces an empty region.
- **It emits when something is actually blocked**, which is when the decision is
  worth asking for, and it resolves when that category gets an account.
- It does not ask an operator to make fourteen decisions they have not been
  blocked by.

⚠️ **This changes what the session's proof demonstrates.** The dispatch chose
this fragment as proof that the contract and the gate produce *something real
rather than something demonstrable*. Under the grounded condition it produces
**nothing today** — which is a truthful demonstration of the gate and a weak
demonstration of the contract.

**That trade is James's, not mine.** Either:

1. **Grounded condition** — honest, gate-respecting, emits zero today, and the
   session needs a different fragment as its worked example; or
2. **Configuration condition** — emits 15 immediately, demonstrates the pipeline
   end to end, and ships fifteen prompts nobody can resolve until the
   posting-map surface exists. If chosen, it should be a NON-PROMPT, since a
   prompt with no available end transition contradicts the contract.

---

## 5. What did NOT change, and what I did not do

- **Unmapped categories keep refusing to post.** Nothing here touches posting.
- **No fragment declared, no registry entry, no gate implemented.** Stopping
  before the worked example is declared is the point — four more fragments on
  this assumption is the cost the STOP avoids.
- **The posting-map surface prompt is not emitted here** either; what it should
  target depends on which condition is chosen.
- Read-only against production throughout.
