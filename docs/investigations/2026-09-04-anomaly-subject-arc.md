# The anomaly-subject arc — scope

> ## ⚠️ [CORRECTED 2026-09-04] — THIS DOCUMENT'S PREMISE IS WRONG
>
> **A subject does not prevent duplication. It makes supersede POSSIBLE;
> supersede is what makes it happen.**
>
> The arc reasoned from `expense_no_gl_mapping` — no subject, therefore 1,825
> duplicates — and generalised backwards to "subjects prevent duplication."
> Measured against production at phase 5's precondition probe: **192
> `expense_classification_failed` rows against ONE `vendor_bill_line`**, each
> carrying a real UUID subject, plus eight more colliding groups. **251
> unresolved subjected rows collapse to 11 decisions.** None of those rows was
> ever among the 34 this arc set out to fix.
>
> The 1,825 were conspicuous because they had nothing to key on, **not because
> they were the only case.** So phases 1–4 are precondition and not repair, which
> the phasing below already said and the framing above obscured: this document
> reads as though filling subjects were the fix.
>
> **Phase 5 is the fix.** See
> `2026-09-04-anomaly-subject-phase5-preconditions.md` §4.

**Date:** 2026-09-04 · **Scope document.** No code written.
**Status:** drafted for dispatch. Session 2 resumes after this lands.

Operator ruling: **shape 2** — require a subject at `add_anomaly`, so a
subjectless anomaly becomes *unexpressible* rather than discouraged. Item 5's
contract fix ships in the same commit as phase 1.

The argument is the criterion landed this morning (CLAUDE.md §11, *Removal
before recognition*): prefer removing the method over asking for care. Fixing one
writer leaves 44 sites able to reproduce the defect and relies on future authors
remembering. The signature change is the same move as deleting `instance_key`
rather than validating it, and as refusing `run`/`job`/`sweep` by name — the
parameter's absence at the call site becomes the enforcement, rather than a
convention someone must uphold.

That it cannot be done mechanically is a feature. Four agents have never had
anyone decide what their anomalies are about, and a mechanical fix would paper
that over with whatever field was nearest.

---

## 1. ⚠️ The phasing figure in the ruling does not reconcile — re-derived

> ## ⚠️ [CORRECTED 2026-09-04] — THE CALL-SITE FIGURES BELOW ARE WRONG
>
> **75 / 30 / 45 counted eleven `def _make_anomaly(` DEFINITIONS as call sites.**
> The grep was `'_make_anomaly(\|add_anomaly('`, which matches a definition line
> as readily as a call. Measured correctly: **64 call sites, 30 with a subject,
> 34 without.** 75 = 64 + 11; 45 = 34 + the same 11.
>
> Two conclusions drawn from the bad figures also fall:
> - **`ar_collections_agent` IS complete** — 3 sites, all compliant. Its "1
>   lacking" was its own definition. So "no agent is already complete" is false.
> - The phase split is **20 lacking across 7 partially-covered agents + 14 across
>   4 zero-coverage agents = 34**, not 27 + 18 = 45.
>
> Caught by `test_call_sites_are_actually_found` — a positive control written
> against the wrong number, which found the number wrong. Original text preserved.


The ruling proposed "the thirty already-passing sites first… then the forty-one
that pass nothing but have an obvious subject. Then the four agents needing a
ruling." Re-derived per agent:

| agent | call sites | with subject | lacking |
|---|---:|---:|---:|
| `year_end_close_agent` | 8 | 1 | 7 |
| `tax_package_agent` | 6 | **0** | 6 |
| `estimated_tax_prep_agent` | 5 | **0** | 5 |
| `month_end_close_agent` | 12 | 7 | 5 |
| `prep_1099_agent` | 7 | 2 | 5 |
| `budget_vs_actual_agent` | 4 | **0** | 4 |
| `annual_budget_agent` | 3 | **0** | 3 |
| `inventory_reconciliation_agent` | 10 | 7 | 3 |
| `cash_receipts_agent` | 6 | 4 | 2 |
| `expense_categorization_agent` | 4 | 2 | 2 |
| `unbilled_orders_agent` | 6 | 4 | 2 |
| `ar_collections_agent` | 4 | 3 | 1 |
| **total** | **75** | **30** | **45** |

**27 lacking sites sit in 8 partially-covered agents; 18 sit in 4
zero-coverage agents. 27 + 18 = 45.** The 41 does not appear in the data under
any grouping I can construct.

