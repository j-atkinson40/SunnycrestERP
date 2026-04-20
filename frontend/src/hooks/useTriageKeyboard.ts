/**
 * Keyboard shortcut binding for the triage workspace.
 *
 * Reads the active queue's `action_palette` from the triage
 * session context + binds each action's `keyboard_shortcut` to an
 * onPress handler supplied by the caller. Shortcut strings follow
 * the same convention as the backend config:
 *   - single key: "Enter", "r", "s", "n"
 *   - chord:      "shift+d", "shift+Enter"
 * All shortcut matches are case-insensitive for letters; special
 * keys use their JavaScript `KeyboardEvent.key` names.
 *
 * The hook ignores keydown events whose target is an input, textarea,
 * contenteditable, or aria-role="textbox" so that typing into a
 * reason field doesn't fire an action. Event listener runs at the
 * capture phase so it beats app-level shortcut handlers (e.g. Cmd+K).
 */

import { useEffect } from "react";
import type { TriageActionConfig } from "@/types/triage";

type OnPress = (action: TriageActionConfig) => void;

export function useTriageKeyboard(
  actions: TriageActionConfig[],
  onPress: OnPress,
  options: { enabled?: boolean } = {},
): void {
  const { enabled = true } = options;

  useEffect(() => {
    if (!enabled) return;

    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target) {
        const tag = target.tagName;
        if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
        if (target.isContentEditable) return;
        if (target.getAttribute("role") === "textbox") return;
      }

      for (const action of actions) {
        const shortcut = action.keyboard_shortcut;
        if (!shortcut) continue;
        if (_matches(shortcut, e)) {
          e.preventDefault();
          e.stopPropagation();
          onPress(action);
          return;
        }
      }
    };

    window.addEventListener("keydown", handler, { capture: true });
    return () => {
      window.removeEventListener("keydown", handler, { capture: true });
    };
  }, [actions, onPress, enabled]);
}

function _matches(shortcut: string, e: KeyboardEvent): boolean {
  const parts = shortcut.toLowerCase().split("+").map((p) => p.trim());
  const key = parts.pop() ?? "";
  const needShift = parts.includes("shift");
  const needAlt = parts.includes("alt") || parts.includes("option");
  const needMeta = parts.includes("cmd") || parts.includes("meta");
  const needCtrl = parts.includes("ctrl") || parts.includes("control");

  if (needShift !== e.shiftKey) return false;
  if (needAlt !== e.altKey) return false;
  if (needMeta !== e.metaKey) return false;
  if (needCtrl !== e.ctrlKey) return false;

  const eKey = e.key.toLowerCase();
  // "enter" / "escape" / "tab" / letter / digit.
  return eKey === key;
}
