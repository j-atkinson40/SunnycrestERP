"""The declared surfaces for each object type.

`rows.py` is the mechanism; this is the data — the same split `schema.py` keeps
between `FieldDefinition` and `CAPTURE_TEMPLATES`.

⚠️ EVERY ROW, LABEL, ORDER AND SEPARATOR HERE IS MEASURED FROM A CITED PROTOTYPE,
NOT CHOSEN. Two files, each with its digest, because the four row states come from
two different ones:

    docs/prototypes/2026-09-call-to-print.html
        1,072,184 bytes  md5 56e1e24c3a4a873e1ef6d45fc58ba18e
        screen 1 `<!-- 1 — CALL over the note -->`   the capture surface
        screen 2 `<!-- 2 — CALL SUMMARY in the overlay -->`  the summary surface

    docs/prototypes/2026-09-22-capture-schema-prototype.html
        66,024 bytes  md5 5d286c79a855f7397a8d62f3ad983228
        `.cap.unconfig` — the NOT_CONFIGURED styling, absent from the other file

⚠️ A NEWER REVISION OF THE FIRST EXISTS AND IS NOT IN THE REPO (984,337 bytes,
md5 8ee8e117d9f4564f18a4ab580b9666ca). The two agree on every measured marker and
differ by 87,847 bytes — so matching markers meant the design agreed, not that the
file did. Anything taken from here is from the 1,072,184-byte copy.

⚠️ THE TWO SURFACES COMPOSE DIFFERENTLY AND THAT IS THE POINT OF THE LAYER:
`Cemetery` becomes `Burial`, `Contact` demotes from a row to a secondary line,
the decedent's name and dates leave the grid for the subject, and the word for
unanswered-required changes from "needed" to "missing".

⚠️ TWO GAPS ARE DECLARED AT THE ROWS THAT WANT THEM, rather than filled by inventing
fields. Each is marked `GAP` below. A row that renders less than the design is a
visible, reported shortfall; a field invented to fill it would be an unreported claim.

⚠️ THIS SAID "FOUR" AND WAS ALREADY WRONG BEFORE PIECE 4 TOUCHED IT. Measured
2026-10-06: HEAD carried THREE row-level `GAP:` markers under a docstring claiming
four. Piece 4 then closed one (the capture Service row — `service_time` now exists)
and narrowed another (the summary Service row keeps a DATE gap, not a date-and-time
one), leaving two.

A count written beside the thing it counts drifts the moment either changes, and this
one drifted without any edit to the gaps at all. See CLAUDE.md §11 — a file's account
of itself is untested prose, and this is the second count in this module to go wrong
that way.
"""
from __future__ import annotations

from app.services.capture.rows import (
    LiteralSource,
    FirstOf,
    ComposedSource,
    FieldSource,
    FooterSlot,
    NotesSlot,
    RecordSource,
    Row,
    SubjectSlot,
    Surface,
)
from app.services.capture.schema import SALES_ORDER

#: Separators, verbatim from the prototype.
_DOT = " · "
_DASH = " — "


# ---------------------------------------------------------------------------
# The capture surface — screen 1. Nine rows, counts worded "needed".
# ---------------------------------------------------------------------------

