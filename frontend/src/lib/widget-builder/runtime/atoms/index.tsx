/**
 * WB-2 Phase 1 atom renderer placeholders.
 *
 * Eight semantic-HTML renderers — one per atom_type in the Phase 1
 * vocabulary (text_label, value_display, icon, status_badge, divider,
 * button, image, conditional_container). Each emits `data-atom-type`
 * + `data-atom-id` attributes so integration tests + the runtime
 * editor's selection overlay can identify the rendered atom.
 *
 * Placeholder UI ONLY. WB-3 swaps in real typography/theme/icon UI
 * driven by per-atom config. The component interface (the
 * `AtomRendererProps<TConfig>` shape) stays stable across WB-2 → WB-3
 * so AtomRenderer's dispatch doesn't change when real UI lands.
 *
 * No accessibility refinement (real ARIA semantics land in WB-3 with
 * real UI). No registerComponent wrapping on leaf atoms — they render
 * inside ComposedWidget's hit-testable inner-div per Area 6
 * dual-wrapping lock. ConditionalContainer DOES get its own
 * registerComponent wrap (the only Phase 1 atom with children), but
 * AtomRenderer applies that wrap at dispatch time, not here.
 */

import { type ReactNode } from "react"

import type {
  AtomNode,
  ButtonConfig,
  ConditionalContainerConfig,
  DividerConfig,
  IconConfig,
  ImageConfig,
  StatusBadgeConfig,
  TextLabelConfig,
  ValueDisplayConfig,
} from "../../types/composition-blob"


/** Common props passed to every atom renderer. */
export interface AtomRendererProps<TConfig> {
  atom: AtomNode
  config: TConfig
  /** Resolved binding values keyed by config field name (e.g.
   *  `{ text: "Hello", value: 42 }`). Phase 1: AtomRenderer builds
   *  via resolveBinding; renderers may use or ignore. */
  resolvedBindings: Record<string, unknown>
  /** Children renders, populated only for container atoms (Phase 1:
   *  conditional_container). AtomRenderer recursively builds + passes
   *  these so the leaf renderer doesn't reach back into the atom_tree. */
  children?: ReactNode
}


function dataAttrs(atom: AtomNode): Record<string, string> {
  return {
    "data-atom-type": atom.atom_type,
    "data-atom-id": atom.atom_id,
  }
}


// ── text_label ──────────────────────────────────────────────────────

export function TextLabelRenderer({
  atom,
  config,
  resolvedBindings,
}: AtomRendererProps<TextLabelConfig>) {
  // Phase 1: prefer a resolved binding under "text"; fall back to a
  // static config.text passthrough (WB-1 schema doesn't declare
  // config.text — but tests + early WB-3 prototypes may use a static
  // value for placeholder content); final fallback is a deterministic
  // marker so the layout space is preserved in regressions.
  const bound = resolvedBindings.text
  const staticText = (config as TextLabelConfig & { text?: unknown }).text
  const text =
    typeof bound === "string"
      ? bound
      : typeof staticText === "string"
        ? staticText
        : "Text label"
  return <span {...dataAttrs(atom)}>{text}</span>
}


// ── value_display ───────────────────────────────────────────────────

export function ValueDisplayRenderer({
  atom,
  config,
  resolvedBindings,
}: AtomRendererProps<ValueDisplayConfig>) {
  // Phase 1: surface the bound value if any, else show the format
  // marker so authors see the slot is wired but unbound.
  const bound = resolvedBindings.value
  if (bound !== undefined && bound !== null) {
    return <span {...dataAttrs(atom)}>{String(bound)}</span>
  }
  return <span {...dataAttrs(atom)}>{`[${config?.format ?? "value"}]`}</span>
}


// ── icon ────────────────────────────────────────────────────────────

export function IconRenderer({
  atom,
  config,
}: AtomRendererProps<IconConfig>) {
  // icon_name is required per WB-1's IconConfig — codec rejects atoms
  // missing it. Defensive throw here catches direct construction
  // (tests, future bypass) per investigation Area 1 guidance.
  if (!config?.icon_name) {
    throw new Error(
      `[IconRenderer] atom ${atom.atom_id} missing required config.icon_name`,
    )
  }
  return <span {...dataAttrs(atom)}>{`[icon:${config.icon_name}]`}</span>
}


// ── status_badge ────────────────────────────────────────────────────

export function StatusBadgeRenderer({
  atom,
  resolvedBindings,
}: AtomRendererProps<StatusBadgeConfig>) {
  const status = resolvedBindings.status
  const text =
    typeof status === "string" ? `[badge:${status}]` : "[badge]"
  return <span {...dataAttrs(atom)}>{text}</span>
}


// ── divider ─────────────────────────────────────────────────────────

export function DividerRenderer({
  atom,
  config,
}: AtomRendererProps<DividerConfig>) {
  // Use a single <hr> regardless of orientation in Phase 1.
  // WB-3 ships orientation-aware visual treatment.
  return (
    <hr
      {...dataAttrs(atom)}
      data-orientation={config?.orientation ?? "horizontal"}
    />
  )
}


// ── button ──────────────────────────────────────────────────────────

export function ButtonRenderer({
  atom,
  config,
  resolvedBindings,
}: AtomRendererProps<ButtonConfig>) {
  // Phase 1 placeholder: onClick is a no-op. WB-7 wires actual action
  // dispatch (navigate, open_focus, open_peek, mutate, trigger_workflow).
  const bound = resolvedBindings.label
  const staticLabel = (config as ButtonConfig & { label?: unknown }).label
  const label =
    typeof bound === "string"
      ? bound
      : typeof staticLabel === "string"
        ? staticLabel
        : "[button]"
  return (
    <button
      type="button"
      {...dataAttrs(atom)}
      data-action-kind={config?.action_kind ?? "navigate"}
      onClick={() => {
        // WB-7: dispatch config.action_kind + action_config.
      }}
    >
      {label}
    </button>
  )
}


// ── image ───────────────────────────────────────────────────────────

export function ImageRenderer({
  atom,
  config,
}: AtomRendererProps<ImageConfig>) {
  // Phase 1: no <img src> yet — image source resolution depends on
  // vault_asset lookup + URL-binding which WB-6 / WB-7 wire. Placeholder
  // span keeps the atom present + introspectable in the DOM.
  return (
    <span
      {...dataAttrs(atom)}
      data-source-kind={config?.source_kind ?? "url"}
    >
      [image]
    </span>
  )
}


// ── conditional_container ───────────────────────────────────────────

export function ConditionalContainerRenderer({
  atom,
  config,
  children,
}: AtomRendererProps<ConditionalContainerConfig>) {
  // Only container atom in Phase 1. AtomRenderer recursively builds
  // child ReactNodes + passes via the `children` prop.
  return (
    <div
      {...dataAttrs(atom)}
      data-direction={config?.direction ?? "row"}
    >
      {children}
    </div>
  )
}
