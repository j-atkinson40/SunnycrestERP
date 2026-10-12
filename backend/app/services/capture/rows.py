"""The display layer: what a surface shows, over what the template can capture.

Two layers, ruled 2026-10-05 (DECISIONS 2026-10-02, "One capture engine, one
template per object type"):

    FIELD   what can be CAPTURED — one fact, one answer.      `schema.py`
    ROW     what is SHOWN, on ONE SURFACE.                    here

⚠️ ROWS ARE NOT FIELDS, AND THE MEASUREMENT IS WHY THIS MODULE EXISTS. The
approved design's capture list holds NINE rows over FIFTEEN template fields, and
its summary holds SIX plus a subject header. Four distinct mismatches, none
cosmetic:

    COMPOSITION         `Burial` = cemetery + burial time, one row
    COLLAPSE            three personalization questions, one row
    ROW WITH NO FIELD   `Contact` comes from the customer record
    FIELD WITH NO ROW   `grave_location` belongs to a surface not built yet

A label-and-order-per-field design would render fifteen rows where the design has
nine and six, and no amount of labelling fixes a structural mismatch. Measured in
`docs/investigations/2026-10-05-part1-rows-are-not-fields.md`.

⚠️ AND THE TWO SURFACES COMPOSE DIFFERENTLY, which is why a row set belongs to a
surface rather than to the template. The same facts become different rows, with
different labels, under different count vocabulary: `Cemetery` is relabelled
`Burial`, `Contact` demotes from a row to a secondary line, and the decedent's
name and dates leave the grid entirely for the subject header.

SOURCES, AND THE TWO AMENDMENTS THAT MADE THE SHAPE WORK:

1. **A row's sources are ORDERED and the first yielding a value wins.** `Contact`
   is `[field contact_name, record customer.contact_name]` — the call knows who
   actually spoke and that beats the record's default. Costs nothing for the rows
   with one source, which is most of them.

   ⚠️ "YIELDING A VALUE" MEANS `is_answered`, NEVER TRUTHINESS. The engine has
   exactly one definition of answered — `none` is an answer, blank is not — and a
   second notion of "has a value" inside this module would reproduce the split
   that put `answered` and `missing` on different footings in the first place.

2. **Orphan detection is over the UNION of every surface's sources.** A field with
   no row on one surface is not an orphan. See `orphan_field_ids`.

⚠️ THIS MODULE IS COLD-PATH IN FULL. Nothing renders it yet, and the surfaces it
describes live behind an overlay with no production entrance. Its tests are the
entire claim, not a net under a working path.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.services.capture.missing import is_answered
from app.services.capture.schema import ResolvedField


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FieldSource:
    """A template field's answer."""

    field_id: str


@dataclass(frozen=True)
class RecordSource:
    """A value read from a related record rather than captured.

    ⚠️ A REAL CATEGORY, NOT A MISSING FIELD. `Contact` is the funeral home's
    contact on the customer record (`customers.contact_name` exists, measured);
    nothing captures it and nothing should. Distinguishing this from a missing
    capture field is what stopped three rows being mistaken for three gaps.
    """

    record: str
    path: str


@dataclass(frozen=True)
class LiteralSource:
    """Fixed text. Carries no state and never makes a row unanswered."""

    text: str


@dataclass(frozen=True)
class ComposedSource:
    """Several sources rendered as one value.

    `join` is the separator the design uses — `" · "` between a place and a time,
    `" — "` between two dates. Composition is the design's own, measured from the
    prototype rather than chosen here.
    """

    sources: tuple["Source", ...]
    join: str = " · "


