"""Class registry snapshot — backend mirror of the frontend
`frontend/src/lib/visual-editor/registry/class-registrations.ts`.

The frontend file is the canonical source of truth. This snapshot
mirrors what the backend needs to validate writes (prop names +
types + bounds per class) and to compose resolved sources for the
admin UI's source-tracking output.

Manual mirror — when the frontend class registrations change, this
file must be updated alongside them.

Storage shape:
    CLASS_REGISTRY_SNAPSHOT[class_name] = {
        prop_name: {
            "type": "boolean" | "number" | "string" | "enum" |
                    "tokenReference" | "componentReference" |
                    "array" | "object",
            "bounds": ...,
            "tokenCategory": ...,    # for tokenReference props
        },
        ...
    }
"""

from __future__ import annotations

from typing import Any


PropSchema = dict[str, Any]
ClassProps = dict[str, PropSchema]


# ─── Shared prop catalogs ────────────────────────────────────────


_SHADOW_TOKEN: PropSchema = {
    "type": "tokenReference",
    "tokenCategory": "shadow",
}

_SURFACE_TOKEN: PropSchema = {
    "type": "tokenReference",
    "tokenCategory": "surface",
}

_RADIUS_TOKEN: PropSchema = {
    "type": "tokenReference",
    "tokenCategory": "radius",
}

_ACCENT_TOKEN: PropSchema = {
    "type": "tokenReference",
    "tokenCategory": "accent",
}

_DENSITY: PropSchema = {
    "type": "enum",
    "bounds": ["compact", "comfortable", "spacious"],
}

_BORDER_TREATMENT: PropSchema = {
    "type": "enum",
    "bounds": ["none", "subtle", "accent"],
}

_HOVER_ELEVATION: PropSchema = {"type": "boolean"}


# ─── Class definitions ───────────────────────────────────────────


_WIDGET: ClassProps = {
    "shadowToken": _SHADOW_TOKEN,
    "surfaceToken": _SURFACE_TOKEN,
    "radiusToken": _RADIUS_TOKEN,
    "density": _DENSITY,
    "borderTreatment": _BORDER_TREATMENT,
    "hoverElevation": _HOVER_ELEVATION,
    "headerStyle": {
        "type": "enum",
        "bounds": ["title-and-eyebrow", "title-only", "minimal"],
    },
    "showFooter": {"type": "boolean"},
}


_ENTITY_CARD: ClassProps = {
    "shadowToken": _SHADOW_TOKEN,
    "surfaceToken": _SURFACE_TOKEN,
    "radiusToken": _RADIUS_TOKEN,
    "density": _DENSITY,
    "accentTreatment": {
        "type": "enum",
        "bounds": ["none", "left-bar", "border-tint", "header-bar"],
    },
    "hoverElevation": _HOVER_ELEVATION,
    "imagePosition": {"type": "enum", "bounds": ["none", "left", "top"]},
    "actionBarStyle": {
        "type": "enum",
        "bounds": ["always-visible", "hover-reveal", "menu"],
    },
}


_FOCUS: ClassProps = {
    "headerStyle": {
        "type": "enum",
        "bounds": ["title-and-eyebrow", "title-only", "breadcrumb"],
    },
    "actionBarLayout": {
        "type": "enum",
        "bounds": ["right-aligned", "centered", "split"],
    },
    "transitionStyle": {
        "type": "enum",
        "bounds": ["fade", "slide-up", "slide-from-right"],
    },
    "dismissBehavior": {
        "type": "enum",
        "bounds": ["click-outside", "explicit-only", "esc-or-outside"],
    },
    "accentBorderTreatment": {
        "type": "enum",
        "bounds": ["none", "top-edge", "left-edge", "outline"],
    },
}


_FOCUS_TEMPLATE: ClassProps = {
    "scribePanelPosition": {
        "type": "enum",
        "bounds": ["none", "right", "left", "bottom"],
    },
    "optionalFieldsVisible": {"type": "boolean"},
    "autosaveIntervalSeconds": {"type": "number", "bounds": [5, 120]},
}


_DOCUMENT_BLOCK: ClassProps = {
    "typographyFamily": {"type": "tokenReference", "tokenCategory": "text"},
    "accentToken": _ACCENT_TOKEN,
    "alignment": {"type": "enum", "bounds": ["left", "center", "right"]},
    "spacingRhythm": {
        "type": "enum",
        "bounds": ["tight", "comfortable", "generous"],
    },
    "accentBarHeight": {"type": "number", "bounds": [0, 16]},
}


_WORKFLOW_NODE: ClassProps = {
    "nodeShape": {
        "type": "enum",
        "bounds": ["rectangle", "rounded-rectangle", "rounded-pill"],
    },
    "connectionArrowStyle": {
        "type": "enum",
        "bounds": ["thin", "medium", "thick"],
    },
    "labelPosition": {"type": "enum", "bounds": ["inside", "below", "above"]},
    "accentToken": _ACCENT_TOKEN,
}


_BUTTON: ClassProps = {
    "radiusToken": _RADIUS_TOKEN,
    "paddingDensity": {
        "type": "enum",
        "bounds": ["compact", "comfortable", "spacious"],
    },
    "hoverBehavior": {
        "type": "enum",
        "bounds": ["tint", "darken", "lift"],
    },
    "iconPosition": {
        "type": "enum",
        "bounds": ["leading", "trailing", "icon-only"],
    },
    "fontWeight": {
        "type": "enum",
        "bounds": ["regular", "medium", "semibold"],
    },
}


_FORM_INPUT: ClassProps = {
    "borderTreatment": _BORDER_TREATMENT,
    "focusRingStyle": {
        "type": "enum",
        "bounds": ["none", "accent-glow", "accent-border", "thick-outline"],
    },
    "paddingDensity": {
        "type": "enum",
        "bounds": ["compact", "comfortable", "spacious"],
    },
    "labelPosition": {
        "type": "enum",
        "bounds": ["above", "inline", "floating"],
    },
    "errorTreatment": {
        "type": "enum",
        "bounds": ["border-only", "message-only", "border-and-message"],
    },
}


_SURFACE_CARD: ClassProps = {
    "shadowToken": _SHADOW_TOKEN,
    "surfaceToken": _SURFACE_TOKEN,
    "radiusToken": _RADIUS_TOKEN,
    "paddingDensity": {
        "type": "enum",
        "bounds": ["compact", "comfortable", "spacious"],
    },
    "borderTreatment": _BORDER_TREATMENT,
}


CLASS_REGISTRY_SNAPSHOT: dict[str, ClassProps] = {
    "widget": _WIDGET,
    "entity-card": _ENTITY_CARD,
    "focus": _FOCUS,
    "focus-template": _FOCUS_TEMPLATE,
    "document-block": _DOCUMENT_BLOCK,
    "workflow-node": _WORKFLOW_NODE,
    "button": _BUTTON,
    "form-input": _FORM_INPUT,
    "surface-card": _SURFACE_CARD,
}


def lookup_class(class_name: str) -> ClassProps | None:
    """Return the class-level prop schema map for a given class name,
    or None if unknown to the backend snapshot."""
    return CLASS_REGISTRY_SNAPSHOT.get(class_name)


def all_classes() -> list[str]:
    """Return every class name known to the backend snapshot."""
    return sorted(CLASS_REGISTRY_SNAPSHOT.keys())
