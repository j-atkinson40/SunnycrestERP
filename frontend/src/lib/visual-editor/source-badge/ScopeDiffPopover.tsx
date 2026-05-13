/**
 * Arc 4d — ScopeDiffPopover.
 *
 * Eleventh canonical candidate, **co-located** in the source-badge
 * module per extract-when-second-consumer-emerges canon (Arc 4c
 * AlignmentGuideOverlay precedent). The single canonical consumer
 * today is the inspector-tab SourceBadge-wrapping integration; a
 * second consumer would warrant extraction to its own module.
 *
 * Settled Q-ARC4D-2 + Q-ARC4D-5: hover-reveal popover showing the
 * full scope-resolution chain ABOVE the winning source. When the
 * operator hovers a tenant-override badge, the popover lists the
 * platform_default + vertical_default values it overrides.
 *
 * Hover-reveal mechanics:
 *   - 300ms open delay (matches Tooltip canon per DESIGN_LANGUAGE §6)
 *   - Esc + click-outside dismiss
 *   - Lightweight bespoke popover (not base-ui Popover.Root) because
 *     trigger is a non-interactive <span> badge — base-ui Popover
 *     requires a clickable trigger element. Hover-reveal over a span
 *     is closer to Tooltip semantics; we render Tooltip-shape chrome
 *     with Popover-rich content (ordered scope list).
 *
 * Empty sources → null render. Trigger always renders.
 */
import type { JSX, ReactNode } from "react"
import { useEffect, useRef, useState } from "react"


/**
 * Canonical scope vocabulary mirroring backend resolver returns.
 * `draft` represents an in-memory operator edit not yet persisted.
 */
export type ResolutionScope =
  | "platform_default"
  | "vertical_default"
  | "tenant_override"
  | "draft"


/**
 * One entry in the resolution chain. Order in `sources[]` is
 * resolver-order (winning entry typically first per first-match-wins
 * semantics in §4 Documents canon + parallel themes/component_configs/
 * focus_compositions resolvers).
 */
export interface ResolutionSourceEntry {
  scope: ResolutionScope
  value: unknown
  /** Optional version number (themes/configs/compositions only). */
  version?: number
  /** Optional vertical filter (vertical_default scope only). */
  vertical?: string
  /** Optional tenant filter (tenant_override scope only). */
  tenant_id?: string
}


export interface ScopeDiffPopoverProps {
  /**
   * Resolution chain in resolver order. Winning entry FIRST (matches
   * resolver-returns convention). Empty array suppresses popover.
   */
  sources: ResolutionSourceEntry[]
  /** Currently-active resolved value. */
  currentValue?: unknown
  /** Optional label for the field being diffed (e.g. "accent token"). */
  fieldLabel?: string
  /** Trigger element (typically a SourceBadge). */
  children: ReactNode
  /** Open delay in ms; default 300 per DESIGN_LANGUAGE §6 Tooltip canon. */
  openDelayMs?: number
  /** Test-id for the trigger wrapper. */
  "data-testid"?: string
}


const SCOPE_LABEL: Record<ResolutionScope, string> = {
  platform_default: "Platform default",
  vertical_default: "Vertical default",
  tenant_override: "Tenant override",
  draft: "Draft (unsaved)",
}


/**
 * Renders the trigger always; popover content appears on hover with
 * delay. Trigger ref + popover ref tracked for click-outside +
 * Esc-dismiss.
 */
