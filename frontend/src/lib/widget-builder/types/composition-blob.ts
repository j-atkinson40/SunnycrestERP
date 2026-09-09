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
  /** WB-8 Lock 6a — variant_id consumers render when no explicit
   *  variantId is passed. When undefined/null, consumers fall through
   *  to `variants[0]?.variant_id` then to undefined ("all atoms").
   *  Backend validator enforces referential integrity at write time:
   *  when set, it MUST equal a variant_id in `variants[]`. */
  default_variant_id?: string | null;
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

// WB-4b — shared semantic vocab matching runtime atom renderers.
export type TypographyVariant =
  | "body"
  | "body-sm"
  | "caption"
  | "label"
  | "heading-1"
  | "heading-2"
  | "heading-3"
  | "mono"
  | "serif";

export type SemanticColor =
  | "default"
  | "muted"
  | "subtle"
  | "accent"
  | "success"
  | "warning"
  | "danger";

export type SemanticAlign = "start" | "center" | "end";
export type AlignmentFour = "start" | "center" | "end" | "stretch";

export type IconSizeToken = "xs" | "sm" | "md" | "lg" | "xl";

export interface TextLabelConfig {
  // WB-4b runtime fields.
  text?: string;
  variant?: TypographyVariant;
  alignment?: SemanticAlign;
  color?: SemanticColor;
  max_lines?: number;
  // Legacy WB-1 fields retained for back-compat.
  typography_token?: string;
  align?: TextAlign;
}

export interface ValueDisplayConfig {
  format: NumberFormat;
  format_config: Record<string, unknown>;
  // WB-4b runtime fields.
  variant?: TypographyVariant;
  alignment?: SemanticAlign;
  color?: SemanticColor;
  placeholder?: string;
  binding_id?: string; // WB-6 binding picker placeholder
  // Legacy WB-1 fields.
  typography_token?: string;
  align?: TextAlign;
}

export interface IconConfig {
  icon_name: string;
  size_token?: IconSizeToken;
  // WB-4b — semantic color + stroke_width.
  stroke_width?: number;
  color?: SemanticColor;
  // Legacy WB-1 field.
  color_token?: string;
}

export type StatusBadgeVariant =
  | "neutral"
  | "success"
  | "warning"
  | "danger"
  | "info";

export interface StatusBadgeConfig {
  // WB-4b runtime fields.
  label?: string;
  variant?: StatusBadgeVariant;
  icon_name?: string;
  status_map: Record<string, string>;
  show_icon: boolean;
  typography_token?: string;
}

export type DividerOrientation = "horizontal" | "vertical";
export type DividerSpacing = "compact" | "normal" | "loose";
export type DividerColor = "subtle" | "normal";

export interface DividerConfig {
  orientation: DividerOrientation;
  // WB-4b semantic enums.
  spacing?: DividerSpacing;
  color?: DividerColor;
  // Legacy WB-1 field.
  spacing_token?: string;
}

export type ButtonActionKind =
  | "navigate"
  | "open_focus"
  | "open_peek"
  | "mutate"
  | "trigger_workflow";

// WB-4b — extended button variant vocab (adds destructive).
export type ButtonVariant =
  | "primary"
  | "secondary"
  | "ghost"
  | "destructive";

export type ButtonSize = "sm" | "md" | "lg";


// ── WB-7 ActionRef substrate (Area 2 Lock 2a discriminated union) ──
//
// TypeScript mirror of `backend/app/schemas/widget_composition.py`
// ActionRef + ParameterBindingRef shapes. Field names + Literal values
// match exactly per WB-7 Area 2 + Area 6 cross-side symmetry canon.

export type ParameterBindingSource =
  | "literal"
  | "static"
  | "route_param"
  | "query_param"
  | "focus_context"
  | "tenant_context"
  | "operator_context"
  | "current_row";