@dataclass(frozen=True)
class FirstOf:
    """The first child that yields anything. A FALLBACK, not a composition.

    ⚠️ ADDED 2026-10-12 TO FIX A DEFECT THAT WAS NOT IN THE SCREENSHOT, found while
    verifying the one that was. The capture Service row expressed its fallback as TWO
    `ComposedSource`s over `row.sources`, relying on `_first`'s "ordered, first
    yielding wins":

        Composed(service_location_other, service_date, service_time)
        Composed(service_location,       service_date, service_time)

    Each alternative also carried the date and the time, so the FIRST one started
    yielding the moment a DATE existed — even with `service_location_other` empty —
    and the location silently disappeared from the row. Measured: "service at the
    church" showed `Church`; adding "service on March 2 2027" changed it to
    `2027-03-02`. A field the director had given, gone from the row, with nothing
    reported.

    `FirstOf` makes the intent expressible INSIDE a composition — "whichever location
    we have, then the date, then the time" — instead of emerging from the interaction
    of two overlapping alternatives. ⚠️ Exactly one row had this shape; the summary
    surface's Service row uses two bare `FieldSource`s, which is a true fallback and
    is correct as written. Measured over both surfaces rather than assumed.
    """

    sources: tuple["Source", ...]


Source = FieldSource | RecordSource | LiteralSource | ComposedSource | FirstOf


# ---------------------------------------------------------------------------
# Rows and slots
# ---------------------------------------------------------------------------


class RowState(str, Enum):
    """⚠️ FOUR STATES, EACH TAKEN FROM A CITED PROTOTYPE RATHER THAN INVENTED.

    THREE from `docs/prototypes/2026-09-call-to-print.html`
    (1,072,184 bytes, md5 `56e1e24c3a4a873e1ef6d45fc58ba18e`):

        NOT_MENTIONED  the default: grey mark, value "Not mentioned yet" in italic
        DONE           `.cap.done` — green check, solid value
        NEEDED         `.cap.needed` — amber, `animation: needpulse 1.9s`,
                       value "Still needed"

    THE FOURTH from `docs/prototypes/2026-09-22-capture-schema-prototype.html`
    (66,024 bytes, md5 `5d286c79a855f7397a8d62f3ad983228`), where it is
    `.cap.unconfig` — amber at lower intensity with a DASHED mark border:

        .cap.unconfig{border-color:rgba(224,168,74,.35);background:rgba(224,168,74,.04)}
        .cap.unconfig .mk{border-color:var(--need);border-style:dashed}

    ⚠️ `unconfig` has ZERO hits in the call-to-print copy, so that file is
    authoritative for three states and SILENT on the fourth. Two sources, each
    cited with its digest, neither inferred from the other.

    ⚠️ AND THE FOURTH IS NOT A VARIANT OF `NEEDED`. "Still needed" means the
    answer exists and nobody gave it. "Not configured" means the platform does not
    know whether the question applies to this licensee, so Opas asks rather than
    assuming. Collapsing them is a default standing in for a measurement: the row
    looks answerable when what is actually missing is the licensee's setup.

    ⚠️ A FIFTH, `PARTIAL`, ADDED 2026-10-12 AND NOT FROM EITHER PROTOTYPE — because
    neither prototype had the case. It is a DEFECT FIX, and the defect was visible on
    James's screen: he typed "start an order for Hopkins Funeral Home ... service at
    the church" and the Service row showed **"Church" in the not-mentioned style** —
    italic, no check — because the row composes several fields and one of them
    (`service_date`) was still required and unanswered. The branch below read
    "something required is missing" and returned NOT_MENTIONED without looking at
    whether anything had rendered.

    `PARTIAL` means: THIS ROW HAS CAPTURED SOMETHING AND IS NOT FINISHED. It exists so
    the state and the appearance agree, which is the ruling — row style follows row
    state — and so the server stays the only thing deciding. A pane that inferred
    "has a value but the state says not-mentioned, so style it differently" would be
    a second source of truth for completeness.

    ⚠️ IT DOES NOT DEFER TO `NEEDED` AFTER THE DONE SIGNAL, AND THAT WAS A REAL
    CHOICE. Letting NEEDED win once the director says "that's everything" would make
    the row amber and emphatic — but it would also re-introduce the original defect,
    because NEEDED's prototype value text is "Still needed" and the captured value
    would vanish from the row again. What is blocking is already carried by the
    `missing` set and rendered in the header; what the ROW must not do is deny the
    director typed something. So PARTIAL holds regardless of the signal.
    """

    NOT_MENTIONED = "not_mentioned"
    DONE = "done"
    NEEDED = "needed"
    NOT_CONFIGURED = "not_configured"
    PARTIAL = "partial"


