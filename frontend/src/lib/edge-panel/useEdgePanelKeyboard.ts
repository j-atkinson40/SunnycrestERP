/**
 * R-5.0 — keyboard handlers for edge panel.
 *
 * Cmd/Ctrl+Shift+E   → toggle open/closed (skipped when typing in input)
 * Esc (when open)    → close
 * ArrowLeft/Right    → cycle pages (skipped when typing in input)
 *
 * Handler is window-level keydown; ignores events with target =
 * INPUT/TEXTAREA/SELECT/contentEditable so typing in forms doesn't
 * fire the toggle. Matches DotNav's gate.
 */
import { useEffect } from "react"

import { useEdgePanel } from "./EdgePanelProvider"


function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  const tag = target.tagName
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true
  if (target.isContentEditable) return true
  return false
}


export function useEdgePanelKeyboard(): void {
  const {
    isOpen,
    isReady,
    composition,
    currentPageIndex,
    setCurrentPageIndex,
    closePanel,
    togglePanel,
    tenantConfig,
  } = useEdgePanel()

  useEffect(() => {
    if (!isReady || !tenantConfig.enabled) return

    function onKeyDown(e: KeyboardEvent) {
      // Cmd+Shift+E (Mac) / Ctrl+Shift+E (Windows/Linux) — toggle.
      if (
        (e.metaKey || e.ctrlKey) &&
        e.shiftKey &&
        e.key.toLowerCase() === "e"
      ) {
        if (isTypingTarget(e.target)) return
        e.preventDefault()
        togglePanel()
        return
      }

      // Below this point, only handle keys when panel is open.
      if (!isOpen) return

      if (e.key === "Escape") {
        e.preventDefault()
        closePanel()
        return
      }

      // Page cycling — gate against typing too.
      if (isTypingTarget(e.target)) return

      const pages = composition?.pages ?? []
      if (pages.length <= 1) return

      if (e.key === "ArrowLeft") {
        e.preventDefault()
        const next = currentPageIndex - 1
        setCurrentPageIndex(next < 0 ? pages.length - 1 : next)
      } else if (e.key === "ArrowRight") {
        e.preventDefault()
        const next = currentPageIndex + 1
        setCurrentPageIndex(next >= pages.length ? 0 : next)
      }
    }

    window.addEventListener("keydown", onKeyDown)
    return () => {
      window.removeEventListener("keydown", onKeyDown)
    }
  }, [
    isReady,
    tenantConfig.enabled,
    isOpen,
    composition,
    currentPageIndex,
    setCurrentPageIndex,
    closePanel,
    togglePanel,
  ])
}
