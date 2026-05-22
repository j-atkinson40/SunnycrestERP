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

import { useCallback, useRef, useState, type ReactNode } from "react"
import { useNavigate, useParams, useSearchParams } from "react-router-dom"
import { toast } from "sonner"
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

import { useAuthOptional } from "@/contexts/auth-context"
import { useFocusOptional } from "@/contexts/focus-context"
import { usePeekOptional } from "@/contexts/peek-context"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button as UIButton } from "@/components/ui/button"
import { dispatchAction } from "@/lib/runtime-host/buttons/action-dispatch"
import {
  resolveBindings,
  type BindingContext,
} from "@/lib/runtime-host/buttons/parameter-resolver"
import type {
  ParameterBinding,
  R4ActionType,
} from "@/lib/runtime-host/buttons/types"

import type {
  AtomNode,
  ActionRef,
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
  /** WB-7 — render-time data context. Propagated by AtomRenderer
   *  per Area 6 Lock 6b. Atoms that don't need it (the existing 8
   *  leaves) ignore the prop; ButtonRenderer reads it for action
   *  context (per-row dict when inside a repeater). The shape is
   *  intentionally `unknown` so leaf atoms aren't tightly coupled to
   *  WB-5's 3-flavor discriminator — ButtonRenderer narrows as needed.
   */
  dataContext?: unknown
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

// ── WB-7 ActionRef lifting ─────────────────────────────────────────
//
// Lift a composition-blob ActionRef into the R-4 dispatch contract per
// WB-7 Area 3 Lock 3a. Returns the ActionType + ActionConfig + the
// parameter binding list to resolve at click-time.
//
// Lift target is the R-4 substrate at
// `frontend/src/lib/runtime-host/buttons/{types.ts,action-dispatch.ts,
// parameter-resolver.ts}` — consumed verbatim for the 3 overlapping
// verbs (navigate / open_focus / trigger_workflow) and extended for
// the 2 WB-7 additions (open_peek / mutate).

interface LiftedAction {
  actionType: R4ActionType
  // Match the R-4 ActionConfig surface — keys not under the active
  // type are ignored at dispatch time.
  actionConfig: {
    route?: string
    focusId?: string
    peekEntityType?: string
    workflowId?: string
    mutateKind?: string
  }
  bindings: ParameterBinding[]
  confirmBeforeFire: boolean
  confirmCopy?: string
}

const WB_TO_R4_SOURCE_MAP: Record<string, ParameterBinding["source"]> = {
  literal: "literal",
  static: "literal",
  route_param: "current_route_param",
  query_param: "current_query_param",
  focus_context: "current_focus_id",
  tenant_context: "current_tenant",
  operator_context: "current_user",
  current_row: "current_row",
}

function liftParameterBinding(
  binding: {
    name?: string
    source?: string
    value?: unknown
    static_value?: unknown
    param_name?: string
    field_name?: string
    row_field?: string
  },
  // Allow overriding the binding's `name` (used when lifting a
  // single-binding slot like target_id_binding or href_binding into
  // the resolved-params dict under a canonical key).
  forceName?: string,
): ParameterBinding | null {
  if (!binding.source) return null
  const r4Source = WB_TO_R4_SOURCE_MAP[binding.source]
  if (!r4Source) return null
  const out: ParameterBinding = {
    name: forceName ?? binding.name ?? "",
    source: r4Source,
  }
  if (binding.source === "literal" || binding.source === "static") {
    const v =
      binding.value !== undefined ? binding.value : binding.static_value
    if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") {
      out.value = v
    }
  } else if (binding.source === "route_param" || binding.source === "query_param") {
    out.paramName = binding.param_name
  } else if (
    binding.source === "tenant_context" ||
    binding.source === "operator_context"
  ) {
    // Map field_name → userField / tenantField when known. Fall through
    // to "id" default at resolve time when unset.
    const fname = binding.field_name
    if (
      fname === "id" ||
      fname === "email" ||
      fname === "role" ||
      fname === "slug" ||
      fname === "vertical"
    ) {
      if (binding.source === "operator_context") {
        out.userField = fname === "slug" || fname === "vertical"
          ? "id"  // unsupported on operator; fall back
          : (fname as "id" | "email" | "role")
      } else {
        out.tenantField = fname === "email" || fname === "role"
          ? "id"  // unsupported on tenant; fall back
          : (fname as "id" | "slug" | "vertical")
      }
    }
  } else if (binding.source === "current_row") {
    out.rowField = binding.row_field
  }
  return out
}