export interface ParameterBindingRef {
  name: string;
  source: ParameterBindingSource;
  /** literal source — direct value. */
  value?: unknown;
  /** static source — alias for literal (distinct for picker UX). */
  static_value?: unknown;
  /** route_param / query_param — URL param name. */
  param_name?: string;
  /** focus_context / tenant_context / operator_context — field selector. */
  field_name?: string;
  /** current_row — dotted access into the row dict. */
  row_field?: string;
}

interface _ActionRefBase {
  confirm_before?: boolean;
  confirm_copy?: string;
}

export interface NavigateActionRef extends _ActionRefBase {
  action_kind: "navigate";
  href: string;
  href_binding?: ParameterBindingRef;
  params?: ParameterBindingRef[];
}

export interface OpenFocusActionRef extends _ActionRefBase {
  action_kind: "open_focus";
  focus_template_slug: string;
  initial_context?: ParameterBindingRef[];
}

export type PeekViewType =
  | "fh_case"
  | "invoice"
  | "sales_order"
  | "task"
  | "contact"
  | "saved_view";

export interface OpenPeekActionRef extends _ActionRefBase {
  action_kind: "open_peek";
  peek_view_type: PeekViewType;
  initial_context?: ParameterBindingRef[];
}

export interface TriggerWorkflowActionRef extends _ActionRefBase {
  action_kind: "trigger_workflow";
  workflow_slug: string;
  workflow_input?: ParameterBindingRef[];
}

export type MutateKind = "anomaly_acknowledge";

export interface MutateActionRef extends _ActionRefBase {
  action_kind: "mutate";
  mutate_kind: MutateKind;
  target_id_binding: ParameterBindingRef;
}

/** Discriminated union per WB-7 Area 2 Lock 2a — TypeScript narrows
 *  on `action_kind` at consumer sites (ActionPicker, action-lift,
 *  validators). */
export type ActionRef =
  | NavigateActionRef
  | OpenFocusActionRef
  | OpenPeekActionRef
  | TriggerWorkflowActionRef
  | MutateActionRef;

export interface ButtonConfig {
  // WB-4b runtime fields.
  label?: string;
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon_name?: string;
  action_kind: ButtonActionKind;
  action_config: Record<string, unknown>;
  /** WB-7 — new discriminated-union ActionRef. When present, the
   *  runtime dispatcher consumes this field. `action_kind` +
   *  `action_config` remain for backward-compat reads of pre-WB-7
   *  blobs but operators author via this field. */
  action?: ActionRef;
  /** WB-7 — RETIRED. The forward-compat string slot was never
   *  populated in production. Typed as `never` so any new author code
   *  that attempts to assign a string surfaces a compile error;
   *  legacy persisted values parsed as undefined via the codec's
   *  permissive read pattern. */
  action_ref?: never;
  // Forward-compat alias key.
  variantVocab?: ButtonVariant;
}

export type ImageSourceKind = "url" | "vault_asset";
export type ImageFit = "cover" | "contain" | "fill";
export type ImageAspectRatioToken = "square" | "video" | "portrait" | "auto";
export type ImageObjectFit = "cover" | "contain";

export interface ImageConfig {
  source_kind: ImageSourceKind;
  // WB-4b runtime fields.
  src?: string;
  alt?: string;
  aspect_ratio_token?: ImageAspectRatioToken;
  object_fit?: ImageObjectFit;
  fallback_icon_name?: string;
  // Legacy WB-1 fields.
  fit?: ImageFit;
  aspect_ratio?: string;
}

export type ConditionalContainerDirection = "row" | "column";
export type ConditionalContainerSpacing = "compact" | "normal" | "loose";

export interface ConditionalContainerConfig {
  direction: ConditionalContainerDirection;
  gap_token?: string;
  // WB-4b — Surprise-1 schema extension + spacing semantic alias.
  spacing?: ConditionalContainerSpacing;
  alignment?: AlignmentFour;
  condition_binding_id?: string; // WB-7 placeholder
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
