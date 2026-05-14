"""Chrome blob validation for Focus Template Inheritance (sub-arc B-3.5).

Validates the chrome v2 shape stored at three tiers:

    Tier 1: focus_cores.chrome           (full defaults)
    Tier 2: focus_templates.chrome_overrides   (partial; field-level)
    Tier 3: focus_compositions.deltas.chrome_overrides (partial; field-level)

Same shape at every tier. Tier 1 typically stores complete values;
Tiers 2+3 store partial overrides — present keys override the
parent tier, absent keys inherit. Empty dict `{}` is valid at any
tier (inherit everything from parent).

Chrome v2 vocabulary (locked sub-arc B-3.5 decisions):

    {
        "preset":           "card" | "modal" | "dropdown" |
                            "toast" | "floating" | "frosted" |
                            "custom" | None,
        "elevation":        int (0-100) | None,
        "corner_radius":    int (0-100) | None,
        "backdrop_blur":    int (0-100) | None,
        "background_token": str | None,    # design-token reference
        "border_token":     str | None,    # design-token reference
        "padding_token":    str | None,    # design-token reference
    }

Preset semantics: named compositions resolve to specific token
defaults in the resolver (see resolver._PRESETS). Explicit fields
(elevation, corner_radius, *_token) override the preset's defaults
for those fields. `preset="custom"` means "no preset — use explicit
overrides only." Per-field cascade is the resolver's concern, NOT
this validator's — this fn only checks shape.

Token references are validated permissively at the service layer
(any non-empty string accepted). Missing-token resolution is a
consumer-side concern (CSS variable fallback in the runtime
renderer).
"""

from __future__ import annotations

from typing import Any


CHROME_FIELDS: tuple[str, ...] = (
    "preset",
    "elevation",
    "corner_radius",
    "backdrop_blur",
    "background_token",
    "border_token",
    "padding_token",
)

VALID_PRESETS: frozenset[str] = frozenset(
    {"card", "modal", "dropdown", "toast", "floating", "frosted", "custom"}
)


class InvalidChromeShape(ValueError):
    """Raised when a chrome blob fails validation. Inherits from
    ValueError so callers can catch it generically; the service-
    layer route translator converts it to HTTP 422 / 400."""


def _validate_preset(value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, str) or value not in VALID_PRESETS:
        raise InvalidChromeShape(
            f"preset must be one of {sorted(VALID_PRESETS)} or null; "
            f"got {value!r}"
        )


def _validate_slider(value: Any, field: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidChromeShape(f"{field} must be an integer in [0, 100]")
    if value < 0 or value > 100:
        raise InvalidChromeShape(
            f"{field} must be in [0, 100]; got {value}"
        )


def _validate_token(value: Any, field: str) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value:
        raise InvalidChromeShape(
            f"{field} must be a non-empty string or null"
        )


_FIELD_VALIDATORS = {
    "preset": _validate_preset,
    "elevation": lambda v: _validate_slider(v, "elevation"),
    "corner_radius": lambda v: _validate_slider(v, "corner_radius"),
    "backdrop_blur": lambda v: _validate_slider(v, "backdrop_blur"),
    "background_token": lambda v: _validate_token(v, "background_token"),
    "border_token": lambda v: _validate_token(v, "border_token"),
    "padding_token": lambda v: _validate_token(v, "padding_token"),
}


def validate_chrome_blob(chrome: Any) -> None:
    """Validate a chrome v2 blob. Raises InvalidChromeShape on any
    structural / type violation. Empty dict `{}` is valid (means
    "inherit everything from parent tier"). Unknown top-level keys
    rejected — B-3's vocabulary (background_color / drop_shadow /
    border / padding) is fully retired and will trip the unknown-key
    check.
    """
    if not isinstance(chrome, dict):
        raise InvalidChromeShape("chrome must be a dict")
    unknown = set(chrome.keys()) - set(CHROME_FIELDS)
    if unknown:
        raise InvalidChromeShape(
            f"chrome has unknown keys: {sorted(unknown)}; "
            f"allowed: {CHROME_FIELDS}"
        )
    for field, value in chrome.items():
        _FIELD_VALIDATORS[field](value)
