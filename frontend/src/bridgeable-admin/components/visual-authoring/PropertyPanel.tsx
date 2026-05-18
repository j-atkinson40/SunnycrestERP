/**
 * PropertyPanel — visual-authoring substrate (sub-arc C-1).
 *
 * Tall narrow inspector container with stacked collapsible sections.
 * Adapted from Sketch's right-side inspector; rendered on
 * warm-cream / warm-charcoal substrate (DESIGN_LANGUAGE §6 surface
 * canon).
 *
 * Three exported primitives:
 *
 *   PropertyPanel    — the outer container. Provides vertical
 *                      stacking + scroll containment.
 *   PropertySection  — a collapsible header + body block. Tight
 *                      vertical rhythm (space-2 internal, space-4
 *                      between sections).
 *   PropertyRow      — a row inside a section: label on the left,
 *                      control on the right.
 *
 * Future consumers (sub-arc C-2 Tier 1+2 editor, sub-arc D Tier 3
 * in-place editor, theme editor refinements) compose against this
 * substrate.
 */
import * as React from "react"
import { ChevronDown, ChevronRight, RotateCcw } from "lucide-react"

import { cn } from "@/lib/utils"

export interface PropertyPanelProps {
  children: React.ReactNode
  className?: string
  /**
   * Optional override for the outer container's data-testid. Defaults
   * to "property-panel" (the C-1 canonical id). Sub-arc C-2.2c added
   * the passthrough so consumers like InheritedCoreInspectorPanel can
   * mount a second PropertyPanel in the same tree without testid
   * collisions.
   */
  "data-testid"?: string
}

export function PropertyPanel({
  children,
  className,
  "data-testid": dataTestId,
}: PropertyPanelProps) {
  return (
    <div
      data-testid={dataTestId ?? "property-panel"}
      className={cn(
        "flex h-full w-full flex-col",
        "border-l border-[color:var(--border-subtle)] bg-[color:var(--surface-base)]",
        "overflow-y-auto",
        className,
      )}
    >
      <div className="flex flex-col gap-4 p-4">{children}</div>
    </div>
  )
}

export interface PropertySectionProps {
  title: string
  /**
   * Optional lineage hint rendered as a thin caption below the title.
   * Added in sub-arc C-2.2b for the Tier 2 inspector to surface where
   * each section's values cascade from (e.g. "cascading from:
   * scheduling-kanban-core"). C-2.3 ships polished inheritance chrome;
   * this is the minimal-extension version.
   */
  lineageHint?: string
  collapsible?: boolean
  defaultExpanded?: boolean
  children: React.ReactNode
  className?: string
}

export function PropertySection({
  title,
  lineageHint,
  collapsible = true,
  defaultExpanded = true,
  children,
  className,
}: PropertySectionProps) {
  const [expanded, setExpanded] = React.useState(defaultExpanded)
  const Icon = expanded ? ChevronDown : ChevronRight
  return (
    <section
      data-testid="property-section"
      data-expanded={expanded || undefined}
      className={cn("flex flex-col gap-2", className)}
    >
      <header
        className={cn(
          "flex items-center justify-between",
          collapsible && "cursor-pointer select-none",
        )}
        onClick={() => collapsible && setExpanded((v) => !v)}
        role={collapsible ? "button" : undefined}
        aria-expanded={collapsible ? expanded : undefined}
        tabIndex={collapsible ? 0 : -1}
        onKeyDown={(e) => {
          if (!collapsible) return
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault()
            setExpanded((v) => !v)
          }
        }}
      >
        <span className="flex flex-col">
          <span
            className="text-[10px] font-semibold tracking-[0.08em] uppercase text-[color:var(--content-muted)]"
            style={{ fontFamily: "var(--font-plex-sans)" }}
          >
            {title}
          </span>
          {lineageHint ? (
            <span
              data-testid="property-section-lineage"
              className="mt-0.5 text-[10px] tracking-wide text-[color:var(--content-subtle)]"
              style={{ fontFamily: "var(--font-plex-mono)" }}
            >
              {lineageHint}
            </span>
          ) : null}
        </span>
        {collapsible ? (
          <Icon
            className="h-3.5 w-3.5 text-[color:var(--content-muted)]"
            aria-hidden
          />
        ) : null}
      </header>
      {expanded ? (
        <div data-testid="property-section-body" className="flex flex-col gap-2">
          {children}
        </div>
      ) : null}
    </section>
  )
}

