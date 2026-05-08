/**
 * R-5.0 — EdgePanel.
 *
 * Slides in from the right when isOpen. Renders one page at a time
 * via CompositionRenderer (kind=focus rows from each page treated as
 * a row-set). Page navigation:
 *   - Dots indicator at panel bottom (one dot per page; brass-filled
 *     active; outline inactive). Click to jump.
 *   - Esc + click-outside close the panel. Cmd+Shift+E toggle handled
 *     by useEdgePanelKeyboard (mounted by the provider's children).
 *   - ArrowLeft/ArrowRight cycle pages (also via the keyboard hook).
 *
 * No backdrop — quick-action surface; user keeps visual context.
 *
 * Z-index: var(--z-edge-panel) (96). Handle disappears under Focus
 * backdrop when Focus is open (Focus = 100).
 *
 * Empty composition: render a placeholder with "No actions yet" copy.
 * Disabled tenant: doesn't render at all (gated at the host).
 */
import { useEffect, useRef } from "react"

import { CompositionRenderer } from "@/lib/visual-editor/compositions/CompositionRenderer"
import type { ResolvedComposition } from "@/lib/visual-editor/compositions/types"
import { useEdgePanel } from "./EdgePanelProvider"
import type { EdgePanelPage } from "./types"


function pageToResolvedComposition(
  page: EdgePanelPage,
  panelKey: string,
): ResolvedComposition {
  return {
    focus_type: panelKey,
    vertical: null,
    tenant_id: null,
    source: "platform_default",
    source_id: null,
    source_version: null,
    rows: page.rows,
    canvas_config: page.canvas_config ?? {},
  }
}


export function EdgePanel() {
  const {
    isOpen,
    isReady,
    composition,
    currentPageIndex,
    setCurrentPageIndex,
    closePanel,
    tenantConfig,
    panelKey,
  } = useEdgePanel()

  const panelRef = useRef<HTMLDivElement | null>(null)

  // Click-outside-to-close. Captured at document level when open.
  useEffect(() => {
    if (!isOpen) return
    function onDocClick(e: MouseEvent) {
      const el = panelRef.current
      if (el && e.target instanceof Node && !el.contains(e.target)) {
        closePanel()
      }
    }
    // Defer attach to next tick so the click that opened the panel
    // doesn't immediately close it.
    const t = window.setTimeout(() => {
      document.addEventListener("click", onDocClick)
    }, 0)
    return () => {
      window.clearTimeout(t)
      document.removeEventListener("click", onDocClick)
    }
  }, [isOpen, closePanel])

  if (!isReady) return null
  if (!tenantConfig.enabled) return null

  const pages = composition?.pages ?? []
  const safeIndex =
    pages.length === 0
      ? 0
      : Math.max(0, Math.min(currentPageIndex, pages.length - 1))
  const activePage = pages[safeIndex] ?? null

  return (
    <div
      ref={panelRef}
      data-testid="edge-panel"
      data-edge-panel-open={isOpen ? "true" : "false"}
      role="dialog"
      aria-label="Edge panel"
      aria-hidden={!isOpen}
      style={{
        position: "fixed",
        top: 0,
        right: 0,
        bottom: 0,
        width: tenantConfig.width,
        zIndex: "var(--z-edge-panel)" as unknown as number,
        background: "var(--surface-elevated)",
        boxShadow: "var(--shadow-level-3)",
        borderLeft: "1px solid var(--border-subtle)",
        display: "flex",
        flexDirection: "column",
        transform: isOpen ? "translateX(0)" : "translateX(100%)",
        transition: isOpen
          ? "transform var(--duration-arrive) var(--ease-settle)"
          : "transform var(--duration-settle) var(--ease-gentle)",
        pointerEvents: isOpen ? "auto" : "none",
      }}
    >
      {/* Page header — eyebrow with active page name. */}
      {activePage !== null && (
        <div
          data-testid="edge-panel-page-header"
          className="border-b border-border-subtle bg-surface-base px-4 py-2"
        >
          <div className="text-micro uppercase tracking-wider text-content-muted">
            {activePage.name}
          </div>
        </div>
      )}

      {/* Page content. */}
      <div
        data-testid="edge-panel-content"
        style={{
          flex: 1,
          overflowY: "auto",
          overflowX: "hidden",
        }}
      >
        {activePage !== null ? (
          <CompositionRenderer
            composition={pageToResolvedComposition(activePage, panelKey)}
            editorMode={false}
          />
        ) : (
          <div
            data-testid="edge-panel-empty"
            className="flex items-center justify-center p-6 text-caption text-content-subtle"
          >
            No actions yet. Admins can add buttons via the visual editor.
          </div>
        )}
      </div>

      {/* Page indicator dots — bottom of panel; only when 2+ pages. */}
      {pages.length > 1 && (
        <div
          data-testid="edge-panel-dots"
          className="flex items-center justify-center gap-1.5 border-t border-border-subtle bg-surface-base px-4 py-2"
        >
          {pages.map((page, idx) => {
            const active = idx === safeIndex
            return (
              <button
                key={page.page_id}
                type="button"
                aria-label={`Go to page ${page.name}`}
                aria-current={active ? "page" : undefined}
                data-testid={`edge-panel-dot-${idx}`}
                data-active={active ? "true" : "false"}
                onClick={() => setCurrentPageIndex(idx)}
                className="rounded-full"
                style={{
                  width: 8,
                  height: 8,
                  border: "1px solid var(--accent)",
                  background: active ? "var(--accent)" : "transparent",
                  cursor: "pointer",
                  padding: 0,
                  transition: "background var(--duration-quick) var(--ease-gentle)",
                }}
              />
            )
          })}
        </div>
      )}
    </div>
  )
}
