// Cmd/Ctrl + 1..5 interception — installed at module-import time,
// BEFORE React mounts. This guarantees the capture-phase listener is
// attached before any other code runs, eliminating every possible race
// window with the browser's Cmd+N tab-switch shortcut.
//
// The handler reads from module-scope state refs that the React layer
// updates. When the command bar is closed, the handler does nothing and
// normal browser Cmd+N tab switching works as expected.

import type { CommandAction } from "@/core/actionRegistry"

interface ShortcutState {
  isOpen: boolean
  results: CommandAction[]
  execute: ((action: CommandAction) => void) | null
  debug: boolean
}

// Module-level singleton — React components write, the listener reads.
const state: ShortcutState = {
  isOpen: false,
  results: [],
  execute: null,
  debug: typeof window !== "undefined"
    && (localStorage.getItem("debug_cmd_shortcuts") === "true"),
}

export function setCmdShortcutState(update: Partial<ShortcutState>): void {
  Object.assign(state, update)
  if (state.debug) {
    // eslint-disable-next-line no-console
    console.log("[cmd-shortcuts] state updated", {
      isOpen: state.isOpen,
      resultCount: state.results.length,
      hasExecute: !!state.execute,
    })
  }
}

function handleKeyDown(e: KeyboardEvent): void {
  // We only act when the command bar is open.
  if (!state.isOpen) return
  if (!(e.metaKey || e.ctrlKey)) return
  if (e.altKey || e.shiftKey) return   // don't interfere with other combos

  // Safari/Chrome report e.key = "1"; Firefox layouts vary — also check e.code
  const fromKey = parseInt(e.key, 10)
  const fromCode = e.code && e.code.startsWith("Digit")
    ? parseInt(e.code.slice(5), 10) : NaN
  const num = !Number.isNaN(fromKey) && fromKey >= 1 && fromKey <= 5
    ? fromKey
    : (!Number.isNaN(fromCode) && fromCode >= 1 && fromCode <= 5 ? fromCode : null)
  if (!num) return

  if (state.debug) {
    // eslint-disable-next-line no-console
    console.log("[cmd-shortcuts] intercepting Cmd+" + num, {
      key: e.key, code: e.code, metaKey: e.metaKey, ctrlKey: e.ctrlKey,
      target: state.results[num - 1]?.title || "(no target)",
    })
  }

  // CRITICAL: preventDefault first and unconditionally. We own this
  // shortcut while the bar is open, regardless of whether a matching
  // result exists yet.
  e.preventDefault()
  e.stopPropagation()
  const maybeStopImmediate = (e as KeyboardEvent & {
    stopImmediatePropagation?: () => void
  }).stopImmediatePropagation
  if (typeof maybeStopImmediate === "function") {
    maybeStopImmediate.call(e)
  }

  const target = state.results[num - 1]
  const exec = state.execute
  if (target && exec) {
    try {
      exec(target)
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[cmd-shortcuts] execute threw", err)
    }
  }
}

let installed = false

/** Install the capture-phase listener exactly once. Safe to call repeatedly. */
export function installCmdDigitShortcuts(): void {
  if (installed || typeof window === "undefined") return
  installed = true

  const opts: AddEventListenerOptions = { capture: true, passive: false }
  window.addEventListener("keydown", handleKeyDown, opts)
  document.addEventListener("keydown", handleKeyDown, opts)

  if (state.debug) {
    // eslint-disable-next-line no-console
    console.log("[cmd-shortcuts] listener installed on window + document (capture phase)")
  }
}
