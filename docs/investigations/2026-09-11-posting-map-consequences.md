# The three consequences of the suggestion ruling, taken back through

**Date:** 2026-09-11 · **HEAD:** `d0ea486a` · **Read-only. No code changed.**

Follows the cardinality STOP. The ruling: there is no mapping, only a
**suggestion** — the system proposes an account, a person posts the line.

---

## 1. The fragment's end transition — confirmed wrong, and so is its subject

`expense_posting_map` as landed:

```
kind="prompt"          subject_kind="expense_category"
target_surface="focus" target_key="expense_posting_map"
end_transition: entity_kind="expense_category"
                resolved_when="category_posting_account_recorded"
                outcomes=(Outcome("recorded", "…recorded N category posting account(s)"))
```

All four of those encode the mapping model. Under the ruling **nothing records
a posting account**, so `resolved_when` names an event that will never occur and
the `recorded` outcome describes an act nobody performs.

The subject moves from the category to the bill line, and the arc's own test is
what forces it: *one act clears it.* Posting the line clears it. Writing a
mapping for the category clears nothing, because the category does not determine
the account — which is §0's measurement, not a preference.

⚠️ **This reverses the anomaly arc's subject ruling for this fragment only, and
the reason is specific rather than general.** The arc ruled the subject is the
thing one act clears. For `collections_outstanding` that is the customer. Here
the category fails the same test that the customer passes.

---

## 2. The anomaly's subject — and §4's premise does not hold

### The figures, re-derived

`expense_no_gl_mapping`: **open 1 · superseded 1,824 · resolved 0 · total 1,825.**

⚠️ **My first probe reported 1,825 open.** It filtered on `resolved is not true`
and ignored `superseded_at`. `AgentAnomaly.open_filter()` is
`resolved IS FALSE AND superseded_at IS NULL`, and its docstring says in capitals
to use it rather than a bare `resolved` filter — there is even a scanner test,
`test_no_read_site_filters_on_resolved_alone`, enforcing it at read sites. I
reproduced the exact defect that scanner exists to prevent, in an ad-hoc probe
where the scanner does not reach. STATE's figure was right and mine was wrong.

### ⚠️ The open row has NO SUBJECT

```
entity_type = NULL
entity_id   = NULL
created     2026-08-31
description "Category 'vehicle_expense' has no GL account mapping…"
```

All 1,824 superseded rows are the same: `entity_type` and `entity_id` NULL.

The current code DOES set them — `expense_categorization_agent.py:398` passes
`entity_type="expense_category", entity_id=proposed_category`, and
`base_agent._make_anomaly` carries them through. The open row predates that: it
was written 2026-08-31, and the anomaly-subject arc landed 2026-09-08.

**So §4's instruction — "establish that it resolves when the mapping is
written" — cannot be satisfied.** The row has no structural link to
`vehicle_expense`. The category appears *only in the description prose*, and
resolving it by reading that prose is the move this project has rejected three
times. It can be superseded by a correctly-subjected successor, or closed by
hand. It cannot be resolved by subject, because it has none.

### Per-line versus per-category

Under the ruling a **per-category subject is permanently unresolvable**: there is
no mapping to write, so nothing ever clears "category X has no account." An
anomaly that can never clear is worse than the one the supersede arc fixed —
that one duplicated, this one would simply never close.

**Per-line passes.** One act — posting the line — clears it.

**Volume, measured:** production holds **10 vendor bill lines** in total; 8 carry
a NULL `expense_category` and 2 carry the literal string `nonexistent_category`.
**Zero lines carry a real classifier category.** So per-line is not a flood
today; it is nearly nothing.

⚠️ And a loose end: the open anomaly names `vehicle_expense`, which **no current
bill line carries**. Whatever it was raised against is not in
`vendor_bill_lines` now.

---

## 3. Nothing auto-posts — stated as the ruling it is

Recorded here so it is a product decision rather than a property of the
implementation. `approve_line` in the expense adapter is the human-approval path;
the agents run dry-run by default with `guard_write()` refusing writes. Nothing
found that posts a line without a person. **The ruling makes that permanent
rather than incidental**, and it is the reason the suggestion can improve
(last account used for this vendor and category, ranked first) without ever
becoming authoritative.

---

## 4. What the build needs before it starts

1. **The fragment's four declarations are rewritten**, not adjusted — subject,
   `resolved_when`, `entity_kind` and the outcome all encode the mapping model.
2. **A decision on the existing open anomaly**: supersede it with a
   correctly-subjected successor, or close it by hand. It cannot resolve itself.
3. **A decision on whether `expense_no_gl_mapping` is renamed.** Its text says
   "Add a mapping in Settings → GL Accounts", which points at the COA surface
   answering the inverse question, and under the ruling there is no mapping to
   add anywhere.
4. ⚠️ **There is no production data to build against.** Ten bill lines, none
   with a real category. Any surface built now is tested against fixtures only,
   and "run the repaired path" has nothing real to run on.

---

## 5. Method notes

- The 1,825-vs-1 error is recorded above rather than corrected silently. It is
  the first thing this investigation produced and it was wrong.
- The fragment declaration was read from the registry source, not from the
  arc doc describing it.
- One statement per connection; production read through a connection-level
  read-only guard.
