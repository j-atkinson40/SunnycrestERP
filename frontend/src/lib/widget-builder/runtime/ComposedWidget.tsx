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

import { useMemo } from "react"

import type {
  CompositionBlob,
  VariantId,
} from "../types/composition-blob"
import { parseCompositionBlob } from "../composition-blob-codec"

import { AtomRenderer } from "./AtomRenderer"


/** Minimal subset of the WB-1-extended WidgetDefinition shape needed
 *  by ComposedWidget. Loose-typed at the boundary so callers passing
 *  the existing `WidgetDefinition` (which doesn't yet carry
 *  composition_blob in its TS interface — that's a WB-3+ catalog
 *  follow-up) plus an extra blob field can hand the value through
 *  without coercion gymnastics. */
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

  return (
    <div
      data-composed-widget-root="true"
      data-widget-id={widgetDefinition.widget_id}
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