CAPTURE_SALES_ORDER = Surface(
    id="capture",
    unanswered_word="needed",
    # ⚠️ EVERY APPLICABLE QUESTION GETS A ROW, which is the prototype's own
    # `ORDER.filter(applicable)` and what the 2026-10-27 fixes list requires: without
    # it `cemetery_equipment` is optional-and-unmentioned on a fresh order, so the
    # Equipment row James named would not render and could not be clicked.
    show_unmentioned_optional=True,
    # ── ONE ROW PER QUESTION, IN CALL ORDER ─────────────────────────────────────────
    #
    # ⚠️ RESHAPED 2026-10-27 BY RULING, after James walked the screen: "The prototype's
    # pane has a line per question (service day, time and place separately), highlights
    # the line Opas is asking about, labels it 'Deceased'". The previous shape was nine
    # rows grouped by SUBJECT — one "Service" row carrying location, day and time — and
    # it is wrong for guided capture for one reason: the pane now outlines the row Opas
    # is ASKING about, and a row that answers three questions cannot be outlined for
    # one of them.
    #
    # ⚠️ IN THE ENGINE'S `CALL_ORDER`, AND THE DISPATCH'S OWN PARENTHETICAL DISAGREES
    # WITH IT. James wrote "a two-column row per question in call order (Funeral home,
    # Deceased, Vault, Personalization/Print/Dates when they apply, Service day, Time,
    # Service, Cemetery, Equipment)" — that list is the PROTOTYPE's `ORDER`, which puts
    # personalization between the vault and the day. The engine's `CALL_ORDER` puts
    # personalization and its follow-ups LAST, deliberately ("in the order they are
    # chosen").
    #
    # The stated authority is "call order", so that is what this follows, and the
    # behaviour is also better: the asking outline moves DOWN the list and never jumps
    # back up it. Reported to James rather than resolved silently — if he wants the
    # prototype's order, `CALL_ORDER` is the one place to change and this follows it.
    rows=(
        Row(id="funeral_home", label="Funeral home", order=1,
            sources=(FieldSource("funeral_home"),),
            edit_target="funeral_home"),

        # ⚠️ "Deceased", NEVER "Deceased name" — James, 2026-10-27, twice: once in the
        # question clause and once again in the fixes. The field's own label was
        # changed to match; this row had its own copy, which is exactly how a label
        # gets corrected in one place and stays wrong in another.
        Row(id="deceased_name", label="Deceased", order=2,
            sources=(FieldSource("deceased_name"),),
            edit_target="deceased_name"),

        # ⚠️ "Vault", NOT "Vault / Product". The prototype's `LABEL.vault` is "Vault";
        # the slash form was this surface's own invention for a pane that also showed
        # non-vault products.
        Row(id="vault", label="Vault", order=3,
            sources=(FieldSource("vault"),),
            edit_target="vault"),

        # ── the three that were one row ─────────────────────────────────────────────
        # ⚠️ SPLIT BY RULING. The prototype has `day`, `time` and `place` as separate
        # LABELs and asks them as separate questions; combining them meant one row for
        # three questions, so the asking outline had nowhere correct to land.
        Row(id="service_date", label="Service day", order=4,
            sources=(FieldSource("service_date"),),
            edit_target="service_date"),

        # ⚠️ `service_location_other` RIDES THIS ROW rather than opening its own. It is
        # the ANSWER to "where exactly?" when the location is `other`, so "Other ·
        # Smith residence" is one fact read aloud. `FirstOf` prefers the specific text
        # when it exists, which is what the previous combined row already did.
        Row(id="service", label="Service", order=5,
            sources=(FirstOf((
                FieldSource("service_location_other"),
                FieldSource("service_location"),
            )),),
            edit_target="service_location"),

        Row(id="service_time", label="Time", order=6,
            sources=(FieldSource("service_time"),),
            edit_target="service_time"),

        # ⚠️ THE TOWN AND THE ETA STILL COMPOSE HERE, and the reason is unchanged from
        # the row this replaces: the town is not a fact anyone wants on its own — it
        # exists to make the NAME unambiguous — and the ETA is the cemetery ARRIVAL,
        # read back as "St. Mary's · Skaneateles · 11:30 AM". Neither is a question
        # Opas asks on its own in `CALL_ORDER`'s sense: `cemetery_city` is optional and
        # said in the same breath as the name, and `eta` is prompted-but-never-required.
        Row(id="cemetery", label="Cemetery", order=7,
            sources=(ComposedSource((
                FieldSource("cemetery"),
                FieldSource("cemetery_city"),
                FieldSource("eta"),
            ), join=_DOT),),
            edit_target="cemetery"),

        # ⚠️ KEPT THOUGH THE DISPATCH'S LIST OMITS IT, and flagged rather than dropped.
        # `grave_location` is CAPTURED — a director can say "section 4 lot 12" — and a
        # row is the only place it appears. Dropping it to match the list would make a
        # typed value vanish, which is the defect the 2026-10-12 ruling ("captured
        # values must be visible") was made about. It is optional and unmentioned on
        # almost every order, so the hide-optional-unmentioned rule keeps it off screen
        # until somebody says it.
        Row(id="grave_location", label="Grave", order=8,
            sources=(FieldSource("grave_location"),),
            edit_target="grave_location"),

        # ⚠️ "Equipment", not "Cemetery Equipment" — the prototype's `LABEL.equip`. The
        # label flips to "Cremation setup" on an urn vault, and that flip happens where
        # the cremation is KNOWN (the serializer), not here: `Row.label` is static and
        # this layer cannot see the vault's form.
        Row(id="cemetery_equipment", label="Equipment", order=9,
            sources=(FieldSource("cemetery_equipment"),),
            secondary=(FieldSource("extra_chairs_count"),),
            edit_target="cemetery_equipment"),

        # ── personalization and its follow-ups, last, as `CALL_ORDER` asks them ──────
        Row(id="personalization", label="Personalization", order=10,
            sources=(ComposedSource((
                FieldSource("personalization"),
                FieldSource("lifes_reflections_symbol"),
            ), join=_DOT),),
            edit_target="personalization"),

        # ⚠️ ITS OWN ROW NOW, because it is its own QUESTION — "Which Legacy series?"
        # then "Which print?". It composed into Personalization when rows were grouped
        # by subject; under one-row-per-question the asking outline needs it separate.
        Row(id="legacy_print", label="Legacy print", order=11,
            sources=(ComposedSource((
                FieldSource("legacy_series"),
                FieldSource("legacy_print_name"),
            ), join=_DOT),),
            edit_target="legacy_series"),

        # ⚠️ ALSO ITS OWN ROW, and `nameplate_date_format` rides it rather than opening
        # a twelfth: it is a property OF the dates ("1948 — 2026 · Years"), not a fact
        # beside them. Same reasoning that kept it off its own row before the reshape.
        Row(id="dates", label="Dates", order=12,
            sources=(ComposedSource((
                FieldSource("date_of_birth"),
                FieldSource("date_of_death"),
                FieldSource("nameplate_date_format"),
            ), join=_DASH),),
            edit_target="date_of_birth"),

        # ⚠️ `contact` IS GONE, AND IT WAS NOT A QUESTION. It read
        # `RecordSource("customer", "contact_name")` — the customer record, never
        # anything the director said — so under one-row-per-question it has no question
        # to be a row for. Its own comment recorded it as waiting for "the day a
        # captured contact field is ruled in"; that day has not come, and the row can
        # return with the field.
        #
        # ⚠️ AND `burial` IS GONE for the same reason: it sourced `grave_location`,
        # which now has its own row under its own name. A "Burial" row that showed only
        # the grave was a label describing more than it carried.
    ),
)

