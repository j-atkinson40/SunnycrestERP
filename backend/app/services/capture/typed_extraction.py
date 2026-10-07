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
from typing import Protocol

from sqlalchemy.orm import Session

from app.services.capture.schema import (
    NAMEPLATE_DATE_FORMATS,
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
_EQUIPMENT: tuple[tuple[str, str], ...] = (
    (r"full\s+(?:equipment|setup|set\s*up)", "Full Equipment"),
    (r"(?:lowering\s+)?device\s+(?:and|&|\+)\s+grass(?:\s+mats)?", "Lowering Device & Grass"),
    (r"grass\s+(?:and|&|\+)\s+(?:lowering\s+)?device", "Lowering Device & Grass"),
    (r"tent\s+only", "Tent Only"),
    (r"just\s+(?:a\s+|the\s+)?tent", "Tent Only"),
    (r"(?:lowering\s+)?device\s+only", "Lowering Device Only"),
    (r"just\s+(?:the\s+)?(?:lowering\s+)?device", "Lowering Device Only"),
    (r"vault\s+placer", "Vault Placer"),
    (r"extra\s+chairs", "Extra Chairs (over 8)"),
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


def _mark(spans: list[tuple[int, int]], m: re.Match) -> None:
    spans.append((m.start(), m.end()))


def _leftovers(line: str, spans: list[tuple[int, int]]) -> tuple[str, ...]:
    """The text no parser claimed, as trimmed fragments.

    ⚠️ THIS IS THE "NEVER DROPPED" GUARANTEE, AND IT IS STRUCTURAL. Every parser
    records its span; this returns the complement. A parser that matched nothing and
    said nothing still leaves its text here, so silence is visible.

    ⚠️ NOISE WORDS ARE REMOVED FROM FRAGMENTS, NOT FROM THE LINE. Removing them from
    the line first would merge two unrelated fragments into one — "for Hopkins ... and
    the Smith" would read as one unplaced phrase.
    """
    taken = sorted(spans)
    out: list[str] = []
    cur = 0
    for a, b in taken:
        if a > cur:
            out.append(line[cur:a])
        cur = max(cur, b)
    if cur < len(line):
        out.append(line[cur:])

    frags: list[str] = []
    for frag in out:
        words = [w for w in re.split(r"[^A-Za-z0-9'&\-]+", frag) if w]
        kept = [w for w in words if w.casefold() not in _NOISE_WORDS]
        if kept:
            frags.append(" ".join(kept))
    return tuple(frags)


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
                    values["cemetery_equipment"] = val
                    _mark(spans, m)
                else:
                    note_restated("cemetery_equipment", m)
                break

        # ── personalization answer ───────────────────────────────────────
        for pat, val in _PERSONALIZATION:
            m = re.search(pat, low)
            if m:
                if once(QUESTION_PERSONALIZATION):
                    values[QUESTION_PERSONALIZATION] = val
                    _mark(spans, m)
                else:
                    note_restated(QUESTION_PERSONALIZATION, m)
                break

        # ── legacy series ───────────────────────────────────────────────
        if once("legacy_series"):
            for pat, val in _LEGACY_SERIES:
                m = re.search(pat, low)
                if m:
                    values["legacy_series"] = val
                    _mark(spans, m)
                    break

        # ── nameplate date format ───────────────────────────────────────
        if once("nameplate_date_format"):
            for pat, val in _DATE_FORMAT_WORDS:
                m = re.search(pat, low)
                if m:
                    assert val in NAMEPLATE_DATE_FORMATS, val
                    values["nameplate_date_format"] = val
                    _mark(spans, m)
                    break

        # ── service location ────────────────────────────────────────────
        if once("service_location"):
            for words, val in _LOCATION_WORDS.items():
                i = low.find(words)
                if i >= 0:
                    assert val in SERVICE_LOCATIONS, val
                    values["service_location"] = val
                    spans.append((i, i + len(words)))
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
                    values["legacy_print_name"] = pr.print_name
                    _mark(spans, m)
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
            values["date_of_birth"] = b
            values["date_of_death"] = d
            spans.append(span)

        # ── explicit decedent name ──────────────────────────────────────
        if once("deceased_name"):
            en = _explicit_name(line)
            if en:
                values["deceased_name"] = en[0]
                spans.append(en[1])

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
                values["grave_location"] = ", ".join(parts)
                _mark(spans, m)

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
                if pd and pd.get("value"):
                    values["burial_date"] = pd["value"]
                    _mark(spans, m)

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
                    values["cemetery"] = cr.candidates[0].name
                    if cr.candidates[0].city:
                        values["cemetery_city"] = cr.candidates[0].city
                    _mark(spans, m)
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
                    values["funeral_home"] = fr.candidates[0].name
                    _mark(spans, m)
                elif len(fr.candidates) > 1:
                    picks.append(Pick(
                        "funeral_home", m.group(1).strip(),
                        tuple((c.name, c.label) for c in fr.candidates),
                        fr.discriminators[0].value if fr.discriminators else None,
                    ))
                    _mark(spans, m)

        # ── vault ───────────────────────────────────────────────────────
        # ⚠️ RUNS LATE AND OVER THE WHOLE LINE, because a vault phrase is bare words
        # ("an oversized", "34 inch Continental") with no marker in front of it. Running
        # it early would let it claim spans that belong to a cemetery or a party.
        if once("vault"):
            remaining = _leftovers(line, spans)
            for frag in remaining:
                vr = resolve_vault(build_index(db), frag)
                if vr.variant_template_id:
                    values["vault"] = vr.candidates[0].display_name
                    i = low.find(frag.casefold())
                    if i >= 0:
                        spans.append((i, i + len(frag)))
                    break
                if len(vr.candidates) > 1:
                    picks.append(Pick(
                        "vault", frag,
                        tuple((c.display_name, f"{c.sku} — {c.display_name}")
                              for c in vr.candidates),
                        vr.discriminators[0].value if vr.discriminators else None,
                    ))
                    i = low.find(frag.casefold())
                    if i >= 0:
                        spans.append((i, i + len(frag)))
                    break

        # ── service date / time / eta ───────────────────────────────────
        # ⚠️ LAST, AND OVER LEFTOVERS ONLY. `parse_date` is greedy about bare numbers,
        # so running it over the whole line would swallow "34 inch" and the year pair.
        for frag in _leftovers(line, spans):
            if once("service_date"):
                pd = parse_date(frag)
                if pd and pd.get("value"):
                    values["service_date"] = pd["value"]
                    i = low.find(frag.casefold())
                    if i >= 0:
                        spans.append((i, i + len(frag)))
                    continue
            if once("service_time"):
                pt = parse_time(frag)
                if pt and pt.get("value"):
                    values["service_time"] = pt["value"]
                    i = low.find(frag.casefold())
                    if i >= 0:
                        spans.append((i, i + len(frag)))

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
    from app.services.personalization.enrollment import read_personalization_config
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
        personalization_config=read_personalization_config(db, tenant_id),
        vault_form=vault_form,
        platform_fields=capture.template_for(capture.SALES_ORDER),
    )
    return resolution, state
