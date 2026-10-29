"""Words the engine could not place, and the two questions asked about them.

James's dispatch of 2026-10-28, slice 2, clauses 2, 4 and 5. One module because the
three things below are one decision wearing three hats:

    within_two      is this word a typo of that term?
    did_you_mean    is it a typo of EXACTLY ONE term?
    still_forming   is a longer known term still being typed?

⚠️ `within_two` IS SHARED BY CLAUSES 2 AND 5 ON PURPOSE, AND THE DISPATCH IS WHY. Clause
2 holds a word that is "within 2 letters of a known term" (that is a typo, not a name);
clause 5 suggests a correction for a word "within 2 letters of exactly one known term".
Those are the same measurement used for two decisions. Two implementations would drift —
and the drift would be invisible, because each would still look right on its own: a word
could be held as a typo and then never suggested, or suggested and then not held.

⚠️ AND THE MEASUREMENT IS EDIT DISTANCE, NOT A SIMILARITY RATIO. The codebase already has
four `SequenceMatcher(...).ratio()` call sites (import_alias, network_discovery,
charge_matching) and NONE of them answers "within 2 letters": a ratio is relative to
length, so a 0.8 threshold is ~1 letter on a 5-letter word and ~4 on a 20-letter one.
"montcello" -> "monticello" is one insertion whatever the word length, which is what the
dispatch asked for.
"""
from __future__ import annotations

from dataclasses import dataclass, field

#: The dispatch's threshold, for both clauses. One name so it cannot be two numbers.
MAX_TYPO_DISTANCE = 2

#: ⚠️ A FLOOR ON THE WORD LENGTH, AND IT IS NOT IN THE DISPATCH — reported rather than
#: assumed. At distance 2, every 3-letter word is "within 2 letters" of a huge number of
#: terms: "flg" reaches "flag", "fly", "fog", "leg". Below this length the measurement
#: stops discriminating, so a short word is held WITHOUT a suggestion rather than
#: suggested wrongly. Four is the shortest length at which distance 2 still leaves most
#: of the word intact.
MIN_SUGGESTIBLE_LENGTH = 4


def _norm(s: object) -> str:
    """Lower-case, collapse whitespace. The same shape `prefix_resolve._norm` uses."""
    return " ".join(str(s or "").lower().split())


def _words(s: object) -> list[str]:
    """Lower-cased words with punctuation stripped from each end.

    ⚠️ PUNCTUATION-INSENSITIVE, AND A PRODUCTION PROBE IS WHY. The office types
    `st marys`; the term is `St. Mary's Cemetery`. Under `_norm` alone,
    `"st. mary's cemetery".startswith("st marys")` is **False** — the period and the
    apostrophe are both in the way — so the lookahead would never fire on the very term
    the dispatch's example names.

    ⚠️ AND IT STRIPS ONLY AT THE EDGES, matching `prefix_resolve._word_key`'s own
    behaviour, so an interior apostrophe is kept where it is part of the word. `Mary's`
    becomes `marys` here because the apostrophe is interior-adjacent to the final `s`,
    which is the form the office types.
    """
    out: list[str] = []
    for raw in _norm(s).split():
        w = raw.strip(".,;:!?()\u201c\u201d\"").replace("\u2019", "").replace("'", "")
        if w:
            out.append(w)
    return out


