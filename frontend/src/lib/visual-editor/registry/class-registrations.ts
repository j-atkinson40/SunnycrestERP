/**
 * Component class registrations — source of truth for the class
 * configuration layer (May 2026).
 *
 * For each class, declares:
 *   - displayName + description
 *   - configurableProps the class editor exposes
 *
 * v1 invariant: each class corresponds 1:1 to a ComponentKind, so
 * `componentClasses: [type]` is the default when a registration
 * doesn't override. Future multi-class support extends this map
 * with non-Kind classes (e.g., a "primary-action" class crossing
 * buttons + form-input submit affordances).
 *
 * Class-level configurableProps are intentionally narrow — they
 * declare what's worth tuning ACROSS every component in the class.
 * Component-level configurableProps remain at the registration
 * level for per-component variation.
 *
 * Validation: a value written to a class config's prop_overrides
 * must conform to the schema declared here. The backend snapshot
 * mirrors this at app/services/component_class_config/registry_snapshot.py.
 */

import type { ConfigPropSchema } from "./types"
// Arc 4a.1 — Focus action bar substrate via class-level buttonSlugs.
// Imported from `shared-props.ts` (NOT `entity-card-sections.ts`) to
// avoid the circular load order that would otherwise register the
// 10 entity-card sub-sections before the auto-register barrel fires.
import { BUTTON_SLUGS_PROP } from "./registrations/shared-props"


export interface ClassRegistration {
  /** The class name. v1 = ComponentKind name. */
  className: string
  displayName: string
  description: string
  /** Class-level configurable props — applied via the class
   * inheritance layer to all components in the class. */
  configurableProps: Record<string, ConfigPropSchema>
}


// ─── Shared prop catalogs ──────────────────────────────────────


const SHADOW_TOKEN_PROP: ConfigPropSchema = {
  type: "tokenReference",
  default: "shadow-level-1",
  tokenCategory: "shadow",
  displayLabel: "Shadow elevation",
  description: "Default shadow level applied to every component in this class.",
}


const SURFACE_TOKEN_PROP: ConfigPropSchema = {
  type: "tokenReference",
  default: "surface-elevated",
  tokenCategory: "surface",
  displayLabel: "Background surface",
  description: "Default surface token used for the component's chrome.",
}


const RADIUS_TOKEN_PROP: ConfigPropSchema = {
  type: "tokenReference",
  default: "radius-base",
  tokenCategory: "radius",
  displayLabel: "Corner radius",
  description: "Default border-radius token applied to component chrome.",
}


const ACCENT_TOKEN_PROP: ConfigPropSchema = {
  type: "tokenReference",
  default: "accent",
  tokenCategory: "accent",
  displayLabel: "Accent token",
  description: "Default accent color used for highlights, focus rings, etc.",
}


const DENSITY_PROP: ConfigPropSchema = {
  type: "enum",
  default: "comfortable",
  bounds: ["compact", "comfortable", "spacious"],
  displayLabel: "Content density",
  description: "How tightly content is packed inside the component.",
}


const BORDER_TREATMENT_PROP: ConfigPropSchema = {
  type: "enum",
  default: "subtle",
  bounds: ["none", "subtle", "accent"],
  displayLabel: "Border style",
  description: "How the perimeter border is drawn — invisible, subtle, or accented.",
}


const HOVER_ELEVATION_PROP: ConfigPropSchema = {
  type: "boolean",
  default: false,
  displayLabel: "Lift on hover",
  description: "When enabled, the component gains a slight shadow lift on hover.",
}


// ─── Class definitions ─────────────────────────────────────────


