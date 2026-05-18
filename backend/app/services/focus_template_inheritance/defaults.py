"""Canonical defaults for newly-created Focus Templates (sub-arc E-1).

The C-2.2c modal sends empty/null `chrome_overrides` / `substrate` /
`typography` on create — operators creating a Tier 2 template via the
new-template flow get a known-good visual baseline matching the
funeral-scheduling mockup canvas.

Discipline (locked decision #6/#8 of sub-arc E-1):
  - Empty-or-null on the API boundary → populate with these defaults.
  - Explicit non-empty values (any field present, even with a `None`
    leaf) → respected verbatim; defaults NOT applied.

`chrome_overrides` deliberately stays an empty dict so a newly-created
template cascades chrome from its inherited Tier 1 core unchanged.
`substrate` + `typography` populate with canonical mockup values so a
fresh template has the warm sunrise atmosphere + frosted-text weights
out of the box.
"""

from __future__ import annotations

from typing import Any, Mapping


# Cascade chrome from the inherited core unchanged. Explicit empty
# dict, not None — empty dict is a valid persisted shape that the
# resolver interprets as "no overrides at this tier."
DEFAULT_CHROME_OVERRIDES: dict[str, Any] = {}


# Canonical "morning-warm at intensity 100" — matches the
# funeral-scheduling apple-pre-liquid-glass mockup canvas exactly.
DEFAULT_SUBSTRATE: dict[str, Any] = {
    "preset": "morning-warm",
    "intensity": 100,
    "base_token": "surface-base",
    "accent_token_1": "surface-elevated",
    "accent_token_2": None,
}


# Canonical "frosted-text" weights + warm content tokens — matches the
# mockup card-title + body-row treatment.
DEFAULT_TYPOGRAPHY: dict[str, Any] = {
    "preset": "frosted-text",
    "heading_weight": 600,
    "body_weight": 500,
    "heading_color_token": "content-strong",
    "body_color_token": "content-base",
}


def is_empty_blob(blob: Mapping[str, Any] | None) -> bool:
    """Empty-or-null sentinel used by `create_template`.

    True when:
      - blob is None
      - blob is an empty mapping (no keys)

    Any blob with at least one key is treated as explicit operator
    intent — defaults are NOT applied even if every value is null.
    """
    return blob is None or len(blob) == 0
