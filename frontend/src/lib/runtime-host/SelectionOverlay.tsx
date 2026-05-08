/**
 * Phase R-1 — SelectionOverlay.
 *
 * Mounts inside the runtime editor shell. When edit mode is active:
 *   1. Capture-phase click handler walks up from event.target to
 *      the nearest [data-component-name] (Phase R-1 §3 attribute
 *      injected by registerComponent HOC). Found → set selection +
 *      preventDefault + stopPropagation. Not found → clear selection.
 *      Walking stops at [data-runtime-host-root] boundary.
 *   2. Brass selection border drawn via fixed-position overlay sized
 *      to the selected element's getBoundingClientRect. Updated on
 *      scroll + resize via ResizeObserver + scroll listener.
 *   3. Hover affordance: 30%-opacity brass outline on
 *      [data-component-name]:hover (CSS rule injected once).
 *
 * When edit mode is INACTIVE, this component renders null + has no
 * effect — the click capture is gated on `isEditing === true`.
 *
 * Operational handlers within registered widgets are gated on
 * `_editMode === true` per the existing widget convention. The
 * capture-phase preventDefault here adds belt-and-suspenders for
 * components that consume click events directly (anchor tags,
 * <button> handlers) without checking edit mode.
 */
import { useCallback, useEffect, useRef, useState } from "react"

import { getByName } from "@/lib/visual-editor/registry"
import type { ComponentKind } from "@/lib/visual-editor/registry"

import { useEditMode } from "./edit-mode-context"


interface SelectionRect {
  top: number
  left: number
  width: number
  height: number
}


