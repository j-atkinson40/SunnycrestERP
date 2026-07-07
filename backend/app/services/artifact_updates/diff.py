"""Derived diffs over retained version snapshots (Focus Variations V-2).

Version bumps retain every prior row (is_active=false), so a release's
delta is a pure function of two snapshots. The diff feeds three surfaces:
the patch-notes SCAFFOLD at publish (authored-with-derived-fallback), the
offer panel's review, and the accept flow's per-field choose step.

Core→template inheritance is FIELD-granular by construction (the chrome
cascade is key-presence; geometry/identity aren't template-overridable;
placements are NEVER core-inherited — a core publish cannot touch a
variation's own rows). So the choose step is per-FIELD: a field the
target has overridden is marked `target_state="customized"` — the
cascade keeps the target's value winning after a pin move (keep-mine is
FREE); "take-new" is the explicit opt-in that drops the override key.

Diff JSONB shape (stored on publishes + offers, rendered by the panel):

    {
      "fields": [
        {"family": "identity"|"component"|"geometry"|"chrome"|"canvas",
         "field": str, "from": Any, "to": Any,
         "target_state": "inherited"|"customized",   # offers only
         "target_value": Any}                        # when customized
      ],
      "summary": str,          # the derived one-liner (scaffold fallback)
    }
"""

from __future__ import annotations

from typing import Any

from app.models.focus_core import FocusCore
from app.models.focus_template import FocusTemplate
from app.services.focus_template_inheritance.chrome_validation import (
    CHROME_FIELDS,
)
from app.services.focus_template_inheritance.resolver import expand_preset

_IDENTITY_FIELDS = ("display_name", "description")
_COMPONENT_FIELDS = ("registered_component_kind", "registered_component_name")
_GEOMETRY_FIELDS = (
    "default_starting_column",
    "default_column_span",
    "default_row_index",
    "min_column_span",
    "max_column_span",
)

_FAMILY_LABELS = {
    "identity": "Identity",
    "component": "Component",
    "geometry": "Geometry",
    "chrome": "Chrome",
    "canvas": "Canvas",
}


def derive_core_diff(
    from_core: FocusCore | None,
    to_core: FocusCore,
    *,
    template: FocusTemplate | None = None,
) -> dict:
    """Delta between two core snapshots (from may be None = first publish).

    With `template`, chrome fields the template overrides are marked
    customized (key-presence on the EXPANDED override blob — the same
    check the resolver's cascade runs)."""
    fields: list[dict[str, Any]] = []

    template_chrome = (
        expand_preset(dict(template.chrome_overrides or {}))
        if template is not None
        else {}
    )

    def _add(family: str, field: str, frm: Any, to: Any) -> None:
        if frm == to:
            return
        entry: dict[str, Any] = {
            "family": family, "field": field, "from": frm, "to": to,
            "target_state": "inherited",
        }
        if family == "chrome" and field in template_chrome:
            entry["target_state"] = "customized"
            entry["target_value"] = template_chrome[field]
        fields.append(entry)

    for f in _IDENTITY_FIELDS:
        _add("identity", f, getattr(from_core, f, None) if from_core else None,
             getattr(to_core, f))
    for f in _COMPONENT_FIELDS:
        _add("component", f, getattr(from_core, f, None) if from_core else None,
             getattr(to_core, f))
    for f in _GEOMETRY_FIELDS:
        _add("geometry", f, getattr(from_core, f, None) if from_core else None,
             getattr(to_core, f))

    from_chrome = expand_preset(dict(from_core.chrome or {})) if from_core else {}
    to_chrome = expand_preset(dict(to_core.chrome or {}))
    for f in CHROME_FIELDS:
        _add("chrome", f, from_chrome.get(f), to_chrome.get(f))

    from_canvas = dict(from_core.canvas_config or {}) if from_core else {}
    to_canvas = dict(to_core.canvas_config or {})
    for k in sorted(set(from_canvas) | set(to_canvas)):
        _add("canvas", k, from_canvas.get(k), to_canvas.get(k))

    return {"fields": fields, "summary": _summarize(fields, from_core, to_core)}


def _summarize(
    fields: list[dict], from_core: FocusCore | None, to_core: FocusCore
) -> str:
    """The derived one-liner — the patch-notes scaffold's fallback body."""
    if from_core is None:
        return f"First publish of {to_core.display_name} (v{to_core.version})."
    if not fields:
        return (
            f"v{from_core.version} → v{to_core.version}: no field changes "
            "(component behavior may have changed in code)."
        )
    parts: list[str] = []
    by_family: dict[str, list[dict]] = {}
    for f in fields:
        by_family.setdefault(f["family"], []).append(f)
    for family, items in by_family.items():
        label = _FAMILY_LABELS.get(family, family)
        segs = ", ".join(
            f"{i['field']} {_short(i['from'])} → {_short(i['to'])}"
            for i in items
        )
        parts.append(f"{label}: {segs}")
    return f"v{from_core.version} → v{to_core.version} — " + "; ".join(parts)


def _short(v: Any) -> str:
    if v is None:
        return "—"
    s = str(v)
    return s if len(s) <= 24 else s[:21] + "…"
