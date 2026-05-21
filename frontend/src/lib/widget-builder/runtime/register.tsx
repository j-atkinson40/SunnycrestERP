/**
 * WB-2 widget-renderer registration for the "composed" key.
 *
 * Side-effect module — importing this file registers ComposedWidget
 * with the canvas widget-renderer registry under the key "composed",
 * following the established pattern from
 * `frontend/src/components/widgets/foundation/register.ts`
 * (SavedViewWidget is the canonical config-driven precedent).
 *
 * Per investigation Area 6 dual-wrapping reconciliation: the
 * "composed" registry entry is the entry-point that
 * `dispatchWidgetDefinition()` routes to when a widget definition's
 * `composition_blob` is populated. The adapter below bridges the
 * WidgetRendererProps shape (widget_id + variant_id + surface +
 * config) to ComposedWidget's input — pulling the composition_blob
 * out of `config.composition_blob` per dispatch convention.
 *
 * Imported once at app bootstrap (via the WB-2 barrel re-export).
 */

import { type ComponentType } from "react"

import {
  registerWidgetRenderer,
  type WidgetRendererProps,
} from "@/components/focus/canvas/widget-renderers"

import { ComposedWidget } from "./ComposedWidget"
import type { VariantId as WBVariantId } from "../types/composition-blob"


/** Adapter — translates WidgetRendererProps (canvas registry's
 *  shape) to ComposedWidget's input. The dispatch helper attaches
 *  the composition_blob to `config.composition_blob` when it routes
 *  here; ComposedWidget parses + renders.
 *
 *  When config lacks composition_blob, ComposedWidget throws —
 *  intentional: routing should have skipped the "composed" key for
 *  hand-coded widgets per the dispatch-helper contract.
 */
const ComposedWidgetAdapter: ComponentType<WidgetRendererProps> = (
  props: WidgetRendererProps,
) => {
  const compositionBlob = props.config?.composition_blob
  return (
    <ComposedWidget
      widgetDefinition={{
        widget_id: props.widgetId,
        composition_blob: compositionBlob,
      }}
      variantId={
        props.variant_id as WBVariantId | undefined
      }
    />
  )
}

ComposedWidgetAdapter.displayName = "ComposedWidgetAdapter"


// Register under the canonical "composed" key. Dispatch helper
// (`dispatchWidgetDefinition`) routes composition_blob-populated
// widgets here regardless of their declared widget_id.
registerWidgetRenderer("composed", ComposedWidgetAdapter)