function liftCompositionBlobActionToR4(
  action: ActionRef,
): LiftedAction | null {
  const bindings: ParameterBinding[] = []
  switch (action.action_kind) {
    case "navigate": {
      if (action.href_binding) {
        // href_binding feeds into the URL via template substitution
        // under the binding's name. Operators may also use {x} tokens
        // in the literal href that resolve from `params`. Lift the
        // href_binding into the params list so substituteTemplate
        // can replace.
        const b = liftParameterBinding(action.href_binding)
        if (b) bindings.push(b)
      }
      for (const p of action.params ?? []) {
        const b = liftParameterBinding(p)
        if (b) bindings.push(b)
      }
      return {
        actionType: "navigate",
        actionConfig: { route: action.href },
        bindings,
        confirmBeforeFire: action.confirm_before === true,
        confirmCopy: action.confirm_copy,
      }
    }
    case "open_focus": {
      for (const p of action.initial_context ?? []) {
        const b = liftParameterBinding(p)
        if (b) bindings.push(b)
      }
      return {
        actionType: "open_focus",
        actionConfig: { focusId: action.focus_template_slug },
        bindings,
        confirmBeforeFire: action.confirm_before === true,
        confirmCopy: action.confirm_copy,
      }
    }
    case "open_peek": {
      for (const p of action.initial_context ?? []) {
        const b = liftParameterBinding(p)
        if (b) bindings.push(b)
      }
      return {
        actionType: "open_peek",
        actionConfig: { peekEntityType: action.peek_view_type },
        bindings,
        confirmBeforeFire: action.confirm_before === true,
        confirmCopy: action.confirm_copy,
      }
    }
    case "trigger_workflow": {
      for (const p of action.workflow_input ?? []) {
        const b = liftParameterBinding(p)
        if (b) bindings.push(b)
      }
      return {
        actionType: "trigger_workflow",
        actionConfig: { workflowId: action.workflow_slug },
        bindings,
        // Lock 5b — trigger_workflow defaults to confirm. The picker
        // sets confirm_before=true by default; runtime honors it.
        confirmBeforeFire: action.confirm_before !== false,
        confirmCopy: action.confirm_copy,
      }
    }
    case "mutate": {
      // mutate's target_id_binding is a single binding (not a list).
      // Lift it under the canonical resolved key `target_id` so the
      // mutate handler can read resolved["target_id"].
      const target = liftParameterBinding(
        action.target_id_binding,
        "target_id",
      )
      if (target) bindings.push(target)
      return {
        actionType: "mutate",
        actionConfig: { mutateKind: action.mutate_kind },
        bindings,
        // Lock 5b — mutate defaults to confirm.
        confirmBeforeFire: action.confirm_before !== false,
        confirmCopy: action.confirm_copy,
      }
    }
    default: {
      // Exhaustive guard — unknown verb in the discriminated union.
      const _exhaust: never = action
      void _exhaust
      return null
    }
  }
}


/** Extract row dict from `dataContext` when shaped per-row. Returns
 *  null for the canvas-preview map (top level), summary, or undefined
 *  contexts. Per WB-7 Lock 6b shape contract. */
function extractCurrentRow(
  dataContext: unknown,
): Record<string, unknown> | null {
  if (typeof dataContext !== "object" || dataContext === null) return null
  const ctx = dataContext as Record<string, unknown>
  if (ctx.__row === true) {
    // Strip discriminator + __index marker; keep the row dict.
    const out: Record<string, unknown> = { ...ctx }
    delete out.__row
    delete out.__index
    return out
  }
  return null
}


