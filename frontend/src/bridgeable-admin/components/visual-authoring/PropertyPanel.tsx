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
import { ChevronDown, ChevronRight } from "lucide-react"

import { cn } from "@/lib/utils"

export interface PropertyPanelProps {
  children: React.ReactNode
  className?: string
}

export function PropertyPanel({ children, className }: PropertyPanelProps) {
  return (
    <div
      data-testid="property-panel"
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

export interface PropertyRowProps {
  label?: string
  children: React.ReactNode
  className?: string
}

export function PropertyRow({ label, children, className }: PropertyRowProps) {
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      {label ? (
        <span
          className="text-[10px] tracking-wide uppercase text-[color:var(--content-subtle)]"
          style={{ fontFamily: "var(--font-plex-sans)" }}
        >
          {label}
        </span>
      ) : null}
      {children}
    </div>
  )
}

export default PropertyPanel
