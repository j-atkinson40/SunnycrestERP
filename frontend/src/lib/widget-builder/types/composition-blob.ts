/**
 * Widget composition blob TypeScript types (WB-1).
 *
 * Frontend mirror of `backend/app/schemas/widget_composition.py`.
 * Field names, enum values, optional/required discipline match
 * the Pydantic schemas exactly. Cross-side parity is load-bearing
 * for WB-2 through WB-8 — the Widget Builder authoring shell + the
 * `ComposedWidget` runtime renderer + the backend validator all
 * consume the same shape.
 *
 * Per investigation `docs/investigations/2026-05-21-widget-builder.md`
 * Area 7 (Q-30) for the canonical shape.
 *
 * NO LOGIC IN THIS FILE — types only. Defensive parsing +
 * deterministic serialization live in `../composition-blob-codec.ts`.
 */

// ── Atom-type vocabulary ─────────────────────────────────────────────

export type AtomType =
  | "text_label"
  | "value_display"
  | "icon"
  | "status_badge"
  | "divider"
  | "button"
  | "image"
  | "conditional_container"
  // WB-3 — repeater_atom for iteration-shaped widgets. Renders its
  // children once per row of an iterating BindingRef
  // (iteration_mode === 'per_row'). Phase 1 cross-container nesting
  // cap rejects repeater-inside-repeater.
  | "repeater_atom";

/**
 * Phase 1 set of atom_types that may carry children (Q-5 two-level
 * nesting cap; conditional_container + repeater_atom are the container
 * atoms in Phase 1 post-WB-3).
 */
export const CONTAINER_ATOM_TYPES: ReadonlySet<AtomType> = new Set([
  "conditional_container",
  "repeater_atom",
]);

// ── Variant + surface vocabulary ────────────────────────────────────

export type VariantId = "glance" | "brief" | "detail" | "deep";

export type TargetSurface =
  | "focus_canvas"
  | "page_canvas"
  | "palette_preview";

// ── Binding refs (Q-7) ──────────────────────────────────────────────

export type BindingType = "literal" | "field_path";
/** Phase 1 binding vocabulary. 'expression' deferred to WB-7. */

export type IterationMode = "per_row" | "single_summary" | "single_record";

export interface BindingRef {
  binding_id: string;
  binding_type: BindingType;
  /** Present when binding_type === 'literal'. */
  literal_value?: unknown;
  /** Present when binding_type === 'field_path'. */
  saved_view_id?: string;
  /** Present when binding_type === 'field_path'. */
  field_path?: string;
  /** Present when binding_type === 'field_path'. */
  iteration_mode?: IterationMode;
}

// ── Atom node ───────────────────────────────────────────────────────

export interface AtomNode {
  atom_id: string;
  atom_type: AtomType;
  config: Record<string, unknown>;
  /** Children only on container atoms (Phase 1: conditional_container). */
  children?: string[];
  /** When omitted, atom renders in every variant the widget supports. */
  visible_in_variants?: VariantId[];
  /** Maps logical prop name → binding_id in CompositionBlob.bindings_catalog. */
  binding_refs?: Record<string, string>;
}

// ── Variants ────────────────────────────────────────────────────────

export interface VariantDefinition {
  variant_id: string;
  variant_name: string;
  target_surface: TargetSurface;
  canonical_dimensions?: { width: number; height: number };
}

// ── Top-level composition blob ──────────────────────────────────────

export interface CompositionBlob {
  schema_version: 1;
  root_atom_id: string;
  atom_tree: Record<string, AtomNode>;
  variants: VariantDefinition[];
  bindings_catalog: Record<string, BindingRef>;
}

// ── Per-atom-type Phase 1 config shapes ─────────────────────────────
//
// These mirror the Pydantic Config classes at
// backend/app/schemas/widget_composition.py. AtomNode.config is typed
// as Record<string, unknown> for forward-compat; consumers wanting
// type-safe per-atom config narrow via these interfaces.

export type NumberFormat =
  | "number"
  | "currency"
  | "percent"
  | "date"
  | "duration";

export type TextAlign = "left" | "center" | "right";

export interface TextLabelConfig {
  typography_token?: string;
  align?: TextAlign;
  max_lines?: number;
}

export interface ValueDisplayConfig {
  format: NumberFormat;
  format_config: Record<string, unknown>;
  typography_token?: string;
  align?: TextAlign;
}

export type IconSizeToken = "xs" | "sm" | "md" | "lg";

export interface IconConfig {
  icon_name: string;
  size_token?: IconSizeToken;
  color_token?: string;
}

export interface StatusBadgeConfig {
  status_map: Record<string, string>;
  show_icon: boolean;
  typography_token?: string;
}

export type DividerOrientation = "horizontal" | "vertical";

export interface DividerConfig {
  orientation: DividerOrientation;
  spacing_token?: string;
}

export type ButtonActionKind =
  | "navigate"
  | "open_focus"
  | "open_peek"
  | "mutate"
  | "trigger_workflow";

export type ButtonVariant = "primary" | "secondary" | "ghost";

export interface ButtonConfig {
  action_kind: ButtonActionKind;
  action_config: Record<string, unknown>;
  variant?: ButtonVariant;
}

export type ImageSourceKind = "url" | "vault_asset";
export type ImageFit = "cover" | "contain" | "fill";

export interface ImageConfig {
  source_kind: ImageSourceKind;
  fit: ImageFit;
  aspect_ratio?: string;
}

export type ConditionalContainerDirection = "row" | "column";

export interface ConditionalContainerConfig {
  direction: ConditionalContainerDirection;
  gap_token?: string;
}

export type RepeaterDirection = "row" | "column";
export type RepeaterSpacing = "compact" | "normal" | "loose";

/** WB-3 — RepeaterAtomConfig. Iteration primitive for list-shaped
 *  composed widgets. `binding_id` references a BindingRef in
 *  bindings_catalog with binding_type='field_path' + iteration_mode='per_row'.
 *  `children` is the ordered list of atom_ids rendered once per row;
 *  the same list MUST appear on AtomNode.children for tree-walking
 *  parity (codec + backend validator both enforce). */
export interface RepeaterAtomConfig {
  binding_id: string;
  children: string[];
  direction?: RepeaterDirection;
  spacing?: RepeaterSpacing;
  empty_state?: string;
  max_rows?: number;
}

/**
 * Lookup of atom_type → human label (Phase 1). Used by the WB-2
 * atom palette + atom inspector. NOT used by the runtime renderer.
 */
export const ATOM_TYPE_LABELS: Record<AtomType, string> = {
  text_label: "Text label",
  value_display: "Value",
  icon: "Icon",
  status_badge: "Status badge",
  divider: "Divider",
  button: "Button",
  image: "Image",
  conditional_container: "Conditional container",
  repeater_atom: "Repeater",
};
