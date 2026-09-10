"""One span serialiser, for every consumer of note text.

⚠️ PROSE, THE DEFERRAL RECORD AND THE SETTLED RECORD ALL COME THROUGH HERE.

Three copies of "turn spans into JSON" would drift, and the drift shows up as a
record whose measured spans stopped being links — provenance quietly lost on
exactly the copy someone reads a week later, with nothing about the sentence
looking wrong. The tests assert EQUALITY between what prose emits and what a
record emits, not the shape of each.
"""

from __future__ import annotations

from typing import Any, Iterable


def serialise_spans(spans: Iterable[Any]) -> list[dict[str, Any]]:
    """Typed spans -> the wire shape. The only implementation."""
    return [
        {
            "text": sp.text,
            "state": sp.kind,
            "href": sp.reference.href if sp.reference else None,
            "entity_id": sp.reference.entity_id if sp.reference else None,
        }
        for sp in spans
    ]
