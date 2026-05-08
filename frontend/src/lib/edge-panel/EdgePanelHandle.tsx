/**
 * R-5.0 — Edge panel handle.
 *
 * Right-edge tab; hover-expand reveals a chevron icon. Click invokes
 * the panel.
 *
 * Hidden when:
 *   - tenantConfig.enabled === false
 *   - !isReady (composition still loading)
 *   - panel is open (handle is part of the panel surface; the panel
 *     itself takes over the right edge when open)
 *   - body[data-runtime-editor-mode="edit"] is set (mode-mutex with
 *     runtime editor inspector — both want right-edge real estate)
 *
 * Z-index: var(--z-edge-panel) (96).
 */
import { useEffect, useState } from "react"
import { ChevronLeft } from "lucide-react"

import { useEdgePanel } from "./EdgePanelProvider"


export function EdgePanelHandle() {
  const { isOpen, isReady, openPanel, tenantConfig } = useEdgePanel()
  const [editorActive, setEditorActive] = useState(false)
  const [hovered, setHovered] = useState(false)

  // Mode-mutex with runtime editor — observe body data-attr so the
  // handle hides when editor edit-mode is on.
  useEffect(() => {
    if (typeof document === "undefined") return
    const update = () => {
      setEditorActive(
        document.body.getAttribute("data-runtime-editor-mode") === "edit",
      )
    }
    update()
    const obs = new MutationObserver(update)
    obs.observe(document.body, {
      attributes: true,
      attributeFilter: ["data-runtime-editor-mode"],
    })
    return () => obs.disconnect()
  }, [])

  if (!isReady) return null
  if (!tenantConfig.enabled) return null
  if (isOpen) return null
  if (editorActive) return null

  return (
    <button
      type="button"
      data-testid="edge-panel-handle"
      aria-label="Open edge panel"
      onClick={openPanel}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        position: "fixed",
        right: 0,
        top: "50%",
        transform: "translateY(-50%)",
        zIndex: "var(--z-edge-panel)" as unknown as number,
        height: 80,
        width: hovered ? 24 : 6,
        background: "var(--accent-subtle)",
        borderRadius: "3px 0 0 3px",
        border: "none",
        cursor: "pointer",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 0,
        transition: "width var(--duration-quick) var(--ease-gentle)",
      }}
    >
      {hovered && <ChevronLeft size={16} className="text-accent" />}
    </button>
  )
}