@dataclass(frozen=True)
class Row:
    """One line of a surface."""

    id: str
    label: str
    order: int
    sources: tuple[Source, ...]
    group: str | None = None
    secondary: tuple[Source, ...] = ()
    #: Which field this row's edit affordance opens, when a row composes several.
    edit_target: str | None = None


@dataclass(frozen=True)
class SubjectSlot:
    """A header above the grid, not a row in it.

    ⚠️ EXISTS BECAUSE THE DESIGN HAS ONE. The summary renders `John Smith` over
    `March 14, 1948 — September 14, 2026` above the rows — measured. Modelling it
    as a row would have put the decedent's name in the grid, which is not the
    approved design.
    """

    primary: tuple[Source, ...]
    secondary: tuple[Source, ...] = ()


@dataclass(frozen=True)
class NotesSlot:
    """A free-text box on the object.

    ⚠️ NOT A TEMPLATE FIELD, DELIBERATELY. Nothing extracts it, so it has no
    answer to be missing and no state to render. It belongs to the surface.
    """

    label: str = "Notes"
    placeholder: str = ""


@dataclass(frozen=True)
class FooterSlot:
    """⚠️ DECLARED AND UNFILLED, ON PURPOSE.

    The design's footer carries a hint derived from captured values and an approve
    action naming the object type. The slot is declared so the surface's shape is
    complete; the derivation is NOT built, because building a templating mechanism
    for one cosmetic line before a second line exists is the generalisation this
    arc has spent three days catching.

    `hint` stays None until something needs it.
    """

    approve_label: str
    hint: None = None


@dataclass(frozen=True)
class Surface:
    """A named set of slots. One object type may have several.

    ⚠️ SLOTS, NOT JUST ROWS. subject / rows / notes / footer — because the design
    has four regions and three of them are not rows.
    """

    id: str
    rows: tuple[Row, ...]
    subject: SubjectSlot | None = None
    notes: NotesSlot | None = None
    footer: FooterSlot | None = None
    #: The word this surface uses for unanswered-required. Measured: the capture
    #: list says "needed" and the summary says "missing", for the same set.
    unanswered_word: str = "needed"


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResolvedRow:
    row_id: str
    label: str
    group: str | None
    state: RowState
    value: str | None
    secondary_value: str | None
    edit_target: str | None


@dataclass(frozen=True)
class ResolvedSurface:
    surface_id: str
    rows: tuple[ResolvedRow, ...]
    subject_primary: str | None = None
    subject_secondary: str | None = None


def _source_field_ids(src: Source) -> tuple[str, ...]:
    if isinstance(src, FieldSource):
        return (src.field_id,)
    if isinstance(src, (ComposedSource, FirstOf)):
        out: list[str] = []
        for s in src.sources:
            out.extend(_source_field_ids(s))
        return tuple(out)
    return ()


def row_field_ids(row: Row) -> tuple[str, ...]:
    """Every template field this row reads, primary and secondary."""
    out: list[str] = []
    for src in row.sources + row.secondary:
        out.extend(_source_field_ids(src))
    return tuple(out)