**And no agent is already complete.** All twelve have at least one gap, so "the
thirty already-passing sites" is not a phase — those thirty are scattered across
the same twelve files the other forty-five live in. The mechanical unit is the
*signature change*, not a set of files.

Recording this rather than adopting the figure, per the ruling's own point that
the do-not-inherit line does real work.

---

## 2. Phases

### Phase 1 — the signature, and item 5. One commit.

**The signature change.** `entity_type` and `entity_id` become required on
`BaseAgent.add_anomaly` / `_make_anomaly`. A call site omitting either fails
loudly rather than writing a subjectless row.

> ### ⚠️ BREAKING 45 CALL SITES IS THE MECHANISM, NOT THE COST
>
> The next reader will see a commit that breaks 45 sites and reach for a default
> parameter. **Do not.** No default, no nullable escape, no
> `subject_optional=True`, no "temporary" permissive mode.
>
> Every one of those restores a hole with a guard on it, which is precisely the
> shape CLAUDE.md §11 *Removal before recognition* rejects — and the shape this
> project keeps re-learning. The whole value of the change is that a call site
> omitting a subject **cannot be written**, not that it is discouraged.
>
> If the breakage feels like too much to walk, that is a measurement of how far
> the defect spread, not an argument for softening the fix.

**Item 5's contract fix, same commit.** In `emit_for_user`, when a condition
returns instances and *every one* is rejected at validation, log at ERROR naming
the fragment. That is the only point where a permanently-broken fragment and a
legitimately-quiet one are distinguishable — registration cannot detect it
without executing the condition, and the current per-instance `logger.exception`
does not distinguish "one bad instance" from "this fragment has never once
emitted."

Higher-value than the signature change, because session 2 declares four more
fragments into that hole.

**Positive control required on both.** A signature that rejects everything and a
signature that rejects nothing pass the same "it raised" test. And an ERROR log
that never fires is indistinguishable from one that cannot.

### Phase 2 — the 27 lacking sites in 8 partially-covered agents

These agents already pass a subject somewhere, so the subject vocabulary for the
agent is established and each lacking site can be answered against its own
siblings. Per-site, not per-agent — a sibling passing `invoice_id` does not mean
this site's subject is an invoice.

### Phase 3 — the 18 sites in 4 zero-coverage agents, as a batch of Type B calls

`tax_package` (6), `estimated_tax_prep` (5), `budget_vs_actual` (4),
`annual_budget` (3). Nothing in these files establishes what their anomalies are
about; there is no sibling to answer against.

⚠️ **Surface all four as one batch, not one at a time.** They are the same
question asked four times — "what is this anomaly about?" — and answering them
together is how the answers stay consistent. Answering them serially invites
four different framings.

Expect some to have no good subject at all. An anomaly about "the budget as a
whole" may be legitimately tenant-scoped, in which case the subject is the
period or the budget, and that is a real answer rather than a failure.

### Phase 4 — the three unlocated types, by enumeration

`uncategorized_expense`, `invoice_severely_overdue`, `invoice_overdue` exist as
unresolved production rows with **no literal occurrence anywhere under `app/`**.

⚠️ **This stays a failed lookup, not an absence, until enumeration resolves it.**
A constructed type name — an f-string, a mapping, a variable — evades a literal
search entirely. Resolve by enumerating what actually writes to
`agent_anomalies` (call graph into `add_anomaly`, which phase 1's signature
change makes tractable), not by searching harder for the string.

### Phase 5 — supersede. Inside this arc, not the arc that follows.

DECISIONS 2026-09-01 makes supersede a condition of shipping **any**
anomaly-writing fix. This arc rewrites every anomaly write site in the codebase.
If supersede lands as a separate arc, there is a window in which 75 sites carry
subjects and still duplicate — **the current defect with better metadata, and a
window that looks like progress.** That is the failure mode to avoid, so
supersede is phase 5 of this arc.

Keyed on the subject phases 1–4 establish, matching the entry's named shape
`(provenance_kind, provenance_ref_type, provenance_ref_id, event_kind)` — or the
nearest equivalent `agent_anomalies` can carry, which is itself a STOP if it
does not transfer.

