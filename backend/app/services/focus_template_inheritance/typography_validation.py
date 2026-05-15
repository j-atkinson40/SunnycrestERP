"""Typography blob validation for Focus Template Inheritance (sub-arc B-5).

Validates the typography v1 shape stored at two tiers:

    Tier 2: focus_templates.typography           (defaults)
    Tier 3: focus_compositions.deltas.typography_overrides (partial; field-level)

Same shape at both tiers. Tier 2 typically stores complete values
(via preset); Tier 3 stores partial overrides — present keys override
Tier 2, absent keys inherit. Tier 1 cores are intentionally
typography-free (typography is a Focus-level concern, not a core
composition concern).

Typography v1 vocabulary (locked sub-arc B-5 decisions):

    {
        "preset":              "card-text" | "frosted-text" |
                               "headline" | "custom" | None,
        "heading_weight":      int (400-900) | None,
        "heading_color_token": str | None,    # design-token reference
        "body_weight":         int (400-900) | None,
        "body_color_token":    str | None,    # design-token reference
    }

Preset semantics: named compositions resolve to specific defaults in
the resolver (see resolver.TYPOGRAPHY_PRESETS). Explicit fields
override the preset's defaults for those fields. `preset="custom"`
means "no preset — use explicit overrides only." Per-field cascade
is the resolver's concern, NOT this validator's — this fn only
checks shape.

Token references are validated permissively (any non-empty string
accepted). Missing-token resolution is a consumer-side concern.

Weight semantics: CSS font-weight scale, integer 400-900 inclusive.
Multiples of 100 NOT enforced — the spec accepts any int in range.
Family / line-height / letter-spacing / size are platform-canonical
concerns owned by DESIGN_LANGUAGE §4, NOT part of this vocabulary.
"""

from __future__ import annotations

from typing import Any


TYPOGRAPHY_FIELDS: tuple[str, ...] = (
    "preset",
    "heading_weight",
    "heading_color_token",
    "body_weight",
    "body_color_token",
)

VALID_TYPOGRAPHY_PRESETS: frozenset[str] = frozenset(
    {"card-text", "frosted-text", "headline", "custom"}
)


class InvalidTypographyShape(ValueError):
    """Raised when a typography blob fails validation. Inherits from
    ValueError so callers can catch it generically; the service-
    layer route translator converts it to HTTP 422 / 400."""


def _validate_preset(value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, str) or value not in VALID_TYPOGRAPHY_PRESETS:
        raise InvalidTypographyShape(
            f"preset must be one of {sorted(VALID_TYPOGRAPHY_PRESETS)} or null; "
            f"got {value!r}"
        )


def _validate_weight(value: Any, field: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidTypographyShape(
            f"{field} must be an integer in [400, 900]"
        )
    if value < 400 or value > 900:
        raise InvalidTypographyShape(
            f"{field} must be in [400, 900]; got {value}"
        )


def _validate_token(value: Any, field: str) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value:
        raise InvalidTypographyShape(
            f"{field} must be a non-empty string or null"
        )


_FIELD_VALIDATORS = {
    "preset": _validate_preset,
    "heading_weight": lambda v: _validate_weight(v, "heading_weight"),
    "heading_color_token": lambda v: _validate_token(v, "heading_color_token"),
    "body_weight": lambda v: _validate_weight(v, "body_weight"),
    "body_color_token": lambda v: _validate_token(v, "body_color_token"),
}


def validate_typography_blob(typography: Any) -> None:
    """Validate a typography v1 blob. Raises InvalidTypographyShape on
    any structural / type violation. Empty dict `{}` is valid (means
    "inherit everything from parent tier"). Unknown top-level keys
    rejected.
    """
    if not isinstance(typography, dict):
        raise InvalidTypographyShape("typography must be a dict")
    unknown = set(typography.keys()) - set(TYPOGRAPHY_FIELDS)
    if unknown:
        raise InvalidTypographyShape(
            f"typography has unknown keys: {sorted(unknown)}; "
            f"allowed: {TYPOGRAPHY_FIELDS}"
        )
    for field, value in typography.items():
        _FIELD_VALIDATORS[field](value)