def _render(
    src: Source,
    values: dict[str, object],
    records: dict[str, dict],
    defs: dict[str, object] | None = None,
) -> str | None:
    """A source's rendered value, or None when it yields nothing.

    ⚠️ `is_answered` DECIDES, not truthiness. See the module docstring.

    ⚠️ A FIELD WITH OPTIONS IS RENDERED THROUGH `label_for`, NEVER `str`. This line
    used to be `str(v)` for every field, and it put the raw id `funeral_home` on
    James's screen in the Service row on production. An enum field stores an id; the
    display label is declared beside the field's options in `schema.py` and nowhere
    else — not here, and not in the frontend.

    ⚠️ `defs=None` RENDERS RAW, AND THAT IS A REAL RISK, SO IT IS NAMED. A caller
    that forgets to pass the definitions gets slugs back and nothing complains. Every
    caller inside this module passes them; `test_enum_display.py` asserts the shipped
    path renders labels, which is what makes the default safe rather than merely
    convenient.
    """
    if isinstance(src, LiteralSource):
        return src.text
    if isinstance(src, FieldSource):
        v = values.get(src.field_id)
        if not is_answered(v):
            return None
        d = (defs or {}).get(src.field_id)
        return d.label_for(v) if d is not None else str(v)
    if isinstance(src, RecordSource):
        v = (records.get(src.record) or {}).get(src.path)
        return str(v) if is_answered(v) else None
    if isinstance(src, FirstOf):
        for child in src.sources:
            got = _render(child, values, records, defs)
            if got is not None:
                return got
        return None
    parts = [p for p in (_render(s, values, records, defs) for s in src.sources) if p]
    return src.join.join(parts) if parts else None


def _first(
    sources: tuple[Source, ...],
    values: dict[str, object],
    records: dict[str, dict],
    defs: dict[str, object] | None = None,
) -> str | None:
    """⚠️ AMENDMENT 1: ordered, first yielding a value wins."""
    for src in sources:
        got = _render(src, values, records, defs)
        if got is not None:
            return got
    return None


def resolve_surface(
    surface: Surface,
    resolved_fields: tuple[ResolvedField, ...],
    values: dict[str, object],
    *,
    records: dict[str, dict] | None = None,
    done_signal: bool = False,
) -> ResolvedSurface:
    """Render one surface's slots against the resolved schema and the answers.

    ⚠️ TAKES `resolved_fields`, NOT `CaptureState`, AND THAT IS THE POINT.
    `CaptureState` reduces the schema to three tuples of ids and DISCARDS
    availability — measured 2026-10-05: an OFFERED-but-unanswered question and a
    NOT_CONFIGURED one produce byte-identical CaptureStates. `ResolvedField`
    carries it, so the fourth row state is derivable here without the engine
    computing anything new.

    ⚠️ `done_signal` IS PRESENTATION, NOT MEMBERSHIP. Which fields are unanswered
    is the server's answer; whether to render them amber is the surface's. So the
    server never needs to see the signal, and `NEEDED` is `NOT_MENTIONED` after it.
    """
    records = records or {}
    by_id = {f.field_id: f for f in resolved_fields}
    #: ⚠️ THE LABEL LOOKUP, BUILT ONCE. Keyed by field id -> FieldDefinition, so
    #: `_render` can ask a field how to display its own stored value. Built from
    #: `resolved_fields` rather than from the platform tuple, because a tenant may
    #: have switched a field off and a row must not render through a definition the
    #: resolver excluded.
    _defs = {f.field_id: f.definition for f in resolved_fields}
    applicable = set(by_id)

    out: list[ResolvedRow] = []
    for row in sorted(surface.rows, key=lambda r: r.order):
        ids = row_field_ids(row)

        # A row every one of whose fields is inapplicable is absent, not empty.
        # Rows with no fields at all (record/literal only) are always present.
        if ids and not any(i in applicable for i in ids):
            continue

        value = _first(row.sources, values, records, _defs)
        secondary = (
            _first(row.secondary, values, records, _defs) if row.secondary else None
        )

        unanswered_required = [
            i for i in ids
            if i in by_id and by_id[i].required and not is_answered(values.get(i))
        ]
        not_configured = [
            i for i in ids
            if i in by_id
            and by_id[i].definition.is_conditional
            and not by_id[i].permitted_answers
        ]

        if not_configured:
            state = RowState.NOT_CONFIGURED
        elif unanswered_required and value is not None:
            # ⚠️ ORDER MATTERS AND THIS CLAUSE MUST PRECEDE THE NEXT. A row can be
            # BOTH incomplete and partly captured; the old code tested only the first
            # half and returned NOT_MENTIONED over a rendered value. See the class
            # docstring for what that looked like on James's screen.
            state = RowState.PARTIAL
        elif unanswered_required:
            state = RowState.NEEDED if done_signal else RowState.NOT_MENTIONED
        elif value is None:
            # Nothing required is missing, but nothing rendered either — an
            # optional row nobody answered, or a record-only row whose record
            # holds nothing. Shown as not-mentioned, never done.
            #
            # ⚠️ THE `and ids` GUARD WAS A BUG AND A TEST FOUND IT. With it, a
            # RECORD-ONLY row (no template fields at all, like `Contact`) fell
            # through to DONE while rendering nothing — a row claiming to be
            # answered with no value in it. Record-only rows are exactly the
            # category amendment 1 exists for, so getting them wrong would have
            # mattered.
            state = RowState.NOT_MENTIONED
        else:
            state = RowState.DONE

        out.append(ResolvedRow(
            row_id=row.id, label=row.label, group=row.group, state=state,
            value=value, secondary_value=secondary, edit_target=row.edit_target,
        ))

    subj_p = subj_s = None
    if surface.subject is not None:
        subj_p = _first(surface.subject.primary, values, records, _defs)
        subj_s = (
            _first(surface.subject.secondary, values, records, _defs)
            if surface.subject.secondary
            else None
        )

    return ResolvedSurface(
        surface_id=surface.id, rows=tuple(out),
        subject_primary=subj_p, subject_secondary=subj_s,
    )


