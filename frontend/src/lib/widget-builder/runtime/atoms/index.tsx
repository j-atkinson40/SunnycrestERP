/**
 * WB-3 production atom renderers (Phase 1).
 *
 * Replaces the WB-2 placeholders with theme-token-driven UI per
 * DESIGN_LANGUAGE.md typography + theme integration (IBM Plex Sans
 * body / IBM Plex Serif editorial / IBM Plex Mono technical; warm
 * surface tokens; brass accent discipline). Each renderer consumes
 * `var(--<token>)` exclusively for colors / shadows / borders — NO
 * hardcoded hex values.
 *
 * The 9-atom Phase 1 catalog:
 *   - text_label, value_display, icon, status_badge, divider, button,
 *     image, conditional_container (existing 8 from WB-2)
 *   - repeater_atom (NEW in WB-3 — iteration primitive)
 *
 * Per investigation Area 6 dual-wrapping lock: leaf atoms render
 * without their own registerComponent wrap (ComposedWidget's
 * inner-div is the single hit-test surface). conditional_container
 * AND repeater_atom DO each get a registerComponent wrap, applied at
 * AtomRenderer dispatch time (not here).
 *
 * Each renderer:
 *   - Consumes typed config per WB-1 schema + WB-3 enrichments
 *   - Renders semantic HTML
 *   - Emits `data-atom-type` + `data-atom-id` attributes for
 *     click-to-select + test ids
 *   - Handles missing/empty config gracefully (Phase 1 empty-dict
 *     acceptable; sensible defaults)
 *
 * Behavior pending future phases:
 *   - Button onClick is a no-op (WB-7 wires action dispatch)
 *   - Image src resolution is a placeholder (WB-6 wires vault-asset +
 *     URL-binding resolution)
 *   - Repeater iteration data is a 1-row placeholder (WB-6 wires
 *     real saved-view row projection)
 */

import { type ReactNode } from "react"
import {
  Check,
  ChevronRight,
  Circle,
  Image as ImageIcon,
  Info,
  AlertTriangle,
  AlertCircle,
  ListChecks,
  Layers,
  Plus,
  Minus,
  X,
  type LucideIcon,
} from "lucide-react"

import type {
  AtomNode,
  ButtonConfig,
  ConditionalContainerConfig,
  DividerConfig,
  IconConfig,
  ImageConfig,
  RepeaterAtomConfig,
  StatusBadgeConfig,
  TextLabelConfig,
  ValueDisplayConfig,
} from "../../types/composition-blob"


/** Common props passed to every atom renderer. */
export interface AtomRendererProps<TConfig> {
  atom: AtomNode
  config: TConfig
  /** Resolved binding values keyed by config field name. */
  resolvedBindings: Record<string, unknown>
  /** Children renders, populated only for container atoms
   *  (conditional_container, repeater_atom). */
  children?: ReactNode
}


function dataAttrs(atom: AtomNode): Record<string, string> {
  return {
    "data-atom-type": atom.atom_type,
    "data-atom-id": atom.atom_id,
  }
}


// ── Typography mapping per DESIGN_LANGUAGE.md ───────────────────────

type TypographyVariant =
  | "body"
  | "body-sm"
  | "caption"
  | "label"
  | "heading-1"
  | "heading-2"
  | "heading-3"
  | "mono"
  | "serif"

const TYPOGRAPHY_CLASSES: Record<TypographyVariant, string> = {
  body: "text-body font-normal",
  "body-sm": "text-body-sm font-normal",
  caption: "text-caption font-normal",
  label: "text-body-sm font-medium",
  "heading-1": "text-h1 font-medium",
  "heading-2": "text-h2 font-medium",
  "heading-3": "text-h3 font-medium",
  mono: "text-body-sm font-plex-mono",
  serif: "text-body font-plex-serif",
}

function typographyClass(variant: TypographyVariant | undefined): string {
  return TYPOGRAPHY_CLASSES[variant ?? "body"]
}


