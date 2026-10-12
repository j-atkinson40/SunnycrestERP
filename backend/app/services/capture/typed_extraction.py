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

    @property
    def understood_nothing(self) -> bool:
        return not self.values and not self.picks


class LineExtractor(Protocol):
    """⚠️ THE SEAM. A model-backed extractor implements this and nothing else changes."""

    def extract_line(
        self, db: Session, *, tenant_id: str, line: str, answers: dict[str, object]
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
        self, db: Session, *, tenant_id: str, line: str, answers: dict[str, object]
    ) -> LineExtraction:
        from app.services.legacy_print_resolver import resolve as resolve_print
        from app.services.nl_creation.structured_parsers import parse_date, parse_time
        from app.services.party_resolver import resolve_cemetery, resolve_funeral_home
        from app.services.product_name_resolver import build_index, resolve as resolve_vault

        spans: list[tuple[int, int]] = []
        values: dict[str, object] = {}
        picks: list[Pick] = []
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
            # ⚠️ THE NAME GROUP MUST STOP AT RESERVED WORDS, and the first version did
            # not: `{0,2}` greedily took "cemetery in" into the name, so
            # "to St Mary's cemetery in Auburn" asked the resolver for
            # "St Mary's cemetery in" — a stray preposition no candidate carries — and
            # matched NOTHING while the bare name matched one. A greedy group that
            # eats its own delimiters fails silently; the lookahead makes it stop.
            _STOP = r"(?!\b(?:cemetery|cemeteries|in|on|at|for|with|and)\b)"
            m = re.search(
                r"\b(?:to|at|going to|burial at|buried at)\s+"
                rf"({_STOP}[A-Za-z'][A-Za-z'\-]*(?:\s+{_STOP}[A-Za-z'][A-Za-z'\-]*){{0,2}})"
                r"\s*(?:cemetery|cemeteries)?"
                # ⚠️ `{2,30}` NOT `{{2,30}}`. Only the NAME fragment above is an f-string; this
            # one is a plain r-string, so doubled braces stayed literal and the city
            # group matched the text "{2,30}" — i.e. never. The city was silently
            # never captured, so the conflict check below could not fire and
            # "St Mary's in Auburn" resolved to the Skaneateles row.
            r"(?:\s+in\s+([A-Za-z][A-Za-z'\- ]{2,30}))?", line, re.I)
            if m:
                phrase, city = m.group(1).strip(), (m.group(2) or "").strip() or None
                cr = resolve_cemetery(db, tenant_id, phrase, city_hint=city)
                if cr.party_id:
                    if _mark(spans, m):
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
                    picks.append(Pick(
                        "cemetery", phrase,
                        tuple((c.name, c.label) for c in cr.candidates),
                        cr.discriminators[0].value if cr.discriminators else None,
                    ))
                    _mark(spans, m)

        # ── funeral home ────────────────────────────────────────────────
        if once("funeral_home"):
            m = re.search(
                r"\b(?:for|from|with)\s+"
                r"([A-Z][A-Za-z'&\-]*(?:\s+[A-Z][A-Za-z'&\-]*){0,3})", line)
            if m:
                fr = resolve_funeral_home(db, tenant_id, m.group(1).strip())
                if fr.party_id:
                    if _mark(spans, m):
                        values["funeral_home"] = fr.candidates[0].name
                elif len(fr.candidates) > 1:
                    picks.append(Pick(
                        "funeral_home", m.group(1).strip(),
                        tuple((c.name, c.label) for c in fr.candidates),
                        fr.discriminators[0].value if fr.discriminators else None,
                    ))
                    _mark(spans, m)

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
        chosen = values.get(QUESTION_PERSONALIZATION, answers.get(QUESTION_PERSONALIZATION))
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
            index = build_index(db)
            for kept, raw in _leftover_pairs(line, spans):
                # ⚠️ TWO READINGS, STRIPPED FIRST, AND THE CATALOG DECIDES. The
                # noise list contains words that are also inside catalog names, so a
                # stripped fragment that reaches nothing is not evidence the director
                # named no vault — see `_leftover_pairs`. The raw reading is tried
                # only on a miss, so nothing that resolves today changes.
                vr = resolve_vault(index, kept)
                frag = kept
                if raw.casefold() != kept.casefold():
                    alt = resolve_vault(index, raw)
                    if _narrower(alt, vr):
                        vr, frag = alt, raw
                if vr.variant_template_id:
                    # ⚠️ `low.find` CAN LAND ON AN EARLIER, ALREADY-CLAIMED COPY of
                    # the same words, which is why this claims rather than appends.
                    # The fragment itself came from the unclaimed complement, so the
                    # claim normally succeeds; a refusal means `find` pointed at the
                    # wrong occurrence and the value must not be written from it.
                    i = low.find(raw.casefold())
                    if i >= 0 and _claim(spans, i, i + len(raw)):
                        values["vault"] = vr.candidates[0].display_name
                    break
                if len(vr.candidates) > 1:
                    picks.append(Pick(
                        "vault", frag,
                        tuple((c.display_name, f"{c.sku} — {c.display_name}")
                              for c in vr.candidates),
                        vr.discriminators[0].value if vr.discriminators else None,
                    ))
                    i = low.find(raw.casefold())
                    if i >= 0:
                        _claim(spans, i, i + len(raw))
                    break

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
        )


#: The extractor this slice uses. ⚠️ A module-level instance so the endpoint layer
#: names the seam rather than the implementation — swapping in a model-backed
#: extractor later is one line here and no change anywhere else.
EXTRACTOR: LineExtractor = DeterministicExtractor()


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

    for segment in segments(text):
        ex = EXTRACTOR.extract_line(db, tenant_id=tenant_id, line=segment, answers={})
        for field_id, value in ex.values.items():
            last[field_id] = ("value", value)
        for pick in ex.picks:
            last[pick.field_id] = ("pick", pick)
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

    return TextExtraction(
        text=text,
        values=values,
        picks=tuple(picks),
        unrecognized=tuple(unrecognized),
        policy=MentionPolicy.LAST_WINS,
    )


def evaluate_typed(db: Session, *, tenant_id: str | None, answers: dict[str, object]):
    """Resolve the vault from a typed session's answers and evaluate the capture.

    Returns `(resolution, CaptureState)` — the same pair `resolve_and_evaluate` returns.

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

    state = capture.evaluate(
        answers,
        vault_product_id=resolution.variant_template_id,
        personalization_config=resolve_availability_config(db, tenant_id),
        vault_form=vault_form,
        platform_fields=capture.template_for(capture.SALES_ORDER),
    )
    return resolution, state
