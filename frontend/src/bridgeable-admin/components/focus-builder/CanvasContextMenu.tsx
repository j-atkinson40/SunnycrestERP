/**
 * CanvasContextMenu — sub-arc FF-5.
 *
 * Right-click context menu surface for the four z-order actions
 * (front / forward / backward / back). The first right-click context
 * menu in Focus Builder; establishes the substrate for future
 * canvas-level context menus (FF-7 multi-select align is a likely
 * follow-on consumer).
 *
 * Per Q-31 (c): inspector buttons + right-click context menu both
 * dispatch the same action vocabulary. The inspector surface lives in
 * `LayerInspectorSection`; both surfaces ultimately call
 * `hook.setWidgetZIndex(placementId, action)` via the page-level
 * dispatcher.
 *
 * Rendering:
 *   - React `createPortal` into `document.body` so the menu is NOT
 *     clipped by overflow:hidden parents on the canvas / right-rail.
 *   - `position: fixed` at the cursor coordinates passed via props.
 *   - Closes on: option click (after firing onAction), Escape key,
 *     click-outside (document-level mousedown listener that ignores
 *     mousedowns landing inside the menu's DOM subtree).
 *
 * Visual: brass-accent bordered, surface-elevated background, shadow-
 * level-2, rounded-md. Matches the F-series overlay-family
 * conventions (DropdownMenu / Popover) without pulling in a shadcn
 * primitive (the menu's lifecycle is fully controlled by the parent
 * via `isOpen`).
 *
 * Selection-model preservation (FF-5 contract): right-click does NOT
 * change the operator's current selection. The widget's left-click
 * handler continues to own selection; this menu just acts on the
 * right-clicked target whatever the selection state is. Mirrors
 * Figma / Sketch precedent.
 */
import * as React from "react"
import { createPortal } from "react-dom"
import {
  ChevronsUp,
  ChevronUp,
  ChevronDown,
  ChevronsDown,
} from "lucide-react"

import type { ZIndexAction } from "@/bridgeable-admin/hooks/useFocusTemplateDraft"

export interface CanvasContextMenuProps {
  /** Whether the menu is open. */
  isOpen: boolean
  /** Cursor coordinates (viewport space) at which the menu anchors. */
  position: { x: number; y: number }
  /** Fired on Escape, click-outside, or option click (after onAction). */
  onClose: () => void
  /** Fired when an option is clicked. Action is the canonical z-order
   * action vocabulary shared with LayerInspectorSection. */
  onAction: (action: ZIndexAction) => void
}

interface MenuItem {
  action: ZIndexAction
  label: string
  testId: string
  Icon: typeof ChevronsUp
}

const MENU_ITEMS: MenuItem[] = [
  {
    action: "front",
    label: "Bring to front",
    testId: "context-menu-action-front",
    Icon: ChevronsUp,
  },
  {
    action: "forward",
    label: "Bring forward",
    testId: "context-menu-action-forward",
    Icon: ChevronUp,
  },
  {
    action: "backward",
    label: "Send backward",
    testId: "context-menu-action-backward",
    Icon: ChevronDown,
  },
  {
    action: "back",
    label: "Send to back",
    testId: "context-menu-action-back",
    Icon: ChevronsDown,
  },
]

export function CanvasContextMenu(props: CanvasContextMenuProps) {
  const { isOpen, position, onClose, onAction } = props
  const menuRef = React.useRef<HTMLDivElement | null>(null)

  // Document-level listeners (Escape + click-outside). Mounted only
  // while the menu is open; cleaned up on close + unmount.
  React.useEffect(() => {
    if (!isOpen) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose()
      }
    }
    const handleMouseDown = (e: MouseEvent) => {
      // Ignore mousedowns that land INSIDE the menu DOM subtree.
      const target = e.target as Node | null
      if (target && menuRef.current && menuRef.current.contains(target)) {
        return
      }
      onClose()
    }
    document.addEventListener("keydown", handleKeyDown)
    // mousedown (not click) so the listener fires before the click
    // event would surface — matches DropdownMenu / Popover conventions.
    document.addEventListener("mousedown", handleMouseDown)
    return () => {
      document.removeEventListener("keydown", handleKeyDown)
      document.removeEventListener("mousedown", handleMouseDown)
    }
  }, [isOpen, onClose])

  if (!isOpen) return null

  return createPortal(
    <div
      ref={menuRef}
      data-testid="canvas-context-menu"
      role="menu"
      style={{
        position: "fixed",
        top: `${position.y}px`,
        left: `${position.x}px`,
        zIndex: 9999,
        minWidth: 180,
        fontFamily: "var(--font-plex-sans)",
      }}
      className={[
        "flex flex-col",
        "rounded-md",
        "border border-[color:var(--accent)]",
        "bg-[color:var(--surface-elevated)]",
        "py-1",
        "shadow-level-2",
      ].join(" ")}
    >
      {MENU_ITEMS.map(({ action, label, testId, Icon }) => (
        <button
          key={action}
          type="button"
          role="menuitem"
          data-testid={testId}
          onClick={() => {
            onAction(action)
            onClose()
          }}
          className={[
            "flex items-center gap-2 px-3 py-1.5",
            "text-[12px] text-left",
            "text-[color:var(--content-base)]",
            "transition-colors duration-100",
            "hover:bg-[color:var(--accent)]/10 hover:text-[color:var(--accent)]",
            "focus-visible:outline-none focus-visible:bg-[color:var(--accent)]/10",
          ].join(" ")}
        >
          <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden />
          <span>{label}</span>
        </button>
      ))}
    </div>,
    document.body,
  )
}

export default CanvasContextMenu