type SemanticColor =
  | "default"
  | "muted"
  | "subtle"
  | "accent"
  | "success"
  | "warning"
  | "danger"

const COLOR_CLASSES: Record<SemanticColor, string> = {
  default: "text-content-base",
  muted: "text-content-muted",
  subtle: "text-content-subtle",
  accent: "text-[color:var(--accent)]",
  success: "text-status-success",
  warning: "text-status-warning",
  danger: "text-status-error",
}

function colorClass(color: SemanticColor | undefined): string {
  return COLOR_CLASSES[color ?? "default"]
}


type SemanticAlign = "start" | "center" | "end"

const ALIGN_CLASSES: Record<SemanticAlign, string> = {
  start: "text-left",
  center: "text-center",
  end: "text-right",
}

function alignClass(align: SemanticAlign | undefined): string {
  return ALIGN_CLASSES[align ?? "start"]
}


// ── Lucide icon resolution ──────────────────────────────────────────

const ICON_MAP: Record<string, LucideIcon> = {
  check: Check,
  "chevron-right": ChevronRight,
  circle: Circle,
  image: ImageIcon,
  info: Info,
  warning: AlertTriangle,
  "alert-triangle": AlertTriangle,
  "alert-circle": AlertCircle,
  "list-checks": ListChecks,
  layers: Layers,
  plus: Plus,
  minus: Minus,
  x: X,
}

function resolveIcon(name: string | undefined): LucideIcon {
  if (!name) return Layers
  return ICON_MAP[name] ?? Layers
}


const ICON_SIZE_PX: Record<string, number> = {
  xs: 12,
  sm: 16,
  md: 20,
  lg: 24,
  xl: 32,
}

function iconSizePx(size: string | undefined): number {
  return ICON_SIZE_PX[size ?? "md"] ?? 20
}


// ── text_label ──────────────────────────────────────────────────────

export function TextLabelRenderer({
  atom,
  config,
  resolvedBindings,
}: AtomRendererProps<
  TextLabelConfig & {
    text?: unknown
    variant?: TypographyVariant
    alignment?: SemanticAlign
    color?: SemanticColor
    max_lines?: number
  }
>) {
  const bound = resolvedBindings.text
  const staticText = config?.text
  const text =
    typeof bound === "string"
      ? bound
      : typeof staticText === "string"
        ? staticText
        : "Text label"
  const variant = (config?.variant as TypographyVariant | undefined) ?? "body"
  const align = (config?.alignment as SemanticAlign | undefined) ?? "start"
  const color = (config?.color as SemanticColor | undefined) ?? "default"
  const maxLines = config?.max_lines
  const style: React.CSSProperties | undefined =
    typeof maxLines === "number" && maxLines > 0
      ? {
          display: "-webkit-box",
          WebkitLineClamp: maxLines,
          WebkitBoxOrient: "vertical",
          overflow: "hidden",
        }
      : undefined
  return (
    <span
      {...dataAttrs(atom)}
      className={`${typographyClass(variant)} ${alignClass(align)} ${colorClass(color)}`}
      style={style}
    >
      {text}
    </span>
  )
}


// ── value_display ───────────────────────────────────────────────────

type ValueFormat =
  | "text"
  | "number"
  | "currency"
  | "percent"
  | "date"
  | "duration"
  | "relative-time"

