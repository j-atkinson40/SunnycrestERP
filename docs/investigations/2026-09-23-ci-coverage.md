# What CI covers, what it cannot see, and one thing I could not reconcile

**2026-09-23.** Read-only. No CI changes. Settles an inference I recorded yesterday as
inference, and measures what the CI gate actually selects.

**Headline: my inference was REFUTED by measurement — and the measurement that refuted it
turned up something larger. Zero of the 25 currently-failing test files are in the CI
manifest.**

---

## 1. The inference, refuted

Yesterday I recorded, explicitly as inference rather than measurement, that the nine
completeness tests were "almost certainly failing in CI as well" and were probably part of
the 30-run red streak.

The newest pre-fix CI run — `35747156571`, commit `aee39780`, 2026-09-22T15:24Z — reports:

```
2333 passed, 28 skipped, 218 warnings, 1 error in 668.05s
```

**Zero failures.** The single error is
`test_note_session2_fragments::test_a_measured_span_may_be_unlinked_but_never_unsourced`,
a teardown `BaseExceptionGroup`, and it is what makes `Run scoped test gate` exit 1.

So the nine were not failing in CI, and they are not part of the streak. **The inference was
wrong and is withdrawn.**

⚠️ **Worth noting what the backend gate's red actually is: ONE teardown error.** Not
TypeScript — that is the separate Frontend CI job. The backend half of CI is 2333 passing
tests and a single error.

## 2. ⚠️ And I cannot reconcile that with the local measurement

Both files are in the manifest at that commit (`ci_gate.txt:292` and `:294`, verified
against `git show aee39780:backend/tests/ci_gate.txt`), and the manifest is byte-identical
today — 169 entries then and now.

Both the bound and the literal predate the run by six weeks: `_tenant_start` and
`date(2026, 8, 13)` both entered on 2026-08-13 (`a2013fce`).

`ensure_company` creates the tenant with `created_at` defaulted in Python to
`datetime.now(timezone.utc)`, so CI's testco is minutes old.

And the mechanism reproduces locally under exactly the scope CI uses. With the fix reverted
and a tenant created today, those two files **alone**:

```
9 failed, 78 passed
```

Not order-coupling — the same nine, in isolation, in a 2-file run.

**So CI should have failed and did not.** I could not establish why from the logs.

The candidate worth one check by someone with CI access: `_tenant_start` returns `None` when
no `companies` row is found, and a `None` start cannot bound anything — if CI's review saw
`began is None`, every period is due and all nine pass. That would mean the fixture's row is
not visible to the service's session at review time in CI. **Stated as the next thing to
test, not as a finding.**

⚠️ I am recording this as an open discrepancy rather than picking whichever explanation fits.
The fix is correct either way — it was verified against the failure it addresses and
break-tested — but the reason CI behaved differently is not established, and a plausible
explanation is still a claim about the world.

## 3. What the CI gate actually selects

```
tests/ci_gate.txt        169 entries
backend/tests/test_*.py  446 files
coverage                 38%
```

`ci.yml:92` runs `python -m pytest $(grep -vE '^\s*#|^\s*$' tests/ci_gate.txt | tr '\n' ' ') -q`.
The file carries no header explaining its selection criteria; membership is a list, not a
rule. Its last change was `50c71d34`, 2026-09-09.

⚠️ **AND HERE IS THE FINDING THAT MATTERS MORE THAN THE ONE I SET OUT TO SETTLE.**

Of the 41 failures in today's full-tree run, spread across **25 distinct files**:

```
in the CI manifest:   0
outside it:          25
```

Every currently-failing file is outside the gate. `test_admin_portal`,
`test_anomalies_widget`, `test_plaid_b2`, `test_vertical_inventory`,
`test_workflow_scope_phase8a`, `test_vault_v1e_accounting` and nineteen others.

That is not a coincidence about which tests are broken — it is what a curated manifest
converges to when it is maintained by adding what passes. CLAUDE.md §11's *a gate reports its
denominator* names the mechanism: "a gate that SELECTS rather than COVERS can be satisfied by
adding files to the manifest, and it can be silently narrowed by files never being added.
Neither movement appears in the number."

Here the number is 2333 passing and one error, and the 41 are invisible to it.

## 4. The sequenced plan — recorded, not executed

CI has been red for 30 consecutive runs. Adding seeds now would surface a new set of failures
into a channel already failing for an unrelated cause, and nobody could separate them. The
order matters more than any individual step.

**Step 1 — get CI green.** Two independent items:
- *Frontend CI*: three TypeScript errors (`TS2322` ×2 in test files, `TS6133` in
  `preview-data.tsx`). Ordinary in-repo work, no credentials, no dashboard.
- *Backend CI*: one teardown error in `test_note_session2_fragments`.

  **Cost:** small and bounded. **Buys:** a channel whose red means something, which every
  later step depends on.

**Step 2 — seed CI.** One step in `ci.yml` between migrations and pytest running
`scripts/seed_dev.sh`, ~12s.

  **Cost:** 12s per run, plus a batch of newly-visible failures. **Buys:** the suite starts
  testing against the database shape deploys actually produce. This is what would have caught
  the `tax_jurisdictions` class.

  ⚠️ **Expect failures and read them the way the 54→41 progression was read** — each one
  accounted for individually, none treated as a regression against a number measured under
  different conditions.

**Step 3 — widen the manifest, or state its denominator.** §3 shows the gate currently
selects a set that excludes every known failure. Either it grows toward the tree, or every
report of it says "169 of 446" so the gap stays visible.

  **Cost:** growing it surfaces the 41 into CI. **Buys:** the gate's green stops being
  compatible with 41 failures.

⚠️ **Steps 2 and 3 both make CI redder before they make it better.** That is the correct
direction and it only works if step 1 lands first, because a red channel cannot report a new
red.

## 5. What this does not establish

- Why CI passed the completeness tests. §2.
- What the other 29 red CI runs consist of. Only the newest was read.
- Whether `ci_gate.txt` has a selection rule that lives somewhere other than the file.