export function ScopeDiffPopover({
  sources,
  currentValue,
  fieldLabel,
  children,
  openDelayMs = 300,
  "data-testid": testId,
}: ScopeDiffPopoverProps): JSX.Element {
  const [open, setOpen] = useState(false)
  const triggerRef = useRef<HTMLSpanElement | null>(null)
  const popoverRef = useRef<HTMLDivElement | null>(null)
  const openTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const clearOpenTimer = () => {
    if (openTimerRef.current !== null) {
      clearTimeout(openTimerRef.current)
      openTimerRef.current = null
    }
  }

  const scheduleOpen = () => {
    clearOpenTimer()
    if (sources.length === 0) return
    openTimerRef.current = setTimeout(() => {
      setOpen(true)
      openTimerRef.current = null
    }, openDelayMs)
  }

  const closeNow = () => {
    clearOpenTimer()
    setOpen(false)
  }

  // Document-level Esc + click-outside dismiss.
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeNow()
    }
    const onMouseDown = (e: MouseEvent) => {
      const target = e.target as Node | null
      if (!target) return
      if (
        triggerRef.current?.contains(target) ||
        popoverRef.current?.contains(target)
      ) {
        return
      }
      closeNow()
    }
    document.addEventListener("keydown", onKey)
    document.addEventListener("mousedown", onMouseDown)
    return () => {
      document.removeEventListener("keydown", onKey)
      document.removeEventListener("mousedown", onMouseDown)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  // Cleanup timer on unmount.
  useEffect(() => clearOpenTimer, [])

  // Empty sources: render trigger only, skip popover entirely. This
  // keeps integration sites simple — they always wrap, but the
  // popover only surfaces when there IS a chain to diff.
  if (sources.length === 0) {
    return (
      <span
        ref={triggerRef}
        data-testid={testId ?? "scope-diff-popover"}
        data-state="empty"
      >
        {children}
      </span>
    )
  }

  return (
    <span
      ref={triggerRef}
      onMouseEnter={scheduleOpen}
      onMouseLeave={closeNow}
      onFocus={scheduleOpen}
      onBlur={closeNow}
      data-testid={testId ?? "scope-diff-popover"}
      data-state={open ? "open" : "closed"}
      className="relative inline-flex"
    >
      {children}
      {open && (
        <div
          ref={popoverRef}
          role="dialog"
          aria-label={
            fieldLabel ? `Scope chain for ${fieldLabel}` : "Scope chain"
          }
          className="absolute left-0 top-full z-50 mt-1 min-w-[14rem] max-w-[20rem] rounded-md border border-border-subtle bg-surface-raised p-2 shadow-level-2"
          data-testid={`${testId ?? "scope-diff-popover"}-content`}
          // Stop mouseleave inside content from closing trigger's hover.
          onMouseEnter={clearOpenTimer}
        >
          {fieldLabel && (
            <div className="px-1 pb-1 text-[10px] uppercase tracking-wide text-content-subtle">
              {fieldLabel}
            </div>
          )}
          <ol className="flex flex-col gap-1">
            {sources.map((entry, idx) => {
              const isWinning = idx === 0
              return (
                <li
                  key={`${entry.scope}-${idx}`}
                  className={`flex flex-col gap-0.5 rounded-sm border px-2 py-1.5 text-caption ${
                    isWinning
                      ? "border-accent bg-accent-subtle/40"
                      : "border-border-subtle bg-surface-elevated"
                  }`}
                  data-testid={`scope-diff-entry-${idx}`}
                  data-scope={entry.scope}
                  data-winning={isWinning ? "true" : "false"}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span
                      className={`text-[10px] font-medium uppercase tracking-wide ${
                        isWinning ? "text-accent" : "text-content-muted"
                      }`}
                    >
                      {SCOPE_LABEL[entry.scope]}
                      {isWinning && (
                        <span className="ml-1 normal-case text-[10px] text-accent">
                          ✓ winning
                        </span>
                      )}
                    </span>
                    {entry.version !== undefined && (
                      <span className="font-plex-mono text-[10px] text-content-subtle">
                        v{entry.version}
                      </span>
                    )}
                  </div>
                  <div className="font-plex-mono text-[11px] text-content-strong break-all">
                    {formatValue(entry.value)}
                  </div>
                  {(entry.vertical || entry.tenant_id) && (
                    <div className="text-[10px] text-content-subtle">
                      {entry.vertical && `vertical: ${entry.vertical}`}
                      {entry.vertical && entry.tenant_id && " · "}
                      {entry.tenant_id &&
                        `tenant: ${entry.tenant_id.slice(0, 8)}…`}
                    </div>
                  )}
                </li>
              )
            })}
          </ol>
          {currentValue !== undefined && sources[0]?.value !== currentValue && (
            <div
              className="mt-2 rounded-sm border border-status-warning/40 bg-status-warning-muted px-2 py-1 text-[10px] text-status-warning"
              data-testid="scope-diff-drift-warning"
            >
              Current value differs from winning resolved value (possible
              drift).
            </div>
          )}
        </div>
      )}
    </span>
  )
}


function formatValue(v: unknown): string {
  if (v === null) return "null"
  if (v === undefined) return "undefined"
  if (typeof v === "string") return v || '""'
  if (typeof v === "number" || typeof v === "boolean") return String(v)
  try {
    return JSON.stringify(v)
  } catch {
    return "[unserializable]"
  }
}