export const CLASS_REGISTRATIONS: Record<string, ClassRegistration> = {
  widget: {
    className: "widget",
    displayName: "Widget",
    description:
      "Widgets shared base. Affects every widget across dashboards, Pulse layers, and pinable surfaces.",
    configurableProps: {
      shadowToken: SHADOW_TOKEN_PROP,
      surfaceToken: SURFACE_TOKEN_PROP,
      radiusToken: RADIUS_TOKEN_PROP,
      density: DENSITY_PROP,
      borderTreatment: BORDER_TREATMENT_PROP,
      hoverElevation: HOVER_ELEVATION_PROP,
      headerStyle: {
        type: "enum",
        default: "title-and-eyebrow",
        bounds: ["title-and-eyebrow", "title-only", "minimal"],
        displayLabel: "Header style",
        description: "Default header treatment for widget chrome.",
      },
      showFooter: {
        type: "boolean",
        default: true,
        displayLabel: "Show footer",
        description: "Whether widgets render their footer affordance row by default.",
      },
    },
  },

  "entity-card": {
    className: "entity-card",
    displayName: "Entity card",
    description:
      "Cards representing a single entity (case file, batch, contact). Affects kanban tiles, list rows, detail headers.",
    configurableProps: {
      shadowToken: SHADOW_TOKEN_PROP,
      surfaceToken: SURFACE_TOKEN_PROP,
      radiusToken: RADIUS_TOKEN_PROP,
      density: DENSITY_PROP,
      accentTreatment: {
        type: "enum",
        default: "left-bar",
        bounds: ["none", "left-bar", "border-tint", "header-bar"],
        displayLabel: "Accent treatment",
        description: "Where the entity's accent color is applied.",
      },
      hoverElevation: HOVER_ELEVATION_PROP,
      imagePosition: {
        type: "enum",
        default: "left",
        bounds: ["none", "left", "top"],
        displayLabel: "Default image position",
        description: "Where representative imagery sits when present.",
      },
      actionBarStyle: {
        type: "enum",
        default: "hover-reveal",
        bounds: ["always-visible", "hover-reveal", "menu"],
        displayLabel: "Action bar style",
        description: "How per-entity action affordances surface.",
      },
    },
  },

  focus: {
    className: "focus",
    displayName: "Focus",
    description:
      "Focus shells (Decision, Coordination, Execution, Review, Generation). Affects every Focus instance across the platform.",
    configurableProps: {
      headerStyle: {
        type: "enum",
        default: "title-and-eyebrow",
        bounds: ["title-and-eyebrow", "title-only", "breadcrumb"],
        displayLabel: "Header style",
        description: "Default header treatment for the Focus shell.",
      },
      actionBarLayout: {
        type: "enum",
        default: "right-aligned",
        bounds: ["right-aligned", "centered", "split"],
        displayLabel: "Action bar layout",
        description: "How action buttons are arranged in the footer.",
      },
      // Arc 4a.1 — Focus action bar buttons composed via class-level
      // buttonSlugs (R-2.1 canon reuse). Per the Q-ARC4A-2 settled
      // call: per-instance + per-mode + per-button-conditional
      // substrate evolution triggers are NOT met today, so class
      // scope is canonical. Tenant overrides via the class
      // configuration layer apply across every Focus instance in
      // the tenant. Future: when per-Focus-type buttonSlugs is
      // demanded by concrete operator signal, the substrate
      // evolves additively (e.g., per-Focus-template overrides via
      // focus-template class) without retiring this slot.
      buttonSlugs: BUTTON_SLUGS_PROP,
      transitionStyle: {
        type: "enum",
        default: "slide-up",
        bounds: ["fade", "slide-up", "slide-from-right"],
        displayLabel: "Transition style",
        description: "How the Focus enters and exits.",
      },
      dismissBehavior: {
        type: "enum",
        default: "click-outside",
        bounds: ["click-outside", "explicit-only", "esc-or-outside"],
        displayLabel: "Dismiss behavior",
        description: "What gestures dismiss the Focus.",
      },
      accentBorderTreatment: {
        type: "enum",
        default: "top-edge",
        bounds: ["none", "top-edge", "left-edge", "outline"],
        displayLabel: "Accent border",
        description: "Where the accent stripe is drawn around the Focus shell.",
      },
    },
  },

  "focus-template": {
    className: "focus-template",
    displayName: "Focus template",
    description:
      "Pre-configured Focus instances (Triage Decision, Arrangement Scribe, etc.). Inherits Focus class defaults plus template-specific tuning.",
    configurableProps: {
      scribePanelPosition: {
        type: "enum",
        default: "right",
        bounds: ["none", "right", "left", "bottom"],
        displayLabel: "Scribe panel position",
        description: "Where the side scribe / context panel sits.",
      },
      optionalFieldsVisible: {
        type: "boolean",
        default: false,
        displayLabel: "Show optional fields by default",
        description: "When true, optional fields render expanded; when false, collapsed.",
      },
      autosaveIntervalSeconds: {
        type: "number",
        default: 15,
        bounds: [5, 120],
        displayLabel: "Autosave interval",
        description: "How often draft state is committed (seconds).",
      },
      // Arc 4a.1 — per-template action bar override slot. Empty array
      // means "inherit from the parent `focus` class buttonSlugs".
      // When populated, this template's action bar overrides the
      // class-level default per the standard class inheritance walk
      // (registration → class → platform → vertical → tenant → draft).
      buttonSlugs: BUTTON_SLUGS_PROP,
    },
  },

  "document-block": {
    className: "document-block",
    displayName: "Document block",
    description:
      "Composable blocks within rendered documents — header, signature, body sections.",
    configurableProps: {
      typographyFamily: {
        type: "tokenReference",
        default: "font-plex-serif",
        tokenCategory: "text",
        displayLabel: "Typography family",
        description: "Default font family for document chrome.",
      },
      accentToken: ACCENT_TOKEN_PROP,
      alignment: {
        type: "enum",
        default: "left",
        bounds: ["left", "center", "right"],
        displayLabel: "Default alignment",
        description: "Block content alignment when no explicit override.",
      },
      spacingRhythm: {
        type: "enum",
        default: "comfortable",
        bounds: ["tight", "comfortable", "generous"],
        displayLabel: "Spacing rhythm",
        description: "Vertical spacing rhythm between block lines.",
      },
      accentBarHeight: {
        type: "number",
        default: 4,
        bounds: [0, 16],
        displayLabel: "Accent bar height (px)",
        description: "Height of the accent bar at the top of header blocks.",
      },
    },
  },

  "workflow-node": {
    className: "workflow-node",
    displayName: "Workflow node",
    description:
      "Nodes inside workflow canvases. Affects how every node type renders on the canvas.",
    configurableProps: {
      nodeShape: {
        type: "enum",
        default: "rounded-rectangle",
        bounds: ["rectangle", "rounded-rectangle", "rounded-pill"],
        displayLabel: "Node shape",
        description: "Default node silhouette.",
      },
      connectionArrowStyle: {
        type: "enum",
        default: "thin",
        bounds: ["thin", "medium", "thick"],
        displayLabel: "Connection arrow style",
        description: "Weight of arrows drawn between nodes.",
      },
      labelPosition: {
        type: "enum",
        default: "inside",
        bounds: ["inside", "below", "above"],
        displayLabel: "Label position",
        description: "Where the node's label is rendered.",
      },
      accentToken: ACCENT_TOKEN_PROP,
    },
  },

  button: {
    className: "button",
    displayName: "Button",
    description:
      "Interactive buttons across the platform — primary, secondary, destructive, ghost.",
    configurableProps: {
      radiusToken: RADIUS_TOKEN_PROP,
      paddingDensity: {
        type: "enum",
        default: "comfortable",
        bounds: ["compact", "comfortable", "spacious"],
        displayLabel: "Padding density",
        description: "Internal padding scale.",
      },
      hoverBehavior: {
        type: "enum",
        default: "tint",
        bounds: ["tint", "darken", "lift"],
        displayLabel: "Hover behavior",
        description: "Visual treatment on hover.",
      },
      iconPosition: {
        type: "enum",
        default: "leading",
        bounds: ["leading", "trailing", "icon-only"],
        displayLabel: "Icon position",
        description: "Default icon placement.",
      },
      fontWeight: {
        type: "enum",
        default: "medium",
        bounds: ["regular", "medium", "semibold"],
        displayLabel: "Font weight",
        description: "Default font weight.",
      },
    },
  },

  "form-input": {
    className: "form-input",
    displayName: "Form input",
    description:
      "Input fields, selectors, toggles. Affects every form-input across the platform.",
    configurableProps: {
      borderTreatment: BORDER_TREATMENT_PROP,
      focusRingStyle: {
        type: "enum",
        default: "accent-glow",
        bounds: ["none", "accent-glow", "accent-border", "thick-outline"],
        displayLabel: "Focus ring style",
        description: "How the focus ring is drawn.",
      },
      paddingDensity: {
        type: "enum",
        default: "comfortable",
        bounds: ["compact", "comfortable", "spacious"],
        displayLabel: "Padding density",
        description: "Internal padding scale.",
      },
      labelPosition: {
        type: "enum",
        default: "above",
        bounds: ["above", "inline", "floating"],
        displayLabel: "Label position",
        description: "Where the field label sits relative to the input.",
      },
      errorTreatment: {
        type: "enum",
        default: "border-and-message",
        bounds: ["border-only", "message-only", "border-and-message"],
        displayLabel: "Error treatment",
        description: "How validation errors surface.",
      },
    },
  },

  "surface-card": {
    className: "surface-card",
    displayName: "Surface card",
    description:
      "Underlying card primitive other components compose into. Affects modals, popovers, panels.",
    configurableProps: {
      shadowToken: SHADOW_TOKEN_PROP,
      surfaceToken: SURFACE_TOKEN_PROP,
      radiusToken: RADIUS_TOKEN_PROP,
      paddingDensity: {
        type: "enum",
        default: "comfortable",
        bounds: ["compact", "comfortable", "spacious"],
        displayLabel: "Padding density",
        description: "Internal padding scale.",
      },
      borderTreatment: BORDER_TREATMENT_PROP,
    },
  },

  // ── R-2.1 — entity-card-section (May 2026) ───────────────────
  // Named sub-components of `entity-card` registrations
  // (`delivery-card.header` / `delivery-card.body` / etc).
  // Class-level dials below tune properties admins reach for
  // across every sub-section: padding inside, gap between content
  // lines, perimeter border treatment, and density. Per-section
  // configurableProps live at the per-registration level and
  // override class defaults at the prop-resolution layer.
  "entity-card-section": {
    className: "entity-card-section",
    displayName: "Entity card section",
    description:
      "Sub-section of an entity card (header / body / actions / custom). Inherits class defaults from its parent entity-card class but exposes its own padding + spacing dials so admins can tune per-section rhythm without touching the parent card's chrome.",
    configurableProps: {
      padding: {
        type: "enum",
        default: "comfortable",
        bounds: ["compact", "comfortable", "spacious"],
        displayLabel: "Padding",
        description:
          "Inside-section padding scale. Inherits from parent card's density when omitted.",
      },
      gapToken: {
        type: "tokenReference",
        default: "spacing-1",
        tokenCategory: "spacing",
        displayLabel: "Inner gap",
        description: "Vertical gap between content lines inside the section.",
      },
      borderTreatment: BORDER_TREATMENT_PROP,
      density: DENSITY_PROP,
    },
  },
}


/** Convenience: list all class names. */
export function getAllClassNames(): readonly string[] {
  return Object.keys(CLASS_REGISTRATIONS).sort()
}


/** Lookup a class registration by name. */
export function getClassRegistration(
  className: string,
): ClassRegistration | undefined {
  return CLASS_REGISTRATIONS[className]
}


/** Class-level configurable prop schema for a specific prop name. */
export function getClassProp(
  className: string,
  propName: string,
): ConfigPropSchema | undefined {
  return CLASS_REGISTRATIONS[className]?.configurableProps[propName]
}
