"""Every backend test file is in exactly one of two lists.

⚠️ WHAT THIS BUYS, AND IT IS ONE THING: a test file cannot land outside CI by
DEFAULT. Before 2026-10-06 it could, and nothing recorded it. Three separate test
files each carry a comment remarking "was not in ci_gate.txt" —
`test_phase_8_9_agents.py:83`, `test_income_statement_a3.py:441`,
`test_suite_jobs_beat_rewrites.py:11`. Three authors hit the gap and all three wrote
prose, because noticing it was never anybody's task.

⚠️ WHAT IT DOES NOT BUY. It runs no excluded test, makes none of them green, and
surfaces none of the 41 known failures outside the manifest. Widening the gate is
PARKED (STATE 2026-10-06) with a declared trigger. This is the step that makes
widening DECIDABLE later — when the park reopens, whoever reopens it reads 297 named
files instead of re-deriving a set difference and trusting the derivation.

⚠️ AND THE DERIVATION IS EXACTLY WHAT WENT WRONG GETTING HERE. The ceiling was
proposed as 284, from `ls tests/test_*.py` — a glob that silently encodes "top level
only" and misses the 13 files under `tests/tasks/`. The real population is 474 and the
real exclusion count is 297. That is CLAUDE.md §11's constructed-name failure at the
enumeration layer, and it is why `test_the_enumerator_sees_a_nested_file` below exists
as its own control rather than being folded into a count assertion.

THE THREE THINGS ASSERTED:

1. PARTITION — every discovered file is in exactly one list; neither list holds a
   path that does not exist.
2. THE RATCHET — the exclusion list's length has an EXACT ceiling. Growing it fails.
   Shrinking it means lowering `_EXCLUDED_CEILING` in the same diff.
3. TWO POSITIVE CONTROLS — §11: *a ratchet needs two positive controls, not one.*
   One proves the enumerator can SEE (including into subdirectories); one proves the
   ceiling is TIGHT. An enumerator that matches nothing satisfies the partition
   assertion trivially, and a ceiling above the real count has stopped ratcheting.
"""
from __future__ import annotations

from pathlib import Path

TESTS = Path(__file__).resolve().parent
GATE = TESTS / "ci_gate.txt"
EXCLUDED = TESTS / "ci_excluded.txt"

#: ⚠️ EXACT, NOT A FLOOR. Measured 2026-10-06 as
#: len(set(tests/**/test_*.py) - set(ci_gate.txt)) with this file in the gate.
#: LOWER THIS when a file moves into the gate. NEVER RAISE IT — raising it is how a
#: ratchet stops ratcheting, and the growth would then be invisible in the number.
_EXCLUDED_CEILING = 291

#: A top-level file and a NESTED one. The nested entry is the control on the
#: enumeration bug described in the module docstring: a top-level-only glob finds the
#: first and misses the second, and every count built on it is wrong by 13.
_KNOWN_PRESENT = (
    "tests/test_map_accounting_content_r157.py",
    "tests/tasks/test_substrate_schema.py",
)


def _entries(path: Path) -> list[str]:
    """Non-comment, non-blank lines — the same filter `ci.yml` applies.

    ⚠️ A list, not a set, so `test_neither_list_has_duplicates` can see repeats. A
    set here would silently absorb them and the partition would still pass.
    """
    return [
        line.strip()
        for line in path.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _discovered() -> set[str]:
    """⚠️ rglob, NOT glob. See the module docstring — glob misses `tests/tasks/`."""
    return {
        str(p.relative_to(TESTS.parent)) for p in TESTS.rglob("test_*.py")
    }


# ---------------------------------------------------------------------------
# The controls come FIRST, deliberately. §11: require the control to be non-zero
# and read that number before the result it is vouching for.
# ---------------------------------------------------------------------------

def test_the_enumerator_sees_a_nested_file():
    """⚠️ CONTROL A. A glob matching nothing — or matching only the top level —
    satisfies the partition assertion trivially, because an empty or short
    `discovered` set has nothing left over to be unclassified.

    Both entries are asserted individually so a failure names WHICH one is missing:
    losing the nested file is the specific regression that produced the wrong
    ceiling.
    """
    found = _discovered()
    assert len(found) >= 400, (
        f"the enumerator found only {len(found)} test files — it is not seeing the "
        f"tree, and every assertion below is vacuous"
    )
    for known in _KNOWN_PRESENT:
        assert known in found, (
            f"{known} was not discovered. If this is a nested path, the enumeration "
            f"has regressed to a top-level-only glob — the exact bug that made the "
            f"ceiling 284 instead of 297."
        )


def test_the_ceiling_is_tight():
    """⚠️ CONTROL B. A ceiling ABOVE the real count has stopped ratcheting and
    rejects nothing. This asserts equality, so the ceiling cannot drift upward from
    the population it is supposed to constrain.

    When a file moves into the gate, this fails until `_EXCLUDED_CEILING` is lowered
    in the same diff — which is the whole mechanism.
    """
    n = len(_entries(EXCLUDED))
    assert n == _EXCLUDED_CEILING, (
        f"the exclusion list holds {n} entries against a ceiling of "
        f"{_EXCLUDED_CEILING}. If you ADDED a file, that is the ratchet refusing: "
        f"put it in ci_gate.txt instead, or argue for the exclusion and lower "
        f"nothing. If you MOVED a file into the gate, lower the ceiling here."
    )


# ---------------------------------------------------------------------------
# The partition
# ---------------------------------------------------------------------------

def test_every_backend_test_file_is_classified():
    """The claim. A new test file fails here until someone chooses."""
    unclassified = _discovered() - (set(_entries(GATE)) | set(_entries(EXCLUDED)))
    assert unclassified == set(), (
        "these test files are in neither ci_gate.txt nor ci_excluded.txt, so they "
        "landed outside CI without anyone choosing that:\n  "
        + "\n  ".join(sorted(unclassified))
    )


def test_no_file_is_in_both_lists():
    """Double-listed means the gate runs it AND the record says it is excluded."""
    both = set(_entries(GATE)) & set(_entries(EXCLUDED))
    assert both == set(), f"listed twice: {sorted(both)}"


def test_neither_list_holds_a_path_that_does_not_exist():
    """⚠️ Stale entries rot both lists. A stale gate entry makes `pytest` fail at
    collection; a stale exclusion entry inflates the count and buys slack in the
    ratchet that no real file is using."""
    stale = (set(_entries(GATE)) | set(_entries(EXCLUDED))) - _discovered()
    assert stale == set(), f"listed but absent from disk: {sorted(stale)}"


def test_neither_list_has_duplicates():
    """A repeat inflates the exclusion count and loosens the ratchet by one."""
    for path in (GATE, EXCLUDED):
        entries = _entries(path)
        dupes = {e for e in entries if entries.count(e) > 1}
        assert dupes == set(), f"{path.name} lists these more than once: {sorted(dupes)}"


def test_this_check_is_itself_in_the_gate():
    """⚠️ OTHERWISE IT NEVER RUNS. A membership check outside the channel it
    polices is the shape §11 calls a monitor whose failure mode is silence."""
    assert "tests/test_ci_membership.py" in _entries(GATE)