export function SelectionOverlay() {
  const {
    isEditing,
    selectedComponentName,
    selectComponent,
    selectSection,
  } = useEditMode()
  const [rect, setRect] = useState<SelectionRect | null>(null)
  const observerRef = useRef<ResizeObserver | null>(null)
  const trackedElementRef = useRef<HTMLElement | null>(null)

  // Inject hover-affordance CSS once.
  useEffect(() => {
    if (typeof document === "undefined") return
    const id = "runtime-editor-hover-style"
    if (document.getElementById(id)) return
    const styleEl = document.createElement("style")
    styleEl.id = id
    styleEl.textContent = `
      [data-runtime-editor-mode="edit"] [data-component-name]:hover {
        outline: 1px solid color-mix(in srgb, var(--accent) 30%, transparent);
        outline-offset: 2px;
        cursor: pointer;
      }
    `
    document.head.appendChild(styleEl)
    return () => {
      const el = document.getElementById(id)
      if (el) el.remove()
    }
  }, [])

  // Reflect edit mode on document.body for the hover-affordance
  // CSS selector.
  useEffect(() => {
    if (typeof document === "undefined") return
    if (isEditing) {
      document.body.setAttribute("data-runtime-editor-mode", "edit")
    } else {
      document.body.removeAttribute("data-runtime-editor-mode")
    }
    return () => {
      document.body.removeAttribute("data-runtime-editor-mode")
    }
  }, [isEditing])

  // Capture-phase click handler — runs BEFORE any tenant component's
  // own click handler. preventDefault + stopPropagation block the
  // operational handler from firing while edit mode is active.
  useEffect(() => {
    if (!isEditing) return
    if (typeof document === "undefined") return

    const handler = (e: MouseEvent) => {
      const target = e.target as HTMLElement | null
      if (!target) return

      // Walk up looking for a registered component boundary.
      let node: HTMLElement | null = target
      let foundName: string | null = null
      while (node && node !== document.body) {
        // Stop at the runtime host root if encountered before a match
        // (so toggle / inspector clicks don't get hijacked).
        if (node.hasAttribute("data-runtime-host-root")) {
          break
        }
        // Skip if we're inside the inspector panel itself.
        if (node.hasAttribute("data-runtime-editor-chrome")) {
          return
        }
        const name = node.getAttribute("data-component-name")
        if (name) {
          foundName = name
          break
        }
        node = node.parentElement
      }

      if (foundName) {
        e.preventDefault()
        e.stopPropagation()
        // R-2.1 — when the resolved slug is dot-separated (canonical
        // sub-section convention `<parent>.<child>`), dispatch the
        // section-aware selectSection action so the inspector mounts
        // the parent's outer-tab strip + scopes its inner triad
        // (theme/class/props) to the section. Bare slugs route through
        // the legacy selectComponent action.
        //
        // Parent linkage is consulted via the registry's
        // `extensions.entityCardSection` shape — slug-string parsing
        // is convenient (`slug.split(".")[0]`) but NOT canonical;
        // future parents whose slugs themselves contain dots stay
        // parseable through metadata. Falls back to the slug split if
        // the registry entry is missing (defensive — selection still
        // records the section name + a best-effort parent).
        if (foundName.includes(".")) {
          const sectionEntry = getByName(
            "entity-card-section",
            foundName,
          )
          const ext = sectionEntry?.metadata.extensions
            ?.entityCardSection as
            | {
                parentKind?: ComponentKind
                parentName?: string
              }
            | undefined
          const parentKind: ComponentKind = ext?.parentKind ?? "entity-card"
          const parentName: string =
            ext?.parentName ?? foundName.split(".")[0]
          selectSection(parentKind, parentName, foundName)
        } else {
          selectComponent(foundName)
        }
      } else {
        // Clicking outside any registered component clears selection
        // ONLY if the click landed on the tenant content region — clicks
        // on chrome (toggle, inspector) shouldn't clear.
        // Heuristic: if the click went through the runtime host content
        // region, clear. Inspector/toggle have data-runtime-editor-chrome
        // and we returned early above.
        selectComponent(null)
      }
    }

    document.addEventListener("click", handler, true) // capture phase
    return () => {
      document.removeEventListener("click", handler, true)
    }
  }, [isEditing, selectComponent, selectSection])

  // Track selected element + its bounding rect.
  const updateRect = useCallback(() => {
    const el = trackedElementRef.current
    if (!el) {
      setRect(null)
      return
    }
    const r = el.getBoundingClientRect()
    setRect({ top: r.top, left: r.left, width: r.width, height: r.height })
  }, [])

  useEffect(() => {
    if (!isEditing || !selectedComponentName) {
      trackedElementRef.current = null
      setRect(null)
      observerRef.current?.disconnect()
      observerRef.current = null
      return
    }

    if (typeof document === "undefined") return

    const el = document.querySelector<HTMLElement>(
      `[data-component-name="${CSS.escape(selectedComponentName)}"]`,
    )
    if (!el) {
      trackedElementRef.current = null
      setRect(null)
      return
    }

    trackedElementRef.current = el
    updateRect()

    const ro = new ResizeObserver(() => updateRect())
    ro.observe(el)
    observerRef.current = ro

    const onScroll = () => updateRect()
    window.addEventListener("scroll", onScroll, true)
    window.addEventListener("resize", onScroll)

    return () => {
      ro.disconnect()
      observerRef.current = null
      window.removeEventListener("scroll", onScroll, true)
      window.removeEventListener("resize", onScroll)
      trackedElementRef.current = null
    }
  }, [isEditing, selectedComponentName, updateRect])

  if (!isEditing || !selectedComponentName || !rect) return null

  return (
    <div
      aria-hidden="true"
      data-runtime-editor-chrome="true"
      data-testid="runtime-editor-selection-overlay"
      className="pointer-events-none fixed"
      style={{
        top: rect.top - 2,
        left: rect.left - 2,
        width: rect.width + 4,
        height: rect.height + 4,
        outline: "2px solid var(--accent)",
        outlineOffset: 0,
        borderRadius: 4,
        zIndex: 92,
        boxShadow: "0 0 0 4px color-mix(in srgb, var(--accent) 20%, transparent)",
      }}
    />
  )
}
