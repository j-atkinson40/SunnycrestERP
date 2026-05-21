/**
 * dispatchWidgetDefinition — WB-2 dispatch helper.
 *
 * Single additive entry-point that routes between the WB-2
 * ComposedWidget runtime (composition_blob populated) and the
 * existing hand-coded `getWidgetRenderer(widget_id)` path
 * (composition_blob NULL / undefined).
 *
 * Existing callers of `getWidgetRenderer` (Canvas, BottomSheet,
 * StackRail, StackExpandedOverlay, PulsePiece, PinnedSection)
 * continue to work UNCHANGED — they only deal in widget_id +
 * config without the composition_blob axis. Hand-coded widget
 * render path is intentionally untouched (regression preservation
 * per WB-2 invariants).
 *
 * NEW callers (the WB-3+ Widget Builder + future
 * composition-blob-aware surfaces) use `dispatchWidgetDefinition`
 * to hand a full widget_definition row through. The helper routes
 * by checking composition_blob presence:
 *
 *   - composition_blob populated → returns the "composed" renderer +
 *     stashes composition_blob into config.composition_blob so the
 *     ComposedWidgetAdapter can extract it on render.
 *   - composition_blob NULL → returns the renderer registered under
 *     widget_id (the existing path); config passes through verbatim.
 *
 * The shape that comes back is a tuple of (Renderer, props) so
 * callers can render via `<Renderer {...props} />` without further
 * boilerplate.
 */

import { type ComponentType } from "react"

import {
  getWidgetRenderer,
  type WidgetRendererProps,
} from "@/components/focus/canvas/widget-renderers"


/** Minimal subset of the backend WidgetDefinition row needed by
 *  the dispatch helper. Accepts the WB-1-extended shape (with
 *  composition_blob optional) without coupling to the
 *  `components/widgets/types.ts::WidgetDefinition` interface
 *  (which doesn't yet declare composition_blob — WB-3+ folds it in). */
export interface DispatchableWidgetDefinition {
  widget_id: string
  composition_blob?: unknown | null
}


export interface DispatchResult {
  Renderer: ComponentType<WidgetRendererProps>
  props: WidgetRendererProps
}


export function dispatchWidgetDefinition(
  definition: DispatchableWidgetDefinition,
  baseProps: Omit<WidgetRendererProps, "widgetId">,
): DispatchResult {
  const hasCompositionBlob =
    definition.composition_blob !== null &&
    definition.composition_blob !== undefined

  if (hasCompositionBlob) {
    // Route via the "composed" registry key. The adapter at
    // `register.tsx` extracts composition_blob from config and
    // hands it to ComposedWidget. We avoid mutating the caller's
    // config object by spreading.
    const Renderer = getWidgetRenderer("composed")
    return {
      Renderer,
      props: {
        ...baseProps,
        widgetId: definition.widget_id,
        config: {
          ...(baseProps.config ?? {}),
          composition_blob: definition.composition_blob,
        },
      },
    }
  }

  // Existing path: dispatch via widget_id. Hand-coded widget
  // renderer path UNCHANGED.
  const Renderer = getWidgetRenderer(definition.widget_id)
  return {
    Renderer,
    props: {
      ...baseProps,
      widgetId: definition.widget_id,
    },
  }
}
