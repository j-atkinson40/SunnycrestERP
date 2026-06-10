/**
 * ShortcutOverlay — the DESIGN_LANGUAGE §18.3 `?` cheat sheet.
 *
 * A shared one-screen overlay listing a surface's shortcuts, grouped by
 * task, in the §18.3 kbd treatment. One screen — if it scrolls, the
 * surface has too many shortcuts or the sheet is padding itself.
 *
 * Built on ui/dialog (base-ui): focus-trapped, Esc closes, backdrop
 * dismisses — the a11y canon for free. The `?`-binding lives in the
 * companion hook `useShortcutOverlayKey`, which applies the established
 * input-suppression discipline (INPUT/TEXTAREA/SELECT/contenteditable/
 * role=textbox never trigger it — the useTriageKeyboard precedent).
 *
 * NOTE: the tenant tree's legacy `core/KeyboardHelpOverlay` predates this
 * primitive (pre-DESIGN_LANGUAGE styling, prop-less). It is NOT mounted in
 * the admin tree (verified — no `?` collision there) and migrates onto this
 * primitive at follower velocity.
 */
import { useEffect } from "react"

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"
import { Kbd } from "@/components/ui/kbd"

export interface ShortcutItem {
  /** The resolved key string, e.g. "⌘ ↵", "⇧ click", "Esc". */
  keys: string
  label: string
}

export interface ShortcutGroup {
  /** The task this group serves, e.g. "Canvas", "Editing", "Assistant". */
  title: string
  shortcuts: ShortcutItem[]
}

export interface ShortcutOverlayProps {
  groups: ShortcutGroup[]
  open: boolean
  onOpenChange: (open: boolean) => void
  /** The surface's name for the dialog title, e.g. "Workflow editor". */
  surface?: string
}

export function ShortcutOverlay({
  groups,
  open,
  onOpenChange,
  surface,
}: ShortcutOverlayProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-lg"
        data-testid="shortcut-overlay"
      >
        <DialogHeader>
          <DialogTitle>
            {surface ? `${surface} shortcuts` : "Keyboard shortcuts"}
          </DialogTitle>
          <DialogDescription className="sr-only">
            The keyboard shortcuts available on this surface, grouped by
            task. Press Escape to close.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          {groups.map((group) => (
            <div key={group.title} className="space-y-2">
              <div className="text-micro uppercase tracking-wider text-content-muted">
                {group.title}
              </div>
              <ul className="space-y-1">
                {group.shortcuts.map((s) => (
                  <li
                    key={`${group.title}-${s.keys}-${s.label}`}
                    className="flex items-center justify-between gap-3 text-body-sm text-content-base"
                  >
                    <span>{s.label}</span>
                    <Kbd className="shrink-0 tabular-nums">{s.keys}</Kbd>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="border-t border-border-subtle pt-2 text-caption text-content-muted">
          Press <Kbd>?</Kbd> again or <Kbd>Esc</Kbd> to close
        </div>
      </DialogContent>
    </Dialog>
  )
}

/**
 * Binds `?` (no modifiers, no focused input) to toggle the overlay.
 * Input-suppression per the established useTriageKeyboard discipline.
 */
export function useShortcutOverlayKey(
  setOpen: (updater: (open: boolean) => boolean) => void,
) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key !== "?" || e.metaKey || e.ctrlKey || e.altKey) return
      const target = e.target as HTMLElement | null
      if (target) {
        const tag = target.tagName
        if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return
        if (target.isContentEditable) return
        if (target.getAttribute("role") === "textbox") return
      }
      e.preventDefault()
      setOpen((v) => !v)
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [setOpen])
}
