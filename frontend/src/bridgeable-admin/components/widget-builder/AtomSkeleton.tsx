/**
 * AtomSkeleton — WB-5 first-load placeholder per atom shape.
 *
 * Per Area 5 Lock 5a:
 *  - Renders a per-atom-type skeleton when canvas has no prior data
 *    (cold start). Skeleton matches the atom's intrinsic rendered
 *    shape so the operator perceives the layout taking shape rather
 *    than a generic spinner.
 *  - Optional `shimmer` prop adds a subtle motion overlay used by
 *    optimistic-stale refresh (Lock 5a step 2).
 *
 * Uses DESIGN_LANGUAGE.md surface tokens (`bg-surface-sunken`,
 * `bg-surface-base`, etc.) and `--accent-subtle` for shimmer. NEVER
 * uses raw hex / Tailwind palette names; every color is a token.
 *
 * Visual chrome MUST stay distinct from WB-4b validation chrome
 * (red outline / outline-status-error) — skeleton uses muted
 * surface tones, no error colors.
 */
import { cn } from "@/lib/utils"
import type { AtomType } from "@/lib/widget-builder/types/composition-blob"


export interface AtomSkeletonProps {
  atomType: AtomType
  /** When true, overlays a subtle shimmer to communicate
   *  "data being refreshed" (Area 5 Lock 5a). */
  shimmer?: boolean
}


/** Single shimmer-overlay wrapper. Pure CSS animation via Tailwind. */
function ShimmerOverlay() {
  return (
    <div
      data-testid="atom-skeleton-shimmer"
      aria-hidden="true"
      className={cn(
        "pointer-events-none absolute inset-0",
        "animate-pulse rounded-sm bg-accent-subtle/30",
      )}
    />
  )
}


/** Each per-atom-type skeleton is a small render fragment that the
 *  dispatcher below picks via switch. Keeping the shapes inline (vs.
 *  separate exports) keeps the file compact for the catalog. */
function pickSkeletonBody(atomType: AtomType): React.ReactNode {
  switch (atomType) {
    case "text_label":
      // Short pill, roughly word-sized.
      return (
        <div
          data-testid="atom-skeleton-body"
          className="h-4 w-24 rounded-sm bg-surface-sunken"
        />
      )
    case "value_display":
      // Taller, slightly wider — number-sized.
      return (
        <div
          data-testid="atom-skeleton-body"
          className="h-7 w-32 rounded-sm bg-surface-sunken"
        />
      )
    case "icon":
      // Square.
      return (
        <div
          data-testid="atom-skeleton-body"
          className="h-5 w-5 rounded-sm bg-surface-sunken"
        />
      )
    case "status_badge":
      // Pill — wider than text_label but shorter than value_display.
      return (
        <div
          data-testid="atom-skeleton-body"
          className="h-5 w-16 rounded-full bg-surface-sunken"
        />
      )
    case "divider":
      // Thin horizontal rule.
      return (
        <div
          data-testid="atom-skeleton-body"
          className="h-0.5 w-full rounded-full bg-surface-sunken"
        />
      )
    case "button":
      // Button-shaped block (taller than value_display).
      return (
        <div
          data-testid="atom-skeleton-body"
          className="h-9 w-24 rounded-md bg-surface-sunken"
        />
      )
    case "image":
      // Square-ish — small thumbnail proxy.
      return (
        <div
          data-testid="atom-skeleton-body"
          className="h-16 w-16 rounded-sm bg-surface-sunken"
        />
      )
    case "conditional_container":
      // Container — render a row of two muted blocks so the layout
      // is shape-correct.
      return (
        <div
          data-testid="atom-skeleton-body"
          className="flex w-full flex-col gap-2"
        >
          <div className="h-4 w-3/4 rounded-sm bg-surface-sunken" />
          <div className="h-4 w-1/2 rounded-sm bg-surface-sunken" />
        </div>
      )
    case "repeater_atom":
      // Repeater — render 3 stacked rows.
      return (
        <div
          data-testid="atom-skeleton-body"
          className="flex w-full flex-col gap-2"
        >
          <div className="h-5 w-full rounded-sm bg-surface-sunken" />
          <div className="h-5 w-full rounded-sm bg-surface-sunken" />
          <div className="h-5 w-5/6 rounded-sm bg-surface-sunken" />
        </div>
      )
    default: {
      const _exhaustive: never = atomType
      return _exhaustive
    }
  }
}


export function AtomSkeleton({ atomType, shimmer = false }: AtomSkeletonProps) {
  return (
    <div
      data-testid={`atom-skeleton-${atomType}`}
      data-atom-type={atomType}
      data-shimmer={shimmer ? "true" : "false"}
      aria-hidden="true"
      className={cn("relative inline-flex w-full items-center")}
    >
      {pickSkeletonBody(atomType)}
      {shimmer && <ShimmerOverlay />}
    </div>
  )
}

export default AtomSkeleton
