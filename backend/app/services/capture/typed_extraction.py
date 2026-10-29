"""One typed line -> candidate field values, deterministically. No model.

⚠️ E1 (2026-10-07): EXTRACTION IN THIS SLICE IS DETERMINISTIC. Nothing here calls a
model. The reason is measured rather than stylistic: the production extraction prompt
routes to `claude-sonnet-4-6` and the nearest comparable prompt averages 6,336 ms and
$0.0220 per call (`intelligence_executions` on dev, n=33). A call per typed line is
roughly 48 s and $0.16 for an eight-line order, and the pane would feel dead between
keystrokes.

⚠️ EVERYTHING UNPLACED IS RETURNED, NEVER DROPPED AND NEVER GUESSED. The mechanism is
SPAN CONSUMPTION: each parser reports the character range it consumed, and whatever is
left over — minus a small noise list — comes back as `unrecognized`. That is a
structural guarantee rather than a promise. A parser that silently ignored half a line
would leave that half in `unrecognized`, so the pane shows it and the director can see
the extractor did not understand.

⚠️ THE SEAM IS `LineExtractor`, SO A MODEL EXTRACTOR SLOTS IN BEHIND IT LATER. The
protocol takes a line plus the session's answers so far and returns a `LineExtraction`.
A model implementation would satisfy the same protocol and the pane would not change.
NOT BUILT — by ruling.

⚠️ IT RESOLVES NOTHING ITSELF. Vault phrases go to `product_name_resolver`, print names
to `legacy_print_resolver`, parties to `party_resolver`. All three return candidate sets
and a discriminator; this module carries those sets through to the caller as `picks`
rather than choosing. The one rule it must not break is the one those resolvers exist
to enforce: never pick.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, time
from enum import Enum
from typing import Protocol

from sqlalchemy.orm import Session

from app.services.capture.prefix_resolve import (
    KINDS_FUNERAL_HOME,
    KINDS_VAULT,
)
from app.services.capture.schema import (
    SERVICE_LOCATION_GRAVESIDE,
    NAMEPLATE_DATE_FORMATS,
    EQUIPMENT_PACKAGES,
    SERVICE_LOCATIONS,
)
from app.services.personalization.questions import (
    ANSWER_COVER_EMBLEM_ONLY,
    ANSWER_LEGACY_PRINT,
    ANSWER_LIFES_REFLECTIONS,
    ANSWER_NAMEPLATE_AND_COVER_EMBLEM,
    ANSWER_NAMEPLATE_AND_LIFES_REFLECTIONS,
    ANSWER_NAMEPLATE_ONLY,
    ANSWER_NONE,
    LEGACY_SERIES_CUSTOM,
    LEGACY_SERIES_STANDARD,
    QUESTION_PERSONALIZATION,
    VINYL_ANSWERS,
    VINYL_BEARING_ANSWERS,
)


@dataclass(frozen=True)
class Pick:
    """An ambiguous resolution the director has to settle.

    ⚠️ `options` CARRIES LABELS, NOT IDS ALONE. A numbered pick renders these, and
    "St. Mary's / St. Mary's" is not a choice — `PartyCandidate.label` puts the town in.
    """

    field_id: str
    phrase: str
    #: (value_to_store, label_to_show)
    options: tuple[tuple[str, str], ...]
    discriminator: str | None


@dataclass(frozen=True)
class LineExtraction:
    """What one typed line yielded."""

    line: str
    #: field_id -> value. Only unambiguous hits land here.
    values: dict[str, object] = field(default_factory=dict)
    #: Ambiguous hits, awaiting a numbered pick. NOT in `values`.
    picks: tuple[Pick, ...] = ()
    #: ⚠️ TEXT THE EXTRACTOR COULD NOT PLACE. Shown to the director, never dropped.
    unrecognized: tuple[str, ...] = ()
    #: Values chosen on the director's behalf, each with its one alternative.
    switches: tuple[Switch, ...] = ()
    #: ⚠️ RELATIVE TO THIS LINE. `extract_text` shifts them by the segment's offset.
    spans: tuple[TextSpan, ...] = ()

    @property
    def understood_nothing(self) -> bool:
        return not self.values and not self.picks


@dataclass(frozen=True)
class TextSpan:
    """One stretch of the director's text, and what the engine did with it.

    ⚠️ ADDED 2026-10-15 SO THE BAR CAN SHOW WHAT WAS UNDERSTOOD IN THE TEXT ITSELF.
    James: "The extraction response returns the claimed spans: field, start, end,
    state." `start`/`end` are offsets into the WHOLE typed text, not into a segment —
    the pane renders over what the director can see.

    ⚠️ `field_ids` IS A TUPLE BECAUSE ONE SPAN MAY FEED TWO FIELDS. "1948 to 2026" is
    one claim and two years. It is empty for `unrecognized`, which by definition fed
    nothing.
    """

    start: int
    end: int
    #: "captured" | "unrecognized". A third, "conflict", is applied one layer up by
    #: `session_service`, which is where conflicts are known — `extract_text` reads
    #: text and does not evaluate applicability.
    state: str
    field_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Switch:
    """A value we CHOSE for the director, with the one alternative, one click away.

    ⚠️ THIS IS NOT A PICK AND THE DIFFERENCE IS THE WHOLE POINT. A pick means "I do
    not know which you meant" and blocks the field. A switch means "I took the
    common one; here is the other" — the field is CAPTURED and the order can be
    completed without touching it. Ruled 2026-10-13: a vault ambiguous ONLY by form
    resolves to the burial vault and offers the urn vault as a switch, because the
    burial vault is what an office means nine times in ten and a pick there is a
    question with a known answer.

    ⚠️ `to_value` IS WHAT GETS STORED, and it is validated against this offer by the
    endpoint — so the one-click control cannot be used to set an arbitrary value.
    """

    field_id: str
    #: What we chose, for the pane to show as the current reading.
    from_label: str
    #: The alternative: stored value and the label on the control.
    to_value: str
    to_label: str


class LineExtractor(Protocol):
    """⚠️ THE SEAM. A model-backed extractor implements this and nothing else changes."""

    def extract_line(
        self,
        db: Session,
        *,
        tenant_id: str,
        line: str,
        answers: dict[str, object],
        gating: dict[str, object] | None = None,
    ) -> LineExtraction: ...


# ── vocabularies, derived not typed ──────────────────────────────────────

#: Equipment packages, by the words a director actually says. ⚠️ ORDERED LONGEST-INTENT
#: FIRST: "lowering device and grass" must be tried before "lowering device", or
#: "device and grass" resolves to the device alone and the grass becomes unrecognized.
#: ⚠️ STORES IDS, NOT LABELS, SINCE 2026-10-12. This was the ONE enum field whose
#: extractor wrote a display label ("Tent Only") while every other wrote an id — so
#: nothing could tell, per field, whether a stored value was an id or a name, which
#: is why `rows.py` ever did `str(v)` and why `service_location` reached James's
#: screen as `funeral_home`. Ruled: fix it at the source.
#:
#: ⚠️ THE IDS ARE LOOKED UP BY LABEL FROM `EQUIPMENT_PACKAGES`, NOT RETYPED. The
#: label strings below are the exact ones this table used to store, so a mistyped
#: label raises a KeyError at import rather than silently writing a value no
#: `label_for` can resolve.
_EQ_ID: dict[str, str] = {label: ident for ident, label in EQUIPMENT_PACKAGES}

_EQUIPMENT: tuple[tuple[str, str], ...] = (
    (r"full\s+(?:equipment|setup|set\s*up)", _EQ_ID["Full Equipment"]),
    (r"(?:lowering\s+)?device\s+(?:and|&|\+)\s+grass(?:\s+mats)?", _EQ_ID["Lowering Device & Grass"]),
    (r"grass\s+(?:and|&|\+)\s+(?:lowering\s+)?device", _EQ_ID["Lowering Device & Grass"]),
    (r"tent\s+only", _EQ_ID["Tent Only"]),
    (r"just\s+(?:a\s+|the\s+)?tent", _EQ_ID["Tent Only"]),
    (r"(?:lowering\s+)?device\s+only", _EQ_ID["Lowering Device Only"]),
    (r"just\s+(?:the\s+)?(?:lowering\s+)?device", _EQ_ID["Lowering Device Only"]),
    (r"vault\s+placer", _EQ_ID["Vault Placer"]),
    # ⚠️ CHAIRS ARE NOT IN THIS TABLE, AND THEY USED TO BE. They are recognised by
    # `_chairs` instead, because a chair phrase yields TWO values — the package and
    # the count — from ONE span, and this table maps one pattern to one value.
    # `_year_pair` is the same shape and the same precedent. Leaving the old
    # `extra\s+chairs` entry here as well would mean two recognisers for one phrase,
    # the second reporting the first as a re-statement ("extra chairs —
    # cemetery_equipment is already 'extra_chairs'").
    (r"no\s+equipment|don'?t\s+need\s+equipment", ANSWER_NONE),
)

#: Chairs included in every graveside package, per the price list: the per-unit
#: charge is "Extra Chairs (Over 8)", so eight are already in the setup.
#:
#: ⚠️ IT IS THE PIVOT BETWEEN THE TWO PHRASINGS James RULED (2026-10-14) AND NOT A
#: TUNABLE. "12 chairs" is a TOTAL and bills 4; "extra chairs 4" is already the
#: EXTRA and bills 4. Both readings need this number and they need the same one.
CHAIRS_INCLUDED = 8

#: Chair phrasings, longest-intent first. Each yields `(count_or_None, span)`.
#:
#: ⚠️ THE TWO GROUPS ANSWER DIFFERENT QUESTIONS AND MUST NOT BE MERGED. An "extra"
#: pattern's number is the extra count as given; a bare "N chairs" is the total and
#: has `CHAIRS_INCLUDED` subtracted. A single pattern with an optional "extra" would
#: have to decide which arithmetic to apply after matching, from the presence of a
#: word it had already discarded.
_CHAIRS_EXTRA: tuple[str, ...] = (
    r"extra\s+chairs?\s*:?\s*(\d+)",
    r"(\d+)\s+extra\s+chairs?",
    r"chairs?\s+over\s+%d\s*:?\s*(\d+)" % CHAIRS_INCLUDED,
)
_CHAIRS_TOTAL: tuple[str, ...] = (
    r"(\d+)\s+chairs?\b",
    r"chairs?\s*:?\s*(\d+)\b",
)
#: The package with no number at all — "extra chairs", "we'll need extra chairs".
_CHAIRS_BARE = r"extra\s+chairs?"

#: Personalization answers by phrasing. ⚠️ COMBINATIONS BEFORE SINGLES, same reason.
_PERSONALIZATION: tuple[tuple[str, str], ...] = (
    (r"nameplate\s+(?:and|&|\+)\s+(?:cover\s+)?emblem", ANSWER_NAMEPLATE_AND_COVER_EMBLEM),
    (r"nameplate\s+(?:and|&|\+)\s+(?:a\s+)?(?:life'?s\s+reflections|vinyl)",
     ANSWER_NAMEPLATE_AND_LIFES_REFLECTIONS),
    (r"(?:cover\s+)?emblem\s+only|just\s+(?:a\s+|the\s+)?(?:cover\s+)?emblem",
     ANSWER_COVER_EMBLEM_ONLY),
    (r"nameplate\s+only|just\s+(?:a\s+|the\s+)?nameplate", ANSWER_NAMEPLATE_ONLY),
    (r"legacy\s+(?:series\s+)?print|legacy\s+print", ANSWER_LEGACY_PRINT),
    (r"life'?s\s+reflections|vinyl", ANSWER_LIFES_REFLECTIONS),
    (r"no\s+personalization|nothing\s+on\s+it|plain", ANSWER_NONE),
)

#: Life's Reflections® symbols, by the words a director says. ⚠️ THE OFFICE SAYS
#: "VINYL" (James, 2026-10-12), and the answer vocabulary already accepted it — what
#: was missing is the SYMBOL. `lifes_reflections_symbol` was a template field with NO
#: EXTRACTOR AT ALL (grep count: 0), so "vinyl cross" set the answer and dropped
#: "cross" into `unrecognized`. Measured before building, not assumed.
#:
#: ⚠️ THE TABLE ORDER IS COSMETIC, AND A BREAK TEST IS WHY THIS COMMENT SAYS SO.
#: It first read "ORDERED LONGEST-INTENT FIRST, and the reason is 'patriotic /
#: american flag'". Swapping those two rows left ALL 29 TESTS GREEN — because the
#: selection rule below is "the match that reaches FURTHEST wins" (max end offset),
#: which makes order irrelevant for any two patterns that do not match the identical
#: span. "patriotic" and "american flag" never compete: only one of them matches a
#: given phrase.
#:
#: So the longest-match RULE is load-bearing and the ORDERING is not. Order only
#: decides an exact tie — same start AND same end — which no two rows here produce.
#: Reading the order as the guarantee is the mistake; it is listed longest-first
#: because that reads well, not because anything depends on it.
#:
#: ⚠️ IDS LOOKED UP FROM `VINYL_ANSWERS`, NOT RETYPED, so a phrase cannot store an id
#: the schema has no label for. `test_enum_display.py`'s totality ratchet reads this
#: table, so a new phrase with a bad id fails there by name.
_VINYL_SYMBOLS: tuple[tuple[str, str], ...] = tuple(
    (pat, ident) for pat, ident in (
        (r"star\s+of\s+david", "star_of_david"),
        (r"praying\s+hands", "praying_hands"),
        (r"american\s+flag", "patriotic_american_flag"),
        (r"patriotic", "patriotic_american_flag"),
        (r"masonic|mason", "masonic"),
        (r"floral|flowers?", "floral"),
        (r"\bcross\b", "cross"),
        (r"\bdove\b", "dove"),
        (r"\bflag\b", "patriotic_american_flag"),
    )
    if ident in VINYL_ANSWERS
)
assert len({i for _, i in _VINYL_SYMBOLS}) == 7, (
    "⚠️ SEVEN OF THE EIGHT SYMBOLS HAVE PHRASES. `other` is deliberately absent: it "
    "means 'a symbol not on the list, specified in notes', so there is no word for a "
    "director to say that should resolve TO it — a line mentioning some other symbol "
    "must come back unrecognized and be asked about, not silently filed as `other`."
)

_LEGACY_SERIES: tuple[tuple[str, str], ...] = (
    (r"custom\s+(?:series|artwork|print)|legacy\s+custom", LEGACY_SERIES_CUSTOM),
    (r"standard\s+(?:series|print)?|off\s+the\s+poster", LEGACY_SERIES_STANDARD),
)

#: `service_location` vocabulary, derived from the engine's tuple so a typo here
#: cannot invent a value no condition compares against.
_LOCATION_WORDS: dict[str, str] = {
    "church": "church",
    "funeral home": "funeral_home",
    "funeral-home": "funeral_home",
    "graveside": "graveside",
    "grave side": "graveside",
    "at the grave": "graveside",
}

_DATE_FORMAT_WORDS: tuple[tuple[str, str], ...] = (
    (r"years?\s+only|just\s+(?:the\s+)?years?", "years"),
    (r"numeric|all\s+numbers?|digits", "numeric"),
    (r"written\s+out|spelled\s+out|written", "written"),
)

#: `gating` key: is the last word of this line also the last word the director has
#: typed? True unless the caller knows a later segment follows. See the abbreviation
#: pass for why the final word is left alone.
GATING_TAIL_OPEN = "tail_open"

#: Words that carry no field and must not be reported as unrecognized.
#:
#: ⚠️ THE LIST MOVED TO `capture/noise.py` AND THIS NAME IS NOW AN ALIAS, so the six use
#: sites below are untouched. It moved because a ratchet forbids any other module
#: importing THIS one — the E6 guarantee — and `held.py` needs the same list for clause
#: 5's suggestions. Same frozenset object, read from a leaf module both can import.
from app.services.capture.noise import NOISE_WORDS as _NOISE_WORDS


def _free(spans: list[tuple[int, int]], a: int, b: int) -> bool:
    """Is `[a, b)` unclaimed by every span recorded so far?

    ⚠️ HALF-OPEN, SO ABUTTING IS NOT OVERLAPPING. `(0, 5)` and `(5, 9)` are adjacent
    and both legal; only a shared character counts.
    """
    return not any(a < end and start < b for start, end in spans)


class _Spans(list):
    """The claim list, which now also remembers WHICH FIELD each interval fed.

    ⚠️ A `list` SUBCLASS SO NOTHING ELSE HAS TO CHANGE. `_free`, `_unclaimed_slices`,
    `_leftover_pairs` and four inline loops all walk `spans` as `(a, b)` pairs;
    turning it into a list of triples would have rewritten every one of them, and the
    span algebra is the part of this module least worth disturbing.

    ⚠️ ATTRIBUTION IS OPTIONAL BY CONSTRUCTION, AND THAT IS DELIBERATE SEQUENCING
    rather than laziness. CLAUDE.md §11 is explicit that a required parameter added
    to a function with non-compliant callers raises nothing at import and `TypeError`
    at whatever hour the path is next taken. There are 37 claim sites here. So the
    parameter lands optional, the callers get filled, and
    `test_every_captured_value_has_a_span.py` is the ratchet that keeps the
    unattributed count at zero — with a positive control, because "no unattributed
    claims" is also what an instrument that recorded nothing would report.
    """

    def __init__(self, *args):
        super().__init__(*args)
        #: (start, end) -> field_id, for the claims that named one.
        self.fields: dict[tuple[int, int], str] = {}


def _claim(
    spans: list[tuple[int, int]], a: int, b: int, field: str | None = None
) -> bool:
    """Claim `[a, b)` for one field, or REFUSE because another field has it.

    ⚠️ THE RULE THIS ENFORCES: NO SPAN FEEDS TWO FIELDS. Ruled 2026-10-12 after
    James walked production and found "start an order for Hopkins Funeral Home" had
    set `service_location = funeral_home` — the words "Funeral Home" were read once
    as part of the party's NAME and again as the place the service is held, so the
    Service row claimed an answer he had never given.

    ⚠️ AND A REFUSED CLAIM MUST NOT SET A VALUE, which is why callers check the
    return BEFORE writing. Appending the span after writing the value — the shape
    this replaces — records the overlap without preventing it.
    """
    if not _free(spans, a, b):
        return False
    if field is not None and isinstance(spans, _Spans):
        # ⚠️ ALWAYS A TUPLE, BECAUSE A SPAN MAY LEGITIMATELY FEED TWO FIELDS. "1948 to
        # 2026" is one claim and two years; "12 chairs" is one claim, a package and a
        # count. Storing a bare string would force those two sites to pick a winner,
        # and the pane would tint the span while tying it to only one of the rows it
        # actually filled. This is the one place the no-span-feeds-two-fields rule is
        # deliberately relaxed, and it is relaxed by a single recogniser each time.
        spans.fields[(a, b)] = field if isinstance(field, tuple) else (field,)
    spans.append((a, b))
    return True


def _mark(
    spans: list[tuple[int, int]], m: re.Match, field: str | None = None
) -> bool:
    """`_claim` for a regex match. Returns False when the span is already taken."""
    return _claim(spans, m.start(), m.end(), field)


def _evidence(
    frag: str, frag_start: int, parsed: dict, field: str = ""
) -> tuple[int, int]:
    """Where in the LINE the parser actually read its value from.

    ⚠️ THIS EXISTS BECAUSE CLAIMING THE WHOLE FRAGMENT WAS A LIVE DEFECT, MEASURED ON
    PRODUCTION FROM JAMES'S OWN SENTENCE (2026-10-20). `order hopk monti thursday 10
    am st. mary's` left `hopk monti thursday` as one leftover; `parse_date` read
    "thursday" out of it and the caller then claimed all nineteen characters for
    `service_date`. That did two separate harms at once:

      1. It told the director that "hopk" and "monti" fed a date. They fed nothing.
      2. `_claim` refuses an overlapping span, so the funeral home and the vault
         became UNCLAIMABLE — the span that lied is also the span that blocked.

    So the two symptoms James reported were one cause, and narrowing the claim is
    what fixes both. The parsers now return `span`; see `_date_result`.

    ⚠️ IT FALLS BACK TO THE WHOLE FRAGMENT WHEN NO SPAN CAME BACK, which is the old
    behaviour: wide, but never wrong about position. A parser that cannot say where it
    read from must not have a position invented for it.
    """
    span = parsed.get("span")
    if (
        isinstance(span, (tuple, list))
        and len(span) == 2
        and all(isinstance(x, int) for x in span)
        and 0 <= span[0] < span[1] <= len(frag)
    ):
        return (frag_start + span[0], frag_start + span[1])
    return (frag_start, frag_start + len(frag))


def _leftovers(line: str, spans: list[tuple[int, int]]) -> tuple[str, ...]:
    """The text no parser claimed, as trimmed fragments.

    ⚠️ THIS IS THE "NEVER DROPPED" GUARANTEE, AND IT IS STRUCTURAL. Every parser
    records its span; this returns the complement. A parser that matched nothing and
    said nothing still leaves its text here, so silence is visible.

    ⚠️ NOISE WORDS ARE REMOVED FROM FRAGMENTS, NOT FROM THE LINE. Removing them from
    the line first would merge two unrelated fragments into one — "for Hopkins ... and
    the Smith" would read as one unplaced phrase.

    ⚠️ DELEGATES TO `_leftover_pairs` RATHER THAN RECOMPUTING. It held a second copy
    of the same span-complement walk until 2026-10-07; two copies of a rule about
    which text is unclaimed is one copy too many, and the drift would have been
    invisible because both would have looked right in isolation.
    """
    return tuple(kept for kept, _ in _leftover_pairs(line, spans))


def _leftover_pairs(line: str, spans: list[tuple[int, int]]) -> tuple[tuple[str, str], ...]:
    """`(noise-stripped fragment, the fragment exactly as typed)` for each leftover.

    ⚠️ NOISE-WORD REMOVAL IS A HINT, NOT A FILTER, AND THAT IS THE RULE THIS
    FUNCTION EXISTS TO MAKE POSSIBLE. `_NOISE_WORDS` holds words a director says
    AROUND a value — and three of them are also words INSIDE catalog names
    (`cemetery`, `burial`, `vault`; measured 2026-10-07). Stripping `burial` and
    `vault` is what lets "Continental Burial Vault" reach the family phrase, so the
    list is right; stripping `cemetery` deleted the first word of the only two
    variants named "Cemetery Tent - ...", and "cemetery tent single" came back
    unrecognized.

    So a caller resolves BOTH readings and lets the catalog decide: the stripped one
    first, then, only if that reached nothing, the line as the director typed it.
    Returning the pair rather than switching behaviour keeps the stripped form
    primary, which is what every other field depends on.

    ⚠️ AND THE RAW FORM IS THE ONLY ONE WHOSE SPAN CAN BE FOUND IN THE LINE. The
    stripped fragment is a REJOIN of non-adjacent words, so `line.find(kept)` returns
    -1 whenever a noise word sat in the middle — "Loved and Cherished 24" rejoins to
    "Loved Cherished 24", which appears nowhere in the line. Any caller marking a
    span marks the raw one.
    """
    pairs: list[tuple[str, str]] = []
    for frag in out_fragments(line, spans):
        words = [w for w in re.split(r"[^A-Za-z0-9'&\-]+", frag) if w]
        kept = [w for w in words if w.casefold() not in _NOISE_WORDS]
        if kept:
            pairs.append((" ".join(kept), frag.strip()))
    return tuple(pairs)


def _narrower(alt, base) -> bool:
    """Is `alt` a strictly better answer than `base`?

    ⚠️ "BETTER" IS FEWER CANDIDATES, NOT MERELY SOME. The first version of this read
    "take the raw reading only when the stripped one matched NOTHING", and it left the
    reported defect half-fixed: "Veteran burial vault" strips to "Veteran", which after
    r207 reaches TWO candidates, so the raw reading was never consulted and the pane
    asked "burial or urn?" about a line that had already said burial. The stripped
    reading reaching something is not evidence it reached the right something.

    ⚠️ ZERO IS NEVER BETTER. A raw fragment is usually a whole clause ("we need an
    oversized vault") that matches nothing; it must not displace a good stripped hit.
    """
    if not alt.candidates:
        return False
    if not base.candidates:
        return True
    return len(alt.candidates) < len(base.candidates)


def _unclaimed_slices(
    line: str, spans: list[tuple[int, int]]
) -> tuple[tuple[int, str], ...]:
    """`(offset_in_line, slice)` for each unclaimed run of the line.

    ⚠️ THE OFFSET IS THE POINT. A pass that scans a slice finds a match at a position
    relative to THAT SLICE, and claiming it needs the position in the LINE. Returning
    the slice alone forces the caller to `line.find()` it back, which is wrong the
    moment the same words appear twice.
    """
    out: list[tuple[int, str]] = []
    cur = 0
    for a, b in sorted(spans):
        if a > cur:
            out.append((cur, line[cur:a]))
        cur = max(cur, b)
    if cur < len(line):
        out.append((cur, line[cur:]))
    return tuple(out)


def _describe_spans(line: str, spans) -> tuple["TextSpan", ...]:
    """Every claim as a captured span, plus every real leftover as an unrecognized one.

    ⚠️ THE UNRECOGNIZED SPANS ARE BUILT THE SAME WAY `unrecognized` IS, and that is
    deliberate rather than convenient. `_leftover_pairs` drops a slice with no
    non-noise word in it, which is why "order for hopkins" reports nothing unplaced —
    "order" and "for" are noise. A span renderer that underlined every unclaimed
    slice would put a dotted line under the first two words of almost every order.
    Same predicate, same answer, one rule.

    ⚠️ IT MARKS THE RAW SLICE, NOT THE NOISE-STRIPPED REJOIN, as `_leftover_pairs`'s
    own docstring requires: the stripped fragment is a rejoin of non-adjacent words
    and `line.find(kept)` returns -1 whenever a noise word sat in the middle.

    ⚠️ A CLAIM WITH NO FIELD IS NOT REPORTED AS CAPTURED. Re-statements claim their
    span so the words do not land in the unplaced list, but they filled nothing — so
    they are neither captured nor unrecognized, and the bar leaves them plain.
    """
    out: list[TextSpan] = []
    attributed = getattr(spans, "fields", {})
    for (a, b), field_ids in attributed.items():
        out.append(TextSpan(start=a, end=b, state="captured", field_ids=tuple(field_ids)))

    # ⚠️ ONE SPAN PER WORD, NOT ONE PER SLICE, BY RULING (James, walk 2026-10-20):
    # "unrecognized spans are word-level". His screenshot showed a single dotted block
    # covering three words, which reads as one unknown phrase and says nothing about
    # which word the engine could not place. A slice is whatever happened to be left
    # between two claims; it is not a unit of meaning.
    #
    # ⚠️ AND IT IS WHY THE NOISE WORDS STOP BEING UNDERLINED AT ALL. The old code
    # tested the slice for ANY non-noise word and then marked the WHOLE slice — so
    # "order hopk" put a dotted line under "order" too, a word the engine deliberately
    # ignores. Per word, the test and the mark are the same unit, and "order" is
    # simply never marked.
    for start, slice_ in _unclaimed_slices(line, spans):
        for m in re.finditer(r"[A-Za-z0-9'&\-]+", slice_):
            if m.group(0).casefold() in _NOISE_WORDS:
                continue
            out.append(
                TextSpan(start=start + m.start(), end=start + m.end(),
                         state="unrecognized")
            )
    return tuple(sorted(out, key=lambda s: (s.start, s.end)))


def out_fragments(line: str, spans: list[tuple[int, int]]) -> tuple[str, ...]:
    """The raw unclaimed slices of the line, before any noise-word removal."""
    taken = sorted(spans)
    out: list[str] = []
    cur = 0
    for a, b in taken:
        if a > cur:
            out.append(line[cur:a])
        cur = max(cur, b)
    if cur < len(line):
        out.append(line[cur:])
    return tuple(out)


def _year_pair(line: str) -> tuple[tuple[str, str], tuple[int, int]] | None:
    """`1948-2026` / `1948 to 2026` -> (birth year, death year) + span.

    ⚠️ YEARS ONLY, AND IT DOES NOT SET THE DATE FORMAT. A director saying "1948 to
    2026" has given two dates; whether the NAMEPLATE is lettered years-only is a
    separate instruction they have to give, and inferring it from how they typed would
    be reading a format preference out of shorthand.
    """
    m = re.search(r"\b(1[89]\d{2}|20[0-4]\d)\s*(?:-|–|—|to)\s*(1[89]\d{2}|20[0-4]\d)\b", line)
    if not m:
        return None
    a, b = int(m.group(1)), int(m.group(2))
    if b < a:
        return None
    return (m.group(1), m.group(2)), (m.start(), m.end())


def _explicit_name(line: str) -> tuple[str, tuple[int, int]] | None:
    """A decedent name, ONLY behind an explicit marker.

    ⚠️ NEVER FROM BARE CAPITALISATION. "Hopkins Funeral Home" is capitalised and is not
    a decedent; a greedy name parser would steal the funeral home on the opening line,
    which is the one line most likely to contain both. Markers only.
    """
    m = re.search(
        r"\b(?:decedent|deceased|for the late|the late|name is|named)\s*(?:is\s+|:\s*)?"
        r"([A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+){1,2})",
        line,
    )
    if not m:
        return None
    return m.group(1).strip(), (m.start(), m.end())


#: A surname given on its own, behind a marker that says it is one.
#:
#: ⚠️ ONE WORD, AND ONLY BEHIND A MARKER. Ruled 2026-10-13 after James's walk:
#: directors often give just a surname, and "last name Smith" was landing in Not
#: Understood because `_explicit_name` demands two or more capitalised words.
#:
#: ⚠️ LOWERCASE IS ALLOWED HERE AND NOWHERE ELSE. What makes that safe is the
#: marker — "last name smith" says in words that a name follows. A bare lowercase
#: word elsewhere in the sentence is still not a name, which is why this pattern
#: cannot be relaxed into a general one.
#:
#: ⚠️ THE TRAILING `family` FORM IS LISTED TWICE ON PURPOSE. "the Smith family" and
#: "Smith family" differ only by the article, and a single optional-`the` pattern
#: would also match a bare "family".
#: Words a marker-led span must never END on.
#:
#: ⚠️ THE TEST IS "WOULD THE NORMALIZER DELETE IT", NOT "IS IT A COMMON WORD". These
#: are the separator words `party_resolver.normalize` strips, which is why a span
#: ending on one resolves to the same record as the span without it — and therefore
#: claims a word it has no reason to own.
_SPAN_TAIL_STOPS = frozenset(
    {"the", "a", "an", "and", "of", "in", "on", "at", "to", "for", "with"}
)


#: ⚠️ ONE OR TWO WORDS SINCE 2026-10-14, BY RULING, AND THE SECOND WORD IS WHY THIS
#: PATTERN CHANGED AT ALL. Measured on testco the day before: "decedent mary smith"
#: captured `mary` and left `smith` in Not understood; "the mary smith family"
#: captured `smith` and left `mary`. That is worse than capturing nothing — the pane
#: shows a name, so it looks like it understood, and half the name is sitting in the
#: unplaced list where nobody reads it. James: "after a marker take the whole name
#: span... nothing orphaned into Not understood."
#:
#: ⚠️ STILL ONLY BEHIND A MARKER, AND BARE LOWERCASE IS STILL UNPLACED. The ruling
#: says so in terms, and the marker is the entire warrant for reading a lowercase
#: word as a name — see `_explicit_name` for why capitalisation alone cannot be one.
#:
#: ⚠️ THE SECOND WORD IS OPTIONAL AND GREEDY, WHICH NEEDS `_trim_absorbed_word`. A
#: one-word name followed by anything else — "decedent smith friday 11am" — would
#: otherwise become "smith friday".
_SURNAME_WORD = r"[A-Za-z][A-Za-z'\-]*"
_SURNAME_NAME = rf"({_SURNAME_WORD}(?:\s+{_SURNAME_WORD})?)"
_SURNAME_CLAUSE = re.compile(
    r"\b(?:"
    rf"last\s+name(?:\s+is)?\s+{_SURNAME_NAME}"
    rf"|name\s+is\s+{_SURNAME_NAME}"
    rf"|decedent\s+{_SURNAME_NAME}"
    rf"|the\s+{_SURNAME_NAME}\s+family\b"
    # ⚠️ THE BARE `X family` FORM TAKES ONE WORD ONLY, AND MAKING IT TWO BROKE A TEST
    # IMMEDIATELY. Every other alternative here is bounded on the LEFT by its marker;
    # this one has no marker in front of it, so a two-word group extends BACKWARDS
    # into the sentence. Measured 2026-10-14: "order for riverside Keegan family"
    # captured the decedent as "riverside Keegan" — it ate the funeral home, which is
    # the exact failure `_trim_absorbed_word` cannot help with because the absorbed
    # word is at the START of the span and the trim only looks at the end.
    #
    # ⚠️ AND THE RULING DOES NOT ASK FOR IT. James's family example is "the mary smith
    # family", which is bounded on both sides and is the alternative above.
    rf"|({_SURNAME_WORD})\s+family\b"
    r")",
    re.I,
)

#: ⚠️ MOVED TO `noise.py` ON 2026-10-29 and aliased here under its old private
#: name so every use below is unchanged. It left because clause 2 needs the same
#: closed class and the E6 ratchet forbids importing this module — see
#: `noise.py` for the full argument. One list, two readers.
from sqlalchemy.exc import SQLAlchemyError
from app.services.capture.names import bare_name_before_a_term
from app.services.capture.noise import FUNCTION_WORDS as _FUNCTION_WORDS


#: Words a two-word name span must not absorb as its second word.
#:
#: ⚠️ IT IS THE VOCABULARY THIS MODULE ALREADY RECOGNISES, not a theory about names.
#: A weekday, a month or a separator has a job in some other recogniser; a surname
#: is an open set and no rule about its shape is safe. See `_trim_absorbed_word`.
_NOT_A_NAME_WORD = frozenset(
    {
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
        "mon", "tue", "tues", "wed", "thu", "thur", "thurs", "fri", "sat", "sun",
        "january", "february", "march", "april", "may", "june", "july", "august",
        "september", "october", "november", "december",
        "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct",
        "nov", "dec",
        "today", "tomorrow", "yesterday", "morning", "afternoon", "evening",
        "am", "pm", "noon", "midnight",
        "vault", "cemetery", "service", "burial", "graveside", "chapel", "church",
        "funeral", "home", "section", "lot", "space", "grave", "plot",
        "nameplate", "emblem", "print", "vinyl", "equipment", "tent", "chairs",
        "next", "this", "last",
    }
    | _SPAN_TAIL_STOPS
    | _FUNCTION_WORDS
)


def _chairs(line: str) -> tuple[int | None, tuple[int, int]] | None:
    """The extra-chair count and the span that said it, or None if no chair phrase.

    Returns `(count, span)`; `count` is None when chairs were asked for without a
    number, which is a GAP rather than a zero — see `extra_chairs_count` in
    `schema.py`.

    ⚠️ ONE SPAN, TWO VALUES, WHICH IS WHY THIS IS A FUNCTION AND NOT A ROW IN
    `_EQUIPMENT`. "12 chairs" settles both the package and the quantity, and the span
    rule is per-span rather than per-field — `_year_pair` does the same thing for a
    birth and a death year and is the precedent this follows.

    ⚠️ "EXTRA" PATTERNS BEFORE TOTALS, BECAUSE "extra chairs 4" CONTAINS "chairs 4".
    Tried the other way round, the extra count is read as a total and 4 chairs bills
    as zero — the arithmetic silently inverts and the order is $20 light.
    """
    for pat in _CHAIRS_EXTRA:
        m = re.search(pat, line, re.I)
        if m:
            return int(m.group(1)), (m.start(), m.end())
    for pat in _CHAIRS_TOTAL:
        m = re.search(pat, line, re.I)
        if m:
            # ⚠️ CLAMPED AT ZERO RATHER THAN ALLOWED NEGATIVE. "6 chairs" is fewer
            # than the package includes; the extra count is 0 and `evaluate_typed`
            # raises that as a conflict rather than billing -2 chairs.
            return max(0, int(m.group(1)) - CHAIRS_INCLUDED), (m.start(), m.end())
    m = re.search(_CHAIRS_BARE, line, re.I)
    if m:
        return None, (m.start(), m.end())
    return None


def _surname_clause(
    line: str, belongs_elsewhere=None
) -> tuple[str, tuple[int, int]] | None:
    """The surname and the span of the whole clause, marker included.

    ⚠️ THE SPAN COVERS THE MARKER TOO. Claiming only the name would leave "last
    name" unclaimed, and those two words would then be reported as text the engine
    could not place — which is half of what James saw.
    """
    m = _SURNAME_CLAUSE.search(line)
    if m is None:
        return None
    gi = next((i for i, g in enumerate(m.groups(), start=1) if g), None)
    if gi is None:
        return None
    name = m.group(gi)
    start, end = m.start(), m.end()

    trimmed = _trim_absorbed_word(name, belongs_elsewhere)
    if trimmed != name and m.end(gi) == end:
        # ⚠️ THE SPAN SHRINKS WITH THE NAME, AND FORGETTING THAT IS WORSE THAN THE BUG
        # IT FIXES. A trimmed name over an untrimmed span claims "friday" as part of
        # the decedent's name clause — so the date recogniser cannot see it AND it is
        # not reported as unplaced text either. That is a silent drop, which is the
        # one outcome the walk notes rule out.
        #
        # ⚠️ ONLY WHEN THE NAME ENDS THE MATCH. In "the mary smith family" the clause
        # ends on `family`, which bounds the name on both sides — nothing was
        # over-absorbed there and the two words are both the name.
        end -= len(name) - len(trimmed)
        name = trimmed

    return name, (start, end)


def _trim_absorbed_word(name: str, belongs_elsewhere=None) -> str:
    """Drop a second word the two-word form should not have taken.

    ⚠️ THE TWO-WORD FORM IS GREEDY AND THE SEGMENT IS NOT ALWAYS A CLAUSE. "decedent
    mary smith" is the case James ruled for, and "decedent smith friday 11am" is the
    same pattern against a sentence with no comma in it — there the second word is a
    weekday and taking it would name the decedent "smith friday". `segments()` splits
    on commas and a few correction words, so most sentences arrive pre-bounded; the
    ones that do not are exactly the ones a greedy parser gets wrong.

    ⚠️ THE TEST IS A CLOSED LIST OF WORDS THAT ARE SOMETHING ELSE, NOT A GUESS AT
    WHAT A NAME LOOKS LIKE. Surnames are an open set — any rule of the form "a name
    does not look like this" is wrong about somebody's family. What IS closed is the
    vocabulary the rest of this module recognises: weekdays, months, and the
    separators `party_resolver.normalize` strips. A word in that set has a job
    already.

    ⚠️ ANYTHING WITH A DIGIT IN IT GOES TOO. "11am", "2pm" and "4" are not names and
    do not need enumerating one by one.

    ⚠️ `belongs_elsewhere` IS THE PER-TENANT HALF, ADDED BY RULING (James,
    2026-10-15): "Name spans never absorb a product, alias, funeral home or cemetery
    word." The frozenset above is closed vocabulary and cannot know that THIS tenant
    sells a Monticello; the predicate asks the resolvers. It is optional so the
    pure-text behaviour stays testable without a database.
    """
    parts = name.split()
    if len(parts) < 2:
        return name
    tail = parts[-1].lower()
    if tail in _NOT_A_NAME_WORD or any(ch.isdigit() for ch in tail):
        return " ".join(parts[:-1])
    if belongs_elsewhere is not None and belongs_elsewhere(parts[-1]):
        return " ".join(parts[:-1])
    return name


def _word_belongs_to_another_field(db, tenant_id: str, index) -> "callable":
    """Is this word the property of the catalog, a funeral home, or a cemetery?

    ⚠️ THE CATALOG AND THE PARTY RECORDS ARE TESTED DIFFERENTLY, AND THE ASYMMETRY IS
    THE WHOLE CARE IN THIS FUNCTION. Measured 2026-10-15 on both tenants:

        monticello   vault=2 on testco AND sunnycrest, fh=0
        smith        vault=0 everywhere, fh=1 on testco ("Smith & Sons Funeral Home")

    So a CATALOG hit is decisive — "monticello" is a vault word on every tenant that
    sells one, which is exactly James's example ("decedent smith monticello" ->
    Smith + Monticello) and it works on his tenant and on testco.

    ⚠️ A FUNERAL-HOME OR CEMETERY HIT IS NOT DECISIVE, AND TREATING IT AS ONE WOULD
    UNDO THE RULING OF 2026-10-14. That ruling says a surname is accepted behind a
    marker EVEN IF it appears inside a multi-word FH or cemetery record, and it was
    made because testco's commonest surname is a fragment of "Smith & Sons Funeral
    Home". A naive `resolve_funeral_home(word).candidates` test re-breaks "decedent
    mary smith" — the exact sentence he ruled on — on that tenant.

    So the party half fires only on a WHOLE-NAME match: the word must BE the record,
    not appear inside it. "Smith & Sons Funeral Home" is not "smith", so the surname
    survives; a cemetery actually named "Oakwood" would be caught.

    ⚠️ THIS SCOPING IS MINE, NOT JAMES'S. He listed four categories flatly. Applying
    the party half flatly contradicts his previous ruling on a tenant he tests on, so
    I implemented the reading that satisfies both and flagged the collision rather
    than silently picking one. See DECISIONS 2026-10-15.
    """
    from app.services.party_resolver import (
        normalize,
        resolve_cemetery,
        resolve_funeral_home,
    )
    from app.services.product_name_resolver import resolve as resolve_vault

    def belongs(word: str) -> bool:
        if resolve_vault(index, word).candidates:
            return True
        key = normalize(word)
        if not key:
            return False
        for res in (
            resolve_funeral_home(db, tenant_id, word),
            resolve_cemetery(db, tenant_id, word),
        ):
            for cand in res.candidates:
                if normalize(getattr(cand, "name", "")) == key:
                    return True
        return False

    return belongs


class DeterministicExtractor:
    """The E1 extractor. Rules only."""

    def extract_line(
        self,
        db: Session,
        *,
        tenant_id: str,
        line: str,
        answers: dict[str, object],
        gating: dict[str, object] | None = None,
    ) -> LineExtraction:
        """Extract one line.

        ⚠️ `answers` AND `gating` ARE DIFFERENT THINGS AND MUST STAY SEPARATE.

            answers   what has already been ANSWERED. Used for FIRST_WINS
                      re-statement reporting — "equipment is already Full
                      Equipment". Passing values here changes what the line is
                      allowed to overwrite.

            gating    context a GATED pass needs in order to fire at all, and
                      nothing else. The vinyl-symbol pass only runs when the
                      chosen personalization bears vinyl; a line that says only
                      "cross" cannot know that from its own words.

        ⚠️ WHY `gating` EXISTS. `extract_text` extracts each segment in isolation
        with `answers={}`, which is what makes LAST_WINS possible — a later
        segment must be free to overwrite an earlier one. But isolation also hid
        the personalization answer from the symbol gate, so a director typing
        "nameplate and vinyl, cross" had the WORD "cross" come back UNRECOGNIZED
        while the vinyl answer sat two segments earlier. Measured over HTTP on
        dev. Passing the accumulated answers as `answers` would have fixed the
        gate and broken LAST_WINS; two parameters is the whole repair.
        """
        from app.services.legacy_print_resolver import resolve as resolve_print
        from app.services.nl_creation.structured_parsers import parse_date, parse_time
        from app.services.party_resolver import (
            cemetery_rows,
            funeral_home_rows,
            normalize as _party_norm,
            resolve_cemetery,
            resolve_from_rows,
            resolve_funeral_home,
        )
        from app.services.product_name_resolver import build_index, resolve as resolve_vault

        spans = _Spans()
        values: dict[str, object] = {}
        picks: list[Pick] = []
        switches: list[Switch] = []
        low = line.casefold()

        restated: list[str] = []

        def once(field_id: str) -> bool:
            """A field not yet answered in this session.

            ⚠️ RETURNING FALSE USED TO LEAVE THE SPAN UNCLAIMED, AND THAT WAS WORSE THAN
            OVERWRITING. "tent only" after "full setup" left "tent" for a later parser,
            and the VAULT resolver claimed it — the catalog has `Cemetery Tent - Single`
            and `- Double`, so a correction to the equipment came back as an ambiguous
            VAULT pick. A silent ignore became a confusing question about a different
            field.

            The caller now records the re-statement explicitly (see `restated`), so the
            pane can say "cemetery_equipment is already Full Equipment" instead of
            offering tents as vaults. Changing an answer is a separate interaction and
            is NOT in this slice.
            """
            return field_id not in answers and field_id not in values

        def note_restated(field_id: str, m: re.Match) -> None:
            """Claim the span and record that the field is already settled."""
            _mark(spans, m, field_id)
            cur = answers.get(field_id, values.get(field_id))
            restated.append(f"{m.group(0).strip()} — {field_id} is already {cur!r}")

        # ── equipment package, every kind except chairs ──────────────────
        #
        # ⚠️ CHAIRS ARE NOT IN THIS TABLE AND ARE RECOGNISED FURTHER DOWN, after the
        # grave location. A chair phrase carries a NUMBER, and so does a grave
        # location; the ordering decides which of them owns a bare digit. See the
        # chairs block for the measurement that forced it.
        for pat, val in _EQUIPMENT:
            m = re.search(pat, low)
            if m:
                if once("cemetery_equipment"):
                    if _mark(spans, m, "cemetery_equipment"):
                        values["cemetery_equipment"] = val
                else:
                    note_restated("cemetery_equipment", m)
                break

        # ── personalization answer ───────────────────────────────────────
        for pat, val in _PERSONALIZATION:
            m = re.search(pat, low)
            if m:
                if once(QUESTION_PERSONALIZATION):
                    if _mark(spans, m, QUESTION_PERSONALIZATION):
                        values[QUESTION_PERSONALIZATION] = val
                else:
                    note_restated(QUESTION_PERSONALIZATION, m)
                break

        # ── legacy series ───────────────────────────────────────────────
        if once("legacy_series"):
            for pat, val in _LEGACY_SERIES:
                m = re.search(pat, low)
                if m:
                    if _mark(spans, m, "legacy_series"):
                        values["legacy_series"] = val
                    break

        # ── nameplate date format ───────────────────────────────────────
        if once("nameplate_date_format"):
            for pat, val in _DATE_FORMAT_WORDS:
                m = re.search(pat, low)
                if m:
                    assert val in NAMEPLATE_DATE_FORMATS, val
                    if _mark(spans, m, "nameplate_date_format"):
                        values["nameplate_date_format"] = val
                    break

        # ── named legacy print ──────────────────────────────────────────
        # ⚠️ ONLY BEHIND AN EXPLICIT MARKER. Print names are ordinary words — "Clouds",
        # "Dock", "Cardinal" — and scanning the line for any of the 64 would match
        # "praying hands" inside an unrelated sentence.
        if once("legacy_print_name"):
            m = re.search(r"\b(?:print|design)\s+(?:is\s+|:\s*)?([A-Za-z][A-Za-z'&\- ]{2,40})", line)
            if m:
                pr = resolve_print(m.group(1).strip())
                if pr.print_name:
                    if _mark(spans, m, "legacy_print_name"):
                        values["legacy_print_name"] = pr.print_name
                elif len(pr.candidates) > 1:
                    picks.append(Pick(
                        "legacy_print_name", m.group(1).strip(),
                        tuple((c.name, f"{c.name} — {c.category}") for c in pr.candidates),
                        pr.discriminators[0].value if pr.discriminators else None,
                    ))
                    _mark(spans, m, "legacy_print_name")
                # ⚠️ NO MATCH -> SPAN LEFT UNCLAIMED, so the typed name appears in
                # `unrecognized`. The ruling: kept verbatim and flagged, never coerced.

        # ── year pair -> both dates ─────────────────────────────────────
        yp = _year_pair(line)
        if yp and once("date_of_birth") and once("date_of_death"):
            (b, d), span = yp
            if _claim(spans, span[0], span[1], ("date_of_birth", "date_of_death")):
                values["date_of_birth"] = b
                values["date_of_death"] = d

        # ── explicit decedent name ──────────────────────────────────────
        if once("deceased_name"):
            en = _explicit_name(line)
            if en and _claim(spans, en[1][0], en[1][1], "deceased_name"):
                values["deceased_name"] = en[0]

        # ── a surname on its own ────────────────────────────────────────
        # ⚠️ AFTER THE TWO-WORD FORM, SO "decedent Mary Smith" KEEPS BOTH NAMES. The
        # surname pattern would match "decedent Mary" and stop; running it second
        # means it only sees clauses the fuller parser declined.
        #
        # ⚠️ THE FH AND CEMETERY GUARDS ARE LIFTED BEHIND A MARKER, BY RULING
        # (James, 2026-10-14). They were applied here until then, and the cost was
        # measured: testco holds "Smith & Sons Funeral Home", so `last name Smith`
        # — the commonest surname there — was refused, while the same sentence worked
        # on sunnycrest. **The marker is the evidence.** A director who says "last
        # name" has said in words that a surname follows, and a one-word fragment of
        # a four-word funeral-home name is weak evidence against that — especially
        # when the funeral home itself is already captured from earlier in the same
        # sentence.
        #
        # ⚠️ THE CATALOG GUARD STAYS, AND THE RULING SCOPES IT THAT WAY ("FH/cemetery").
        # Measured the same day: testco holds a product named exactly `Monticello`, so
        # "last name monticello" is a word that IS a product rather than a fragment of
        # one — and lifting this check too would name a decedent "monticello" and lose
        # the vault.
        #
        # ⚠️ WITHOUT A MARKER THE GUARD STAYS IN FULL — that is the marker-less pass
        # further down, which keeps all three lookups.
        if once("deceased_name"):
            # ⚠️ THE INDEX IS BUILT ONCE AND USED TWICE — by the first-word guard
            # below and by the trailing-word predicate. Two `build_index(db)` calls
            # in one pass would be two scans of the same catalog.
            _name_index = build_index(db)
            sn = _surname_clause(
                line,
                belongs_elsewhere=_word_belongs_to_another_field(
                    db, tenant_id, _name_index
                ),
            )
            if sn is not None:
                word, (a, b) = sn
                if not resolve_vault(_name_index, word).candidates:
                    if _claim(spans, a, b, "deceased_name"):
                        # ⚠️ AS GIVEN. The office's own capitalisation is information;
                        # `.title()` would turn "deSoto" into "Desoto".
                        values["deceased_name"] = word

        # ── grave location ──────────────────────────────────────────────
        if once("grave_location"):
            m = re.search(
                # ⚠️ EVERY LABEL IS WORD-BOUNDED, AND `grave` IS WHY. Without the
                # `\b` it matched the "grave" inside "graveSIDE": measured 2026-10-13,
                # "section 4 graveside Friday 11am" produced
                # `grave_location='Section 4, Space side'` and swallowed the word, so
                # the SERVICE LOCATION was lost and the order still asked for one.
                # The same sentence with anything between — "section 4 11 graveside" —
                # worked, which is what made it look like a graveside problem.
                #
                # ⚠️ `l` AND `sp` CARRY THE SAME RISK AND ARE BOUNDED TOO. A bare `l`
                # would match the "l" starting any word after a comma.
                r"\b(?:section|sec\.?)\s*([A-Za-z0-9]+)"
                r"(?:[,\s]+(?:lot|l)\b\s*([A-Za-z0-9]+))?"
                r"(?:[,\s]+(?:space|grave|sp)\b\s*([A-Za-z0-9]+))?", line, re.I)
            if m:
                parts = [f"Section {m.group(1)}"]
                if m.group(2):
                    parts.append(f"Lot {m.group(2)}")
                if m.group(3):
                    parts.append(f"Space {m.group(3)}")
                if _mark(spans, m, "grave_location"):
                    values["grave_location"] = ", ".join(parts)

        # ── chairs: the package AND its count, from one span ─────────────
        #
        # ⚠️ AFTER THE GRAVE LOCATION, AND THAT ORDERING IS A MEASUREMENT RATHER THAN
        # A PREFERENCE. Both recognisers want a bare digit, and run the other way
        # round the chair pattern wins one it has no claim to: measured 2026-10-14,
        # "going to oakwood section 12 chairs" read "12 chairs" as a TOTAL and
        # produced `extra_chairs_count='4'` with `grave_location=None`. The section
        # was silently lost — the one outcome the span rule exists to prevent.
        #
        # ⚠️ THE GRAVE LABELS ARE EXPLICIT AND "chairs" IS NOT, which is the reason
        # the tie breaks this way. "section 12" says in words which field the 12
        # belongs to. With the grave location claimed first, the same sentence keeps
        # `Section 12` and reports "chairs" as unplaced text — visible and
        # correctable, instead of a quietly missing grave.
        #
        # ⚠️ ONE SPAN, TWO VALUES, so this is a function rather than a row in
        # `_EQUIPMENT` — the same shape as `_year_pair`.
        chairs = _chairs(line)
        if chairs is not None:
            count, (ca, cb) = chairs
            if once("cemetery_equipment"):
                if _claim(spans, ca, cb, ("cemetery_equipment", "extra_chairs_count")):
                    values["cemetery_equipment"] = _EQ_ID["Extra Chairs (Over 8)"]
                    # ⚠️ ONLY WHEN A NUMBER WAS GIVEN. `None` means "chairs, count
                    # unsaid", and writing a count there would invent one — the
                    # field stays unanswered and `required_when` reports the gap.
                    if count is not None and once("extra_chairs_count"):
                        values["extra_chairs_count"] = str(count)
            else:
                # ⚠️ CLAIMED AND THE RETURN IGNORED, exactly as `note_restated` does
                # with `_mark`. The span is spoken for either way; what matters is
                # that these words do not also land in the unplaced list.
                _claim(spans, ca, cb, "cemetery_equipment")
                cur = answers.get("cemetery_equipment", values.get("cemetery_equipment"))
                restated.append(
                    f"{line[ca:cb].strip()} — cemetery_equipment is already {cur!r}"
                )

        # ── burial date ─────────────────────────────────────────────────
        # ⚠️ ADDED AFTER A TEST FAILED FOR THE RIGHT REASON. `burial_date` is REQUIRED on
        # the template and had no parser at all, so "burial on March 3" landed in
        # `service_date` via the generic fallback and NO typed order could ever be
        # complete. Marker-based and ahead of the fallback, because "burial" and
        # "service" are different days (the same distinction r199 made for times).
        if once("burial_date"):
            # ⚠️ `(?!vaults?\b)` BECAUSE "BURIAL" IS IN THE PRODUCT NAME. Every
            # director types "monticello burial vault", so the marker matched there
            # first. ⚠️ AND THE PLURAL IS IN THE LOOKAHEAD DELIBERATELY: written
            # `(?!vault\b)`, the `\b` fails between "vault" and "s" and "burial
            # vaults" would still eat the date.
            #
            # ⚠️ `finditer`, NOT `search`, AND THAT IS THE OTHER HALF OF THE FIX. The
            # old version took the FIRST match and a fixed 30-CHARACTER window after
            # it, then gave up — so one failed parse consumed the field for the whole
            # sentence, because `once()` never lets it try again. Measured
            # 2026-10-13:
            #
            #   "monticello burial vault burial thursday 11am"
            #       tail 'vault burial thursday 11am'      -> 2026-10-15   (worked)
            #   "monticello burial vault Mary Smith 1948 to 2026 burial thursday 11am"
            #       tail 'vault Mary Smith 1948 to 2026 '  -> None         (lost)
            #
            # The short sentence passed by luck: the 30 characters happened to reach
            # the real clause. Put a decedent between them and `burial_date` — a
            # REQUIRED field — became uncapturable, so no order could ever complete
            # and Approve was unreachable. The symptom appeared on `service_date`,
            # which picked the day up through the generic fallback.
            #
            # ⚠️ THE TAIL IS WORD-BOUNDED, NOT A CHARACTER RUN. Third instance of
            # that defect in this file; `_CEM_TOWN` and its inline duplicate were the
            # first two. A character count cannot find the end of a clause in
            # comma-free text.
            from app.services.nl_creation.structured_parsers import parse_date as _pd

            # ⚠️ "graveside" WAS IN THIS MARKER AND IT IS A LOCATION WORD, NOT A
            # DATE ONE. Measured 2026-10-13: "graveside friday 11am" matched HERE, so
            # it set a BURIAL DATE and the service LOCATION was lost entirely — the one
            # phrasing James named for a graveside service was the one phrasing that
            # could not express it. Removed by the same ruling that stopped asking for
            # a burial date at all.
            #
            # ⚠️ THE TAIL IS THE LONGEST RUN THAT PARSES, NOT A FIXED THREE WORDS.
            # Measured: a fixed tail handed `parse_date` "saturday 11am nameplate",
            # got None and dropped the date — while the same clause at the END of a
            # sentence parsed fine. Whether the burial date was read depended on what
            # came after it. Same shape as the funeral-home marker: try the longest
            # candidate and shorten until something resolves.
            for m in re.finditer(
                r"\b(?:burial|interment)\s+(?!vaults?\b)(?:is\s+|on\s+|:\s*)?",
                line,
                re.I,
            ):
                words = list(
                    re.finditer(r"[A-Za-z0-9][A-Za-z0-9/.,'\-]*", line[m.end():])
                )[:3]
                # ⚠️ THE SHORTEST TAIL THAT PARSES, AND THE CLAIM IS TRIED PER
                # LENGTH. Longest-first was wrong twice over: `parse_date` answers
                # the same date for "saturday", "saturday 11am" and "saturday 11am
                # nameplate", so the longest run won and its span reached into
                # "nameplate" — a word the personalization pass already owned, so the
                # claim FAILED and the date was dropped entirely. Measured
                # 2026-10-13: "burial saturday 11am nameplate only" stored no burial
                # date and reported "saturday 11am" as unplaced.
                #
                # ⚠️ SHORTEST IS ALSO THE RIGHT RULE, not merely the working one. A
                # marker-led span must not swallow following words — the same rule
                # the cemetery town and the funeral home already follow — and a date
                # clause is as short as it can be.
                claimed = False
                for n in range(1, len(words) + 1):
                    a = m.end() + words[0].start()
                    b = m.end() + words[n - 1].end()
                    pd = _pd(line[a:b].strip())
                    if not (pd and pd.get("value")):
                        continue
                    # ⚠️ A TIME IMMEDIATELY AFTER THE DATE IS CLAIMED WITH IT, even
                    # though nothing stores it. "burial saturday 11am" is one clause
                    # the director said about the burial; shortening the span to
                    # "saturday" left "11am" to be reported as a word the engine
                    # could not place, which is noise this very change introduced.
                    #
                    # ⚠️ THERE IS NO BURIAL-TIME FIELD AND THAT IS DELIBERATE — the
                    # service time and the cemetery ETA are the two times an order
                    # has. Claiming the token places the words without inventing a
                    # third.
                    tail = _TIME_TOKEN.match(line[b:].lstrip())
                    if tail is not None:
                        gap = len(line[b:]) - len(line[b:].lstrip())
                        b += gap + tail.end()
                    if _claim(spans, m.start(), b, "burial_date"):
                        values["burial_date"] = pd["value"]
                        claimed = True
                    break
                if claimed:
                    break

        _cem_town_cache: frozenset[str] | None = None

        def _cem_towns() -> frozenset[str]:
            """The towns this tenant holds cemeteries in. Fetched at most once per line.

            ⚠️ MEMOISED ON A NONLOCAL RATHER THAN RECOMPUTED, because both the marker
            path and the record scan below want it and a line can reach both.
            """
            nonlocal _cem_town_cache
            if _cem_town_cache is None:
                from app.services.party_resolver import cemetery_rows
                from app.services.party_resolver import normalize as _pn

                _cem_town_cache = frozenset(
                    _pn(_city) for _i, _n, _city in cemetery_rows(db, tenant_id) if _city
                )
            return _cem_town_cache

        # ── cemetery (+ city) ───────────────────────────────────────────
        # ⚠️ THE CITY IS PARSED FROM THE SAME CLAUSE AND PASSED AS A HINT, not stored
        # as an answer unless the cemetery resolves — a town with no cemetery attached
        # is not a fact about the order.
        if once("cemetery"):
            # ⚠️ ONE CALL TO A STEP PARSER, NOT ONE REGEX. See
            # `parse_cemetery_clause` for the three silent failures that bought this.
            #
            # ⚠️ THE TOWN LIST IS PASSED IN SINCE JAMES'S RULING OF 2026-10-29, AND IT
            # COSTS ONE QUERY AT MOST ONCE PER LINE. Without it the clause parser cannot
            # tell a bare adjacent town from any other word — "st marys skaneateles" was
            # parsed as `name='st marys skaneateles'`, resolved to nothing, and the town
            # fell out as text the engine could not place. `cemetery_rows` is documented
            # as "exposed so a scan can fetch ONCE and match in memory"; this is the same
            # lazy shape as `_vocab()` further down, and for the same reason: a line with
            # no cemetery clause must not pay for the read.
            clause = parse_cemetery_clause(line, _cem_towns())
            if clause:
                # ⚠️ A BARE TOWN IS ONLY A HINT WHEN A CEMETERY OF THIS NAME IS IN IT,
                # which is what keeps this path agreeing with the record scan below. The
                # peel still runs either way — it is what stops the greedy name
                # swallowing the town — but an inconsistent bare town is dropped rather
                # than raising a pick that un-answers the row. See `_towns_for_name`;
                # the explicit "in <town>" form is unaffected and still conflicts.
                hint = clause.town
                claim_end = clause.end
                if hint and not clause.town_explicit:
                    from app.services.party_resolver import cemetery_rows as _cr
                    from app.services.party_resolver import normalize as _pn

                    if _pn(hint) not in _towns_for_name(
                        _cr(db, tenant_id), clause.name
                    ):
                        hint = None
                        # ⚠️ AND THE CLAIM GIVES THE WORD BACK, which is the half that
                        # makes this honest rather than merely safe. A dropped hint whose
                        # span stayed claimed would swallow a word the director typed and
                        # the engine did not use — silently, with nothing on screen to
                        # say so. Unclaimed, it surfaces as text the engine could not
                        # place, which is true and is what slice 2's held-word strip is
                        # for. The record scan below already behaves this way; this makes
                        # the two paths agree.
                        if clause.town_span is not None:
                            claim_end = min(claim_end, clause.town_span[0])
                cr = resolve_cemetery(
                    db, tenant_id, clause.name, city_hint=hint
                )
                if cr.party_id:
                    if _claim(spans, clause.start, claim_end, "cemetery"):
                        values["cemetery"] = cr.candidates[0].name
                        if cr.candidates[0].city:
                            values["cemetery_city"] = cr.candidates[0].city
                elif len(cr.candidates) > 1 or cr.city_conflict:
                    # ⚠️ A CITY CONFLICT BECOMES A PICK EVEN WITH ONE CANDIDATE. The
                    # director named a town no candidate is in; showing them
                    # "St. Mary's Cemetery — Skaneateles" lets them confirm it or
                    # realise they meant somewhere else. Leaving it as unrecognized
                    # text would be honest but useless — they said a cemetery and the
                    # pane would show them nothing to act on.
                    if _claim(spans, clause.start, claim_end, "cemetery"):
                        picks.append(Pick(
                            "cemetery", clause.name,
                            tuple((c.name, c.label) for c in cr.candidates),
                            cr.discriminators[0].value
                            if cr.discriminators else None,
                        ))

        # ── funeral home ────────────────────────────────────────────────
        if once("funeral_home"):
            # ⚠️ CASE-INSENSITIVE SINCE 2026-10-12, AND IT USED TO REQUIRE CAPITALS.
            # The pattern was `([A-Z][A-Za-z'&\-]*(?:\s+[A-Z]...){0,3})`, so a
            # director typing fast on a call — lowercase, as James did on production
            # with "order for hopkins" — matched NOTHING here and the name came back
            # unrecognized. Measured: "order for Hopkins" resolved, "order for
            # hopkins" did not.
            #
            # ⚠️ AND THE MARKER-LESS RECORD LOOKUP BELOW COULD NOT COVER IT EITHER,
            # which is why one fix is not two. That scan IS case-insensitive but
            # tries n-gram sizes (5, 4, 3, 2) — minimum TWO words — so the
            # single-word "hopkins" fell through both paths. Two independent gaps,
            # and neither alone explains the failure.
            #
            # ⚠️ WIDENING THE CASE CANNOT INVENT A FUNERAL HOME. The span is only
            # claimed when `resolve_funeral_home` returns a party or a candidate set
            # (the two branches below); a span that resolves to nothing claims
            # nothing and falls through to every later pass unchanged. So the cost of
            # a wrong match is bounded by the resolver, not by this regex.
            #
            # ⚠️ `re.I` IS THE OPERATIVE CHANGE AND THE WIDENED CHARSET IS REDUNDANT
            # UNDER IT. Measured, because a break test removing the charset change
            # produced no red and I would otherwise have left both reading as
            # load-bearing:
            #
            #     phrase               [A-Z] no I   [A-Z]+I   [A-Za-z] no I   both
            #     order for hopkins    -            hopkins   hopkins         hopkins
            #     order for Hopkins    Hopkins      Hopkins   Hopkins         Hopkins
            #     ORDER FOR HOPKINS    -            HOPKINS   -               HOPKINS
            #
            # `[A-Z]` under `re.I` already matches lowercase, so `re.I` alone fixes
            # the reported defect. The charset is kept DEFENSIVELY, not because it is
            # needed: it means the pattern's basic meaning does not depend on a flag
            # at the far end of the call, so removing `re.I` later degrades to
            # "lowercase names work, SHOUTED markers do not" rather than to the
            # original defect. That is a stated reason for keeping redundant code,
            # which is the alternative to it reading as a second fix.
            # ⚠️ THE LONGEST PREFIX THAT RESOLVES — NOT THE LONGEST RUN OF WORDS.
            # This used to take up to four words after the marker and hand the whole
            # thing to the resolver, which is correct only when a comma stops it.
            # Measured 2026-10-13 on run-on text, which is how a director actually
            # types: "order for hopkins continental" captured the span
            # "hopkins continental", resolved NOTHING, claimed nothing, and the
            # funeral home that had been captured one keystroke earlier was LOST —
            # along with the vault, because "continental" was left glued behind
            # "hopkins" in a single unplaced blob.
            #
            # Ruled: a marker-led span must not swallow following words. So the
            # candidate words are taken once and tried LONGEST-FIRST, and the first
            # prefix that resolves wins; everything after it is left for the other
            # passes. "for hopkins continental" claims only "hopkins".
            #
            # ⚠️ LONGEST-FIRST AND NOT SHORTEST, which matters for the names that
            # contain each other: "Hopkins Funeral Home" must beat "Hopkins" when
            # both are typed, or the words "Funeral Home" fall through and the
            # service-location pass reads them as a venue.
            m = re.search(
                r"\b(?:for|from|with)\s+"
                r"((?:[A-Za-z][A-Za-z'&\-]*)(?:\s+[A-Za-z][A-Za-z'&\-]*){0,3})",
                line, re.I)
            if m:
                wordm = list(re.finditer(r"[A-Za-z][A-Za-z'&\-]*", m.group(1)))
                base = m.start(1)
                for n in range(len(wordm), 0, -1):
                    # ⚠️ A SPAN MUST NOT END ON A WORD THE NORMALIZER DELETES, and
                    # that is a real defect rather than tidiness. `normalize` strips
                    # separator words, so `resolve_funeral_home("riverside the")`
                    # RESOLVES — measured 2026-10-13 — and the loop then claimed the
                    # trailing "the" along with the name. Harmless until something
                    # else wanted that word: "order for riverside the Keegan family"
                    # lost the FUNERAL HOME, because the surname clause had already
                    # claimed "the Keegan family" and the overlapping claim failed.
                    #
                    # ⚠️ SKIPPED RATHER THAN TRIMMED, because the loop is already
                    # longest-first: dropping this n means the next one down is the
                    # same phrase without the dead word, which is the span we want.
                    if wordm[n - 1].group(0).casefold() in _SPAN_TAIL_STOPS:
                        continue
                    a = base + wordm[0].start()
                    b = base + wordm[n - 1].end()
                    phrase = line[a:b].strip()
                    fr = resolve_funeral_home(db, tenant_id, phrase)
                    if fr.party_id:
                        if _claim(spans, a, b, "funeral_home"):
                            values["funeral_home"] = fr.candidates[0].name
                        break
                    if len(fr.candidates) > 1:
                        if _claim(spans, a, b, "funeral_home"):
                            picks.append(Pick(
                                "funeral_home", phrase,
                                tuple((c.name, c.label) for c in fr.candidates),
                                fr.discriminators[0].value
                                if fr.discriminators else None,
                            ))
                        break

        # ── cemetery by RECORD LOOKUP, no marker needed ─────────────────
        # ⚠️ RULED 2026-10-12: "a cemetery that exists in your records should be
        # recognised wherever it's typed. Matching a known name isn't guessing." The
        # marker path above stays and still runs first; this catches the rest —
        # "St. Mary's Cemetery" on its own, and "St Mary's in Auburn" without a "to".
        #
        # ⚠️ IT SCANS UNCLAIMED SLICES ONLY, so the funeral home, the vault and the
        # dates keep whatever they have already taken. A cemetery called "Hopkins"
        # cannot steal the funeral home's span, because the funeral home pass runs
        # BEFORE this one and claims first.
        #
        # ⚠️ LONGEST N-GRAM FIRST. "St Mary's Cemetery" must beat "St Mary's" when
        # both are in the records, and a shorter match claiming first would leave
        # "Cemetery" orphaned — the same orphaned-fragment defect the `graveside`
        # probe caught in the location vocabulary.
        if once("cemetery"):
            rows = cemetery_rows(db, tenant_id)
            # ⚠️ AN EXACT NAME MATCH, NOT A TOKEN OVERLAP, AND A PROBE IS WHY.
            # `resolve_from_rows` matches on SIGNIFICANT TOKENS, so the single word
            # "Mary" resolved to "St. Mary's Cemetery" — and the scan claimed it.
            # "Mary Smith" therefore came back with "Mary" taken as a cemetery and
            # "Smith" orphaned as unplaced text, and the decedent could never be
            # found. Measured, not reasoned about: every line containing a first name
            # that happens to appear in a cemetery's name was broken.
            #
            # Ruling 2 says "a span matching an existing cemetery record" — the NAME,
            # which is what "matching a known name isn't guessing" means. So the
            # candidate must EQUAL a record's name, with a trailing "cemetery"
            # optionally dropped because that is how directors say it ("Oakwood").
            # `resolve_from_rows` still does the resolving and still owns the
            # city-conflict rule; it just no longer decides what counts as a mention.
            exact = set()
            # ⚠️ THE TOWNS WE HOLD RECORDS FOR, which is what bounds a town span —
            # see `_narrow_town`. A record set rather than a word list, because a
            # town can be named after anything and a stop-list rejected "New".
            town_names = frozenset(
                _party_norm(_city) for _i, _n, _city in rows if _city
            )
            for _cid, _name, _city in rows:
                n = _party_norm(_name)
                exact.add(n)
                for suf in (" cemetery", " cemeteries"):
                    if n.endswith(suf):
                        exact.add(n[: -len(suf)].strip())
            if rows:
                for frag_start, frag in _unclaimed_slices(line, spans):
                    hit = None
                    words = list(re.finditer(r"[A-Za-z'][A-Za-z'\-\.]*", frag))
                    # ⚠️ NO N-GRAM MAY CONTAIN A PREPOSITION, AND MY FIRST VERSION
                    # DID — the identical defect the marker path above already
                    # documents. `resolve_from_rows` matches on significant tokens, so
                    # "St Mary's in" matched "St. Mary's Cemetery" just as well as
                    # "St Mary's" did; the longest-first scan took it, the span ended
                    # at "in", and `\s+in\s+<Town>` had nothing left to match. The
                    # town was never read and "Auburn" fell into `unrecognized` —
                    # which is precisely the conflict ruling 1 exists to raise.
                    # Measured before and after, not reasoned about.
                    stop = {"in", "on", "at", "to", "for", "with", "and", "the"}
                    ok = [
                        w for w in words if w.group(0).casefold() not in stop
                    ]
                    for size in (4, 3, 2, 1):
                        for i in range(len(ok) - size + 1):
                            run = ok[i:i + size]
                            # contiguous in the ORIGINAL word list, so a dropped
                            # preposition breaks the run rather than closing over it
                            idx = [words.index(w) for w in run]
                            if idx != list(range(idx[0], idx[0] + size)):
                                continue
                            a, b = run[0].start(), run[-1].end()
                            if _party_norm(frag[a:b]) in exact:
                                hit = (a, b, None)
                                break
                        if hit:
                            break
                    if not hit:
                        continue
                    a, b, _ = hit
                    # ⚠️ THE TOWN IS READ FROM WHAT FOLLOWS THE NAME, so the conflict
                    # rule applies here exactly as it does on the marker path.
                    #
                    # ⚠️ THIS WAS A SECOND, INLINE COPY OF THE TOWN PATTERN AND IT IS
                    # WHY A FIX LANDED YESTERDAY DID NOT TAKE. `_CEM_TOWN` gained the
                    # period in its charset on 2026-10-12 — for "St. Albans" — and
                    # this duplicate did not, so the record path still could not read
                    # an abbreviated town. Worse, it kept the 30-CHARACTER run, and on
                    # comma-free text that runs straight through word boundaries:
                    # "st marys in auburn service at the church thursday 10am"
                    # claimed 43 characters, through to "...th", and reported
                    # **'ursday'** as text the engine could not place. Traced by
                    # instrumenting `_claim` rather than by reading.
                    #
                    # One pattern, one place. A fix to the town now reaches both
                    # callers, which is the whole reason the constant exists.
                    # ⚠️ `_town_after` SINCE JAMES'S RULING OF 2026-10-29, which reads a
                    # BARE adjacent town as well as the "in <town>" form. This was
                    # `_CEM_TOWN.match` alone, requiring the word "in" — so the walk
                    # sentence "…graveside st marys skaneateles" resolved the cemetery
                    # (the record scan matches "st marys" on its own) and then reported
                    # **'skaneateles'** as text the engine could not place. Measured.
                    #
                    # ⚠️ AND THE BARE FORM IS NARROWED STRICTLY INSIDE THE HELPER, so
                    # "st marys tent only" still claims no town. The forgiving narrowing
                    # — which returns a town we hold no record of, deliberately, so a
                    # conflict raises the pick — applies only when the director wrote
                    # "in", because that word is what says a town follows.
                    # ⚠️ NARROWED TO THE TOWNS THIS NAME ACTUALLY SITS IN — see
                    # `_towns_for_name` for why, and for which of James's three cases is
                    # deferred until clause 1 lands.
                    name_towns = _towns_for_name(rows, frag[a:b])
                    after = _town_after(frag[b:], town_names, bare_known=name_towns)
                    city = after[0] if after else None
                    # ⚠️ AND A TOWN TYPED BEFORE THE NAME, per the same ruling. The claim
                    # has to extend BACKWARDS over it or the word is left unclaimed and
                    # reported as text the engine could not place — which is the defect,
                    # moved rather than fixed.
                    #
                    # ⚠️ THE TRAILING FORM WINS WHEN BOTH APPEAR. "skaneateles st marys
                    # auburn" is a director correcting themselves and the last thing said
                    # is the one that counts, as everywhere else in this module.
                    before = None if city else _town_before(frag[:a], name_towns)
                    if before is not None:
                        city = before[0]
                    # ⚠️ THE CLAIM ENDS WHERE THE NARROWED TOWN ENDS, not where the
                    # pattern matched. Claiming the pattern's full span is what ate
                    # the following clause; the words the town did not use must stay
                    # available to the passes that want them.
                    end = b + (after[1] if after else 0)
                    start_at = before[1] if before is not None else a
                    cr = resolve_from_rows(rows, frag[a:b], city)
                    if cr.party_id:
                        if _claim(spans, frag_start + start_at, frag_start + end, "cemetery"):
                            values["cemetery"] = cr.candidates[0].name
                            if cr.candidates[0].city:
                                values["cemetery_city"] = cr.candidates[0].city
                    elif len(cr.candidates) > 1 or cr.city_conflict:
                        if _claim(spans, frag_start + start_at, frag_start + end, "cemetery"):
                            picks.append(Pick(
                                "cemetery", frag[a:b],
                                tuple((c.name, c.label) for c in cr.candidates),
                                cr.discriminators[0].value
                                if cr.discriminators else None,
                            ))
                    break

        # ── funeral home by RECORD LOOKUP, no marker needed ────────────
        # ⚠️ THIS IS DEFECT 3a AGAIN, REACHED BY THE PHRASING THE FIX DID NOT COVER,
        # AND IT WAS FOUND BY A BREAK TEST THAT DID NOT FIRE.
        #
        # 3a was fixed by ORDER: the funeral-home pass claims the party's name before
        # the location vocabulary can read "funeral home" out of it. But that pass is
        # marker-gated — it needs "for"/"from"/"with" — so a director who types just
        # "Hopkins Funeral Home" gets no claim, and the vocabulary eats the words
        # again. Measured 2026-10-12: `"Hopkins Funeral Home"` alone produced
        # `service_location='funeral_home'` and left "Hopkins" unplaced. The Service
        # row would say "Funeral home" for the second time.
        #
        # ⚠️ ADDED SCOPE, FLAGGED: ruling 2 names CEMETERIES. The same reasoning and
        # the same defect apply to funeral homes, and leaving it would mean the bug
        # James reported is still reachable by the most obvious phrasing there is.
        #
        # Exact name match against the records, same as the cemetery scan, for the
        # same reason: `resolve_from_rows` matches on significant tokens, so a token
        # overlap is not a mention.
        if once("funeral_home"):
            fh_rows = funeral_home_rows(db, tenant_id)
            fh_exact = {_party_norm(n): n for _i, n, _c in fh_rows}
            if fh_exact:
                for frag_start, frag in _unclaimed_slices(line, spans):
                    words = list(re.finditer(r"[A-Za-z&'][A-Za-z&'\-\.]*", frag))
                    stop = {"in", "on", "at", "to", "for", "with", "the"}
                    ok = [w for w in words if w.group(0).casefold() not in stop]
                    hit = None
                    for size in (5, 4, 3, 2):
                        for i in range(len(ok) - size + 1):
                            run = ok[i:i + size]
                            idx = [words.index(w) for w in run]
                            if idx != list(range(idx[0], idx[0] + size)):
                                continue
                            a, b = run[0].start(), run[-1].end()
                            if _party_norm(frag[a:b]) in fh_exact:
                                hit = (a, b)
                                break
                        if hit:
                            break
                    if not hit:
                        continue
                    a, b = hit
                    fr = resolve_funeral_home(db, tenant_id, frag[a:b])
                    if fr.party_id:
                        if _claim(spans, frag_start + a, frag_start + b, "funeral_home"):
                            values["funeral_home"] = fr.candidates[0].name
                    elif len(fr.candidates) > 1:
                        if _claim(spans, frag_start + a, frag_start + b, "funeral_home"):
                            picks.append(Pick(
                                "funeral_home", frag[a:b],
                                tuple((c.name, c.label) for c in fr.candidates),
                                fr.discriminators[0].value
                                if fr.discriminators else None,
                            ))
                    break

        # ── service location ────────────────────────────────────────────
        # ⚠️ MOVED HERE 2026-10-12, AFTER THE FUNERAL HOME, AND THE ORDER IS THE FIX.
        # It used to run eighth, scanning the WHOLE line with `low.find`, so "start an
        # order for Hopkins Funeral Home" matched the words "funeral home" inside the
        # party's own name and answered a question James never asked. `_claim` alone
        # would not have fixed it: this pass ran FIRST and would simply have won the
        # span, blocking the funeral home instead. The specific entity has to claim its
        # name before a bare vocabulary scan is allowed to look at the text.
        #
        # ⚠️ IT SCANS `out_fragments`, THE RAW UNCLAIMED SLICES — NOT `_leftovers`.
        # `_leftovers` strips noise words, and `funeral`, `home` and `service` are all
        # in `_NOISE_WORDS`, so a noise-stripped fragment can never contain the phrase
        # "funeral home" and "the service is at the funeral home" would resolve to
        # nothing. The distinction is invisible until you try it.
        if once("service_location"):
            for frag_start, frag in _unclaimed_slices(line, spans):
                folded = frag.casefold()
                # ⚠️ THE MATCH THAT CONSUMES THE MOST TEXT WINS, NOT THE EARLIEST ONE.
                # My first version took the earliest start and a probe caught it:
                # "service at the graveside" matched `at the grave` (8-20) before
                # `graveside` (15-24), claimed the shorter span, and left "side" in
                # `unrecognized`. Maximising the END offset picks `graveside` and
                # consumes the whole word; `at the grave` on its own still matches,
                # because then it is the only candidate.
                #
                # ⚠️ AND THIS IS WHY THE VOCABULARY'S DICT ORDER IS NOT THE RULE.
                # Relying on insertion order worked here by luck and would break the
                # first time someone added a key in the wrong place — the same trap
                # `_EQUIPMENT` documents as "ORDERED LONGEST-INTENT FIRST", made
                # structural instead of conventional.
                hit = None
                for words, val in _LOCATION_WORDS.items():
                    i = folded.find(words)
                    if i < 0:
                        continue
                    cand = (i + len(words), -i, words, val)
                    if hit is None or cand > hit:
                        hit = cand
                if hit:
                    end, neg_start, words, val = hit
                    assert val in SERVICE_LOCATIONS, val
                    a = frag_start + (-neg_start)
                    if _claim(spans, a, a + len(words), "service_location"):
                        values["service_location"] = val
                    break

        # ── Life's Reflections symbol ───────────────────────────────────
        # ⚠️ GATED ON THE ANSWER, NOT ON THE WORD. These are ordinary words — Cross,
        # Dove, Floral, Praying Hands are also Legacy print names — so the pass only
        # runs when the personalization answer is vinyl-bearing, which is exactly the
        # schema's own `AnswerIn(QUESTION_PERSONALIZATION, VINYL_BEARING_ANSWERS)`
        # condition. A bare "cross" with no vinyl in the line sets nothing.
        #
        # ⚠️ AND IT RUNS HERE, AFTER THE CEMETERY AND THE FUNERAL HOME, FOR THE SAME
        # REASON `service_location` DOES. "vinyl, to Holy Cross Cemetery" would
        # otherwise have the symbol pass claim "Cross" out of the cemetery's own name
        # — the identical defect James found in the Service row, one field over.
        # ⚠️ Raw unclaimed slices, not `_leftovers`: "of" is a noise word, so a
        # noise-stripped fragment can never contain "star of david".
        # ⚠️ THREE SOURCES, IN THIS ORDER, AND THE THIRD IS WHY `gating` EXISTS. This
        # line's own words win; then what is already answered; then the gating
        # context, which is the only one a segment-isolated re-read has.
        chosen = values.get(
            QUESTION_PERSONALIZATION,
            answers.get(
                QUESTION_PERSONALIZATION,
                (gating or {}).get(QUESTION_PERSONALIZATION),
            ),
        )
        if chosen in VINYL_BEARING_ANSWERS and once("lifes_reflections_symbol"):
            for frag_start, frag in _unclaimed_slices(line, spans):
                hit = None
                for pat, ident in _VINYL_SYMBOLS:
                    m = re.search(pat, frag, re.I)
                    if m is None:
                        continue
                    cand = (m.end(), -m.start(), m, ident)
                    if hit is None or cand[:2] > hit[:2]:
                        hit = cand
                if hit:
                    _, _, m, ident = hit
                    a = frag_start + m.start()
                    if _claim(spans, a, frag_start + m.end(), "lifes_reflections_symbol"):
                        values["lifes_reflections_symbol"] = ident
                    break

        # ── vault ───────────────────────────────────────────────────────
        # ⚠️ RUNS LATE AND OVER THE WHOLE LINE, because a vault phrase is bare words
        # ("an oversized", "34 inch Continental") with no marker in front of it. Running
        # it early would let it claim spans that belong to a cemetery or a party.
        if once("vault"):
            # ⚠️ AN N-GRAM SCAN OVER EACH UNCLAIMED SLICE, LONGEST-FIRST — AND IT USED
            # TO RESOLVE THE WHOLE SLICE AS ONE PHRASE. That is right only when a
            # comma has already cut the slice down to the product words. Measured
            # 2026-10-13 on run-on text: "order for hopkins continental 34 mary"
            # left "continental 34 mary" as one unclaimed slice, `resolve_vault` on
            # the whole thing matched nothing, and THE VAULT CAPTURED ONE KEYSTROKE
            # EARLIER WAS LOST. A director types no commas, so the slice keeps
            # growing and the product name keeps being diluted.
            #
            # ⚠️ THE PARTY PASSES ALREADY SCAN N-GRAMS; this makes the vault consistent
            # with them rather than inventing a mechanism. Longest-first so
            # "Continental 34" beats "Continental" and produces a resolution instead
            # of a two-option pick.
            #
            # ⚠️ EACH N-GRAM IS TRIED STRIPPED **AND** RAW, which is the reading the
            # old code did with `_leftover_pairs`. Catalog names contain words that
            # are also noise words, so a stripped miss is not evidence the director
            # named no vault. Keeping both readings is why no resolution that worked
            # before stops working.
            index = build_index(db)
            hit = False
            for frag_start, frag in _unclaimed_slices(line, spans):
                if hit:
                    break
                # ⚠️ DIGITS ARE PART OF A PRODUCT WORD. "34" is a word here, unlike
                # in the party scans — the catalog's names carry sizes, and a pattern
                # that skipped digits would make "Continental 34" unreachable as a
                # two-word n-gram and leave only the ambiguous "Continental".
                wordm = list(re.finditer(r"[A-Za-z0-9][A-Za-z0-9'&.\-]*", frag))
                if not wordm:
                    continue
                # ⚠️ SIX WORDS IS THE CEILING AND IT IS MEASURED, NOT CHOSEN: the
                # longest display name in the catalog is well inside it, and an
                # unbounded scan over a run-on sentence is quadratic in its length.
                for size in range(min(6, len(wordm)), 0, -1):
                    if hit:
                        break
                    for i0 in range(0, len(wordm) - size + 1):
                        run = wordm[i0:i0 + size]
                        a, b = run[0].start(), run[-1].end()
                        raw = frag[a:b]
                        kept = " ".join(
                            w for w in raw.split() if w.casefold() not in _NOISE_WORDS
                        )
                        vr = resolve_vault(index, kept) if kept else None
                        chosen = kept
                        if vr is None or not vr.candidates:
                            vr, chosen = resolve_vault(index, raw), raw
                        elif raw.casefold() != kept.casefold():
                            alt = resolve_vault(index, raw)
                            if _narrower(alt, vr):
                                vr, chosen = alt, raw
                        if not vr.candidates:
                            continue
                        A, B = frag_start + a, frag_start + b
                        if vr.variant_template_id:
                            if _claim(spans, A, B, "vault"):
                                values["vault"] = vr.candidates[0].display_name
                                hit = True
                            break
                        if len(vr.candidates) > 1:
                            # ⚠️ AMBIGUOUS ONLY BY FORM -> TAKE THE BURIAL VAULT,
                            # BY RULING (2026-10-13). "Monticello" matches a burial
                            # vault and an urn vault and nothing else distinguishes
                            # them, so a pick there asks a question whose answer the
                            # office already knows nine times in ten. The urn vault
                            # is offered as a one-click SWITCH instead, so the
                            # order is complete and still correctable.
                            #
                            # ⚠️ THE TEST IS `discriminators == ("form",)` EXACTLY,
                            # measured rather than inferred: "Continental" is
                            # ambiguous by SIZE (both burial vaults) and must still
                            # ask. A check for "form is among the discriminators"
                            # silently resolves "triune" and "venetian" (form AND
                            # option) and "oversize" (form, line AND size) — each
                            # has a burial_vault candidate for the loose check to
                            # seize on, so it would pick an option or a size on the
                            # office's behalf.
                            #
                            # ⚠️ "GRAVELINER" IS NOT THE CASE THAT PROTECTS THIS,
                            # though I claimed it here first. Its forms are
                            # grave_liner and urn_vault with no burial_vault among
                            # them, so it falls through on `mine is None` and asks
                            # either way. A break test with the loose check left the
                            # whole suite green until the three phrases above
                            # replaced it.
                            discs = tuple(d.value for d in vr.discriminators)
                            if discs == ("form",):
                                # ⚠️ "urn" ANYWHERE IN THE VAULT PHRASE WINS, by
                                # ruling — and the phrase is the UNCLAIMED SLICE,
                                # not the matched n-gram.
                                #
                                # I bounded this to `chosen` first, reasoning that
                                # "urn" in another clause is not a statement about
                                # this vault. Measured: that broke the ruling
                                # outright. "monticello urn" resolves its 2-word
                                # n-gram to nothing and falls back to the 1-word
                                # "monticello", so `chosen` never contains "urn" and
                                # BOTH "monticello urn" and "urn monticello" took the
                                # burial vault.
                                #
                                # The slice is the right bound: it is already
                                # delimited by every other pass's claims, so the
                                # funeral home, the cemetery and the equipment are
                                # not in it. What remains is the words the director
                                # typed about the product.
                                want = (
                                    "urn_vault"
                                    if "urn" in frag.casefold()
                                    else "burial_vault"
                                )
                                mine = next(
                                    (c for c in vr.candidates if c.form == want), None
                                )
                                other = next(
                                    (c for c in vr.candidates if c.form != want), None
                                )
                                if mine is not None and _claim(spans, A, B, "vault"):
                                    values["vault"] = mine.display_name
                                    if other is not None:
                                        switches.append(Switch(
                                            field_id="vault",
                                            from_label=mine.display_name,
                                            to_value=other.display_name,
                                            to_label=f"Switch to {other.display_name}",
                                        ))
                                    hit = True
                                    break
                            if _claim(spans, A, B, "vault"):
                                picks.append(Pick(
                                    "vault", chosen,
                                    tuple((c.display_name,
                                           f"{c.sku} — {c.display_name}")
                                          for c in vr.candidates),
                                    vr.discriminators[0].value
                                    if vr.discriminators else None,
                                ))
                                hit = True
                            break

        # ── deceased name, by elimination ───────────────────────────────
        # ⚠️ RULED 2026-10-12: "if exactly one person-like name is left over after
        # everything else is placed, it becomes the decedent. If there are two, it
        # doesn't guess." So this runs LAST of the claiming passes, over what nothing
        # else took, and it refuses when the answer is not unique.
        #
        # ⚠️ TWO-TO-THREE CAPITALISED WORDS, WHICH IS WHY "Hopkins" CAN NEVER BE A
        # DECEDENT. A single word is not a candidate at all — structural, not a
        # special case. "Hopkins Funeral Home" IS three words and is excluded by the
        # record check below instead.
        #
        # ⚠️ AND THE EXCLUSIONS ARE LOOKUPS, NOT A WORD LIST. A span that names a
        # funeral home, a cemetery, or anything in the catalog (including aliases) is
        # not a person. A hand-written list of "words that are not names" would be
        # wrong for every tenant whose records we have not seen.
        if once("deceased_name"):
            person = re.compile(r"\b[A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+){1,2}\b")
            cem = cemetery_rows(db, tenant_id)
            idx = build_index(db)
            found: list[tuple[int, int, str]] = []
            for frag_start, frag in _unclaimed_slices(line, spans):
                for m in person.finditer(frag):
                    phrase = m.group(0)
                    if resolve_from_rows(cem, phrase).candidates:
                        continue
                    if resolve_vault(idx, phrase).candidates:
                        continue
                    if resolve_funeral_home(db, tenant_id, phrase).candidates:
                        continue
                    found.append((frag_start + m.start(), frag_start + m.end(), phrase))
            # ⚠️ EXACTLY ONE, OR NOTHING. Two leftover names mean the engine cannot
            # tell which is the decedent, and both stay visible as unplaced text —
            # which is the honest outcome and the one the ruling asks for.
            if len(found) == 1:
                a, b, phrase = found[0]
                if _claim(spans, a, b, "deceased_name"):
                    values["deceased_name"] = phrase

        # ── service date / time / eta ───────────────────────────────────
        # ⚠️ LAST, AND OVER LEFTOVERS ONLY. `parse_date` is greedy about bare numbers,
        # so running it over the whole line would swallow "34 inch" and the year pair.
        # ── cemetery arrival (ETA) ──────────────────────────────────────
        # ⚠️ MARKER-GATED AND BEFORE THE SERVICE TIME, because "eta 11:30" and
        # "service at 11:30" are different facts and the generic time pass would
        # claim either. The marker is what distinguishes them, exactly as
        # `burial_date` is marker-gated against `service_date`.
        if once("eta"):
            mk = _ETA_MARKER.search(line)
            if mk:
                tail = line[mk.end():]
                tm = _TIME_TOKEN.search(tail)
                if tm:
                    pt = parse_time(tm.group(0))
                    if pt and pt.get("value"):
                        a = mk.start()
                        b = mk.end() + tm.end()
                        if _claim(spans, a, b, "eta"):
                            values["eta"] = pt["value"]

        # ── a graveside service: the location IS the service location ───
        # ⚠️ IT SETS BOTH FIELDS FROM ONE PHRASE, by ruling. "11 graveside" says where
        # the service is and when it is, and before this the bare "11" was reported as
        # text the engine could not place while the location arrived from the separate
        # location vocabulary.
        #
        # ⚠️ AHEAD OF THE GENERIC TIME PASS, so the claim is made by the rule that
        # understands the phrase rather than by a scan that happens to reach it.
        # ⚠️ THE WORD IS CLAIMED FOR THE LOCATION FIRST, AND IT HAS TO BE. Measured
        # 2026-10-13: in a full sentence "…section 4 graveside Friday 11am…" the
        # generic service-DATE pass runs over leftovers and `parse_date("graveside
        # Friday")` returns Friday — claiming the whole fragment, "graveside"
        # included. So the location vanished in a long sentence while working in a
        # short one, which is the same greedy-pass defect as the burial marker.
        #
        # ⚠️ CLAIMED RATHER THAN MERELY READ, because no span may feed two fields.
        # Taking the word here is what leaves "Friday" for the date and makes the
        # location's claim the one that owns it.
        if once("service_location"):
            gw = _GRAVESIDE_WORD.search(line)
            if gw is not None and _claim(spans, gw.start(), gw.end(), "service_location"):
                values["service_location"] = SERVICE_LOCATION_GRAVESIDE

        if once("service_time"):
            gt = _graveside_time(line)
            if gt is not None:
                when, (a, b) = gt
                if _claim(spans, a, b, "service_time"):
                    values["service_time"] = when
                    # ⚠️ THE LOCATION IS NOT SET HERE. The pass above owns it and
                    # has already claimed the word; setting it twice would be two
                    # writers for one field and the second would be unreachable.

        # ── abbreviations: an unambiguous prefix of a known term IS that term ──
        #
        # ⚠️ RULED BY JAMES ON HIS 2026-10-20 WALK. He typed "order hopk monti thursday
        # 10 am st. mary's". The ghost had been offering "ins Funeral Home" a keystroke
        # earlier, but he typed a space and kept going instead of pressing Tab — and the
        # extractor, which only ever matched whole names, reported the funeral home and
        # the vault as not understood. The bar knew and the engine did not.
        #
        # ⚠️ IT RUNS AFTER THE EXACT SCANS AND BEFORE THE DATE, AND BOTH HALVES OF THAT
        # ARE LOAD-BEARING. After, because a fully typed name must never be read as an
        # abbreviation of something else — the exact scans own their spans and
        # `_claim` then refuses this pass. Before, because the date's leftover loop
        # claims whatever is left around its evidence, and an abbreviation sitting
        # beside a weekday would be inside that claim before this pass could ask.
        #
        # ⚠️ IT EXPANDS AND HANDS THE FULL NAME TO THE ORDINARY RESOLVER. Nothing is
        # resolved here; see `prefix_resolve`'s docstring. The span claimed is the
        # ABBREVIATION the director typed, never the expansion — the expansion is not
        # in the text, and a span has to point at characters that exist.
        #
        # ⚠️ THE FINAL WORD OF THE WHOLE TEXT IS STILL BEING TYPED, AND IT BELONGS TO
        # THE GHOST, NOT TO THIS PASS. This is the one judgement in the abbreviation
        # ruling, and it reconciles two rulings that look opposed:
        #
        #   2026-10-13  "a half-typed word resolves to nothing" — every keystroke
        #               re-reads the text, so "Contin" is seen on almost every pass and
        #               guessing Continental fills in an answer not yet given.
        #   2026-10-20  "if hopk can only mean Hopkins, it's Hopkins."
        #
        # They are one rule over different words. James's own description says which:
        # "once you type a SPACE AND KEEP GOING without pressing Tab". A word the
        # director has MOVED PAST is a committed abbreviation; the word under the caret
        # is a work in progress, and `ghost.ts` already draws exactly that line —
        # `completionFor` completes only when "the caret must be at the END".
        #
        # ⚠️ SO THE FOUR `test_a_partial_word_resolves_to_nothing` CASES ARE NOT
        # SUPERSEDED, AND I CHECKED RATHER THAN ASSUMED: "Contin", "Continenta", "34
        # inch Contin" and "Hopk" every one sit at the END of their text.
        tail_open = bool((gating or {}).get(GATING_TAIL_OPEN, True))
        _tail_at = len(line.rstrip())

        _vocab_cache: list | None = None

        def _vocab() -> tuple:
            """⚠️ FETCHED AT MOST ONCE PER LINE, AND ONLY IF AN ABBREVIATION IS
            PLAUSIBLE. `build_vocabulary` runs five queries; paying that on every line
            that happens to have a leftover word would put it on the hot path for
            orders containing no abbreviation at all."""
            nonlocal _vocab_cache
            if _vocab_cache is None:
                from app.services.capture.vocabulary import build_vocabulary

                _vocab_cache = list(build_vocabulary(db, tenant_id))
            return tuple(_vocab_cache)

        def _prefix_pass(field: str, kinds: tuple[str, ...], finish) -> None:
            """Try each unclaimed word run as an abbreviation. Longest run first.

            `finish(res, a, b, frag)` does the field-specific work with the resolution,
            the span of what was actually typed, and the unclaimed slice it sat in —
            which the vault needs, because the "urn" rule is bounded to the slice.
            """
            from app.services.capture.prefix_resolve import MIN_PREFIX, resolve_prefix

            for frag_start, frag in _unclaimed_slices(line, spans):
                wordm = [
                    m for m in re.finditer(r"[A-Za-z0-9][A-Za-z0-9'&.\-]*", frag)
                    if m.group(0).casefold() not in _NOISE_WORDS
                ]
                if not wordm:
                    continue
                # ⚠️ LONGEST RUN FIRST, SO "st m" BEATS "st". A two-word abbreviation
                # is more specific than its first word, and the ghost tries them in
                # the same order for the same reason.
                for size in range(min(4, len(wordm)), 0, -1):
                    for i0 in range(0, len(wordm) - size + 1):
                        run = wordm[i0:i0 + size]
                        a, b = run[0].start(), run[-1].end()
                        typed = frag[a:b]
                        if len(typed) < MIN_PREFIX:
                            continue
                        # the run still under the caret
                        if tail_open and frag_start + b >= _tail_at:
                            continue
                        res = resolve_prefix(typed, _vocab(), kinds)
                        if res is None:
                            continue
                        if finish(res, frag_start + a, frag_start + b, frag):
                            return

        if once("funeral_home"):

            def _finish_fh(res, A, B, frag) -> bool:
                # ⚠️ THE EXPANSION GOES BACK THROUGH `resolve_funeral_home`, so a
                # tenant with two records under one name still asks, exactly as it
                # does for a fully typed name. One resolver, one answer.
                if res.chosen is not None:
                    fr = resolve_funeral_home(db, tenant_id, res.chosen.text)
                    if fr.party_id and _claim(spans, A, B, "funeral_home"):
                        values["funeral_home"] = fr.candidates[0].name
                        return True
                    # ⚠️ AMBIGUITY FOUND ONE LAYER DOWN STILL ASKS. An abbreviation can
                    # narrow to ONE name and that name still match two RECORDS; dropping
                    # it there would report "not understood" about a word the engine
                    # understood well enough to narrow, which is the complaint this
                    # whole slice answers.
                    if len(fr.candidates) > 1 and _claim(spans, A, B, "funeral_home"):
                        picks.append(Pick(
                            "funeral_home", res.prefix,
                            tuple((c.name, c.label) for c in fr.candidates),
                            fr.discriminators[0].value if fr.discriminators else "name",
                        ))
                        return True
                    return False
                # ⚠️ AN AMBIGUOUS ABBREVIATION IS THE ORDINARY CHOICE LIST, NEVER A
                # GUESS. The options are the FULL NAMES, because the row has to show
                # the director what the abbreviation would become.
                if len(res.matches) > 1 and _claim(spans, A, B, "funeral_home"):
                    picks.append(Pick(
                        "funeral_home", res.prefix,
                        tuple((m.text, m.note or m.text) for m in res.matches),
                        "name",
                    ))
                    return True
                return False

            _prefix_pass("funeral_home", KINDS_FUNERAL_HOME, _finish_fh)

        if once("vault"):
            from app.services.product_name_resolver import build_index
            from app.services.product_name_resolver import resolve as _rv

            _pidx = build_index(db)

            def _finish_vault(res, A, B, frag) -> bool:
                if res.chosen is not None:
                    vr = _rv(_pidx, res.chosen.text)
                    if vr.variant_template_id and _claim(spans, A, B, "vault"):
                        values["vault"] = vr.candidates[0].display_name
                        return True
                    # ⚠️ AMBIGUITY FOUND ONE LAYER DOWN STILL ASKS, AND IT IS NOT A
                    # HYPOTHETICAL — IT IS WHAT PRODUCTION DOES. Measured 2026-10-20,
                    # read-only, on James's own second phrase: "conti" narrows to the
                    # ONE term sunnycrest carries, `Continental Burial Vault`, and that
                    # NAME then matches two variants differing by SIZE. My first version
                    # returned False here and "conti" came back as not understood — on
                    # production only, because testco carries neither Continental and
                    # the carried filter never narrowed it to one. Local was green.
                    #
                    # ⚠️ THIS MIRRORS THE N-GRAM SCAN'S DECISION ABOVE RATHER THAN
                    # RE-DECIDING: form-only takes the form the slice implies and offers
                    # the other as a Switch; anything else asks, labelled by SKU.
                    # `test_both_vault_paths_settle_the_same_way` holds the two together.
                    if len(vr.candidates) > 1:
                        discs = tuple(d.value for d in vr.discriminators)
                        if discs == ("form",):
                            want = "urn_vault" if "urn" in frag.casefold() else "burial_vault"
                            mine = next(
                                (c for c in vr.candidates if c.form == want), None)
                            other = next(
                                (c for c in vr.candidates if c.form != want), None)
                            if mine is not None and _claim(spans, A, B, "vault"):
                                values["vault"] = mine.display_name
                                if other is not None:
                                    switches.append(Switch(
                                        field_id="vault",
                                        from_label=mine.display_name,
                                        to_value=other.display_name,
                                        to_label=f"Switch to {other.display_name}",
                                    ))
                                return True
                        if _claim(spans, A, B, "vault"):
                            picks.append(Pick(
                                "vault", res.prefix,
                                tuple((c.display_name, f"{c.sku} — {c.display_name}")
                                      for c in vr.candidates),
                                vr.discriminators[0].value
                                if vr.discriminators else None,
                            ))
                            return True
                    return False
                if len(res.matches) > 1 and _claim(spans, A, B, "vault"):
                    picks.append(Pick(
                        "vault", res.prefix,
                        tuple((m.text, m.note or m.text) for m in res.matches),
                        "name",
                    ))
                    return True
                return False

            _prefix_pass("vault", KINDS_VAULT, _finish_vault)

        # ── the service TIME, claimed before the date can swallow it ────
        # ⚠️ A TIME TOKEN IS NARROW AND A DATE IS NOT. `parse_date` on the fragment
        # "Thursday 10am" consumed the whole thing, so the time was lost. The time is
        # found and claimed first; the date pass below then sees only what is left.
        if once("service_time"):
            for frag_start, frag in _unclaimed_slices(line, spans):
                tm = _TIME_TOKEN.search(frag)
                if not tm:
                    continue
                pt = parse_time(tm.group(0))
                if pt and pt.get("value"):
                    a = frag_start + tm.start()
                    if _claim(spans, a, frag_start + tm.end(), "service_time"):
                        values["service_time"] = pt["value"]
                    break

        for frag in _leftovers(line, spans):
            if once("service_date"):
                pd = parse_date(frag)
                if pd and pd.get("value"):
                    i = low.find(frag.casefold())
                    a, b = _evidence(frag, i, pd)
                    if i >= 0 and _claim(spans, a, b, "service_date"):
                        values["service_date"] = pd["value"]
                        continue
            if once("service_time"):
                pt = parse_time(frag)
                if pt and pt.get("value"):
                    i = low.find(frag.casefold())
                    a, b = _evidence(frag, i, pt)
                    if i >= 0 and _claim(spans, a, b, "service_time"):
                        values["service_time"] = pt["value"]

        # ⚠️ A DISJOINTNESS ASSERTION STOOD HERE AND WAS DELETED, BECAUSE A BREAK
        # TEST PROVED IT WAS A TAUTOLOGY. It asserted that no two entries in `spans`
        # overlap. `_claim` refuses an overlapping span, so the list is disjoint BY
        # CONSTRUCTION and the assertion could not fail.
        #
        # The break: the original defective `service_location` pass was restored, so
        # "start an order for Hopkins Funeral Home" again produced BOTH
        # `service_location='funeral_home'` AND `funeral_home='Hopkins Funeral Home'`
        # from overlapping words. The assertion stayed SILENT — because the second
        # claim was refused, leaving one span, while the VALUE had already been
        # written on the line above the claim.
        #
        # ⚠️ THAT IS THE WHOLE LESSON AND IT IS WHY EVERY SITE NOW CLAIMS BEFORE IT
        # WRITES. The guarantee is not "the span list is disjoint" — that is free and
        # meaningless. It is "a field is only set from text no other field has taken",
        # which lives at each call site and is tested behaviourally in
        # `test_no_span_feeds_two_fields.py`. CLAUDE.md §11: a check that cannot be
        # made to fail is documentation, so it was filed as a comment and removed.

        # ⚠️ RE-STATEMENTS JOIN `unrecognized` RATHER THAN GETTING THEIR OWN FIELD.
        # The pane's job is the same for both: show the director text the engine did
        # not act on. A separate list would need a separate renderer for no gain.
        return LineExtraction(
            line=line,
            values=values,
            picks=tuple(picks),
            unrecognized=_leftovers(line, spans) + tuple(restated),
            switches=tuple(switches),
            spans=_describe_spans(line, spans),
        )


#: The extractor this slice uses. ⚠️ A module-level instance so the endpoint layer
#: names the seam rather than the implementation — swapping in a model-backed
#: extractor later is one line here and no change anywhere else.
EXTRACTOR: LineExtractor = DeterministicExtractor()


#: Every template field this extractor can write.
#:
#: ⚠️ DECLARED HERE AND CHECKED AGAINST THE SOURCE, so the declaration cannot lie.
#: `test_the_declared_writable_set_matches_what_the_code_writes` scans this module for
#: `values[...] = ` assignments and fails if the two disagree in either direction — a
#: field listed here that nothing writes, or a field written that is not listed.
#:
#: ⚠️ IT EXISTS BECAUSE THREE FIELDS AND STATES WERE FOUND, BY ACCIDENT, TO BE
#: UNREACHABLE: `lifes_reflections_symbol` had no extractor, `RowState.NEEDED` could
#: not occur, and `eta` had no parser. Each was discovered while looking for something
#: else. Together with `FieldDefinition.not_typeable` this partitions the template so
#: a fourth is a failing test rather than a discovery.
WRITABLE_FIELDS: frozenset[str] = frozenset({
    "burial_date",
    "cemetery",
    "cemetery_city",
    "cemetery_equipment",
    "date_of_birth",
    "date_of_death",
    "deceased_name",
    "eta",
    # ⚠️ ADDED 2026-10-14, AND THE RATCHET NAMED IT BEFORE I DID. `_chairs` writes
    # this alongside `cemetery_equipment` from one span, and I shipped the writer
    # without declaring it — `test_every_field_is_typeable.py` failed twice over, once
    # because the field looked unreachable from typed text and once because the
    # declaration disagreed with a scan of this module's own assignments. Exactly the
    # gap it was built for after `lifes_reflections_symbol`, `RowState.NEEDED` and
    # `eta`.
    "extra_chairs_count",
    "funeral_home",
    "grave_location",
    "legacy_print_name",
    "legacy_series",
    "lifes_reflections_symbol",
    "nameplate_date_format",
    QUESTION_PERSONALIZATION,
    "service_date",
    "service_location",
    "service_time",
    "vault",
})


class MentionPolicy(str, Enum):
    """What happens when one field is mentioned twice.

    ⚠️ EXPLICIT PER INPUT SOURCE, BY RULING (2026-10-12), because the two sources
    genuinely disagree and a single default would be wrong for one of them.

        FIRST_WINS   One line at a time, each a fresh statement the director just
                     made. An earlier answer is not silently overwritten; the
                     re-statement is reported so the pane can say "equipment is
                     already Full Equipment". This is `extract_line`'s behaviour and
                     it is unchanged.

        LAST_WINS    The WHOLE TEXT is the source and is re-read from scratch on every
                     pause. "full setup ... actually tent only" is ONE statement
                     containing a correction, and the director can see both words on
                     screen — so the later mention is simply the answer, and there is
                     nothing to report as a re-statement.

    ⚠️ AND THE CALL PIPELINE HAS NO POLICY HERE, WHICH IS WHY E6 IS SAFE BY
    CONSTRUCTION RATHER THAN BY CARE. `call_extraction_service.resolve_and_evaluate`
    does not import this module at all — measured: `typed_extraction` is imported by
    exactly ONE module in `app/`, `capture/session_service.py`. The call path reaches
    `capture.evaluate` through `_captured_from_result`, never through a line
    extractor, so no change here can reach it. Asserted in
    `test_whole_text_extraction.py` by enumeration, not by reading.
    """

    FIRST_WINS = "first_wins"
    LAST_WINS = "last_wins"


# ── the cemetery clause, parsed in NAMED STEPS ───────────────────────────
#
# ⚠️ THIS REPLACES ONE EXPRESSION THAT FAILED SILENTLY THREE TIMES, and the three are
# worth naming because they are three different ways for a single regex to break:
#
#   1. a greedy `{0,2}` name group ATE ITS OWN DELIMITER — "to St Mary's cemetery in
#      Auburn" asked the resolver for "St Mary's cemetery in" and matched nothing.
#   2. `{{2,30}}` in a plain r-string left the braces LITERAL, so the town group
#      matched the text "{2,30}" — i.e. never. The town was never captured at all.
#   3. `\s*(?:cemetery)?` CONSUMED THE SPACE THE TOWN GROUP NEEDED, so with
#      "Cemetery" omitted `\s+in\s+` could not match and the town was silently lost.
#
# Every one was invisible: the clause still matched, still produced a name, and the
# part that broke was OPTIONAL — so its absence looked like the director not having
# said a town. Ruled 2026-10-12: replace it with named, separately tested parts so a
# whitespace change in one cannot disable another.
#
# ⚠️ AND COMPOSING THE PARTS BACK INTO ONE PATTERN WOULD NOT HAVE HELPED. Failure 3
# was precisely an interaction BETWEEN two adjacent fragments; string-concatenating
# named fragments reproduces it exactly. So the clause is parsed in STEPS: each part
# is anchored at an explicit position, reports where it ended, and the next part
# starts from there. A part that consumes too much shortens its own span — visible —
# rather than starving the part after it.

#: Step 1: the words that introduce a cemetery.
#: ⚠️ THE MULTI-WORD MARKERS COME FIRST, AND THE REASON IS WHAT WAS BROKEN. A bare
#: `to` inside "headed to" matches at the LATER position, so the clause used to start
#: at the "to" and leave "headed" behind as text the engine could not place — the
#: cemetery resolved and the sentence still showed a Not-understood word. Listing the
#: longer forms first makes the intent explicit even though leftmost-match already
#: decides it: at the "h" of "headed", only `headed to` can match.
#:
#: ⚠️ "headed to" AND "out to" ADDED 2026-10-13 by James's walk note. Widening the
#: marker set cannot invent a cemetery — the span is claimed only when
#: `resolve_cemetery` returns a record, so "going to the shop" claims nothing.
_CEM_MARKER = re.compile(
    r"\b(?:going to|headed to|out to|burial at|buried at|to|at)\s+", re.I
)

#: Step 2: the name. ⚠️ THE LOOKAHEAD IS WHAT STOPS IT EATING ITS OWN DELIMITERS;
#: failure 1 was this group without it.
_CEM_STOP = r"(?!\b(?:cemetery|cemeteries|in|on|at|for|with|and)\b)"
#: ⚠️ THE PERIOD IS IN THE SET SINCE 2026-10-13, AND ITS ABSENCE WAS THE SAME BUG
#: `_CEM_TOWN` HAD ONE STEP OVER. The town charset gained `.` on 2026-10-12 for
#: "St. Albans"; this one did not, so an abbreviated TOWN read fine while an
#: abbreviated CEMETERY stopped dead at the period: "going to St. Mary's" parsed
#: `name='St'` and claimed only "going to St", leaving "Mary's" to be reported as
#: text the engine could not place. That is James's 11:24 walk note.
#:
#: ⚠️ AND THE VALUE WAS RIGHT THE WHOLE TIME, WHICH IS WHY IT SURVIVED. `name='St'`
#: still resolved to "St. Mary's Cemetery" on the seeded tenant, so every test that
#: asserted `values["cemetery"]` passed over the defect. The town was the second
#: casualty and silent: with the name ending early, the suffix and town steps ran
#: against the wrong offset and "St. Mary's Cemetery in Skaneateles" returned
#: `town=None` — not a wrong town, no town at all.
_CEM_NAME = re.compile(
    rf"{_CEM_STOP}[A-Za-z'][A-Za-z'\-.]*(?:\s+{_CEM_STOP}[A-Za-z'][A-Za-z'\-.]*){{0,2}}",
    re.I,
)

#: Step 3: the optional word "cemetery". ⚠️ IT OWNS ITS OWN LEADING SPACE, which is
#: failure 3 made structural: a step that does not match consumes NOTHING, so the
#: separator the next step needs is still there.
_CEM_SUFFIX = re.compile(r"\s+(?:cemetery|cemeteries)\b", re.I)

#: Step 4: the optional town. ⚠️ `{2,30}` in a PLAIN r-string — failure 2 was this
#: quantifier written as `{{2,30}}` inside an f-string, where the braces stayed
#: literal. Kept out of any f-string for that reason.
#: ⚠️ THE PERIOD IS IN THE SET BECAUSE A TEST FOUND IT MISSING. Towns are abbreviated
#: the way the cemeteries are — "St. Albans", "Mt. Vernon" — and the original charset
#: allowed apostrophes and hyphens but not periods, so those towns were silently
#: unreadable while the clause still matched and still produced a name. The same
#: failure mode as the three above, in a part nobody had tested alone.
#:
#: ⚠️ WORD-BOUNDED SINCE 2026-10-13, AND IT USED TO BE A 30-CHARACTER RUN:
#: `[A-Za-z'\-. ]{2,30}` — with a SPACE in the set, so it ran straight across word
#: boundaries and stopped wherever character 30 happened to fall. On comma-free text
#: that is mid-word. Measured: "st marys in auburn service at the church thursday
#: 10am" claimed through to "...Th" and reported **'ursday'** as text the engine
#: could not place. A director types no commas, so nothing stopped it.
#:
#: ⚠️ UP TO THREE WORDS, AND THE CALLER NARROWS — see `_narrow_town`. A stop-word
#: lookahead was tried here first and REJECTED A REAL TOWN: `_NOISE_WORDS` contains
#: "new", so "in New Hartford" matched nothing at all. The vocabulary that tells a
#: label from a place cannot be a word list, because towns are named after anything.
#: What CAN tell them apart is the records, which is the same rule the funeral-home
#: marker follows: the longest prefix that matches something real.
#: ⚠️ THE FIRST WORD NEEDS TWO CHARACTERS, DELIBERATELY. The old character
#: quantifier rejected a one-letter town as a side effect; keeping that rejection
#: explicit means "in A" is still not a town, which matters because a stray single
#: letter after "in" is far more likely to be a typo than a place.


@dataclass(frozen=True)
class CemeteryClause:
    """What one cemetery clause said, and exactly which characters each part used."""

    name: str
    town: str | None
    start: int
    end: int
    name_span: tuple[int, int]
    suffix_span: tuple[int, int] | None
    town_span: tuple[int, int] | None
    #: ⚠️ DID THE DIRECTOR WRITE "in <town>"? The caller treats the two forms
    #: differently and cannot tell them apart from the text alone once the clause is
    #: parsed. An explicit town is taken at face value and a conflicting one raises the
    #: pick (ruled 2026-10-12); a BARE town is only honoured when a cemetery of that
    #: name is actually in it — see `_towns_for_name`. Defaults True so a clause built
    #: without this field behaves as explicit, which is how every caller behaved before
    #: the bare form existed.
    town_explicit: bool = True


def _peel_trailing_town(
    line: str, name_span: tuple[int, int], known: frozenset[str]
) -> tuple[int, str, tuple[int, int]] | None:
    """A known town the NAME swallowed, as `(new_name_end, town, town_span)`.

    ⚠️ THE NAME IS GREEDY AND THAT IS WHY THIS EXISTS. `_CEM_NAME` takes up to three
    words, so "going to st marys skaneateles" parses `name='st marys skaneateles'` and
    `town=None` — measured 2026-10-29. The town is not missing from the clause; it is
    INSIDE the name, which is worse, because `resolve_cemetery` then looks up a cemetery
    whose name includes a town and finds nothing.

    ⚠️ LONGEST RUN FIRST, so a two-word town wins over its first word. "New Hartford"
    must not peel as "Hartford" leaving a name ending in "New".

    ⚠️ AND IT NEVER PEELS THE WHOLE NAME. A cemetery called after its town — plausible —
    would otherwise leave no name at all and the clause would resolve nothing.
    """
    a, b = name_span
    runs = [(m.start(), m.end()) for m in re.finditer(r"\S+", line[a:b])]
    if len(runs) < 2:
        return None
    for i in range(1, len(runs)):
        start = a + runs[i][0]
        # ⚠️ NARROWED OVER THE REST OF THE LINE, NOT JUST THE NAME SPAN, AND A TWO-WORD
        # TOWN IS WHY. `_CEM_NAME` takes at most three words, so "going to st marys new
        # hartford" matched `name='st marys new'` and left "hartford" outside it
        # entirely — a peel bounded by the name span found "new" (not a town) and gave
        # up, which is how my first version lost a real town. Measured.
        #
        # ⚠️ AND STRICTLY, so this cannot over-reach. `_narrow_town(strict=True)` returns
        # the LONGEST prefix that is a town we hold records for, and "" otherwise — so
        # "st marys tent only" peels nothing rather than claiming "tent", and a town
        # cannot swallow the clause behind it.
        town = _narrow_town(line[start:], known, strict=True)
        if town:
            return a + runs[i - 1][1], town, (start, start + len(town))
    return None


#: ⚠️ THE TOWN HELPERS MOVED TO `capture/towns.py` AND THESE NAMES ARE NOW ALIASES, so
#: every call site below is untouched. They moved because James ruled on 2026-10-29 that
#: ONE town pattern is shared by the capture bar and the cemetery pane — and a ratchet
#: forbids the pane importing THIS module, so a leaf module is the only place both can
#: take it from. Same shape as `noise.py`, same reason.
from app.services.capture.towns import CEM_TOWN as _CEM_TOWN
from app.services.capture.towns import CEM_TOWN_BARE as _CEM_TOWN_BARE
from app.services.capture.towns import narrow_town as _narrow_town
from app.services.capture.towns import town_after as _town_after
from app.services.capture.towns import town_before as _town_before
from app.services.capture.towns import towns_for_name as _towns_for_name


def parse_cemetery_clause(
    line: str, known_towns: frozenset[str] | None = None
) -> CemeteryClause | None:
    """Marker, name, optional "cemetery", optional town — in that order.

    ⚠️ EACH STEP STARTS WHERE THE LAST ONE ENDED. That is the whole design: there is
    no shared backtracking and no fragment adjacency, so a change to one part can
    shorten or lengthen its own span and nothing else.

    ⚠️ `known_towns` IS OPTIONAL AND CHANGES TWO THINGS WHEN GIVEN, per James's ruling of
    2026-10-29 ("towns typed with a cemetery are part of it, not held words"): a town the
    greedy NAME swallowed is peeled back off it, and a town following with no "in" is
    read. Without it the parser behaves exactly as it did — which keeps every existing
    caller and every existing test on the old path rather than silently reinterpreting
    them.
    """
    mk = _CEM_MARKER.search(line)
    if not mk:
        return None
    nm = _CEM_NAME.match(line, mk.end())
    if not nm:
        return None
    name_span = nm.span()
    name_text = nm.group(0)
    bare_town: str | None = None
    bare_span: tuple[int, int] | None = None

    if known_towns:
        peeled = _peel_trailing_town(line, name_span, known_towns)
        if peeled is not None:
            new_end, bare_town, bare_span = peeled
            name_span = (name_span[0], new_end)
            name_text = line[name_span[0]:new_end]

    pos = name_span[1]
    sfx = _CEM_SUFFIX.match(line, pos)
    if sfx:
        pos = sfx.end()
    twn = _CEM_TOWN.match(line, pos)
    explicit = False
    if twn:
        pos = twn.end()
        town, town_span = twn.group(1).strip() or None, twn.span(1)
        explicit = True
    elif bare_town is not None:
        # ⚠️ THE PEELED TOWN LOSES TO AN "in <town>" THAT FOLLOWS IT, and my first version
        # got this backwards. "going to st marys skaneateles in auburn" is a director
        # correcting themselves, and the LAST thing they said wins — the rule the rest of
        # this module runs on. The `_CEM_TOWN` match above starts at the end of the
        # SHORTENED name, which is before the peeled town, so it cannot see the "in"; it
        # has to be retried from the end of the peel.
        after_peel = _CEM_TOWN.match(line, bare_span[1]) if bare_span else None
        if after_peel is not None:
            town, town_span = after_peel.group(1).strip() or None, after_peel.span(1)
            pos = after_peel.end()
            explicit = True
        else:
            town, town_span = bare_town, bare_span
            if bare_span is not None and bare_span[1] > pos:
                pos = bare_span[1]
    else:
        town, town_span = None, None
        if known_towns:
            after = _town_after(line[pos:], known_towns)
            if after is not None:
                town, used = after
                town_span = (pos + (len(line[pos:]) - len(line[pos:].lstrip())), pos + used)
                pos = pos + used

    return CemeteryClause(
        name=name_text.strip(),
        town=(town.strip() if town else None) or None,
        start=mk.start(),
        end=pos,
        name_span=name_span,
        suffix_span=sfx.span() if sfx else None,
        town_span=town_span,
        town_explicit=explicit,
    )


#: A clock time as a director writes one: "10am", "10:30", "2:30 pm", "11:30".
#:
#: ⚠️ THIS EXISTS BECAUSE THE DATE PASS SWALLOWED THE TIME. `parse_date` is greedy and
#: the pass claimed the WHOLE leftover fragment, so "Thursday 10am" produced a date and
#: NO TIME — measured on James's own sample order, where "service at the church
#: Thursday 10am" captured the location and the date and lost the 10am. A time token is
#: narrowly shaped and a date is not, so the time is found and claimed FIRST and the
#: date gets what remains. Same rule as everywhere else today: no span feeds two
#: fields, and the more specific claim goes first.
_TIME_TOKEN = re.compile(
    r"\b(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)\b|\b(\d{1,2}):(\d{2})\b",
    re.I,
)

#: A bare hour sitting against the word "graveside".
#:
#: ⚠️ RULED 2026-10-13: "a graveside service is just a service whose location is the
#: graveside, with its time being the burial time", and the phrasings James named are
#: "11 graveside", "graveside at 11" and "graveside friday 11am". The third already
#: worked once "graveside" stopped being a burial-date marker; the first two did not,
#: because a BARE hour is not a `_TIME_TOKEN` — deliberately, since a loose number is
#: far more often a size, a lot or a section.
#:
#: ⚠️ ADJACENCY TO THE WORD IS WHAT LICENSES THE BARE NUMBER, and nothing wider. "11"
#: anywhere else in a sentence is still not a time. That is the whole reason this is a
#: separate pattern rather than a relaxation of `_TIME_TOKEN`.
#: The word itself. ⚠️ UNAMBIGUOUS, WHICH IS WHY ITS PRESENCE IS ENOUGH. "graveside"
#: names one service location and nothing else in this vocabulary; a director who says
#: it has said where the service is.
_GRAVESIDE_WORD = re.compile(r"\bgraveside\b", re.I)

#: A bare hour sitting against the word "graveside", from either side.
#:
#: ⚠️ TWO PATTERNS, NOT ONE ALTERNATION, AND THE REASON IS CONSUMPTION. Written as
#: `(\d+)\s+graveside|graveside\s+at\s+(\d+)`, the first branch matched the SECTION
#: NUMBER in "section 4 graveside at 11" and ate the word "graveside" with it — so the
#: second branch could never see the sentence and the real "11" was invisible. The
#: before-form now uses a LOOKAHEAD, so it never owns the word and both forms get a
#: look at every sentence.
#:
#: ⚠️ A BARE HOUR IS ONLY A TIME NEXT TO THIS WORD. Elsewhere it is a size, a lot or a
#: section, which is why `_TIME_TOKEN` rightly refuses it and why this is a separate
#: rule rather than a relaxation of that one.
_GRAVESIDE_TIME_BEFORE = re.compile(
    r"\b(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?\s+(?=graveside\b)", re.I
)
_GRAVESIDE_TIME_AFTER = re.compile(
    r"\bgraveside\b(?:\s+at)?\s+(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?", re.I
)

#: Words that own the number after them, so the number is a PLACE and not a time.
#:
#: ⚠️ THE SAME RULE `pick-digit.ts` NEEDS, for the same reason. Measured: without it,
#: "section 4 graveside at 11" read the section number as four in the afternoon.
_GRAVE_NUMBER_LABELS = ("section", "sec", "lot", "space", "grave", "sp", "no", "number")


def _graveside_time(line: str) -> tuple[str, tuple[int, int]] | None:
    """The service time from a graveside phrase, and the span of the time itself.

    ⚠️ THE AM/PM DEFAULT IS THE PROTOTYPE'S OWN RULE, verbatim from
    `docs/prototypes/2026-10-01-opas-overlay.html`: `ap=(h>=7&&h<=11)?'AM':'PM'`. A
    graveside service at "11" is eleven in the morning and at "2" is two in the
    afternoon; inventing a second convention here would make the same words mean
    different times in two places.

    ⚠️ THE SPAN IS THE TIME ONLY, NOT THE PHRASE. The location pass runs earlier and
    has already claimed the word "graveside", so a claim covering it would fail and
    this rule would silently do nothing — measured, and it did.
    """
    for pattern in (_GRAVESIDE_TIME_BEFORE, _GRAVESIDE_TIME_AFTER):
        for m in pattern.finditer(line):
            before = line[: m.start(1)]
            tail = re.search(r"([A-Za-z]+)[\s.]*$", before)
            if tail is not None and tail.group(1).casefold() in _GRAVE_NUMBER_LABELS:
                continue
            h = int(m.group(1))
            if h < 1 or h > 23:
                continue
            mins = int(m.group(2)) if m.group(2) else 0
            if mins > 59:
                continue
            tag = (m.group(3) or "").replace(".", "").lower()
            if tag.startswith("p"):
                if h < 12:
                    h += 12
            elif tag.startswith("a"):
                if h == 12:
                    h = 0
            elif h < 7:
                # 7..11 reads as morning; 1..6 as afternoon. 12 stays noon.
                h += 12
            end = max(
                m.end(g) for g in (1, 2, 3) if m.group(g) is not None
            )
            return f"{h:02d}:{mins:02d}", (m.start(1), end)
    return None


#: Markers that mean the CEMETERY ARRIVAL rather than the service.
#:
#: ⚠️ `eta` HAD NO PARSER AT ALL. The field is on the template, is applicable whenever
#: the service is not graveside, and nothing could ever fill it — "eta 11:30", "eta is
#: 11:30" and "arrival 11:30" all extracted nothing. Third instance today of complete
#: machinery behind an unprovisioned entrance, after the vinyl symbol field and
#: `RowState.NEEDED`. ⚠️ ADDED SCOPE, FLAGGED: no ruling asked for this parser; the
#: dispatch's own walk sentence contains "eta 11:30", so without it the walk loses a
#: field in front of James.
_ETA_MARKER = re.compile(r"\b(?:eta|e\.t\.a\.?|arrival|arriv(?:e|ing)|at the cemetery(?: at)?)\b", re.I)

#: Where one statement ends and the next begins.
#:
#: ⚠️ NOT ON BARE " and ", AND THAT IS THE WHOLE DIFFICULTY. Three real phrases depend
#: on it: "device and grass" (one equipment package), "Loved and Cherished" (a product
#: name), "nameplate and vinyl" (one personalization answer). Splitting there would cut
#: each in half and leave both halves unrecognized.
#:
#: ⚠️ " actually " IS A SEPARATOR BECAUSE IT IS HOW A CORRECTION SOUNDS. James's own
#: sample order ends "full setup actually tent only", and under LAST_WINS the later
#: segment is the answer — which is exactly what he described.
_SEGMENT_RE = re.compile(
    r"\n|[,;]|\bactually\b|\bscratch that\b|\bno wait\b|\bmake that\b",
    re.I,
)


@dataclass(frozen=True)
class TextExtraction:
    """Everything one re-read of the whole text yields.

    ⚠️ NOTHING ACCUMULATES. `unrecognized` is rebuilt from scratch every time, because
    the text is the source: if the director deletes a word, the pane must stop
    reporting it. The line-append model accumulated, which was right when each line
    was a separate event and is wrong now.
    """

    text: str
    values: dict[str, object]
    picks: tuple[Pick, ...] = ()
    unrecognized: tuple[str, ...] = ()
    #: ⚠️ KEYED BY FIELD AND LAST-WINS LIKE EVERYTHING ELSE. A later segment naming
    #: the same vault replaces the earlier switch rather than offering two.
    switches: tuple[Switch, ...] = ()
    policy: MentionPolicy = MentionPolicy.LAST_WINS
    #: ⚠️ WHOLE-TEXT COORDINATES, ordered by position. See `TextSpan`.
    spans: tuple[TextSpan, ...] = ()


def segments_with_offsets(text: str) -> tuple[tuple[int, str], ...]:
    """`(offset_in_text, segment)` for each statement, in order. Empty pieces dropped.

    ⚠️ THE OFFSET IS THE WHOLE REASON THIS EXISTS, and it is the same argument
    `_unclaimed_slices` makes one level down. Each segment is extracted in isolation,
    so every span a parser records is relative to THAT SEGMENT; reporting spans
    against the text the director can see needs the segment's own position. `re.split`
    throws that away, and recovering it with `text.find(segment)` is wrong the moment
    the same words appear in two segments — "monticello, actually monticello" is not
    a strange thing to type.

    ⚠️ THE OFFSET POINTS AT THE STRIPPED SEGMENT, NOT THE RAW CHUNK. Segments are
    `.strip()`ed, so leading whitespace has to be added back or every span after a
    ", " separator would render two characters to the left.
    """
    out: list[tuple[int, str]] = []
    body = text or ""
    pos = 0

    def take(start: int, end: int) -> None:
        raw = body[start:end]
        stripped = raw.strip()
        if stripped:
            out.append((start + (len(raw) - len(raw.lstrip())), stripped))

    for m in _SEGMENT_RE.finditer(body):
        take(pos, m.start())
        pos = m.end()
    take(pos, len(body))
    return tuple(out)


def segments(text: str) -> tuple[str, ...]:
    """The text as separate statements, in order. Empty pieces dropped.

    ⚠️ DELEGATES SINCE 2026-10-15 RATHER THAN HOLDING A SECOND COPY of the splitting
    rule. Two implementations of "where does a statement end" would look right in
    isolation and drift on the first edit — the same reason `_leftovers` was made to
    delegate to `_leftover_pairs` on 2026-10-07.
    """
    return tuple(piece for _, piece in segments_with_offsets(text))


def extract_text(
    db: Session,
    *,
    tenant_id: str,
    text: str,
    resolutions: dict[str, object] | None = None,
    prefill: dict[str, object] | None = None,
) -> TextExtraction:
    """Re-read the WHOLE typed text. Last mention wins; resolutions outrank it.

    ⚠️ THREE TIERS SINCE 2026-10-24, AND `prefill` IS THE ONE BELOW THE TEXT:

        prefill       a pane's choice made BEFORE any text. Fills a field the text says
                      nothing about; yields the moment the text names something else.
        text          last mention wins, as below.
        resolutions   the director's decision ABOUT ambiguous text. Outranks it.

    The order is the ruling: "a funeral home filled from the Customer Pane is the
    person's choice… Re-extraction can't clear it. It's replaced only if the person
    names a different funeral home in the text" (James, 2026-10-24).

    ⚠️ IT COMPOSES `extract_line` RATHER THAN REPLACING IT, which is why the span rule,
    every vocabulary, the party resolvers and the claim-before-write discipline all
    still apply unchanged. Each segment is extracted in isolation — so spans cannot
    collide across a comma, which they never should — and later segments overwrite
    earlier ones.

    ⚠️ A LATER MENTION REPLACES WHATEVER THE EARLIER ONE PRODUCED, VALUE OR QUESTION.
    "Continental, actually 34 inch Continental" must end with the vault RESOLVED and
    NO pending pick; "34 inch Continental, actually Continental" must end with the
    pick and no value. So the last segment to say anything about a field decides which
    of the two it is — tracked per field rather than by merging two dicts, because
    `values.update()` plus a separate pick list cannot express "the pick replaced the
    value".

    ⚠️ RESOLUTIONS OUTRANK RE-EXTRACTION, BY RULING. A pick the director settled by
    CLICKING is a decision about text that is still on screen and still ambiguous;
    re-reading that text would raise the same question again on the next keystroke and
    the pane would be unusable.
    """
    assert isinstance(text, str), type(text)
    last: dict[str, tuple[str, object]] = {}
    unrecognized: list[str] = []
    #: field_id -> the switch most recently offered for it. Last-wins, like values.
    switch_by_field: dict[str, Switch] = {}

    segs = segments(text)

    # ── pass 1: each segment in isolation, which is what makes LAST_WINS possible ──
    for _i, segment in enumerate(segs):
        # ⚠️ ONLY THE LAST SEGMENT HAS AN OPEN TAIL. "hopk, thursday" has moved past
        # "hopk" even though it ends that segment.
        ex = EXTRACTOR.extract_line(
            db, tenant_id=tenant_id, line=segment, answers={},
            gating={GATING_TAIL_OPEN: _i == len(segs) - 1},
        )
        for field_id, value in ex.values.items():
            last[field_id] = ("value", value)
        for pick in ex.picks:
            last[pick.field_id] = ("pick", pick)
        for sw in ex.switches:
            switch_by_field[sw.field_id] = sw

    # ── pass 2: the same segments, re-read with what pass 1 learned as GATING ──
    #
    # ⚠️ A SECOND PASS, NOT A SMARTER FIRST ONE, AND THE ORDER IS THE REASON. A GATED
    # pass can only fire once something ELSEWHERE in the text has been read: the
    # vinyl-symbol pass runs only when the chosen personalization bears vinyl, and a
    # segment that says just "cross" cannot know that from its own words. Measured
    # over HTTP on dev: "nameplate and vinyl, cross" came back with `cross`
    # UNRECOGNIZED and no symbol captured, because segment isolation hid the answer
    # that was two segments earlier.
    #
    # ⚠️ IT CAN ONLY ADD, NEVER OVERWRITE, and that is what keeps LAST_WINS intact. A
    # field pass 1 decided — value or pick — is left exactly as it was; pass 2's
    # result for it is discarded. So the second read cannot reorder anything, and the
    # policy stays "the last segment to SAY something about a field decides".
    #
    # ⚠️ UNRECOGNIZED IS COLLECTED FROM PASS 2, NOT PASS 1. Pass 1's leftovers include
    # every word a gated pass was about to claim, so reporting them would tell the
    # director "cross" was not understood in the same response that captures it.
    gating = {
        field_id: payload
        for field_id, (kind, payload) in last.items()
        if kind == "value"
    }
    # ⚠️ SNAPSHOT TAKEN BEFORE THE LOOP, NOT TESTED AGAINST `last` INSIDE IT, AND THE
    # DIFFERENCE IS LAST_WINS. My first version guarded with `if field_id not in last`,
    # which made pass 2 FIRST_WINS WITHIN ITSELF: the first segment to produce a
    # gated field put it in `last`, and every later segment was then skipped. Measured
    # — "vinyl, cross, actually praying hands" captured `cross` and discarded the
    # correction, which is the exact policy whole-text extraction exists to provide.
    # Guarding against the SNAPSHOT lets pass-2 segments overwrite each other while
    # still never touching what pass 1 decided.
    decided = frozenset(last)
    # ⚠️ SPANS COME FROM PASS 2 FOR THE SAME REASON `unrecognized` DOES. Pass 1's
    # leftovers include every word a gated pass is about to claim, so a span list
    # built from pass 1 would put a dotted "not understood" underline beneath the
    # very word the response captures — "nameplate and vinyl, cross" would underline
    # `cross` while filling the symbol row.
    text_spans: list[TextSpan] = []
    _segs_off = list(segments_with_offsets(text))
    for _i, (offset, segment) in enumerate(_segs_off):
        ex = EXTRACTOR.extract_line(
            db, tenant_id=tenant_id, line=segment, answers={},
            gating={**gating, GATING_TAIL_OPEN: _i == len(_segs_off) - 1},
        )
        # ⚠️ SHIFTED INTO WHOLE-TEXT COORDINATES HERE, where the segment's own offset
        # is still in hand. The pane renders over the text the director can see.
        text_spans.extend(
            TextSpan(start=sp.start + offset, end=sp.end + offset,
                     state=sp.state, field_ids=sp.field_ids)
            for sp in ex.spans
        )
        for field_id, value in ex.values.items():
            if field_id not in decided:
                last[field_id] = ("value", value)
        for pick in ex.picks:
            if pick.field_id not in decided:
                last[pick.field_id] = ("pick", pick)
        for sw in ex.switches:
            if sw.field_id not in decided:
                switch_by_field[sw.field_id] = sw
        unrecognized.extend(ex.unrecognized)

    values: dict[str, object] = {}
    picks: list[Pick] = []
    for field_id, (kind, payload) in last.items():
        if kind == "value":
            values[field_id] = payload
        else:
            picks.append(payload)

    # ── CLAUSE 2: A BARE NAME MID-SENTENCE (James, 2026-10-28) ──────────────
    #
    # ⚠️ IT RUNS HERE, OVER THE WHOLE TEXT, AND THE FIRST ATTEMPT PUT IT IN
    # `extract_line` WHERE IT COULD NOT WORK. A director's commas SPLIT the text into
    # statements: "new order for riverside, keegan, thursday" is three segments, and
    # inside the middle one "keegan" has nothing before or after it. The clause's whole
    # evidence is that a word sits BETWEEN two things the engine understood — which is a
    # property of the typed TEXT, not of a segment. Measured before moving it: the
    # per-line version fired on nothing.
    #
    # ⚠️ AND "MID-SENTENCE" IN THIS CODEBASE MEANS MID-TEXT. The dispatch's word is
    # "sentence"; a sentence here is `segments()`-plural, so reading it as a single
    # segment is the narrower claim and the wrong one.
    if "deceased_name" not in values and not any(
        pk.field_id == "deceased_name" for pk in picks
    ):
        _claimed = sorted(
            (sp.start, sp.end) for sp in text_spans if sp.state == "captured"
        )
        if _claimed:
            _known: list[str] = []
            try:
                from app.services.party_resolver import (
                    cemetery_rows as _cem_rows,
                    funeral_home_rows as _fh_rows,
                )

                _known += [n for _i, n, _c in _cem_rows(db, tenant_id)]
                _known += [n for _i, n, _c in _fh_rows(db, tenant_id)]
            except SQLAlchemyError:
                # ⚠️ NARROW, AND IT DEGRADES THE GUARD RATHER THAN THE CLAUSE. With no
                # vocabulary the typo test cannot fire, so a mistyped funeral home could
                # be taken as a name. That direction is deliberate: the clause's own
                # evidence still holds, and a filled row the director can correct beats a
                # held word they have to place by hand. Not `except Exception` — sweep
                # item 1 is about precisely that.
                _known = []
            _bare = bare_name_before_a_term(
                text, list(_claimed), _unclaimed_slices(text, list(_claimed)),
                known_terms=_known,
            )
            if _bare is not None:
                _name, _a, _b = _bare
                values["deceased_name"] = _name
                # ⚠️ THE WORD MUST STOP BEING HELD, OR THE PANE SHOWS IT IN BOTH PLACES —
                # filled on the Deceased row AND in "not placed yet". The held list is
                # noise-stripped text, so the comparison is on the stripped form.
                _nf = _name.casefold()
                unrecognized = [u for u in unrecognized if u.casefold() != _nf]
                # ⚠️ AND THE SPAN FLIPS TO `captured`, so the bar underlines it the way it
                # underlines every other filled field rather than dotting it as unknown.
                text_spans = [
                    sp for sp in text_spans
                    if not (sp.start >= _a and sp.end <= _b and sp.state == "unrecognized")
                ]
                text_spans.append(
                    TextSpan(start=_a, end=_b, state="captured",
                             field_ids=("deceased_name",))
                )
                text_spans.sort(key=lambda sp: (sp.start, sp.end))

    # ⚠️ BENEATH THE TEXT, WHICH IS THE WHOLE POINT, SO `setdefault` AND NOT `[...] =`.
    # A prefilled field the text is silent about stays filled; one the text names
    # differently is replaced by the text and gets the ordinary conflict handling, since
    # the text's value is already in `values` by the time this runs.
    #
    # ⚠️ AND A PENDING PICK IS NOT "SILENT". If the text produced a QUESTION for the
    # field, the director is being asked which of several things they meant — answering
    # it from a prefill would settle their question for them without saying so. The
    # prefill is skipped and the pick stands.
    asked = {p.field_id for p in picks}
    for field_id, value in (prefill or {}).items():
        if field_id in values or field_id in asked:
            continue
        values[field_id] = value

    for field_id, value in (resolutions or {}).items():
        values[field_id] = value
        picks = [p for p in picks if p.field_id != field_id]
        # ⚠️ THE DIRECTOR HAS DECIDED, SO THERE IS NOTHING LEFT TO OFFER. A switch
        # surviving its own resolution would invite them to undo the click they just
        # made, and — because resolutions outrank extraction — the offer would come
        # back on every keystroke.
        switch_by_field.pop(field_id, None)

    # ⚠️ A SWITCH IS DROPPED THE MOMENT ITS FIELD STOPS BEING A SWITCH. If a later
    # segment resolves the vault outright, or a resolution settles it, the offer is
    # no longer true — and an offer to "switch to the urn vault" on a field the
    # director has since pinned would be the response contradicting itself again.
    # ⚠️ THE VALUE MUST STILL BE THE ONE THE SWITCH WAS OFFERED AGAINST, not merely
    # present. A later segment naming a different vault replaces the value and leaves
    # a stale offer pointing at the wrong counterpart; comparing the label catches
    # that where an `in values` check cannot.
    switches = tuple(
        sw for sw in switch_by_field.values()
        if values.get(sw.field_id) == sw.from_label
    )
    return TextExtraction(
        text=text,
        values=values,
        picks=tuple(picks),
        unrecognized=tuple(unrecognized),
        switches=switches,
        policy=MentionPolicy.LAST_WINS,
        spans=tuple(sorted(text_spans, key=lambda s: (s.start, s.end))),
    )


@dataclass(frozen=True)
class Conflict:
    """The director said something the vault does not allow.

    ⚠️ THIS IS NOT "NOT UNDERSTOOD". The extractor understood both phrases perfectly;
    they contradict each other. "Continental 34, nameplate and vinyl" names a vault
    that offers `nameplate_only` and a personalization that is not in that set. Filing
    it under `unrecognized` would tell the director the words were unreadable, when
    the problem is that the combination is not available.

    ⚠️ AND IT IS NOT DROPPED. `value` and `permitted` are both carried, so the pane can
    say what was asked for AND what is available — which is the only form of this
    message a director can act on.
    """

    field_id: str
    value: object
    permitted: tuple[str, ...]
    message: str


def evaluate_typed(db: Session, *, tenant_id: str | None, answers: dict[str, object]):
    """Resolve the vault from a typed session's answers and evaluate the capture.

    Returns `(resolution, CaptureState, conflicts)`.

    ⚠️ A THIRD ELEMENT WAS ADDED 2026-10-12 BECAUSE THIS FUNCTION USED TO RAISE INTO A
    500. Measured over HTTP on dev, not in a test: typing "Continental 34 … nameplate
    and vinyl" made the extractor produce `personalization=
    'nameplate_and_lifes_reflections'` against a vault whose availability permits only
    `nameplate_only`, `capture.evaluate` raised `UnpermittedAnswer`, and the request
    returned `Internal Server Error`. The pane died mid-sentence.

    ⚠️ IT WAS INVISIBLE TO EVERY TEST BECAUSE THE TEST TENANTS HAVE NO PRODUCTS. With
    no vault resolving, availability never narrows, `permitted_answers` is empty, and
    `_reject_unpermitted` returns early by design. A test can pass because data is
    MISSING (CLAUDE.md §11) — and the raise was documented in a test comment
    (`test_vinyl_is_what_the_office_says.py:40`) as expected behaviour, with no handler
    anywhere in `app/`. A raise whose only reader is a test is an unhandled error on
    every live path.

    ⚠️ THE CALL PIPELINE HAS THE SAME HOLE AND IT IS NOT CLOSED HERE. `evaluate_typed`
    is reached only from `capture/session_service.py` (measured by enumeration), so
    this change cannot touch the call path — which is required (E6) and also means
    `resolve_and_evaluate` still raises into a 500 on the same input. Reported, not
    fixed: closing it is a change to call-overlay behaviour and that needs James.

    ⚠️ THE CONFLICTING ANSWER IS WITHHELD FROM `evaluate`, NOT FROM THE DIRECTOR. It
    cannot go into `evaluate` — that is what raises — so the capture is evaluated
    without it and the conflict is returned alongside, for the pane to show. The
    WORDING, and whether this should instead become a numbered pick, is James's call;
    not crashing is not.

    ⚠️ THIS IS A SIBLING OF `call_extraction_service.resolve_and_evaluate`, NOT A REUSE
    OF IT, AND THE REASON IS A KEY-SHAPE MISMATCH RATHER THAN A PREFERENCE. That
    function takes the EXTRACTION PAYLOAD's names — `vault_type`, `funeral_home_name`,
    `cemetery_name` — and renames them to capture field ids via
    `_captured_from_result`. A typed line already produces field ids, because the pane
    renders the template's own fields. Feeding it through `resolve_and_evaluate` would
    mean reverse-mapping field ids back into payload names so the rename could undo it.
    Two renames to arrive where we started.

    ⚠️ WHAT IT DELIBERATELY SHARES is everything that matters: the same
    `product_name_resolver`, the same `read_personalization_config`, the same
    `capture.evaluate`, the same template, and the same `vault_form` rule — including
    `None` for an ambiguous set, so an ambiguous vault reads INDETERMINATE here exactly
    as it does on a call. The two seams must not drift; `test_typed_capture_slice1.py`
    asserts they agree on a shared case.

    ⚠️ THE CALL PATH IS UNTOUCHED. `resolve_and_evaluate` keeps its signature and its
    callers (E6: existing call-overlay behaviour must not change).
    """
    from app.services import capture
    from app.services.personalization.enrollment import resolve_availability_config
    from app.services.product_name_resolver import build_index, resolve as resolve_vault

    from app.services.capture.vault_form import linked_variant

    phrase = str(answers.get("vault") or "").strip()

    # ⚠️ THE TENANT'S EXPLICIT LINK WINS, AND THE RESOLVER IS NOT CONSULTED AT ALL WHEN
    # IT ANSWERS. James's ruling of 2026-10-28: "An explicit
    # products.variant_template_id wins over name resolution wherever a vault's
    # variant is resolved (form ladder AND availability)."
    #
    # ⚠️ IT MATTERS MOST EXACTLY WHERE THE RESOLVER IS WEAKEST. `Continental Burial
    # Vault` returns TWO candidates — the standard and the 34-inch — so the resolver
    # abstains and personalization was never asked on it, even on a tenant that had
    # declared which one it sells. The link settles both halves at once.
    linked = linked_variant(db, tenant_id=tenant_id, vault=phrase or None)
    # ⚠️ BOUND ON BOTH PATHS, AND THIS LINE IS NOT TIDINESS. Two sites further down
    # read `resolution` — the `vault_label` for a conflict message and the
    # `_permitted_for` call — so leaving it unbound on the link path would raise
    # NameError only when a product IS linked. That is only Sunnycrest, and only in
    # the walk: a crash reachable in production and in no test on a dev database,
    # where nothing is linked.
    resolution = None
    if linked.via is not None:
        vault_product_id = linked.variant_template_id
        vault_form = linked.form
    else:
        resolution = resolve_vault(build_index(db), phrase or None)
        vault_product_id = resolution.variant_template_id
        # ⚠️ UNCHANGED FOR AN UNLINKED PRODUCT, DELIBERATELY — the ruling's second
        # half is "unlinked products behave exactly as today", and this is the rule
        # that would be easiest to loosen by accident. None FOR AMBIGUOUS, matching
        # `_resolved_form`: an ambiguous set can span forms ("Graveliner" spans
        # grave_liner and urn_vault), so a form read off candidates[0] would be
        # whichever the sort put first. NOTE this is STRICTER than the form ladder's
        # unanimity rule, and the difference is pre-existing and intentional.
        vault_form = None
        if resolution.variant_template_id and resolution.candidates:
            vault_form = resolution.candidates[0].form

    from app.services.capture.missing import UnpermittedAnswer

    config = resolve_availability_config(db, tenant_id)
    template = capture.template_for(capture.SALES_ORDER)
    conflicts: list[Conflict] = []
    trial = dict(answers)

    # ⚠️ A BOUNDED LOOP, NOT `while True`. `evaluate` reports ONE unpermitted answer per
    # call, so several contradictions need several passes — and a loop with no ceiling
    # would hang the request if a pass ever failed to remove the field it named. The
    # ceiling is the number of answers, which is the most passes that can make progress.
    for _ in range(len(answers) + 1):
        try:
            state = capture.evaluate(
                trial,
                vault_product_id=vault_product_id,
                personalization_config=config,
                vault_form=vault_form,
                platform_fields=template,
            )
            break
        except UnpermittedAnswer as e:
            field_id = _conflicting_field(e, trial)
            if field_id is None:
                # ⚠️ RE-RAISED RATHER THAN SWALLOWED. If the message cannot be
                # attributed to a field, removing a guess would silently discard an
                # answer; a 500 with a real traceback is better than a quiet wrong
                # order. This is the one path that still produces one, deliberately.
                raise
            conflicts.append(
                Conflict(
                    field_id=field_id,
                    value=trial[field_id],
                    permitted=_permitted_from(e),
                    message=str(e),
                )
            )
            del trial[field_id]
    else:  # pragma: no cover - the ceiling is unreachable while each pass removes one
        raise RuntimeError(
            f"evaluate_typed did not settle after {len(answers) + 1} passes"
        )

    # ⚠️ AN ANSWER WHOSE FIELD IS NOT APPLICABLE IS A SILENT DROP, AND THIS IS WHERE
    # IT USED TO HAPPEN. Walk note 2026-10-13: "nameplate only" on a Monticello
    # produced NO row — correct, the vault offers no personalization — and NO
    # conflict either, so the director was never told. `capture.evaluate` does not
    # raise for this case: availability NOT_OFFERED filters the field into
    # `not_applicable` and the answer is simply ignored.
    #
    # ⚠️ IT IS A DIFFERENT SILENCE FROM `UnpermittedAnswer`, WHICH ALREADY HAD A
    # HANDLER. That one fires when the vault offers a DIFFERENT set; this one when it
    # offers nothing at all. Both now arrive as conflicts, so the pane has one thing
    # to render and Approve has one thing to block on.
    #
    # ⚠️ ONLY FIELDS THE DIRECTOR ACTUALLY ANSWERED. `not_applicable` is full of
    # fields nobody mentioned (`legacy_print_name`, `nameplate_date_format`); naming
    # those would be noise about questions never asked.
    vault_label = ""
    if resolution is not None and resolution.candidates and resolution.variant_template_id:
        vault_label = resolution.candidates[0].display_name
    elif answers.get("vault"):
        # ⚠️ ALSO THE LINK PATH, AND IT IS THE BETTER LABEL THERE. When the tenant has
        # linked the product, the name the director typed IS the tenant's own name for
        # it; the catalogue's `display_name` would rename it in the message.
        vault_label = str(answers["vault"])

    # ⚠️ A TYPED BURIAL DATE THAT DISAGREES WITH THE SERVICE DATE IS A CONTRADICTION,
    # NOT A SECOND FACT. Ruled 2026-10-13: the burial is always the service day, and
    # when it is not, what the director means is a GRAVESIDE SERVICE. So two different
    # dates are two readings of one day, and storing the second quietly would put a
    # date on the order that the office never agreed to.
    #
    # ⚠️ IT IS REPORTED RATHER THAN CORRECTED. Picking one of the two would be the
    # engine deciding which day the funeral is on.
    burial = answers.get("burial_date")
    service = answers.get("service_date")
    if burial and service and str(burial) != str(service):
        conflicts.append(
            Conflict(
                field_id="burial_date",
                value=burial,
                permitted=(str(service),),
                message=(
                    "Burial is always the service day. This order says the service "
                    f"is {service} and the burial is {burial}. For a burial on a "
                    "different day, say it as a graveside service."
                ),
            )
        )

    # ⚠️ ZERO EXTRA CHAIRS RAISES NOTHING, BY RULING (James, 2026-10-15), SUPERSEDING
    # THE CONFLICT THAT STOOD HERE FOR ONE DAY. His words: "8 or fewer chairs: no
    # extra-chairs line, no conflict."
    #
    # What was here argued that an extra count of 0 is a contradiction the office must
    # resolve, so it blocked Approve with a message. That reasoning was MINE — his
    # original dispatch gave two examples and neither reaches zero — and he has now
    # ruled the other way. "8 chairs" is a director describing the standard setup, not
    # a mistake to be corrected: there is simply nothing extra to bill.
    #
    # ⚠️ THE ANSWER IS STILL CAPTURED AND STILL SHOWN, which is what keeps this from
    # being a silent drop. `cemetery_equipment` stays `extra_chairs` and the count
    # stays 0, so the pane says it understood; what changes is that `approval.assess`
    # builds no line and nothing blocks. See `_equipment_quantity` and the row
    # rendering of a zero count.

    already = {c.field_id for c in conflicts}
    for field_id in state.not_applicable:
        if field_id in already or field_id not in answers:
            continue
        # ⚠️ DECLINING IS NEVER A CONFLICT, ON ANY VAULT (James, 2026-10-16). "none"
        # answers the question rather than contradicting it: a director saying "no
        # personalization" on a vault that offers none is AGREEING with the vault, and
        # being told "Monticello Burial Vault doesn't offer None" is the engine arguing
        # with someone who said the same thing it did.
        #
        # ⚠️ AND THE OTHER ENFORCEMENT PATH ALREADY HELD THIS RULE, which is what makes
        # the omission here a bug rather than a design choice. `missing._reject_unpermitted`
        # exempts `ANSWER_NONE` with the comment "Declining is permitted wherever the
        # question is asked at all" — that guard covers a vault with a CONFIGURED
        # permitted set, and this loop covers a vault where the question does not apply
        # at all. Two paths, one rule, and only one of them had it. Measured on
        # production 2026-10-16: the item-8 walk was refused for answering "none".
        #
        # ⚠️ IT DOES NOT MAKE THE FIELD `answered`. The field stays in `not_applicable`,
        # which is correct — the vault genuinely offers nothing — so no row claims a
        # personalization that will not be made and `assess` builds no line. What
        # changes is only that the decline stops blocking Approve.
        if str(answers[field_id]) == ANSWER_NONE:
            continue
        permitted = _permitted_for(
            template, field_id, vault_product_id, config
        )
        conflicts.append(
            Conflict(
                field_id=field_id,
                value=answers[field_id],
                permitted=permitted,
                message=_not_offered_message(
                    vault_label, field_id, answers[field_id], permitted
                ),
            )
        )

    return resolution, state, tuple(conflicts)


