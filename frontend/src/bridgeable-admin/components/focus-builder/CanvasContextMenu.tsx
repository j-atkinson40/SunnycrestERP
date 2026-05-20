/**
 * CanvasContextMenu — sub-arc FF-5 + FF-7 multi-select extension.
 *
 * Right-click context menu surface. FF-5 shipped the z-order action
 * vocabulary (front / forward / backward / back). FF-7 extends with
 * an alternate action set for multi-select context: six align
 * actions (left / center-horizontal / right / top / center-vertical
 * / bottom) per Q-17 (b). The caller selects which set to render
 * via `actionSet`.
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
  AlignCenterHorizontal,
  AlignCenterVertical,
  AlignEndHorizontal,
  AlignEndVertical,
  AlignStartHorizontal,
  AlignStartVertical,
  ChevronsUp,
  ChevronUp,
  ChevronDown,
  ChevronsDown,
} from "lucide-react"

import type { ZIndexAction } from "@/bridgeable-admin/hooks/useFocusTemplateDraft"
import type { AlignAction } from "./computeAlignTargets"

export type ContextMenuActionSet = "z-order" | "align"
export type ContextMenuAction = ZIndexAction | AlignAction

export interface CanvasContextMenuProps {
  /** Whether the menu is open. */
  isOpen: boolean
  /** Cursor coordinates (viewport space) at which the menu anchors. */
  position: { x: number; y: number }
  /** Fired on Escape, click-outside, or option click (after onAction). */
  onClose: () => void
  /** Fired when an option is clicked. The action is typed across both
   * vocabularies; the caller dispatches on the action union by
   * actionSet. */
  onAction: (action: ContextMenuAction) => void
  /** Which vocabulary to render. Defaults to z-order for FF-5
   * backward compat. */
  actionSet?: ContextMenuActionSet
}

interface MenuItem<A extends string> {
  action: A
  label: string
  testId: string
  Icon: typeof ChevronsUp
}

const Z_ORDER_ITEMS: MenuItem<ZIndexAction>[] = [
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

const ALIGN_ITEMS: MenuItem<AlignAction>[] = [
  {
    action: "left",
    label: "Align left",
    testId: "context-menu-action-align-left",
    Icon: AlignStartVertical,
  },
  {
    action: "center-horizontal",
    label: "Center horizontal",
    testId: "context-menu-action-align-center-horizontal",
    Icon: AlignCenterVertical,
  },
  {
    action: "right",
    label: "Align right",
    testId: "context-menu-action-align-right",
    Icon: AlignEndVertical,
  },
  {
    action: "top",
    label: "Align top",
    testId: "context-menu-action-align-top",
    Icon: AlignStartHorizontal,
  },
  {
    action: "center-vertical",
    label: "Center vertical",
    testId: "context-menu-action-align-center-vertical",
    Icon: AlignCenterHorizontal,
  },
  {
    action: "bottom",
    label: "Align bottom",
    testId: "context-menu-action-align-bottom",
    Icon: AlignEndHorizontal,
  },
]

export function CanvasContextMenu(props: CanvasContextMenuProps) {
  const { isOpen, position, onClose, onAction, actionSet = "z-order" } = props
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

  const items: Array<MenuItem<ZIndexAction> | MenuItem<AlignAction>> =
    actionSet === "align" ? ALIGN_ITEMS : Z_ORDER_ITEMS

  return createPortal(
    <div
      ref={menuRef}
      data-testid="canvas-context-menu"
      data-action-set={actionSet}
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
      {items.map((item) => {
        const { action, label, testId, Icon } = item
        return (
          <button
            key={action}
            type="button"
            role="menuitem"
            data-testid={testId}
            onClick={() => {
              onAction(action as ContextMenuAction)
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
        )
      })}
    </div>,
    document.body,
  )
}

export default CanvasContextMenu
