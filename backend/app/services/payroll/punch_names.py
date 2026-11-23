"""Whose punch is this? — the name-resolution ruling, implemented.

⚠️ **THE PUNCH FILE CARRIES NAMES AND NO EMPLOYEE NUMBERS.** Every other
payroll import is keyed on the Payentry file number; this one is not, so a
punch cannot be attached to a person without deciding that two spellings are
the same human being. That decision is the whole of this module.

**The ruling** (James, Payroll 3 go message, item 4; restated 2026-11-23):

  1. match Punch Location names to `emp_id` via **the same week's Employee
     Hours names**, then via **register names**,
  2. after normalising **case, spacing, Sr./Jr. and punctuation**,
  3. **unmatched or ambiguous is a finding**,
  4. a **person-confirmed** mapping is stored as an alias — "Micheal" → 22 was
     the first,
  5. **never fuzzy-match silently.**

⚠️ **THERE IS NO EDIT DISTANCE IN HERE AND THAT IS DELIBERATE.** "Micheal" and
"Michael" are one character apart and a Levenshtein threshold would join them
without anybody deciding. The same threshold joins two real brothers. So the
only joins this module makes are EXACT after normalisation; everything else is
reported for a person to confirm, and their confirmation becomes an alias that
makes the match exact next time.

⚠️ **THE ORDER OF THE TWO SOURCES MATTERS.** The week's own hours file wins
over the register because it is the same week: a register spanning a year may
contain somebody who left in March, and a punch in November is not theirs.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field

#: Generational suffixes, stripped before comparing. ⚠️ A person is "Hunt Jr"
#: on one export and "Hunt" on the other, and that is not two people.
_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}

#: ⚠️ NOT STRIPPED: anything that is part of a name. Only separators and
#: punctuation go. `O'Brien` -> `obrien` and `Smith-Jones` -> `smith jones`,
#: both of which are stable across the two exports.
_PUNCT = re.compile(r"[.,'’`]")
_SEPARATORS = re.compile(r"[-/\\_]+")
_SPACE = re.compile(r"\s+")


def normalise(name: str) -> str:
    """A name reduced to the form two exports can be compared in.

    ⚠️ **TOKENS ARE SORTED, BECAUSE THE TWO FILES DISAGREE ABOUT ORDER.** The
    register writes "Hunt, Michael" and the punch file writes "Michael Hunt".
    Comparing them as written would make every single person unmatched, and
    the first thing anybody would reach for is a fuzzy match — which is the
    thing the ruling forbids. Sorting the tokens makes the comparison exact
    without making it loose.
    """
    if not name:
        return ""
    # Strip accents so "Peña" and "Pena" are the same person across two
    # exports that disagree about encoding.
    folded = unicodedata.normalize("NFKD", name)
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    folded = folded.casefold()
    folded = _PUNCT.sub("", folded)
    folded = _SEPARATORS.sub(" ", folded)
    tokens = [t for t in _SPACE.split(folded.strip()) if t]
    tokens = [t for t in tokens if t not in _SUFFIXES]
    return " ".join(sorted(tokens))


#: Why a punch could not be attached to anybody.
UNMATCHED = "punch_name_unmatched"
AMBIGUOUS = "punch_name_ambiguous"


@dataclass(frozen=True)
class NameFinding:
    """A punch name a person has to look at. Never a guess."""

    kind: str
    raw_name: str
    normalised: str
    #: For `AMBIGUOUS`, the employee numbers it could be — so the person
    #: confirming is choosing from a named list rather than typing one.
    candidates: tuple[str, ...] = ()

    @property
    def detail(self) -> str:
        if self.kind == AMBIGUOUS:
            return (f"{self.raw_name!r} matches more than one employee "
                    f"({', '.join(self.candidates)}). Confirm which one it is; "
                    "nothing is matched until somebody does.")
        return (f"{self.raw_name!r} on the punch file matches nobody in this "
                "week's hours, the register, or the confirmed aliases. Confirm "
                "who it is, or it stays unattached.")


@dataclass
class Resolution:
    """What the punch names resolved to, and what needs a person."""

    by_raw_name: dict[str, str] = field(default_factory=dict)
    findings: list[NameFinding] = field(default_factory=list)

    @property
    def matched(self) -> int:
        return len(self.by_raw_name)


def build_index(
    *sources: dict[str, Iterable[str]] | dict[str, str],
) -> dict[str, set[str]]:
    """Normalised name → the employee numbers that spell it that way.

    Sources are consulted in order and EARLIER ONES WIN: the week's own hours
    file before the register, because a register spanning a year may hold
    somebody who left in March and a punch in November is not theirs.
    """
    index: dict[str, set[str]] = {}
    claimed: set[str] = set()
    for source in sources:
        local: dict[str, set[str]] = {}
        for emp_id, names in source.items():
            for name in ({names} if isinstance(names, str) else names):
                key = normalise(name)
                if not key:
                    continue
                local.setdefault(key, set()).add(emp_id)
        for key, emps in local.items():
            # ⚠️ A LATER SOURCE NEVER WIDENS AN EARLIER MATCH. If the hours
            # file says this spelling is employee 22, the register saying it is
            # also employee 7 does not make it ambiguous — the week's own file
            # is the better evidence and it already answered.
            if key in claimed:
                continue
            index.setdefault(key, set()).update(emps)
        claimed.update(local)
    return index


def resolve(
    punch_names: set[str],
    *,
    # ⚠️ Iterable, not set: the hours report ships lists (JSON has no sets) and
    # a hint promising a set would be a stated reason that is not true.
    hours_names_by_emp: dict[str, Iterable[str]],
    register_names_by_emp: dict[str, Iterable[str]],
    aliases: dict[str, str],
) -> Resolution:
    """Attach each punch name to an employee, or report it.

    `aliases` is normalised-name → emp_id, person-confirmed. ⚠️ **THEY ARE
    CONSULTED FIRST AND THEY ARE EXACT.** A confirmed mapping is somebody's
    decision and outranks both exports — which is what makes confirming one
    worth doing: the same name never comes back as a finding.
    """
    index = build_index(hours_names_by_emp, register_names_by_emp)
    out = Resolution()

    for raw in sorted(punch_names):
        key = normalise(raw)
        if not key:
            continue
        if key in aliases:
            out.by_raw_name[raw] = aliases[key]
            continue
        candidates = index.get(key, set())
        if len(candidates) == 1:
            out.by_raw_name[raw] = next(iter(candidates))
        elif len(candidates) > 1:
            # ⚠️ AMBIGUOUS IS NOT "PICK THE FIRST". Two people whose names
            # normalise the same is exactly when a guess attaches somebody's
            # hours to their brother.
            out.findings.append(NameFinding(
                AMBIGUOUS, raw, key, tuple(sorted(candidates))))
        else:
            out.findings.append(NameFinding(UNMATCHED, raw, key))
    return out
