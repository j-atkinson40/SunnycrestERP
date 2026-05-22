/**
 * CanvasPreviewBanner — WB-5 canvas-level banner for network errors
 * + active-fetch indicator.
 *
 * Per Area 4 + Area 5 locks:
 *  - SURFACES ONLY for network-class errors (CanvasPreviewError
 *    with network_class=true). Atom-level errors (404 / 403 / shape
 *    mismatch) get the per-atom AtomResolutionIndicator instead.
 *  - When at least one in-flight fetch but no network errors → a
 *    passive "Fetching preview…" pill (Lock 5a step 4).
 *  - When network errors present → banner with [Retry] affordance.
 *
 * Visual chrome MUST stay distinct from WB-4b validation chrome:
 *  - WB-4b ErrorSummary uses status-error red.
 *  - This banner uses status-warning (amber) for network class to
 *    signal "transient — try again," visually distinct from "this
 *    composition is invalid." Source-shape gates enforce the
 *    distinction at the class-name level.
 */
import { cn } from "@/lib/utils"
import { AlertTriangle, Loader2 } from "lucide-react"

import type { CanvasPreviewDataMap } from "@/bridgeable-admin/hooks/useCanvasPreviewData"


export interface CanvasPreviewBannerProps {
  previewData: CanvasPreviewDataMap
  /** Operator-initiated retry. Fires re-fetch for all failed views
   *  (in practice the parent currently re-mounts the hook by
   *  cycling the blob ref; callers may also pull the underlying
   *  manual-refresh from the hook in a future revision). */
  onRetry?: () => void
}


/** Pull the set of network-class errors out of the preview map. */
function pickNetworkErrors(
  previewData: CanvasPreviewDataMap,
): Array<{ viewId: string; message: string }> {
  const errs: Array<{ viewId: string; message: string }> = []
  for (const [viewId, state] of Object.entries(previewData)) {
    if (
      state.status === "error" &&
      state.error?.network_class === true
    ) {
      errs.push({
        viewId,
        message: state.error.message,
      })
    }
  }
  return errs
}


/** True if any view is currently loading (fresh or refresh). */
function hasInFlight(previewData: CanvasPreviewDataMap): boolean {
  for (const state of Object.values(previewData)) {
    if (state.status === "loading") return true
  }
  return false
}


export function CanvasPreviewBanner({
  previewData,
  onRetry,
}: CanvasPreviewBannerProps) {
  const networkErrors = pickNetworkErrors(previewData)
  const inFlight = hasInFlight(previewData)

  if (networkErrors.length === 0 && !inFlight) {
    return null
  }

  if (networkErrors.length > 0) {
    return (
      <div
        data-testid="widget-builder-canvas-preview-banner"
        data-banner-state="network-error"
        role="status"
        className={cn(
          "mb-3 flex items-start gap-3 rounded-md p-3",
          "border border-status-warning/40 bg-status-warning-muted",
          "text-status-warning",
        )}
      >
        <AlertTriangle
          className="mt-0.5 h-4 w-4 shrink-0"
          aria-hidden="true"
        />
        <div className="flex-1">
          <div className="text-body-sm font-medium">
            Network error — canvas preview unavailable
          </div>
          <div className="mt-0.5 text-caption text-content-muted">
            {networkErrors.length === 1
              ? networkErrors[0].message
              : `${networkErrors.length} saved views failed to load.`}
          </div>
        </div>
        {onRetry && (
          <button
            type="button"
            data-testid="widget-builder-canvas-preview-banner-retry"
            onClick={onRetry}
            className={cn(
              "shrink-0 rounded-sm px-2 py-1 text-caption font-medium",
              "border border-status-warning/40 bg-surface-elevated",
              "text-content-strong hover:bg-accent-subtle",
              "focus-visible:ring-2 focus-visible:ring-accent",
            )}
          >
            Retry
          </button>
        )}
      </div>
    )
  }

  // In-flight indicator (passive pill).
  return (
    <div
      data-testid="widget-builder-canvas-preview-banner"
      data-banner-state="fetching"
      role="status"
      aria-live="polite"
      className={cn(
        "mb-3 inline-flex items-center gap-2 rounded-full px-3 py-1",
        "border border-border-subtle bg-surface-base",
        "text-caption text-content-muted",
      )}
    >
      <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
      <span>Fetching preview…</span>
    </div>
  )
}

export default CanvasPreviewBanner