function formatValue(
  raw: unknown,
  format: ValueFormat,
  formatConfig: Record<string, unknown> | undefined,
): string {
  if (raw === undefined || raw === null) return ""
  switch (format) {
    case "text":
      return String(raw)
    case "number": {
      const n = typeof raw === "number" ? raw : Number(raw)
      if (!Number.isFinite(n)) return String(raw)
      return new Intl.NumberFormat(undefined).format(n)
    }
    case "currency": {
      const n = typeof raw === "number" ? raw : Number(raw)
      if (!Number.isFinite(n)) return String(raw)
      const cc =
        (formatConfig?.currency_code as string | undefined) ?? "USD"
      try {
        return new Intl.NumberFormat(undefined, {
          style: "currency",
          currency: cc,
        }).format(n)
      } catch {
        return `${cc} ${n.toFixed(2)}`
      }
    }
    case "percent": {
      const n = typeof raw === "number" ? raw : Number(raw)
      if (!Number.isFinite(n)) return String(raw)
      return new Intl.NumberFormat(undefined, {
        style: "percent",
        maximumFractionDigits: 1,
      }).format(n)
    }
    case "date": {
      const d = raw instanceof Date ? raw : new Date(String(raw))
      if (Number.isNaN(d.getTime())) return String(raw)
      return new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
      }).format(d)
    }
    case "duration": {
      const ms = typeof raw === "number" ? raw : Number(raw)
      if (!Number.isFinite(ms)) return String(raw)
      const m = Math.floor(ms / 60000)
      const s = Math.floor((ms % 60000) / 1000)
      return `${m}m ${s}s`
    }
    case "relative-time": {
      const d = raw instanceof Date ? raw : new Date(String(raw))
      if (Number.isNaN(d.getTime())) return String(raw)
      const diffSec = Math.round((d.getTime() - Date.now()) / 1000)
      const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" })
      if (Math.abs(diffSec) < 60) return rtf.format(diffSec, "second")
      if (Math.abs(diffSec) < 3600) return rtf.format(Math.round(diffSec / 60), "minute")
      if (Math.abs(diffSec) < 86400) return rtf.format(Math.round(diffSec / 3600), "hour")
      return rtf.format(Math.round(diffSec / 86400), "day")
    }
    default:
      return String(raw)
  }
}

export function ValueDisplayRenderer({
  atom,
  config,
  resolvedBindings,
}: AtomRendererProps<
  ValueDisplayConfig & {
    variant?: TypographyVariant
    alignment?: SemanticAlign
    color?: SemanticColor
    placeholder?: string
  }
>) {
  const bound = resolvedBindings.value
  const variant = (config?.variant as TypographyVariant | undefined) ?? "body"
  const align = (config?.alignment as SemanticAlign | undefined) ?? "start"
  const color = (config?.color as SemanticColor | undefined) ?? "default"
  if (bound === undefined || bound === null || bound === "") {
    const placeholder = config?.placeholder ?? `[${config?.format ?? "value"}]`
    return (
      <span
        {...dataAttrs(atom)}
        className={`${typographyClass(variant)} ${alignClass(align)} ${colorClass("subtle")}`}
      >
        {placeholder}
      </span>
    )
  }
  const formatted = formatValue(
    bound,
    (config?.format as ValueFormat | undefined) ?? "text",
    config?.format_config,
  )
  return (
    <span
      {...dataAttrs(atom)}
      className={`${typographyClass(variant)} ${alignClass(align)} ${colorClass(color)}`}
    >
      {formatted}
    </span>
  )
}


// ── icon ────────────────────────────────────────────────────────────

export function IconRenderer({
  atom,
  config,
}: AtomRendererProps<
  IconConfig & {
    stroke_width?: number
    color?: SemanticColor
  }
>) {
  if (!config?.icon_name) {
    throw new Error(
      `[IconRenderer] atom ${atom.atom_id} missing required config.icon_name`,
    )
  }
  const Lucide = resolveIcon(config.icon_name)
  const size = iconSizePx(config.size_token)
  const stroke = config.stroke_width ?? 2
  const color = (config.color as SemanticColor | undefined) ?? "default"
  return (
    <span
      {...dataAttrs(atom)}
      className={`inline-flex items-center justify-center ${colorClass(color)}`}
      aria-hidden="true"
    >
      <Lucide
        width={size}
        height={size}
        strokeWidth={stroke}
        data-icon-name={config.icon_name}
      />
    </span>
  )
}


// ── status_badge ────────────────────────────────────────────────────

type StatusVariant = "neutral" | "success" | "warning" | "danger" | "info"

