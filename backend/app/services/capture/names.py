"""Clause 2 of guided capture slice 2: a bare name mid-sentence.

James's dispatch of 2026-10-28, clause 2: *"names mid-sentence"* — an unknown word
sitting between two things the engine DID understand is the decedent, without needing
"last name" in front of it.

⚠️ WHY A BARE NAME WAS NOT ALREADY CAPTURED, AND IT WAS NOT AN OVERSIGHT. The surname
rules in `typed_extraction` all require a MARKER ("last name smith", "decedent smith",
"the smith family"), and the reason is written there: surnames are an OPEN set, so any
rule about what a name LOOKS like is wrong about somebody's family. A bare word cannot
be recognised as a name by its shape.

⚠️ SO THIS CLAUSE DOES NOT USE SHAPE. IT USES POSITION. The evidence that "smith" is a
name in

    "new order for hopkins, smith, thursday, 2 chairs, st marys skaneateles"

is not that it looks like one — it is that the engine understood everything around it
and this word is what is left between two of those understandings. That is a fact about
the sentence rather than a guess about the word, which is what makes it admissible where
a frequency list or a capitalisation rule would not be.

⚠️ MEASURED ON PRODUCTION BEFORE BUILDING (2026-10-29): the sentence above returns
`deceased_name=None` and `unrecognized=('smith',)`, while the marker form returns
`deceased_name='smith'` and nothing held. So this clause closes a gap James hit in his
own walk, and the marker path already works and must keep working.
"""

from __future__ import annotations

import re

from app.services.capture.held import is_typo_of_a_known_term
from app.services.capture.noise import FUNCTION_WORDS, NOISE_WORDS

#: ⚠️ A SEPARATOR-ONLY GAP CHECK STOOD HERE AND WAS DELETED, BECAUSE A BREAK TEST
#: PROVED IT A TAUTOLOGY. It asked whether only separators sat between the unclaimed run
#: and the next claimed span — which cannot be otherwise: `_unclaimed_slices` returns
#: MAXIMAL unclaimed runs, so a run ends exactly where the next claimed span begins and
#: the gap is always "". Measured over four sentence shapes: every gap was `''`.
#:
#: Disabling it turned NOTHING red, which is the signature CLAUDE.md §11 names — "a
#: check that cannot be made to fail is documentation". Filed as this comment and
#: removed, the same disposal the disjointness assertion in `typed_extraction` got.
#: ⚠️ THE SAME CLOSED-CLASS ARGUMENT THE SURNAME RULES MAKE, reused rather than
#: restated. `FUNCTION_WORDS` exists because "last name smith it is 1 oclock" produced
#: the decedent "Smith It" on James's walk of 2026-10-26, and the ruling then was "fix
#: it in the name rules, not a one-word stoplist". A bare run that IS a function word
#: is not a name for exactly that reason.


def bare_name_before_a_term(
    line: str,
    spans: list[tuple[int, int]],
    unclaimed: tuple[tuple[int, str], ...],
    *,
    known_terms=(),
) -> tuple[str, int, int] | None:
    """`(name, start, end)` for an unclaimed run that is the decedent, or None.

    The run qualifies when ALL of these hold:

    * it is immediately followed by a span the engine CLAIMED, with only separators in
      between — this is the whole evidence, per the module docstring;
    * at least one claimed span also sits BEFORE it, so the word is genuinely between
      two understandings rather than dangling off the front of the line;
    * no word in it is a noise word or a function word;
    * it is not within two letters of a known term — that is a TYPO, and clause 5 asks
      "did you mean" about it rather than this clause filing it as a name.

    ⚠️ THE TYPO TEST USES THE SHARED `within_two`, which is the one James accepted for
    clause 2's holding and clause 5's suggesting both: *"one distance, two uses"*. Two
    copies would drift, and the design review called that out before either was built.

    ⚠️ `unclaimed` IS PASSED IN RATHER THAN COMPUTED, AND THE E6 RATCHET IS WHY. This
    module may not import `typed_extraction` — `test_only_the_typed_path_imports_the_
    extractor` allows exactly one importer and PARSES rather than greps, so even a lazy
    import inside a function is caught. It was caught: the ratchet went red on this file
    before any behaviour was tested. Taking the runs as data inverts the dependency and
    leaves this a pure function, which is also easier to test than one that queries.
    """
    if not spans:
        return None

    claimed = sorted(spans)
    noise = NOISE_WORDS
    funcs = FUNCTION_WORDS

    for start, slice_ in unclaimed:
        end = start + len(slice_)
        words = [w for w in re.split(r"[^A-Za-z'\-]+", slice_) if w]
        if not words:
            continue
        if any(w.casefold() in noise or w.casefold() in funcs for w in words):
            continue

        # ⚠️ BOUNDED ON BOTH SIDES. A run with nothing claimed before it is the opening
        # of the sentence ("smith, order for hopkins") and this clause does not claim
        # it — the dispatch says "mid-sentence", and a leading run is where an
        # unresolved funeral home or a stray opener lands.
        before = [s for s in claimed if s[1] <= start]
        after = [s for s in claimed if s[0] >= end]
        if not before or not after:
            continue

        name = " ".join(words)
        # ⚠️ ONE DISTANCE, TWO USES — clause 2's holding and clause 5's suggesting come
        # from the same `within_two`, via `held`, which James accepted at design review.
        # ⚠️ AND IT COMPARES AGAINST INTERIOR WORDS, NOT JUST WHOLE NAMES. The first
        # version compared to the full recorded name and let "riversde" through as a
        # decedent, because it is nowhere near "Riverside Funeral Home" as a string.
        if is_typo_of_a_known_term(name, known_terms):
            continue
        if any(is_typo_of_a_known_term(w, known_terms) for w in words):
            continue

        # ⚠️ THE RUN AS TYPED, TRIMMED TO THE WORDS. The slice carries the separators
        # that surrounded it (", smith, "), and claiming those would eat the comma the
        # next pass may need. The span is the first word's start to the last word's end.
        m_first = re.search(r"[A-Za-z'\-]", slice_)
        m_last = None
        for m_last in re.finditer(r"[A-Za-z'\-]", slice_):
            pass
        if m_first is None or m_last is None:
            continue
        return name, start + m_first.start(), start + m_last.end()

    return None
