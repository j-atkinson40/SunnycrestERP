/**
 * ComposedWidget — WB-2 runtime renderer for composition_blob-driven
 * widgets.
 *
 * Single React component (NOT codegen) per investigation Area 5
 * "hybrid Model C" lock. Parses the WB-1 composition_blob via the
 * existing codec + recursively dispatches to atom renderers.
 *
 * Per Area 6 dual-wrapping lock:
 *   - Outer registerComponent wrap (display:contents) comes from
 *     class-registrations.ts when ComposedWidget is registered with
 *     the visual-editor registry as a widget kind. That wrap carries
 *     `data-component-name="composed"` so the runtime editor can
 *     identify ComposedWidget as a unit.
 *   - This component itself renders an inner `<div
 *     data-composed-widget-root>` — a real layout box that bypasses
 *     the display:contents hit-test cascade per hover-fix d9ffd90.
 *     All hit-testing for leaf atoms inside this widget resolves to
 *     this single box.
 *   - Container atoms (conditional_container) inside get THEIR own
 *     registerComponent wrap via AtomRenderer; leaf atoms render
 *     inside this widget's inner-div hit-test surface.
 *
 * Dispatch entry-point: callers with a WidgetDefinition row check
 * whether composition_blob is populated; populated → ComposedWidget;
 * null → existing widget_id registry path (hand-coded). See
 * `widget-renderer-dispatch.ts` for the dispatch helper.
 */

import { useMemo, type CSSProperties } from "react"

import type {
  CompositionBlob,
  VariantDefinition,
  VariantId,
} from "../types/composition-blob"
import { parseCompositionBlob } from "../composition-blob-codec"
import { surfaceDefaultDimensions } from "../types/surface-mapping"

import { AtomRenderer } from "./AtomRenderer"


/** Minimal subset of the WB-1-extended WidgetDefinition shape needed
 *  by ComposedWidget.
 *
 *  WB-3 — the canonical `components/widgets/types.ts::WidgetDefinition`
 *  interface now carries `composition_blob` + `composition_version` +
 *  `tier_scope` as additive optional fields. This local shape stays
 *  narrow on purpose: the renderer only needs `widget_id` + the blob,
 *  and the canonical WidgetDefinition is a structural superset that
 *  satisfies this contract without coercion. Callers passing a full
 *  canonical row through work unchanged. */
export interface ComposedWidgetInput {
  /** Required — used for the data-widget-id attribute on the inner
   *  layout box (telemetry + DOM identification). */
  widget_id: string
  /** Parsed CompositionBlob OR raw JSON-shaped blob. Parsing happens
   *  inside ComposedWidget so callers don't have to. Throwing the
   *  parse error in component-render is intentional: the dispatch
   *  helper should have routed unblobbed widgets elsewhere. */
  composition_blob: CompositionBlob | unknown
}


export interface ComposedWidgetProps {
  widgetDefinition: ComposedWidgetInput
  /** Which variant to render (glance / brief / detail / deep). When
   *  undefined, all atoms render regardless of visible_in_variants
   *  (catalog-preview / unscoped render). */
  variantId?: VariantId
  /** Reserved for WB-6 data binding wiring. Unused in Phase 1; kept
   *  on the public signature so consumer wiring (FF / Pulse /
   *  dashboard) can pass through without recoordination later. */
  dataContext?: unknown
}


export function ComposedWidget({
  widgetDefinition,
  variantId,
  dataContext,
}: ComposedWidgetProps) {
  if (
    widgetDefinition.composition_blob === null ||
    widgetDefinition.composition_blob === undefined
  ) {
    // Defensive: dispatch should have routed null-blob widgets to
    // the existing hand-coded path. Surfacing as a thrown error
    // lets QA see the mis-dispatch immediately rather than rendering
    // empty.
    throw new Error(
      `[ComposedWidget] widget_id=${widgetDefinition.widget_id} has no composition_blob — should have dispatched to hand-coded path.`,
    )
  }

  // Parse defensively. If the blob has already been parsed (i.e.
  // matches the CompositionBlob shape), parseCompositionBlob is
  // idempotent against a structurally-valid input. WB-1 codec throws
  // CompositionBlobParseError on malformed input.
  const blob = useMemo<CompositionBlob>(
    () => parseCompositionBlob(widgetDefinition.composition_blob),
    [widgetDefinition.composition_blob],
  )

  const rootAtom = blob.atom_tree[blob.root_atom_id]
  if (!rootAtom) {
    // Defensive: WB-1 backend validator catches missing root_atom_id
    // against atom_tree. At runtime, surface clearly.
    throw new Error(
      `[ComposedWidget] root_atom_id "${blob.root_atom_id}" not found in atom_tree`,
    )
  }

  // WB-8 Lock 5b — apply the active variant's canonical_dimensions
  // (with surface-default fallback) to the widget container. When no
  // variant is active (variantId === undefined → "all atoms"), the
  // container renders with no explicit dimensions and inherits from
  // the parent canvas.
  const dimensionStyle = useMemo<CSSProperties | undefined>(() => {
    if (!variantId) return undefined
    const activeVariant: VariantDefinition | undefined = blob.variants.find(
      (v) => v.variant_id === variantId,
    )
    if (!activeVariant) return undefined
    const dims =
      activeVariant.canonical_dimensions ??
      surfaceDefaultDimensions(activeVariant.target_surface)
    return { width: `${dims.width}px`, height: `${dims.height}px` }
  }, [blob.variants, variantId])

  return (
    <div
      data-composed-widget-root="true"
      data-widget-id={widgetDefinition.widget_id}
      data-active-variant-id={variantId ?? undefined}
      style={dimensionStyle}
    >
      <AtomRenderer
        atom={rootAtom}
        atomTree={blob.atom_tree}
        bindingsCatalog={blob.bindings_catalog}
        variantId={variantId}
        dataContext={dataContext}
      />
    </div>
  )
}

export default ComposedWidget
