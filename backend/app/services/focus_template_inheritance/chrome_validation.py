"""Chrome blob validation for Focus Template Inheritance (sub-arc B-3).

Validates the chrome shape stored at three tiers:

    Tier 1: focus_cores.chrome           (full defaults)
    Tier 2: focus_templates.chrome_overrides   (partial; field-level)
    Tier 3: focus_compositions.deltas.chrome_overrides (partial; field-level)

Same shape at every tier. Tier 1 typically stores complete values;
Tiers 2+3 store partial overrides — present keys override the
parent tier, absent keys inherit. Empty dict `{}` is valid at any
tier (inherit everything from parent).

Chrome v1 vocabulary (locked decisions):

    {
        "background_color": str | None,                # any non-empty string OR None
        "drop_shadow": {                               # OR None
            "offset_x": int,
            "offset_y": int,
            "blur": int (>= 0),
            "spread": int (can be negative),
            "color": str (non-empty)
        } | None,
        "border": {                                    # OR None
            "width": int (>= 0),
            "style": "solid" | "dashed" | "dotted" | "none",
            "color": str (non-empty),
            "radius": int (>= 0)
        } | None,
        "padding": {                                   # OR None
            "top": int (>= 0),
            "right": int (>= 0),
            "bottom": int (>= 0),
            "left": int (>= 0)
        } | None
    }

Unknown top-level keys are rejected. Per-sub-object unknown keys
are rejected too — drop_shadow / border / padding accept exactly
the fields enumerated above.

Color strings: service-layer accepts any non-empty string. The
sub-arc C-1 color picker emits CSS-valid values (hex / rgb / rgba
/ hsl / oklch). Service stays permissive so existing operators can
paste arbitrary tokens.
"""

from __future__ import annotations

from typing import Any


CHROME_FIELDS: tuple[str, ...] = (
    "background_color",
    "drop_shadow",
    "border",
    "padding",
)

BORDER_STYLES: frozenset[str] = frozenset(
    {"solid", "dashed", "dotted", "none"}
)

_DROP_SHADOW_FIELDS: tuple[str, ...] = (
    "offset_x",
    "offset_y",
    "blur",
    "spread",
    "color",
)

_BORDER_FIELDS: tuple[str, ...] = ("width", "style", "color", "radius")

_PADDING_FIELDS: tuple[str, ...] = ("top", "right", "bottom", "left")


class InvalidChromeShape(ValueError):
    """Raised when a chrome blob fails validation. Inherits from
    ValueError so callers can catch it generically; the service-
    layer route translator converts it to HTTP 422 / 400."""


def _require_int(value: Any, field: str, *, allow_negative: bool = False) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise InvalidChromeShape(f"{field} must be an integer")
    if not allow_negative and value < 0:
        raise InvalidChromeShape(f"{field} must be >= 0")
    return value


def _require_nonempty_str(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise InvalidChromeShape(f"{field} must be a non-empty string")
    return value


def _validate_background_color(value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value:
        raise InvalidChromeShape(
            "background_color must be a non-empty string or null"
        )


def _validate_drop_shadow(value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise InvalidChromeShape("drop_shadow must be a dict or null")
    unknown = set(value.keys()) - set(_DROP_SHADOW_FIELDS)
    if unknown:
        raise InvalidChromeShape(
            f"drop_shadow has unknown keys: {sorted(unknown)}; "
            f"allowed: {_DROP_SHADOW_FIELDS}"
        )
    missing = set(_DROP_SHADOW_FIELDS) - set(value.keys())
    if missing:
        raise InvalidChromeShape(
            f"drop_shadow missing required keys: {sorted(missing)}"
        )
    _require_int(value["offset_x"], "drop_shadow.offset_x", allow_negative=True)
    _require_int(value["offset_y"], "drop_shadow.offset_y", allow_negative=True)
    _require_int(value["blur"], "drop_shadow.blur")  # >= 0
    _require_int(value["spread"], "drop_shadow.spread", allow_negative=True)
    _require_nonempty_str(value["color"], "drop_shadow.color")


def _validate_border(value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise InvalidChromeShape("border must be a dict or null")
    unknown = set(value.keys()) - set(_BORDER_FIELDS)
    if unknown:
        raise InvalidChromeShape(
            f"border has unknown keys: {sorted(unknown)}; "
            f"allowed: {_BORDER_FIELDS}"
        )
    missing = set(_BORDER_FIELDS) - set(value.keys())
    if missing:
        raise InvalidChromeShape(
            f"border missing required keys: {sorted(missing)}"
        )
    _require_int(value["width"], "border.width")  # >= 0
    style = value["style"]
    if not isinstance(style, str) or style not in BORDER_STYLES:
        raise InvalidChromeShape(
            f"border.style must be one of {sorted(BORDER_STYLES)}; "
            f"got {style!r}"
        )
    _require_nonempty_str(value["color"], "border.color")
    _require_int(value["radius"], "border.radius")  # >= 0


def _validate_padding(value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise InvalidChromeShape("padding must be a dict or null")
    unknown = set(value.keys()) - set(_PADDING_FIELDS)
    if unknown:
        raise InvalidChromeShape(
            f"padding has unknown keys: {sorted(unknown)}; "
            f"allowed: {_PADDING_FIELDS}"
        )
    missing = set(_PADDING_FIELDS) - set(value.keys())
    if missing:
        raise InvalidChromeShape(
            f"padding missing required keys: {sorted(missing)}"
        )
    for f in _PADDING_FIELDS:
        _require_int(value[f], f"padding.{f}")  # >= 0


_FIELD_VALIDATORS = {
    "background_color": _validate_background_color,
    "drop_shadow": _validate_drop_shadow,
    "border": _validate_border,
    "padding": _validate_padding,
}


def validate_chrome_blob(chrome: Any) -> None:
    """Validate a chrome blob. Raises InvalidChromeShape on any
    structural / type violation. Empty dict `{}` is valid (means
    "inherit everything from parent tier"). Unknown top-level keys
    rejected.

    Per-field validators handle None (explicit-null override) +
    full-object shapes. Field-level cascade is the resolver's
    concern, not this validator's — this fn only checks shape.
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