def _permitted_for(template, field_id, vault_product_id, config) -> tuple[str, ...]:
    """What the vault DOES offer for this field, if the field is availability-gated."""
    from app.services.capture.schema import _permitted_answers

    definition = next(
        (f for f in template if f.field_id == field_id), None
    )
    if definition is None:
        return ()
    return _permitted_answers(definition, vault_product_id, config)


def _not_offered_message(
    vault_label: str, field_id: str, value: object, permitted: tuple[str, ...]
) -> str:
    """The sentence the office reads, in James's words from the walk note.

    ⚠️ IT NAMES THE VAULT AND THE THING THEY ASKED FOR. "personalization is not
    applicable" is true and useless; "Monticello Burial Vault doesn't offer
    Nameplate Only" is what a director needs on a call, and it is the wording the
    dispatch specified.

    ⚠️ AND IT SAYS WHAT THE VAULT DOES OFFER WHEN THERE IS ANYTHING TO SAY. A
    refusal with no alternative leaves the office guessing; a refusal listing the
    options is a decision they can make on the phone.
    """
    from app.services.capture.schema import (
        PERSONALIZATION_ANSWER_LABELS,
        PLATFORM_DEFAULT_FIELDS,
    )

    def label(v: object) -> str:
        return PERSONALIZATION_ANSWER_LABELS.get(str(v), str(v).replace("_", " "))

    field_label = next(
        (f.label for f in PLATFORM_DEFAULT_FIELDS if f.field_id == field_id),
        field_id.replace("_", " "),
    )
    subject = vault_label or "This vault"
    asked = label(value) if field_id == "personalization" else f"{field_label}: {value}"
    head = f"{subject} doesn't offer {asked}."
    if permitted:
        offers = ", ".join(label(p) for p in permitted)
        return f"{head} It offers: {offers}."
    return f"{head} It offers no personalization."


