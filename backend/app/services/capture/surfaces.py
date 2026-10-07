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
    rows=(
        Row(id="funeral_home", label="Funeral Home", order=1,
            sources=(FieldSource("funeral_home"),)),

        # ⚠️ RECORD-ONLY, AND THE ORDERED-SOURCE EXAMPLE DOES NOT YET APPLY. The
        # amendment-1 illustration was `[captured contact_name, customer record]`,
        # which presumes a CAPTURED contact field. No such template field exists
        # and none was ruled in — the three fields added 2026-10-05 were
        # date_of_birth, date_of_death and cemetery_equipment.
        #
        # So this row reads the record alone. The ordered mechanism is built and
        # tested, and this row becomes its first production instance the day a
        # captured contact field is ruled in — the call does know who spoke, which
        # is the argument for it.
        Row(id="contact", label="Contact", order=2,
            sources=(RecordSource("customer", "contact_name"),)),

        Row(id="deceased_name", label="Deceased Name", order=3,
            sources=(FieldSource("deceased_name"),)),

        # Prototype: "Mar 14, 1948 — Sep 14, 2026". Two fields, one row.
        Row(id="dates", label="Dates", order=4,
            sources=(ComposedSource(
                (FieldSource("date_of_birth"), FieldSource("date_of_death")),
                join=_DASH),),
            edit_target="date_of_death"),

        # Prototype: "St. Mary's · Thu 10:00 AM".
        #
        # ⚠️ ORDERED SOURCES, FIRST-ANSWERED-WINS — and this row is the mechanism's
        # first production use. `service_location_other` comes FIRST because it is the
        # more specific answer: when the director said "other", the place's name is in
        # that field and the vocabulary value is just the word "other".
        #
        # ⚠️ NO NEW ROW, BY RULING. `service_location_other` continues this row rather
        # than opening one of its own — the prototype shows the service as a single
        # line, and a row per field is the assumption this layer exists to break.
        #
        # ⚠️ THE SERVICE-TIME GAP IS CLOSED. This comment used to record that
        # `service_time` had no template field and that my 2026-10-05 ruling calling it
        # "already captured as burial_time" had read a defect as the specification. The
        # field now exists — `burial_time` was renamed to it — so the row composes a
        # location and a time as the prototype shows ("St. Mary's · Thu 10:00 AM").
        # ⚠️ `service_date` JOINED THIS ROW 2026-10-07 (R4). The prototype's line is
        # "St. Mary's · Thu 10:00 AM" — a place, a DAY and a time — and the day had
        # no template field until R4. It composes into the existing row rather than
        # opening one of its own, for the same reason the location did: the prototype
        # shows the service as a single line.
        Row(id="service", label="Service", order=5,
            sources=(ComposedSource((
                FieldSource("service_location_other"),
                FieldSource("service_date"),
                FieldSource("service_time"),
            ), join=_DOT),
                ComposedSource((
                    FieldSource("service_location"),
                    FieldSource("service_date"),
                    FieldSource("service_time"),
                ), join=_DOT)),
            edit_target="service_location"),

        # Prototype: "Forest Lawn · Thu 11:30 AM" — labelled `Cemetery` here and
        # `Burial` on the summary. Same facts, different label per surface.
        # ⚠️ `eta` REPLACES `burial_time` HERE, BY RULING, and the slot is the
        # argument: the prototype shows "Forest Lawn · Thu 11:30 AM", the cemetery
        # ARRIVAL, which is the procession ETA. The field that used to render here was
        # named `burial_time` and actually held what the director said about the
        # SERVICE, which is why it was renamed to `service_time` and moved to the
        # Service row.
        #
        # Two time facts, two rows, and no third name for anyone to conflate.
        # ⚠️ `cemetery_city` JOINED THIS ROW 2026-10-07 (R4). It composes with the
        # name rather than standing alone because the town is not a fact anyone wants
        # on its own — it exists to make the NAME unambiguous, and "St. Mary's ·
        # Auburn · 11:30 AM" is how a director reads it back.
        Row(id="cemetery", label="Cemetery", order=6,
            sources=(ComposedSource((
                FieldSource("cemetery"),
                FieldSource("cemetery_city"),
                FieldSource("eta"),
            ), join=_DOT),),
            edit_target="cemetery"),

        # ⚠️ NO SIZE ROW, AND NO LONGER A GAP. This comment used to record
        # `vault_size` as deliberately unsourced — the prototype shows
        # "Wilbert Bronze" with no size, and the field was ruled redundant but
        # kept until a resolver existed. The resolver exists and the field is
        # gone, so there is nothing to source: the variant IS the size, and the
        # product name is the whole answer.
        Row(id="vault", label="Vault / Product", order=7,
            sources=(FieldSource("vault"),)),

        # ⚠️ REPOINTED 2026-10-07 FOR R1, AND THE OLD SOURCES WERE DEAD THE MOMENT
        # THE QUESTIONS COLLAPSED. This row read `legacy_print`,
        # `nameplate_cover_emblem` and `lifes_reflections` — three template fields
        # that no longer exist, so every source would have resolved to nothing and
        # the row would have rendered blank on every order. The orphan check caught
        # it, which is what that check is for.
        #
        # ⚠️ AND THE COLLAPSE MADE THE ROW MATCH THE PROTOTYPE MORE CLOSELY, NOT
        # LESS. The prototype renders "Legacy print · American Flag" — a KIND and a
        # DETAIL, which is exactly the shape R1 produces: the answer names the kind,
        # `legacy_print_name` or `lifes_reflections_symbol` names the thing. Under
        # three questions this row was joining three kinds and the detail had
        # nowhere to come from.
        Row(id="personalization", label="Personalization", order=8,
            sources=(ComposedSource((
                FieldSource("personalization"),
                FieldSource("legacy_print_name"),
                FieldSource("lifes_reflections_symbol"),
            ), join=_DOT),),
            edit_target="personalization"),

        Row(id="cemetery_equipment", label="Cemetery Equipment", order=9,
            sources=(FieldSource("cemetery_equipment"),)),
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
        Row(id="burial", label="Burial", order=4,
            sources=(FieldSource("cemetery"),),
            # ⚠️ `eta`, not `burial_time` — same ruling as the capture Cemetery row.
            # The prototype's secondary here is "Thu, Sep 17 · 11:30 AM", the arrival.
            secondary=(ComposedSource(
                (FieldSource("burial_date"), FieldSource("eta")), join=_DOT),),
            edit_target="cemetery"),

        # ⚠️ REPOINTED 2026-10-07 FOR R1, same dead-source problem as the capture
        # row. ⚠️ AND THE PRIMARY/SECONDARY SPLIT NOW MEANS SOMETHING IT DID NOT:
        # the primary is the KIND of personalization and the secondary is WHICH print
        # or symbol. Before, the primary was one of three kinds and the secondary was
        # the other two — a split with no reading behind it.
        Row(id="personalization", label="Personalization", order=5,
            sources=(FieldSource("personalization"),),
            secondary=(ComposedSource((
                FieldSource("legacy_print_name"),
                FieldSource("lifes_reflections_symbol"),
            ), join=_DOT),),
            edit_target="personalization"),

        # ⚠️ GAP: the prototype's secondary is "Lowering device, tent, chairs" —
        # the contents of the equipment package. `cemetery_equipment` resolves to
        # ONE catalog product; its contents belong to the graveside-services model,
        # which is deliberately unbuilt. Primary renders, secondary does not.
        Row(id="cemetery_equipment", label="Cemetery equipment", order=6,
            sources=(FieldSource("cemetery_equipment"),)),
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