# ---------------------------------------------------------------------------
# The summary surface — screen 2. Six rows + subject, counts worded "missing".
# ---------------------------------------------------------------------------

SUMMARY_SALES_ORDER = Surface(
    id="summary",
    unanswered_word="missing",
    # Prototype: "John Smith" over "March 14, 1948 — September 14, 2026", ABOVE
    # the grid rather than in it.
    subject=SubjectSlot(
        primary=(FieldSource("deceased_name"),),
        secondary=(ComposedSource(
            (FieldSource("date_of_birth"), FieldSource("date_of_death")),
            join=_DASH),),
    ),
    rows=(
        # ⚠️ `Contact` IS A SECONDARY LINE HERE, a row on the capture surface.
        Row(id="funeral_home", label="Funeral home", order=1,
            sources=(FieldSource("funeral_home"),),
            secondary=(RecordSource("customer", "contact_name"),)),

        Row(id="vault", label="Vault", order=2,
            sources=(FieldSource("vault"),)),

        # ⚠️ GAP CLOSED 2026-10-07 (R4). This marker has now been through all three
        # states and the sequence is the record worth keeping:
        #
        #   original   "a service DATE and TIME, NEITHER of which is a template field"
        #   narrowed   the TIME arrived as `service_time` with Piece 4 (2026-10-06)
        #   closed     the DATE arrived as `service_date` with R4 (2026-10-07)
        #
        # The prototype's secondary is "Thu, Sep 17 · 10:00 AM", and both halves now
        # have fields, so the secondary composes them. Nothing was invented to close
        # it — the field was ruled in, and the marker tracked the shortfall until it
        # was. That is what a declared gap is for.
        Row(id="service", label="Service", order=3,
            sources=(FieldSource("service_location_other"), FieldSource("service_location")),
            secondary=(ComposedSource(
                (FieldSource("service_date"), FieldSource("service_time")), join=_DOT),),
            edit_target="service_location"),

        # ⚠️ RELABELLED. `Cemetery` on capture, `Burial` here. Prototype secondary:
        # "Thu, Sep 17 · 11:30 AM" — burial date AND time, both template fields.
        # ⚠️ THE TOWN AND THE GRAVE LOCATION JOIN THIS ROW, 2026-10-14. James: every
        # captured field must appear on the Review. Measured the same day, three did
        # not — `cemetery_city`, `grave_location` and `nameplate_date_format` were
        # capturable and had nowhere on this surface to show. The town composes with
        # the cemetery exactly as it does on the capture surface; the grave location
        # belongs with the burial and joins its secondary.
        Row(id="burial", label="Burial", order=4,
            sources=(ComposedSource(
                (FieldSource("cemetery"), FieldSource("cemetery_city")),
                join=_DOT),),
            # ⚠️ `eta`, not `burial_time` — same ruling as the capture Cemetery row.
            # The prototype's secondary here is "Thu, Sep 17 · 11:30 AM", the arrival.
            # ⚠️ `service_date`, NOT `burial_date`, SINCE 2026-10-13. Same ruling:
            # the burial day IS the service day, so the summary shows the date the
            # order actually carries rather than a field nobody is asked for.
            secondary=(ComposedSource(
                (FieldSource("service_date"), FieldSource("eta"),
                 FieldSource("grave_location")), join=_DOT),),
            edit_target="cemetery"),

        # ⚠️ REPOINTED 2026-10-07 FOR R1, same dead-source problem as the capture
        # row. ⚠️ AND THE PRIMARY/SECONDARY SPLIT NOW MEANS SOMETHING IT DID NOT:
        # the primary is the KIND of personalization and the secondary is WHICH print
        # or symbol. Before, the primary was one of three kinds and the secondary was
        # the other two — a split with no reading behind it.
        Row(id="personalization", label="Personalization", order=5,
            sources=(FieldSource("personalization"),),
            # ⚠️ `nameplate_date_format` ADDED 2026-10-14 for the same reason — it
            # was captured and shown nowhere on the Review. It is a property of the
            # personalization work, which is this row.
            secondary=(ComposedSource((
                FieldSource("legacy_series"),
                FieldSource("legacy_print_name"),
                FieldSource("lifes_reflections_symbol"),
                FieldSource("nameplate_date_format"),
            ), join=_DOT),),
            edit_target="personalization"),

        # ⚠️ GAP, STILL: the prototype's secondary is "Lowering device, tent, chairs"
        # — the CONTENTS of the equipment package. `cemetery_equipment` resolves to
        # ONE catalog product; its contents belong to the graveside-services model,
        # which is deliberately unbuilt.
        #
        # ⚠️ THE CHAIR COUNT IS NOT THAT GAP CLOSING. James 2026-10-14 asked for the
        # quantity on the Review line, and this is where a Review line carries a
        # second fact. It renders one number for one package; the other six packages
        # still show a primary alone, and the contents of none of them are modelled.
        Row(id="cemetery_equipment", label="Cemetery equipment", order=6,
            sources=(FieldSource("cemetery_equipment"),),
            secondary=(FieldSource("extra_chairs_count"),)),
    ),
    notes=NotesSlot(label="Notes"),
    # ⚠️ DECLARED AND UNFILLED. `hint` is fixed at None by the type — the
    # prototype's derived footer line is not built, and one cosmetic line does not
    # justify a templating mechanism. The approve label names the object type,
    # verbatim from the prototype ("Approve &amp; Create Sales Order").
    footer=FooterSlot(approve_label="Approve & Create Sales Order"),
)


#: Object type -> its declared surfaces, in no particular order.
#:
#: ⚠️ A REGISTRY, LIKE `CAPTURE_TEMPLATES`, so a second object type is a row here
#: rather than a refactor. `sales_order` is the only entry, as it is there.
#:
#: ⚠️ NO `driver` SURFACE IS DECLARED, DELIBERATELY. `grave_location` is captured
#: at order time and displayed to the delivery crew, so it will appear in
#: `orphan_field_ids` until that surface exists — and that report is CORRECT.
#: Declaring a surface nobody is building, to stop a true finding appearing, is
#: editing the record to match the belief (CLAUDE.md §11).
SURFACES: dict[str, tuple[Surface, ...]] = {
    SALES_ORDER: (CAPTURE_SALES_ORDER, SUMMARY_SALES_ORDER),
}


def surfaces_for(object_type: str) -> tuple[Surface, ...]:
    """The declared surfaces for an object type.

    Raises rather than returning empty: an unregistered type is a programming
    error, and an empty tuple would render nothing while looking like a surface
    with no rows.
    """
    try:
        return SURFACES[object_type]
    except KeyError:
        raise KeyError(
            f"no surfaces declared for object type {object_type!r}; "
            f"registered: {sorted(SURFACES)}"
        ) from None
