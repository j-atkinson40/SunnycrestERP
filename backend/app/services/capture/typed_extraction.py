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

from app.services.capture.schema import (
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

    @property
    def understood_nothing(self) -> bool:
        return not self.values and not self.picks


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
    (r"extra\s+chairs", _EQ_ID["Extra Chairs (over 8)"]),
    (r"no\s+equipment|don'?t\s+need\s+equipment", ANSWER_NONE),
)

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

#: Words that carry no field and must not be reported as unrecognized.
_NOISE_WORDS: frozenset = frozenset({
    "a", "an", "the", "and", "for", "with", "to", "at", "on", "in", "of", "is",
    "it", "its", "please", "thanks", "ok", "okay", "also", "plus", "then",
    "order", "vault", "need", "needs", "want", "wants", "get", "put", "add",
    "new", "start", "create", "make", "enter", "take", "going", "goes", "be",
    "will", "we", "they", "he", "she", "her", "his", "their", "this", "that",
    "no", "not", "none", "only", "just", "both", "all", "some", "there",
    # Label words a director says around a value rather than as one.
    "service", "burial", "cemetery", "funeral", "home", "decedent", "deceased",
    "print", "design", "date", "time", "day", "section", "lot", "space",
})


def _free(spans: list[tuple[int, int]], a: int, b: int) -> bool:
    """Is `[a, b)` unclaimed by every span recorded so far?

    ⚠️ HALF-OPEN, SO ABUTTING IS NOT OVERLAPPING. `(0, 5)` and `(5, 9)` are adjacent
    and both legal; only a shared character counts.
    """
    return not any(a < end and start < b for start, end in spans)


def _claim(spans: list[tuple[int, int]], a: int, b: int) -> bool:
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
    spans.append((a, b))
    return True