⚠️ **WHY PHASES 1–4 ARE NOT FOUR VIOLATIONS OF THAT CANON RULE.** A future reader
will see four phases touching anomaly write sites without supersede and read
them as the rule being broken four times. They are not: phases 1–4 ship **no
behavioural fix to production**. They change a signature, fill in subjects, and
enumerate writers — establishing the precondition the entry's prescribed fix
requires and which the preliminary found missing. **Phase 5 is where the pass
actually completes.** The entry says supersede ships in the same pass; this arc
is the pass.

---

## 2a. Two findings from phase 1 that change how the rest is read

### A positive control's value is not bounded by what it was written to catch

`test_call_sites_are_actually_found` was written to check one thing: that the
scanner matches *anything*, since a scanner finding nothing satisfies a ratchet
trivially. It caught something it was not looking for — that the arc's 75/30/45
figures were wrong — because it was **the only thing in the pipeline touching the
actual population rather than a description of it.**

The audit described the population. The arc scope inherited the description. The
ruling reasoned over the inherited description. Three documents, one unexamined
measurement. The control ran against the files.

That generalises: a control is worth writing even when the thing it checks seems
too obvious to fail, because its real function is contact with reality, and
contact catches more than the assertion names.

### The mechanism: a definition and a call look identical to a text search

`grep '_make_anomaly(\|add_anomaly('` matched eleven `def _make_anomaly(` lines
as readily as it matched calls. This is the false-presence-from-substring shape
(CLAUDE.md §11) with one difference that explains its survival: **the substring
was syntactically legitimate.** A search for `"ring"` matching `spring_burial`
looks wrong the moment anyone reads the match. A search for `_make_anomaly(`
matching its own definition looks *correct* — the text is genuinely there, in a
genuinely relevant context, and every match is a true match of the pattern.

The pattern was right and the population was wrong. That is why it survived three
documents and a ruling, and why the fix is not a better regex but a control that
touches the files.

Correct form when counting call sites: match `self._make_anomaly(` /
`self.add_anomaly(` and exclude `def `-prefixed lines explicitly, or parse rather
than grep.

---

## 3. The census this arc must produce, and its one binding constraint

⚠️ **Per-row, never per-type.** `payment_unmatched_recent` carries a subject on
**2 of 3** unresolved rows and on **204 of 204** resolved ones. Any per-type
summary — including the one the ruling would have asked for — reports that type
as covered. Partial coverage within a type means "does this type carry subjects"
has no answer; only rows have answers.

This is the same defect as the `LIMIT 6` claim in the preliminary, one level up:
a summary that aggregates away the variation reports the majority and hides the
exception.

---

## 4. Out of scope, explicitly

- **The 1,825 orphans.** No subject, cannot be retroactively subjected from the
  rows themselves. Deletion destroys the only record the classifier ran;
  marking them superseded-without-subject preserves it. Operator's call, and not
  this arc's.
- **The `*/15` cron.** Whether the cadence is right is a separate question from
  whether the writer is correct. It is also the multiplier behind the 11,930
  `workflow_runs` in `awaiting_input`, so it deserves its own look rather than a
  side-effect fix.
**Supersede is NO LONGER out of scope** — it is phase 5, per the ruling. See §2.
Recorded here because an earlier draft of this document listed it as out of
scope, and a reader arriving at that draft's framing would conclude the arc
violates the 2026-09-01 entry.

---

## 5. STOP lines for the dispatch

- Any of the four zero-coverage agents where no subject is defensible even after
  deliberation.
- Any place the required signature cannot be satisfied without inventing a
  subject — inventing one is worse than stopping.
- Any call site whose subject differs from what its siblings pass, since that
  suggests the agent's vocabulary is not what phase 2 assumes.
- Any finding that the 2026-09-01 supersede entry's prescribed key shape does not
  transfer to `agent_anomalies` once a subject exists.

---

## 6. Estimate

**4–5 sessions, or 6 if phase 3 goes wide.** Phase 5 (supersede) adds one to the
earlier 3–4. The uncertainty is concentrated in phase 3.

Phase 1 is one session: a signature change, 45 mechanical failures to walk, item
5, and their positive controls. Phase 2 is one session if the sibling vocabulary
holds and two if it does not. Phase 3 is a decision session plus the edits, and
its length depends on how many of the four have a defensible subject.

⚠️ **The estimate assumes phase 2's siblings answer.** If the 27 turn out to need
rulings too, this is phase 3 with a larger batch and the estimate is 6. That is
measurable at the start of phase 2 by taking the agent with the most lacking
sites that still has coverage — `year_end_close`, 7 lacking against 1 covered —
and seeing whether one covered site is enough to answer seven.