export function ButtonRenderer({
  atom,
  config,
  resolvedBindings,
  dataContext,
}: AtomRendererProps<
  ButtonConfig & {
    label?: string
    variantVocab?: ButtonVariantVocab
    icon_name?: string
    size?: ButtonSize
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

  // WB-7 — null-safe context hooks (R-4.0 R-5.0.3 / R-5.0.4 canonical
  // pattern). Admin-tree previews don't mount Focus / Peek / Auth
  // providers; the optional variants return null and the dispatcher
  // handlers (open_focus / open_peek) gracefully no-op via the
  // null-safe deps.
  const navigate = useNavigate()
  const focus = useFocusOptional()
  const peek = usePeekOptional()
  const auth = useAuthOptional()
  const user = auth?.user ?? null
  const company = auth?.company ?? null
  const routeParams = useParams()
  const [searchParams] = useSearchParams()

  // Confirm Dialog + click-during-loading scope.
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [pending, setPending] = useState(false)
  // AbortController separate from WB-4a auto-save + WB-5 canvas
  // preview per the Area 3 separation. Each new click during a
  // pending request supersedes the in-flight one (rare; defense).
  const abortRef = useRef<AbortController | null>(null)

  const handleFire = useCallback(async () => {
    if (!config?.action) return
    const lifted = liftCompositionBlobActionToR4(config.action)
    if (!lifted) return

    // Click-during-loading: supersede any in-flight request.
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
    }
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setPending(true)
    try {
      const ctx: BindingContext = {
        user: user
          ? {
              id: user.id,
              email: user.email,
              role: user.role_slug ?? null,
            }
          : null,
        tenant: company
          ? {
              id: company.id,
              slug: company.slug ?? null,
              vertical: company.vertical ?? null,
            }
          : null,
        nowMs: Date.now(),
        routeParams,
        queryParams: searchParams,
        currentFocusId: focus?.currentFocus?.id ?? null,
        currentRow: extractCurrentRow(dataContext),
      }
      const resolved = resolveBindings(lifted.bindings, ctx)
      const result = await dispatchAction(
        lifted.actionType,
        lifted.actionConfig,
        resolved,
        {
          navigate,
          openFocus: focus?.open ?? (() => undefined),
          openPeek: peek
            ? (args) =>
                peek.openPeek({
                  entityType: args.entityType as Parameters<
                    typeof peek.openPeek
                  >[0]["entityType"],
                  entityId: args.entityId,
                  triggerType: args.triggerType ?? "click",
                })
            : undefined,
          abortSignal: ctrl.signal,
        },
      )
      if (result.status === "error") {
        toast.error(result.errorMessage ?? "Action failed.")
      } else if (result.status === "success") {
        // Phase 1: silent success for navigate / open_focus / open_peek
        // (the UX feedback is the navigation / panel itself). mutate
        // surfaces a friendly toast; trigger_workflow surfaces a
        // "Workflow started" toast with the run id.
        if (lifted.actionType === "mutate") {
          toast.success("Done.")
        } else if (lifted.actionType === "trigger_workflow") {
          const runId = result.data?.run_id
          toast.success(
            runId ? `Workflow started (run ${runId})` : "Workflow started",
          )
        }
      }
      // "skipped" status (admin preview no-op) — silent.
    } finally {
      setPending(false)
      if (abortRef.current === ctrl) abortRef.current = null
    }
  }, [
    config?.action,
    user,
    company,
    routeParams,
    searchParams,
    focus,
    peek,
    navigate,
    dataContext,
  ])

  const handleClick = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation()
      if (!config?.action) {
        // Backward-compat: button atoms without an `action` field
        // (legacy WB-1..4 blobs or freshly-defaulted unwired buttons)
        // preserve the WB-3 no-op behavior.
        return
      }
      const lifted = liftCompositionBlobActionToR4(config.action)
      if (lifted?.confirmBeforeFire) {
        setConfirmOpen(true)
        return
      }
      void handleFire()
    },
    [config?.action, handleFire],
  )

  const liftedForConfirm =
    config?.action !== undefined
      ? liftCompositionBlobActionToR4(config.action)
      : null

  return (
    <>
      <button
        type="button"
        {...dataAttrs(atom)}
        data-action-kind={config?.action_kind ?? "navigate"}
        data-variant={variant}
        data-size={size}
        data-pending={pending ? "true" : undefined}
        disabled={pending}
        className={`inline-flex items-center gap-1.5 rounded-md border font-medium transition-colors focus-visible:outline-none focus-ring-accent ${BUTTON_VARIANT_CLASSES[variant]} ${BUTTON_SIZE_CLASSES[size]}`}
        onClick={handleClick}
      >
        {Lucide ? <Lucide width={14} height={14} strokeWidth={2.25} /> : null}
        <span>{label}</span>
      </button>
      {liftedForConfirm?.confirmBeforeFire ? (
        <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{label}</DialogTitle>
              <DialogDescription>
                {liftedForConfirm.confirmCopy ?? `Confirm: ${label}?`}
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <UIButton
                variant="outline"
                onClick={() => setConfirmOpen(false)}
                data-testid="wb-button-confirm-cancel"
              >
                Cancel
              </UIButton>
              <UIButton
                variant="default"
                onClick={async () => {
                  setConfirmOpen(false)
                  await handleFire()
                }}
                data-testid="wb-button-confirm-fire"
              >
                Confirm
              </UIButton>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      ) : null}
    </>
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

// Four-value alignment for container flex-cross-axis (matches WB-4b
// canonical AlignmentFour vocab).
const ALIGN_ITEMS: Record<"start" | "center" | "end" | "stretch", string> = {
  start: "items-start",
  center: "items-center",
  end: "items-end",
  stretch: "items-stretch",
}

export function ConditionalContainerRenderer({
  atom,
  config,
  children,
  resolvedBindings,
}: AtomRendererProps<
  ConditionalContainerConfig & {
    spacing?: ContainerSpacing
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
  const alignment =
    (config?.alignment as "start" | "center" | "end" | "stretch" | undefined) ??
    "start"
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