def _mark(spans: list[tuple[int, int]], m: re.Match) -> bool:
    """`_claim` for a regex match. Returns False when the span is already taken."""
    return _claim(spans, m.start(), m.end())


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

        spans: list[tuple[int, int]] = []
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
            _mark(spans, m)
            cur = answers.get(field_id, values.get(field_id))
            restated.append(f"{m.group(0).strip()} — {field_id} is already {cur!r}")

        # ── equipment package ────────────────────────────────────────────
        for pat, val in _EQUIPMENT:
            m = re.search(pat, low)
            if m:
                if once("cemetery_equipment"):
                    if _mark(spans, m):
                        values["cemetery_equipment"] = val
                else:
                    note_restated("cemetery_equipment", m)
                break

        # ── personalization answer ───────────────────────────────────────
        for pat, val in _PERSONALIZATION:
            m = re.search(pat, low)
            if m:
                if once(QUESTION_PERSONALIZATION):
                    if _mark(spans, m):
                        values[QUESTION_PERSONALIZATION] = val
                else:
                    note_restated(QUESTION_PERSONALIZATION, m)
                break

        # ── legacy series ───────────────────────────────────────────────
        if once("legacy_series"):
            for pat, val in _LEGACY_SERIES:
                m = re.search(pat, low)
                if m:
                    if _mark(spans, m):
                        values["legacy_series"] = val
                    break

        # ── nameplate date format ───────────────────────────────────────
        if once("nameplate_date_format"):
            for pat, val in _DATE_FORMAT_WORDS:
                m = re.search(pat, low)
                if m:
                    assert val in NAMEPLATE_DATE_FORMATS, val
                    if _mark(spans, m):
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
                    if _mark(spans, m):
                        values["legacy_print_name"] = pr.print_name
                elif len(pr.candidates) > 1:
                    picks.append(Pick(
                        "legacy_print_name", m.group(1).strip(),
                        tuple((c.name, f"{c.name} — {c.category}") for c in pr.candidates),
                        pr.discriminators[0].value if pr.discriminators else None,
                    ))
                    _mark(spans, m)
                # ⚠️ NO MATCH -> SPAN LEFT UNCLAIMED, so the typed name appears in
                # `unrecognized`. The ruling: kept verbatim and flagged, never coerced.

        # ── year pair -> both dates ─────────────────────────────────────
        yp = _year_pair(line)
        if yp and once("date_of_birth") and once("date_of_death"):
            (b, d), span = yp
            if _claim(spans, span[0], span[1]):
                values["date_of_birth"] = b
                values["date_of_death"] = d

        # ── explicit decedent name ──────────────────────────────────────
        if once("deceased_name"):
            en = _explicit_name(line)
            if en and _claim(spans, en[1][0], en[1][1]):
                values["deceased_name"] = en[0]

        # ── grave location ──────────────────────────────────────────────
        if once("grave_location"):
            m = re.search(
                r"\b(?:section|sec\.?)\s*([A-Za-z0-9]+)"
                r"(?:[,\s]+(?:lot|l)\s*([A-Za-z0-9]+))?"
                r"(?:[,\s]+(?:space|grave|sp)\s*([A-Za-z0-9]+))?", line, re.I)
            if m:
                parts = [f"Section {m.group(1)}"]
                if m.group(2):
                    parts.append(f"Lot {m.group(2)}")
                if m.group(3):
                    parts.append(f"Space {m.group(3)}")
                if _mark(spans, m):
                    values["grave_location"] = ", ".join(parts)

        # ── burial date ─────────────────────────────────────────────────
        # ⚠️ ADDED AFTER A TEST FAILED FOR THE RIGHT REASON. `burial_date` is REQUIRED on
        # the template and had no parser at all, so "burial on March 3" landed in
        # `service_date` via the generic fallback and NO typed order could ever be
        # complete. Marker-based and ahead of the fallback, because "burial" and
        # "service" are different days (the same distinction r199 made for times).
        if once("burial_date"):
            m = re.search(r"\b(?:burial|interment|graveside)\s+(?:is\s+|on\s+|:\s*)?(.{3,30})", line, re.I)
            if m:
                from app.services.nl_creation.structured_parsers import parse_date as _pd
                pd = _pd(m.group(1).strip())
                if pd and pd.get("value") and _mark(spans, m):
                    values["burial_date"] = pd["value"]

        # ── cemetery (+ city) ───────────────────────────────────────────
        # ⚠️ THE CITY IS PARSED FROM THE SAME CLAUSE AND PASSED AS A HINT, not stored
        # as an answer unless the cemetery resolves — a town with no cemetery attached
        # is not a fact about the order.
        if once("cemetery"):
            # ⚠️ ONE CALL TO A STEP PARSER, NOT ONE REGEX. See
            # `parse_cemetery_clause` for the three silent failures that bought this.
            clause = parse_cemetery_clause(line)
            if clause:
                cr = resolve_cemetery(
                    db, tenant_id, clause.name, city_hint=clause.town
                )
                if cr.party_id:
                    if _claim(spans, clause.start, clause.end):
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
                    if _claim(spans, clause.start, clause.end):
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
                    a = base + wordm[0].start()
                    b = base + wordm[n - 1].end()
                    phrase = line[a:b].strip()
                    fr = resolve_funeral_home(db, tenant_id, phrase)
                    if fr.party_id:
                        if _claim(spans, a, b):
                            values["funeral_home"] = fr.candidates[0].name
                        break
                    if len(fr.candidates) > 1:
                        if _claim(spans, a, b):
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
                    tail = _CEM_TOWN.match(frag[b:])
                    city = (
                        _narrow_town(tail.group(1), town_names) if tail else None
                    ) or None
                    # ⚠️ THE CLAIM ENDS WHERE THE NARROWED TOWN ENDS, not where the
                    # pattern matched. Claiming the pattern's full span is what ate
                    # the following clause; the words the town did not use must stay
                    # available to the passes that want them.
                    end = b + (
                        tail.start(1) - tail.start() + len(city) if tail and city
                        else 0
                    )
                    cr = resolve_from_rows(rows, frag[a:b], city)
                    if cr.party_id:
                        if _claim(spans, frag_start + a, frag_start + end):
                            values["cemetery"] = cr.candidates[0].name
                            if cr.candidates[0].city:
                                values["cemetery_city"] = cr.candidates[0].city
                    elif len(cr.candidates) > 1 or cr.city_conflict:
                        if _claim(spans, frag_start + a, frag_start + end):
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
                        if _claim(spans, frag_start + a, frag_start + b):
                            values["funeral_home"] = fr.candidates[0].name
                    elif len(fr.candidates) > 1:
                        if _claim(spans, frag_start + a, frag_start + b):
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
                    if _claim(spans, a, a + len(words)):
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
                    if _claim(spans, a, frag_start + m.end()):
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
                            if _claim(spans, A, B):
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
                                if mine is not None and _claim(spans, A, B):
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
                            if _claim(spans, A, B):
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
                if _claim(spans, a, b):
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
                        if _claim(spans, a, b):
                            values["eta"] = pt["value"]

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
                    if _claim(spans, a, frag_start + tm.end()):
                        values["service_time"] = pt["value"]
                    break

        for frag in _leftovers(line, spans):
            if once("service_date"):
                pd = parse_date(frag)
                if pd and pd.get("value"):
                    i = low.find(frag.casefold())
                    if i >= 0 and _claim(spans, i, i + len(frag)):
                        values["service_date"] = pd["value"]
                        continue
            if once("service_time"):
                pt = parse_time(frag)
                if pt and pt.get("value"):
                    i = low.find(frag.casefold())
                    if i >= 0 and _claim(spans, i, i + len(frag)):
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
_CEM_TOWN = re.compile(
    r"\s+in\s+([A-Za-z][A-Za-z'\-.]+(?:\s+[A-Za-z][A-Za-z'\-.]*){0,2})", re.I
)