def distance_within(a: str, b: str, limit: int = MAX_TYPO_DISTANCE) -> int | None:
    """Levenshtein distance between `a` and `b`, or None if it exceeds `limit`.

    ⚠️ BOUNDED, AND THE BOUND IS WHY THIS IS NOT `difflib`. Only distances up to `limit`
    matter, so the row is abandoned as soon as its cheapest cell exceeds it — which also
    means a long word and a short one cost almost nothing to reject (their lengths differ
    by more than `limit`, so the answer is known before any work).

    Returns the distance so a caller can prefer a closer match; None rather than a
    sentinel so "too far" cannot be compared as a number by accident.
    """
    s1, s2 = _norm(a), _norm(b)
    if s1 == s2:
        return 0
    # ⚠️ THE LENGTH GATE IS NOT AN OPTIMISATION, it is most of the correctness: two words
    # whose lengths differ by more than `limit` cannot be within `limit`, and without
    # this a one-letter word would be compared against every term in the vocabulary.
    if abs(len(s1) - len(s2)) > limit:
        return None
    if not s1 or not s2:
        return len(s1) or len(s2)

    previous = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1, start=1):
        current = [i]
        for j, c2 in enumerate(s2, start=1):
            current.append(min(
                previous[j] + 1,          # deletion
                current[j - 1] + 1,       # insertion
                previous[j - 1] + (c1 != c2),  # substitution
            ))
        # ⚠️ THE EARLY EXIT IS ON THE ROW MINIMUM, NOT THE LAST CELL. Every remaining
        # path costs at least the cheapest cell in this row, so a row whose minimum
        # already exceeds the limit cannot recover.
        if min(current) > limit:
            return None
        previous = current
    d = previous[-1]
    return d if d <= limit else None


def within_two(a: str, b: str) -> bool:
    """Is `a` within `MAX_TYPO_DISTANCE` letters of `b`? The shared test."""
    return distance_within(a, b) is not None


@dataclass(frozen=True)
class Suggestion:
    """The one term a held word probably meant."""

    #: The word as the director typed it.
    word: str
    #: The term it probably meant, in the office's own capitalisation.
    term: str
    #: Which row that term would fill, so the caller can place it without re-resolving.
    kind: str
    #: How far apart they are. 0 never occurs here — an exact match is not a typo.
    distance: int


def _candidates(terms) -> list[tuple[str, str]]:
    """`(comparable, kind)` for every term AND every word inside a term.

    ⚠️ WORD LEVEL IS REQUIRED, NOT A REFINEMENT, AND A PRODUCTION PROBE IS WHY. The
    dispatch's headline case is "montcello" -> "Did you mean Monticello?" — and measured
    against Sunnycrest's real vocabulary **there is no term "Monticello"**. The terms are
    full product names: `Monticello Burial Vault`, `Monticello Urn Vault`. "montcello" is
    nowhere near either as a whole string (distance 11), so a whole-term comparison
    returns None and the dispatch's own example fails.

    The office says "monticello" and means the vault, which is why the ABBREVIATION
    machinery (`prefix_resolve`) matches interior words. The same has to be true of typos.

    ⚠️ AND THE SUGGESTION'S OUTPUT IS TEXT FOR THE EXTRACTOR, NOT A RESOLVED VALUE. Yes on
    "Did you mean Monticello?" replaces the word and re-extracts: measured, `"monticello"`
    alone resolves to `Monticello Burial Vault` through the form-default rule of
    2026-10-16, with no pick. If the suggestion carried a resolved value instead, it would
    be a second answer to "which Monticello" and could disagree with that rule.
    """
    out: list[tuple[str, str]] = []
    for term in terms or ():
        text = getattr(term, "text", None)
        if not text:
            continue
        kind = str(getattr(term, "kind", "") or "")
        out.append((str(text), kind))
        words = str(text).split()
        if len(words) > 1:
            for w in words:
                # ⚠️ INTERIOR WORDS ONLY WHERE THEY CARRY MEANING. "Vault", "Burial" and
                # "Cemetery" appear in dozens of terms, so suggesting them would make
                # every near-miss ambiguous and the question would never be asked. They
                # are exactly `_NOISE_WORDS`' "label words a director says around a value
                # rather than as one".
                if _is_label_word(w):
                    continue
                out.append((w, kind))
    return out


