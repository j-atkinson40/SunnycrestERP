"""Server-side prose composition — three text states, distinguished without colour.

⚠️ SYNTHESIS MOVES TO THE SERVER, SUPERSEDING THE LAYER SERVICES' PLACEMENT.
`pulse/*_layer_service` compose prose in the frontend deliberately. That position
is superseded per the session-2 dispatch, and the reason is mechanical rather
than aesthetic: "every factual claim is a link" requires the synthesiser to hold
ENTITY IDS, and the renderer does not reliably have them. A frontend synthesiser
can write "three invoices are overdue" and cannot say WHICH without the ids
having been carried forward for it -- so the sentence and the links get built in
two places from two sources, and they drift.

⚠️ AND IT IS DETERMINISTIC, NOT GENERATED. Wording must be stable across
refreshes: a note that re-words itself daily cannot be trusted, cannot be
diffed, and cannot be tested. Fragments are typed and individually composed --
there is no single large generation call over the whole note. That also means a
fragment's prose is a pure function of its condition inputs, which is what lets
the composition gate digest the inputs rather than the sentence.

──────────────────────────────────────────────────────────────────────────
THE THREE STATES, AND WHY THEY ARE SPANS RATHER THAN MARKUP

  MEASURED   -- a link. THE LINK IS THE PROVENANCE MARK; there is no separate
                badge saying "this is real". Carries a ReferencedItem.
  INFERRED   -- unlinked, carrying a distinguishing mark. Exact treatment is the
                aesthetics arc's and must survive the chrome/steel language; a
                dotted underline or weight reduction is the documented
                placeholder.
  CONNECTIVE -- plain. The words that make the other two into a sentence.

⚠️ FUNCTIONAL COLOUR IS RESERVED FOR MEANING per DESIGN_LANGUAGE, so none of the
three is expressed with colour. A reader who cannot distinguish red from green
must still be able to tell a measurement from an inference.

⚠️ SPANS, NOT SUBSTRING MARKERS. The obvious cheaper design is to emit one
string plus a list of substrings to mark. That is the false-presence-from-
substring shape (CLAUDE.md §11) waiting to happen: a label that occurs twice in
a sentence gets marked in the wrong place, and nothing about the result looks
wrong. Spans carry their own text, so there is nothing to search for.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

from app.services.fragments.types import FragmentPayload, ReferencedItem

SpanKind = Literal["measured", "inferred", "plain"]


class SynthesisError(ValueError):
    """A span violated the three-state contract. Raised at composition time."""


@dataclass(frozen=True)
class TextSpan:
    """One run of prose in exactly one of the three states."""

    text: str
    kind: SpanKind
    #: Required iff kind == "measured", forbidden otherwise. A measured claim
    #: IS its link; a measured span without one is a claim with no provenance
    #: wearing a provenance mark.
    reference: ReferencedItem | None = None


def measured(text: str, ref: ReferencedItem) -> TextSpan:
    return TextSpan(text=text, kind="measured", reference=ref)


def inferred(text: str) -> TextSpan:
    return TextSpan(text=text, kind="inferred")


def plain(text: str) -> TextSpan:
    return TextSpan(text=text, kind="plain")


#: ⚠️ THE BANNED-WORD TEST, EXTENDED FROM STANDING-SET LABELS TO PROSE.
#: A sentence that tells the reader to act does a badge's work through language,
#: which is the same erosion the standing set refuses -- it just arrives as a
#: verb instead of a colour. The note reports; the prompt's TARGET is where
#: acting happens.
BANNED_IMPERATIVES = (
    "urgent", "immediately", "asap", "must ", "you should", "you need to",
    "action required", "act now", "don't forget", "remember to", "attention",
    "critical:", "warning:", "!",
)


def _assert_not_a_demand(text: str) -> None:
    low = text.lower()
    hits = [w for w in BANNED_IMPERATIVES if w in low]
    if hits:
        raise SynthesisError(
            f"fragment prose reads as a demand ({hits}): {text!r}. The note "
            "reports what is true; the prompt's target is where acting happens. "
            "A sentence that tells the reader to act does a badge's work through "
            "language."
        )


def compose(spans: Sequence[TextSpan], *, title: str, priority: int = 50) -> FragmentPayload:
    """Build a payload from typed spans.

    `synthesized_text` is the concatenation, so every existing consumer that
    reads it keeps working and reads exactly what the spans say -- the two
    cannot drift, because one is derived from the other rather than written
    twice.
    """
    for s in spans:
        if s.kind == "measured" and s.reference is None:
            raise SynthesisError(
                f"measured span carries no reference: {s.text!r}. The link IS "
                "the provenance mark; a measured span without one is a claim "
                "wearing a provenance mark it has not earned."
            )
        if s.kind != "measured" and s.reference is not None:
            raise SynthesisError(
                f"{s.kind} span carries a reference: {s.text!r}. Only measured "
                "text links; an inferred claim that links reads as measured."
            )

    text = "".join(s.text for s in spans)
    _assert_not_a_demand(text)

    return FragmentPayload(
        title=title,
        synthesized_text=text,
        referenced_items=tuple(
            s.reference for s in spans if s.kind == "measured" and s.reference
        ),
        priority=priority,
        spans=tuple(spans),
    )
