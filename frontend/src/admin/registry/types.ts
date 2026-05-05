/**
 * Bridgeable Admin Visual Editor — Phase 1 Component Registry.
 *
 * Type definitions for the registration metadata schema. The
 * expressiveness of this schema is the ceiling on the editor's
 * eventual capability — every category that's missing here is
 * something the editor cannot edit, no matter how sophisticated
 * its UI. New categories are added via the `extensions` field
 * (forward-compat) or by extending the schema and bumping
 * `REGISTRY_SCHEMA_VERSION`.
 */

import type { ComponentType } from "react"


// Current schema version of the registry's metadata format. Bump
// when the shape of `RegistrationMetadata` changes in a way that
// requires migration of existing registrations. Tracked per
// registration via `RegistrationMetadata.schemaVersion`.
export const REGISTRY_SCHEMA_VERSION = 1


// ─── Component type discriminator ────────────────────────────────

/** Top-level kind of a registered component. Extensible — Phase 2+
 * adds editor-driven types ("vertical-template", "theme", etc.)
 * without breaking existing registrations. */
export type ComponentKind =
  | "widget"
  | "focus"
  | "focus-template"
  | "document-block"
  | "pulse-widget"
  | "workflow-node"
  | "layout"
  | "composite"


// ─── Scope dimensions ────────────────────────────────────────────

/** Tenant vertical applicability. `"all"` means universal across
 * every vertical the platform supports today and tomorrow. The
 * literal vertical strings mirror `Company.vertical` values. */
export type VerticalScope =
  | "all"
  | "manufacturing"
  | "funeral_home"
  | "cemetery"
  | "crematory"

/** Which user paradigms this component is designed for. Per
 * PLATFORM_PRODUCT_PRINCIPLES.md, four canonical paradigms.
 * `"all"` means the component adapts across all four. */
export type UserParadigm =
  | "all"
  | "owner-operator"
  | "operator-power-user"
  | "focused-executor"
  | "customer-external-user"


// ─── Configurable prop schema ────────────────────────────────────

/** Schema-described type for a single configurable prop. The
 * editor renders different inputs per type (boolean → switch,
 * tokenReference → palette picker, componentReference →
 * component picker, etc.). */
export type ConfigPropType =
  | "boolean"
  | "number"
  | "string"
  | "enum"
  | "tokenReference"
  | "componentReference"
  | "array"
  | "object"

/** Categories of design tokens consumable via tokenReference
 * props. Mirrors the families declared in `tokens.css` (surface,
 * content, border, accent, status, shadow, radius, text/typography,
 * duration, easing). The editor uses this to filter the picker to
 * only valid tokens for a given prop. */
export type TokenCategory =
  | "surface"
  | "content"
  | "border"
  | "accent"
  | "status"
  | "shadow"
  | "radius"
  | "text"
  | "spacing"
  | "duration"
  | "easing"
  | "any"

/** Per-prop schema entry. The editor reads this to render the
 * right input. Runtime is unaffected — the component still receives
 * the prop as a normal React prop. */
export interface ConfigPropSchema<TDefault = unknown> {
  type: ConfigPropType
  /** Default value rendered when the editor first opens or when
   * the user resets to default. Always required so the editor
   * never has to invent a value. */
  default: TDefault
  /** For `number`: `[min, max]` clamping. For `enum`: array of
   * allowed values. For `array`: `{ minLength?, maxLength? }`.
   * Optional otherwise. */
  bounds?: unknown
  /** For `tokenReference`: which family of tokens are valid.
   * Defaults to `"any"`. */
  tokenCategory?: TokenCategory
  /** For `componentReference`: array of `ComponentKind` values
   * allowed for the picker. */
  componentTypes?: ComponentKind[]
  /** Human-readable description of what the prop does. Shown in
   * the editor as a tooltip / help text. */
  description?: string
  /** Human-readable label for the editor UI. Falls back to a
   * humanized form of the prop key when omitted. */
  displayLabel?: string
  /** For `array` / `object`: the schema for child entries. */
  itemSchema?: ConfigPropSchema
  /** Indicates the prop is required (editor will not allow
   * clearing it). Defaults to false. */
  required?: boolean
}


// ─── Composition (slots + children) ──────────────────────────────

/** A named region inside a component into which children can be
 * placed. The editor uses slots to drive composition UIs (drop
 * zones, child pickers). */
export interface SlotDeclaration {
  name: string
  /** Component kinds that may be placed in this slot. Empty
   * array means "any registered component". */
  acceptedTypes: ComponentKind[]
  /** Optional cap on number of children. */
  maxChildren?: number
  /** Optional default composition (component-name references,
   * resolved at editor open). */
  defaultChildren?: Array<{ kind: ComponentKind; name: string }>
  /** Human-readable label for the editor UI. */
  displayLabel?: string
  description?: string
}


