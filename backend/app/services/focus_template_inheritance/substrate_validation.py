"""Substrate blob validation for Focus Template Inheritance (sub-arc B-4).

Validates the substrate v1 shape stored at two tiers:

    Tier 2: focus_templates.substrate           (defaults)
    Tier 3: focus_compositions.deltas.substrate_overrides (partial; field-level)

Same shape at both tiers. Tier 2 typically stores complete values
(via preset); Tier 3 stores partial overrides — present keys override
Tier 2, absent keys inherit. Tier 1 cores are intentionally
substrate-free (substrate is a Focus-level atmospheric backdrop, not
a core composition concern).

Substrate v1 vocabulary (locked sub-arc B-4 decisions):

    {
        "preset":         "morning-warm" | "morning-cool" |
                          "evening-lounge" | "neutral" |
                          "custom" | None,
        "intensity":      int (0-100) | None,
        "base_token":     str | None,    # design-token reference
        "accent_token_1": str | None,    # design-token reference
        "accent_token_2": str | None,    # design-token reference
    }

Preset semantics: named compositions resolve to specific token
defaults in the resolver (see resolver.SUBSTRATE_PRESETS). Explicit
fields override the preset's defaults for those fields. `preset=
"custom"` means "no preset — use explicit overrides only." Per-field
cascade is the resolver's concern, NOT this validator's — this fn
only checks shape.

Token references are validated permissively (any non-empty string
accepted). Missing-token resolution is a consumer-side concern (CSS
variable fallback in the runtime renderer, C-2's responsibility).

Intensity field semantics: storage is slider position 0-100; runtime
CSS computation (gradient stops, alpha, lightness translation) is
the frontend renderer's concern — the resolver preserves the integer
value verbatim.
"""

from __future__ import annotations

from typing import Any


SUBSTRATE_FIELDS: tuple[str, ...] = (
    "preset",
    "intensity",
    "base_token",
    "accent_token_1",
    "accent_token_2",
)

VALID_SUBSTRATE_PRESETS: frozenset[str] = frozenset(
    {"morning-warm", "morning-cool", "evening-lounge", "neutral", "custom"}
)


class InvalidSubstrateShape(ValueError):
    """Raised when a substrate blob fails validation. Inherits from
    ValueError so callers can catch it generically; the service-
    layer route translator converts it to HTTP 422 / 400."""


def _validate_preset(value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, str) or value not in VALID_SUBSTRATE_PRESETS:
        raise InvalidSubstrateShape(
            f"preset must be one of {sorted(VALID_SUBSTRATE_PRESETS)} or null; "
            f"got {value!r}"
        )


def _validate_intensity(value: Any) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidSubstrateShape("intensity must be an integer in [0, 100]")
    if value < 0 or value > 100:
        raise InvalidSubstrateShape(
            f"intensity must be in [0, 100]; got {value}"
        )


def _validate_token(value: Any, field: str) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value:
        raise InvalidSubstrateShape(
            f"{field} must be a non-empty string or null"
        )


_FIELD_VALIDATORS = {
    "preset": _validate_preset,
    "intensity": _validate_intensity,
    "base_token": lambda v: _validate_token(v, "base_token"),
    "accent_token_1": lambda v: _validate_token(v, "accent_token_1"),
    "accent_token_2": lambda v: _validate_token(v, "accent_token_2"),
}


def validate_substrate_blob(substrate: Any) -> None:
    """Validate a substrate v1 blob. Raises InvalidSubstrateShape on
    any structural / type violation. Empty dict `{}` is valid (means
    "inherit everything from parent tier"). Unknown top-level keys
    rejected.
    """
    if not isinstance(substrate, dict):
        raise InvalidSubstrateShape("substrate must be a dict")
    unknown = set(substrate.keys()) - set(SUBSTRATE_FIELDS)
    if unknown:
        raise InvalidSubstrateShape(
            f"substrate has unknown keys: {sorted(unknown)}; "
            f"allowed: {SUBSTRATE_FIELDS}"
        )
    for field, value in substrate.items():
        _FIELD_VALIDATORS[field](value)
