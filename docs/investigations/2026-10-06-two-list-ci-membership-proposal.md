# The two-list CI membership check — evaluation

**2026-10-06. PROPOSAL ONLY — nothing built.** Origin: James's dispatch of 2026-10-06.
Widening CI itself stays **parked** (STATE, 2026-10-06).

---

## ⚠️ CORRECTED 2026-10-06 — EVERY "284" BELOW IS WRONG; THE REAL FIGURE IS 297

This document was written with **284** excluded files, from **461** total. Both came
from `ls tests/test_*.py` — a glob meaning TOP LEVEL ONLY, which misses the **13** test
files under `tests/tasks/`, **none** of which is in the gate.

    derived with rglob:   474 test files
                          177 in ci_gate.txt
                          297 outside          <- the ceiling that was built

The original figures are left in the body rather than edited out, because the error is
the document's most useful content: it is CLAUDE.md §11's constructed-enumeration
failure committed inside a proposal about enumerating test files, and it was caught only
by `find -mindepth 2` while building the thing. The shipped
`tests/test_ci_membership.py` uses `rglob` and carries a dedicated control asserting a
NESTED file is discovered, specifically so this cannot recur silently.

---

## Verdict

**Build it, with one amendment: the exclusion list must be a RATCHET, not a register.**
Without that it reproduces the defect it is built to catch, one layer out.

---

## 1. Does an existing mechanism already do this? No — and the gap has been noticed three times

Measured today. Every reference to `ci_gate.txt` under `backend/tests/` is **prose**.
No assertion, no file read, no membership check:

| file | line | what it says |
|---|---|---|
| `tests/conftest.py` | 32 | corrects an earlier false claim that CI doesn't run pytest |
| `tests/test_phase_8_9_agents.py` | 83 | *"The file was not in ci_gate.txt"* |
| `tests/test_income_statement_a3.py` | 441 | *"was not in ci_gate.txt"* |
| `tests/test_suite_jobs_beat_rewrites.py` | 11 | *"is not in `ci_gate.txt`"* |

⚠️ **Three separate authors hit the gap, and all three wrote a comment instead of a
check.** That is the argument for the proposal stated better than I could state it: the
need has been felt repeatedly and never mechanised, because noticing it was never
anybody's task — it was always a remark made while doing something else. §11's *"a rule
that is read and violated is placed wrong, not worded wrong"* applies to the absent
rule too.

There are nine `*_ratchet.py` files in `tests/`, so the ratchet pattern this needs is
already idiomatic here. None of them covers manifest membership.

---

## 2. Does it fit "make the channel trustworthy", or conflict with §11's ordering?

**It fits, and it occupies the EARLIEST slot in that ordering rather than a later one.**

§11's entry *"a manifest maintained by adding what passes converges on covering only
what passes"* names the untrustworthy property precisely, and it is not the manifest's
size:

> A file is added when it passes; a file that fails is left out until someone fixes it,
> and nobody does, because the gate is green.

**Membership is decided by results.** That is the defect. The two-list check attacks
exactly that: a new file can no longer *default* to outside the channel. Someone has to
choose, in a diff, where it goes.

And it does not touch the thing §11 warns against:

| §11's warning | this proposal |
|---|---|
| "widening surfaces every known failure at once" | runs **no** excluded test |
| "into a channel that may already be red" | adds one check that is green on day one |
| "read what breaks with each item accounted for" | breaks nothing |

So it is **not** widening-by-another-name, and it is **not** a substitute for widening.
It is the step that makes widening decidable later: when the park's trigger fires,
whoever reopens it reads a list of 284 named files instead of deriving a set difference
and hoping the derivation is right.

⚠️ **One way it could conflict, and the amendment that prevents it.** An exclusion list
*maintained by adding whatever fails* is the original defect wearing different clothes —
"a manifest maintained by adding what passes" becomes "an exclusion list maintained by
adding what fails", the check stays green forever, and the list grows. Nothing in the
check as described stops that.