// ─── Variants ────────────────────────────────────────────────────

/** A named variant of a component (e.g., button "primary" vs
 * "destructive", widget "glance" vs "detail"). Each variant can
 * narrow or override the component-level configurable props and
 * token consumption. */
export interface VariantDeclaration {
  name: string
  displayLabel?: string
  description?: string
  /** Per-variant overrides for configurable props. Keys must be
   * a subset of the component-level `configurableProps`. */
  configurableProps?: Record<string, ConfigPropSchema>
  /** Tokens this variant additionally consumes (additive to the
   * component-level `consumedTokens` list). */
  additionalConsumedTokens?: string[]
}


// ─── Token consumption ───────────────────────────────────────────

/** Map of tokens this component allows being overridden at the
 * instance level (via the editor). Keys are arbitrary editor-
 * facing labels; values are the actual underlying token names
 * the override targets. Future phases use this to scope which
 * tokens the editor exposes per component. */
export type TokenOverrideMap = Record<string, string>


// ─── Registration metadata ───────────────────────────────────────

/** The full payload a component supplies when registering. Stored
 * frozen in the registry. */
export interface RegistrationMetadata {
  // Identity ────
  type: ComponentKind
  /** Unique within `type`. Validated at registration time. */
  name: string
  displayName: string
  description?: string
  /** Optional grouping label. The editor groups components by
   * category for browsing ("data display", "input", "navigation"). */
  category?: string

  // Scope ────
  verticals: VerticalScope[]
  userParadigms: UserParadigm[]
  /** Optional product-line gates (e.g., `["urns"]` for urn-only
   * widgets). Empty array means "no product-line gating". */
  productLines?: string[]

  // Token consumption ────
  /** Token names this component reads from. Names match
   * `tokens.css` variable names with the leading `--` stripped.
   * Used by the inverse-lookup query (`getComponentsConsumingToken`). */
  consumedTokens: string[]
  /** Optional per-instance override slots. The editor exposes
   * these in the visual editor; runtime applies them via
   * style overrides (Phase 2+). */
  tokenOverrides?: TokenOverrideMap

  // Configuration schema ────
  configurableProps?: Record<string, ConfigPropSchema>

  // Composition ────
  slots?: SlotDeclaration[]

  // Variants ────
  variants?: VariantDeclaration[]

  // Versioning ────
  /** Schema version of this metadata payload. Phase 1 components
   * register at `REGISTRY_SCHEMA_VERSION`. The registry stores it
   * verbatim so future migrations can target older registrations. */
  schemaVersion: number
  /** Component implementation version. Increment when the
   * runtime behavior or visible output changes in a non-additive
   * way. Used by editor change-tracking + deprecation flows. */
  componentVersion: number

  // Forward-compat ────
  /** Arbitrary additional metadata. Future categories (data
   * binding, event emission, permission gates, accessibility
   * declarations, etc.) land here without bumping the schema
   * version, so long as they're additive. */
  extensions?: Record<string, unknown>
}

/** Frozen, registry-stored shape returned by introspection. The
 * `component` field is the React component itself (kept on the
 * record so the editor can mount previews without a separate
 * lookup table). */
export interface RegistryEntry {
  metadata: Readonly<RegistrationMetadata>
  /** The React component that the registration wraps. Typed as
   * `ComponentType<unknown>` because the registry doesn't know the
   * component's prop shape at the type level — the
   * `registerComponent` HOC enforces shape locally at the
   * registration site. */
  component: ComponentType<unknown>
  /** Wall-clock timestamp of the most recent registration. Hot-
   * reload re-registrations refresh this. */
  registeredAt: number
}

/** Composite key used internally by the registry. Exposed for
 * tests and the introspection API. */
export interface RegistryKey {
  type: ComponentKind
  name: string
}


// ─── Configurable-prop value type extraction ─────────────────────

/** Helpers that let `registerComponent` enforce that the
 * configured component receives its declared props at the right
 * type. Best-effort — TypeScript can't fully narrow `enum` bounds
 * to literal-union types without const assertions, but
 * `boolean` / `number` / `string` are tight. */
export type ResolveConfigPropValue<S extends ConfigPropSchema> =
  S["type"] extends "boolean" ? boolean
    : S["type"] extends "number" ? number
      : S["type"] extends "string" ? string
        : S["type"] extends "enum" ? S["default"] extends infer D ? D : string
          : S["type"] extends "tokenReference" ? string
            : S["type"] extends "componentReference" ? string
              : S["type"] extends "array" ? unknown[]
                : S["type"] extends "object" ? Record<string, unknown>
                  : unknown

export type ResolveConfigurableProps<
  P extends Record<string, ConfigPropSchema> | undefined,
> = P extends Record<string, ConfigPropSchema>
  ? { [K in keyof P]: ResolveConfigPropValue<P[K]> }
  : Record<string, never>