#: The field id at the front of an `UnpermittedAnswer` message.
#:
#: ⚠️ PARSED FROM THE MESSAGE, AND THAT IS A REAL WEAKNESS WORTH NAMING RATHER THAN
#: HIDING. `UnpermittedAnswer` is a bare `ValueError` carrying only a formatted string
#: (`missing.py:272`), so there is no structured field to read. The alternative —
#: giving the exception attributes — is a change to `missing.py`, which the CALL
#: PIPELINE shares, and E6 says that path does not change in this slice. So the parse
#: is confined here, anchored to the message's own leading `field_id=` shape, and a
#: test pins it against the real exception rather than against a string I wrote.
_CONFLICT_FIELD = re.compile(r"^([a-z_][a-z0-9_]*)=")
_CONFLICT_PERMITTED = re.compile(r"permitted: \[([^\]]*)\]")


def _conflicting_field(e: Exception, answers: dict[str, object]) -> str | None:
    m = _CONFLICT_FIELD.match(str(e))
    if m is None:
        return None
    field_id = m.group(1)
    # ⚠️ CONFIRMED AGAINST THE ANSWERS. A parsed name that is not a key would make
    # `del` raise, turning a reportable conflict into a KeyError.
    return field_id if field_id in answers else None


def _permitted_from(e: Exception) -> tuple[str, ...]:
    m = _CONFLICT_PERMITTED.search(str(e))
    if m is None:
        return ()
    return tuple(
        part.strip().strip("'").strip('"')
        for part in m.group(1).split(",")
        if part.strip()
    )