const STATUS_BG: Record<StatusVariant, string> = {
  neutral: "bg-surface-sunken text-content-base border-[color:var(--border-base)]",
  success: "bg-status-success-muted text-status-success border-status-success/30",
  warning: "bg-status-warning-muted text-status-warning border-status-warning/30",
  danger: "bg-status-error-muted text-status-error border-status-error/30",
  info: "bg-status-info-muted text-status-info border-status-info/30",
}

export function StatusBadgeRenderer({
  atom,
  config,
  resolvedBindings,
}: AtomRendererProps<
  StatusBadgeConfig & {
    label?: string
    variant?: StatusVariant
    icon_name?: string
  }
>) {
  const statusBound = resolvedBindings.status
  const labelBound = resolvedBindings.label
  // Variant resolution: explicit config.variant wins; else look up
  // status_map for the bound status value; else default 'neutral'.
  let variant: StatusVariant =
    (config?.variant as StatusVariant | undefined) ?? "neutral"
  if (
    config?.status_map &&
    typeof statusBound === "string" &&
    config.status_map[statusBound]
  ) {
    const mapped = config.status_map[statusBound] as StatusVariant
    if (["neutral", "success", "warning", "danger", "info"].includes(mapped)) {
      variant = mapped
    }
  }
  const label =
    (typeof labelBound === "string" ? labelBound : undefined) ??
    config?.label ??
    (typeof statusBound === "string" ? statusBound : "Status")
  const Lucide = config?.icon_name ? resolveIcon(config.icon_name) : null
  return (
    <span
      {...dataAttrs(atom)}
      data-variant={variant}
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 ${typographyClass("caption")} ${STATUS_BG[variant]}`}
    >
      {Lucide ? <Lucide width={12} height={12} strokeWidth={2.5} /> : null}
      <span>{label}</span>
    </span>
  )
}


// ── divider ─────────────────────────────────────────────────────────

type DividerSpacing = "compact" | "normal" | "loose"
type DividerColor = "subtle" | "normal"

const DIVIDER_MARGIN: Record<DividerSpacing, string> = {
  compact: "my-1",
  normal: "my-2",
  loose: "my-4",
}

const DIVIDER_COLOR: Record<DividerColor, string> = {
  subtle: "border-[color:var(--border-subtle)]",
  normal: "border-[color:var(--border-base)]",
}

export function DividerRenderer({
  atom,
  config,
}: AtomRendererProps<
  DividerConfig & {
    spacing?: DividerSpacing
    color?: DividerColor
  }
>) {
  const orient = config?.orientation ?? "horizontal"
  const spacing = (config?.spacing as DividerSpacing | undefined) ?? "normal"
  const color = (config?.color as DividerColor | undefined) ?? "subtle"
  if (orient === "vertical") {
    return (
      <div
        {...dataAttrs(atom)}
        role="separator"
        aria-orientation="vertical"
        data-orientation="vertical"
        className={`inline-block self-stretch border-l ${DIVIDER_COLOR[color]}`}
        style={{ width: 0 }}
      />
    )
  }
  return (
    <hr
      {...dataAttrs(atom)}
      data-orientation="horizontal"
      className={`border-0 border-t ${DIVIDER_COLOR[color]} ${DIVIDER_MARGIN[spacing]}`}
    />
  )
}


// ── button ──────────────────────────────────────────────────────────

type ButtonVariantVocab = "primary" | "secondary" | "ghost" | "destructive"
type ButtonSize = "sm" | "md" | "lg"

const BUTTON_VARIANT_CLASSES: Record<ButtonVariantVocab, string> = {
  primary:
    "bg-[color:var(--accent)] text-[color:var(--content-on-accent,var(--content-strong))] hover:bg-[color:var(--accent-hover)] border-transparent",
  secondary:
    "bg-surface-elevated text-content-strong border-[color:var(--border-base)] hover:bg-surface-raised",
  ghost:
    "bg-transparent text-content-base border-transparent hover:bg-surface-sunken",
  destructive:
    "bg-status-error text-white hover:opacity-90 border-transparent",
}

const BUTTON_SIZE_CLASSES: Record<ButtonSize, string> = {
  sm: "px-2.5 py-1 text-body-sm",
  md: "px-3 py-1.5 text-body-sm",
  lg: "px-4 py-2 text-body",
}

export function ButtonRenderer({
  atom,
  config,
  resolvedBindings,
}: AtomRendererProps<
  ButtonConfig & {
    label?: string
    variantVocab?: ButtonVariantVocab
    icon_name?: string
    size?: ButtonSize
    action_ref?: string
  }
>) {
  const bound = resolvedBindings.label
  const label =
    typeof bound === "string"
      ? bound
      : typeof config?.label === "string"
        ? config.label
        : "Button"
  // The WB-1 ButtonConfig.variant vocab is primary/secondary/ghost;
  // WB-3 also accepts "destructive". Map config.variant to the
  // broader vocab; fall back to "secondary".
  const variant: ButtonVariantVocab =
    (config?.variantVocab as ButtonVariantVocab | undefined) ??
    ((config?.variant as ButtonVariantVocab | undefined) ?? "secondary")
  const size: ButtonSize = (config?.size as ButtonSize | undefined) ?? "md"
  const Lucide = config?.icon_name ? resolveIcon(config.icon_name) : null
  return (
    <button
      type="button"
      {...dataAttrs(atom)}
      data-action-kind={config?.action_kind ?? "navigate"}
      data-variant={variant}
      data-size={size}
      className={`inline-flex items-center gap-1.5 rounded-md border font-medium transition-colors focus-visible:outline-none focus-ring-accent ${BUTTON_VARIANT_CLASSES[variant]} ${BUTTON_SIZE_CLASSES[size]}`}
      onClick={(e) => {
        e.stopPropagation()
        // WB-7: dispatch config.action_kind + action_config /
        // config.action_ref. No-op in Phase 1.
      }}
    >
      {Lucide ? <Lucide width={14} height={14} strokeWidth={2.25} /> : null}
      <span>{label}</span>
    </button>
  )
}


// ── image ───────────────────────────────────────────────────────────

type ImageAspect = "square" | "video" | "portrait" | "auto"

const ASPECT_CLASSES: Record<ImageAspect, string> = {
  square: "aspect-square",
  video: "aspect-video",
  portrait: "aspect-[3/4]",
  auto: "",
}

export function ImageRenderer({
  atom,
  config,
  resolvedBindings,
}: AtomRendererProps<
  ImageConfig & {
    src?: string
    alt?: string
    aspect_ratio_token?: ImageAspect
    object_fit?: "cover" | "contain"
    fallback_icon_name?: string
  }
>) {
  const boundSrc = resolvedBindings.src
  const src =
    typeof boundSrc === "string"
      ? boundSrc
      : typeof config?.src === "string"
        ? config.src
        : ""
  const alt = config?.alt ?? ""
  const aspect =
    (config?.aspect_ratio_token as ImageAspect | undefined) ?? "auto"
  const fit = config?.object_fit ?? "cover"
  const fallbackIconName = config?.fallback_icon_name ?? "image"
  if (!src) {
    const Lucide = resolveIcon(fallbackIconName)
    return (
      <div
        {...dataAttrs(atom)}
        data-source-kind={config?.source_kind ?? "url"}
        role="img"
        aria-label={alt || "image placeholder"}
        className={`flex items-center justify-center rounded-md bg-surface-sunken text-content-subtle ${ASPECT_CLASSES[aspect]}`}
        style={{ minHeight: aspect === "auto" ? 48 : undefined }}
      >
        <Lucide width={24} height={24} strokeWidth={1.5} />
      </div>
    )
  }
  return (
    <img
      {...dataAttrs(atom)}
      data-source-kind={config?.source_kind ?? "url"}
      src={src}
      alt={alt}
      className={`rounded-md ${ASPECT_CLASSES[aspect]}`}
      style={{
        objectFit: fit,
        width: "100%",
        height: aspect === "auto" ? "auto" : undefined,
      }}
    />
  )
}


// ── conditional_container ───────────────────────────────────────────

type ContainerSpacing = "compact" | "normal" | "loose"

const SPACING_GAP: Record<ContainerSpacing, string> = {
  compact: "gap-1",
  normal: "gap-2",
  loose: "gap-4",
}

const ALIGN_ITEMS: Record<SemanticAlign, string> = {
  start: "items-start",
  center: "items-center",
  end: "items-end",
}

export function ConditionalContainerRenderer({
  atom,
  config,
  children,
  resolvedBindings,
}: AtomRendererProps<
  ConditionalContainerConfig & {
    spacing?: ContainerSpacing
    alignment?: SemanticAlign
    condition_binding_id?: string
  }
>) {
  // Phase 1: when a condition binding is wired, the placeholder
  // resolver returns truthy/falsy via WB-2 semantics. WB-7 makes the
  // condition predicate real; today we render unconditionally when
  // no condition is wired or the resolved value is truthy.
  const cond = resolvedBindings.condition
  if (cond !== undefined && !cond) {
    return null
  }
  const direction = config?.direction ?? "row"
  const spacing = (config?.spacing as ContainerSpacing | undefined) ?? "normal"
  const alignment = (config?.alignment as SemanticAlign | undefined) ?? "start"
  return (
    <div
      {...dataAttrs(atom)}
      data-direction={direction}
      className={`flex ${direction === "row" ? "flex-row" : "flex-col"} ${SPACING_GAP[spacing]} ${ALIGN_ITEMS[alignment]}`}
    >
      {children}
    </div>
  )
}


// ── repeater_atom ───────────────────────────────────────────────────

const REPEATER_GAP: Record<ContainerSpacing, string> = {
  compact: "gap-1",
  normal: "gap-2",
  loose: "gap-3",
}

/** Repeater atom renderer (WB-3, NEW).
 *
 *  Iteration primitive for list-shaped composed widgets. The
 *  AtomRenderer dispatch builds `rowRenders` — an array of
 *  ReactNode arrays, one per row — and passes them via the
 *  `children` prop (each entry is one row's child atoms rendered
 *  with that row's dataContext).
 *
 *  Phase 1: WB-3 renders a single mock row when iteration data is
 *  not yet wired. The `children` array contains the per-row renders
 *  prepared by AtomRenderer. When `children` is empty / undefined,
 *  the empty_state copy renders (or a default placeholder).
 *
 *  Defensive nesting cap: at render time, throw if a descendant atom
 *  is also a repeater_atom — defense-in-depth alongside the
 *  Pydantic/codec validators. */
export function RepeaterAtomRenderer({
  atom,
  config,
  children,
}: AtomRendererProps<RepeaterAtomConfig & { children: string[] }>) {
  const direction = config?.direction ?? "column"
  const spacing = (config?.spacing as ContainerSpacing | undefined) ?? "normal"
  const emptyState = config?.empty_state

  // children is the array of per-row renders prepared by AtomRenderer.
  // Wrap in a flow container; per-row content is already a flex
  // group built by the dispatch path.
  const childArr = Array.isArray(children)
    ? children
    : children === undefined || children === null
      ? []
      : [children]

  if (childArr.length === 0) {
    return (
      <div
        {...dataAttrs(atom)}
        data-direction={direction}
        className={`flex ${direction === "row" ? "flex-row" : "flex-col"} items-start ${REPEATER_GAP[spacing]} ${typographyClass("caption")} ${colorClass("subtle")}`}
      >
        {emptyState ?? "No items"}
      </div>
    )
  }

  return (
    <div
      {...dataAttrs(atom)}
      data-direction={direction}
      data-row-count={childArr.length}
      className={`flex ${direction === "row" ? "flex-row" : "flex-col"} items-start ${REPEATER_GAP[spacing]}`}
    >
      {childArr}
    </div>
  )
}
