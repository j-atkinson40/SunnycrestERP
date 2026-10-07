"""Resolve a spoken Legacy Series print name against the print list.

⚠️ CANDIDATES AND A DISCRIMINATOR. NEVER A PICK. Same contract as
`product_name_resolver`, and for the same reason: a director says "the cross one"
and there are three crosses. Choosing one of them silently puts a print on a vault
nobody asked for, and the family sees it at the funeral.

⚠️ AN UNMATCHED NAME IS KEPT VERBATIM AND FLAGGED, NEVER DROPPED OR COERCED — by
ruling (2026-10-07). The three reasons a name can fail to match are all live:

    the print list is wrong      Bridgeable's 64 and the portal's two lists
                                 disagree by 14 names each way, and the Wilbert
                                 poster has not arrived to settle it
    the director misremembered   "Field and Barn" for "Green Field & Barn"
    it is a custom print         Legacy Custom Series carries artwork, not a
                                 catalogue name

Coercing to the nearest match would make all three look like the first, and
dropping would lose what the director actually said. So `Resolution.phrase` always
carries the input and `matched` says whether anything in the list corresponds.

⚠️ THE 64 ARE NOT AUTHORITATIVE AND THIS MODULE SAYS SO RATHER THAN IMPLYING IT.
Measured 2026-10-07: Bridgeable's `LEGACY_SERIES_PRINTS` holds 64 distinct names;
the ordering portal's burial list holds 51 and its urn list 48, the two portal lists
disagree with each other, and against the union of them Bridgeable has 14 names
nobody else lists while they have 14 it does not. All three are transcriptions of
one Wilbert poster. The poster is the declared tiebreak. Until it arrives this
resolver matches against the 64 BECAUSE THEY ARE IN THE REPOSITORY, not because
they are right.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from app.services.personalization_config import LEGACY_SERIES_PRINTS


class PrintDiscriminator(str, Enum):
    """What separates the candidates, when more than one matched.

    ⚠️ NAMES THE QUESTION TO ASK, which is the whole point of returning a set. A
    caller that renders "3 matches" has told the director nothing; one that renders
    "which finish — gold, silver or white?" has asked a question they can answer.
    """

    #: Same base name, different finish or colour: `Cross — Gold` / `— Silver`.
    FINISH = "finish"
    #: Same base name, numbered variants: `Jewish 1` / `Jewish 2`.
    VARIANT = "variant"
    #: Different prints that merely share a word. The weakest case.
    UNRELATED = "unrelated"


@dataclass(frozen=True)
class PrintCandidate:
    name: str
    category: str


@dataclass(frozen=True)
class PrintResolution:
    """⚠️ `phrase` IS ALWAYS THE INPUT, UNCHANGED, whatever happened. A caller
    persisting a resolution keeps what the director said even when nothing matched,
    which is the ruling."""

    phrase: str
    normalized: str
    candidates: tuple[PrintCandidate, ...]
    discriminators: tuple[PrintDiscriminator, ...]

    @property
    def matched(self) -> bool:
        """Anything in the list corresponds. ⚠️ NOT "resolved" — see `print_name`."""
        return bool(self.candidates)

    @property
    def print_name(self) -> str | None:
        """The one name, or None when zero or several matched.

        ⚠️ NONE FOR AMBIGUOUS AND NONE FOR UNMATCHED, DELIBERATELY THE SAME VALUE,
        because a caller must not be able to tell them apart from THIS property —
        it would read "no print" for a director who named three. The distinction is
        `matched`, and a caller that needs it has to ask.
        """
        return self.candidates[0].name if len(self.candidates) == 1 else None


#: name -> category, flattened once at import.
_BY_NAME: dict[str, str] = {
    p: cat["category"] for cat in LEGACY_SERIES_PRINTS for p in cat["prints"]
}


def normalize(s: str | None) -> str:
    """Casefold, strip punctuation, collapse whitespace.

    ⚠️ TRIM BEFORE STRIPPING PUNCTUATION, NOT AFTER. The reverse order leaves a
    trailing separator behind when the input ends in whitespace — the exact defect
    measured in `normalizeRequest` on 2026-10-03, where stripping first meant an
    anchor failed on trailing space. `—`, `&`, `'` and `/` all appear in these
    names, so this is not hypothetical.
    """
    if not s:
        return ""
    out = s.strip().casefold()
    out = out.replace("&", " and ")
    out = re.sub(r"[^a-z0-9]+", " ", out)
    return re.sub(r"\s+", " ", out).strip()


#: normalized -> the names that normalize to it. ⚠️ A LIST, not a single name:
#: `Cross — Gold` and `Cross Gold` would collide, and a dict would silently keep one.
_BY_NORMALIZED: dict[str, list[str]] = {}
for _name in _BY_NAME:
    _BY_NORMALIZED.setdefault(normalize(_name), []).append(_name)


def _classify(names: tuple[str, ...], norm: str) -> tuple[PrintDiscriminator, ...]:
    """Why do these candidates differ?

    ⚠️ CLASSIFIED AGAINST THE PHRASE, NOT AGAINST A LIST OF KNOWN SUFFIXES. The
    first version stripped a hardcoded set — `gold`, `silver`, `white`,
    `no poem` — and got `Stained Glass — Gold Marble` / `— White Marble` wrong,
    because "gold marble" was not in the list. Extending the list is whack-a-mole
    against a catalogue that changes, and every print the list does not know gets
    misclassified as UNRELATED.

    The phrase itself is the base. If every candidate begins with what the director
    SAID, then what separates them is whatever trails it — a finish or a number —
    and the question to ask is about that. If they diverge before the phrase ends,
    they merely share a word.
    """
    if len(names) < 2:
        return ()
    if not all(normalize(n).startswith(norm) for n in names):
        return (PrintDiscriminator.UNRELATED,)
    found: set[PrintDiscriminator] = set()
    for n in names:
        tail = normalize(n)[len(norm):].strip()
        found.add(
            PrintDiscriminator.VARIANT if re.fullmatch(r"\d+", tail)
            else PrintDiscriminator.FINISH
        )
    return tuple(sorted(found, key=lambda d: d.value))


def resolve(phrase: str | None) -> PrintResolution:
    """Resolve a spoken print name. Never raises, never picks, never coerces.

    Three passes, widening, and it STOPS at the first that matches — a widening
    search that kept going would return the union and make every exact name
    ambiguous with everything containing it.

      1. exact, normalized          "cross gold" -> Cross — Gold
      2. the phrase is a whole-word prefix of a NAME  ("cross" -> the 3 crosses)
      3. every word of the phrase appears in the name

    ⚠️ PASS 2 IS ONE-DIRECTIONAL AND THE OTHER DIRECTION IS A COERCION. It ran both
    ways first, and matching a name that is a prefix of the PHRASE means DISCARDING
    WORDS THE DIRECTOR SAID: "Tropical Island" became `Tropical` and
    "Sunrise-Sunset 1" became `Sunrise-Sunset`. Both are plausibly the same picture —
    the portal's urn list uses the longer names and its burial list the shorter — and
    that is exactly why dropping the extra word is a GUESS recorded as a fact. The
    poster is the declared tiebreak; until it arrives these must surface as unmatched
    so the 14/14 divergence is visible rather than silently resolved.

    Narrowing the other way is not a coercion: a director who says "cross" has said
    something true of three prints, and returning all three asks rather than assumes.

    ⚠️ NO FUZZY DISTANCE, DELIBERATELY. `Bridge 1` and `Bridge 2` are one edit
    apart and are different prints; so are `Marble — Gold` and `Marble — White`.
    Edit distance cannot tell a typo from a sibling product here, and on this list
    the siblings are the common case.
    """
    norm = normalize(phrase)
    if not norm:
        return PrintResolution(phrase or "", "", (), ())

    names: list[str] = []

    exact = _BY_NORMALIZED.get(norm)
    if exact:
        names = list(exact)
    else:
        words = norm.split()
        # ⚠️ ONE DIRECTION ONLY — see the docstring. `norm.startswith(name)` would
        # drop words the director said.
        prefix = [n for n in _BY_NAME if normalize(n).startswith(norm + " ")]
        if prefix:
            names = prefix
        else:
            names = [
                n for n in _BY_NAME
                if all(w in normalize(n).split() for w in words)
            ]

    names.sort()
    return PrintResolution(
        phrase=phrase or "",
        normalized=norm,
        candidates=tuple(PrintCandidate(n, _BY_NAME[n]) for n in names),
        discriminators=_classify(tuple(names), norm),
    )


def print_count() -> int:
    """⚠️ EXISTS SO A TEST CAN ASSERT THE INSTRUMENT SEES SOMETHING. A resolver over
    an empty list returns "no match" for every input, which is indistinguishable
    from a list that does not contain what was asked for."""
    return len(_BY_NAME)