def _narrow_town(raw: str, known: frozenset[str]) -> str:
    """The longest word-prefix of `raw` that is a town we have a record of.

    ⚠️ THIS IS THE FUNERAL-HOME RULE APPLIED TO TOWNS, by the same ruling: a
    marker-led span must not swallow following words, and what bounds it is a
    record rather than a word count. "in Skaneateles tent only" gives
    "Skaneateles" because that is a city we hold and "Skaneateles tent" is not.

    ⚠️ AN UNKNOWN TOWN IS STILL READ, because a typed town that CONFLICTS with the
    record is supposed to raise the pick (ruled 2026-10-12) — it is the signal, so
    dropping it would lose the conflict. It is truncated at the first LABEL word
    after the first, which is what actually separates a place from the clause behind
    it: "Auburn service at" -> "Auburn".

    ⚠️ THE FIRST WORD IS NEVER DROPPED, and that exemption is load-bearing. A
    one-word fallback was tried and truncated two real towns — "New Hartford" became
    "New" and "St. Albans" became "St." — because `_NOISE_WORDS` contains "new" (for
    "new order") and the bare fallback took a single word. Towns are named after
    anything, including words this module treats as noise elsewhere, so the first
    word of a town span is exempt by construction rather than by a longer list.

    ⚠️ RESIDUAL, STATED RATHER THAN HIDDEN: an UNKNOWN town followed by a label that
    is not in `_NOISE_WORDS` still over-reaches by those words — "Xville tent only"
    reads "Xville tent". Every town in the seeded data takes the record path above,
    so this is reachable only for a town we hold no record of, and it is bounded at
    three words rather than the 30 CHARACTERS that produced 'ursday'.
    """
    # ⚠️ IMPORTED HERE, NOT AT MODULE LEVEL, BECAUSE THAT IS WHERE IT LIVES. The
    # name `_party_norm` is an alias created INSIDE `extract_line`
    # (`normalize as _party_norm`), so a module-level reference to it compiles,
    # imports, and raises `NameError` at call time. It did — caught by running the
    # function, not by reading it (CLAUDE.md §11: the check that catches this is
    # importing, or better, calling).
    from app.services.party_resolver import normalize as _norm

    words = raw.split()
    for n in range(len(words), 0, -1):
        if _norm(" ".join(words[:n])) in known:
            return " ".join(words[:n])
    if not words:
        return ""
    keep = [words[0]]
    for w in words[1:]:
        if w.casefold().strip(".,'") in _NOISE_WORDS:
            break
        keep.append(w)
    return " ".join(keep)


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


def parse_cemetery_clause(line: str) -> CemeteryClause | None:
    """Marker, name, optional "cemetery", optional "in <town>" — in that order.

    ⚠️ EACH STEP STARTS WHERE THE LAST ONE ENDED. That is the whole design: there is
    no shared backtracking and no fragment adjacency, so a change to one part can
    shorten or lengthen its own span and nothing else.
    """
    mk = _CEM_MARKER.search(line)
    if not mk:
        return None
    nm = _CEM_NAME.match(line, mk.end())
    if not nm:
        return None
    pos = nm.end()
    sfx = _CEM_SUFFIX.match(line, pos)
    if sfx:
        pos = sfx.end()
    twn = _CEM_TOWN.match(line, pos)
    if twn:
        pos = twn.end()
    return CemeteryClause(
        name=nm.group(0).strip(),
        town=(twn.group(1).strip() if twn else None) or None,
        start=mk.start(),
        end=pos,
        name_span=nm.span(),
        suffix_span=sfx.span() if sfx else None,
        town_span=twn.span(1) if twn else None,
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


def segments(text: str) -> tuple[str, ...]:
    """The text as separate statements, in order. Empty pieces dropped."""
    return tuple(
        piece for piece in (p.strip() for p in _SEGMENT_RE.split(text or "")) if piece
    )


def extract_text(
    db: Session,
    *,
    tenant_id: str,
    text: str,
    resolutions: dict[str, object] | None = None,
) -> TextExtraction:
    """Re-read the WHOLE typed text. Last mention wins; resolutions outrank it.

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
    for segment in segs:
        ex = EXTRACTOR.extract_line(db, tenant_id=tenant_id, line=segment, answers={})
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
    for segment in segs:
        ex = EXTRACTOR.extract_line(
            db, tenant_id=tenant_id, line=segment, answers={}, gating=gating
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

    phrase = str(answers.get("vault") or "").strip()
    resolution = resolve_vault(build_index(db), phrase or None)

    # ⚠️ None FOR AMBIGUOUS, matching `_resolved_form`. An ambiguous set can span forms
    # ("Graveliner" spans grave_liner and urn_vault), so a form read off candidates[0]
    # would be whichever the sort put first.
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
                vault_product_id=resolution.variant_template_id,
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

    return resolution, state, tuple(conflicts)


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
