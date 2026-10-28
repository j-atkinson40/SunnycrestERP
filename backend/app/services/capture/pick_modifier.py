"""Which modifier picks a pill — a per-user preference.

James's ruling of 2026-10-28:

> A preference on the user: pick modifier = Option (default) | Control | Command.
> Pill labels show the chosen key (⌥1 / ⌃1 / ⌘1). Set James's to Control. Read the
> key by `e.code`, as now.

⚠️ THE DEFAULT IS OPTION AND THAT IS THE EARLIER RULING, NOT AN ARBITRARY PICK.
James, 2026-10-27: "Chrome keeps ⌘1–8 for switching tabs, so ⌘ would only ever work
in a desktop app. ⌥ works in every browser." So Option stays the value a user who
has never chosen gets; Command remains available because a desktop app or a
different browser makes it workable, and the ruling says to offer it.

⚠️ AND THE GLYPH IS SERVED, NOT INFERRED CLIENT-SIDE. The pill label has to show the
key the user actually chose, and a second mapping in the frontend is a second answer
to one question — the shape this codebase keeps paying for. One table here, one
`glyph` field on the wire.
"""
from __future__ import annotations

#: The stored key on `User.preferences`.
PREFERENCE_KEY = "pick_modifier"

MODIFIER_OPTION = "option"
MODIFIER_CONTROL = "control"
MODIFIER_COMMAND = "command"

#: ⚠️ THE DEFAULT, AND IT IS LOAD-BEARING: a user who has never chosen must behave
#: exactly as before this ruling shipped.
DEFAULT_MODIFIER = MODIFIER_OPTION

#: modifier -> the glyph the pill label shows.
#: ⚠️ `⌃` IS THE CONTROL GLYPH (U+2303), NOT A CARET. A literal "^" reads as an
#: exponent beside a digit; `⌃1` is what the key is called on a Mac keyboard.
GLYPHS: dict[str, str] = {
    MODIFIER_OPTION: "⌥",
    MODIFIER_CONTROL: "⌃",
    MODIFIER_COMMAND: "⌘",
}

#: modifier -> the `KeyboardEvent` boolean the browser sets for it.
#: ⚠️ SERVED SO THE CLIENT DOES NOT MAP IT AGAIN. The frontend reads the digit from
#: `e.code` (James's ruling, "as now" — on macOS ⌥1 puts "¡" in `e.key`, so a test on
#: `key` is silently dead under the one modifier the default requires). Which FLAG to
#: check is the same decision, and it belongs beside the glyph.
EVENT_FLAGS: dict[str, str] = {
    MODIFIER_OPTION: "altKey",
    MODIFIER_CONTROL: "ctrlKey",
    MODIFIER_COMMAND: "metaKey",
}

ALLOWED: tuple[str, ...] = (MODIFIER_OPTION, MODIFIER_CONTROL, MODIFIER_COMMAND)


def normalise(value: object) -> str | None:
    """A stored or submitted value as one of `ALLOWED`, or None if it is not one.

    ⚠️ RETURNS None RATHER THAN THE DEFAULT, so a caller can tell "not set" from
    "set to something I do not recognise". The read path treats both as the default;
    the WRITE path must refuse the second rather than silently storing the first.
    """
    if not isinstance(value, str):
        return None
    lowered = value.strip().lower()
    return lowered if lowered in ALLOWED else None


def modifier_of(preferences: object) -> str:
    """The user's modifier, defaulting to Option.

    ⚠️ A STORED VALUE THAT IS NO LONGER ALLOWED FALLS BACK TO THE DEFAULT RATHER THAN
    RAISING. `User.preferences` is a JSONB blob with no constraint, so anything can be
    in there — a hand-edited row, an older vocabulary, a typo from a script. The pills
    must still work.
    """
    if not isinstance(preferences, dict):
        return DEFAULT_MODIFIER
    return normalise(preferences.get(PREFERENCE_KEY)) or DEFAULT_MODIFIER


def describe(modifier: str) -> dict:
    """The three things the client needs: which modifier, its glyph, its event flag."""
    safe = normalise(modifier) or DEFAULT_MODIFIER
    return {
        "pick_modifier": safe,
        "pick_modifier_glyph": GLYPHS[safe],
        "pick_modifier_event_flag": EVENT_FLAGS[safe],
    }
