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

⚠️ FOUR GAPS ARE DECLARED AT THE ROWS THAT WANT THEM, rather than filled by
inventing fields. Each is marked `GAP:` below. A row that renders less than the
design is a visible, reported shortfall; a field invented to fill it would be an
unreported claim.
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
        # ⚠️ GAP: THE SERVICE TIME HAS NO TEMPLATE FIELD, and this corrects an
        # earlier finding of mine. On 2026-10-05 I ruled `service_time` "already
        # captured as burial_time" because `create_draft_order_from_extraction`
        # writes `service_time = extraction.burial_time`. The prototype shows them
        # as DIFFERENT FACTS — service at 10:00 AM, burial at 11:30 AM, with the
        # `eta` column's "procession ETA" comment describing the gap between them.
        # So that writer is CONFLATING two times rather than evidencing their
        # equivalence, and my verdict took the defect for the specification.
        #
        # This row therefore renders the location only, which is less than the
        # design. Declared rather than papered over; a service-time field is a
        # product question nobody has ruled.
        Row(id="service", label="Service", order=5,
            sources=(FieldSource("service_location"),),
            edit_target="service_location"),

        # Prototype: "Forest Lawn · Thu 11:30 AM" — labelled `Cemetery` here and
        # `Burial` on the summary. Same facts, different label per surface.
        Row(id="cemetery", label="Cemetery", order=6,
            sources=(ComposedSource(
                (FieldSource("cemetery"), FieldSource("burial_time")), join=_DOT),),
            edit_target="cemetery"),

        # ⚠️ GAP: `vault_size` IS NOT SOURCED HERE, deliberately. The prototype
        # shows "Wilbert Bronze" with no size, and the field is ruled redundant
        # (the variant is the size) but kept until a resolver exists. Sourcing it
        # would render a size the design does not show; leaving it unsourced makes
        # it appear in `orphan_field_ids`, which is the correct report.
        Row(id="vault", label="Vault / Product", order=7,
            sources=(FieldSource("vault"),)),

        # ⚠️ COLLAPSE: three template fields, one row. Prototype:
        # "Legacy print · American Flag".
        Row(id="personalization", label="Personalization", order=8,
            sources=(ComposedSource((
                FieldSource("legacy_print"),
                FieldSource("nameplate_cover_emblem"),
                FieldSource("lifes_reflections"),
            ), join=_DOT),),
            edit_target="legacy_print"),

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

        # ⚠️ GAP: the prototype's secondary is "Thu, Sep 17 · 10:00 AM" — a
        # service DATE and TIME, neither of which is a template field. See the
        # capture surface's `service` row for why that is a correction rather
        # than an omission.
        Row(id="service", label="Service", order=3,
            sources=(FieldSource("service_location"),),
            edit_target="service_location"),

        # ⚠️ RELABELLED. `Cemetery` on capture, `Burial` here. Prototype secondary:
        # "Thu, Sep 17 · 11:30 AM" — burial date AND time, both template fields.
        Row(id="burial", label="Burial", order=4,
            sources=(FieldSource("cemetery"),),
            secondary=(ComposedSource(
                (FieldSource("burial_date"), FieldSource("burial_time")), join=_DOT),),
            edit_target="cemetery"),

        Row(id="personalization", label="Personalization", order=5,
            sources=(FieldSource("legacy_print"),),
            secondary=(ComposedSource((
                FieldSource("nameplate_cover_emblem"),
                FieldSource("lifes_reflections"),
            ), join=_DOT),),
            edit_target="legacy_print"),

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