def _is_label_word(word: str) -> bool:
    """⚠️ READ FROM `capture.noise` RATHER THAN RE-LISTED, AND A RATCHET DECIDED WHERE.
    Clause 2 needs the same exclusion ("service monti" must not name the deceased
    Service), so two copies would drift. My first version imported it from
    `typed_extraction` — which `test_only_the_typed_path_imports_the_extractor` forbids,
    by the E6 guarantee that the mention policy stays isolated to the typed path. The
    gate caught it; review did not. The list now lives in a leaf module both sides take.
    """
    from app.services.capture.noise import NOISE_WORDS

    return _norm(word).strip(".,;:'\u2019") in NOISE_WORDS


def did_you_mean(word: str, terms) -> Suggestion | None:
    """The single term `word` is a typo of, or None.

    `terms` is anything yielding objects with `.text` and `.kind` — i.e.
    `vocabulary.build_vocabulary`'s `Term`s. Both whole terms and the meaningful words
    inside them are candidates; see `_candidates`.

    ⚠️ "EXACTLY ONE" IS THE DISPATCH'S WORD AND IT IS THE WHOLE GUARD. A word within two
    letters of several terms has not identified anything: "montcello" reaching only
    Monticello is a correction worth offering, while a word reaching both Monticello and
    Monticello Urn Vault is the ambiguity question, not this one.

    ⚠️ AN EXACT MATCH RETURNS None, NOT A SUGGESTION. A word that IS a known term was
    never held in the first place; reaching here with one means something upstream is
    wrong, and offering "Did you mean Monticello?" about the word "Monticello" would be
    the pane asking a question it has already answered.

    ⚠️ AND TIES ARE REFUSED RATHER THAN BROKEN BY DISTANCE. Two terms at distance 1 and 2
    look like a clear winner and are not: the closer one is closer by SPELLING, which says
    nothing about which the director meant. "Did you mean X?" with a Yes pill has to be
    right, because Yes places it.
    """
    w = _norm(word)
    if not w or len(w) < MIN_SUGGESTIBLE_LENGTH:
        return None

    found: dict[str, Suggestion] = {}
    for text, kind in _candidates(terms):
        key = _norm(text)
        if key == w:
            return None  # it IS the term (or a word of one); see the docstring
        if key in found:
            continue
        d = distance_within(w, key)
        if d is None or d == 0:
            continue
        found[key] = Suggestion(word=str(word), term=str(text), kind=kind, distance=d)
        # ⚠️ KEYED ON THE NORMALISED TEXT RATHER THAN COUNTED, because the same word
        # appears inside many terms — "Monticello" is a word of both Monticello vaults,
        # and that is ONE suggestion, not two.
        #
        # ⚠️ THIS EARLY EXIT IS AN OPTIMISATION, NOT THE TIE GUARD, AND A BREAK TEST IS
        # HOW I KNOW. I first wrote it as though it were load-bearing. Removing it leaves
        # every test green, because the `len(found) == 1` below answers the same question
        # — two guards for one condition, and only the second is required. What the early
        # exit genuinely buys is stopping a scan that cannot change its answer; it does
        # NOT buy order-independence either, since the final check is order-independent on
        # its own. CLAUDE.md §11: a guard whose protection is supplied by a layer beneath
        # it. Kept because a vocabulary scan is not free, labelled so nobody trusts it.
        if len(found) > 1:
            return None
    # ⚠️ THIS IS THE TIE GUARD. "Exactly one" is the dispatch's word; break this and the
    # suggestion starts guessing between spellings.
    return next(iter(found.values())) if len(found) == 1 else None


