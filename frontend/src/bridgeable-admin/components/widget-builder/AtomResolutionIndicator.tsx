/**
 * AtomResolutionIndicator — WB-5 per-atom resolution-error chrome.
 *
 * Per Area 4 Locks 4a + 4d:
 *  - Surfaces an inline ⚠ icon overlay when an atom's binding(s)
 *    failed to resolve (view not found, permission denied, shape
 *    mismatch). Hover surfaces the specific error message via
 *    `title=`.
 *  - Visually DISTINCT from WB-4b's AtomErrorIndicator. WB-4b uses
 *    `outline-status-error` (red) for composition-validation errors.
 *    This indicator overlays a warning-pill chrome on the corner so
 *    operators can distinguish "this composition is structurally
 *    invalid (red)" from "this composition is fine but the data
 *    didn't load (warning)."
 *  - Composes with selection ring — both render simultaneously because
 *    they live in different DOM layers (selection ring is on the
 *    CanvasAtom wrapper; indicator is an overlay on the wrapped
 *    content).
 *  - For masked-field case (cross-tenant masking), the chrome shifts
 *    to a lock-icon variant per Lock 4a E7.
 */
import { AlertTriangle, Lock } from "lucide-react"

import { cn } from "@/lib/utils"


export type AtomResolutionVariant = "error" | "masked"


export interface AtomResolutionIndicatorProps {
  atomId: string
  /** When set, the indicator renders. When undefined / null, the
   *  wrapped children render verbatim (no chrome added). */
  message?: string
  variant?: AtomResolutionVariant
  children: React.ReactNode
}


export function AtomResolutionIndicator({
  atomId,
  message,
  variant = "error",
  children,
}: AtomResolutionIndicatorProps) {
  if (!message) {
    return <>{children}</>
  }

  const Icon = variant === "masked" ? Lock : AlertTriangle
  const tone =
    variant === "masked"
      ? "border-border-base bg-surface-elevated text-content-muted"
      : // Warning tone — distinct from WB-4b's status-error red.
        "border-status-warning/40 bg-status-warning-muted text-status-warning"

  return (
    <div
      data-testid={`widget-builder-canvas-atom-resolution-${atomId}`}
      data-atom-id={atomId}
      data-resolution-variant={variant}
      data-has-resolution-error="true"
      title={message}
      className="relative inline-block w-full"
    >
      {children}
      <div
        aria-hidden="true"
        className={cn(
          "pointer-events-none absolute -top-1 -right-1",
          "inline-flex h-4 w-4 items-center justify-center",
          "rounded-full border shadow-sm",
          tone,
        )}
      >
        <Icon className="h-2.5 w-2.5" />
      </div>
    </div>
  )
}

export default AtomResolutionIndicator