def counts(resolved: ResolvedSurface) -> tuple[int, int]:
    """`(done, unanswered)` over a surface's rows.

    ⚠️ COUNTS BELONG TO THE CAPTURE, NOT TO THE SURFACE RENDERING THEM. Measured:
    the summary displays `9 captured / 0 missing` while showing SIX rows — nine is
    the CAPTURE surface's row count. So a summary is rendered with the capture's
    counts rather than its own, and this function is called on the capture surface
    in both cases. Not a bug to fix; the design's own choice.
    """
    done = sum(1 for r in resolved.rows if r.state is RowState.DONE)
    return done, len(resolved.rows) - done


def orphan_field_ids(
    template_field_ids: frozenset[str], surfaces: tuple[Surface, ...]
) -> frozenset[str]:
    """⚠️ AMENDMENT 2: fields minus the UNION of every surface's row sources.

    A field with no row on ONE surface is not an orphan — `grave_location` is
    captured from the funeral home at order time and displayed on the driver's
    surface, so per-surface absence would report it falsely.

    ⚠️ AND A REPORTED ORPHAN IS A FINDING, NOT A BUG TO SILENCE. Until a driver
    surface is declared, `grave_location` WILL appear here, and that is correct.
    Declaring a surface nobody is building, in order to make a true finding stop
    appearing, is editing the record to match the belief — see CLAUDE.md §11.

    The value of this function is that "a captured field with nowhere to show it"
    becomes a COMPUTABLE SET rather than silence, which keeps its three causes
    distinguishable: redundant field, surface not yet declared, genuine oversight.
    Measured 2026-10-05, the first such set held one of each.
    """
    shown: set[str] = set()
    for s in surfaces:
        for row in s.rows:
            shown.update(row_field_ids(row))
        if s.subject is not None:
            for src in s.subject.primary + s.subject.secondary:
                shown.update(_source_field_ids(src))
    return frozenset(template_field_ids) - shown
