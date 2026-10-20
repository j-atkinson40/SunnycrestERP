"""An unambiguous prefix of a known term IS that term.

⚠️ THE RULE JAMES RULED (walk 2026-10-20): "Extraction accepts an unambiguous prefix of
a known term, using exactly the ghost's vocabulary and tie-break rules." The ghost
already knew that "hopk" can only mean Hopkins; the extractor did not, so a director
who typed the abbreviation and kept going — without pressing Tab — got a funeral home
and a vault marked as not understood while the bar had been offering the completion a
moment earlier. The bar knew and the engine did not.

⚠️ IT EXPANDS, IT DOES NOT RESOLVE. This module turns "hopk" into "Hopkins Funeral
Home" and then stops. The expanded name goes back through `resolve_funeral_home` or
`product_name_resolver` exactly as a fully typed name does, which is what keeps
`typed_extraction`'s own standing claim true — "IT RESOLVES NOTHING ITSELF". A second
resolver living here would be the two-lists defect wearing a new hat.

⚠️ ONE SOURCE OF TRUTH FOR THE VOCABULARY, AND A CROSS-CHECKED PAIR FOR THE RULE —
stated plainly because the two are not the same guarantee and the difference is
load-bearing.

    the vocabulary   `build_vocabulary` is the single producer. The ghost is served
                     the same rows from `/capture/vocabulary` that this module reads
                     in-process. There is no second list.

    the tie-break    implemented HERE, in Python, and mirrored by `ghost.ts`. It cannot
                     literally be one implementation: James ruled on 2026-10-16 that
                     "matching is client-side only... keystroke latency must not depend
                     on the network", so the ghost cannot call this and this cannot
                     call the ghost.

                     ⚠️ SO THE PAIR IS HELD BY A SHARED CORPUS, NOT BY CARE.
                     `tests/data/opas_prefix_corpus.json` is GENERATED FROM THIS
                     MODULE and asserted by `ghost-agrees.test.ts` on the other side.
                     A rule changed here and not there turns the TypeScript suite red.
                     That is the same device the canvas validators use (CLAUDE.md:
                     "Both validators MUST agree on schema rules... tested
                     cross-reference").

⚠️ AN AMBIGUOUS PREFIX IS A QUESTION, NEVER A GUESS. Two terms that share a prefix and
differ by anything other than form produce the ordinary choice list. The one tie-break
that resolves without asking is the form default, and it is the one the office already
made nine times in ten.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.capture.vocabulary import Term

#: ⚠️ THE SAME FLOOR AS THE GHOST'S `MIN_PREFIX`, AND THE CORPUS PROVES IT STILL IS.
#: One letter matches most of the vocabulary, so a one-character "abbreviation" would
#: resolve to whatever happened to sort first.
MIN_PREFIX = 2

#: ⚠️ THE SAME DEFAULT THE CAPTURE AND THE GHOST BOTH ALREADY APPLY (James,
#: 2026-10-13, extended to the ghost 2026-10-16). A vault phrase ambiguous ONLY by
#: form is a burial vault.
BURIAL = "burial_vault"

#: Which vocabulary kinds can fill which field. Vault aliases are included because
#: `build_vocabulary` says in terms that they are the only route to some variants.
KINDS_FUNERAL_HOME = ("funeral_home",)
KINDS_VAULT = ("vault", "vault_alias")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def consume_loose(term: str, prefix: str) -> int:
    """How far into `term` the typed `prefix` reaches, or -1.

    ⚠️ A CHARACTER-WALK, NOT `startswith`, AND PUNCTUATION IS WHY. A director types
    "st m"; the record is `St. Mary's Cemetery`. A lowercased `startswith` fails on the
    PERIOD. This is a port of `ghost.ts::consumeLoose` and the corpus holds it to that.

    ⚠️ A SPACE IN THE PREFIX FORCES A WORD BOUNDARY IN THE TERM, so "st m" cannot match
    "stm..." inside a single word.
    """
    skippable = lambda ch: re.match(r"[^a-z0-9]", ch, re.I) is not None
    ti = pi = 0
    while pi < len(prefix):
        if skippable(prefix[pi]):
            if prefix[pi].isspace():
                while ti < len(term) and not term[ti].isspace():
                    ti += 1
                while ti < len(term) and term[ti].isspace():
                    ti += 1
            pi += 1
            continue
        while ti < len(term) and skippable(term[ti]) and not term[ti].isspace():
            ti += 1
        if ti >= len(term):
            return -1
        if term[ti].lower() != prefix[pi].lower():
            return -1
        ti += 1
        pi += 1
    return ti


def differ_only_by_form(matches: tuple[Term, ...]) -> bool:
    """Do these differ ONLY by their catalog form?

    ⚠️ THE TEST IS WHETHER REMOVING EACH TERM'S OWN FORM WORD LEAVES THEM IDENTICAL —
    which is the capture's `discriminators == ("form",)` condition expressed over
    names. `Continental Burial Vault` and `Continental 34"` differ by SIZE as well, and
    the capture refuses to guess there; so does this.
    """
    if len(matches) < 2:
        return False
    if not all(m.form for m in matches):
        return False
    if len({m.form for m in matches}) < 2:
        return False
    stems = set()
    for m in matches:
        word = (m.form or "").split("_")[0]  # burial_vault -> "burial"
        stems.add(
            re.sub(r"\s+", " ", re.sub(rf"\b{re.escape(word)}\b", "", _norm(m.text))).strip()
        )
    return len(stems) == 1


@dataclass(frozen=True)
class PrefixResolution:
    """What a prefix reached."""

    #: The prefix as typed.
    prefix: str
    #: Every term still in play after the tie-breaks.
    matches: tuple[Term, ...]
    #: The single term this prefix means, or None when it is a question.
    chosen: Term | None

    @property
    def ambiguous(self) -> bool:
        """⚠️ NOT `len(matches) > 1` — a form tie resolves and still has two matches."""
        return self.chosen is None and len(self.matches) > 1


def resolve_prefix(
    prefix: str, vocab: tuple[Term, ...], kinds: tuple[str, ...] | None = None
) -> PrefixResolution | None:
    """The term an abbreviation means, by the ghost's rule. None when it reaches nothing.

    THE RULE, IN ORDER — the same seven steps as `ghost.ts::completionFor`, minus the
    caret handling, which is a property of a text box and not of a vocabulary:

      1. shorter than `MIN_PREFIX` -> nothing.
      2. matches are terms this prefix reaches and is SHORTER than. A prefix equal to
         the whole term is not an abbreviation; the exact scans already own that, and
         claiming it here would put two writers on one span.
      3. restricted to `kinds`, so a prefix resolving for the vault cannot fill the
         funeral home. ⚠️ MEASURED ON PRODUCTION: a `company_entities` row is named
         "St. Mary's Cemetery", so "st m" reaches a funeral home AND a cemetery. Kind
         scoping is what keeps that from being an ambiguity it is not.
      4. if ANY match is carried by this tenant, only carried matches count.
      5. exactly one -> that is what it means.
      6. several differing only by form -> the burial vault.
      7. otherwise -> a question. ⚠️ IT DOES NOT FALL BACK TO A SHORTER PREFIX.
         Ambiguous at this length means ambiguous; the director typed the longer thing.
    """
    p = _norm(prefix)
    if len(p) < MIN_PREFIX:
        return None

    pool = [t for t in vocab if kinds is None or t.kind in kinds]
    matches = tuple(
        t for t in pool
        if 0 < consume_loose(t.text, prefix) < len(t.text)
    )
    if not matches:
        return None

    carried = tuple(t for t in matches if t.carried)
    if carried:
        matches = carried

    if len(matches) == 1:
        return PrefixResolution(prefix, matches, matches[0])

    if differ_only_by_form(matches):
        burial = next((m for m in matches if m.form == BURIAL), None)
        if burial is not None:
            return PrefixResolution(prefix, matches, burial)

    # ⚠️ SEVERAL TERMS WITH THE SAME TEXT ARE ONE ANSWER, NOT A QUESTION. The vocabulary
    # is keyed on (kind, text), so one name carried as both a variant and a confirmed
    # alias appears twice. Asking "did you mean Monticello Burial Vault or Monticello
    # Burial Vault?" is not a question anybody can answer.
    if len({_norm(m.text) for m in matches}) == 1:
        return PrefixResolution(prefix, matches, matches[0])

    return PrefixResolution(prefix, matches, None)