/**
 * Sub-arc C-2.3 — per-row inheritance source vocabulary.
 *
 *   "explicit"          — value is authored at the current tier;
 *                         full opacity; reset ↺ shows on hover when
 *                         onReset is supplied.
 *   { tier: <label> }   — value cascades from a parent tier; the
 *                         value block dims and a "↑ inherited from
 *                         <label>" caption renders below.
 *   undefined / null    — neutral; no source signal applied.
 *
 * Driven entirely by the resolver's `sources.*_sources` provenance
 * (locked decision #4). Per-row consumers map the resolver's
 * "tier1" / "tier2" / "tier3" / null strings to display labels.
 */
export type PropertyRowInheritance =
  | "explicit"
  | { tier: string }
  | null
  | undefined

export interface PropertyRowProps {
  label?: string
  children: React.ReactNode
  className?: string
  /**
   * Sub-arc C-2.3 — inheritance source for this row's value. See
   * PropertyRowInheritance for the vocabulary. Omitted = neutral row.
   */
  inheritanceSource?: PropertyRowInheritance
  /**
   * Sub-arc C-2.3 — reset-to-inherited handler. When supplied AND
   * `inheritanceSource === "explicit"`, a hover-only ↺ button
   * renders to the right of the row's value block. Hover-only so it
   * doesn't compete with the value at rest. Inherited / neutral rows
   * never render the button.
   */
  onReset?: () => void
}

export function PropertyRow({
  label,
  children,
  className,
  inheritanceSource,
  onReset,
}: PropertyRowProps) {
  const isInherited =
    inheritanceSource != null &&
    typeof inheritanceSource === "object" &&
    "tier" in inheritanceSource
  const isExplicit = inheritanceSource === "explicit"
  const showReset = isExplicit && typeof onReset === "function"
  return (
    <div
      className={cn("group/property-row flex flex-col gap-1", className)}
      data-inheritance={
        isInherited ? "inherited" : isExplicit ? "explicit" : undefined
      }
    >
      {label ? (
        <span
          className="text-[10px] tracking-wide uppercase text-[color:var(--content-subtle)]"
          style={{ fontFamily: "var(--font-plex-sans)" }}
        >
          {label}
        </span>
      ) : null}
      <div className="relative flex items-start gap-1.5">
        <div
          data-testid="property-row-value"
          data-dimmed={isInherited ? "true" : undefined}
          className={cn(
            "min-w-0 flex-1 transition-opacity",
            isInherited && "opacity-60",
          )}
        >
          {children}
        </div>
        {showReset ? (
          <button
            type="button"
            data-testid="property-row-reset"
            aria-label="Reset to inherited"
            title="Reset to inherited"
            onClick={onReset}
            className={cn(
              "shrink-0 self-start rounded-sm p-1",
              "text-[color:var(--content-muted)] hover:text-[color:var(--accent)]",
              "hover:bg-[color:var(--accent-subtle)]",
              "opacity-0 transition-opacity",
              "group-hover/property-row:opacity-100 focus-visible:opacity-100",
              "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[color:var(--accent)]",
            )}
          >
            <RotateCcw className="h-3 w-3" aria-hidden />
          </button>
        ) : null}
      </div>
      {isInherited ? (
        <span
          data-testid="property-row-inheritance-caption"
          className="text-[10px] tracking-wide text-[color:var(--accent)]"
          style={{ fontFamily: "var(--font-plex-mono)" }}
        >
          ↑ inherited from {(inheritanceSource as { tier: string }).tier}
        </span>
      ) : null}
    </div>
  )
}

export default PropertyPanel
