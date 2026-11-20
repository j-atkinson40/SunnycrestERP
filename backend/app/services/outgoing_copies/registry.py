"""Which document kinds exist, and which area each belongs to.

⚠️ **THE AREA IS WHAT DECIDES WHO MAY SEE A COPY, SO IT IS DECLARED HERE AND
NOWHERE ELSE.** `outgoing_copies` is one table holding documents from every
part of the platform. A payroll-limited reader must see R-115 copies and must
not see, say, an invoice copy — and the only thing that can enforce that is a
mapping from document kind to area, applied on every read.

This is the COMPOSED-SURFACE pattern the area guard already knows: the route
carries no single `area:` tag because its rows span areas, so it declares
itself composed and filters its own output. `COMPOSED_ROUTES` in
`core/areas.py` is what records that the filtering is BUILT rather than
intended — see the Opas capabilities router, which does the same thing for the
same reason.

⚠️ **A KIND NOT IN THIS REGISTRY IS REFUSED, NOT DEFAULTED.** Defaulting an
unknown kind to a permissive area would make the next document kind visible to
everyone the day somebody forgot to register it; defaulting to a restrictive
one would hide copies with no sign that they existed. Raising is the only
option that cannot be wrong quietly.
"""
from __future__ import annotations

from dataclasses import dataclass


class UnknownDocumentKind(KeyError):
    """A document kind with no registry entry. Never defaulted."""


@dataclass(frozen=True)
class DocumentKind:
    kind: str
    #: The area a caller must be able to read for its copies to be visible.
    area: str
    #: What a screen calls it.
    label: str
    #: ⚠️ The renderer's id and version are stamped onto every copy, because
    #: a copy freezes DATA and needs to say what turned it into a page. Bump
    #: the version when the layout changes in a way that would make an old
    #: copy reprint differently.
    renderer: str
    renderer_version: str


KINDS: dict[str, DocumentKind] = {
    "r115": DocumentKind(
        kind="r115",
        area="payroll",
        label="Union remittance (R-115)",
        renderer="r115_print",
        renderer_version="1",
    ),
}


def kind_for(document_kind: str) -> DocumentKind:
    try:
        return KINDS[document_kind]
    except KeyError:
        raise UnknownDocumentKind(
            f"{document_kind!r} is not a registered document kind; known: "
            f"{sorted(KINDS)}. A kind must declare its AREA before copies of "
            "it can be stored or shown — the area is what decides who may see "
            "them, and defaulting it would either leak the copy or hide it "
            "with no sign it exists."
        ) from None


def readable_kinds(grants) -> list[str]:
    """The kinds this caller may see copies of.

    `grants` is `allowed_area_grants(...)`: `None` for an unlimited role,
    otherwise a mapping of area to level. ⚠️ Only READ is asked here —
    `area_admits_read`'s own docstring says the LEVEL is not consulted, and a
    copy is a read whatever level the caller holds in that area.
    """
    from app.core.areas import area_admits_read

    return sorted(k for k, d in KINDS.items() if area_admits_read(d.area, grants))
