/**
 * S-2 (§4.3) contextual-surface widget registration barrel.
 *
 * Side-effect import at App bootstrap (same pattern as the visual-editor
 * auto-register barrel + the scheduling-focus register.ts): importing
 * each widget module runs its bottom-of-file registerWidgetRenderer call,
 * so surface.quote-preview + surface.price-list-reference are in the
 * canvas widget-renderer registry before CommandBarSurfaceHost dispatches
 * to them.
 */

import "./QuotePreviewWidget"
import "./PriceListReferenceWidget"