def still_forming(phrase: str, terms) -> bool:
    """Is a LONGER known term still being typed? Clause 1's waiting rule.

    > wait on "st marys " because "st marys skaneateles" exists

    ⚠️ THIS IS NOT `GATING_TAIL_OPEN`, AND CONFUSING THE TWO IS THE EASY MISTAKE. That
    gate is about an INCOMPLETE word — it exists so "Hopk" does not resolve to Hopkins
    while the director is still inside the word. This is about a COMPLETE term that is a
    PREFIX of a longer complete term. "Hopk" is not a term at all; "st marys" is.
    `tail_open` would answer False for "st marys " (the space closed the word) and the
    word must still wait.

    ⚠️ THE TEST IS "STARTS WITH AND EXTENDS PAST", NOT "CONTAINS". A term containing the
    phrase somewhere in the middle is a different term, not a continuation of this one:
    "Mary" appears inside "St. Mary's" without "Mary" being a prefix of it, and holding
    the answer on that basis would make a word wait for something the director is
    demonstrably not typing.
    """
    typed = _words(phrase)
    if not typed:
        return False
    for term in terms or ():
        words = _words(getattr(term, "text", "") or "")
        # ⚠️ WORD-WISE, NOT CHARACTER-WISE, which is what makes the boundary rule
        # automatic: a term CONTINUES this phrase only if it has every word of it in
        # order and then at least one more. Comparing strings needed an explicit "the
        # next character is a space" test and still failed on punctuation.
        #
        # ⚠️ AND "monti" DOES NOT WAIT FOR "monticello" UNDER THIS RULE, deliberately —
        # `monti != monticello` as words, so the abbreviation case the ghost already
        # handles is untouched.
        if len(words) > len(typed) and words[:len(typed)] == typed:
            return True
    return False


#: ⚠️ WHERE A HELD WORD CAME FROM. Clause 6 logs "held, dragged, edited, suggested,
#: accepted and declined", and a held word's own record has to say which of those
#: happened to it — a word the director EDITED is not in the same state as one the
#: engine merely failed to place, and clause 5's "never asks about that word again"
#: needs the declining to be remembered on the word itself.
ORIGIN_TYPED = "typed"
ORIGIN_EDITED = "edited"
ORIGIN_DRAGGED = "dragged"


@dataclass
class HeldWord:
    """One word the engine could not place, as it is stored on the session.

    ⚠️ IT CANNOT LIVE IN `unrecognized`, AND I EXPECTED IT COULD. That field is
    `tuple[str, ...]` — no position, no state — and is RECOMPUTED FROM THE TEXT on every
    read. Measured on production, one session holds
    `['smith', '1', '1 oclock church', 'friday']`: transient junk from a half-typed
    sentence. Held words must survive the next keystroke, be retried after each answer,
    be dragged and edited — and, once clause 1 removes words from the bar, a list computed
    from the text cannot see them at all.
    """

    #: The word as it stands now — the director's text, or their edit of it.
    word: str
    #: `ORIGIN_*` — how it came to be held.
    origin: str = ORIGIN_TYPED
    #: ⚠️ TERMS THE DIRECTOR HAS SAID NO TO. Clause 5: "No keeps it held and never asks
    #: about that word again." Stored as the terms declined rather than a bare flag, so
    #: editing the word to something else can still be suggested about.
    declined: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        out: dict = {"word": self.word, "origin": self.origin}
        if self.declined:
            out["declined"] = list(self.declined)
        return out

    @classmethod
    def from_dict(cls, raw: object) -> "HeldWord | None":
        """⚠️ TOLERATES A BARE STRING, because the column is JSON and an older row (or a
        hand-edit) may hold one. A held word that cannot be parsed is dropped rather than
        raising: the strip is an aid, and a malformed entry must not take the pane down.
        """
        if isinstance(raw, str):
            return cls(word=raw) if raw.strip() else None
        if not isinstance(raw, dict):
            return None
        word = str(raw.get("word") or "").strip()
        if not word:
            return None
        origin = str(raw.get("origin") or ORIGIN_TYPED)
        declined = raw.get("declined")
        return cls(
            word=word,
            origin=origin if origin in (ORIGIN_TYPED, ORIGIN_EDITED, ORIGIN_DRAGGED)
            else ORIGIN_TYPED,
            declined=[str(d) for d in declined] if isinstance(declined, list) else [],
        )