**So the exclusion list needs a one-way ratchet on its length**, which is §11's own
remedy (*"ENFORCE DIRECTION — a ratchet: the non-compliant count may only shrink"*).
The check then has pressure in it rather than only bookkeeping.

---

## 3. What it would cost

**To build**

- One file, `tests/ci_excluded.txt`, 284 entries, generated once from
  `set(test_*.py) - set(ci_gate.txt)`.
- One test file, ~40 lines, with **two positive controls** (§4 below).
- One line added to `ci_gate.txt` so the new check actually runs. ⚠️ Omitting this is
  the obvious way to ship a check that never executes.

**Ongoing**

- ⚠️ **Every new test file now requires a decision in the diff.** That is the entire
  point and it is also friction, felt by whoever is adding a test in a hurry. Stated
  rather than minimised.
- Moving or renaming a test file breaks the check until both lists are updated. Minor,
  real, and loud rather than silent — which is the right direction.
- Deleting a test file must fail too, or the exclusion list rots. `ci_gate.txt`
  currently has **0** stale entries (measured), so the same staleness assertion should
  bind both lists.

**What it does NOT cost**

- No CI time beyond one file-system walk.
- No change to what runs. 177 files before, 177 after.

---

## 4. The check, as I would build it

```
test_every_backend_test_file_is_classified
    discovered = {p.name for p in (BACKEND/"tests").glob("test_*.py")}
    gate       = entries of ci_gate.txt
    excluded   = entries of ci_excluded.txt

    assert discovered - (gate | excluded) == set()     # unclassified -> FAIL
    assert gate & excluded == set()                    # double-listed -> FAIL
    assert (gate | excluded) - discovered == set()     # stale in either -> FAIL

test_the_enumerator_can_see                 # CONTROL A
    assert len(discovered) >= 400
    assert "test_map_accounting_content_r157.py" in discovered

test_the_exclusion_list_only_shrinks        # CONTROL B — the ratchet
    CEILING = 284        # 2026-10-06. Lower this. Never raise it.
    assert len(excluded) <= CEILING
    assert CEILING - len(excluded) <= 0 or ...   # see note
```

⚠️ **Both controls are required and they test different failures.** §11: *a ratchet
needs two positive controls, not one.*

- **Control A — the enumerator can SEE.** A glob that matches nothing satisfies
  `discovered - (gate|excluded) == set()` trivially and the whole check passes while
  measuring an empty set. This is the shape that made `find` over a symlink return zero.
- **Control B — the ceiling is TIGHT.** A ceiling above the real count has stopped
  ratcheting and rejects nothing. At 284 against a real 284, adding one exclusion
  fails — which is the behaviour being bought.

⚠️ **And the ratchet must be break-tested on landing**, per §11's remedy: add a
throwaway test file, confirm the classification test goes red *specifically*, and
report the control that proved the break landed.

---

## 5. Two alternatives considered and rejected

**(a) No second list — derive the excluded set and ratchet only its count.** One file
fewer, nothing to drift. **Rejected:** a new test file would silently consume headroom
freed by someone fixing a different file, so the count could stay at 284 forever while
membership churned. It also loses the thing the dispatch is actually buying — *"nobody
chooses that"* becomes false only when the choice is a named line in a diff.

**(b) Require a reason per exclusion, like the quarantine discipline.** Tempting,
because that is what §11's `quarantined` disposition demands. **Rejected for now:** 284
reasons written in one sitting would be fabricated, and a file of invented reasons is
worse than a file of names — it reads as deliberate. ⚠️ **Reasons become the right ask
once the list is small enough that they would be real**, and that is the natural
follow-up when the park reopens.

---

## 6. What this does not claim

- It does not make the 284 files green, or measured, or safe.
- It does not reduce the 41 known failures outside the manifest.
- It does not make "gate green" a complete sentence — §11's denominator rule still
  binds every report.

It makes **one** thing true that is false today: a test file cannot land outside CI by
default. That is smaller than widening and is a precondition for it.
